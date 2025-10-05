"""Application configuration using pydantic settings."""

from typing import List
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

    # Environment
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    class Config:
        env_file = "../.env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra environment variables not defined in Settings


# Create global settings instance
settings = Settings()
