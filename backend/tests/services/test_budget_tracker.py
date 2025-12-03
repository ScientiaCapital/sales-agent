"""Tests for BudgetTracker - per-batch cost limits."""

import pytest
from unittest.mock import AsyncMock


class TestBudgetTracker:
    """Test BudgetTracker functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.hset = AsyncMock()
        redis.hget = AsyncMock(return_value=b"0.0")
        redis.hgetall = AsyncMock(return_value={})
        redis.hincrby = AsyncMock()
        redis.hincrbyfloat = AsyncMock(return_value=0.05)
        return redis

    @pytest.mark.asyncio
    async def test_init_batch(self, mock_redis):
        """Test initializing a new batch with budget."""
        from app.services.supervised_pipeline.budget_tracker import BudgetTracker

        tracker = BudgetTracker(redis=mock_redis, batch_id="batch-001", limit_usd=5.0)
        await tracker.init_batch(total_companies=100)

        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_can_proceed_under_budget(self, mock_redis):
        """Test can_proceed returns True when under budget."""
        from app.services.supervised_pipeline.budget_tracker import BudgetTracker

        mock_redis.hget.return_value = b"1.50"

        tracker = BudgetTracker(redis=mock_redis, batch_id="batch-001", limit_usd=5.0)
        can_proceed = await tracker.can_proceed()

        assert can_proceed is True

    @pytest.mark.asyncio
    async def test_can_proceed_over_budget(self, mock_redis):
        """Test can_proceed returns False when over budget."""
        from app.services.supervised_pipeline.budget_tracker import BudgetTracker

        mock_redis.hget.return_value = b"5.50"

        tracker = BudgetTracker(redis=mock_redis, batch_id="batch-001", limit_usd=5.0)
        can_proceed = await tracker.can_proceed()

        assert can_proceed is False

    @pytest.mark.asyncio
    async def test_add_cost_atomic(self, mock_redis):
        """Test adding cost uses atomic HINCRBYFLOAT."""
        from app.services.supervised_pipeline.budget_tracker import BudgetTracker

        tracker = BudgetTracker(redis=mock_redis, batch_id="batch-001", limit_usd=5.0)
        await tracker.add_cost(0.05)

        # Verify atomic increment was used (not read-modify-write)
        mock_redis.hincrbyfloat.assert_called()
