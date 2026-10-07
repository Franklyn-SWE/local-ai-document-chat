"""
Purpose:
    Defines and validates application configuration loaded from environment variables.

Place in the system:
    This module is the single configuration boundary used by the API and later
    corpus, retrieval, inference, and observability components.
"""

from functools import lru_cache

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration for the application."""

    llm_url: HttpUrl = Field(alias="LLM_URL")
    llm_model: str = Field(min_length=1, alias="LLM_MODEL")
    data_dir: str = Field(default="/data", alias="DATA_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return the validated application settings."""
    return Settings()