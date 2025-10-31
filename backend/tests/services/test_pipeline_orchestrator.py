"""
Tests for Pipeline Orchestrator
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

# Mock the agent classes at module level before importing PipelineOrchestrator
import sys
import app.services.pipeline_orchestrator as orch_module

# Prevent lazy import by setting mocks directly
orch_module.QualificationAgent = Mock
orch_module.EnrichmentAgent = Mock
orch_module.DeduplicationService = Mock
orch_module.CloseService = Mock

from app.services.pipeline_orchestrator import PipelineOrchestrator
from app.schemas.pipeline import (
    PipelineTestRequest,
    PipelineTestOptions,
    PipelineTestResponse
)


@pytest.fixture
def sample_lead():
    """Sample lead data for testing"""
    return {
        "name": "A & A GENPRO INC.",
        "email": "contact@aagenpro.com",
        "phone": "(713) 830-3280",
        "website": "https://www.aagenpro.com/",
        "icp_score": 72.8,
        "oem_certifications": ["Generac", "Cummins"],
        "city": "Houston",
        "state": "TX"
    }


@pytest.fixture
def pipeline_orchestrator():
    """Create orchestrator instance (agents already mocked at module level)"""
    return PipelineOrchestrator()


@pytest.mark.asyncio
async def test_orchestrator_initialization(pipeline_orchestrator):
    """Test orchestrator initializes with all required agents"""
    assert pipeline_orchestrator is not None
    assert hasattr(pipeline_orchestrator, 'qualification_agent')
    assert hasattr(pipeline_orchestrator, 'enrichment_agent')
    assert hasattr(pipeline_orchestrator, 'deduplication_service')
    assert hasattr(pipeline_orchestrator, 'close_service')


@pytest.mark.asyncio
async def test_full_pipeline_success(pipeline_orchestrator, sample_lead):
    """Test successful execution through all 4 stages"""
    request = PipelineTestRequest(
        lead=sample_lead,
        options=PipelineTestOptions(
            stop_on_duplicate=False,
            skip_enrichment=False,
            create_in_crm=False,  # Don't actually create in CRM during tests
            dry_run=True
        )
    )

    # Mock all agent responses
    with patch.object(pipeline_orchestrator, 'qualification_agent') as mock_qual, \
         patch.object(pipeline_orchestrator, 'enrichment_agent') as mock_enrich, \
         patch.object(pipeline_orchestrator, 'deduplication_service') as mock_dedup, \
         patch.object(pipeline_orchestrator, 'close_service') as mock_close:

        # Setup mocks
        mock_qual.qualify = AsyncMock(return_value={
            "score": 72, "tier": "high_value", "reasoning": "Good fit"
        })
        mock_enrich.enrich = AsyncMock(return_value={
            "company_info": {"employees": 50}, "contacts": []
        })
        mock_dedup.check_duplicate = AsyncMock(return_value={
            "is_duplicate": False, "confidence": 0.0
        })
        mock_close.create_lead = AsyncMock(return_value={
            "id": "lead_123", "status": "created"
        })

        # Execute pipeline
        result = await pipeline_orchestrator.execute(request)

        # Verify response structure
        assert isinstance(result, PipelineTestResponse)
        assert result.success is True
        assert result.lead_name == "A & A GENPRO INC."
        assert result.total_latency_ms >= 0  # Mocked async calls may complete instantly
        assert result.total_cost_usd >= 0

        # Verify all stages executed
        assert "qualification" in result.stages
        assert "enrichment" in result.stages
        assert "deduplication" in result.stages
        assert "close_crm" in result.stages

        # Verify stage results
        assert result.stages["qualification"].status == "success"
        assert result.stages["enrichment"].status == "success"
        assert result.stages["deduplication"].status == "no_duplicate"
        # Close CRM is skipped because dry_run=True in test options
        assert result.stages["close_crm"].status == "skipped"


@pytest.mark.asyncio
async def test_pipeline_stops_on_duplicate(pipeline_orchestrator, sample_lead):
    """Test pipeline stops when duplicate detected and stop_on_duplicate=True"""
    request = PipelineTestRequest(
        lead=sample_lead,
        options=PipelineTestOptions(
            stop_on_duplicate=True,
            create_in_crm=False,
            dry_run=True
        )
    )

    with patch.object(pipeline_orchestrator, 'qualification_agent') as mock_qual, \
         patch.object(pipeline_orchestrator, 'enrichment_agent') as mock_enrich, \
         patch.object(pipeline_orchestrator, 'deduplication_service') as mock_dedup, \
         patch.object(pipeline_orchestrator, 'close_service') as mock_close:

        mock_qual.qualify = AsyncMock(return_value={"score": 72, "tier": "high_value"})
        mock_enrich.enrich = AsyncMock(return_value={"company_info": {}})
        mock_dedup.check_duplicate = AsyncMock(return_value={
            "is_duplicate": True, "confidence": 0.95, "matched_lead_id": "existing_123"
        })

        result = await pipeline_orchestrator.execute(request)

        # Pipeline should stop after deduplication
        assert result.success is False
        assert result.error_stage == "deduplication"
        assert "duplicate" in result.error_message.lower()

        # Close CRM should not be called
        mock_close.create_lead.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_skips_enrichment(pipeline_orchestrator, sample_lead):
    """Test pipeline skips enrichment when skip_enrichment=True"""
    request = PipelineTestRequest(
        lead=sample_lead,
        options=PipelineTestOptions(
            skip_enrichment=True,
            create_in_crm=False,
            dry_run=True
        )
    )

    with patch.object(pipeline_orchestrator, 'qualification_agent') as mock_qual, \
         patch.object(pipeline_orchestrator, 'enrichment_agent') as mock_enrich, \
         patch.object(pipeline_orchestrator, 'deduplication_service') as mock_dedup, \
         patch.object(pipeline_orchestrator, 'close_service') as mock_close:

        mock_qual.qualify = AsyncMock(return_value={"score": 72, "tier": "high_value"})
        mock_dedup.check_duplicate = AsyncMock(return_value={"is_duplicate": False})
        mock_close.create_lead = AsyncMock(return_value={"id": "lead_123"})

        result = await pipeline_orchestrator.execute(request)

        assert result.success is True
        assert result.stages["enrichment"].status == "skipped"

        # Enrichment agent should not be called
        mock_enrich.enrich.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_handles_agent_failure(pipeline_orchestrator, sample_lead):
    """Test pipeline handles agent failures gracefully"""
    request = PipelineTestRequest(
        lead=sample_lead,
        options=PipelineTestOptions(dry_run=True)
    )

    with patch.object(pipeline_orchestrator, 'qualification_agent') as mock_qual:
        # Simulate qualification failure
        mock_qual.qualify = AsyncMock(side_effect=Exception("API timeout"))

        result = await pipeline_orchestrator.execute(request)

        assert result.success is False
        assert result.error_stage == "qualification"
        assert "timeout" in result.error_message.lower()
        assert result.stages["qualification"].status == "failed"


@pytest.mark.asyncio
async def test_pipeline_tracks_per_stage_metrics(pipeline_orchestrator, sample_lead):
    """Test pipeline tracks latency and cost per stage"""
    request = PipelineTestRequest(
        lead=sample_lead,
        options=PipelineTestOptions(create_in_crm=False, dry_run=True)
    )

    with patch.object(pipeline_orchestrator, 'qualification_agent') as mock_qual, \
         patch.object(pipeline_orchestrator, 'enrichment_agent') as mock_enrich, \
         patch.object(pipeline_orchestrator, 'deduplication_service') as mock_dedup, \
         patch.object(pipeline_orchestrator, 'close_service') as mock_close:

        mock_qual.qualify = AsyncMock(return_value={"score": 72})
        mock_enrich.enrich = AsyncMock(return_value={"company_info": {}})
        mock_dedup.check_duplicate = AsyncMock(return_value={"is_duplicate": False})
        mock_close.create_lead = AsyncMock(return_value={"id": "lead_123"})

        result = await pipeline_orchestrator.execute(request)

        # All stages should have timing data
        for stage_name, stage_result in result.stages.items():
            assert stage_result.latency_ms is not None
            assert stage_result.latency_ms >= 0

            # Most stages should have cost data (deduplication might be free)
            if stage_name != "deduplication":
                assert stage_result.cost_usd is not None
                assert stage_result.cost_usd >= 0

        # Total should be sum of stages
        total_stage_latency = sum(
            s.latency_ms for s in result.stages.values() if s.latency_ms
        )
        assert result.total_latency_ms == total_stage_latency
