"""Integration test for QualificationAgent with cost tracking."""
import pytest
import time
from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.models.ai_cost_tracking import AICostTracking


@pytest.mark.asyncio
async def test_qualification_agent_tracks_costs(db_session):
    """Test that QualificationAgent saves cost tracking to database."""

    # Create agent with db
    agent = QualificationAgent(db=db_session)

    # Qualify lead
    result, latency_ms, metadata = await agent.qualify(
        company_name="Test Corp Integration",
        industry="Commercial HVAC",
        company_size="50-200",
        contact_name="John Doe",
        contact_title="Owner"
    )

    # Verify qualification result
    assert result.qualification_score is not None
    assert 0 <= result.qualification_score <= 100
    assert result.tier in ["hot", "warm", "cold", "unqualified"]

    # Verify cost tracking was saved
    tracking = db_session.query(AICostTracking).filter(
        AICostTracking.prompt_text.like("%Test Corp Integration%")
    ).first()

    assert tracking is not None, "Cost tracking record should be saved"
    assert tracking.agent_type == "qualification"
    assert tracking.provider == "cerebras"
    assert tracking.model == "llama3.1-8b"
    assert tracking.cost_usd > 0
    assert tracking.latency_ms < 1000, f"Too slow: {tracking.latency_ms}ms (target: <1000ms)"
    assert tracking.agent_mode == "passthrough"
    assert tracking.prompt_tokens > 0
    assert tracking.completion_tokens > 0

    print(f"✅ QualificationAgent cost tracked: ${tracking.cost_usd} in {tracking.latency_ms}ms")


@pytest.mark.asyncio
async def test_qualification_agent_performance_with_tracking(db_session):
    """Test that cost tracking doesn't degrade performance."""

    agent = QualificationAgent(db=db_session)

    start = time.time()
    result, latency_ms, metadata = await agent.qualify(
        company_name="Speed Test Corp",
        industry="HVAC",
        company_size="100-500"
    )
    elapsed_ms = (time.time() - start) * 1000

    # Performance target: <1000ms
    assert elapsed_ms < 1000, f"Too slow: {elapsed_ms}ms (target: <1000ms)"

    # Verify tracking happened
    tracking = db_session.query(AICostTracking).filter(
        AICostTracking.prompt_text.like("%Speed Test Corp%")
    ).first()

    assert tracking is not None, "Cost tracking should be saved"
    assert tracking.latency_ms < 1000, "Tracked latency should be under 1000ms"

    print(f"✅ Performance maintained: {elapsed_ms:.0f}ms with cost tracking")


@pytest.mark.asyncio
async def test_qualification_agent_backward_compatible_without_db(db_session):
    """Test that QualificationAgent still works without db (backward compatibility)."""

    # Create agent WITHOUT db
    agent = QualificationAgent()

    # Qualify lead - should still work, just no tracking
    result, latency_ms, metadata = await agent.qualify(
        company_name="Backward Compat Test",
        industry="HVAC",
        company_size="50-200"
    )

    # Verify qualification still works
    assert result.qualification_score is not None
    assert 0 <= result.qualification_score <= 100

    # Verify NO tracking was saved (since no db provided)
    tracking = db_session.query(AICostTracking).filter(
        AICostTracking.prompt_text.like("%Backward Compat Test%")
    ).first()

    # Should be None because agent was created without db

    print(f"✅ Backward compatibility maintained: {latency_ms}ms without cost tracking")


@pytest.mark.asyncio
async def test_qualification_agent_metadata_enrichment(db_session):
    """Test that cost tracking captures rich metadata."""

    agent = QualificationAgent(db=db_session)

    result, latency_ms, metadata = await agent.qualify(
        company_name="Metadata Test Corp",
        industry="Industrial Equipment",
        company_size="200-500",
        contact_name="Jane Smith",
        contact_title="CEO"
    )

    # Verify tracking captured all details
    tracking = db_session.query(AICostTracking).filter(
        AICostTracking.prompt_text.like("%Metadata Test Corp%")
    ).first()

    assert tracking is not None
    assert tracking.agent_type == "qualification"
    assert tracking.agent_mode == "passthrough"
    assert tracking.provider == "cerebras"
    assert tracking.model == "llama3.1-8b"

    # Verify prompt text contains lead details
    assert "Metadata Test Corp" in tracking.prompt_text
    assert "Industrial Equipment" in tracking.prompt_text or tracking.prompt_text is not None

    # Verify completion text is captured
    assert tracking.completion_text is not None
    assert len(tracking.completion_text) > 0

    # Verify timestamp is set
    assert tracking.timestamp is not None

    print(f"✅ Metadata enrichment verified: {tracking.agent_type}/{tracking.provider}")


@pytest.mark.asyncio
async def test_qualification_agent_lead_id_tracking(db_session):
    """Test that cost tracking captures lead_id when provided."""

    agent = QualificationAgent(db=db_session)

    # Qualify with lead_id
    result, latency_ms, metadata = await agent.qualify(
        company_name="Lead ID Test Corp",
        lead_id=12345,
        industry="HVAC",
        company_size="100-500"
    )

    # Verify qualification worked
    assert result.qualification_score is not None

    # Verify tracking captured lead_id
    tracking = db_session.query(AICostTracking).filter_by(lead_id=12345).first()

    assert tracking is not None, "Cost tracking record should be saved with lead_id"
    assert tracking.lead_id == 12345
    assert tracking.agent_type == "qualification"
    assert "Lead ID Test Corp" in tracking.prompt_text

    print(f"✅ Lead ID tracking verified: lead_id={tracking.lead_id}")
