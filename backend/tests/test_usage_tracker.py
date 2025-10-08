"""
Unit tests for unified usage tracker service
"""
import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch
from sqlalchemy.orm import Session

from app.services.usage_tracker import UsageTracker
from app.models.unified_api_call import APICallLog, ProviderType, OperationType


@pytest.fixture
def mock_db():
    """Mock database session"""
    db = Mock(spec=Session)
    db.add = Mock()
    db.commit = Mock()
    db.refresh = Mock()
    db.execute = Mock()
    return db


@pytest.fixture
def mock_redis():
    """Mock Redis client"""
    redis = AsyncMock()
    redis.get = AsyncMock(return_value=None)
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
def tracker(mock_db, mock_redis):
    """Create UsageTracker instance with mocks"""
    return UsageTracker(db=mock_db, redis_client=mock_redis)


class TestCostCalculation:
    """Test cost calculation logic for different providers"""

    def test_cerebras_per_request_pricing(self, tracker):
        """Cerebras uses per-request pricing"""
        cost, input_cost, output_cost = UsageTracker.calculate_cost(
            provider=ProviderType.CEREBRAS,
            model="llama3.1-8b",
            prompt_tokens=100,
            completion_tokens=200
        )

        assert cost == 0.000006  # Fixed per-request cost
        assert input_cost is None
        assert output_cost is None

    def test_anthropic_per_token_pricing(self, tracker):
        """Anthropic uses per-token pricing"""
        cost, input_cost, output_cost = UsageTracker.calculate_cost(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-sonnet",
            prompt_tokens=1000,  # 0.001M tokens
            completion_tokens=500  # 0.0005M tokens
        )

        # Claude Sonnet: $3/M input, $15/M output
        expected_input = (1000 / 1_000_000) * 3.00
        expected_output = (500 / 1_000_000) * 15.00
        expected_total = expected_input + expected_output

        assert cost == pytest.approx(expected_total, abs=1e-8)
        assert input_cost == pytest.approx(expected_input, abs=1e-8)
        assert output_cost == pytest.approx(expected_output, abs=1e-8)

    def test_deepseek_per_token_pricing(self, tracker):
        """DeepSeek uses per-token pricing"""
        cost, input_cost, output_cost = UsageTracker.calculate_cost(
            provider=ProviderType.DEEPSEEK,
            model="deepseek-chat",
            prompt_tokens=2000,
            completion_tokens=1000
        )

        # DeepSeek Chat: $0.27/M input, $1.10/M output
        expected_input = (2000 / 1_000_000) * 0.27
        expected_output = (1000 / 1_000_000) * 1.10
        expected_total = expected_input + expected_output

        assert cost == pytest.approx(expected_total, abs=1e-8)
        assert input_cost == pytest.approx(expected_input, abs=1e-8)
        assert output_cost == pytest.approx(expected_output, abs=1e-8)

    def test_ollama_free_pricing(self, tracker):
        """Ollama is free (local inference)"""
        cost, input_cost, output_cost = UsageTracker.calculate_cost(
            provider=ProviderType.OLLAMA,
            model="llama3.1:8b",
            prompt_tokens=1000,
            completion_tokens=500
        )

        assert cost == 0.0
        assert input_cost == 0.0
        assert output_cost == 0.0

    def test_openrouter_default_pricing(self, tracker):
        """OpenRouter uses default pricing for unknown models"""
        cost, input_cost, output_cost = UsageTracker.calculate_cost(
            provider=ProviderType.OPENROUTER,
            model="unknown-model",
            prompt_tokens=1000,
            completion_tokens=500
        )

        # Default: $0.50/M input, $1.50/M output
        expected_input = (1000 / 1_000_000) * 0.50
        expected_output = (500 / 1_000_000) * 1.50
        expected_total = expected_input + expected_output

        assert cost == pytest.approx(expected_total, abs=1e-8)


