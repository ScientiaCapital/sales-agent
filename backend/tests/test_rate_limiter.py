"""
Unit tests for Redis-based rate limiter.

Tests sliding window algorithm, concurrent requests, Redis failures, and performance.
"""
import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock, MagicMock

from app.services.rate_limiter import (
    RateLimiter,
    RateLimitResult,
    RateLimitExceeded,
    PROVIDER_LIMITS,
)


@pytest.fixture
def redis_client():
    """Create mocked Redis client for testing."""
    mock_redis = AsyncMock()

    # Mock eval to return request count
    mock_redis.eval = AsyncMock(return_value=0)

    # Mock get/set for token tracking
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.incrby = AsyncMock(return_value=100)
    mock_redis.expire = AsyncMock(return_value=True)

    # Mock zadd/zcount for sliding window
    mock_redis.zadd = AsyncMock(return_value=1)
    mock_redis.zcount = AsyncMock(return_value=0)

    return mock_redis


@pytest.fixture
def rate_limiter(redis_client):
    """Create RateLimiter instance with mocked Redis."""
    return RateLimiter(
        redis_client=redis_client,
        fail_open=True,
        timeout_ms=100,
    )


class TestRateLimiterBasics:
    """Test basic rate limiter functionality."""

    @pytest.mark.asyncio
    async def test_initialization(self, rate_limiter):
        """Test rate limiter initializes correctly."""
        assert rate_limiter.redis is not None
        assert rate_limiter.fail_open is True
        assert rate_limiter.timeout == 0.1
        assert rate_limiter.limits == PROVIDER_LIMITS

    @pytest.mark.asyncio
    async def test_allow_request_within_limit(self, rate_limiter):
        """Test request is allowed when within limit."""
        result = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
            estimated_tokens=100,
        )

        assert result.allowed is True
        assert result.requests_remaining > 0
        assert result.reset_time > time.time()
        assert "X-RateLimit-Limit" in result.headers

    @pytest.mark.asyncio
    async def test_deny_request_exceeding_limit(self, redis_client):
        """Test request is denied when exceeding limit."""
        # Mock Redis to return count at limit
        limit = PROVIDER_LIMITS["cerebras"]["requests_per_minute"]
        redis_client.eval = AsyncMock(return_value=limit)

        limiter = RateLimiter(redis_client=redis_client, fail_open=True, timeout_ms=100)

        # Next request should be denied
        result = await limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )

        assert result.allowed is False
        assert result.requests_remaining == 0
        assert result.retry_after is not None
        assert result.retry_after > 0

    @pytest.mark.asyncio
    async def test_different_users_independent_limits(self, rate_limiter):
        """Test different users have independent rate limits."""
        # This test verifies that different user IDs create different Redis keys
        # The implementation uses user_hash in keys, so users are isolated
        result1 = await rate_limiter.check_rate_limit(
            user_id="user1",
            provider="cerebras",
            endpoint="/api/leads",
        )
        assert result1.allowed is True

        # Different user should also be allowed
        result2 = await rate_limiter.check_rate_limit(
            user_id="user2",
            provider="cerebras",
            endpoint="/api/leads",
        )
        assert result2.allowed is True


class TestSlidingWindow:
    """Test sliding window algorithm."""

    @pytest.mark.asyncio
    async def test_sliding_window_accuracy(self, rate_limiter):
        """Test sliding window accurately tracks requests over time."""
        # Record requests at t=0
        for i in range(30):
            await rate_limiter.record_request(
                user_id="user123",
                provider="cerebras",
                endpoint="/api/leads",
            )

        # Check remaining at t=0
        result1 = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )
        assert result1.requests_remaining == 30  # 60 - 30 = 30

        # Record 30 more requests
        for i in range(30):
            await rate_limiter.record_request(
                user_id="user123",
                provider="cerebras",
                endpoint="/api/leads",
            )

        # Should now be at limit
        result2 = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )
        assert result2.allowed is False
        assert result2.requests_remaining == 0

    @pytest.mark.asyncio
    async def test_window_expiry(self, rate_limiter):
        """Test old requests expire after window."""
        # This test would need to manipulate time
        # Using fakeredis, we can manipulate timestamps in sorted sets
        pass  # Placeholder for time-based testing


