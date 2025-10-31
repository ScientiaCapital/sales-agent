"""
Tests for Pipeline Testing API Endpoints
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, AsyncMock, patch

from app.main import app
from app.schemas.pipeline import PipelineTestResponse, PipelineStageResult


@pytest.fixture
def client():
    """Create FastAPI test client"""
    return TestClient(app)


@pytest.fixture
def mock_orchestrator():
    """Mock PipelineOrchestrator for testing"""
    with patch('app.api.pipeline.PipelineOrchestrator') as mock:
        orchestrator_instance = Mock()
        mock.return_value = orchestrator_instance

        # Mock successful pipeline execution
        orchestrator_instance.execute = AsyncMock(return_value=PipelineTestResponse(
            success=True,
            total_latency_ms=4250,
            total_cost_usd=0.002014,
            lead_name="Test Company",
            stages={
                "qualification": PipelineStageResult(
                    status="success",
                    latency_ms=633,
                    cost_usd=0.000006,
                    output={"score": 72, "tier": "high_value"}
                ),
                "enrichment": PipelineStageResult(
                    status="success",
                    latency_ms=2450,
                    cost_usd=0.0001,
                    output={"company_info": {}}
                ),
                "deduplication": PipelineStageResult(
                    status="no_duplicate",
                    latency_ms=45,
                    cost_usd=0.0,
                    confidence=0.0,
                    output={"is_duplicate": False}
                ),
                "close_crm": PipelineStageResult(
                    status="created",
                    latency_ms=1122,
                    cost_usd=0.0,
                    output={"id": "lead_123"}
                )
            }
        ))

        yield orchestrator_instance


def test_pipeline_endpoint_exists(client):
    """Test that pipeline endpoint is registered"""
    response = client.post(
        "/api/leads/test-pipeline",
        json={
            "lead": {"name": "Test Company"},
            "options": {}
        }
    )
    # Should not return 404
    assert response.status_code != 404


def test_test_pipeline_with_lead_data(client, mock_orchestrator):
    """Test pipeline execution with direct lead data"""
    response = client.post(
        "/api/leads/test-pipeline",
        json={
            "lead": {
                "name": "A & A GENPRO INC.",
                "email": "contact@aagenpro.com",
                "phone": "(713) 830-3280",
                "website": "https://www.aagenpro.com/",
                "icp_score": 72.8
            },
            "options": {
                "stop_on_duplicate": True,
                "skip_enrichment": False,
                "create_in_crm": False,
                "dry_run": True
            }
        }
    )

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert data["success"] is True
    assert data["lead_name"] == "Test Company"
    assert data["total_latency_ms"] == 4250
    assert data["total_cost_usd"] == 0.002014
    assert "stages" in data
    assert "qualification" in data["stages"]
    assert "enrichment" in data["stages"]

    # Verify orchestrator was called
    mock_orchestrator.execute.assert_called_once()


def test_test_pipeline_with_csv_import(client, mock_orchestrator):
    """Test pipeline execution with CSV lead import"""
    with patch('app.api.pipeline.LeadCSVImporter') as mock_importer:
        # Mock CSV importer
        importer_instance = Mock()
        mock_importer.return_value = importer_instance
        importer_instance.get_lead.return_value = {
            "name": "CSV Company",
            "email": "csv@example.com",
            "icp_score": 75.0
        }

        response = client.post(
            "/api/leads/test-pipeline/csv",
            json={
                "csv_path": "/tmp/test.csv",
                "lead_index": 0,
                "options": {
                    "dry_run": True
                }
            }
        )

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "stages" in data

        # Verify CSV importer was used
        mock_importer.assert_called_once_with(csv_path="/tmp/test.csv")
        importer_instance.get_lead.assert_called_once_with(0)


def test_quick_pipeline_test(client, mock_orchestrator):
    """Test quick pipeline test with hardcoded lead"""
    response = client.get("/api/leads/test-pipeline/quick")

    assert response.status_code == 200
    data = response.json()

    assert data["success"] is True
    assert "stages" in data
    assert data["total_latency_ms"] > 0

    # Verify orchestrator was called with quick test lead
    mock_orchestrator.execute.assert_called_once()


def test_pipeline_validation_error(client):
    """Test pipeline endpoint with invalid data"""
    response = client.post(
        "/api/leads/test-pipeline",
        json={
            "lead": {},  # Missing required name field
            "options": {}
        }
    )

    assert response.status_code == 422  # Validation error


def test_csv_import_validation_error(client):
    """Test CSV import with invalid lead index"""
    response = client.post(
        "/api/leads/test-pipeline/csv",
        json={
            "csv_path": "/tmp/test.csv",
            "lead_index": 300,  # Out of range (max 199)
            "options": {}
        }
    )

    assert response.status_code == 422  # Validation error


def test_pipeline_handles_orchestrator_failure(client):
    """Test API handles orchestrator failures gracefully"""
    with patch('app.api.pipeline.PipelineOrchestrator') as mock:
        orchestrator_instance = Mock()
        mock.return_value = orchestrator_instance
        orchestrator_instance.execute = AsyncMock(
            side_effect=Exception("Database connection failed")
        )

        response = client.post(
            "/api/leads/test-pipeline",
            json={
                "lead": {"name": "Test Company"},
                "options": {}
            }
        )

        assert response.status_code == 500
        assert "error" in response.json() or "detail" in response.json()


def test_pipeline_saves_execution_to_database(client, mock_orchestrator):
    """Test that pipeline execution is saved to database"""
    with patch('app.api.pipeline.save_pipeline_execution') as mock_save:
        response = client.post(
            "/api/leads/test-pipeline",
            json={
                "lead": {"name": "Test Company"},
                "options": {"dry_run": True}
            }
        )

        assert response.status_code == 200

        # Verify execution was saved to database
        mock_save.assert_called_once()
        call_args = mock_save.call_args[0]
        assert call_args[0].success is True  # PipelineTestResponse
