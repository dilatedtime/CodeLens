"""Export the actual Pydantic contracts used by the application."""
import json
from pathlib import Path
from app.schemas import ReviewOutput, ArtifactOutput, JobInput

target = Path(__file__).parent.parent / 'docs' / 'schemas'
target.mkdir(parents=True, exist_ok=True)
for schema in (ReviewOutput, ArtifactOutput, JobInput):
    (target / f'{schema.__name__}.json').write_text(json.dumps(schema.model_json_schema(), indent=2), encoding='utf-8')
print('Exported three JSON schemas.')
