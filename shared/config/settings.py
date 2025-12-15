"""
Centralized Settings for Scientia Capital AI Stack

Loads API keys from environment, provides configuration for all providers.
"""

import os
from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment.

    Supports .env files in project root.
    """

    # ==========================================================================
    # Provider API Keys
    # ==========================================================================

    openrouter_api_key: Optional[str] = Field(
        default=None,
        alias="OPENROUTER_API_KEY",
        description="OpenRouter API key for Chinese VLMs (Qwen)",
    )

    anthropic_api_key: Optional[str] = Field(
        default=None,
        alias="ANTHROPIC_API_KEY",
        description="Anthropic API key for Claude 4.5 models",
    )

    google_api_key: Optional[str] = Field(
        default=None,
        alias="GOOGLE_API_KEY",
        description="Google API key for Gemini models",
    )

    # ==========================================================================
    # LangSmith Configuration (Tracing)
    # ==========================================================================

    langsmith_api_key: Optional[str] = Field(
        default=None,
        alias="LANGSMITH_API_KEY",
        description="LangSmith API key for tracing",
    )

    langsmith_project: str = Field(
        default="scientia-vlm-audit",
        alias="LANGSMITH_PROJECT",
        description="LangSmith project name",
    )

    langsmith_tracing: bool = Field(
        default=True,
        alias="LANGSMITH_TRACING",
        description="Enable LangSmith tracing",
    )

    # ==========================================================================
    # Audit Configuration
    # ==========================================================================

    audit_dir: Path = Field(
        default=Path("audit"),
        description="Directory for audit outputs",
    )

    cost_alert_threshold: float = Field(
        default=0.03,
        description="Cost per call that triggers an alert",
    )

    cost_ceiling: float = Field(
        default=0.05,
        description="Maximum acceptable cost per call",
    )

    # ==========================================================================
    # Provider Defaults
    # ==========================================================================

    default_max_tokens: int = Field(
        default=4096,
        description="Default max tokens for responses",
    )

    default_temperature: float = Field(
        default=0.0,
        description="Default temperature for deterministic output",
    )

    # ==========================================================================
    # Test Configuration
    # ==========================================================================

    test_image_base_path: Path = Field(
        default=Path("/Users/tmkipper/Downloads/construction_research_extracted/home/ubuntu/construction_research"),
        description="Base path to test images",
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def validate_provider_keys(self) -> dict[str, bool]:
        """Check which provider keys are configured."""
        return {
            "openrouter": self.openrouter_api_key is not None,
            "anthropic": self.anthropic_api_key is not None,
            "gemini": self.google_api_key is not None,
            "langsmith": self.langsmith_api_key is not None,
        }

    def get_test_image(self, trade: str, image_type: str = "field_photos") -> Optional[Path]:
        """
        Get a test image path for a specific trade.

        Args:
            trade: Trade type (solar, electrical, hvac, roofing, plumbing)
            image_type: Either 'field_photos' or 'blueprints'

        Returns:
            Path to first image found, or None
        """
        trade_dir = self.test_image_base_path / trade / image_type
        if trade_dir.exists():
            images = list(trade_dir.glob("*.jpg")) + list(trade_dir.glob("*.png"))
            return images[0] if images else None
        return None

    def get_all_test_images(self) -> dict[str, list[Path]]:
        """Get all test images organized by trade."""
        trades = ["solar", "electrical", "hvac", "roofing", "plumbing", "edge_cases"]
        result = {}

        for trade in trades:
            result[trade] = []
            for image_type in ["field_photos", "blueprints"]:
                trade_dir = self.test_image_base_path / trade / image_type
                if trade_dir.exists():
                    images = list(trade_dir.glob("*.jpg")) + list(trade_dir.glob("*.png"))
                    result[trade].extend(images)

        return result


def get_settings() -> Settings:
    """Get settings instance - loads fresh from .env.local each time."""
    # Get the project root (where .env.local lives)
    project_root = Path(__file__).parent.parent.parent
    env_local = project_root / ".env.local"
    env_file = project_root / ".env"

    if env_local.exists():
        return Settings(_env_file=env_local)
    elif env_file.exists():
        return Settings(_env_file=env_file)
    return Settings()


def configure_langsmith() -> None:
    """Configure LangSmith environment variables."""
    settings = get_settings()

    if settings.langsmith_tracing and settings.langsmith_api_key:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGSMITH_API_KEY"] = settings.langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = settings.langsmith_project
        print(f"LangSmith configured: project={settings.langsmith_project}")
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        print("LangSmith tracing disabled")
