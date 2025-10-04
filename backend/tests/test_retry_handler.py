"""Unit tests for retry handler with exponential backoff."""

import pytest
from unittest.mock import Mock, AsyncMock
import asyncio
from datetime import datetime

from app.services.retry_handler import RetryHandler, RetryConfig, RetryExhaustedError


@pytest.fixture
def retry_handler():
    """Create RetryHandler with test configuration."""
    config = RetryConfig(
        max_attempts=3,
        base_delay_ms=100,
        max_delay_ms=1000,
        exponential_base=2
    )
    return RetryHandler(config)


class TestRetryHandler:
    """Test suite for RetryHandler."""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self, retry_handler):
        """Test successful call on first attempt."""
        async def successful_call():
            return "success"

        result = await retry_handler.execute(successful_call)

        assert result == "success"
        assert retry_handler.get_stats()["total_calls"] == 1
        assert retry_handler.get_stats()["successful_calls"] == 1

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, retry_handler):
        """Test retries on transient failures."""
        call_count = 0

        async def flaky_call():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Transient error")
            return "success"

        result = await retry_handler.execute(flaky_call)

        assert result == "success"
        assert call_count == 3  # Failed twice, succeeded third time

    @pytest.mark.asyncio
    async def test_exhausts_retries(self, retry_handler):
        """Test raises error after exhausting retries."""
        async def always_fails():
            raise Exception("Permanent failure")

        with pytest.raises(RetryExhaustedError) as exc_info:
            await retry_handler.execute(always_fails)

        assert "after 3 attempts" in str(exc_info.value)
        assert retry_handler.get_stats()["failed_calls"] == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff(self, retry_handler):
        """Test exponential backoff delays."""
        call_times = []

        async def failing_call():
            call_times.append(datetime.now())
            raise Exception("Fail")

        with pytest.raises(RetryExhaustedError):
            await retry_handler.execute(failing_call)

        # Verify increasing delays
        assert len(call_times) == 3
        
        # First retry should have ~100ms delay
        delay1 = (call_times[1] - call_times[0]).total_seconds() * 1000
        assert 90 <= delay1 <= 150

        # Second retry should have ~200ms delay (exponential)
        delay2 = (call_times[2] - call_times[1]).total_seconds() * 1000
        assert 180 <= delay2 <= 250

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test delay is capped at max_delay_ms."""
        config = RetryConfig(
            max_attempts=5,
            base_delay_ms=100,
            max_delay_ms=200,
            exponential_base=2
        )
        handler = RetryHandler(config)
        call_times = []

        async def failing_call():
            call_times.append(datetime.now())
            raise Exception("Fail")

        with pytest.raises(RetryExhaustedError):
            await handler.execute(failing_call)

        # Later retries should be capped at max_delay
        for i in range(1, len(call_times)):
            delay = (call_times[i] - call_times[i-1]).total_seconds() * 1000
            assert delay <= 250  # Max delay + small margin

    @pytest.mark.asyncio
    async def test_retry_specific_exceptions(self):
        """Test retry only specific exception types."""
        class RetryableError(Exception):
            pass

        class NonRetryableError(Exception):
            pass

        config = RetryConfig(
            max_attempts=3,
            retryable_exceptions=[RetryableError]
        )
        handler = RetryHandler(config)

        # Retryable exception should be retried
        call_count = 0
        async def retryable_fail():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RetryableError("Retry this")
            return "success"

        result = await handler.execute(retryable_fail)
        assert result == "success"
        assert call_count == 2

        # Non-retryable exception should not be retried
        async def nonretryable_fail():
            raise NonRetryableError("Don't retry")

        with pytest.raises(NonRetryableError):
            await handler.execute(nonretryable_fail)

    @pytest.mark.asyncio
    async def test_jitter_adds_randomness(self):
        """Test jitter adds randomness to delays."""
        config = RetryConfig(
            max_attempts=3,
            base_delay_ms=100,
            jitter=True
        )
        handler = RetryHandler(config)
        
        delays = []
        for _ in range(5):
            call_times = []
            
            async def failing_call():
                call_times.append(datetime.now())
                raise Exception("Fail")

            with pytest.raises(RetryExhaustedError):
                await handler.execute(failing_call)

            if len(call_times) >= 2:
                delay = (call_times[1] - call_times[0]).total_seconds() * 1000
                delays.append(delay)

        # With jitter, delays should vary
        assert len(set([int(d/10) for d in delays])) > 1  # Different delay buckets

    @pytest.mark.asyncio
    async def test_concurrent_retries(self, retry_handler):
        """Test handling concurrent operations with retries."""
        call_counts = {i: 0 for i in range(3)}

        async def flaky_call(task_id):
            call_counts[task_id] += 1
            if call_counts[task_id] < 2:
                raise Exception(f"Fail {task_id}")
            return f"success_{task_id}"

        tasks = [
            retry_handler.execute(lambda tid=i: flaky_call(tid))
            for i in range(3)
        ]

        results = await asyncio.gather(*tasks)

        assert len(results) == 3
        assert all("success" in r for r in results)
        assert all(count == 2 for count in call_counts.values())

    def test_get_stats(self, retry_handler):
        """Test retrieving retry statistics."""
        stats = retry_handler.get_stats()

        assert "total_calls" in stats
        assert "successful_calls" in stats
        assert "failed_calls" in stats
        assert "total_retries" in stats
        assert stats["total_calls"] == 0

    @pytest.mark.asyncio
    async def test_reset_stats(self, retry_handler):
        """Test resetting statistics."""
        async def successful_call():
            return "success"

        await retry_handler.execute(successful_call)
        
        assert retry_handler.get_stats()["total_calls"] == 1

        retry_handler.reset_stats()

        assert retry_handler.get_stats()["total_calls"] == 0

    @pytest.mark.asyncio
    async def test_custom_retry_condition(self):
        """Test custom retry condition logic."""
        def should_retry(exception):
            return "retryable" in str(exception).lower()

        config = RetryConfig(
            max_attempts=3,
            retry_condition=should_retry
        )
        handler = RetryHandler(config)

        # Should retry
        call_count = 0
        async def retryable_error():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise Exception("Retryable error")
            return "success"

        result = await handler.execute(retryable_error)
        assert result == "success"
        assert call_count == 2

        # Should not retry
        async def not_retryable():
            raise Exception("Fatal error")

        with pytest.raises(Exception, match="Fatal error"):
            await handler.execute(not_retryable)


class TestRetryConfig:
    """Test RetryConfig data class."""

    def test_config_defaults(self):
        """Test default configuration values."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay_ms == 100
        assert config.max_delay_ms == 5000
        assert config.exponential_base == 2
        assert config.jitter is False

    def test_config_validation(self):
        """Test configuration validation."""
        # max_attempts must be positive
        with pytest.raises(ValueError):
            RetryConfig(max_attempts=0)

        # base_delay_ms must be positive
        with pytest.raises(ValueError):
            RetryConfig(base_delay_ms=-100)

        # max_delay_ms must be >= base_delay_ms
        with pytest.raises(ValueError):
            RetryConfig(base_delay_ms=1000, max_delay_ms=500)


