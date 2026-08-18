"""
Application settings loaded from environment variables / .env file.

Usage anywhere in the backend:
    from config import get_settings
    settings = get_settings()
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    app_env: str = "development"
    app_version: str = "0.1.0"

    # ── Server ────────────────────────────────────────────────────────────────
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origin: str = "http://localhost:5173"

    # ── IBM watsonx.ai — Phase 2+, unused in Phase 1 ─────────────────────────
    watsonx_api_key: str = ""
    watsonx_project_id: str = ""
    watsonx_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        # Extra fields from .env are ignored rather than raising an error
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached Settings instance (one read per process)."""
    return Settings()
