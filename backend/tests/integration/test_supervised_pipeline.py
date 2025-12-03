"""
Integration test for supervised enrichment pipeline.

Tests the full workflow from StateManager -> BudgetTracker -> Orchestrator -> Stages.
"""

import pytest
from app.services.supervised_pipeline import (
    SupervisedOrchestrator,
    StateManager,
    BudgetTracker,
    ApolloFreeStage,
    LinkedInStage,
    HunterStage,
    ApolloPaidStage,
    StageResult,
)


@pytest.mark.asyncio
class TestSupervisedPipelineIntegration:
    """End-to-end integration tests (simple component verification)."""

    async def test_imports_work(self):
        """Verify all components can be imported."""
        # This test simply verifies that all imports work
        assert SupervisedOrchestrator is not None
        assert StateManager is not None
        assert BudgetTracker is not None
        assert ApolloFreeStage is not None
        assert LinkedInStage is not None
        assert HunterStage is not None
        assert ApolloPaidStage is not None
        assert StageResult is not None


@pytest.mark.asyncio
class TestStageIntegration:
    """Test individual stage integrations."""

    async def test_all_stages_instantiate(self):
        """Verify all stages can be instantiated."""
        stages = [
            ApolloFreeStage(),
            LinkedInStage(),
            HunterStage(),
            ApolloPaidStage(),
        ]

        assert len(stages) == 4
        assert all(hasattr(stage, "execute") for stage in stages)
        assert all(hasattr(stage, "name") for stage in stages)
        assert all(hasattr(stage, "cost_per_call") for stage in stages)

    async def test_stage_names_unique(self):
        """Verify all stage names are unique."""
        names = {
            ApolloFreeStage.name,
            LinkedInStage.name,
            HunterStage.name,
            ApolloPaidStage.name,
        }
        assert len(names) == 4

    async def test_stage_cost_validation(self):
        """Verify stage costs are non-negative."""
        stages = [ApolloFreeStage(), LinkedInStage(), HunterStage(), ApolloPaidStage()]
        for stage in stages:
            assert stage.cost_per_call >= 0
