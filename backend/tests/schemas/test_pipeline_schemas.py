"""
Tests for pipeline testing schemas
"""
import pytest
from pydantic import ValidationError

from app.schemas.pipeline import (
    PipelineTestRequest,
    PipelineTestOptions,
    PipelineStageResult,
    PipelineTestResponse
)


def test_pipeline_test_request_validation():
    """Test PipelineTestRequest accepts valid data"""
    request = PipelineTestRequest(
        lead={
            "name": "A & A GENPRO INC.",
            "email": "contact@aagenpro.com",
            "phone": "(713) 830-3280",
            "company": "A & A GENPRO INC.",
            "website": "https://www.aagenpro.com/",
            "icp_score": 72.8,
            "oem_certifications": ["Generac", "Cummins"]
        },
        options=PipelineTestOptions()
    )

    assert request.lead["name"] == "A & A GENPRO INC."
    assert request.options.stop_on_duplicate is True
    assert request.options.create_in_crm is True


def test_pipeline_test_request_missing_required_field():
    """Test validation fails when required lead fields missing"""
    with pytest.raises(ValidationError):
        PipelineTestRequest(
            lead={},  # Missing required "name" field
            options=PipelineTestOptions()
        )


def test_pipeline_stage_result():
    """Test PipelineStageResult schema"""
    stage = PipelineStageResult(
        status="success",
        latency_ms=633,
        cost_usd=0.000006,
        output={"score": 72, "tier": "high_value"}
    )

    assert stage.status == "success"
    assert stage.latency_ms == 633
    assert stage.output["score"] == 72


def test_pipeline_test_response():
    """Test complete PipelineTestResponse schema"""
    response = PipelineTestResponse(
        success=True,
        total_latency_ms=4250,
        total_cost_usd=0.002014,
        lead_name="Test Company",
        stages={
            "qualification": PipelineStageResult(
                status="success",
                latency_ms=633,
                cost_usd=0.000006,
                output={"score": 72}
            )
        }
    )

    assert response.success is True
    assert response.total_latency_ms == 4250
    assert "qualification" in response.stages
