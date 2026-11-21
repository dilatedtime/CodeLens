import ast
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from .schemas import FindingOutput
from .metrics import analyze_code_smells, analyze_file_metrics, compute_project_score

RULE_GUIDANCE = {
    'B006': ('Use None as the default, then create a new list or dictionary inside the function. Preserve an explicitly supplied collection.', 'Call the function twice without passing the collection and confirm the calls do not share state.'),
    'F401': ('Remove the unused import, or make its intended use explicit. Check for deliberate re-exports before removing it.', 'Run the project tests and check any public import paths after changing imports.'),
    'B602': ('Prefer a fixed executable and argument list with shell=False. Validate untrusted arguments for the target program as well.', 'Check normal inputs and shell metacharacters; confirm input is passed as data, not interpreted as a shell command.'),
    'B307': ('Replace eval with a parser appropriate to the expected data, such as JSON parsing or numeric conversion.', 'Test valid values and malformed or executable input; the latter must be rejected.'),
    'B608': ('Use the database driver\'s parameterized query API. Keep SQL structure separate from user-supplied values.', 'Test names containing quotes and SQL-looking text and confirm they are treated as values.'),
    'B101': ('Do not use assert statements for runtime data validation or authorization checks because Python optimizes them out with -O.', 'Run python -O and verify that critical validations still throw proper exceptions.'),
    'B301': ('Do not use pickle for deserializing untrusted data. Use safer formats such as JSON or Protocol Buffers.', 'Attempt deserializing malformed and untrusted payload; ensure code execution is prevented.'),
    'B506': ('Use yaml.safe_load() instead of yaml.load() to prevent arbitrary object instantiation.', 'Verify that custom tags like !!python/object/apply cannot execute system commands.'),
    'SEC001': ('Extract hardcoded secrets into secure environment variables (.env) or a secret manager.', 'Check that secrets are not committed into source control and are loaded dynamically at runtime.'),
    'SMELL_GOD_FUNC': ('Decompose large functions into smaller helper functions with single responsibilities.', 'Add unit tests for each refactored helper function to ensure behavioral equivalence.'),
    'ERR001': ('Catch specific exceptions instead of a bare `except:` to prevent masking SystemExit and KeyboardInterrupt.', 'Trigger a KeyboardInterrupt or specific failure and confirm it behaves as expected.'),
    'DEAD001': ('Remove unreachable dead code to keep the codebase clean and avoid confusion.', 'Run test suite to verify code coverage and ensure no branch is unintentionally discarded.'),
}


def validate_finding(finding, files, source='llm'):
    data = finding.model_dump() if isinstance(finding, FindingOutput) else dict(finding)
    data['sources'] = data.get('sources', [source])
    lines = files.get(data['path'], '').splitlines()
    start, end = data['start_line'], data['end_line']
    if not (1 <= start <= end <= len(lines)):
        data['validation'] = 'invalid_location'
    elif not data.get('evidence', '').strip() or data['evidence'].strip() not in '\n'.join(lines[start-1:end]):
        data['validation'] = 'unsupported_evidence'
    else:
        data['validation'] = 'evidence_matched'
    return data


def deduplicate(findings):
    merged = []
    for item in findings:
        # Conservative: different diagnoses on the same line must remain separate.
        key = (item['path'], item['start_line'], item['end_line'], item['category'], item.get('rule_id') or item['title'].casefold())
        existing = next((x for x in merged if x['_key'] == key), None)
        if existing:
            existing['sources'] = sorted(set(existing['sources'] + item['sources']))
        else:
            merged.append({**item, '_key': key})
    return [{k: v for k, v in x.items() if k != '_key'} for x in merged]


