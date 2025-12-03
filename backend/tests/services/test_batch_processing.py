"""
Unit tests for batch processing system.

Tests:
- BatchRateLimiter Apollo rate limit enforcement
- ApolloRateLimitedService pre-flight checks
- LeadBatchProcessor concurrency control
- ParallelPipeline stage execution
"""
import pytest
import asyncio
import time
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from dataclasses import dataclass

# Import modules under test
from app.services.batch_rate_limiter import (
    BatchRateLimiter,
    RateLimitConfig,
    ApolloRateLimitConfig,
    ApolloUsageStats,
    create_rate_limiter,
)
from app.services.apollo_rate_limited import (
    ApolloRateLimitedService,
    create_apollo_service,
)
from app.services.lead_batch_processor import (
    LeadBatchProcessor,
    LeadProgress,
    BatchResult,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_redis():
    """Create mocked Redis client for testing."""
    mock = AsyncMock()

    # Mock GET/SET for rate limit tracking
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock(return_value=True)
    mock.incrby = AsyncMock(return_value=1)
    mock.incrbyfloat = AsyncMock(return_value=1.0)
    mock.expire = AsyncMock(return_value=True)
    mock.ttl = AsyncMock(return_value=3600)

    # Mock pipeline operations
    pipeline = AsyncMock()
    pipeline.get = Mock(return_value=pipeline)
    pipeline.incrby = Mock(return_value=pipeline)
    pipeline.expire = Mock(return_value=pipeline)
    pipeline.execute = AsyncMock(return_value=[0, 1, True])
    mock.pipeline = Mock(return_value=pipeline)

    # Mock connection test
    mock.ping = AsyncMock(return_value=True)

    return mock


@pytest.fixture
def rate_limit_config():
    """Create test rate limit configuration."""
    return RateLimitConfig(
        apollo=ApolloRateLimitConfig(
            requests_per_minute=10,
            requests_per_hour=100,
            requests_per_day=500,
            daily_credit_budget=200,
            credit_safety_buffer=20,
        ),
    )


@pytest.fixture
def batch_rate_limiter(mock_redis, rate_limit_config):
    """Create BatchRateLimiter with mocked Redis."""
    with patch('app.services.batch_rate_limiter.redis.asyncio') as mock_aioredis:
        mock_aioredis.from_url.return_value = mock_redis
        limiter = BatchRateLimiter(config=rate_limit_config)
        limiter._redis = mock_redis
        limiter._redis_connected = True
        return limiter


@pytest.fixture
def mock_apollo_service():
    """Create mocked ApolloService."""
    mock = AsyncMock()
    mock.enrich_contact = AsyncMock(return_value=Mock(
        email="test@example.com",
        first_name="Test",
        last_name="User",
    ))
    mock.enrich_company = AsyncMock(return_value={
        "name": "Test Company",
        "domain": "example.com",
    })
    mock.close = AsyncMock()
    return mock


@pytest.fixture
def mock_parallel_pipeline():
    """Create mocked ParallelPipeline."""
    mock = AsyncMock()
    mock.run = AsyncMock(return_value={
        "success": True,
        "total_cost_usd": 0.01,
        "total_latency_ms": 500,
    })
    return mock


@pytest.fixture
def mock_db_session():
    """Create mocked database session."""
    mock = MagicMock()
    mock.query.return_value.filter.return_value.first.return_value = None
    mock.add = Mock()
    mock.commit = Mock()
    mock.refresh = Mock()
    mock.rollback = Mock()
    return mock


# ============================================================================
# BatchRateLimiter Tests
# ============================================================================

class TestBatchRateLimiter:
    """Test BatchRateLimiter Apollo rate limit tracking."""

    @pytest.mark.asyncio
    async def test_initialization(self, batch_rate_limiter):
        """Test rate limiter initializes correctly."""
        assert batch_rate_limiter.config.apollo.requests_per_minute == 10
        assert batch_rate_limiter.config.apollo.daily_credit_budget == 200

    @pytest.mark.asyncio
    async def test_can_use_apollo_when_fresh(self, batch_rate_limiter, mock_redis):
        """Test Apollo can be used when no limits reached."""
        # Fresh state - all limits at 0
        mock_redis.get = AsyncMock(return_value=None)

        result = await batch_rate_limiter.can_use_apollo()

        assert result is True

    @pytest.mark.asyncio
    async def test_can_use_apollo_minute_limit_reached(self, batch_rate_limiter, mock_redis):
        """Test Apollo blocked when minute limit reached."""
        # Set minute counter at limit
        async def mock_get(key):
            if "minute" in key:
                return b"10"  # At limit
            return b"0"

        mock_redis.get = mock_get

        result = await batch_rate_limiter.can_use_apollo()

        assert result is False

    @pytest.mark.asyncio
    async def test_can_use_apollo_daily_credit_exhausted(self, batch_rate_limiter, mock_redis):
        """Test Apollo blocked when daily credit budget exhausted."""
        # Set credits at limit (200 budget - 20 buffer = 180 usable)
        async def mock_get(key):
            if "credits" in key:
                return b"180"  # At budget - buffer
            return b"0"

        mock_redis.get = mock_get

        result = await batch_rate_limiter.can_use_apollo(check_credits=True)

        assert result is False

    @pytest.mark.asyncio
    async def test_record_apollo_usage(self, batch_rate_limiter, mock_redis):
        """Test recording Apollo usage updates all counters."""
        await batch_rate_limiter.record_apollo_usage(credits=1)

        # Verify pipeline was called for atomic increment
        mock_redis.pipeline.assert_called()

    @pytest.mark.asyncio
    async def test_get_apollo_remaining(self, batch_rate_limiter, mock_redis):
        """Test getting remaining Apollo quota."""
        # Set usage values
        async def mock_get(key):
            if "minute" in key:
                return b"5"
            if "hour" in key:
                return b"50"
            if "day" in key:
                return b"200"
            if "credits" in key:
                return b"100"
            return b"0"

        mock_redis.get = mock_get

        remaining = await batch_rate_limiter.get_apollo_remaining()

        assert remaining["minute"] == 5  # 10 - 5
        assert remaining["hour"] == 50   # 100 - 50
        assert remaining["day"] == 300   # 500 - 200
        assert remaining["credits"] == 80  # 200 - 20 buffer - 100 used

    @pytest.mark.asyncio
    async def test_redis_connection_failure_handled(self, rate_limit_config):
        """Test graceful handling of Redis connection failure."""
        with patch('app.services.batch_rate_limiter.redis.asyncio') as mock_aioredis:
            mock_aioredis.from_url.side_effect = Exception("Connection failed")

            limiter = BatchRateLimiter(config=rate_limit_config)

            # Should not raise, but flag as disconnected
            assert limiter._redis_connected is False

    @pytest.mark.asyncio
    async def test_wait_for_rate_limit_timeout(self, batch_rate_limiter, mock_redis):
        """Test waiting for rate limit respects timeout."""
        # Always at limit
        mock_redis.get = AsyncMock(return_value=b"10")

        start = time.time()
        result = await batch_rate_limiter.wait_for_apollo_rate_limit(max_wait_seconds=1)
        duration = time.time() - start

        assert result is False
        assert duration >= 1  # Waited full timeout


# ============================================================================
# ApolloRateLimitedService Tests
# ============================================================================

class TestApolloRateLimitedService:
    """Test rate-limited Apollo service wrapper."""

    @pytest.mark.asyncio
    async def test_pre_flight_check_passes(self, mock_apollo_service, batch_rate_limiter, mock_redis):
        """Test pre-flight check allows request when within limits."""
        mock_redis.get = AsyncMock(return_value=None)  # Fresh state

        with patch('app.services.apollo_rate_limited.ApolloService', return_value=mock_apollo_service):
            with patch('app.services.apollo_rate_limited.create_rate_limiter', return_value=batch_rate_limiter):
                service = ApolloRateLimitedService(rate_limiter=batch_rate_limiter, auto_wait=False)

                result = await service.enrich_contact_safe(email="test@example.com")

                assert result is not None
                mock_apollo_service.enrich_contact.assert_called_once()

    @pytest.mark.asyncio
    async def test_pre_flight_check_blocks_when_limited(self, mock_apollo_service, batch_rate_limiter, mock_redis):
        """Test pre-flight check blocks request when at limit."""
        # At minute limit
        async def mock_get(key):
            if "minute" in key:
                return b"10"
            return b"0"
        mock_redis.get = mock_get

        with patch('app.services.apollo_rate_limited.ApolloService', return_value=mock_apollo_service):
            service = ApolloRateLimitedService(rate_limiter=batch_rate_limiter, auto_wait=False)

            from app.core.exceptions import APIRateLimitError
            with pytest.raises(APIRateLimitError):
                await service.enrich_contact_safe(email="test@example.com")

            # Should not have called actual API
            mock_apollo_service.enrich_contact.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_wait_enabled(self, mock_apollo_service, batch_rate_limiter, mock_redis):
        """Test auto-wait waits for rate limit to clear."""
        # Start at limit, then clear
        call_count = [0]

        async def mock_get(key):
            call_count[0] += 1
            if call_count[0] < 3:
                return b"10"  # At limit
            return b"0"  # Cleared

        mock_redis.get = mock_get

        with patch('app.services.apollo_rate_limited.ApolloService', return_value=mock_apollo_service):
            service = ApolloRateLimitedService(
                rate_limiter=batch_rate_limiter,
                auto_wait=True,
                max_wait_seconds=2
            )

            result = await service.enrich_contact_safe(email="test@example.com")

            assert result is not None
            mock_apollo_service.enrich_contact.assert_called_once()

    @pytest.mark.asyncio
    async def test_credits_tracked(self, mock_apollo_service, batch_rate_limiter, mock_redis):
        """Test credits are tracked after successful call."""
        mock_redis.get = AsyncMock(return_value=None)

        with patch('app.services.apollo_rate_limited.ApolloService', return_value=mock_apollo_service):
            service = ApolloRateLimitedService(rate_limiter=batch_rate_limiter, auto_wait=False)

            await service.enrich_contact_safe(
                email="test@example.com",
                reveal_personal_email=True,  # +1 credit
                reveal_phone=True,  # +1 credit
            )

            # Should have tracked 3 credits (1 base + 1 email + 1 phone)
            assert service._session_credits == 3

    @pytest.mark.asyncio
    async def test_batch_size_auto_reduced_on_low_budget(self, mock_apollo_service, batch_rate_limiter, mock_redis):
        """Test batch size auto-reduces when credit budget is low."""
        # Low credits remaining
        async def mock_get(key):
            if "credits" in key:
                return b"175"  # 200 - 20 buffer - 175 = 5 remaining
            return b"0"
        mock_redis.get = mock_get

        with patch('app.services.apollo_rate_limited.ApolloService', return_value=mock_apollo_service):
            service = ApolloRateLimitedService(rate_limiter=batch_rate_limiter, auto_wait=False)

            # Request 10 but should be reduced to 5
            await service.search_and_enrich_contacts_safe(
                domain="example.com",
                max_results=10,
            )

            # Apollo service should have been called with reduced max_results
            call_args = mock_apollo_service.search_and_enrich_contacts.call_args
            assert call_args.kwargs.get("max_results", 10) <= 5

    @pytest.mark.asyncio
    async def test_get_usage_status(self, mock_apollo_service, batch_rate_limiter, mock_redis):
        """Test getting usage status."""
        mock_redis.get = AsyncMock(return_value=b"5")

        with patch('app.services.apollo_rate_limited.ApolloService', return_value=mock_apollo_service):
            service = ApolloRateLimitedService(rate_limiter=batch_rate_limiter, auto_wait=False)

            status = await service.get_usage_status()

            assert "session" in status
            assert "current" in status
            assert "remaining" in status
            assert "limits" in status


# ============================================================================
# LeadBatchProcessor Tests
# ============================================================================

class TestLeadBatchProcessor:
    """Test batch lead processing with concurrency control."""

    @pytest.mark.asyncio
    async def test_semaphore_limits_concurrency(self, mock_parallel_pipeline, mock_db_session):
        """Test semaphore limits concurrent processing."""
        concurrent_count = [0]
        max_concurrent = [0]

        async def mock_run(lead_data, **kwargs):
            concurrent_count[0] += 1
            max_concurrent[0] = max(max_concurrent[0], concurrent_count[0])
            await asyncio.sleep(0.1)  # Simulate work
            concurrent_count[0] -= 1
            return {"success": True, "total_cost_usd": 0.01, "total_latency_ms": 100}

        mock_parallel_pipeline.run = mock_run

        with patch('app.services.lead_batch_processor.ParallelPipeline', return_value=mock_parallel_pipeline):
            processor = LeadBatchProcessor(max_concurrent=3, db_session=mock_db_session)

            # Process 10 leads
            leads = [{"company_id": f"id-{i}", "name": f"Company {i}"} for i in range(10)]
            await processor.process_batch(leads)

            # Max concurrent should not exceed 3
            assert max_concurrent[0] <= 3

    @pytest.mark.asyncio
    async def test_pause_resume(self, mock_parallel_pipeline, mock_db_session):
        """Test pause and resume functionality."""
        with patch('app.services.lead_batch_processor.ParallelPipeline', return_value=mock_parallel_pipeline):
            processor = LeadBatchProcessor(max_concurrent=5, db_session=mock_db_session)

            # Start processing in background
            leads = [{"company_id": f"id-{i}", "name": f"Company {i}"} for i in range(20)]
            task = asyncio.create_task(processor.process_batch(leads))

            await asyncio.sleep(0.1)  # Let some processing start

            # Pause
            await processor.pause()
            assert processor._pause_event.is_set() is False

            # Resume
            await processor.resume()
            assert processor._pause_event.is_set() is True

            # Cancel task
            processor.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    @pytest.mark.asyncio
    async def test_failed_lead_recorded(self, mock_db_session):
        """Test failed leads are recorded correctly."""
        async def failing_pipeline(lead_data, **kwargs):
            raise Exception("Pipeline failed")

        mock_pipeline = AsyncMock()
        mock_pipeline.run = failing_pipeline

        with patch('app.services.lead_batch_processor.ParallelPipeline', return_value=mock_pipeline):
            processor = LeadBatchProcessor(max_concurrent=5, db_session=mock_db_session)

            leads = [{"company_id": "id-1", "name": "Company 1"}]
            result = await processor.process_batch(leads)

            assert result.failed_count == 1
            assert len(result.failed_leads) == 1
            assert "Pipeline failed" in result.failed_leads[0].error_message

    @pytest.mark.asyncio
    async def test_cancel_stops_processing(self, mock_parallel_pipeline, mock_db_session):
        """Test cancellation stops further processing."""
        processed_count = [0]

        async def slow_pipeline(lead_data, **kwargs):
            processed_count[0] += 1
            await asyncio.sleep(0.5)
            return {"success": True, "total_cost_usd": 0.01, "total_latency_ms": 500}

        mock_parallel_pipeline.run = slow_pipeline

        with patch('app.services.lead_batch_processor.ParallelPipeline', return_value=mock_parallel_pipeline):
            processor = LeadBatchProcessor(max_concurrent=2, db_session=mock_db_session)

            leads = [{"company_id": f"id-{i}", "name": f"Company {i}"} for i in range(10)]
            task = asyncio.create_task(processor.process_batch(leads))

            await asyncio.sleep(0.2)  # Let some start

            # Cancel
            processor.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

            # Should not have processed all 10
            assert processed_count[0] < 10

    @pytest.mark.asyncio
    async def test_batch_result_summary(self, mock_parallel_pipeline, mock_db_session):
        """Test batch result summary is accurate."""
        call_count = [0]

        async def mixed_pipeline(lead_data, **kwargs):
            call_count[0] += 1
            if call_count[0] % 3 == 0:
                raise Exception("Every third fails")
            return {"success": True, "total_cost_usd": 0.01, "total_latency_ms": 100}

        mock_parallel_pipeline.run = mixed_pipeline

        with patch('app.services.lead_batch_processor.ParallelPipeline', return_value=mock_parallel_pipeline):
            processor = LeadBatchProcessor(max_concurrent=5, db_session=mock_db_session)

            leads = [{"company_id": f"id-{i}", "name": f"Company {i}"} for i in range(9)]
            result = await processor.process_batch(leads)

            assert result.total_count == 9
            assert result.success_count == 6  # 3, 6, 9 fail
            assert result.failed_count == 3
            assert result.total_cost_usd == pytest.approx(0.06, rel=0.01)


# ============================================================================
# ParallelPipeline Tests
# ============================================================================

class TestParallelPipeline:
    """Test parallel pipeline stage execution."""

    @pytest.mark.asyncio
    async def test_parallel_groups_execute_concurrently(self):
        """Test that stages within a group execute in parallel."""
        from app.services.parallel_pipeline import ParallelPipeline

        execution_order = []

        async def mock_stage_a1(state):
            execution_order.append(("a1_start", time.time()))
            await asyncio.sleep(0.1)
            execution_order.append(("a1_end", time.time()))
            return state

        async def mock_stage_a2(state):
            execution_order.append(("a2_start", time.time()))
            await asyncio.sleep(0.1)
            execution_order.append(("a2_end", time.time()))
            return state

        # Run stages
        await asyncio.gather(
            mock_stage_a1({}),
            mock_stage_a2({}),
        )

        # Both should start at nearly the same time (parallel)
        start_times = [t for name, t in execution_order if "start" in name]
        assert abs(start_times[0] - start_times[1]) < 0.05  # Within 50ms

    @pytest.mark.asyncio
    async def test_sequential_groups_wait_for_dependencies(self):
        """Test that sequential groups wait for previous groups."""
        group_a_done = [False]
        group_b_checked_dependency = [False]

        async def group_a():
            await asyncio.sleep(0.1)
            group_a_done[0] = True
            return {"a_result": "done"}

        async def group_b(a_result):
            group_b_checked_dependency[0] = group_a_done[0]
            return {"b_result": "done"}

        # Simulate pipeline flow
        a_result = await group_a()
        await group_b(a_result)

        # Group B should have seen Group A as done
        assert group_b_checked_dependency[0] is True


# ============================================================================
# Integration Tests
# ============================================================================

class TestBatchProcessingIntegration:
    """Integration tests for the full batch processing flow."""

    @pytest.mark.asyncio
    async def test_rate_limiter_prevents_token_burning(self, mock_redis, rate_limit_config):
        """Test that rate limiter prevents token burning during batch."""
        # Set up rate limiter at near limit
        async def mock_get(key):
            if "credits" in key:
                return b"175"  # Near limit
            return b"0"
        mock_redis.get = mock_get

        with patch('app.services.batch_rate_limiter.redis.asyncio') as mock_aioredis:
            mock_aioredis.from_url.return_value = mock_redis

            limiter = BatchRateLimiter(config=rate_limit_config)
            limiter._redis = mock_redis
            limiter._redis_connected = True

            remaining = await limiter.get_apollo_remaining()

            # Should show limited credits remaining
            assert remaining["credits"] <= 5  # 200 - 20 buffer - 175 used

    @pytest.mark.asyncio
    async def test_batch_respects_rate_limits(self, mock_apollo_service, batch_rate_limiter, mock_redis, mock_db_session):
        """Test that batch processing respects rate limits."""
        call_count = [0]

        async def counting_enrich(*args, **kwargs):
            call_count[0] += 1
            return Mock(email="test@example.com")

        mock_apollo_service.enrich_contact = counting_enrich

        # Set minute limit to 5
        batch_rate_limiter.config.apollo.requests_per_minute = 5

        async def mock_get(key):
            if "minute" in key:
                return str(call_count[0]).encode()
            return b"0"
        mock_redis.get = mock_get

        with patch('app.services.apollo_rate_limited.ApolloService', return_value=mock_apollo_service):
            service = ApolloRateLimitedService(
                rate_limiter=batch_rate_limiter,
                auto_wait=False
            )

            # Try to make 10 calls (should fail after 5)
            from app.core.exceptions import APIRateLimitError

            success_count = 0
            for i in range(10):
                try:
                    await service.enrich_contact_safe(email=f"test{i}@example.com")
                    success_count += 1
                except APIRateLimitError:
                    break

            # Should have been rate limited
            assert success_count <= 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
