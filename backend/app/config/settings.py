from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix='PDF_', env_file='.env', extra='ignore')
    storage: Path = Path('storage')
    workers: int = Field(1, ge=1, le=4)
    max_upload_mb: int = Field(100, ge=1, le=1000)
    max_pages: int = Field(1000, ge=1, le=10000)
    timeout_seconds: int = Field(1800, ge=10)
    memory_mb: int = Field(10000, ge=512)
    device: str = 'cpu'
    marker_python: str = ''
    cors_origins: list[str] = ['http://localhost:5173', 'http://127.0.0.1:5173']

settings = Settings()
settings.storage = settings.storage.resolve()
for folder in ('originals', 'documents', 'tmp'):
    (settings.storage / folder).mkdir(parents=True, exist_ok=True)
