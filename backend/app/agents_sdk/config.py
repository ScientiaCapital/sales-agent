"""Configuration for Claude Agent SDK agents."""
import os
from typing import Optional
from pydantic import BaseModel, Field


class AgentSDKConfig(BaseModel):
    """Configuration for Claude Agent SDK."""

    # Claude API
    anthropic_api_key: str = Field(
        default_factory=lambda: os.getenv("ANTHROPIC_API_KEY", "")
    )

    # Model settings
    default_model: str = "claude-sonnet-4-0-20250514"
    temperature: float = 0.3
    max_tokens: int = 2000

    # Session management
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379/0")
    )
    session_ttl_seconds: int = 86400  # 24 hours

    # Cost optimization
    enable_caching: bool = True
    enable_compression: bool = True
    tool_result_cache_ttl: int = 3600  # 1 hour

    class Config:
        env_file = ".env"


# Global config instance
config = AgentSDKConfig()
