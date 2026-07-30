from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database (async SQLAlchemy + asyncpg) ---
    database_url: str = "postgresql+asyncpg://app:app@localhost:5432/app"

    # --- Redis (Arq queue + cache) ---
    redis_url: str = "redis://localhost:6379"

    # --- OpenAI (hosted chat + embeddings) ---
    openai_api_key: str = ""
    openai_chat_model: str = "gpt-4o-mini"
    openai_embed_model: str = "text-embedding-3-small"
    embedding_dim: int = 1536

    # --- Auth / JWT ---
    # NOTE: override jwt_secret via environment in any real deployment.
    jwt_secret: str = "dev-insecure-change-me"
    jwt_alg: str = "HS256"
    access_ttl_min: int = 30
    refresh_ttl_days: int = 14

    # --- Object storage (S3 / Cloudflare R2 / MinIO) ---
    storage_endpoint: str = "http://localhost:9000"
    storage_region: str = "auto"
    storage_bucket: str = "prescriptions"
    storage_access_key: str = ""
    storage_secret_key: str = ""

    # --- App ---
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
    max_upload_mb: int = 10
    rag_top_k: int = 4
    max_tokens_per_request: int = 4000
    fulltext_language: str = "english"

    # --- Transport security (off by default so local dev stays on HTTP) ---
    enforce_https: bool = False
    hsts_max_age: int = 31536000
    trusted_hosts: str = "*"  # comma-separated; "*" disables the host check

    # --- Auth cookies ---
    # For a same-origin frontend (nginx proxy) keep samesite=lax.
    # For a split frontend origin over HTTPS, use samesite=none + secure=true.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: str = ""

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_hosts_list(self) -> list[str]:
        return [h.strip() for h in self.trusted_hosts.split(",") if h.strip()]

    @property
    def async_database_url(self) -> str:
        """Normalise managed-Postgres URLs (Neon/Render) to the asyncpg driver."""
        url = self.database_url
        if url.startswith("postgresql+"):
            return url
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url


settings = Settings()
