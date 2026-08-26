"""
Centralized configuration.

Everything that differs between local / docker / on-prem deployment is
read from the environment here, and nowhere else in the codebase. This
keeps configuration separated from business logic (a requirement of the
solution brief) and means the same image can be promoted between
environments by changing env vars only.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    secret_key: str = "change-me-in-production"
    log_level: str = "INFO"  # DEBUG | INFO | WARNING | ERROR

    database_url: str = "sqlite:///./eco_review_dev.db"

    # AI provider abstraction — see app/services/ai_provider.py
    ai_provider: str = "mock"          # mock | openai
    openai_api_key: str = ""
    openai_model: str = "claude-sonnet-4-6"

    document_storage_path: str = "./storage/documents"

    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    rules_dir: str = str(Path(__file__).parent / "rules")
    ml_model_path: str = str(Path(__file__).parent / "ml" / "artifacts")

    # Integration adapters — mock | live
    portal_adapter: str = "mock"
    portal_base_url: str = ""
    portal_api_key: str = ""

    messaging_adapter: str = "mock"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    # Translation adapter — mock | live
    translation_adapter: str = "mock"
    translation_base_url: str = "http://localhost:5000"
    translation_api_key: str = ""

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
