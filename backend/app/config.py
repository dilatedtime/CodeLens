from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')
    database_url: str = 'sqlite:///./data/codelens.db'
    queue_mode: str = 'local'
    redis_url: str = 'redis://localhost:6379/0'
    ollama_url: str = 'http://localhost:11434'
    allowed_models: str = 'qwen2.5-coder:1.5b,deepseek-coder:1.3b,codellama:7b'
    default_model: str = 'qwen2.5-coder:1.5b'
    model_timeout: int = 180
    context_chars: int = 12000
    context_tokens: int = 8192
    output_tokens: int = 2048
    temperature: float = 0.1
    max_file_bytes: int = 100000
    max_upload_bytes: int = 2000000
    max_files: int = 30
    job_stale_seconds: int = 2400
    cors_origins: str = 'http://localhost:5173,http://127.0.0.1:5173,http://localhost:4173,http://127.0.0.1:4173'

    @property
    def models(self):
        return [x.strip() for x in self.allowed_models.split(',') if x.strip()]


settings = Settings()
Path('data').mkdir(exist_ok=True)
