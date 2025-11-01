"""Tests for analytics API endpoint."""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.database import Base, get_db
from app.models.ai_cost_tracking import AICostTracking
from app.models.lead import Lead

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db_session():
    """Create a fresh database session for each test."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def client(db_session):
    """Create a test client with database dependency override."""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sample_leads(db_session):
    """Create sample leads for testing."""
    leads = [
        Lead(
            company_name="TechCorp Inc",
            contact_email="contact@techcorp.com",
            qualification_score=85,
            created_at=datetime.utcnow() - timedelta(days=2)
        ),
        Lead(
            company_name="DataCo",
            contact_email="info@dataco.com",
            qualification_score=72,
            created_at=datetime.utcnow() - timedelta(days=1)
        ),
    ]
    for lead in leads:
        db_session.add(lead)
    db_session.commit()

    # Refresh to get IDs
    for lead in leads:
        db_session.refresh(lead)

    return leads


@pytest.fixture
def sample_cost_data(db_session, sample_leads):
    """Create sample AI cost tracking data."""
    now = datetime.utcnow()

    cost_records = [
        # QualificationAgent - Cerebras (passthrough)
        AICostTracking(
            timestamp=now - timedelta(hours=2),
            agent_type="qualification",
            agent_mode="passthrough",
            lead_id=sample_leads[0].id,
            session_id="sess_001",
            prompt_tokens=250,
            completion_tokens=100,
            provider="cerebras",
            model="llama3.1-8b",
            cost_usd=Decimal("0.00001500"),
            latency_ms=450,
            cache_hit=False
        ),
        # EnrichmentAgent - Apollo API
        AICostTracking(
            timestamp=now - timedelta(hours=1),
            agent_type="enrichment",
            agent_mode="passthrough",
            lead_id=sample_leads[0].id,
            session_id="sess_002",
            prompt_tokens=150,
            completion_tokens=80,
            provider="apollo",
            model="api-v1",
            cost_usd=Decimal("0.00005000"),
            latency_ms=1200,
            cache_hit=False
        ),
        # GrowthAgent - DeepSeek (smart_router)
        AICostTracking(
            timestamp=now - timedelta(minutes=30),
            agent_type="growth",
            agent_mode="smart_router",
            lead_id=sample_leads[1].id,
            session_id="sess_003",
            prompt_tokens=500,
            completion_tokens=300,
            provider="deepseek",
            model="deepseek-chat",
            cost_usd=Decimal("0.00010800"),
            latency_ms=2100,
            cache_hit=False
        ),
        # MarketingAgent - Claude (smart_router)
        AICostTracking(
            timestamp=now - timedelta(minutes=15),
            agent_type="marketing",
            agent_mode="smart_router",
            lead_id=sample_leads[1].id,
            session_id="sess_004",
            prompt_tokens=800,
            completion_tokens=600,
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            cost_usd=Decimal("0.00420000"),
            latency_ms=3500,
            cache_hit=False
        ),
        # Cache hit example
        AICostTracking(
            timestamp=now - timedelta(minutes=5),
            agent_type="qualification",
            agent_mode="passthrough",
            lead_id=sample_leads[0].id,
            session_id="sess_005",
            prompt_tokens=250,
            completion_tokens=100,
            provider="cerebras",
            model="llama3.1-8b",
            cost_usd=Decimal("0.00000000"),  # Cache hit = $0
            latency_ms=50,
            cache_hit=True
        ),
    ]

    for record in cost_records:
        db_session.add(record)
    db_session.commit()

    return cost_records


class TestAnalyticsAPI:
    """Test suite for /api/analytics/ai-costs endpoint."""

    def test_get_analytics_all_data(self, client, sample_cost_data):
        """Test analytics endpoint returns all data without filters."""
        response = client.get("/api/analytics/ai-costs")

        assert response.status_code == 200
        data = response.json()

        # Verify total cost and requests
        assert "total_cost_usd" in data
        assert "total_requests" in data
        assert data["total_requests"] == 5

        # Total cost should be sum of all records
        expected_cost = float(
            Decimal("0.00001500") +
            Decimal("0.00005000") +
            Decimal("0.00010800") +
            Decimal("0.00420000") +
            Decimal("0.00000000")  # Cache hit
        )
        assert abs(data["total_cost_usd"] - expected_cost) < 0.000001

    def test_get_analytics_by_agent(self, client, sample_cost_data):
        """Test filtering by agent_type."""
        response = client.get("/api/analytics/ai-costs?agent_type=qualification")

        assert response.status_code == 200
        data = response.json()

        # Should only have 2 qualification requests (1 normal + 1 cache hit)
        assert data["total_requests"] == 2

        # Verify by_agent breakdown includes qualification
        assert "by_agent" in data
        assert len(data["by_agent"]) > 0

        qual_agent = next((a for a in data["by_agent"] if a["agent_type"] == "qualification"), None)
        assert qual_agent is not None
        assert qual_agent["total_requests"] == 2

    def test_get_analytics_by_lead(self, client, sample_cost_data, sample_leads):
        """Test filtering by lead_id."""
        lead_id = sample_leads[0].id
        response = client.get(f"/api/analytics/ai-costs?lead_id={lead_id}")

        assert response.status_code == 200
        data = response.json()

        # Should have 3 requests for first lead (qualification + enrichment + cache hit)
        assert data["total_requests"] == 3

        # Verify by_lead breakdown
        assert "by_lead" in data
        lead_data = next((l for l in data["by_lead"] if l["lead_id"] == lead_id), None)
        assert lead_data is not None
        assert lead_data["company_name"] == "TechCorp Inc"
        assert lead_data["total_requests"] == 3

    def test_get_analytics_date_range(self, client, sample_cost_data):
        """Test filtering by date range."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(hours=1, minutes=30)

        response = client.get(
            f"/api/analytics/ai-costs?start_date={start_date.isoformat()}&end_date={end_date.isoformat()}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only include recent requests (growth, marketing, cache hit)
        assert data["total_requests"] == 3

    def test_get_analytics_by_agent_breakdown(self, client, sample_cost_data):
        """Test by_agent breakdown structure."""
        response = client.get("/api/analytics/ai-costs")

        assert response.status_code == 200
        data = response.json()

        # Verify by_agent structure
        assert "by_agent" in data
        assert len(data["by_agent"]) == 4  # 4 unique agents

        # Check structure of first agent
        agent = data["by_agent"][0]
        assert "agent_type" in agent
        assert "agent_mode" in agent
        assert "total_requests" in agent
        assert "total_cost_usd" in agent
        assert "avg_cost_per_request" in agent
        assert "avg_latency_ms" in agent
        assert "primary_provider" in agent
        assert "primary_model" in agent

    def test_get_analytics_cache_stats(self, client, sample_cost_data):
        """Test cache statistics calculation."""
        response = client.get("/api/analytics/ai-costs")

        assert response.status_code == 200
        data = response.json()

        # Verify cache_stats structure
        assert "cache_stats" in data
        cache_stats = data["cache_stats"]

        assert "total_requests" in cache_stats
        assert "cache_hits" in cache_stats
        assert "cache_hit_rate" in cache_stats
        assert "estimated_savings_usd" in cache_stats

        # 1 cache hit out of 5 requests = 20% hit rate
        assert cache_stats["total_requests"] == 5
        assert cache_stats["cache_hits"] == 1
        assert cache_stats["cache_hit_rate"] == 0.2

        # Estimated savings should be the cost of the cached request (qualification)
        # Original cost was $0.000015, so savings is that amount
        assert cache_stats["estimated_savings_usd"] > 0

    def test_get_analytics_time_series(self, client, sample_cost_data):
        """Test time_series data generation."""
        response = client.get("/api/analytics/ai-costs")

        assert response.status_code == 200
        data = response.json()

        # Verify time_series structure
        assert "time_series" in data
        assert len(data["time_series"]) > 0

        # Check structure of time series point
        point = data["time_series"][0]
        assert "date" in point
        assert "total_cost_usd" in point
        assert "total_requests" in point

    def test_get_analytics_combined_filters(self, client, sample_cost_data, sample_leads):
        """Test combining multiple filters."""
        lead_id = sample_leads[1].id
        response = client.get(
            f"/api/analytics/ai-costs?agent_type=growth&lead_id={lead_id}"
        )

        assert response.status_code == 200
        data = response.json()

        # Should only have 1 request (growth agent for lead 2)
        assert data["total_requests"] == 1

        # Verify the cost matches growth agent
        expected_cost = float(Decimal("0.00010800"))
        assert abs(data["total_cost_usd"] - expected_cost) < 0.000001

    def test_get_analytics_empty_result(self, client, db_session):
        """Test endpoint with no cost data."""
        response = client.get("/api/analytics/ai-costs")

        assert response.status_code == 200
        data = response.json()

        # Should return zero values
        assert data["total_cost_usd"] == 0.0
        assert data["total_requests"] == 0
        assert len(data["by_agent"]) == 0
        assert len(data["by_lead"]) == 0
        assert data["cache_stats"]["cache_hit_rate"] == 0.0

    def test_get_analytics_invalid_date_format(self, client):
        """Test handling of invalid date format."""
        response = client.get("/api/analytics/ai-costs?start_date=invalid-date")

        # Should return 422 validation error
        assert response.status_code == 422

    def test_get_analytics_performance(self, client, sample_cost_data):
        """Test query performance (should be <100ms for small dataset)."""
        import time

        start_time = time.time()
        response = client.get("/api/analytics/ai-costs")
        end_time = time.time()

        assert response.status_code == 200

        # Query should complete in under 100ms
        query_time_ms = (end_time - start_time) * 1000
        assert query_time_ms < 100, f"Query took {query_time_ms}ms, expected <100ms"
