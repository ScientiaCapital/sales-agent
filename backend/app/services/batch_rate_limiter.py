"""
BatchRateLimiter - Rate Limiting for Batch Processing

Manages rate limits and quotas for external services:
- Apollo.io: Hourly/Daily limits + credit/token tracking
- Hunter.io: 50 requests/month (hard limit)
- Browserbase: 5 concurrent sessions
- Cerebras/DeepSeek: 60 requests/minute

Uses Redis for distributed state tracking across workers.

Apollo.io Rate Limits (varies by plan):
    - Free: ~50/hour, ~300/day
    - Basic: ~200/hour, ~2000/day
    - Professional: ~400/hour, ~6000/day
    - Enterprise: Custom

Reference: https://docs.apollo.io/reference/rate-limits

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                     BatchRateLimiter                         │
    │  ┌────────────────┐  ┌────────────────┐  ┌────────────────┐ │
    │  │  Apollo Limits │  │  Hunter Quota  │  │  Browserbase   │ │
    │  │  (hour/day)    │  │  (50/month)    │  │  (5 concurrent)│ │
    │  └────────────────┘  └────────────────┘  └────────────────┘ │
    │           │                  │                   │          │
    │           └──────────────────┼───────────────────┘          │
    │                              ▼                               │
    │                         Redis Store                          │
    │                     (Distributed State)                      │
    └─────────────────────────────────────────────────────────────┘

Usage:
    rate_limiter = BatchRateLimiter(redis_url="redis://localhost:6379")

    # Check before Apollo call
    if await rate_limiter.can_use_apollo():
        result = await apollo.enrich_contact(...)
        await rate_limiter.record_apollo_usage(credits=1)

    # Check before Hunter.io call
    if await rate_limiter.can_use_hunter():
        result = await hunter_api.lookup(email)
        await rate_limiter.record_hunter_usage()
"""

import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from dataclasses import dataclass, field

from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Try to import Redis, but make it optional
try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("Redis not available - using in-memory rate limiting")


@dataclass
class ApolloRateLimitConfig:
    """
    Apollo.io rate limit configuration.

    Apollo uses fixed-window rate limiting with limits per minute, hour, and day.
    Limits vary by subscription plan. Configure based on your Apollo plan.

    Reference: https://docs.apollo.io/reference/rate-limits
    """
    # Request limits (adjust based on your Apollo plan)
    requests_per_minute: int = 10      # Conservative default
    requests_per_hour: int = 200       # Basic plan ~200/hour
    requests_per_day: int = 2000       # Basic plan ~2000/day

    # Credit tracking (enrichments cost credits)
    daily_credit_budget: int = 500     # Max credits to use per day
    credit_safety_buffer: int = 50     # Stop 50 credits before limit

    # Token tracking (for AI-powered Apollo features if applicable)
    daily_token_budget: int = 100000   # If using AI features

    # Retry behavior
    retry_after_rate_limit_seconds: int = 60

    # Endpoint-specific limits (some endpoints have lower limits)
    people_search_per_minute: int = 5
    bulk_enrich_per_minute: int = 3


@dataclass
class RateLimitConfig:
    """Configuration for all rate limits."""
    # Apollo.io configuration
    apollo: ApolloRateLimitConfig = field(default_factory=ApolloRateLimitConfig)

    # Hunter.io monthly quota
    hunter_monthly_limit: int = 50
    hunter_safety_buffer: int = 5  # Stop at 45 to be safe

    # Browserbase concurrent sessions
    browserbase_max_concurrent: int = 5
    browserbase_session_ttl_seconds: int = 300  # 5 min TTL for stuck sessions

    # Cerebras API rate limit
    cerebras_requests_per_minute: int = 60

    # DeepSeek API rate limit
    deepseek_requests_per_minute: int = 60


@dataclass
class ApolloUsageStats:
    """Apollo usage statistics."""
    requests_this_minute: int = 0
    requests_this_hour: int = 0
    requests_this_day: int = 0
    credits_used_today: int = 0
    tokens_used_today: int = 0
    last_request_time: Optional[datetime] = None
    rate_limited_until: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requests_this_minute": self.requests_this_minute,
            "requests_this_hour": self.requests_this_hour,
            "requests_this_day": self.requests_this_day,
            "credits_used_today": self.credits_used_today,
            "tokens_used_today": self.tokens_used_today,
            "last_request_time": self.last_request_time.isoformat() if self.last_request_time else None,
            "rate_limited_until": self.rate_limited_until.isoformat() if self.rate_limited_until else None,
        }


