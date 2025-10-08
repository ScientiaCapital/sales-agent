"""
Unit tests for CostOptimizer service.

Tests budget enforcement, auto-downgrade logic, alert triggering,
and integration with UnifiedRouter.
"""

import asyncio
import json
from datetime import date
from unittest.mock import AsyncMock, Mock, patch, MagicMock
import pytest
import aioredis
from fastapi import HTTPException

from app.services.cost_optimizer import (
    CostOptimizer,
    BudgetStatus,
    ThresholdStatus,
    AlertPayload
)
from app.services.unified_router import RoutingStrategy
from app.services.unified_router_cost_integration import CostOptimizedUnifiedRouter
from app.services.usage_tracker import UsageTracker


@pytest.fixture
async def mock_redis():
    """Create a mock Redis client."""
    redis = AsyncMock(spec=aioredis.Redis)
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.setex = AsyncMock()
    redis.delete = AsyncMock()
    redis.incrbyfloat = AsyncMock()
    redis.expire = AsyncMock()
    redis.scan_iter = AsyncMock(return_value=AsyncMock(__aiter__=lambda self: self, __anext__=AsyncMock(side_effect=StopAsyncIteration)))
    return redis


@pytest.fixture
def mock_usage_tracker():
    """Create a mock UsageTracker."""
    tracker = Mock(spec=UsageTracker)
    tracker.calculate_cost = Mock(return_value=(0.001, 0.0005, 0.0005))
    return tracker


@pytest.fixture
def mock_unified_router():
    """Create a mock UnifiedRouter."""
    router = Mock()
    router.strategy = RoutingStrategy.BALANCED
    return router


@pytest.fixture
async def cost_optimizer(mock_redis, mock_usage_tracker, mock_unified_router):
    """Create a CostOptimizer instance with mocked dependencies."""
    optimizer = CostOptimizer(
        usage_tracker=mock_usage_tracker,
        unified_router=mock_unified_router,
        redis_client=mock_redis
    )
    return optimizer


class TestBudgetStatusCalculation:
    """Tests for budget status calculation."""

    @pytest.mark.asyncio
    async def test_budget_status_under_threshold(self, cost_optimizer, mock_redis):
        """Test budget status when under warning threshold (<80%)."""
        # Mock Redis to return 30 USD spend (60% of 50 USD daily budget)
        mock_redis.get.return_value = "30.0"

        status = await cost_optimizer.check_budget_status(period="daily")

        assert status.current_spend_usd == 30.0
        assert status.budget_limit_usd == 50.0
        assert status.utilization_percent == 60.0
        assert status.threshold_status == ThresholdStatus.OK
        assert "normal range" in status.recommended_action.lower()

    @pytest.mark.asyncio
    async def test_budget_status_warning_threshold(self, cost_optimizer, mock_redis):
        """Test budget status at warning threshold (80-90%)."""
        # Mock Redis to return 42 USD spend (84% of 50 USD daily budget)
        mock_redis.get.return_value = "42.0"

        status = await cost_optimizer.check_budget_status(period="daily")

        assert status.current_spend_usd == 42.0
        assert status.utilization_percent == 84.0
        assert status.threshold_status == ThresholdStatus.WARNING
        assert "BALANCED" in status.recommended_action

    @pytest.mark.asyncio
    async def test_budget_status_critical_threshold(self, cost_optimizer, mock_redis):
        """Test budget status at critical threshold (90-99%)."""
        # Mock Redis to return 47 USD spend (94% of 50 USD daily budget)
        mock_redis.get.return_value = "47.0"

        status = await cost_optimizer.check_budget_status(period="daily")

        assert status.current_spend_usd == 47.0
        assert status.utilization_percent == 94.0
        assert status.threshold_status == ThresholdStatus.CRITICAL
        assert "Auto-downgrading" in status.recommended_action

    @pytest.mark.asyncio
    async def test_budget_status_blocked_threshold(self, cost_optimizer, mock_redis):
        """Test budget status at blocked threshold (>=100%)."""
        # Mock Redis to return 52 USD spend (104% of 50 USD daily budget)
        mock_redis.get.return_value = "52.0"

        status = await cost_optimizer.check_budget_status(period="daily")

        assert status.current_spend_usd == 52.0
        assert status.utilization_percent == 104.0
        assert status.threshold_status == ThresholdStatus.BLOCKED
        assert "blocked" in status.recommended_action.lower()

    @pytest.mark.asyncio
    async def test_budget_status_caching(self, cost_optimizer, mock_redis):
        """Test that budget status is cached for 5 seconds."""
        # First call - should hit Redis
        mock_redis.get.side_effect = [None, "30.0"]  # No cache, then actual value
        status1 = await cost_optimizer.check_budget_status(period="daily")

        # Verify cache was set
        mock_redis.setex.assert_called_once()
        cache_key = mock_redis.setex.call_args[0][0]
        assert "budget:status:daily" in cache_key
        assert mock_redis.setex.call_args[0][1] == 5  # 5 second TTL

        # Second call - should return cached value
        mock_redis.get.side_effect = [status1.json(), None]  # Cache hit
        status2 = await cost_optimizer.check_budget_status(period="daily")

        assert status2.current_spend_usd == status1.current_spend_usd


