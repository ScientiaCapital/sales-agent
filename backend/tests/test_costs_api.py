"""
Integration tests for Cost Reporting API endpoints.

Tests all 5 cost reporting endpoints with various scenarios.
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.models.database import Base, get_db
from app.models.usage_tracker import APICallLog, ProviderType, OperationType


# ============================================================================
# TEST DATABASE SETUP
# ============================================================================

# Create in-memory SQLite database for testing
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Override database dependency with test database."""
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

# Create test database tables
Base.metadata.create_all(bind=engine)

client = TestClient(app)


# ============================================================================
# TEST FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database session for each test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = TestingSessionLocal(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()


@pytest.fixture
def sample_api_calls(db_session):
    """Create sample API call logs for testing."""
    now = datetime.utcnow()

    # Create API calls over the past 7 days
    calls = [
        APICallLog(
            provider=ProviderType.CEREBRAS,
            model="llama3.1-8b",
            endpoint="/chat/completions",
            prompt_tokens=150,
            completion_tokens=300,
            total_tokens=450,
            cost_usd=0.000006,
            latency_ms=633,
            operation_type=OperationType.QUALIFICATION,
            success=True,
            created_at=now - timedelta(days=i % 7)
        )
        for i in range(20)
    ]

    # Add some Anthropic calls
    calls.extend([
        APICallLog(
            provider=ProviderType.ANTHROPIC,
            model="claude-3-5-sonnet",
            endpoint="/messages",
            prompt_tokens=200,
            completion_tokens=400,
            total_tokens=600,
            cost_usd=0.001743,
            latency_ms=4026,
            operation_type=OperationType.RESEARCH,
            success=True,
            created_at=now - timedelta(days=i % 7)
        )
        for i in range(10)
    ])

    # Add some OpenRouter calls
    calls.extend([
        APICallLog(
            provider=ProviderType.OPENROUTER,
            model="deepseek/deepseek-chat",
            endpoint="/chat/completions",
            prompt_tokens=100,
            completion_tokens=200,
            total_tokens=300,
            cost_usd=0.00027,
            latency_ms=2000,
            operation_type=OperationType.RESEARCH,
            success=True,
            created_at=now - timedelta(days=i % 7)
        )
        for i in range(5)
    ])

    db_session.add_all(calls)
    db_session.commit()

    return calls


# ============================================================================
# TEST CASES
# ============================================================================

def test_get_cost_summary_default(sample_api_calls):
    """Test cost summary endpoint with default 7-day period."""
    response = client.get("/api/costs/summary")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "total_cost_usd" in data
    assert "total_requests" in data
    assert "avg_cost_per_request" in data
    assert "provider_breakdown" in data
    assert "cost_trend" in data
    assert "period_days" in data

    # Verify data values
    assert data["total_requests"] == 35  # 20 + 10 + 5
    assert data["period_days"] == 7
    assert len(data["provider_breakdown"]) == 3  # cerebras, anthropic, openrouter

    # Verify provider breakdown
    providers = {p["provider"] for p in data["provider_breakdown"]}
    assert "cerebras" in providers
    assert "anthropic" in providers
    assert "openrouter" in providers


def test_get_cost_summary_custom_period(sample_api_calls):
    """Test cost summary with custom time period."""
    response = client.get("/api/costs/summary?days=3")

    assert response.status_code == 200
    data = response.json()

    assert data["period_days"] == 3
    assert data["total_requests"] > 0


def test_get_cost_summary_invalid_period():
    """Test cost summary with invalid period (exceeds max)."""
    response = client.get("/api/costs/summary?days=100")

    assert response.status_code == 422  # Validation error


def test_get_cost_breakdown_by_provider(sample_api_calls):
    """Test cost breakdown grouped by provider."""
    response = client.get("/api/costs/breakdown?group_by=provider")

    assert response.status_code == 200
    data = response.json()

    assert data["group_by"] == "provider"
    assert len(data["breakdown"]) == 3
    assert data["total_requests"] == 35

    # Verify breakdown items
    for item in data["breakdown"]:
        assert "group_name" in item
        assert "total_cost_usd" in item
        assert "total_requests" in item
        assert "percentage_of_total" in item


def test_get_cost_breakdown_by_model(sample_api_calls):
    """Test cost breakdown grouped by model."""
    response = client.get("/api/costs/breakdown?group_by=model")

    assert response.status_code == 200
    data = response.json()

    assert data["group_by"] == "model"
    assert len(data["breakdown"]) == 3  # llama3.1-8b, claude-3-5-sonnet, deepseek-chat


def test_get_cost_breakdown_by_operation(sample_api_calls):
    """Test cost breakdown grouped by operation type."""
    response = client.get("/api/costs/breakdown?group_by=operation")

    assert response.status_code == 200
    data = response.json()

    assert data["group_by"] == "operation"
    assert len(data["breakdown"]) == 2  # qualification, research


