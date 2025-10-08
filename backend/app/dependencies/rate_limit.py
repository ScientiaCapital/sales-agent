"""
FastAPI dependency for rate limiting.

Provides easy integration of rate limiting into API endpoints.
"""
import os
from typing import Optional
from fastapi import Request, HTTPException, status
import redis.asyncio as redis

from app.services.rate_limiter import RateLimiter, RateLimitExceeded
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None
_redis_client: Optional[redis.Redis] = None


async def get_rate_limiter() -> RateLimiter:
    """
    Get or create global rate limiter instance.

    Returns:
        RateLimiter instance
    """
    global _rate_limiter, _redis_client

    if _rate_limiter is None:
        if _redis_client is None:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            _redis_client = await redis.from_url(redis_url)
            logger.info(f"Redis client initialized for rate limiting: {redis_url}")

        _rate_limiter = RateLimiter(
            redis_client=_redis_client,
            fail_open=True,  # Allow requests on Redis errors
            timeout_ms=100,  # 100ms timeout for Redis ops
        )

    return _rate_limiter


async def rate_limit_dependency(
    request: Request,
    provider: str = "default",
    estimated_tokens: int = 0,
) -> RateLimiter:
    """
    FastAPI dependency for rate limiting.

    Usage in endpoints:
        @app.post("/api/inference")
        async def inference(
            limiter: RateLimiter = Depends(lambda: rate_limit_dependency(provider="cerebras"))
        ):
            # Rate limit is automatically checked before this runs
            ...

    Args:
        request: FastAPI request object
        provider: AI provider name (cerebras, openrouter, etc.)
        estimated_tokens: Estimated token count for request

    Returns:
        RateLimiter instance

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    limiter = await get_rate_limiter()

    # Get user identifier (prefer API key, fallback to IP)
    user_id = _get_user_identifier(request)

    # Check rate limit
    result = await limiter.check_rate_limit(
        user_id=user_id,
        provider=provider,
        endpoint=request.url.path,
        estimated_tokens=estimated_tokens,
    )

    # Add rate limit headers to response
    if hasattr(request.state, "rate_limit_headers"):
        request.state.rate_limit_headers.update(result.headers)
    else:
        request.state.rate_limit_headers = result.headers

    # Raise 429 if limit exceeded
    if not result.allowed:
        logger.warning(
            f"Rate limit exceeded: user={user_id[:8]}, provider={provider}, "
            f"endpoint={request.url.path}"
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "Rate limit exceeded",
                "provider": provider,
                "limit": result.requests_remaining + 1,
                "window": "60 seconds",
                "retry_after": result.retry_after,
            },
            headers=result.headers,
        )

    return limiter


def _get_user_identifier(request: Request) -> str:
    """
    Extract user identifier from request.

    Priority:
    1. API key from Authorization header
    2. API key from query parameter
    3. Client IP address

    Args:
        request: FastAPI request object

    Returns:
        User identifier string
    """
    # Try Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]  # Return API key

    # Try query parameter
    api_key = request.query_params.get("api_key")
    if api_key:
        return api_key

    # Fallback to IP address
    client_ip = request.client.host if request.client else "unknown"
    return f"ip:{client_ip}"


async def cleanup_rate_limiter():
    """
    Cleanup rate limiter and Redis connection.

    Should be called on application shutdown.
    """
    global _rate_limiter, _redis_client

    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis client closed")

    _rate_limiter = None