class TestAPICallLogging:
    """Test API call logging functionality"""

    @pytest.mark.asyncio
    async def test_log_api_call_success(self, tracker, mock_db, mock_redis):
        """Test successful API call logging"""
        log_entry = await tracker.log_api_call(
            provider=ProviderType.CEREBRAS,
            model="llama3.1-8b",
            endpoint="/chat/completions",
            prompt_tokens=100,
            completion_tokens=200,
            latency_ms=633,
            operation_type=OperationType.QUALIFICATION,
            cache_hit=False,
            user_id="test_user",
            success=True
        )

        # Verify database operations
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()
        mock_db.refresh.assert_called_once()

        # Verify Redis cache invalidation
        mock_redis.delete.assert_called_once_with(UsageTracker.REDIS_CACHE_KEY)

    @pytest.mark.asyncio
    async def test_log_api_call_with_error(self, tracker, mock_db):
        """Test logging failed API call with error message"""
        await tracker.log_api_call(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-sonnet",
            endpoint="/v1/messages",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=1000,
            operation_type=OperationType.RESEARCH,
            success=False,
            error_message="Rate limit exceeded"
        )

        mock_db.add.assert_called_once()
        added_log = mock_db.add.call_args[0][0]
        assert added_log.success is False
        assert added_log.error_message == "Rate limit exceeded"

    @pytest.mark.asyncio
    async def test_log_api_call_cache_hit(self, tracker, mock_db):
        """Test logging cached API call"""
        await tracker.log_api_call(
            provider=ProviderType.CEREBRAS,
            model="llama3.1-8b",
            endpoint="/chat/completions",
            prompt_tokens=50,
            completion_tokens=100,
            latency_ms=10,  # Fast cached response
            operation_type=OperationType.QUALIFICATION,
            cache_hit=True
        )

        mock_db.add.assert_called_once()
        added_log = mock_db.add.call_args[0][0]
        assert added_log.cache_hit is True
        assert added_log.latency_ms == 10

    @pytest.mark.asyncio
    async def test_redis_cache_invalidation_failure_handled(self, tracker, mock_db, mock_redis):
        """Test that Redis failures don't block logging"""
        mock_redis.delete.side_effect = Exception("Redis connection failed")

        # Should not raise exception
        await tracker.log_api_call(
            provider=ProviderType.CEREBRAS,
            model="llama3.1-8b",
            endpoint="/chat/completions",
            prompt_tokens=100,
            completion_tokens=200,
            latency_ms=633,
            operation_type=OperationType.QUALIFICATION
        )

        # Database operations should still complete
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()


class TestRealTimeMetrics:
    """Test real-time metrics with Redis caching"""

    @pytest.mark.asyncio
    async def test_real_time_metrics_cache_hit(self, tracker, mock_redis):
        """Test Redis cache hit returns cached data"""
        cached_data = {
            "total_cost": 1.50,
            "total_requests": 100,
            "by_provider": {
                "cerebras": {"requests": 80, "cost_usd": 0.000480},
                "anthropic": {"requests": 20, "cost_usd": 1.499520}
            }
        }

        import json
        mock_redis.get.return_value = json.dumps(cached_data)

        result = await tracker.get_real_time_metrics()

        assert result == cached_data
        mock_redis.get.assert_called_once_with(UsageTracker.REDIS_CACHE_KEY)

    @pytest.mark.asyncio
    async def test_real_time_metrics_cache_miss(self, tracker, mock_db, mock_redis):
        """Test cache miss triggers database query and caching"""
        mock_redis.get.return_value = None

        # Mock database query results
        mock_result = Mock()
        mock_result.total_requests = 50
        mock_result.total_cost = 0.75
        mock_result.avg_latency = 800
        mock_result.provider = ProviderType.CEREBRAS

        mock_db.execute.return_value.all.return_value = [mock_result]

        result = await tracker.get_real_time_metrics()

        # Verify database queried
        assert mock_db.execute.called

        # Verify Redis caching attempted
        mock_redis.setex.assert_called_once()
        call_args = mock_redis.setex.call_args
        assert call_args[0][0] == UsageTracker.REDIS_CACHE_KEY
        assert call_args[0][1] == UsageTracker.REDIS_CACHE_TTL

    @pytest.mark.asyncio
    async def test_real_time_metrics_redis_unavailable(self, tracker, mock_db):
        """Test graceful degradation when Redis unavailable"""
        tracker._cache_enabled = False
        tracker.redis = None

        # Mock database query
        mock_result = Mock()
        mock_result.total_requests = 25
        mock_result.total_cost = 0.50
        mock_result.avg_latency = 600
        mock_result.provider = ProviderType.ANTHROPIC

        mock_db.execute.return_value.all.return_value = [mock_result]

        result = await tracker.get_real_time_metrics()

        # Should still return metrics from database
        assert "total_requests" in result
        assert "total_cost" in result