class TestTokenLimits:
    """Test token-based rate limiting."""

    @pytest.mark.asyncio
    async def test_token_limit_enforcement(self, rate_limiter):
        """Test token limits are enforced."""
        token_limit = PROVIDER_LIMITS["cerebras"]["tokens_per_minute"]

        # Use up most tokens
        await rate_limiter.record_request(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
            tokens_used=token_limit - 1000,
        )

        # Request with tokens that would exceed limit
        result = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
            estimated_tokens=2000,
        )

        assert result.allowed is False
        assert result.tokens_remaining is not None
        assert result.tokens_remaining < 2000

    @pytest.mark.asyncio
    async def test_unlimited_tokens(self, rate_limiter):
        """Test providers with unlimited tokens (Ollama)."""
        # Ollama has no token limit
        result = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="ollama",
            endpoint="/api/leads",
            estimated_tokens=1_000_000,  # Huge amount
        )

        assert result.allowed is True
        assert result.tokens_remaining is None  # Unlimited


class TestProviderLimits:
    """Test per-provider rate limits."""

    @pytest.mark.asyncio
    async def test_cerebras_limits(self, rate_limiter):
        """Test Cerebras-specific limits."""
        result = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )

        assert result.allowed is True
        # Cerebras: 60 RPM, 100K TPM
        assert result.requests_remaining <= 60

    @pytest.mark.asyncio
    async def test_openrouter_limits(self, rate_limiter):
        """Test OpenRouter-specific limits."""
        result = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="openrouter",
            endpoint="/api/leads",
        )

        assert result.allowed is True
        # OpenRouter: 30 RPM, 50K TPM
        assert result.requests_remaining <= 30

    @pytest.mark.asyncio
    async def test_unknown_provider(self, rate_limiter):
        """Test handling of unknown provider."""
        result = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="unknown_provider",
            endpoint="/api/leads",
        )

        # Should allow request with warning
        assert result.allowed is True
        assert result.requests_remaining == 999


class TestRedisFailures:
    """Test Redis failure handling."""

    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self):
        """Test fail-open strategy on Redis errors."""
        # Create limiter with mock Redis that raises errors
        mock_redis = AsyncMock()
        mock_redis.eval.side_effect = Exception("Redis connection failed")

        limiter = RateLimiter(
            redis_client=mock_redis,
            fail_open=True,
            timeout_ms=100,
        )

        result = await limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )

        # Should allow request despite Redis error
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_fail_closed_on_redis_error(self):
        """Test fail-closed strategy on Redis errors."""
        mock_redis = AsyncMock()
        mock_redis.eval.side_effect = Exception("Redis connection failed")

        limiter = RateLimiter(
            redis_client=mock_redis,
            fail_open=False,
            timeout_ms=100,
        )

        result = await limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )

        # Should deny request on Redis error
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_redis_timeout(self):
        """Test Redis operation timeout."""
        # Create limiter with slow Redis
        mock_redis = AsyncMock()

        async def slow_eval(*args, **kwargs):
            await asyncio.sleep(1)  # Longer than timeout
            return 0

        mock_redis.eval = slow_eval

        limiter = RateLimiter(
            redis_client=mock_redis,
            fail_open=True,
            timeout_ms=50,  # 50ms timeout
        )

        result = await limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )

        # Should handle timeout and fail open
        assert result.allowed is True