class TestAutoDowngradeLogic:
    """Tests for automatic strategy downgrade."""

    @pytest.mark.asyncio
    async def test_no_downgrade_under_threshold(self, cost_optimizer):
        """Test no downgrade when under 90% threshold."""
        budget_status = BudgetStatus(
            current_spend_usd=40.0,
            budget_limit_usd=50.0,
            utilization_percent=80.0,
            threshold_status=ThresholdStatus.WARNING,
            recommended_action="Consider downgrade",
            period="daily"
        )

        new_strategy, allowed = await cost_optimizer.enforce_budget(
            current_strategy=RoutingStrategy.QUALITY_OPTIMIZED,
            budget_status=budget_status
        )

        assert new_strategy == RoutingStrategy.QUALITY_OPTIMIZED  # No change
        assert allowed is True

    @pytest.mark.asyncio
    async def test_downgrade_quality_to_balanced(self, cost_optimizer):
        """Test downgrade from QUALITY_OPTIMIZED to BALANCED at 90%."""
        budget_status = BudgetStatus(
            current_spend_usd=45.0,
            budget_limit_usd=50.0,
            utilization_percent=90.0,
            threshold_status=ThresholdStatus.CRITICAL,
            recommended_action="Auto-downgrade",
            period="daily"
        )

        # Mock alert sending
        cost_optimizer._send_alert_if_needed = AsyncMock()

        new_strategy, allowed = await cost_optimizer.enforce_budget(
            current_strategy=RoutingStrategy.QUALITY_OPTIMIZED,
            budget_status=budget_status
        )

        assert new_strategy == RoutingStrategy.BALANCED
        assert allowed is True

    @pytest.mark.asyncio
    async def test_downgrade_balanced_to_cost(self, cost_optimizer):
        """Test downgrade from BALANCED to COST_OPTIMIZED at 90%."""
        budget_status = BudgetStatus(
            current_spend_usd=46.0,
            budget_limit_usd=50.0,
            utilization_percent=92.0,
            threshold_status=ThresholdStatus.CRITICAL,
            recommended_action="Auto-downgrade",
            period="daily"
        )

        # Mock alert sending
        cost_optimizer._send_alert_if_needed = AsyncMock()

        new_strategy, allowed = await cost_optimizer.enforce_budget(
            current_strategy=RoutingStrategy.BALANCED,
            budget_status=budget_status
        )

        assert new_strategy == RoutingStrategy.COST_OPTIMIZED
        assert allowed is True

    @pytest.mark.asyncio
    async def test_block_at_100_percent(self, cost_optimizer):
        """Test request blocking at 100% budget utilization."""
        budget_status = BudgetStatus(
            current_spend_usd=50.0,
            budget_limit_usd=50.0,
            utilization_percent=100.0,
            threshold_status=ThresholdStatus.BLOCKED,
            recommended_action="Blocked",
            period="daily"
        )

        # Mock alert sending
        cost_optimizer._send_alert_if_needed = AsyncMock()

        new_strategy, allowed = await cost_optimizer.enforce_budget(
            current_strategy=RoutingStrategy.COST_OPTIMIZED,
            budget_status=budget_status
        )

        assert allowed is False  # Request should be blocked
        # Strategy doesn't change when blocked
        assert new_strategy == RoutingStrategy.COST_OPTIMIZED


