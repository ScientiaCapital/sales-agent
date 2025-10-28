"""
LangSmith Configuration and Tracing Setup

Configures LangSmith for agent observability and debugging.
Automatically initializes tracing when LANGCHAIN_TRACING_V2=true in .env
"""

import os
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class LangSmithConfig:
    """
    LangSmith configuration and initialization.

    LangSmith provides:
    - Real-time tracing of agent executions
    - Token usage and cost tracking
    - Performance monitoring and debugging
    - Chain/graph visualization
    """

    def __init__(self):
        """Initialize LangSmith configuration from environment variables."""
        self.tracing_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
        self.api_key = os.getenv("LANGCHAIN_API_KEY", "")
        self.endpoint = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
        self.project = os.getenv("LANGCHAIN_PROJECT", "sales-agent-development")

        # Additional configuration
        self.environment = os.getenv("ENVIRONMENT", "development")
        self.session_id: Optional[str] = None

        # Initialize tracing if enabled
        if self.tracing_enabled:
            self._initialize_tracing()
        else:
            logger.info("LangSmith tracing disabled (set LANGCHAIN_TRACING_V2=true to enable)")

    def _initialize_tracing(self):
        """Initialize LangSmith tracing with configuration validation."""
        if not self.api_key:
            logger.warning(
                "LangSmith tracing enabled but LANGCHAIN_API_KEY not set. "
                "Traces will not be uploaded. Get your key at: https://smith.langchain.com"
            )
            return

        if not self.api_key.startswith("ls__"):
            logger.warning(
                f"LANGCHAIN_API_KEY does not start with 'ls__'. "
                f"Verify your API key is correct. Current: {self.api_key[:10]}..."
            )

        # Set environment variables for LangChain SDK
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_ENDPOINT"] = self.endpoint
        os.environ["LANGCHAIN_API_KEY"] = self.api_key
        os.environ["LANGCHAIN_PROJECT"] = self.project

        logger.info(
            f"✅ LangSmith tracing initialized\n"
            f"  Project: {self.project}\n"
            f"  Environment: {self.environment}\n"
            f"  Dashboard: https://smith.langchain.com/o/YOUR_ORG/projects/{self.project}"
        )

    def set_session_id(self, session_id: str):
        """
        Set session ID for grouping related traces.

        Args:
            session_id: Unique identifier for the session (e.g., user_id, conversation_id)
        """
        self.session_id = session_id
        os.environ["LANGCHAIN_SESSION"] = session_id
        logger.debug(f"Set LangSmith session ID: {session_id}")

    def add_tags(self, *tags: str):
        """
        Add tags to current traces for filtering.

        Args:
            *tags: Tags to add (e.g., "production", "qualification", "high-priority")
        """
        current_tags = os.getenv("LANGCHAIN_TAGS", "")
        all_tags = set(current_tags.split(",") if current_tags else [])
        all_tags.update(tags)
        os.environ["LANGCHAIN_TAGS"] = ",".join(all_tags)
        logger.debug(f"Added LangSmith tags: {tags}")

    def add_metadata(self, **metadata):
        """
        Add metadata to current traces.

        Args:
            **metadata: Key-value pairs to add as metadata
        """
        # LangChain will automatically pick up metadata from context
        # This method is for manual metadata setting
        import json
        current_metadata = os.getenv("LANGCHAIN_METADATA", "{}")
        all_metadata = json.loads(current_metadata)
        all_metadata.update(metadata)
        os.environ["LANGCHAIN_METADATA"] = json.dumps(all_metadata)
        logger.debug(f"Added LangSmith metadata: {metadata}")

    def get_trace_url(self, run_id: str) -> str:
        """
        Get direct URL to trace in LangSmith UI.

        Args:
            run_id: The run ID from a traced execution

        Returns:
            URL to the trace in LangSmith
        """
        # Note: Replace YOUR_ORG with actual org name from LangSmith
        return f"https://smith.langchain.com/o/YOUR_ORG/projects/{self.project}/r/{run_id}"

    @property
    def is_enabled(self) -> bool:
        """Check if tracing is enabled and configured."""
        return self.tracing_enabled and bool(self.api_key)


# Global singleton instance
_langsmith_config: Optional[LangSmithConfig] = None


def get_langsmith_config() -> LangSmithConfig:
    """
    Get or create the global LangSmith configuration instance.

    Returns:
        LangSmithConfig singleton instance
    """
    global _langsmith_config
    if _langsmith_config is None:
        _langsmith_config = LangSmithConfig()
    return _langsmith_config


def configure_tracing(
    session_id: Optional[str] = None,
    tags: Optional[list[str]] = None,
    **metadata
):
    """
    Configure LangSmith tracing for current execution context.

    Usage:
        # At the start of agent execution
        configure_tracing(
            session_id="user_123_conversation_456",
            tags=["qualification", "production"],
            user_id="user_123",
            lead_id=789
        )

    Args:
        session_id: Optional session identifier
        tags: Optional list of tags
        **metadata: Additional metadata key-value pairs
    """
    config = get_langsmith_config()

    if not config.is_enabled:
        return

    if session_id:
        config.set_session_id(session_id)

    if tags:
        config.add_tags(*tags)

    if metadata:
        config.add_metadata(**metadata)


# Initialize on module import
get_langsmith_config()
