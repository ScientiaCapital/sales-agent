"""
Structured logging configuration for the sales agent application.
"""
import logging
import sys
from typing import Optional


def setup_logging(name: Optional[str] = None, level: int = logging.INFO) -> logging.Logger:
    """
    Set up structured logging for the application.

    Args:
        name: Logger name (typically __name__ from calling module)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    # Configure root logger if not already configured
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=level,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )

    # Return named logger
    logger = logging.getLogger(name or __name__)
    logger.setLevel(level)

    return logger


# Export a default logger for convenience
logger = setup_logging(__name__)
