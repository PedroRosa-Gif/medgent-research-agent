"""Application configuration.

Framework-light settings loaded from environment variables (and an optional
``.env`` file) via ``pydantic-settings``. Keep this module dependency-free
beyond Pydantic so it can be imported from anywhere without pulling in heavy
adapters.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration sourced from the environment.

    Secrets are optional so the app can boot with the local Ollama provider and
    no external API keys. Populate them (via ``.env`` or real env vars) to enable
    the corresponding providers/integrations.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # LLM provider selection. Local Ollama is the zero-config default.
    llm_provider: str = "ollama"

    # Optional provider / integration credentials (empty by default).
    groq_api_key: str | None = None
    gemini_api_key: str | None = None
    ncbi_api_key: str | None = None
    langsmith_api_key: str | None = None


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    The ``lru_cache`` ensures the environment is read once per process and the
    same instance is reused across the application.
    """
    return Settings()
