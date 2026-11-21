import json
from app.analysis import run_static, validate_finding, deduplicate
from app.context import source_index, build_context
from app.schemas import FindingOutput


def finding(**kwargs):
    return FindingOutput(**({'path':'main.py','start_line':1,'end_line':1,'category':'bug','severity':'medium','title':'Issue','explanation':'Explanation','evidence':'x = 1'} | kwargs))


def test_evidence_validation():
    files = {'main.py':'x = 1\n'}
    assert validate_finding(finding(), files)['validation'] == 'evidence_matched'
    assert validate_finding(finding(start_line=90, end_line=90), files)['validation'] == 'invalid_location'
    assert validate_finding(finding(evidence='x = 2'), files)['validation'] == 'unsupported_evidence'
    assert validate_finding(finding(path='missing.py'), files)['validation'] == 'invalid_location'


def test_dedup_preserves_sources_and_distinct_issues():
    a = validate_finding(finding(), {'main.py':'x = 1'}, 'ruff')
    b = validate_finding(finding(), {'main.py':'x = 1'}, 'llm')
    c = validate_finding(finding(title='Different diagnosis'), {'main.py':'x = 1'})
    result = deduplicate([a,b,c])
    assert len(result) == 2
    assert result[0]['sources'] == ['llm','ruff']


def test_ast_and_context_budget():
    source = 'import math\n\n@decorator\ndef calculate(x):\n    return math.sqrt(x)\n'
    index = source_index('main.py', source)
    assert index['symbols'][0]['start'] == 3
    assert index['symbols'][0]['signature'] == 'calculate(x)'
    context, coverage = build_context({'main.py':source}, 1000)
    assert coverage['complete']
    assert json.loads(context)[0]['start_line'] == 1
    _, coverage = build_context({'main.py':source}, 50)
    assert not coverage['complete'] and coverage['omitted_units']
    assert source_index('bad.py','def (')['syntax_error']


def test_real_static_tools_and_no_execution(tmp_path):
    marker = tmp_path / 'must-not-exist'
    source = f'import subprocess\nfrom pathlib import Path\nPath({str(marker)!r}).write_text("executed")\ndef add(x, items=[]):\n    items.append(x)\n    return items\nsubprocess.run("echo hello", shell=True)\n'
    findings, errors, raw = run_static({'main.py':source})
    assert not marker.exists()
    assert not errors
    assert {'ruff','bandit'} <= set(raw)
    assert any(f['rule_id']=='B006' for f in findings)
    assert any(f['category']=='security' for f in findings)
    assert all(f['validation']=='evidence_matched' for f in findings)


def test_syntax_error_is_a_finding():
    findings, _, _ = run_static({'bad.py':'def broken(:\n    pass\n'})
    assert any(f['rule_id']=='syntax-error' for f in findings)