class TestAlertSystem:
    """Tests for alert triggering and deduplication."""

    @pytest.mark.asyncio
    async def test_alert_sent_at_warning_threshold(self, cost_optimizer, mock_redis):
        """Test that alert is sent at 80% threshold."""
        budget_status = BudgetStatus(
            current_spend_usd=40.0,
            budget_limit_usd=50.0,
            utilization_percent=80.0,
            threshold_status=ThresholdStatus.WARNING,
            recommended_action="Consider downgrade",
            period="daily"
        )

        # Mock webhook URL
        cost_optimizer.webhook_url = "https://example.com/webhook"
        cost_optimizer.send_alert = AsyncMock()
        mock_redis.get.return_value = None  # No previous alert

        await cost_optimizer._send_alert_if_needed(
            "warning",
            budget_status,
            RoutingStrategy.QUALITY_OPTIMIZED
        )

        cost_optimizer.send_alert.assert_called_once()
        # Verify alert deduplication key was set
        mock_redis.setex.assert_called_with(
            "budget:last_alert:warning:warning",
            3600,  # 1 hour TTL
            "1"
        )

    @pytest.mark.asyncio
    async def test_alert_deduplication(self, cost_optimizer, mock_redis):
        """Test that alerts are not sent twice within 1 hour."""
        budget_status = BudgetStatus(
            current_spend_usd=40.0,
            budget_limit_usd=50.0,
            utilization_percent=80.0,
            threshold_status=ThresholdStatus.WARNING,
            recommended_action="Consider downgrade",
            period="daily"
        )

        # Mock that alert was already sent
        mock_redis.get.return_value = "1"
        cost_optimizer.send_alert = AsyncMock()

        await cost_optimizer._send_alert_if_needed(
            "warning",
            budget_status,
            RoutingStrategy.QUALITY_OPTIMIZED
        )

        # Alert should NOT be sent
        cost_optimizer.send_alert.assert_not_called()

    @pytest.mark.asyncio
    async def test_webhook_payload_structure(self, cost_optimizer):
        """Test webhook payload has correct structure."""
        budget_status = BudgetStatus(
            current_spend_usd=45.0,
            budget_limit_usd=50.0,
            utilization_percent=90.0,
            threshold_status=ThresholdStatus.CRITICAL,
            recommended_action="Auto-downgrade",
            period="daily"
        )

        # Mock HTTP client
        cost_optimizer.http_client.post = AsyncMock()
        cost_optimizer.webhook_url = "https://example.com/webhook"

        await cost_optimizer.send_alert(
            alert_type="critical",
            budget_status=budget_status,
            channels=["webhook"]
        )

        # Verify webhook was called
        cost_optimizer.http_client.post.assert_called_once()
        call_args = cost_optimizer.http_client.post.call_args

        # Check payload structure
        payload = call_args[1]["json"]
        assert payload["alert_type"] == "critical"
        assert "timestamp" in payload
        assert payload["budget_status"]["current_spend_usd"] == 45.0
        assert payload["budget_status"]["utilization_percent"] == 90.0
        assert payload["environment"] == "production"


class TestBudgetTracking:
    """Tests for budget spend tracking."""

    @pytest.mark.asyncio
    async def test_update_daily_spend(self, cost_optimizer, mock_redis):
        """Test updating daily budget spend."""
        await cost_optimizer.update_spend(cost_usd=5.25)

        today = date.today()
        daily_key = f"budget:daily:{today.isoformat()}:total_cost"

        # Verify atomic increment
        mock_redis.incrbyfloat.assert_any_call(daily_key, 5.25)
        # Verify expiry set
        mock_redis.expire.assert_any_call(daily_key, 7 * 24 * 3600)

    @pytest.mark.asyncio
    async def test_update_monthly_spend(self, cost_optimizer, mock_redis):
        """Test updating monthly budget spend."""
        await cost_optimizer.update_spend(cost_usd=10.50)

        today = date.today()
        monthly_key = f"budget:monthly:{today.strftime('%Y-%m')}:total_cost"

        # Verify atomic increment
        mock_redis.incrbyfloat.assert_any_call(monthly_key, 10.50)
        # Verify expiry set
        mock_redis.expire.assert_any_call(monthly_key, 90 * 24 * 3600)

    @pytest.mark.asyncio
    async def test_cache_invalidation_on_update(self, cost_optimizer, mock_redis):
        """Test that status cache is cleared when spend is updated."""
        # Setup mock to return cache keys
        cache_keys = [
            "budget:status:daily:global:all",
            "budget:status:monthly:user123:cerebras"
        ]
        mock_redis.scan_iter.return_value = AsyncMock(
            __aiter__=lambda self: self,
            __anext__=AsyncMock(side_effect=cache_keys + [StopAsyncIteration])
        )

        await cost_optimizer.update_spend(cost_usd=1.0)

        # Verify cache invalidation
        mock_redis.scan_iter.assert_called_with(match="budget:status:*")


