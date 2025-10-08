"""Application configuration using pydantic settings."""

from typing import List, Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Project info
    PROJECT_NAME: str = "Sales Agent API"
    VERSION: str = "0.1.0"

    # API Configuration
    API_V1_PREFIX: str = "/api/v1"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # React dev server
        "http://localhost:5173",  # Vite dev server
    ]

    # Database - MUST be provided via environment variable (.env file)
    # No default value to prevent accidental connection to wrong database
    DATABASE_URL: str

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Cerebras API
    CEREBRAS_API_KEY: str = ""
    CEREBRAS_API_BASE: str = "https://api.cerebras.ai/v1"

    # DeepSeek API (via OpenRouter)
    DEEPSEEK_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""

    # Cost Management & Budget Enforcement
    DAILY_BUDGET_USD: float = 50.0
    MONTHLY_BUDGET_USD: float = 1000.0
    COST_WARNING_THRESHOLD: float = 0.80  # 80% - Send warning alert
    COST_DOWNGRADE_THRESHOLD: float = 0.90  # 90% - Auto-downgrade strategy
    COST_BLOCK_THRESHOLD: float = 1.00  # 100% - Block all requests

    # Alert Configuration
    COST_ALERT_WEBHOOK_URL: Optional[str] = None  # Webhook for budget alerts
    COST_ALERT_EMAIL: Optional[str] = None  # Email for budget alerts

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    class Config:
        env_file = "../.env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables not defined in Settings


# Create global settings instance
settings = Settings()
