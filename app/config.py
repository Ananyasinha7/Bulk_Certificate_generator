import os
from pathlib import Path

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


def default_workers() -> int:
    return min(os.cpu_count() or 1, 8)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./certificates.db"
    storage_dir: Path = Path("./storage")
    max_recipients: PositiveInt = 10000
    render_workers: PositiveInt = Field(default_factory=default_workers)
    batch_size: PositiveInt = 50
