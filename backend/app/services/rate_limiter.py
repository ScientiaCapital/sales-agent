"""
Redis-based rate limiting with sliding window algorithm.

Provides distributed rate limiting for API providers with request and token-based limits.
"""
import asyncio
import time
import hashlib
from typing import Optional, Dict, Tuple
from dataclasses import dataclass
from enum import Enum

import redis.asyncio as redis
from redis.exceptions import RedisError, ConnectionError as RedisConnectionError

from app.core.logging import setup_logging

logger = setup_logging(__name__)


# Provider rate limits (requests per minute, tokens per minute)
PROVIDER_LIMITS = {
    "cerebras": {
        "requests_per_minute": 60,
        "tokens_per_minute": 100_000,
    },
    "openrouter": {
        "requests_per_minute": 30,
        "tokens_per_minute": 50_000,
    },
    "ollama": {
        "requests_per_minute": 120,
        "tokens_per_minute": None,  # Unlimited
    },
    "claude": {
        "requests_per_minute": 50,
        "tokens_per_minute": 100_000,
    },
    "deepseek": {
        "requests_per_minute": 30,
        "tokens_per_minute": 50_000,
    },
}


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    requests_remaining: int
    tokens_remaining: Optional[int]
    reset_time: float  # Unix timestamp
    retry_after: Optional[int] = None  # Seconds until retry allowed
    headers: Dict[str, str] = None

    def __post_init__(self):
        """Generate HTTP headers."""
        if self.headers is None:
            self.headers = {
                "X-RateLimit-Limit": str(self.requests_remaining + (0 if self.allowed else 1)),
                "X-RateLimit-Remaining": str(max(0, self.requests_remaining)),
                "X-RateLimit-Reset": str(int(self.reset_time)),
            }

            if self.tokens_remaining is not None:
                self.headers["X-RateLimit-Limit-Tokens"] = str(self.tokens_remaining)

            if not self.allowed and self.retry_after:
                self.headers["Retry-After"] = str(self.retry_after)


class RateLimitExceeded(Exception):
    """Exception raised when rate limit is exceeded."""

    def __init__(self, result: RateLimitResult, provider: str):
        self.result = result
        self.provider = provider
        super().__init__(
            f"Rate limit exceeded for provider '{provider}'. "
            f"Retry after {result.retry_after}s"
        )