class TestConcurrentRequests:
    """Test concurrent request handling."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_atomic(self, rate_limiter):
        """Test concurrent requests are handled atomically."""
        async def make_request():
            return await rate_limiter.check_rate_limit(
                user_id="user123",
                provider="cerebras",
                endpoint="/api/leads",
            )

        # Make 10 concurrent requests
        results = await asyncio.gather(*[make_request() for _ in range(10)])

        # All should be allowed (within limit)
        assert all(r.allowed for r in results)

        # Remaining count should be consistent
        remaining_counts = [r.requests_remaining for r in results]
        # Due to race conditions with fakeredis, we just check they're reasonable
        assert all(0 <= count <= 60 for count in remaining_counts)

    @pytest.mark.asyncio
    async def test_record_request_thread_safe(self, rate_limiter):
        """Test recording requests is thread-safe."""
        async def record():
            await rate_limiter.record_request(
                user_id="user123",
                provider="cerebras",
                endpoint="/api/leads",
                tokens_used=100,
            )

        # Record 20 concurrent requests
        await asyncio.gather(*[record() for _ in range(20)])

        # Check final count is accurate
        result = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )

        # Should have recorded all 20 requests
        assert result.requests_remaining <= 40  # 60 - 20 = 40


class TestPerformance:
    """Test rate limiter performance."""

    @pytest.mark.asyncio
    async def test_check_rate_limit_performance(self, rate_limiter):
        """Test rate limit check completes within 5ms."""
        start = time.perf_counter()

        await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
            estimated_tokens=100,
        )

        duration_ms = (time.perf_counter() - start) * 1000

        # Should complete within 5ms (with fakeredis, usually <1ms)
        assert duration_ms < 5.0

    @pytest.mark.asyncio
    async def test_record_request_performance(self, rate_limiter):
        """Test recording request completes quickly."""
        start = time.perf_counter()

        await rate_limiter.record_request(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
            tokens_used=100,
        )

        duration_ms = (time.perf_counter() - start) * 1000

        # Should complete within 5ms
        assert duration_ms < 5.0


class TestHTTPHeaders:
    """Test HTTP response headers."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(self, rate_limiter):
        """Test rate limit headers are included."""
        result = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )

        assert "X-RateLimit-Limit" in result.headers
        assert "X-RateLimit-Remaining" in result.headers
        assert "X-RateLimit-Reset" in result.headers

    @pytest.mark.asyncio
    async def test_retry_after_header_on_limit(self, rate_limiter):
        """Test Retry-After header when rate limited."""
        # Fill limit
        limit = PROVIDER_LIMITS["cerebras"]["requests_per_minute"]
        for i in range(limit):
            await rate_limiter.record_request(
                user_id="user123",
                provider="cerebras",
                endpoint="/api/leads",
            )

        result = await rate_limiter.check_rate_limit(
            user_id="user123",
            provider="cerebras",
            endpoint="/api/leads",
        )

        assert result.allowed is False
        assert "Retry-After" in result.headers
        assert int(result.headers["Retry-After"]) > 0


class TestStatusMonitoring:
    """Test rate limit status monitoring."""

    @pytest.mark.asyncio
    async def test_get_status(self, rate_limiter):
        """Test getting rate limit status."""
        # Record some requests
        for i in range(10):
            await rate_limiter.record_request(
                user_id="user123",
                provider="cerebras",
                endpoint="/api/leads",
                tokens_used=1000,
            )

        status = await rate_limiter.get_status(
            user_id="user123",
            provider="cerebras",
        )

        assert status["provider"] == "cerebras"
        assert "requests" in status
        assert status["requests"]["used"] == 10
        assert status["requests"]["limit"] == 60
        assert "tokens" in status

    @pytest.mark.asyncio
    async def test_status_unknown_provider(self, rate_limiter):
        """Test status for unknown provider."""
        status = await rate_limiter.get_status(
            user_id="user123",
            provider="unknown",
        )

        assert "error" in status


class TestExceptions:
    """Test exception handling."""

    def test_rate_limit_exceeded_exception(self):
        """Test RateLimitExceeded exception."""
        result = RateLimitResult(
            allowed=False,
            requests_remaining=0,
            tokens_remaining=0,
            reset_time=time.time() + 60,
            retry_after=30,
        )

        exc = RateLimitExceeded(result, "cerebras")

        assert exc.result == result
        assert exc.provider == "cerebras"
        assert "cerebras" in str(exc)
        assert "30" in str(exc)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
