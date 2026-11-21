from typing import Literal
from pydantic import BaseModel, Field


class FindingOutput(BaseModel):
    path: str
    start_line: int = Field(ge=1)
    end_line: int = Field(ge=1)
    category: Literal['bug', 'security', 'performance', 'maintainability', 'style']
    severity: Literal['critical', 'high', 'medium', 'low', 'informational']
    title: str
    explanation: str
    evidence: str
    assumptions: str = ''
    suggested_fix: str = ''
    verification_test: str = ''
    rule_id: str = ''


class ReviewOutput(BaseModel):
    findings: list[FindingOutput] = Field(max_length=100)


class ArtifactOutput(BaseModel):
    markdown: str
    proposed_code: str = ''


class ProjectInput(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class CodeInput(BaseModel):
    path: str = 'main.py'
    code: str = Field(min_length=1, max_length=100000)


class JobInput(BaseModel):
    mode: Literal['static', 'ai', 'hybrid'] = 'hybrid'
    models: list[str] = Field(default_factory=lambda: ['qwen2.5-coder:1.5b'], min_length=1, max_length=3)
    task: Literal['review', 'explanation', 'documentation', 'tests', 'patch', 'docstrings', 'readme'] = 'review'
    path: str | None = None
    symbol: str | None = None
    audience: Literal['beginner', 'intermediate'] = 'beginner'


class FeedbackInput(BaseModel):
    verdict: Literal['useful', 'false_positive', 'unclear']
