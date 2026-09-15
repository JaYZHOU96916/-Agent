from functools import lru_cache

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
