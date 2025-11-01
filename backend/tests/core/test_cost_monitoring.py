"""Tests for cost monitoring helper functions."""

import pytest
from datetime import datetime, timedelta, date
from decimal import Decimal
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.models.database import Base
from app.models.ai_cost_tracking import AICostTracking
from app.models.lead import Lead
from app.core.cost_monitoring import (
    get_daily_spend,
    get_cost_per_lead_avg,
    get_cache_hit_rate,
    check_cost_alerts
)


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
def sample_leads(db_session):
    """Create sample leads for testing."""
    leads = [
        Lead(
            company_name=f"Company {i}",
            contact_email=f"contact{i}@company.com",
            qualification_score=80,
            created_at=datetime.utcnow() - timedelta(days=i)
        )
        for i in range(10)
    ]
    for lead in leads:
        db_session.add(lead)
    db_session.commit()

    # Refresh to get IDs
    for lead in leads:
        db_session.refresh(lead)

    return leads


@pytest.fixture
def cost_data_today(db_session, sample_leads):
    """Create cost tracking data for today."""
    today = datetime.utcnow()

    costs = [
        AICostTracking(
            timestamp=today - timedelta(hours=i),
            agent_type="qualification",
            agent_mode="passthrough",
            lead_id=sample_leads[i].id if i < len(sample_leads) else None,
            prompt_tokens=200,
            completion_tokens=100,
            provider="cerebras",
            model="llama3.1-8b",
            cost_usd=Decimal("0.00001000"),
            latency_ms=500,
            cache_hit=False
        )
        for i in range(5)
    ]

    for cost in costs:
        db_session.add(cost)
    db_session.commit()

    return costs


@pytest.fixture
def cost_data_week(db_session, sample_leads):
    """Create cost tracking data over the past week."""
    costs = []

    for day in range(7):
        day_start = datetime.utcnow() - timedelta(days=day)

        # Create varying number of requests per day
        for hour in range(day + 1):  # More requests on recent days
            cost = AICostTracking(
                timestamp=day_start - timedelta(hours=hour),
                agent_type="qualification",
                agent_mode="passthrough",
                lead_id=sample_leads[day].id if day < len(sample_leads) else None,
                prompt_tokens=200,
                completion_tokens=100,
                provider="cerebras",
                model="llama3.1-8b",
                cost_usd=Decimal("0.00002000"),
                latency_ms=500,
                cache_hit=False
            )
            costs.append(cost)
            db_session.add(cost)

    db_session.commit()
    return costs


@pytest.fixture
def cache_hit_data(db_session, sample_leads):
    """Create cost data with cache hits."""
    now = datetime.utcnow()

    costs = [
        # Regular requests
        AICostTracking(
            timestamp=now - timedelta(hours=i),
            agent_type="qualification",
            agent_mode="passthrough",
            lead_id=sample_leads[0].id,
            prompt_tokens=200,
            completion_tokens=100,
            provider="cerebras",
            model="llama3.1-8b",
            cost_usd=Decimal("0.00001000"),
            latency_ms=500,
            cache_hit=False
        )
        for i in range(7)
    ] + [
        # Cache hits (3 out of 10 = 30% hit rate)
        AICostTracking(
            timestamp=now - timedelta(hours=i),
            agent_type="qualification",
            agent_mode="passthrough",
            lead_id=sample_leads[0].id,
            prompt_tokens=200,
            completion_tokens=100,
            provider="cerebras",
            model="llama3.1-8b",
            cost_usd=Decimal("0.00000000"),
            latency_ms=50,
            cache_hit=True
        )
        for i in range(7, 10)
    ]

    for cost in costs:
        db_session.add(cost)
    db_session.commit()

    return costs