def run_static(files):
    findings, errors, raw = [], [], {}
    file_metrics = []

    def add(path, start, end, category, severity, title, rule, source):
        lines = files[path].splitlines()
        end = min(max(start, end), len(lines))
        item = FindingOutput(path=path, start_line=max(1, start), end_line=max(1, end), category=category,
            severity=severity, title=title, explanation=title, evidence='\n'.join(lines[start-1:end]), rule_id=rule,
            assumptions='Static tool diagnostic; inspect applicability.', suggested_fix='Inspect the highlighted code and the rule documentation before changing behavior.')
        if rule in RULE_GUIDANCE:
            item.suggested_fix, item.verification_test = RULE_GUIDANCE[rule]
        findings.append(validate_finding(item, files, source))

    # Phase 1: Pure AST Analysis (Complexity, Halstead, and Code Smells)
    for path, content in files.items():
        try:
            m = analyze_file_metrics(path, content)
            file_metrics.append(m)
            # Add AST code smells as deterministic findings
            for smell in m.get('smells', []):
                add(path, smell['start_line'], smell['end_line'], smell['category'],
                    smell['severity'], smell['title'], smell['rule_id'], smell.get('sources', ['ast-analyzer'])[0])
        except Exception as exc:
            errors.append(f'{path}: AST metrics analysis failed ({type(exc).__name__})')

    # Phase 2: External Linters (Ruff and Bandit)
    with tempfile.TemporaryDirectory(prefix='codelens-') as directory:
        root = Path(directory)
        for path, content in files.items():
            target = root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
            try:
                ast.parse(content)
            except SyntaxError as exc:
                add(path, exc.lineno or 1, exc.lineno or 1, 'bug', 'high', exc.msg, 'syntax-error', 'python-ast')
            except (ValueError, RecursionError) as exc:
                errors.append(f'{path}: parsing failed ({type(exc).__name__})')
        commands = {
            'ruff': [sys.executable, '-I', '-m', 'ruff', 'check', '--isolated', '--no-cache', '--ignore-noqa', '--no-respect-gitignore', '--select', 'E,F,B,SIM', '--output-format', 'json', *[str(root / path) for path in files]],
            'bandit': [sys.executable, '-I', '-m', 'bandit', '-r', '.', '-f', 'json', '--ignore-nosec', '-q'],
        }
        for tool, command in commands.items():
            try:
                result = subprocess.run(command, cwd=root, capture_output=True, text=True, encoding='utf-8', timeout=40, shell=False)
                if result.returncode not in (0, 1):
                    raise ValueError(f'exit code {result.returncode}')
                payload = json.loads(result.stdout)
                raw[tool] = payload
                items = payload if tool == 'ruff' else payload.get('results', [])
                if tool == 'bandit' and payload.get('errors'):
                    errors.extend(f"Bandit skipped {Path(e.get('filename', '')).name}: {e.get('reason', 'parse error')}" for e in payload['errors'])
                for item in items:
                    candidate = Path(item['filename'])
                    path = candidate.resolve().relative_to(root.resolve()).as_posix() if candidate.is_absolute() else candidate.as_posix().removeprefix('./')
                    if path not in files:
                        continue
                    if tool == 'ruff':
                        rule = item.get('code') or 'syntax-error'
                        add(path, item['location']['row'], item.get('end_location', item['location'])['row'],
                            'bug' if rule.startswith(('F', 'B')) or rule == 'syntax-error' else 'style',
                            'medium' if rule.startswith(('F', 'B')) else 'low', item['message'], rule, tool)
                    else:
                        add(path, item['line_number'], max(item.get('line_range') or [item['line_number']]), 'security',
                            item['issue_severity'].lower(), item['issue_text'], item['test_id'], tool)
            except (subprocess.TimeoutExpired, OSError, ValueError, KeyError) as exc:
                errors.append(f'{tool} analysis failed ({type(exc).__name__}). Verify the analyzer installation.')

    deduped_findings = deduplicate(findings)
    raw['metrics'] = file_metrics
    raw['score'] = compute_project_score(file_metrics, deduped_findings)
    return deduped_findings, errors, raw
