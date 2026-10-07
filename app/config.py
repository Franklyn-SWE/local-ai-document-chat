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

    corpus_poll_interval_seconds: float = Field(
        default=1.0,
        gt=0,
        alias="CORPUS_POLL_INTERVAL_SECONDS",
    )

    corpus_stability_delay_seconds: float = Field(
        default=0.5,
        gt=0,
        alias="CORPUS_STABILITY_DELAY_SECONDS",
    )

    chunk_size_chars: int = Field(
        default=1600,
        gt=0,
        alias="CHUNK_SIZE_CHARS",
    )

    chunk_overlap_chars: int = Field(
        default=200,
        ge=0,
        alias="CHUNK_OVERLAP_CHARS",
    )
   # Maximum number of top-ranked chunks considered before context budgeting.
    retrieval_top_k: int = Field(
        default=8,
        gt=0,
        alias="RETRIEVAL_TOP_K",
    )
   # Minimum lexical relevance score required for a chunk to remain evidence
    retrieval_min_score: float = Field(
        default=0.10,
        ge=0,
        alias="RETRIEVAL_MIN_SCORE",
    )
   # Maximum estimated token allowance for retrieved evidence sent to the model
    context_token_budget: int = Field(
        default=1800,
        gt=0,
        alias="CONTEXT_TOKEN_BUDGET",
    )

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
    settings = Settings()

    if settings.chunk_overlap_chars >= settings.chunk_size_chars:
        raise ValueError(
            "CHUNK_OVERLAP_CHARS must be smaller than CHUNK_SIZE_CHARS"
        )

    return settings