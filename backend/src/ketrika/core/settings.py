"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration settings for Ketrika backend services."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General
    app_env: str = "dev"
    tz_business: str = "Indian/Antananarivo"
    log_level: str = "INFO"
    log_format: str = "console"

    # Database
    postgres_user: str = "ketrika"
    postgres_password: str = "change-me"
    postgres_db: str = "ketrika"
    database_url: str = "postgresql+psycopg://ketrika:change-me@db:5432/ketrika"
    dagster_pg_db: str = "dagster"
    copilot_db_password: str = "change-me-ro"

    # S3 / Object storage
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_bronze: str = "bronze"
    s3_region: str = "auto"

    # Scraping / Network policy
    bot_user_agent: str = "KetrikaAgriBot/0.1 (+https://ketrika.ai/bot)"
    bot_contact_email: str = "contact@example.com"
    http_offline: int = 0
    http_default_max_rps: float = 0.2

    # LLM
    llm_provider: str = "replay"
    llm_model_extract: str = "gemini-2.5-flash"
    llm_model_reason: str = "gemini-2.5-flash"
    gemini_api_key: str | None = None
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    llm_monthly_budget_usd: float = 20.0
    llm_per_run_budget_usd: float = 5.0

    # API / Auth
    jwt_secret: str = "change-me-long-random-secret-key-32chars"
    jwt_ttl_minutes: int = 720
    demo_admin_email: str = "admin@ketrika.local"
    demo_admin_password: str = "change-me"
    cors_origins: str = "http://localhost:3000,http://localhost:3005"

    # Notifications
    smtp_host: str = "mailpit"
    smtp_port: int = 1025
    smtp_from: str = "bulletin@ketrika.local"
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    external_send_enabled: int = 0

    # Web
    next_public_api_base_url: str = "http://localhost:8000"
    api_internal_url: str = "http://api:8000"
    map_style_url: str = ""


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
