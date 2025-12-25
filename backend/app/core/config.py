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
        "https://sales-agent-seven-eta.vercel.app",  # Production dashboard
        "https://sales-agent-b3096zdcs-scientia-capital.vercel.app",  # Preview deployments
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
    CLOSE_API_URL: str = "https://api.close.com/api/v1"  # Close API Base URL
    CLOSE_WRITE_DISABLED: bool = False  # Default: False (enabled). Set True in .env to disable writes
    CLOSE_DEFAULT_OWNER_USER_ID: Optional[str] = None  # Default owner for new leads

    # Apollo.io (Enrichment)
    APOLLO_API_KEY: Optional[str] = None  # Apollo API Key
    APOLLO_WEBHOOK_BASE_URL: Optional[str] = None  # Base URL for Apollo webhooks (e.g., https://api.yourdomain.com)

    # Hunter.io (Email Discovery)
    HUNTER_API_KEY: Optional[str] = None  # Hunter.io API Key

    # LinkedIn (Social Selling)
    LINKEDIN_CLIENT_ID: Optional[str] = None
    LINKEDIN_CLIENT_SECRET: Optional[str] = None
    LINKEDIN_ACCESS_TOKEN: Optional[str] = None

    # Supabase Configuration (for authentication and social intelligence)
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: str = ""  # Public anon key for client-side operations
    SUPABASE_SERVICE_KEY: str = ""  # Service role key for server-side operations

    # JWT Configuration for Supabase
    SUPABASE_JWT_SECRET: Optional[str] = None  # For validating Supabase JWTs
    JWT_SECRET_KEY: Optional[str] = None  # For custom JWT tokens
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = False  # Set DEBUG=true in .env for development

    class Config:
        env_file = "../.env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables not defined in Settings


# Create global settings instance
settings = Settings()