class TestGetDailySpend:
    """Tests for get_daily_spend function."""

    async def test_daily_spend_today(self, db_session, cost_data_today):
        """Test getting today's spend."""
        result = await get_daily_spend(db_session)

        assert "date" in result
        assert "total_cost_usd" in result
        assert "total_requests" in result

        # Today's date
        assert result["date"] == datetime.utcnow().date().isoformat()

        # 5 requests at $0.00001 each = $0.00005
        expected_cost = 5 * 0.00001
        assert abs(result["total_cost_usd"] - expected_cost) < 0.000001
        assert result["total_requests"] == 5

    async def test_daily_spend_specific_date(self, db_session, cost_data_week):
        """Test getting spend for a specific date."""
        target_date = datetime.utcnow().date() - timedelta(days=3)
        result = await get_daily_spend(db_session, date=target_date)

        assert result["date"] == target_date.isoformat()
        assert result["total_requests"] > 0
        assert result["total_cost_usd"] > 0

    async def test_daily_spend_no_data(self, db_session):
        """Test getting daily spend when there's no data."""
        result = await get_daily_spend(db_session)

        assert result["total_cost_usd"] == 0.0
        assert result["total_requests"] == 0

    async def test_daily_spend_future_date(self, db_session, cost_data_today):
        """Test getting spend for future date (should return 0)."""
        future_date = datetime.utcnow().date() + timedelta(days=1)
        result = await get_daily_spend(db_session, date=future_date)

        assert result["total_cost_usd"] == 0.0
        assert result["total_requests"] == 0


class TestGetCostPerLeadAvg:
    """Tests for get_cost_per_lead_avg function."""

    async def test_cost_per_lead_basic(self, db_session, cost_data_week, sample_leads):
        """Test basic cost per lead calculation."""
        result = await get_cost_per_lead_avg(db_session, days=7)

        assert isinstance(result, float)
        assert result > 0

        # With varying costs per day, should have a reasonable average
        # Each day has (day+1) requests at $0.00002
        # Total requests = 1+2+3+4+5+6+7 = 28
        # Total cost = 28 * $0.00002 = $0.00056
        # 7 unique leads = $0.00056 / 7 = $0.00008
        expected_avg = 0.00056 / 7
        assert abs(result - expected_avg) < 0.00001

    async def test_cost_per_lead_custom_days(self, db_session, cost_data_week, sample_leads):
        """Test cost per lead over custom time period."""
        result = await get_cost_per_lead_avg(db_session, days=3)

        assert isinstance(result, float)
        assert result > 0

    async def test_cost_per_lead_no_leads(self, db_session):
        """Test cost per lead when there are no leads."""
        result = await get_cost_per_lead_avg(db_session, days=7)

        # Should return 0 when no leads
        assert result == 0.0

    async def test_cost_per_lead_single_day(self, db_session, cost_data_today, sample_leads):
        """Test cost per lead for single day."""
        result = await get_cost_per_lead_avg(db_session, days=1)

        # 5 requests at $0.00001 = $0.00005 total
        # 5 unique leads = $0.00005 / 5 = $0.00001 per lead
        expected = 0.00005 / 5
        assert abs(result - expected) < 0.000001


class TestGetCacheHitRate:
    """Tests for get_cache_hit_rate function."""

    async def test_cache_hit_rate_basic(self, db_session, cache_hit_data):
        """Test basic cache hit rate calculation."""
        result = await get_cache_hit_rate(db_session, hours=24)

        assert "cache_hit_rate" in result
        assert "total_requests" in result
        assert "cache_hits" in result

        # 3 cache hits out of 10 requests = 30%
        assert result["total_requests"] == 10
        assert result["cache_hits"] == 3
        assert abs(result["cache_hit_rate"] - 0.3) < 0.01

    async def test_cache_hit_rate_no_data(self, db_session):
        """Test cache hit rate with no data."""
        result = await get_cache_hit_rate(db_session, hours=24)

        assert result["cache_hit_rate"] == 0.0
        assert result["total_requests"] == 0
        assert result["cache_hits"] == 0

    async def test_cache_hit_rate_no_hits(self, db_session, cost_data_today):
        """Test cache hit rate when there are no cache hits."""
        result = await get_cache_hit_rate(db_session, hours=24)

        assert result["cache_hit_rate"] == 0.0
        assert result["total_requests"] > 0
        assert result["cache_hits"] == 0

    async def test_cache_hit_rate_custom_hours(self, db_session, cache_hit_data):
        """Test cache hit rate over custom time period."""
        # Only recent data (last 8 hours should have all 3 cache hits)
        result = await get_cache_hit_rate(db_session, hours=8)

        assert result["total_requests"] <= 10
        assert result["cache_hits"] == 3


