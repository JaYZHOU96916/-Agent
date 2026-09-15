from functools import lru_cache
from pathlib import Path

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime settings for the backend and isolated executor."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    sandbox_image: str = "data-analysis-sandbox:latest"
    sandbox_timeout_seconds: PositiveInt = Field(default=10, le=10)
    sandbox_memory_limit_mb: PositiveInt = Field(default=512, le=512)
    sandbox_cpu_nano_cpus: PositiveInt = Field(default=1_000_000_000, le=1_000_000_000)
    sandbox_pids_limit: PositiveInt = Field(default=64, le=64)
    dataset_dir: Path = Path("uploads")
    upload_max_bytes: PositiveInt = 20 * 1024 * 1024
    dataset_max_rows: PositiveInt = 100_000
    dataset_max_columns: PositiveInt = 200
    dataset_max_memory_bytes: PositiveInt = 128 * 1024 * 1024
    profiling_timeout_seconds: PositiveInt = 30
    profiling_concurrency: PositiveInt = 2


@lru_cache
def get_settings() -> Settings:
    return Settings()