class TestAggregations:
    """Test time-series aggregation queries"""

    def test_get_aggregates_hourly(self, tracker, mock_db):
        """Test hourly aggregation"""
        start_date = datetime(2025, 10, 1, 0, 0, 0)
        end_date = datetime(2025, 10, 1, 23, 59, 59)

        # Mock database results
        mock_result = Mock()
        mock_result.period = datetime(2025, 10, 1, 10, 0, 0)
        mock_result.total_requests = 10
        mock_result.total_cost = 0.10
        mock_result.avg_latency = 750
        mock_result.total_tokens = 5000

        mock_db.execute.return_value.all.return_value = [mock_result]

        results = tracker.get_aggregates(
            start_date=start_date,
            end_date=end_date,
            interval="hour"
        )

        assert len(results) == 1
        assert results[0]["total_requests"] == 10
        assert results[0]["total_cost_usd"] == 0.10

    def test_get_aggregates_with_provider_filter(self, tracker, mock_db):
        """Test aggregation with provider filter"""
        start_date = datetime(2025, 10, 1, 0, 0, 0)
        end_date = datetime(2025, 10, 1, 23, 59, 59)

        mock_db.execute.return_value.all.return_value = []

        tracker.get_aggregates(
            start_date=start_date,
            end_date=end_date,
            interval="day",
            provider=ProviderType.CEREBRAS
        )

        # Verify query executed
        assert mock_db.execute.called

    def test_get_aggregates_invalid_interval(self, tracker, mock_db):
        """Test invalid interval raises ValueError"""
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 10, 2)

        with pytest.raises(ValueError, match="interval must be"):
            tracker.get_aggregates(
                start_date=start_date,
                end_date=end_date,
                interval="invalid"
            )


class TestCostBreakdown:
    """Test cost breakdown queries"""

    def test_get_cost_by_provider(self, tracker, mock_db):
        """Test cost breakdown by provider"""
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 10, 7)

        # Mock results for two providers
        mock_results = [
            Mock(provider=ProviderType.CEREBRAS, total_cost=0.50),
            Mock(provider=ProviderType.ANTHROPIC, total_cost=5.00),
        ]

        mock_db.execute.return_value.all.return_value = mock_results

        result = tracker.get_cost_by_provider(
            start_date=start_date,
            end_date=end_date
        )

        assert result["cerebras"] == 0.50
        assert result["anthropic"] == 5.00
        assert len(result) == 2


class TestLatencyPercentiles:
    """Test latency percentile calculations"""

    def test_get_latency_percentiles(self, tracker, mock_db):
        """Test p50, p95, p99 latency calculations"""
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 10, 7)

        # Mock percentile results
        mock_result = Mock(p50=500, p95=1500, p99=3000)
        mock_db.execute.return_value.first.return_value = mock_result

        result = tracker.get_latency_percentiles(
            start_date=start_date,
            end_date=end_date
        )

        assert result["p50"] == 500
        assert result["p95"] == 1500
        assert result["p99"] == 3000

    def test_get_latency_percentiles_with_provider_filter(self, tracker, mock_db):
        """Test latency percentiles for specific provider"""
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 10, 7)

        mock_result = Mock(p50=600, p95=1000, p99=2000)
        mock_db.execute.return_value.first.return_value = mock_result

        result = tracker.get_latency_percentiles(
            start_date=start_date,
            end_date=end_date,
            provider=ProviderType.CEREBRAS
        )

        assert result["p50"] == 600

    def test_get_latency_percentiles_no_data(self, tracker, mock_db):
        """Test percentiles with no data returns zeros"""
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 10, 7)

        mock_db.execute.return_value.first.return_value = None

        result = tracker.get_latency_percentiles(
            start_date=start_date,
            end_date=end_date
        )

        assert result == {"p50": 0, "p95": 0, "p99": 0}


class TestSuccessRate:
    """Test success rate calculations"""

    def test_get_success_rate(self, tracker, mock_db):
        """Test success rate calculation"""
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 10, 7)

        # Mock: 95 successful out of 100 total
        mock_result = Mock(total=100, successful=95)
        mock_db.execute.return_value.first.return_value = mock_result

        success_rate = tracker.get_success_rate(
            start_date=start_date,
            end_date=end_date
        )

        assert success_rate == 95.0

    def test_get_success_rate_zero_calls(self, tracker, mock_db):
        """Test success rate with no API calls"""
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 10, 7)

        mock_result = Mock(total=0, successful=0)
        mock_db.execute.return_value.first.return_value = mock_result

        success_rate = tracker.get_success_rate(
            start_date=start_date,
            end_date=end_date
        )

        assert success_rate == 0.0

    def test_get_success_rate_with_provider(self, tracker, mock_db):
        """Test success rate for specific provider"""
        start_date = datetime(2025, 10, 1)
        end_date = datetime(2025, 10, 7)

        mock_result = Mock(total=50, successful=49)
        mock_db.execute.return_value.first.return_value = mock_result

        success_rate = tracker.get_success_rate(
            start_date=start_date,
            end_date=end_date,
            provider=ProviderType.ANTHROPIC
        )

        assert success_rate == 98.0