class TestCheckCostAlerts:
    """Tests for check_cost_alerts function."""

    async def test_cost_alerts_under_budget(self, db_session, cost_data_today):
        """Test cost alerts when under budget."""
        # Daily spend is $0.00005, well under $10 budget
        alerts = await check_cost_alerts(db_session, daily_budget=10.0)

        # Should have no alerts or info-level alert
        assert isinstance(alerts, list)
        if len(alerts) > 0:
            # If there are alerts, they should be info/success level
            for alert in alerts:
                assert alert["severity"] in ["info", "success"]

    async def test_cost_alerts_approaching_budget(self, db_session):
        """Test cost alerts when approaching budget threshold."""
        # Create data close to 80% of budget
        today = datetime.utcnow()
        for i in range(80):
            cost = AICostTracking(
                timestamp=today - timedelta(minutes=i),
                agent_type="qualification",
                agent_mode="passthrough",
                prompt_tokens=200,
                completion_tokens=100,
                provider="cerebras",
                model="llama3.1-8b",
                cost_usd=Decimal("0.00100000"),  # $0.001 per request
                latency_ms=500,
                cache_hit=False
            )
            db_session.add(cost)
        db_session.commit()

        # Budget is $0.10, spend is $0.08 (80%)
        alerts = await check_cost_alerts(db_session, daily_budget=0.10)

        # Should have warning alert
        assert len(alerts) > 0
        assert any(alert["severity"] == "warning" for alert in alerts)

    async def test_cost_alerts_exceeded_budget(self, db_session):
        """Test cost alerts when budget is exceeded."""
        # Create data exceeding budget
        today = datetime.utcnow()
        for i in range(15):
            cost = AICostTracking(
                timestamp=today - timedelta(minutes=i),
                agent_type="qualification",
                agent_mode="passthrough",
                prompt_tokens=200,
                completion_tokens=100,
                provider="cerebras",
                model="llama3.1-8b",
                cost_usd=Decimal("0.01000000"),  # $0.01 per request
                latency_ms=500,
                cache_hit=False
            )
            db_session.add(cost)
        db_session.commit()

        # Budget is $0.10, spend is $0.15 (150%)
        alerts = await check_cost_alerts(db_session, daily_budget=0.10)

        # Should have critical alert
        assert len(alerts) > 0
        assert any(alert["severity"] in ["critical", "error"] for alert in alerts)
        assert any("exceeded" in alert["message"].lower() for alert in alerts)

    async def test_cost_alerts_no_data(self, db_session):
        """Test cost alerts with no spending data."""
        alerts = await check_cost_alerts(db_session, daily_budget=10.0)

        # Should have info alert or empty list
        assert isinstance(alerts, list)
        if len(alerts) > 0:
            assert alerts[0]["severity"] == "info"

    async def test_cost_alerts_custom_budget(self, db_session, cost_data_today):
        """Test cost alerts with custom budget threshold."""
        # Very low budget to trigger alert
        alerts = await check_cost_alerts(db_session, daily_budget=0.00001)

        # Should have critical alert since spend ($0.00005) > budget ($0.00001)
        assert len(alerts) > 0
        assert any(alert["severity"] in ["critical", "error", "warning"] for alert in alerts)

    async def test_cost_alerts_structure(self, db_session, cost_data_today):
        """Test structure of cost alerts."""
        alerts = await check_cost_alerts(db_session, daily_budget=10.0)

        # Verify alert structure
        for alert in alerts:
            assert "severity" in alert
            assert "message" in alert
            assert "current_spend" in alert
            assert isinstance(alert["severity"], str)
            assert isinstance(alert["message"], str)
            assert isinstance(alert["current_spend"], float)
