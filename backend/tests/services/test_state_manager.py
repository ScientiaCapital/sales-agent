"""Tests for StateManager - Redis + Supabase state tracking."""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Direct import to avoid services package __init__.py
backend_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(backend_path))

# Import directly from module file
import importlib.util
spec = importlib.util.spec_from_file_location(
    "state_manager",
    backend_path / "app" / "services" / "supervised_pipeline" / "state_manager.py"
)
state_manager_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(state_manager_module)
StateManager = state_manager_module.StateManager


class TestStateManager:
    """Test StateManager functionality."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        redis = AsyncMock()
        redis.hset = AsyncMock()
        redis.hget = AsyncMock(return_value=None)
        redis.hgetall = AsyncMock(return_value={})
        redis.delete = AsyncMock()
        return redis

    @pytest.fixture
    def mock_supabase(self):
        """Create mock Supabase client."""
        supabase = MagicMock()
        supabase.table.return_value.update.return_value.eq.return_value.execute = MagicMock()
        return supabase

    @pytest.mark.asyncio
    async def test_update_stage_status(self, mock_redis, mock_supabase):
        """Test updating company stage status in Redis."""
        manager = StateManager(redis=mock_redis, supabase=mock_supabase)

        await manager.update_stage_status(
            company_id="test-123",
            stage="apollo_free",
            status="done"
        )

        mock_redis.hset.assert_called()

    @pytest.mark.asyncio
    async def test_get_company_status(self, mock_redis, mock_supabase):
        """Test retrieving company status from Redis."""
        mock_redis.hgetall.return_value = {
            b"stage": b"linkedin",
            b"apollo_free": b"done",
            b"linkedin": b"running",
        }

        manager = StateManager(redis=mock_redis, supabase=mock_supabase)
        status = await manager.get_company_status("test-123")

        assert status["stage"] == "linkedin"
        assert status["apollo_free"] == "done"

    @pytest.mark.asyncio
    async def test_sync_to_supabase(self, mock_redis, mock_supabase):
        """Test syncing completion status to Supabase.

        Note: sync_to_supabase is currently a no-op because dim_companies
        doesn't have per-stage tracking columns yet. This test verifies
        it doesn't error when called.
        """
        manager = StateManager(redis=mock_redis, supabase=mock_supabase)

        # Should not raise any errors (it's a no-op currently)
        await manager.sync_to_supabase(
            company_id="test-123",
            stage="apollo_free",
            cost_usd=0.0
        )

        # No assertion needed - function is a pass-through until schema updated
