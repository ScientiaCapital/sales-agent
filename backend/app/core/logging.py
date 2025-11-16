"""
Structured JSON logging configuration for production observability.
Uses structlog for rich contextual logging with performance metrics.
"""
import logging
import sys
import os
from typing import Optional, Any, Dict
import structlog


def setup_logging(
    name: Optional[str] = None,
    level: int = logging.INFO,
    json_format: bool = True
) -> structlog.BoundLogger:
    """
    Set up structured JSON logging for the application.

    Args:
        name: Logger name (typically __name__ from calling module)
        level: Logging level (default: INFO)
        json_format: Use JSON output (default: True for production)

    Returns:
        Configured structlog logger instance

    Example:
        >>> logger = setup_logging(__name__)
        >>> logger.info("user_action", user_id="123", action="login", latency_ms=45)
        {"event": "user_action", "user_id": "123", "action": "login", "latency_ms": 45, "timestamp": "..."}
    """
    # Determine environment
    is_production = os.getenv("ENVIRONMENT", "development") == "production"
    use_json = json_format or is_production

    # Configure structlog processors
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]

    if use_json:
        # JSON output for production (machine-readable)
        processors.append(structlog.processors.JSONRenderer())
    else:
        # Human-readable output for development
        processors.append(structlog.dev.ConsoleRenderer())

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    if not logging.getLogger().handlers:
        logging.basicConfig(
            format="%(message)s",
            stream=sys.stdout,
            level=level,
        )

    # Return structlog logger
    logger = structlog.get_logger(name or __name__)
    return logger


def log_performance(
    logger: structlog.BoundLogger,
    service: str,
    operation: str,
    latency_ms: float,
    **extra_context: Any
) -> None:
    """
    Log performance metrics in a standardized format.

    Args:
        logger: Structlog logger instance
        service: Service name (e.g., "linkedin_scraper", "context_analyzer")
        operation: Operation name (e.g., "scrape_profile", "analyze_post")
        latency_ms: Operation latency in milliseconds
        **extra_context: Additional context (cost_usd, tokens, etc.)

    Example:
        >>> logger = setup_logging(__name__)
        >>> log_performance(
        ...     logger,
        ...     service="context_analyzer",
        ...     operation="analyze_post",
        ...     latency_ms=2340.5,
        ...     cost_usd=0.00027,
        ...     tokens=450,
        ...     model="deepseek-chat"
        ... )
    """
    logger.info(
        "performance_metric",
        service=service,
        operation=operation,
        latency_ms=round(latency_ms, 2),
        **extra_context
    )


def log_error(
    logger: structlog.BoundLogger,
    service: str,
    operation: str,
    error: Exception,
    **extra_context: Any
) -> None:
    """
    Log errors in a standardized format with full context.

    Args:
        logger: Structlog logger instance
        service: Service name
        operation: Operation that failed
        error: Exception instance
        **extra_context: Additional context

    Example:
        >>> logger = setup_logging(__name__)
        >>> try:
        ...     risky_operation()
        ... except Exception as e:
        ...     log_error(logger, "linkedin_scraper", "scrape_profile", e, profile_url="...")
    """
    logger.error(
        "operation_failed",
        service=service,
        operation=operation,
        error_type=type(error).__name__,
        error_message=str(error),
        exc_info=True,
        **extra_context
    )


# Export a default logger for convenience
logger = setup_logging(__name__)