def test_get_cost_breakdown_invalid_group_by():
    """Test cost breakdown with invalid group_by parameter."""
    response = client.get("/api/costs/breakdown?group_by=invalid")

    assert response.status_code == 422  # Validation error


def test_get_usage_timeseries_daily(sample_api_calls):
    """Test usage time series with daily interval."""
    now = datetime.utcnow()
    start_date = now - timedelta(days=7)

    response = client.get(
        f"/api/costs/usage?start_date={start_date.isoformat()}&end_date={now.isoformat()}&interval=daily"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["interval"] == "daily"
    assert "data_points" in data
    assert len(data["data_points"]) > 0

    # Verify data point structure
    for point in data["data_points"]:
        assert "timestamp" in point
        assert "total_cost_usd" in point
        assert "total_requests" in point
        assert "avg_latency_ms" in point
        assert "provider_costs" in point


def test_get_usage_timeseries_hourly(sample_api_calls):
    """Test usage time series with hourly interval."""
    now = datetime.utcnow()
    start_date = now - timedelta(hours=24)

    response = client.get(
        f"/api/costs/usage?start_date={start_date.isoformat()}&end_date={now.isoformat()}&interval=hourly"
    )

    assert response.status_code == 200
    data = response.json()

    assert data["interval"] == "hourly"


def test_get_usage_timeseries_missing_dates():
    """Test usage time series without required date parameters."""
    response = client.get("/api/costs/usage")

    assert response.status_code == 422  # Missing required parameters


def test_get_budget_status(sample_api_calls):
    """Test budget status endpoint."""
    response = client.get("/api/costs/budget/status")

    assert response.status_code == 200
    data = response.json()

    # Verify response structure
    assert "daily_budget_usd" in data
    assert "daily_spend_usd" in data
    assert "daily_utilization_percent" in data
    assert "monthly_budget_usd" in data
    assert "monthly_spend_usd" in data
    assert "monthly_utilization_percent" in data
    assert "threshold_status" in data
    assert "current_strategy" in data

    # Verify threshold status is valid
    assert data["threshold_status"] in ["OK", "WARNING", "CRITICAL", "BLOCKED"]


def test_export_costs_csv(sample_api_calls):
    """Test CSV export."""
    response = client.get("/api/costs/export?format=csv")

    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv; charset=utf-8"
    assert "attachment" in response.headers["content-disposition"]

    # Verify CSV content
    content = response.text
    lines = content.split("\n")

    # Check header
    assert "timestamp" in lines[0]
    assert "provider" in lines[0]
    assert "cost_usd" in lines[0]

    # Check data rows
    assert len(lines) > 35  # Should have header + 35 data rows


def test_export_costs_json(sample_api_calls):
    """Test JSON export."""
    response = client.get("/api/costs/export?format=json")

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert "attachment" in response.headers["content-disposition"]

    # Verify JSON content
    data = response.json()
    assert isinstance(data, list)
    assert len(data) == 35

    # Verify first record structure
    assert "timestamp" in data[0]
    assert "provider" in data[0]
    assert "model" in data[0]
    assert "cost_usd" in data[0]


def test_export_costs_with_date_range(sample_api_calls):
    """Test export with custom date range."""
    now = datetime.utcnow()
    start_date = now - timedelta(days=3)

    response = client.get(
        f"/api/costs/export?format=csv&start_date={start_date.isoformat()}&end_date={now.isoformat()}"
    )

    assert response.status_code == 200


def test_export_costs_invalid_format():
    """Test export with invalid format."""
    response = client.get("/api/costs/export?format=xml")

    assert response.status_code == 422  # Validation error


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

def test_cost_summary_matches_breakdown(sample_api_calls):
    """Test that cost summary totals match breakdown totals."""
    summary_response = client.get("/api/costs/summary?days=7")
    breakdown_response = client.get("/api/costs/breakdown?group_by=provider")

    assert summary_response.status_code == 200
    assert breakdown_response.status_code == 200

    summary_data = summary_response.json()
    breakdown_data = breakdown_response.json()

    # Totals should match
    assert summary_data["total_requests"] == breakdown_data["total_requests"]
    assert abs(summary_data["total_cost_usd"] - breakdown_data["total_cost_usd"]) < 0.000001


def test_budget_utilization_calculation(sample_api_calls):
    """Test budget utilization is calculated correctly."""
    response = client.get("/api/costs/budget/status")

    assert response.status_code == 200
    data = response.json()

    # Verify utilization calculation
    expected_daily_util = (data["daily_spend_usd"] / data["daily_budget_usd"]) * 100
    assert abs(data["daily_utilization_percent"] - expected_daily_util) < 0.01

    expected_monthly_util = (data["monthly_spend_usd"] / data["monthly_budget_usd"]) * 100
    assert abs(data["monthly_utilization_percent"] - expected_monthly_util) < 0.01
