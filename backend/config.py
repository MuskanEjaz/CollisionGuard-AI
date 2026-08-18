# Application settings loaded from environment variables / .env file.
#
# Usage anywhere in the backend:
#   from config import get_settings
#   settings = get_settings()
#
# CREDENTIAL SECURITY:
#   All watsonx fields have empty-string defaults so the app starts
#   without credentials (falls back to deterministic ranking).
#   Credential values must never appear in logs, errors, or API responses.
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Application
    app_env: str = "development"
    app_version: str = "0.1.0"

    # Server
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    cors_origin: str = "http://localhost:5173"

    # IBM watsonx.ai credentials (Phase 6+)
    # Canonical env var names match IBM documentation: WATSONX_APIKEY etc.
    # pydantic-settings maps field name -> env var by lowercasing the field.
    # Field "watsonx_apikey" reads WATSONX_APIKEY from the environment.
    watsonx_apikey: str = ""        # WATSONX_APIKEY  (no underscore between API and KEY)
    watsonx_project_id: str = ""    # WATSONX_PROJECT_ID
    watsonx_url: str = ""           # WATSONX_URL  (must be HTTPS for live calls)

    # Configurable model ID -- never hardcode a model assumption in client code.
    # Default is a reasonable Granite model; override via WATSONX_MODEL_ID in .env.
    watsonx_model_id: str = "ibm/granite-3-8b-instruct"  # WATSONX_MODEL_ID

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Cached -- one read per process. Call get_settings.cache_clear() in tests
    # that override settings via environment variables.
    return Settings()
