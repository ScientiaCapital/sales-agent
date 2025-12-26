"""
Tests for HunterStage in the supervised enrichment pipeline.

Tests the cost-optimized approach:
1. FREE email count check gates expensive API calls
2. ATL filtering for decision-maker contacts
3. Proper error handling and cost tracking
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.supervised_pipeline.stages.hunter import HunterStage


@pytest.fixture
def hunter_stage():
    """Create HunterStage with mocked HunterService."""
    with patch('app.services.supervised_pipeline.stages.hunter.HunterService') as MockService:
        mock_service = MagicMock()
        MockService.return_value = mock_service
        stage = HunterStage()
        stage._hunter = mock_service
        yield stage


class TestHunterStageExecution:
    """Test HunterStage.execute() method."""

    @pytest.mark.asyncio
    async def test_execute_success_with_atl_contacts(self, hunter_stage):
        """Test successful execution finding ATL contacts."""
        # Mock email count check (FREE endpoint)
        hunter_stage._hunter.get_email_count = AsyncMock(return_value={
            "total": 25,
            "personal_emails": 20,
            "generic_emails": 5,
            "has_data": True
        })

        # Mock domain search returning ATL contacts
        hunter_stage._hunter.domain_search = AsyncMock(return_value=[
            {
                "email": "ceo@techcorp.com",
                "first_name": "John",
                "last_name": "Smith",
                "position": "CEO",
                "confidence": 95,
                "is_atl": True,
            }
        ])

        result = await hunter_stage.execute({"domain": "techcorp.com"})

        assert result.success is True
        assert result.data["contact_count"] == 1
        assert len(result.data["contacts"]) == 1
        assert result.data["contacts"][0]["email"] == "ceo@techcorp.com"
        assert result.cost_usd == 0.01  # Paid API call was made

    @pytest.mark.asyncio
    async def test_execute_skips_paid_call_when_no_data(self, hunter_stage):
        """Test that paid domain_search is skipped when email_count shows no data."""
        # Mock email count check returning no data (FREE endpoint)
        hunter_stage._hunter.get_email_count = AsyncMock(return_value={
            "total": 0,
            "personal_emails": 0,
            "generic_emails": 0,
            "has_data": False
        })

        # domain_search should NOT be called
        hunter_stage._hunter.domain_search = AsyncMock()

        result = await hunter_stage.execute({"domain": "newstartup.com"})

        assert result.success is True
        assert result.data["contact_count"] == 0
        assert result.cost_usd == 0.0  # No paid API call made
        hunter_stage._hunter.domain_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_execute_no_atl_contacts_found(self, hunter_stage):
        """Test when domain has emails but no ATL contacts."""
        # Mock email count check
        hunter_stage._hunter.get_email_count = AsyncMock(return_value={
            "total": 10,
            "has_data": True
        })

        # Mock domain search returning None (no ATL contacts)
        hunter_stage._hunter.domain_search = AsyncMock(return_value=None)

        result = await hunter_stage.execute({"domain": "noatl.com"})

        assert result.success is True
        assert result.data["contact_count"] == 0
        assert result.data["contacts"] == []
        assert result.cost_usd == 0.01  # Paid call was made but no ATL found

    @pytest.mark.asyncio
    async def test_execute_no_domain_provided(self, hunter_stage):
        """Test error handling when no domain is provided."""
        result = await hunter_stage.execute({})

        assert result.success is False
        assert result.error == "No domain provided"
        assert result.latency_ms == 0

    @pytest.mark.asyncio
    async def test_execute_api_error_handling(self, hunter_stage):
        """Test error handling for API failures."""
        hunter_stage._hunter.get_email_count = AsyncMock(
            side_effect=Exception("API connection failed")
        )

        result = await hunter_stage.execute({"domain": "example.com"})

        assert result.success is False
        assert "API connection failed" in result.error
        assert result.latency_ms > 0

    @pytest.mark.asyncio
    async def test_execute_email_count_none(self, hunter_stage):
        """Test handling when email count returns None."""
        hunter_stage._hunter.get_email_count = AsyncMock(return_value=None)
        hunter_stage._hunter.domain_search = AsyncMock()

        result = await hunter_stage.execute({"domain": "badapi.com"})

        assert result.success is True
        assert result.data["contact_count"] == 0
        assert result.cost_usd == 0.0  # No paid call made
        hunter_stage._hunter.domain_search.assert_not_called()


class TestHunterStageProperties:
    """Test HunterStage class properties."""

    def test_stage_name(self):
        """Test stage name is 'hunter'."""
        assert HunterStage.name == "hunter"

    def test_cost_per_call(self):
        """Test cost per call is $0.01."""
        assert HunterStage.cost_per_call == 0.01

    @pytest.mark.asyncio
    async def test_has_execute_method(self, hunter_stage):
        """Test stage has execute method."""
        assert hasattr(hunter_stage, "execute")
        assert callable(hunter_stage.execute)


class TestHunterStageCostOptimization:
    """Test cost optimization features."""

    @pytest.mark.asyncio
    async def test_free_endpoint_saves_money(self, hunter_stage):
        """Verify FREE email_count check prevents unnecessary paid calls."""
        # Simulate 10 companies, 7 have no Hunter.io data
        no_data_domains = [f"nodata{i}.com" for i in range(7)]
        has_data_domains = [f"hasdata{i}.com" for i in range(3)]

        total_cost = 0.0
        paid_calls = 0

        for domain in no_data_domains:
            hunter_stage._hunter.get_email_count = AsyncMock(return_value={
                "has_data": False, "total": 0
            })
            hunter_stage._hunter.domain_search = AsyncMock()

            result = await hunter_stage.execute({"domain": domain})
            total_cost += result.cost_usd

            if result.cost_usd > 0:
                paid_calls += 1

        for domain in has_data_domains:
            hunter_stage._hunter.get_email_count = AsyncMock(return_value={
                "has_data": True, "total": 10
            })
            hunter_stage._hunter.domain_search = AsyncMock(return_value=[
                {"email": f"ceo@{domain}", "is_atl": True, "position": "CEO"}
            ])

            result = await hunter_stage.execute({"domain": domain})
            total_cost += result.cost_usd

            if result.cost_usd > 0:
                paid_calls += 1

        # Should only pay for 3 calls (domains with data), not all 10
        assert paid_calls == 3
        assert total_cost == 0.03  # $0.01 * 3 = $0.03

        # Without cost optimization, would have paid $0.10 (10 calls)
        savings = 0.10 - total_cost
        assert savings == 0.07  # 70% savings!
