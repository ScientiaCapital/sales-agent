"""
Unit tests for batch processing API endpoints.

Tests:
- POST /batch/start - Start new batch
- GET /batch/{id} - Get batch status
- POST /batch/{id}/pause - Pause batch
- POST /batch/{id}/resume - Resume batch
- POST /batch/{id}/cancel - Cancel batch
- GET /batch/{id}/leads - Get batch leads
- GET /batch/rate-limits/status - Rate limit status
"""
import pytest
import uuid
from unittest.mock import Mock, AsyncMock, MagicMock, patch
from datetime import datetime

from fastapi.testclient import TestClient
from fastapi import FastAPI

# Import the router
from app.api.batch import router, BatchStartRequest


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def app():
    """Create test FastAPI app with batch router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_db_session():
    """Create mocked database session."""
    mock = MagicMock()
    return mock


@pytest.fixture
def mock_batch_job():
    """Create mock batch job."""
    job = Mock()
    job.id = uuid.uuid4()
    job.name = "Test Batch"
    job.status = "running"
    job.priority = "medium"
    job.total_leads = 10
    job.processed_leads = 5
    job.successful_leads = 4
    job.failed_leads = 1
    job.skipped_leads = 0
    job.percent_complete = 50.0
    job.created_at = datetime.utcnow()
    job.started_at = datetime.utcnow()
    job.completed_at = None
    job.error_message = None
    job.options_json = {}
    return job


@pytest.fixture
def mock_rate_limiter():
    """Create mocked rate limiter."""
    mock = AsyncMock()
    mock.get_apollo_remaining = AsyncMock(return_value={
        "minute": 10,
        "hour": 100,
        "day": 500,
        "credits": 200,
    })
    mock.get_status = AsyncMock(return_value={
        "apollo": {
            "requests_this_minute": 0,
            "requests_this_hour": 0,
            "requests_this_day": 0,
            "credits_used_today": 0,
        },
        "hunter": {
            "remaining_monthly": 50,
            "limit_monthly": 50,
        },
        "browserbase": {
            "active_sessions": 0,
            "max_sessions": 5,
        },
        "redis_connected": True,
    })
    return mock


# ============================================================================
# POST /batch/start Tests
# ============================================================================

class TestBatchStart:
    """Test batch start endpoint."""

    def test_start_batch_success(self, client, mock_db_session, mock_batch_job, mock_rate_limiter):
        """Test successful batch start."""
        with patch('app.api.batch.get_db', return_value=mock_db_session):
            with patch('app.api.batch.create_rate_limiter', return_value=mock_rate_limiter):
                with patch('app.api.batch.BatchJob', return_value=mock_batch_job):
                    with patch('app.tasks.batch_tasks.start_batch_task') as mock_task:
                        mock_task.delay = Mock()

                        mock_db_session.add = Mock()
                        mock_db_session.commit = Mock()
                        mock_db_session.refresh = Mock(side_effect=lambda x: setattr(x, 'id', uuid.uuid4()))

                        response = client.post("/batch/start", json={
                            "name": "Test Batch",
                            "company_ids": ["id1", "id2", "id3"],
                            "priority": "high",
                        })

                        # Should return 200 with batch_id
                        assert response.status_code == 200
                        data = response.json()
                        assert "batch_id" in data
                        assert data["status"] == "pending"
                        assert data["total_leads"] == 3

    def test_start_batch_invalid_priority(self, client, mock_db_session, mock_rate_limiter):
        """Test batch start with invalid priority."""
        with patch('app.api.batch.get_db', return_value=mock_db_session):
            with patch('app.api.batch.create_rate_limiter', return_value=mock_rate_limiter):
                response = client.post("/batch/start", json={
                    "name": "Test Batch",
                    "company_ids": ["id1"],
                    "priority": "invalid",
                })

                assert response.status_code == 400
                assert "Priority" in response.json()["detail"]

    def test_start_batch_insufficient_quota(self, client, mock_db_session, mock_rate_limiter):
        """Test batch start fails when Apollo quota insufficient."""
        # Low quota
        mock_rate_limiter.get_apollo_remaining = AsyncMock(return_value={
            "minute": 10,
            "hour": 100,
            "day": 2,  # Only 2 remaining
            "credits": 200,
        })

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            with patch('app.api.batch.create_rate_limiter', return_value=mock_rate_limiter):
                response = client.post("/batch/start", json={
                    "name": "Test Batch",
                    "company_ids": ["id1", "id2", "id3", "id4", "id5"],  # Need 5
                    "priority": "medium",
                })

                assert response.status_code == 429
                assert "quota" in response.json()["detail"].lower()

    def test_start_batch_empty_company_ids(self, client):
        """Test batch start with empty company IDs."""
        response = client.post("/batch/start", json={
            "name": "Test Batch",
            "company_ids": [],
            "priority": "medium",
        })

        # Pydantic validation should require at least one
        assert response.status_code == 422


# ============================================================================
# GET /batch/{id} Tests
# ============================================================================

class TestBatchStatus:
    """Test batch status endpoint."""

    def test_get_batch_status_success(self, client, mock_db_session, mock_batch_job):
        """Test successful batch status retrieval."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_batch_job

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            response = client.get(f"/batch/{mock_batch_job.id}")

            assert response.status_code == 200
            data = response.json()
            assert data["name"] == "Test Batch"
            assert data["status"] == "running"
            assert data["total_leads"] == 10
            assert data["processed_leads"] == 5

    def test_get_batch_status_not_found(self, client, mock_db_session):
        """Test batch status for non-existent batch."""
        mock_db_session.query.return_value.filter.return_value.first.return_value = None

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            response = client.get(f"/batch/{uuid.uuid4()}")

            assert response.status_code == 404