class TestRetryHandlerIntegration:
    """Integration tests for retry handler in realistic scenarios."""

    @pytest.mark.asyncio
    async def test_api_call_retry_pattern(self):
        """Test typical API call retry pattern."""
        config = RetryConfig(
            max_attempts=3,
            base_delay_ms=50,
            exponential_base=2,
            jitter=True
        )
        handler = RetryHandler(config)

        # Simulate flaky API
        api_call_count = 0
        async def api_call():
            nonlocal api_call_count
            api_call_count += 1
            
            if api_call_count == 1:
                raise ConnectionError("Network timeout")
            elif api_call_count == 2:
                raise Exception("503 Service Unavailable")
            else:
                return {"status": "success", "data": "result"}

        result = await handler.execute(api_call)

        assert result["status"] == "success"
        assert api_call_count == 3

    @pytest.mark.asyncio
    async def test_database_retry_pattern(self):
        """Test database connection retry pattern."""
        config = RetryConfig(
            max_attempts=5,
            base_delay_ms=100,
            retryable_exceptions=[ConnectionError, TimeoutError]
        )
        handler = RetryHandler(config)

        attempt = 0
        async def db_query():
            nonlocal attempt
            attempt += 1
            if attempt < 3:
                raise ConnectionError("DB connection lost")
            return [{"id": 1, "name": "test"}]

        result = await handler.execute(db_query)

        assert len(result) == 1
        assert result[0]["name"] == "test"
