from pydantic_settings import BaseSettings
from functools import lru_cache
import secrets


class Settings(BaseSettings):
    # App
    APP_NAME: str = "Payment Workflow Simulator"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql://payment_user:payment_pass@localhost:5432/payment_db"

    # Security
    SECRET_KEY: str = secrets.token_hex(32)
    WEBHOOK_SECRET: str = "whsec_payment_simulator_secret_key_2024"

    # Payment Simulation
    PAYMENT_FAILURE_RATE: float = 0.15          # 15% random failure rate
    WEBHOOK_DELIVERY_FAILURE_RATE: float = 0.20  # 20% webhook delivery failure rate
    MAX_RETRY_ATTEMPTS: int = 5
    RETRY_BASE_DELAY: float = 1.0               # seconds

    # Webhook
    WEBHOOK_ENDPOINT_URL: str = "http://localhost:8000/api/v1/webhooks/receive"

    # CORS
    ALLOWED_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()
