"""
API Rate Limiting with SlowAPI

Protects endpoints from abuse with configurable per-route limits.
Uses IP address or API key for rate limit tracking.
"""

import logging
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.config import settings

logger = logging.getLogger(__name__)


def get_rate_limit_key(request: Request) -> str:
    """
    Get rate limit key from request.

    Priority:
    1. X-API-Key header (for authenticated clients)
    2. IP address (for anonymous clients)
    """
    # Check for API key first
    api_key = request.headers.get("X-API-Key")
    if api_key:
        # Use prefix only for privacy
        return f"api_key:{api_key[:8]}"

    # Fall back to IP address
    return get_remote_address(request)


# Initialize limiter with settings
limiter = Limiter(
    key_func=get_rate_limit_key,
    enabled=settings.RATE_LIMIT_ENABLED,
    default_limits=[settings.RATE_LIMIT_DEFAULT],
)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Handle rate limit exceeded errors.

    Returns JSON response with error details and Retry-After header.
    """
    logger.warning(
        f"Rate limit exceeded for {get_rate_limit_key(request)}: {exc.detail}",
        extra={
            "path": request.url.path,
            "method": request.method,
            "limit": str(exc.detail),
        }
    )

    # Extract retry time from error detail
    retry_after = "60"
    if " per " in str(exc.detail):
        # e.g., "5 per 1 minute" -> extract "60" seconds
        parts = str(exc.detail).split(" per ")
        if "minute" in parts[1]:
            retry_after = "60"
        elif "hour" in parts[1]:
            retry_after = "3600"
        elif "second" in parts[1]:
            retry_after = parts[1].split()[0]

    return JSONResponse(
        status_code=429,
        content={
            "error": "rate_limit_exceeded",
            "message": f"Rate limit exceeded: {exc.detail}",
            "retry_after_seconds": int(retry_after),
        },
        headers={"Retry-After": retry_after}
    )
