"""Tests for SupervisedOrchestrator."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.supervised_pipeline.stages.base import StageResult


class TestSupervisedOrchestrator:
    """Test SupervisedOrchestrator functionality."""

    @pytest.fixture
    def mock_state_manager(self):
        """Create mock StateManager."""
        manager = AsyncMock()
        manager.init_company = AsyncMock()
        manager.update_stage_status = AsyncMock()
        manager.sync_to_supabase = AsyncMock()
        manager.mark_complete = AsyncMock()
        manager.mark_failed = AsyncMock()
        manager.get_company_status = AsyncMock(return_value={})
        return manager

    @pytest.fixture
    def mock_budget_tracker(self):
        """Create mock BudgetTracker."""
        tracker = AsyncMock()
        tracker.can_proceed = AsyncMock(return_value=True)
        tracker.add_cost = AsyncMock(return_value=0.05)
        tracker.increment_processed = AsyncMock()
        tracker.get_status = AsyncMock(return_value={"spent_usd": 0.0, "limit_usd": 5.0})
        return tracker

    @pytest.mark.asyncio
    async def test_enrich_single_company(self, mock_state_manager, mock_budget_tracker):
        """Test enriching a single company through all stages."""
        from app.services.supervised_pipeline.orchestrator import SupervisedOrchestrator

        orchestrator = SupervisedOrchestrator(
            state_manager=mock_state_manager,
            budget_tracker=mock_budget_tracker,
        )

        # Mock all stages to return success
        mock_result = StageResult(success=True, data={"contacts": []}, cost_usd=0.01, latency_ms=100)
        for stage in orchestrator.stages:
            stage.execute = AsyncMock(return_value=mock_result)

        company = {"id": "test-123", "name": "Test Co", "domain": "test.com"}
        result = await orchestrator.enrich_company(company)

        assert result["success"] is True
        assert result["company_id"] == "test-123"
        mock_state_manager.mark_complete.assert_called_once()

    @pytest.mark.asyncio
    async def test_parallel_batch(self, mock_state_manager, mock_budget_tracker):
        """Test processing 2 companies in parallel."""
        from app.services.supervised_pipeline.orchestrator import SupervisedOrchestrator

        orchestrator = SupervisedOrchestrator(
            state_manager=mock_state_manager,
            budget_tracker=mock_budget_tracker,
        )

        mock_result = StageResult(success=True, data={}, cost_usd=0.0, latency_ms=100)
        for stage in orchestrator.stages:
            stage.execute = AsyncMock(return_value=mock_result)

        companies = [
            {"id": "test-1", "name": "Company 1", "domain": "c1.com"},
            {"id": "test-2", "name": "Company 2", "domain": "c2.com"},
        ]

        results = await orchestrator.process_batch(companies)

        assert len(results) == 2
        assert all(r["success"] for r in results)

    @pytest.mark.asyncio
    async def test_budget_exceeded_stops_processing(self, mock_state_manager, mock_budget_tracker):
        """Test that processing stops when budget is exceeded."""
        from app.services.supervised_pipeline.orchestrator import SupervisedOrchestrator

        # Budget exceeded after first check
        mock_budget_tracker.can_proceed = AsyncMock(return_value=False)

        orchestrator = SupervisedOrchestrator(
            state_manager=mock_state_manager,
            budget_tracker=mock_budget_tracker,
        )

        company = {"id": "test-123", "name": "Test Co", "domain": "test.com"}
        result = await orchestrator.enrich_company(company)

        # Should still return success but with budget_exceeded flag
        assert "budget_exceeded" in result or result.get("stages_completed", 0) == 0
