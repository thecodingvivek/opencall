from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class ObservabilitySettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[1] / ".env",
        env_prefix="PHOENIX_", extra="ignore",
    )
    enabled: bool = True
    project_name: str = "opencall"
    collector_endpoint: str = "http://127.0.0.1:6006/v1/traces"
    port: int = 6006
    capture_content: bool = False


@lru_cache
def get_observability_settings() -> ObservabilitySettings:
    return ObservabilitySettings()
