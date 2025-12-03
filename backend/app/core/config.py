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

    # HubSpot CRM (GTM Team Marketing Automation)
    HUBSPOT_API_KEY: Optional[str] = None  # Private App API Key (pat-na1-...)
    HUBSPOT_CLIENT_ID: Optional[str] = None  # OAuth Client ID (if using OAuth)
    HUBSPOT_CLIENT_SECRET: Optional[str] = None  # OAuth Client Secret
    HUBSPOT_PORTAL_ID: Optional[str] = None  # HubSpot Portal/Account ID
    HUBSPOT_WEBHOOK_SECRET: Optional[str] = None  # Webhook verification secret

    # Close CRM (Sales Team)
    CLOSE_API_KEY: Optional[str] = None  # Close API Key
    CLOSE_WRITE_DISABLED: bool = True  # Safety switch - keep True unless testing

    # Apollo.io (Enrichment)
    APOLLO_API_KEY: Optional[str] = None  # Apollo API Key
    APOLLO_WEBHOOK_BASE_URL: Optional[str] = None  # Base URL for Apollo webhooks (e.g., https://api.yourdomain.com)

    # Hunter.io (Email Discovery)
    HUNTER_API_KEY: Optional[str] = None  # Hunter.io API Key

    # LinkedIn (Social Selling)
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_ACCESS_TOKEN: Optional[str] = None

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False  # Set DEBUG=true in .env for development

    class Config:
        env_file = "../.env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables not defined in Settings


# Create global settings instance
settings = Settings()
