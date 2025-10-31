"""
Tests for pipeline testing models
"""
import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from app.models.pipeline_models import PipelineTestExecution


def test_pipeline_test_execution_creation(db_session: Session):
    """Test creating a pipeline test execution record"""
    execution = PipelineTestExecution(
        lead_name="Test Company Inc",
        success=True,
        total_latency_ms=4250,
        total_cost_usd=0.002014,
        stages_json={
            "qualification": {"status": "success", "latency_ms": 633},
            "enrichment": {"status": "success", "latency_ms": 2450},
            "deduplication": {"status": "no_duplicate", "latency_ms": 45},
            "close_crm": {"status": "created", "latency_ms": 1122}
        }
    )

    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)

    assert execution.id is not None
    assert execution.lead_name == "Test Company Inc"
    assert execution.success is True
    assert execution.total_latency_ms == 4250
    assert execution.stages_json["qualification"]["latency_ms"] == 633


def test_pipeline_test_execution_query_by_lead_name(db_session: Session):
    """Test querying executions by lead name"""
    execution1 = PipelineTestExecution(
        lead_name="Company A",
        success=True,
        total_latency_ms=4000,
        total_cost_usd=0.002
    )
    execution2 = PipelineTestExecution(
        lead_name="Company B",
        success=False,
        total_latency_ms=1500,
        total_cost_usd=0.001
    )

    db_session.add_all([execution1, execution2])
    db_session.commit()

    results = db_session.query(PipelineTestExecution).filter_by(lead_name="Company A").all()
    assert len(results) == 1
    assert results[0].lead_name == "Company A"