class TestUnifiedRouterIntegration:
    """Tests for integration with UnifiedRouter."""

    @pytest.mark.asyncio
    async def test_router_blocks_at_100_percent(self):
        """Test that router blocks requests when budget is exhausted."""
        # Create mocks
        mock_redis = AsyncMock()
        mock_redis.get.return_value = "50.0"  # 100% of daily budget
        mock_redis.setex = AsyncMock()

        mock_db = Mock()
        usage_tracker = Mock(spec=UsageTracker)

        # Create cost-optimized router
        router = CostOptimizedUnifiedRouter(
            usage_tracker=usage_tracker,
            db=mock_db,
            redis_client=mock_redis
        )

        # Mock parent route method
        router._init_clients = Mock()
        router.available_providers = {}

        # Attempt to route when budget exhausted
        with pytest.raises(HTTPException) as exc_info:
            await router.route(
                task_type="qualification",
                prompt="Test prompt"
            )

        assert exc_info.value.status_code == 429
        assert "Daily budget exceeded" in exc_info.value.detail["error"]

    @pytest.mark.asyncio
    async def test_router_auto_downgrades_strategy(self):
        """Test that router auto-downgrades strategy at 90%."""
        # Create mocks
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = [None, "45.0"]  # 90% of daily budget
        mock_redis.setex = AsyncMock()

        mock_db = Mock()
        usage_tracker = Mock(spec=UsageTracker)

        # Create cost-optimized router
        router = CostOptimizedUnifiedRouter(
            usage_tracker=usage_tracker,
            db=mock_db,
            redis_client=mock_redis
        )

        # Mock parent route method to avoid actual API calls
        parent_route = AsyncMock(return_value=Mock(
            provider="cerebras",
            model_used="llama3.1-8b",
            cost_usd=0.001,
            latency_ms=100
        ))
        router._init_clients = Mock()
        router.available_providers = {}

        # Start with QUALITY strategy
        router.strategy = RoutingStrategy.QUALITY_OPTIMIZED

        with patch.object(router.__class__.__bases__[0], 'route', parent_route):
            await router.route(
                task_type="qualification",
                prompt="Test prompt"
            )

        # Verify strategy was downgraded
        assert router.strategy == RoutingStrategy.BALANCED

    @pytest.mark.asyncio
    async def test_optimization_rules_retrieval(self):
        """Test getting optimization rules from router."""
        mock_redis = AsyncMock()
        mock_db = Mock()
        usage_tracker = Mock(spec=UsageTracker)

        router = CostOptimizedUnifiedRouter(
            usage_tracker=usage_tracker,
            db=mock_db,
            redis_client=mock_redis
        )

        rules = router.get_optimization_rules()

        assert "current_strategy" in rules
        assert "budget_enforcement" in rules
        assert rules["budget_enforcement"] is True
        assert "thresholds" in rules
        assert "strategy_cascade" in rules


class TestPerformance:
    """Performance tests for cost optimizer."""

    @pytest.mark.asyncio
    async def test_budget_check_performance(self, cost_optimizer, mock_redis):
        """Test that budget check completes within 3ms (with cache)."""
        import time

        # Warm cache
        mock_redis.get.return_value = json.dumps({
            "current_spend_usd": 30.0,
            "budget_limit_usd": 50.0,
            "utilization_percent": 60.0,
            "threshold_status": "ok",
            "recommended_action": "Normal",
            "period": "daily"
        })

        start = time.perf_counter()
        await cost_optimizer.check_budget_status(period="daily")
        elapsed = (time.perf_counter() - start) * 1000  # Convert to ms

        assert elapsed < 3.0, f"Budget check took {elapsed:.2f}ms, expected <3ms"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])