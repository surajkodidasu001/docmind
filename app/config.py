"""Central configuration loaded from environment / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    anthropic_api_key: str = ""
    llm_model: str = "claude-sonnet-4-6"
    llm_model_small: str = "claude-haiku-4-5-20251001"  # cheaper tier for simple lookups
    embedding_model: str = "all-MiniLM-L6-v2"
    qdrant_location: str = ":memory:"
    qdrant_collection: str = "docmind_chunks"
    confidence_threshold: float = 0.55
    max_retries: int = 2
    chunk_size: int = 800
    chunk_overlap: int = 120
    top_k_dense: int = 8
    top_k_bm25: int = 8
    top_k_final: int = 5

    # semantic cache
    cache_enabled: bool = True
    cache_similarity_threshold: float = 0.92
    cache_max_entries: int = 500

    # model routing: queries at/under this word count with no "why/how/compare"
    # style complexity markers get routed to the small model
    simple_query_max_words: int = 12

    # conversation memory (short-term, in-process; swap for Redis/DB for multi-instance)
    memory_max_turns: int = 6

    # contradiction detection
    contradiction_check_enabled: bool = True

    # local model fallback (Ollama) — used when the Anthropic call fails
    # after retries (outage, rate limit, or missing API key)
    ollama_fallback_enabled: bool = False
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_timeout_seconds: float = 30.0

    # observability export
    otel_enabled: bool = False
    otel_exporter: str = "console"  # "console" or "otlp"
    otel_otlp_endpoint: str = "http://localhost:4318"

    # multi-tenancy (API-key based; see app/api/auth.py)
    multi_tenancy_enabled: bool = False
    tenant_api_keys: str = ""  # comma-separated "key:tenant_id" pairs, e.g. "abc123:acme,def456:globex"


settings = Settings()