# ============================================================================
# POST /batch/{id}/pause Tests
# ============================================================================

class TestBatchPause:
    """Test batch pause endpoint."""

    def test_pause_running_batch(self, client, mock_db_session, mock_batch_job):
        """Test pausing a running batch."""
        mock_batch_job.status = "running"
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_batch_job

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            with patch('app.tasks.batch_tasks.pause_batch_task') as mock_task:
                mock_result = Mock()
                mock_result.id = "task-123"
                mock_task.delay.return_value = mock_result

                response = client.post(f"/batch/{mock_batch_job.id}/pause")

                assert response.status_code == 200
                assert response.json()["status"] == "pausing"

    def test_pause_non_running_batch(self, client, mock_db_session, mock_batch_job):
        """Test pausing a non-running batch fails."""
        mock_batch_job.status = "completed"
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_batch_job

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            response = client.post(f"/batch/{mock_batch_job.id}/pause")

            assert response.status_code == 400
            assert "Cannot pause" in response.json()["detail"]


# ============================================================================
# POST /batch/{id}/resume Tests
# ============================================================================

class TestBatchResume:
    """Test batch resume endpoint."""

    def test_resume_paused_batch(self, client, mock_db_session, mock_batch_job):
        """Test resuming a paused batch."""
        mock_batch_job.status = "paused"
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_batch_job

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            with patch('app.tasks.batch_tasks.resume_batch_task') as mock_task:
                mock_result = Mock()
                mock_result.id = "task-123"
                mock_task.delay.return_value = mock_result

                response = client.post(f"/batch/{mock_batch_job.id}/resume")

                assert response.status_code == 200
                assert response.json()["status"] == "resuming"

    def test_resume_non_paused_batch(self, client, mock_db_session, mock_batch_job):
        """Test resuming a non-paused batch fails."""
        mock_batch_job.status = "running"
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_batch_job

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            response = client.post(f"/batch/{mock_batch_job.id}/resume")

            assert response.status_code == 400
            assert "Cannot resume" in response.json()["detail"]


# ============================================================================
# POST /batch/{id}/cancel Tests
# ============================================================================

class TestBatchCancel:
    """Test batch cancel endpoint."""

    def test_cancel_running_batch(self, client, mock_db_session, mock_batch_job):
        """Test cancelling a running batch."""
        mock_batch_job.status = "running"
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_batch_job

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            with patch('app.tasks.batch_tasks.cancel_batch_task') as mock_task:
                mock_result = Mock()
                mock_result.id = "task-123"
                mock_task.delay.return_value = mock_result

                response = client.post(f"/batch/{mock_batch_job.id}/cancel")

                assert response.status_code == 200
                assert response.json()["status"] == "cancelling"

    def test_cancel_completed_batch(self, client, mock_db_session, mock_batch_job):
        """Test cancelling a completed batch fails."""
        mock_batch_job.status = "completed"
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_batch_job

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            response = client.post(f"/batch/{mock_batch_job.id}/cancel")

            assert response.status_code == 400
            assert "terminal state" in response.json()["detail"]


# ============================================================================
# GET /batch/{id}/leads Tests
# ============================================================================

class TestBatchLeads:
    """Test batch leads endpoint."""

    def test_get_batch_leads(self, client, mock_db_session, mock_batch_job):
        """Test getting leads for a batch."""
        mock_lead = Mock()
        mock_lead.id = uuid.uuid4()
        mock_lead.company_id = uuid.uuid4()
        mock_lead.status = "completed"
        mock_lead.started_at = datetime.utcnow()
        mock_lead.completed_at = datetime.utcnow()
        mock_lead.error_message = None
        mock_lead.retry_count = 0
        mock_lead.latency_ms = 500
        mock_lead.cost_usd = 0.01

        mock_db_session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_lead]

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            response = client.get(f"/batch/{mock_batch_job.id}/leads")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["status"] == "completed"

    def test_get_batch_leads_with_status_filter(self, client, mock_db_session, mock_batch_job):
        """Test getting leads with status filter."""
        mock_db_session.query.return_value.filter.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = []

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            response = client.get(f"/batch/{mock_batch_job.id}/leads?status=failed")

            assert response.status_code == 200


# ============================================================================
# GET /batch/rate-limits/status Tests
# ============================================================================

class TestRateLimitStatus:
    """Test rate limit status endpoint."""

    def test_get_rate_limit_status(self, client, mock_rate_limiter):
        """Test getting rate limit status."""
        with patch('app.api.batch.create_rate_limiter', return_value=mock_rate_limiter):
            response = client.get("/batch/rate-limits/status")

            assert response.status_code == 200
            data = response.json()
            assert "apollo" in data
            assert "hunter" in data
            assert "browserbase" in data
            assert data["redis_connected"] is True


# ============================================================================
# GET /batch/ (List) Tests
# ============================================================================

class TestBatchList:
    """Test batch list endpoint."""

    def test_list_batches(self, client, mock_db_session, mock_batch_job):
        """Test listing batches."""
        mock_db_session.query.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_batch_job]

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            response = client.get("/batch/")

            assert response.status_code == 200
            data = response.json()
            assert len(data) == 1
            assert data[0]["name"] == "Test Batch"

    def test_list_batches_with_status_filter(self, client, mock_db_session, mock_batch_job):
        """Test listing batches with status filter."""
        mock_db_session.query.return_value.filter.return_value.order_by.return_value.offset.return_value.limit.return_value.all.return_value = [mock_batch_job]

        with patch('app.api.batch.get_db', return_value=mock_db_session):
            response = client.get("/batch/?status=running")

            assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