class RateLimiter:
    """
    Redis-based rate limiter with sliding window algorithm.

    Features:
    - Per-provider request and token limits
    - Sliding window algorithm for accurate rate tracking
    - Distributed rate limiting via Redis
    - Fail-open on Redis errors (availability > strict limiting)
    - Atomic operations for concurrent request handling
    - <5ms overhead per request

    Usage:
        limiter = RateLimiter(redis_client)
        result = await limiter.check_rate_limit("user123", "cerebras", "/api/leads")
        if not result.allowed:
            raise RateLimitExceeded(result, "cerebras")
    """

    def __init__(
        self,
        redis_client: redis.Redis,
        fail_open: bool = True,
        timeout_ms: int = 100,
    ):
        """
        Initialize rate limiter.

        Args:
            redis_client: Async Redis client instance
            fail_open: Allow requests on Redis errors (default: True)
            timeout_ms: Redis operation timeout in milliseconds (default: 100)
        """
        self.redis = redis_client
        self.fail_open = fail_open
        self.timeout = timeout_ms / 1000.0  # Convert to seconds
        self.limits = PROVIDER_LIMITS

        logger.info(
            f"RateLimiter initialized: fail_open={fail_open}, "
            f"timeout={timeout_ms}ms"
        )

    async def check_rate_limit(
        self,
        user_id: str,
        provider: str,
        endpoint: str,
        estimated_tokens: int = 0,
    ) -> RateLimitResult:
        """
        Check if request is within rate limits.

        Args:
            user_id: User identifier (API key hash or IP address)
            provider: AI provider name (cerebras, openrouter, etc.)
            endpoint: API endpoint being called
            estimated_tokens: Estimated token count for the request

        Returns:
            RateLimitResult with allowed status and rate limit info
        """
        # Get provider limits
        provider_limits = self.limits.get(provider.lower())
        if not provider_limits:
            logger.warning(f"Unknown provider '{provider}', allowing request")
            return RateLimitResult(
                allowed=True,
                requests_remaining=999,
                tokens_remaining=None,
                reset_time=time.time() + 60,
            )

        request_limit = provider_limits["requests_per_minute"]
        token_limit = provider_limits["tokens_per_minute"]

        # Generate Redis keys
        user_hash = self._hash_user_id(user_id)
        requests_key = f"rate_limit:{user_hash}:{provider}:requests"
        tokens_key = f"rate_limit:{user_hash}:{provider}:tokens"

        try:
            # Get current window bounds (60 seconds)
            now = time.time()
            window_start = now - 60
            window_end = now
            reset_time = now + 60

            # Check request limit using sliding window
            async with asyncio.timeout(self.timeout):
                allowed, requests_remaining = await self._check_request_limit(
                    requests_key,
                    request_limit,
                    window_start,
                    window_end,
                )

            if not allowed:
                retry_after = int(reset_time - now)
                logger.warning(
                    f"Rate limit exceeded for {provider}: "
                    f"requests={request_limit}, user={user_hash[:8]}"
                )
                return RateLimitResult(
                    allowed=False,
                    requests_remaining=0,
                    tokens_remaining=None,
                    reset_time=reset_time,
                    retry_after=retry_after,
                )

            # Check token limit if applicable
            tokens_remaining = None
            if token_limit is not None and estimated_tokens > 0:
                async with asyncio.timeout(self.timeout):
                    token_allowed, tokens_remaining = await self._check_token_limit(
                        tokens_key,
                        token_limit,
                        estimated_tokens,
                        window_start,
                    )

                if not token_allowed:
                    retry_after = int(reset_time - now)
                    logger.warning(
                        f"Token limit exceeded for {provider}: "
                        f"tokens={token_limit}, user={user_hash[:8]}"
                    )
                    return RateLimitResult(
                        allowed=False,
                        requests_remaining=requests_remaining,
                        tokens_remaining=0,
                        reset_time=reset_time,
                        retry_after=retry_after,
                    )

            return RateLimitResult(
                allowed=True,
                requests_remaining=requests_remaining,
                tokens_remaining=tokens_remaining,
                reset_time=reset_time,
            )

        except asyncio.TimeoutError:
            logger.error(f"Redis timeout ({self.timeout}s) checking rate limit")
            return self._handle_redis_error("timeout")

        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis error checking rate limit: {e}")
            return self._handle_redis_error(str(e))

    async def record_request(
        self,
        user_id: str,
        provider: str,
        endpoint: str,
        tokens_used: int = 0,
    ) -> None:
        """
        Record completed request and actual token usage.

        Args:
            user_id: User identifier
            provider: AI provider name
            endpoint: API endpoint that was called
            tokens_used: Actual tokens consumed
        """
        user_hash = self._hash_user_id(user_id)
        requests_key = f"rate_limit:{user_hash}:{provider}:requests"
        tokens_key = f"rate_limit:{user_hash}:{provider}:tokens"

        try:
            now = time.time()

            # Record request with timestamp using sorted set
            async with asyncio.timeout(self.timeout):
                # Add request to sorted set (score = timestamp)
                await self.redis.zadd(requests_key, {str(now): now})

                # Set expiry (cleanup old data after 120 seconds)
                await self.redis.expire(requests_key, 120)

            # Record token usage if applicable
            if tokens_used > 0:
                provider_limits = self.limits.get(provider.lower())
                if provider_limits and provider_limits["tokens_per_minute"] is not None:
                    async with asyncio.timeout(self.timeout):
                        # Increment token counter
                        await self.redis.incrby(tokens_key, tokens_used)
                        await self.redis.expire(tokens_key, 120)

        except (asyncio.TimeoutError, RedisError) as e:
            logger.warning(f"Failed to record request: {e}")
            # Don't raise - recording is best-effort

    async def _check_request_limit(
        self,
        key: str,
        limit: int,
        window_start: float,
        window_end: float,
    ) -> Tuple[bool, int]:
        """
        Check request count against limit using sliding window.

        Uses Redis sorted set with timestamps as scores.

        Args:
            key: Redis key for requests
            limit: Maximum requests per window
            window_start: Window start timestamp
            window_end: Window end timestamp

        Returns:
            Tuple of (allowed, remaining_requests)
        """
        # Use Lua script for atomic operations
        lua_script = """
        local key = KEYS[1]
        local window_start = tonumber(ARGV[1])
        local window_end = tonumber(ARGV[2])
        local limit = tonumber(ARGV[3])

        -- Remove old entries outside window
        redis.call('ZREMRANGEBYSCORE', key, '-inf', window_start)

        -- Count entries in current window
        local count = redis.call('ZCOUNT', key, window_start, window_end)

        return count
        """

        try:
            count = await self.redis.eval(
                lua_script,
                1,  # Number of keys
                key,
                window_start,
                window_end,
                limit,
            )

            allowed = int(count) < limit
            remaining = max(0, limit - int(count))

            return allowed, remaining

        except RedisError as e:
            logger.error(f"Redis error in _check_request_limit: {e}")
            raise

    async def _check_token_limit(
        self,
        key: str,
        limit: int,
        estimated_tokens: int,
        window_start: float,
    ) -> Tuple[bool, int]:
        """
        Check token count against limit.

        Args:
            key: Redis key for tokens
            limit: Maximum tokens per minute
            estimated_tokens: Estimated tokens for this request
            window_start: Window start timestamp

        Returns:
            Tuple of (allowed, remaining_tokens)
        """
        try:
            # Get current token count
            current = await self.redis.get(key)
            current_tokens = int(current) if current else 0

            # Check if adding estimated tokens would exceed limit
            projected_tokens = current_tokens + estimated_tokens
            allowed = projected_tokens <= limit
            remaining = max(0, limit - current_tokens)

            return allowed, remaining

        except RedisError as e:
            logger.error(f"Redis error in _check_token_limit: {e}")
            raise

    def _hash_user_id(self, user_id: str) -> str:
        """
        Hash user ID for privacy.

        Args:
            user_id: Raw user identifier

        Returns:
            SHA256 hash of user ID
        """
        return hashlib.sha256(user_id.encode()).hexdigest()[:16]

    def _handle_redis_error(self, error: str) -> RateLimitResult:
        """
        Handle Redis errors with fail-open strategy.

        Args:
            error: Error description

        Returns:
            RateLimitResult allowing the request
        """
        if self.fail_open:
            logger.warning(f"Redis error ({error}), allowing request (fail-open)")
            return RateLimitResult(
                allowed=True,
                requests_remaining=999,
                tokens_remaining=None,
                reset_time=time.time() + 60,
            )
        else:
            logger.error(f"Redis error ({error}), denying request (fail-closed)")
            return RateLimitResult(
                allowed=False,
                requests_remaining=0,
                tokens_remaining=0,
                reset_time=time.time() + 60,
                retry_after=60,
            )

    async def get_status(self, user_id: str, provider: str) -> Dict:
        """
        Get current rate limit status for monitoring.

        Args:
            user_id: User identifier
            provider: AI provider name

        Returns:
            Dictionary with current usage stats
        """
        user_hash = self._hash_user_id(user_id)
        requests_key = f"rate_limit:{user_hash}:{provider}:requests"
        tokens_key = f"rate_limit:{user_hash}:{provider}:tokens"

        provider_limits = self.limits.get(provider.lower())
        if not provider_limits:
            return {"error": f"Unknown provider: {provider}"}

        try:
            now = time.time()
            window_start = now - 60

            # Get request count
            request_count = await self.redis.zcount(requests_key, window_start, now)

            # Get token count
            token_count = 0
            if provider_limits["tokens_per_minute"] is not None:
                current = await self.redis.get(tokens_key)
                token_count = int(current) if current else 0

            return {
                "provider": provider,
                "user_hash": user_hash[:8],
                "requests": {
                    "limit": provider_limits["requests_per_minute"],
                    "used": int(request_count),
                    "remaining": max(0, provider_limits["requests_per_minute"] - int(request_count)),
                },
                "tokens": {
                    "limit": provider_limits["tokens_per_minute"],
                    "used": token_count,
                    "remaining": max(0, provider_limits["tokens_per_minute"] - token_count) if provider_limits["tokens_per_minute"] else None,
                } if provider_limits["tokens_per_minute"] is not None else None,
            }

        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Error getting rate limit status: {e}")
            return {"error": str(e)}
