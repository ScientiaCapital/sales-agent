"""Tests for AICostTracking model."""
import pytest
from datetime import datetime, UTC
from app.models.ai_cost_tracking import AICostTracking
from app.models.lead import Lead


def test_create_cost_tracking_record(db_session):
    """Test creating a cost tracking record."""
    # Create a lead first for foreign key relationship
    lead = Lead(
        company_name="Test Company",
        qualification_score=85.0
    )
    db_session.add(lead)
    db_session.commit()
    db_session.refresh(lead)

    tracking = AICostTracking(
        agent_type="qualification",
        agent_mode="passthrough",
        lead_id=lead.id,
        prompt_text="Test prompt",
        prompt_tokens=50,
        prompt_complexity="simple",
        completion_text="Test response",
        completion_tokens=100,
        provider="cerebras",
        model="llama3.1-8b",
        cost_usd=0.000006,
        latency_ms=633,
        cache_hit=False
    )

    db_session.add(tracking)
    db_session.commit()
    db_session.refresh(tracking)

    assert tracking.id is not None
    assert tracking.agent_type == "qualification"
    assert float(tracking.cost_usd) == 0.000006
    assert tracking.timestamp is not None


def test_nullable_fields(db_session):
    """Test that optional fields can be null."""
    tracking = AICostTracking(
        agent_type="test",
        prompt_tokens=10,
        completion_tokens=20,
        provider="test",
        model="test",
        cost_usd=0.001
    )

    db_session.add(tracking)
    db_session.commit()

    assert tracking.lead_id is None
    assert tracking.session_id is None
    assert tracking.quality_score is None