class BatchRateLimiter:
    """
    Distributed rate limiter for batch processing.

    Uses Redis for distributed state tracking, with fallback to
    in-memory storage for local development.
    """

    def __init__(
        self,
        redis_url: Optional[str] = None,
        config: Optional[RateLimitConfig] = None,
    ):
        """
        Initialize rate limiter.

        Args:
            redis_url: Redis connection URL (optional)
            config: Rate limit configuration
        """
        self.config = config or RateLimitConfig()
        self.redis_url = redis_url
        self._redis: Optional["aioredis.Redis"] = None

        # In-memory fallback storage
        self._memory_storage: dict = {
            "hunter_count": 0,
            "hunter_month": datetime.utcnow().strftime("%Y-%m"),
            "browserbase_sessions": 0,
            "api_timestamps": [],
            # Apollo tracking
            "apollo_minute": [],
            "apollo_hour": [],
            "apollo_day_count": 0,
            "apollo_day_date": datetime.utcnow().strftime("%Y-%m-%d"),
            "apollo_credits_today": 0,
            "apollo_tokens_today": 0,
        }

        # Local semaphore for Browserbase (backup)
        self._browserbase_semaphore = asyncio.Semaphore(
            self.config.browserbase_max_concurrent
        )

        logger.info(
            f"BatchRateLimiter initialized: "
            f"Apollo={self.config.apollo.requests_per_hour}/hour, "
            f"{self.config.apollo.requests_per_day}/day, "
            f"Hunter={self.config.hunter_monthly_limit}/month, "
            f"Browserbase={self.config.browserbase_max_concurrent} concurrent"
        )

    async def _get_redis(self) -> Optional["aioredis.Redis"]:
        """Get or create Redis connection."""
        if not REDIS_AVAILABLE or not self.redis_url:
            return None

        if self._redis is None:
            try:
                self._redis = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                # Test connection
                await self._redis.ping()
                logger.info("Connected to Redis for rate limiting")
            except Exception as e:
                logger.warning(f"Redis connection failed, using memory: {e}")
                self._redis = None

        return self._redis

    # ========== Apollo.io Rate Limiting ==========

    def _apollo_minute_key(self) -> str:
        """Get Redis key for Apollo minute window."""
        minute = datetime.utcnow().strftime("%Y-%m-%d-%H-%M")
        return f"rate_limit:apollo:minute:{minute}"

    def _apollo_hour_key(self) -> str:
        """Get Redis key for Apollo hour window."""
        hour = datetime.utcnow().strftime("%Y-%m-%d-%H")
        return f"rate_limit:apollo:hour:{hour}"

    def _apollo_day_key(self) -> str:
        """Get Redis key for Apollo day window."""
        day = datetime.utcnow().strftime("%Y-%m-%d")
        return f"rate_limit:apollo:day:{day}"

    def _apollo_credits_key(self) -> str:
        """Get Redis key for Apollo credits used today."""
        day = datetime.utcnow().strftime("%Y-%m-%d")
        return f"rate_limit:apollo:credits:{day}"

    def _apollo_tokens_key(self) -> str:
        """Get Redis key for Apollo tokens used today."""
        day = datetime.utcnow().strftime("%Y-%m-%d")
        return f"rate_limit:apollo:tokens:{day}"

    async def get_apollo_usage(self) -> ApolloUsageStats:
        """
        Get current Apollo usage statistics.

        Returns:
            ApolloUsageStats with current usage across all windows
        """
        redis = await self._get_redis()
        now = datetime.utcnow()

        if redis:
            try:
                # Get counts from Redis
                minute_count = await redis.get(self._apollo_minute_key()) or 0
                hour_count = await redis.get(self._apollo_hour_key()) or 0
                day_count = await redis.get(self._apollo_day_key()) or 0
                credits_today = await redis.get(self._apollo_credits_key()) or 0
                tokens_today = await redis.get(self._apollo_tokens_key()) or 0

                return ApolloUsageStats(
                    requests_this_minute=int(minute_count),
                    requests_this_hour=int(hour_count),
                    requests_this_day=int(day_count),
                    credits_used_today=int(credits_today),
                    tokens_used_today=int(tokens_today),
                    last_request_time=now,
                )
            except Exception as e:
                logger.error(f"Redis error getting Apollo usage: {e}")

        # Fallback to memory - clean up old data first
        self._cleanup_memory_apollo()

        return ApolloUsageStats(
            requests_this_minute=len(self._memory_storage["apollo_minute"]),
            requests_this_hour=len(self._memory_storage["apollo_hour"]),
            requests_this_day=self._memory_storage["apollo_day_count"],
            credits_used_today=self._memory_storage["apollo_credits_today"],
            tokens_used_today=self._memory_storage["apollo_tokens_today"],
        )

    def _cleanup_memory_apollo(self):
        """Clean up expired in-memory Apollo tracking data."""
        now = datetime.utcnow()
        today = now.strftime("%Y-%m-%d")

        # Reset day counter if new day
        if self._memory_storage["apollo_day_date"] != today:
            self._memory_storage["apollo_day_count"] = 0
            self._memory_storage["apollo_day_date"] = today
            self._memory_storage["apollo_credits_today"] = 0
            self._memory_storage["apollo_tokens_today"] = 0

        # Filter minute window (keep last 60 seconds)
        minute_ago = now - timedelta(minutes=1)
        self._memory_storage["apollo_minute"] = [
            t for t in self._memory_storage["apollo_minute"]
            if t > minute_ago
        ]

        # Filter hour window (keep last 60 minutes)
        hour_ago = now - timedelta(hours=1)
        self._memory_storage["apollo_hour"] = [
            t for t in self._memory_storage["apollo_hour"]
            if t > hour_ago
        ]

    async def can_use_apollo(
        self,
        endpoint: Optional[str] = None,
        check_credits: bool = True,
    ) -> bool:
        """
        Check if Apollo API can be used (under all limits).

        Args:
            endpoint: Optional endpoint name for endpoint-specific limits
            check_credits: Whether to check credit budget

        Returns:
            True if under all limits
        """
        usage = await self.get_apollo_usage()
        config = self.config.apollo

        # Check minute limit
        minute_limit = config.requests_per_minute
        if endpoint == "people_search":
            minute_limit = config.people_search_per_minute
        elif endpoint == "bulk_enrich":
            minute_limit = config.bulk_enrich_per_minute

        if usage.requests_this_minute >= minute_limit:
            logger.warning(
                f"Apollo minute limit reached: {usage.requests_this_minute}/{minute_limit}"
            )
            return False

        # Check hour limit
        if usage.requests_this_hour >= config.requests_per_hour:
            logger.warning(
                f"Apollo hourly limit reached: {usage.requests_this_hour}/{config.requests_per_hour}"
            )
            return False

        # Check day limit
        if usage.requests_this_day >= config.requests_per_day:
            logger.warning(
                f"Apollo daily limit reached: {usage.requests_this_day}/{config.requests_per_day}"
            )
            return False

        # Check credit budget
        if check_credits:
            credit_limit = config.daily_credit_budget - config.credit_safety_buffer
            if usage.credits_used_today >= credit_limit:
                logger.warning(
                    f"Apollo credit budget near limit: {usage.credits_used_today}/{config.daily_credit_budget}"
                )
                return False

        return True

    async def record_apollo_usage(
        self,
        credits: int = 1,
        tokens: int = 0,
    ) -> ApolloUsageStats:
        """
        Record Apollo API usage.

        Args:
            credits: Number of credits consumed (default: 1 per enrichment)
            tokens: Number of tokens consumed (for AI features)

        Returns:
            Updated usage statistics
        """
        redis = await self._get_redis()
        now = datetime.utcnow()

        if redis:
            try:
                # Increment minute counter (expires in 2 minutes)
                minute_key = self._apollo_minute_key()
                await redis.incr(minute_key)
                await redis.expire(minute_key, 120)

                # Increment hour counter (expires in 2 hours)
                hour_key = self._apollo_hour_key()
                await redis.incr(hour_key)
                await redis.expire(hour_key, 7200)

                # Increment day counter (expires at midnight + 1 hour)
                day_key = self._apollo_day_key()
                await redis.incr(day_key)
                # Calculate seconds until midnight
                tomorrow = (now + timedelta(days=1)).replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
                ttl = int((tomorrow - now).total_seconds()) + 3600
                await redis.expire(day_key, ttl)

                # Track credits
                if credits > 0:
                    credits_key = self._apollo_credits_key()
                    await redis.incrby(credits_key, credits)
                    await redis.expire(credits_key, ttl)

                # Track tokens
                if tokens > 0:
                    tokens_key = self._apollo_tokens_key()
                    await redis.incrby(tokens_key, tokens)
                    await redis.expire(tokens_key, ttl)

                logger.debug(f"Apollo usage recorded: +{credits} credits, +{tokens} tokens")

            except Exception as e:
                logger.error(f"Redis error recording Apollo usage: {e}")

        else:
            # Fallback to memory
            self._cleanup_memory_apollo()
            self._memory_storage["apollo_minute"].append(now)
            self._memory_storage["apollo_hour"].append(now)
            self._memory_storage["apollo_day_count"] += 1
            self._memory_storage["apollo_credits_today"] += credits
            self._memory_storage["apollo_tokens_today"] += tokens

        return await self.get_apollo_usage()

    async def wait_for_apollo_rate_limit(
        self,
        endpoint: Optional[str] = None,
        max_wait_seconds: float = 120,
    ) -> bool:
        """
        Wait until Apollo API request is allowed.

        Args:
            endpoint: Optional endpoint name for specific limits
            max_wait_seconds: Maximum time to wait

        Returns:
            True if allowed within timeout, False if exceeded
        """
        start_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            if await self.can_use_apollo(endpoint=endpoint):
                return True

            # Wait longer if we hit daily limit (no point retrying quickly)
            usage = await self.get_apollo_usage()
            if usage.requests_this_day >= self.config.apollo.requests_per_day:
                logger.warning("Apollo daily limit reached - stopping wait")
                return False

            # Short delay before retry
            await asyncio.sleep(2)

        logger.warning(f"Apollo rate limit wait timeout after {max_wait_seconds}s")
        return False

    async def get_apollo_remaining(self) -> Dict[str, int]:
        """
        Get remaining Apollo capacity across all windows.

        Returns:
            Dictionary with remaining requests per window
        """
        usage = await self.get_apollo_usage()
        config = self.config.apollo

        return {
            "minute": max(0, config.requests_per_minute - usage.requests_this_minute),
            "hour": max(0, config.requests_per_hour - usage.requests_this_hour),
            "day": max(0, config.requests_per_day - usage.requests_this_day),
            "credits": max(0, config.daily_credit_budget - usage.credits_used_today),
        }

    # ========== Hunter.io Rate Limiting ==========

    def _hunter_key(self) -> str:
        """Get Redis key for current month's Hunter usage."""
        month = datetime.utcnow().strftime("%Y-%m")
        return f"rate_limit:hunter:{month}"

    async def get_hunter_usage(self) -> int:
        """Get current Hunter.io usage count for this month."""
        redis = await self._get_redis()

        if redis:
            try:
                count = await redis.get(self._hunter_key())
                return int(count) if count else 0
            except Exception as e:
                logger.error(f"Redis error getting Hunter usage: {e}")

        # Fallback to memory
        current_month = datetime.utcnow().strftime("%Y-%m")
        if self._memory_storage["hunter_month"] != current_month:
            # Reset for new month
            self._memory_storage["hunter_count"] = 0
            self._memory_storage["hunter_month"] = current_month

        return self._memory_storage["hunter_count"]

    async def can_use_hunter(self) -> bool:
        """
        Check if Hunter.io can be used (under quota).

        Returns:
            True if under quota with safety buffer
        """
        usage = await self.get_hunter_usage()
        limit = self.config.hunter_monthly_limit - self.config.hunter_safety_buffer

        can_use = usage < limit

        if not can_use:
            logger.warning(
                f"Hunter.io quota near limit: {usage}/{self.config.hunter_monthly_limit} "
                f"(buffer: {self.config.hunter_safety_buffer})"
            )

        return can_use

    async def record_hunter_usage(self, count: int = 1) -> int:
        """
        Record Hunter.io API usage.

        Args:
            count: Number of requests to record

        Returns:
            New total usage count
        """
        redis = await self._get_redis()

        if redis:
            try:
                key = self._hunter_key()
                new_count = await redis.incrby(key, count)

                # Set expiry to end of month + 1 day
                now = datetime.utcnow()
                next_month = (now.replace(day=28) + timedelta(days=4)).replace(day=1)
                ttl = int((next_month - now).total_seconds()) + 86400
                await redis.expire(key, ttl)

                logger.info(f"Hunter.io usage: {new_count}/{self.config.hunter_monthly_limit}")
                return new_count

            except Exception as e:
                logger.error(f"Redis error recording Hunter usage: {e}")

        # Fallback to memory
        self._memory_storage["hunter_count"] += count
        return self._memory_storage["hunter_count"]

    async def get_hunter_remaining(self) -> int:
        """Get remaining Hunter.io requests for this month."""
        usage = await self.get_hunter_usage()
        return max(0, self.config.hunter_monthly_limit - usage)

    # ========== Browserbase Rate Limiting ==========

    def _browserbase_key(self) -> str:
        """Get Redis key for Browserbase sessions."""
        return "rate_limit:browserbase:sessions"

    @asynccontextmanager
    async def browserbase_semaphore(self):
        """
        Context manager for Browserbase session limiting.

        Limits concurrent sessions to prevent overload.
        Includes TTL-based cleanup for stuck sessions.

        Usage:
            async with rate_limiter.browserbase_semaphore():
                page = await browserbase.new_page()
                # ... do work
        """
        redis = await self._get_redis()
        session_id = f"{time.time()}"

        if redis:
            try:
                # Try to acquire slot with Redis
                key = self._browserbase_key()

                # Use SETNX-based semaphore
                while True:
                    current = await redis.scard(key)
                    if current < self.config.browserbase_max_concurrent:
                        # Add session with TTL
                        await redis.sadd(key, session_id)
                        await redis.expire(key, self.config.browserbase_session_ttl_seconds)
                        break
                    else:
                        # Wait and retry
                        logger.debug(f"Browserbase at capacity ({current}), waiting...")
                        await asyncio.sleep(1)

                try:
                    yield
                finally:
                    # Release slot
                    await redis.srem(key, session_id)

                return

            except Exception as e:
                logger.warning(f"Redis semaphore error, using local: {e}")

        # Fallback to local semaphore
        async with self._browserbase_semaphore:
            yield

    async def get_browserbase_active(self) -> int:
        """Get number of active Browserbase sessions."""
        redis = await self._get_redis()

        if redis:
            try:
                return await redis.scard(self._browserbase_key())
            except Exception:
                pass

        # Estimate from local semaphore
        return self.config.browserbase_max_concurrent - self._browserbase_semaphore._value

    # ========== Generic API Rate Limiting (Token Bucket) ==========

    def _api_key(self, api_name: str) -> str:
        """Get Redis key for API rate limiting."""
        return f"rate_limit:api:{api_name}"

    async def check_api_rate_limit(
        self,
        api_name: str,
        requests_per_minute: Optional[int] = None,
    ) -> bool:
        """
        Check if API request is allowed under rate limit.

        Uses sliding window rate limiting.

        Args:
            api_name: API identifier (e.g., "cerebras", "deepseek")
            requests_per_minute: Override default limit

        Returns:
            True if request is allowed
        """
        limit = requests_per_minute or self.config.cerebras_requests_per_minute
        window_seconds = 60

        redis = await self._get_redis()

        if redis:
            try:
                key = self._api_key(api_name)
                now = time.time()
                window_start = now - window_seconds

                # Remove old entries
                await redis.zremrangebyscore(key, 0, window_start)

                # Count current window
                count = await redis.zcard(key)

                return count < limit

            except Exception as e:
                logger.warning(f"Redis rate limit check error: {e}")

        # Fallback: always allow (no memory tracking for APIs)
        return True

    async def record_api_request(self, api_name: str) -> None:
        """
        Record an API request for rate limiting.

        Args:
            api_name: API identifier
        """
        redis = await self._get_redis()

        if redis:
            try:
                key = self._api_key(api_name)
                now = time.time()

                # Add timestamp to sorted set
                await redis.zadd(key, {str(now): now})

                # Set TTL for cleanup
                await redis.expire(key, 120)  # 2 minutes

            except Exception as e:
                logger.warning(f"Redis rate limit record error: {e}")

    async def wait_for_api_rate_limit(
        self,
        api_name: str,
        requests_per_minute: Optional[int] = None,
        max_wait_seconds: float = 60,
    ) -> bool:
        """
        Wait until API request is allowed under rate limit.

        Args:
            api_name: API identifier
            requests_per_minute: Override default limit
            max_wait_seconds: Maximum time to wait

        Returns:
            True if allowed within max_wait, False if timeout
        """
        start_time = time.time()

        while time.time() - start_time < max_wait_seconds:
            if await self.check_api_rate_limit(api_name, requests_per_minute):
                return True
            await asyncio.sleep(0.5)

        logger.warning(f"API rate limit wait timeout for {api_name}")
        return False

    # ========== Status and Health ==========

    async def get_status(self) -> dict:
        """
        Get current rate limiter status.

        Returns:
            Status dictionary with all limits and usage
        """
        hunter_usage = await self.get_hunter_usage()
        browserbase_active = await self.get_browserbase_active()
        apollo_usage = await self.get_apollo_usage()
        apollo_remaining = await self.get_apollo_remaining()

        return {
            "apollo": {
                "usage": apollo_usage.to_dict(),
                "remaining": apollo_remaining,
                "limits": {
                    "requests_per_minute": self.config.apollo.requests_per_minute,
                    "requests_per_hour": self.config.apollo.requests_per_hour,
                    "requests_per_day": self.config.apollo.requests_per_day,
                    "daily_credit_budget": self.config.apollo.daily_credit_budget,
                },
                "at_limit": not await self.can_use_apollo(check_credits=False),
            },
            "hunter": {
                "used": hunter_usage,
                "limit": self.config.hunter_monthly_limit,
                "remaining": self.config.hunter_monthly_limit - hunter_usage,
                "at_limit": hunter_usage >= (
                    self.config.hunter_monthly_limit - self.config.hunter_safety_buffer
                ),
            },
            "browserbase": {
                "active_sessions": browserbase_active,
                "max_concurrent": self.config.browserbase_max_concurrent,
            },
            "cerebras": {
                "requests_per_minute": self.config.cerebras_requests_per_minute,
            },
            "redis_connected": self._redis is not None,
        }

    async def close(self) -> None:
        """Close Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None


# ========== Factory Function ==========

def create_rate_limiter(
    redis_url: Optional[str] = None,
    hunter_limit: int = 50,
    browserbase_concurrent: int = 5,
    apollo_hourly: int = 200,
    apollo_daily: int = 2000,
    apollo_credit_budget: int = 500,
) -> BatchRateLimiter:
    """
    Factory function to create a BatchRateLimiter.

    Args:
        redis_url: Redis connection URL
        hunter_limit: Hunter.io monthly limit
        browserbase_concurrent: Max Browserbase sessions
        apollo_hourly: Apollo requests per hour
        apollo_daily: Apollo requests per day
        apollo_credit_budget: Apollo daily credit budget

    Returns:
        Configured BatchRateLimiter instance
    """
    import os

    # Use environment variable if not provided
    redis_url = redis_url or os.getenv("REDIS_URL")

    # Load Apollo limits from environment
    apollo_config = ApolloRateLimitConfig(
        requests_per_hour=int(os.getenv("APOLLO_RATE_LIMIT_HOURLY", apollo_hourly)),
        requests_per_day=int(os.getenv("APOLLO_RATE_LIMIT_DAILY", apollo_daily)),
        daily_credit_budget=int(os.getenv("APOLLO_DAILY_CREDIT_BUDGET", apollo_credit_budget)),
    )

    config = RateLimitConfig(
        apollo=apollo_config,
        hunter_monthly_limit=hunter_limit,
        browserbase_max_concurrent=browserbase_concurrent,
    )

    return BatchRateLimiter(redis_url=redis_url, config=config)
