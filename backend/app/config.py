from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = (
        "postgresql+asyncpg://recoverlead:recoverlead_dev@localhost:5432/recoverlead"
    )

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Clerk
    clerk_secret_key: str = ""
    clerk_publishable_key: str = ""
    clerk_webhook_secret: str = ""

    # Anthropic
    anthropic_api_key: str = ""

    # Stripe
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    stripe_qualification_overage_price_id: str = ""
    stripe_letter_overage_price_id: str = ""
    stripe_skip_trace_overage_price_id: str = ""

    # Tracerfy
    tracerfy_api_key: str = ""
    tracerfy_base_url: str = "https://tracerfy.com/v1/api"

    # SendGrid
    sendgrid_api_key: str = ""
    sendgrid_from_email: str = "alerts@recoverlead.com"

    # Embedding
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"

    # Observability
    sentry_dsn: str = ""

    # CORS
    cors_origins: str = "http://localhost:3000"

    # Encryption
    encryption_key: str = ""  # Fernet key for PII column encryption

    # Storage
    scraper_artifacts_dir: str = "/data/scraper_artifacts"

    # App
    environment: str = "development"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    model_config = {"env_file": ("../.env", ".env"), "env_file_encoding": "utf-8"}


settings = Settings()
