import json
import os
import re
from typing import Protocol, Any
import httpx
from pydantic import ValidationError
from .config import settings
from .prompts import SYSTEM
from .schemas import ReviewOutput, ArtifactOutput, FindingOutput


class ProviderError(Exception):
    def __init__(self, message, raw='', failures=0):
        super().__init__(message)
        self.raw = raw
        self.failures = failures


class ModelProvider(Protocol):
    def models(self) -> list[dict]: ...
    def generate(self, model: str, prompt: str, schema: Any) -> tuple[Any, str, dict]: ...


class MockSimulationProvider:
    """High-fidelity offline simulation provider for testing, viva demos,

    and environments without local GPU / Ollama running.
    """

    MOCK_MODELS = [
        {'name': 'mock:qwen2.5-coder', 'model': 'mock:qwen2.5-coder', 'digest': 'sha256:mock_qwen_2_5_1_5b'},
        {'name': 'mock:deepseek-coder', 'model': 'mock:deepseek-coder', 'digest': 'sha256:mock_deepseek_1_3b'},
        {'name': 'mock:codellama', 'model': 'mock:codellama', 'digest': 'sha256:mock_codellama_7b'},
    ]

    def models(self):
        return self.MOCK_MODELS

    def generate(self, model: str, prompt: str, schema: Any):
        # Extract source data from prompt
        source_match = re.search(r'<source_data>\s*(\[.*?\])\s*</source_data>', prompt, re.DOTALL)
        source_units = []
        if source_match:
            try:
                source_units = json.loads(source_match.group(1))
            except Exception:
                pass

        if schema == ReviewOutput:
            findings = []
            for unit in source_units:
                path = unit.get('path', 'main.py')
                code = unit.get('code', '')
                lines = code.splitlines()

                # Look for common bug patterns in code
                for idx, line in enumerate(lines, start=unit.get('start_line', 1)):
                    # Mutable default
                    if 'def ' in line and re.search(r'=\s*(\[\]|\{\})', line):
                        findings.append(FindingOutput(
                            path=path,
                            start_line=idx,
                            end_line=idx,
                            category='bug',
                            severity='medium',
                            title='Dangerous mutable default argument detected',
                            explanation='Python default argument expressions are evaluated once when the function definition is executed, creating shared state between calls.',
                            evidence=line.strip(),
                            assumptions='Function is called repeatedly without explicitly supplying the argument.',
                            suggested_fix='Use None as default parameter, and initialize a new container inside function body if param is None.',
                            verification_test='def test_shared_state():\n    assert func() is not func()',
                            rule_id='AI_B006',
                        ))
                    # Inefficient search / O(n) in loop
                    if 'for ' in line and ' in ' in line and any(k in line for k in ('range', 'list', 'items')):
                        if idx + 1 <= len(lines):
                            next_line = lines[idx] if idx < len(lines) else ''
                            if 'if ' in next_line and ' in ' in next_line:
                                findings.append(FindingOutput(
                                    path=path,
                                    start_line=idx,
                                    end_line=min(idx + 1, unit.get('end_line', idx + 1)),
                                    category='performance',
                                    severity='medium',
                                    title='Potential O(N^2) quadratic search inside loop',
                                    explanation='Performing membership checks on a list inside an iterative loop results in quadratic O(N^2) time complexity.',
                                    evidence=line.strip(),
                                    assumptions='Collection contains large number of elements.',
                                    suggested_fix='Convert the collection to a set or dictionary prior to the loop for O(1) average lookup time.',
                                    verification_test='Benchmark with 10,000 items to observe linear vs quadratic scaling.',
                                    rule_id='AI_PERF01',
                                ))
                    # SQL Injection / f-string query
                    if re.search(r'(SELECT|INSERT|UPDATE|DELETE).*f[\'"]', line, re.IGNORECASE):
                        findings.append(FindingOutput(
                            path=path,
                            start_line=idx,
                            end_line=idx,
                            category='security',
                            severity='critical',
                            title='SQL Injection vulnerability via formatted string query',
                            explanation='Constructing raw SQL queries via string formatting or f-strings allows attackers to bypass authentication and extract data.',
                            evidence=line.strip(),
                            assumptions='Input parameters originate from untrusted external user input.',
                            suggested_fix='Use parameterized queries with prepared statements (e.g. cursor.execute("SELECT ... WHERE id = ?", (user_id,)))',
                            verification_test='Pass "\' OR \'1\'=\'1" and ensure query does not alter SQL syntax.',
                            rule_id='AI_SQLI',
                        ))

            # Fallback finding if no pattern matched
            if not findings and source_units:
                u = source_units[0]
                findings.append(FindingOutput(
                    path=u.get('path', 'main.py'),
                    start_line=u.get('start_line', 1),
                    end_line=min(u.get('start_line', 1) + 2, u.get('end_line', 3)),
                    category='maintainability',
                    severity='informational',
                    title='Code Structure and Documentation Review',
                    explanation='Code analyzed successfully with simulated inference model. Consider adding type annotations and module-level docstrings.',
                    evidence=u.get('code', '').splitlines()[0] if u.get('code') else 'def main():',
                    assumptions='Source code syntax is valid.',
                    suggested_fix='Add PEP 484 type hints to function signatures.',
                    verification_test='Run `mypy .` to verify static typing compliance.',
                    rule_id='AI_CLEAN',
                ))

            parsed = ReviewOutput(findings=findings)
            raw = parsed.model_dump_json(indent=2)
            metrics = {
                'provider': 'MockSimulationProvider',
                'digest': 'sha256:mock_simulated_inference',
                'eval_count': 350,
                'prompt_eval_count': 120,
                'simulated': True,
                'schema_failures': 0,
            }
            return parsed, raw, metrics

        elif schema == ArtifactOutput:
            markdown = (
                "# CodeLens Analysis Artifact\n\n"
                "### Algorithm & Architecture Overview\n"
                "- **Primary Language**: Python 3.11+\n"
                "- **Computational Complexity**: O(N) average time, O(1) space auxiliary\n"
                "- **Design Pattern**: Modular single-responsibility services\n\n"
                "### Key Improvements & Recommendations\n"
                "1. **Input Sanitization**: Validate all external parameters before execution.\n"
                "2. **Error Handling**: Replace broad exception catches with domain-specific errors.\n"
                "3. **Type Safety**: Introduce `typing.Optional` and Pydantic models for request bodies.\n"
            )
            proposed = (
                "# Proposed optimized implementation\n"
                "from typing import Optional, List\n\n"
                "def process_items(items: Optional[List[str]] = None) -> List[str]:\n"
                "    \"\"\"Safely processes items avoiding mutable default arguments.\"\"\"\n"
                "    if items is None:\n"
                "        items = []\n"
                "    return [item.strip() for item in items if item]\n"
            )
            parsed = ArtifactOutput(markdown=markdown, proposed_code=proposed)
            raw = parsed.model_dump_json(indent=2)
            metrics = {'provider': 'MockSimulationProvider', 'simulated': True, 'schema_failures': 0}
            return parsed, raw, metrics

        raise ProviderError(f'Unsupported schema: {schema}')


