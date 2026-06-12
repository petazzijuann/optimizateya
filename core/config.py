"""Configuración central. Valida TODAS las env vars al boot — falla rápido."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: str = Field(alias="TELEGRAM_WEBHOOK_SECRET")
    public_base_url: str = Field(alias="PUBLIC_BASE_URL")

    # Infra
    database_url: str = Field(alias="DATABASE_URL")
    redis_url: str = Field(alias="REDIS_URL")

    # LLM (provider-agnostic, OpenAI-compatible)
    llm_provider: Literal["groq", "ollama"] = Field(default="groq", alias="LLM_PROVIDER")
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_base_url: str = Field(default="https://api.groq.com/openai/v1", alias="GROQ_BASE_URL")
    ollama_base_url: str = Field(default="http://localhost:11434/v1", alias="OLLAMA_BASE_URL")
    llm_model: str = Field(default="llama-3.1-8b-instant", alias="LLM_MODEL")
    llm_model_heavy: str = Field(default="llama-3.3-70b-versatile", alias="LLM_MODEL_HEAVY")
    vision_model: str = Field(
        default="meta-llama/llama-4-scout-17b-16e-instruct", alias="VISION_MODEL"
    )
    embed_model: str = Field(default="nomic-embed-text", alias="EMBED_MODEL")
    stt_model: str = Field(default="whisper-large-v3-turbo", alias="STT_MODEL")
    llm_monthly_budget_tokens: int = Field(default=2_000_000, alias="LLM_MONTHLY_BUDGET_TOKENS")

    # Storage R2
    r2_account_id: str = Field(default="", alias="R2_ACCOUNT_ID")
    r2_access_key_id: str = Field(default="", alias="R2_ACCESS_KEY_ID")
    r2_secret_access_key: str = Field(default="", alias="R2_SECRET_ACCESS_KEY")
    r2_bucket: str = Field(default="optimizateya", alias="R2_BUCKET")

    # Seguridad
    fernet_key: str = Field(alias="FERNET_KEY")

    # OAuth calendarios
    google_client_id: str = Field(default="", alias="GOOGLE_CLIENT_ID")
    google_client_secret: str = Field(default="", alias="GOOGLE_CLIENT_SECRET")
    ms_client_id: str = Field(default="", alias="MS_CLIENT_ID")
    ms_client_secret: str = Field(default="", alias="MS_CLIENT_SECRET")

    # Observabilidad
    sentry_dsn: str = Field(default="", alias="SENTRY_DSN")
    environment: str = Field(default="dev", alias="ENVIRONMENT")

    @field_validator("database_url")
    @classmethod
    def _normalize_to_asyncpg(cls, v: str) -> str:
        """Acepta URLs de Supabase/Railway (postgres://, sslmode=) y las adapta a asyncpg."""
        if v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql://", 1)
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        # asyncpg no entiende sslmode= (estilo libpq); su equivalente es ssl=
        v = v.replace("?sslmode=", "?ssl=").replace("&sslmode=", "&ssl=")
        PostgresDsn(v.replace("postgresql+asyncpg://", "postgresql://", 1))  # valida la forma
        if not v.startswith("postgresql+asyncpg://"):
            raise ValueError("DATABASE_URL debe ser una URL de Postgres")
        return v

    @property
    def database_url_sync(self) -> str:
        """URL con driver sync (psycopg2) para Alembic offline."""
        url = self.database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
        return url.replace("?ssl=", "?sslmode=").replace("&ssl=", "&sslmode=")

    @property
    def llm_base_url(self) -> str:
        return self.groq_base_url if self.llm_provider == "groq" else self.ollama_base_url

    @property
    def llm_api_key(self) -> str:
        return self.groq_api_key if self.llm_provider == "groq" else "ollama"

    @property
    def r2_endpoint_url(self) -> str:
        return f"https://{self.r2_account_id}.r2.cloudflarestorage.com"

    @property
    def webhook_path(self) -> str:
        return f"/webhook/telegram/{self.telegram_webhook_secret}"

    @property
    def webhook_url(self) -> str:
        return f"{self.public_base_url.rstrip('/')}{self.webhook_path}"


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
