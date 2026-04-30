"""
Centralized application settings using Pydantic Settings.

All configuration is loaded from environment variables (or .env file)
with validation and sensible defaults. Import `settings` singleton everywhere.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="app/.env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── API Keys ──────────────────────────────────────────────
    openai_api_key: str = Field(default="", description="OpenAI API key")

    # ── LLM Models ────────────────────────────────────────────
    llm_model_name: str = Field(default="gpt-4o-mini", description="Primary LLM model")
    embedding_model_name: str = Field(
        default="text-embedding-3-small", description="Embedding model"
    )

    # ── FAISS retrieval (index + metadata on disk; bundled in image or mounted) ─
    faiss_index_path: str = Field(default="app/scm_index_v2.faiss")
    faiss_metadata_path: str = Field(default="app/scm_metadata_v2.pkl")
    top_k_results: int = Field(default=10, ge=1, le=100)
    semantic_similarity_weight: float = Field(default=0.8, ge=0.0, le=1.0)
    claim_volume_weight: float = Field(default=0.2, ge=0.0, le=1.0)

    # ── LLM Resilience ────────────────────────────────────────
    max_retries: int = Field(default=3, ge=1, le=10)
    llm_timeout: float = Field(default=30.0, ge=1.0, description="Seconds per LLM call")
    retry_base_delay: float = Field(default=1.0, ge=0.1)

    # ── Circuit Breaker ───────────────────────────────────────
    circuit_breaker_failure_threshold: int = Field(default=5, ge=1)
    circuit_breaker_recovery_timeout: float = Field(
        default=30.0, ge=5.0, description="Seconds before half-open"
    )
    circuit_breaker_window: float = Field(
        default=60.0, ge=10.0, description="Failure counting window in seconds"
    )

    # ── Workflow ──────────────────────────────────────────────
    workflow_max_retries: int = Field(default=2, ge=0, le=5)
    confidence_threshold: float = Field(
        default=0.6, ge=0.0, le=1.0,
        description="Min confidence to accept service code selection without retry",
    )
    clarification_score_gap: float = Field(
        default=0.10, ge=0.0, le=1.0,
        description="If top-2 codes are within this gap, request clarification",
    )

    # ── Rate Limiting ─────────────────────────────────────────
    rate_limit_rpm: int = Field(default=60, ge=0, description="Requests per minute per IP; 0=disabled")
    request_timeout_seconds: float = Field(default=30.0, ge=5.0)

    # ── Observability ─────────────────────────────────────────
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json", description="'json' or 'text'")
    enable_tracing: bool = Field(default=False)
    trace_sample_ratio: float = Field(
        default=0.05, ge=0.0, le=1.0,
        description="OpenTelemetry trace sampling ratio (0.0-1.0)",
    )
    environment: str = Field(default="development")

    # ── Warm FAISS at API startup (env: PRELOAD_FAISS) ─
    preload_faiss: bool = Field(
        default=True,
        description="If true, load FAISS index + metadata into memory at startup",
    )

    # ── GCP (kept for compatibility) ──────────────────────────
    gcp_project_id: str = Field(default="gen-lang-client-0281947410")
    gcp_location: str = Field(default="us-central1")

    @field_validator("log_level")
    @classmethod
    def _upper_log_level(cls, v: str) -> str:
        return v.upper()


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
