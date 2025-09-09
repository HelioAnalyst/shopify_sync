# app/core/config.py
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # ==== Core ====
    ENV: str = "dev"
    LOG_LEVEL: str = "INFO"

    # ==== FastAPI ====
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # ==== Database ====
    DATABASE_URL: Optional[str] = None

    # ==== Public base (for OAuth/webhooks) ====
    APP_BASE_URL: Optional[str] = None

    SHOPIFY_LOCATION_ID: Optional[str] = None


    # ==== Shopify OAuth/App ====
    SHOPIFY_CLIENT_ID: Optional[str] = None
    SHOPIFY_CLIENT_SECRET: Optional[str] = None
    OAUTH_SCOPES: str = "read_products"

    # ==== Queues ====
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: Optional[str] = None
    CELERY_RESULT_BACKEND: Optional[str] = None

    # ==== Shopify (classic creds) ====
    SHOPIFY_SHOP: Optional[str] = None
    SHOPIFY_API_VERSION: str = "2024-10"
    SHOPIFY_API_KEY: Optional[str] = None
    SHOPIFY_WEBHOOK_SECRET: Optional[str] = None
    SHOPIFY_ACCESS_TOKEN: str | None = None


    # ==== BC365 / Business Central ====
    BC365_TENANT_ID: Optional[str] = None
    BC365_CLIENT_ID: Optional[str] = None
    BC365_CLIENT_SECRET: Optional[str] = None
    BC365_ENVIRONMENT: str = "production"   # or "sandbox"
    BC365_COMPANY_ID: Optional[str] = None
    BC365_COMPANY_NAME: Optional[str] = None
    # add in Settings(...)
    BC365_DEFAULT_CUSTOMER: str = "10000"
    # in Settings
    SKU_MAP_JSON: str | None = None



    # ==== Security/Observability ====
    ADMIN_API_TOKEN: str = "change-me"
    PROMETHEUS_ENABLE: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

settings = Settings()