class OllamaProvider:
    def models(self):
        try:
            response = httpx.get(f'{settings.ollama_url}/api/tags', timeout=3)
            response.raise_for_status()
            return response.json().get('models', [])
        except (httpx.HTTPError, ValueError):
            raise ProviderError('Ollama is unavailable. Start Ollama and install a configured model; static analysis remains available.')

    def generate(self, model: str, prompt: str, schema: Any):
        installed = self.models()
        match = next((m for m in installed if m.get('name') == model or m.get('model') == model), None)
        if not match:
            raise ProviderError(f'Model {model} is not installed. Run: ollama pull {model}')
        messages = [{'role': 'system', 'content': SYSTEM}, {'role': 'user', 'content': prompt}]
        raw, failures = '', 0
        options = {'temperature': settings.temperature, 'num_ctx': settings.context_tokens, 'num_predict': settings.output_tokens, 'seed': 42}
        for attempt in range(2):
            try:
                response = httpx.post(f'{settings.ollama_url}/api/chat', timeout=settings.model_timeout,
                    json={'model': model, 'stream': False, 'keep_alive': 0, 'messages': messages, 'format': schema.model_json_schema(), 'options': options})
                response.raise_for_status()
                result = response.json()
                raw = result['message']['content']
                parsed = schema.model_validate_json(raw)
                metrics = {k: result.get(k) for k in ('total_duration', 'load_duration', 'prompt_eval_count', 'eval_count', 'prompt_eval_duration', 'eval_duration')}
                metrics.update({'digest': match.get('digest'), 'options': options, 'schema_failures': failures})
                return parsed, raw, metrics
            except (ValidationError, KeyError, ValueError):
                failures += 1
                if attempt == 0:
                    messages.append({'role': 'user', 'content': 'Previous response was invalid. Return valid JSON with every required schema field. Do not add markdown fences.'})
            except httpx.HTTPError as exc:
                raise ProviderError(f'Ollama request failed ({type(exc).__name__}). Check server availability and timeout settings.', raw, failures)
        raise ProviderError('Model response failed schema validation after one repair attempt.', raw, failures)


def get_default_provider() -> ModelProvider:
    """Returns OllamaProvider if Ollama is accessible, or MockSimulationProvider as fallback."""
    if os.environ.get('CODELENS_MOCK_AI', '').lower() in ('1', 'true', 'yes'):
        return MockSimulationProvider()
    try:
        provider = OllamaProvider()
        provider.models()
        return provider
    except ProviderError:
        return OllamaProvider()
