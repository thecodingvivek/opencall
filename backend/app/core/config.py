from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OpenCall API"
    debug: bool = False
    database_url: SecretStr | None = Field(default=None, validation_alias=AliasChoices("DATABASE_URL", "poolurl", "URL"))
    database_ssl_root_cert: Path | None = None
    database_ssl_root_cert_pem: SecretStr | None = None
    firebase_service_account_path: Path = Path(__file__).resolve().parents[2] / "service.json"
    firebase_service_account_json: SecretStr | None = None
    gnani_api_key: SecretStr | None = None
    groq_api_key: SecretStr | None = None
    groq_fallback_api_key: SecretStr | None = None
    geoapify_api_key: SecretStr | None = None
    groq_model: str = "openai/gpt-oss-20b"
    # Used for a reply when groq_model errors or is slow; empty disables the backup.
    groq_fallback_model: str = "openai/gpt-oss-120b"
    groq_summary_model: str = "qwen/qwen3.8-27b"
    livekit_url: str = "ws://127.0.0.1:7880"
    livekit_api_key: str = "devkey"
    livekit_api_secret: SecretStr = SecretStr("secret")
    conversation_max_seconds: int = 180
    voice_worker_port: int = 8081
    voice_agent_remote: bool = False
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://opencalll.vercel.app",
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()
