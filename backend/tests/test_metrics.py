"""
Tests for metrics tracking and analytics.

Tests cover:
- MetricsService business logic
- API endpoints
- Error handling
- Data validation
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.services.metrics_service import MetricsService
from app.models.agent_models import AgentExecution
from app.models.api_call import CerebrasAPICall
from app.models.analytics_models import AnalyticsSystemMetrics, AnalyticsLeadMetrics
from app.schemas.metrics import (
    MetricsSummaryResponse,
    AgentMetricResponse,
    ProviderCostMetrics
)


@pytest.mark.unit
@pytest.mark.database
class TestMetricsService:
    """Test MetricsService business logic."""

    def test_init(self, db_session):
        """Test service initialization."""
        service = MetricsService(db_session)
        assert service.db == db_session
        assert service.cache is not None

    def test_get_agent_metrics_empty(self, db_session):
        """Test getting agent metrics with no data."""
        service = MetricsService(db_session)
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        metrics = service.get_agent_metrics(start_date, end_date)
        assert isinstance(metrics, list)
        assert len(metrics) == 0

    def test_get_agent_metrics_with_data(self, db_session):
        """Test getting agent metrics with sample data."""
        # Create test agent executions
        execution1 = AgentExecution(
            agent_type="qualification",
            status="success",
            latency_ms=950,
            cost_usd=0.0001,
            model_used="llama3.1-8b",
            prompt_tokens=100,
            completion_tokens=50,
            created_at=datetime.utcnow()
        )
        execution2 = AgentExecution(
            agent_type="qualification",
            status="success",
            latency_ms=1050,
            cost_usd=0.00012,
            model_used="llama3.1-8b",
            prompt_tokens=120,
            completion_tokens=60,
            created_at=datetime.utcnow()
        )
        execution3 = AgentExecution(
            agent_type="qualification",
            status="failed",
            latency_ms=500,
            cost_usd=0.0,
            error_message="Test error",
            created_at=datetime.utcnow()
        )

        db_session.add_all([execution1, execution2, execution3])
        db_session.commit()

        service = MetricsService(db_session)
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(days=1)

        metrics = service.get_agent_metrics(start_date, end_date)

        assert len(metrics) == 1  # Grouped by agent_type and date
        metric = metrics[0]
        assert metric["agent_type"] == "qualification"
        assert metric["total_executions"] == 3
        assert metric["successful_executions"] == 2
        assert metric["failed_executions"] == 1
        assert metric["success_rate"] == pytest.approx(2/3, rel=0.01)
        assert metric["avg_latency_ms"] > 0
        assert metric["total_cost_usd"] > 0

    def test_get_agent_metrics_filter_by_type(self, db_session):
        """Test filtering agent metrics by agent type."""
        # Create multiple agent types
        execution1 = AgentExecution(
            agent_type="qualification",
            status="success",
            latency_ms=950,
            cost_usd=0.0001,
            created_at=datetime.utcnow()
        )
        execution2 = AgentExecution(
            agent_type="enrichment",
            status="success",
            latency_ms=2500,
            cost_usd=0.0002,
            created_at=datetime.utcnow()
        )

        db_session.add_all([execution1, execution2])
        db_session.commit()

        service = MetricsService(db_session)
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(days=1)

        # Filter by qualification
        metrics = service.get_agent_metrics(start_date, end_date, agent_type="qualification")
        assert len(metrics) == 1
        assert metrics[0]["agent_type"] == "qualification"

        # Filter by enrichment
        metrics = service.get_agent_metrics(start_date, end_date, agent_type="enrichment")
        assert len(metrics) == 1
        assert metrics[0]["agent_type"] == "enrichment"

    def test_get_cost_by_provider_cerebras(self, db_session):
        """Test getting cost metrics for Cerebras."""
        # Create Cerebras API calls
        call1 = CerebrasAPICall(
            endpoint="/chat/completions",
            model="llama3.1-8b",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=945,
            cost_usd=0.0001,
            operation_type="lead_qualification",
            success=True,
            created_at=datetime.utcnow()
        )
        call2 = CerebrasAPICall(
            endpoint="/chat/completions",
            model="llama3.1-8b",
            prompt_tokens=200,
            completion_tokens=100,
            total_tokens=300,
            latency_ms=1050,
            cost_usd=0.0002,
            operation_type="lead_qualification",
            success=True,
            created_at=datetime.utcnow()
        )

        db_session.add_all([call1, call2])
        db_session.commit()

        service = MetricsService(db_session)
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(days=1)

        metrics = service.get_cost_by_provider(start_date, end_date)

        # Should have Cerebras metrics
        cerebras_metrics = [m for m in metrics if m["provider"] == "cerebras"]
        assert len(cerebras_metrics) > 0

        metric = cerebras_metrics[0]
        assert metric["total_calls"] == 2
        assert metric["total_tokens"] == 450
        assert metric["total_cost_usd"] == pytest.approx(0.0003, rel=0.01)
        assert metric["avg_latency_ms"] > 0

    def test_get_metrics_summary(self, db_session):
        """Test getting comprehensive metrics summary."""
        # Create test data
        execution = AgentExecution(
            agent_type="qualification",
            status="success",
            latency_ms=950,
            cost_usd=0.0001,
            created_at=datetime.utcnow()
        )
        lead_metric = AnalyticsLeadMetrics(
            qualification_tier="A",
            created_at=datetime.utcnow()
        )

        db_session.add_all([execution, lead_metric])
        db_session.commit()

        service = MetricsService(db_session)
        start_date = datetime.utcnow() - timedelta(days=1)
        end_date = datetime.utcnow() + timedelta(days=1)

        summary = service.get_metrics_summary(start_date, end_date)

        # Validate structure
        assert "period_start" in summary
        assert "period_end" in summary
        assert "total_agent_executions" in summary
        assert "agent_success_rate" in summary
        assert "avg_agent_latency_ms" in summary
        assert "total_cost_usd" in summary
        assert "cost_by_provider" in summary
        assert "leads_processed" in summary
        assert "leads_qualified" in summary
        assert "qualification_rate" in summary

        # Validate values
        assert summary["total_agent_executions"] == 1
        assert summary["agent_success_rate"] == 1.0
        assert summary["leads_processed"] == 1
        assert summary["leads_qualified"] == 1

    def test_track_system_metric(self, db_session):
        """Test tracking a custom system metric."""
        service = MetricsService(db_session)

        metric = service.track_system_metric(
            metric_name="csv_import_throughput",
            metric_value=75.5,
            metric_unit="leads_per_second",
            category="business",
            subcategory="import",
            tags={"import_type": "csv", "file_size": "1000"}
        )

        assert metric.id is not None
        assert metric.metric_name == "csv_import_throughput"
        assert metric.metric_value == 75.5
        assert metric.metric_unit == "leads_per_second"
        assert metric.category == "business"
        assert metric.subcategory == "import"
        assert metric.tags["import_type"] == "csv"


@pytest.mark.integration
@pytest.mark.database
class TestMetricsAPI:
    """Test metrics API endpoints."""

    def test_get_metrics_summary_success(self, client: TestClient, db_session):
        """Test successful metrics summary retrieval."""
        # Create test data
        execution = AgentExecution(
            agent_type="qualification",
            status="success",
            latency_ms=950,
            cost_usd=0.0001,
            created_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()

        response = client.get("/api/v1/metrics/summary")

        assert response.status_code == 200
        data = response.json()

        # Validate response structure
        assert "period_start" in data
        assert "period_end" in data
        assert "total_agent_executions" in data
        assert "agent_success_rate" in data
        assert "total_cost_usd" in data

    def test_get_metrics_summary_with_date_range(self, client: TestClient):
        """Test metrics summary with custom date range."""
        start_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
        end_date = datetime.utcnow().isoformat()

        response = client.get(
            f"/api/v1/metrics/summary?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 200
        data = response.json()
        assert "period_start" in data
        assert "period_end" in data

    def test_get_metrics_summary_invalid_date_range(self, client: TestClient):
        """Test metrics summary with invalid date range."""
        start_date = datetime.utcnow().isoformat()
        end_date = (datetime.utcnow() - timedelta(days=7)).isoformat()

        response = client.get(
            f"/api/v1/metrics/summary?start_date={start_date}&end_date={end_date}"
        )

        assert response.status_code == 400
        assert "start_date must be before end_date" in response.json()["detail"]

    def test_get_agent_metrics_success(self, client: TestClient, db_session):
        """Test successful agent metrics retrieval."""
        # Create test data
        execution = AgentExecution(
            agent_type="qualification",
            status="success",
            latency_ms=950,
            cost_usd=0.0001,
            created_at=datetime.utcnow()
        )
        db_session.add(execution)
        db_session.commit()

        response = client.get("/api/v1/metrics/agents")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_agent_metrics_with_filter(self, client: TestClient, db_session):
        """Test agent metrics with agent_type filter."""
        # Create multiple agent types
        execution1 = AgentExecution(
            agent_type="qualification",
            status="success",
            latency_ms=950,
            cost_usd=0.0001,
            created_at=datetime.utcnow()
        )
        execution2 = AgentExecution(
            agent_type="enrichment",
            status="success",
            latency_ms=2500,
            cost_usd=0.0002,
            created_at=datetime.utcnow()
        )
        db_session.add_all([execution1, execution2])
        db_session.commit()

        response = client.get("/api/v1/metrics/agents?agent_type=qualification")

        assert response.status_code == 200
        data = response.json()
        assert all(m["agent_type"] == "qualification" for m in data)

    def test_get_cost_metrics_success(self, client: TestClient, db_session):
        """Test successful cost metrics retrieval."""
        # Create test data
        call = CerebrasAPICall(
            endpoint="/chat/completions",
            model="llama3.1-8b",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=945,
            cost_usd=0.0001,
            success=True,
            created_at=datetime.utcnow()
        )
        db_session.add(call)
        db_session.commit()

        response = client.get("/api/v1/metrics/costs")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_cost_metrics_with_provider_filter(self, client: TestClient, db_session):
        """Test cost metrics with provider filter."""
        call = CerebrasAPICall(
            endpoint="/chat/completions",
            model="llama3.1-8b",
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            latency_ms=945,
            cost_usd=0.0001,
            success=True,
            created_at=datetime.utcnow()
        )
        db_session.add(call)
        db_session.commit()

        response = client.get("/api/v1/metrics/costs?provider=cerebras")

        assert response.status_code == 200
        data = response.json()
        assert all(m["provider"] == "cerebras" for m in data)

    def test_track_metric_success(self, client: TestClient):
        """Test tracking a custom metric."""
        response = client.post(
            "/api/v1/metrics/track",
            params={
                "metric_name": "test_metric",
                "metric_value": 123.45,
                "metric_unit": "ms",
                "category": "performance"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert "message" in data
        assert "metric_id" in data
        assert "recorded_at" in data

    def test_api_endpoints_require_valid_dates(self, client: TestClient):
        """Test that API endpoints validate date formats."""
        response = client.get("/api/v1/metrics/summary?start_date=invalid-date")

        # Should return 422 for validation error
        assert response.status_code == 422


@pytest.mark.unit
class TestMetricsSchemas:
    """Test Pydantic schemas for metrics."""

    def test_metrics_summary_response_validation(self):
        """Test MetricsSummaryResponse validation."""
        data = {
            "period_start": datetime.utcnow(),
            "period_end": datetime.utcnow(),
            "total_api_requests": 100,
            "avg_response_time_ms": 250.5,
            "error_rate": 0.02,
            "total_agent_executions": 50,
            "agent_success_rate": 0.95,
            "avg_agent_latency_ms": 945.0,
            "total_cost_usd": 5.75,
            "cost_by_provider": {"cerebras": 4.50, "claude": 1.25},
            "leads_processed": 30,
            "leads_qualified": 20,
            "qualification_rate": 0.67
        }

        response = MetricsSummaryResponse(**data)
        assert response.total_api_requests == 100
        assert response.avg_response_time_ms == 250.5
        assert response.error_rate == 0.02
        assert response.cost_by_provider["cerebras"] == 4.50

    def test_agent_metric_response_validation(self):
        """Test AgentMetricResponse validation."""
        data = {
            "agent_type": "qualification",
            "date": datetime.utcnow(),
            "total_executions": 100,
            "successful_executions": 95,
            "failed_executions": 5,
            "avg_latency_ms": 945.0,
            "min_latency_ms": 700.0,
            "max_latency_ms": 1200.0,
            "total_cost_usd": 0.01,
            "avg_cost_usd": 0.0001,
            "success_rate": 0.95
        }

        response = AgentMetricResponse(**data)
        assert response.agent_type == "qualification"
        assert response.total_executions == 100
        assert response.success_rate == 0.95

    def test_provider_cost_metrics_validation(self):
        """Test ProviderCostMetrics validation."""
        data = {
            "provider": "cerebras",
            "date": datetime.utcnow(),
            "total_calls": 500,
            "total_tokens": 75000,
            "total_cost_usd": 4.50,
            "avg_latency_ms": 945.0
        }

        response = ProviderCostMetrics(**data)
        assert response.provider == "cerebras"
        assert response.total_calls == 500
        assert response.total_cost_usd == 4.50
