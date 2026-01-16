"""
Unit tests for Top 500 ICP outreach API endpoints.

Tests:
- GET /icp/top500 - Get top 500 ICP leads
- GET /icp/top500/export - Export to CSV
- POST /icp/top500/refresh - Refresh materialized view
- GET /icp/top500/stats - Get statistics
- GET /icp/top500/tiers - Get tier breakdown
"""
import pytest
import uuid
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from fastapi.testclient import TestClient
from fastapi import FastAPI

from app.api.icp import router
from app.models.database import get_async_db


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Create mock async database session."""
    mock = AsyncMock()
    return mock


@pytest.fixture
def app(mock_db):
    """Create test FastAPI app with ICP router and overridden dependencies."""
    app = FastAPI()
    app.include_router(router)

    async def override_get_async_db():
        yield mock_db

    app.dependency_overrides[get_async_db] = override_get_async_db
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_icp_lead():
    """Create mock ICP lead data."""
    return {
        "company_id": str(uuid.uuid4()),
        "company_name": "ACME HVAC Services",
        "domain": "acmehvac.com",
        "website": "https://acmehvac.com",
        "company_phone": "555-123-4567",
        "city": "Atlanta",
        "state": "GA",
        "icp_score": 85,
        "icp_tier": "PLATINUM",
        "total_score": 535,
        "atl_count": 3,
        "has_phone": True,
        "has_hvac_trade": True,
        "is_mep_contractor": True,
        "has_commercial": True,
        "has_industrial": False,
        "has_residential": True,
        "is_multi_trade": True,
        "trade_count": 4,
        "oem_count": 3,
        "intent_score": 25.5,
        "contact_id": str(uuid.uuid4()),
        "atl_name": "John Smith",
        "atl_title": "Owner",
        "atl_email": "john@acmehvac.com",
        "atl_phone": "555-123-4568",
        "atl_linkedin": "https://linkedin.com/in/johnsmith",
        "atl_verified": True,
        "atl_confidence": 95,
        "atl_source": "hunter",
        "rank": 1,
    }


# ============================================================================
# GET /icp/top500 Tests
# ============================================================================

class TestGetTop500:
    """Test top 500 ICP endpoint."""

    def test_get_top500_success(self, client, mock_icp_lead):
        """Test successful top 500 retrieval."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.get_top500.return_value = {
                "leads": [mock_icp_lead],
                "total": 1,
                "limit": 500,
                "offset": 0,
                "has_more": False,
            }
            MockService.return_value = mock_service

            response = client.get("/icp/top500")

            assert response.status_code == 200
            data = response.json()
            assert "leads" in data
            assert len(data["leads"]) == 1
            assert data["total"] == 1
            assert data["leads"][0]["company_name"] == "ACME HVAC Services"
            assert data["leads"][0]["icp_tier"] == "PLATINUM"

    def test_get_top500_with_tier_filter(self, client, mock_icp_lead):
        """Test top 500 with tier filter."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.get_top500.return_value = {
                "leads": [mock_icp_lead],
                "total": 1,
                "limit": 500,
                "offset": 0,
                "has_more": False,
            }
            MockService.return_value = mock_service

            response = client.get("/icp/top500?tier=PLATINUM")

            assert response.status_code == 200
            mock_service.get_top500.assert_called_once()
            call_args = mock_service.get_top500.call_args
            assert call_args.kwargs["tier"] == "PLATINUM"

    def test_get_top500_with_state_filter(self, client, mock_icp_lead):
        """Test top 500 with state filter."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.get_top500.return_value = {
                "leads": [mock_icp_lead],
                "total": 1,
                "limit": 500,
                "offset": 0,
                "has_more": False,
            }
            MockService.return_value = mock_service

            response = client.get("/icp/top500?state=GA")

            assert response.status_code == 200
            mock_service.get_top500.assert_called_once()
            call_args = mock_service.get_top500.call_args
            assert call_args.kwargs["state"] == "GA"

    def test_get_top500_with_phone_filter(self, client, mock_icp_lead):
        """Test top 500 with has_phone filter."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.get_top500.return_value = {
                "leads": [mock_icp_lead],
                "total": 1,
                "limit": 500,
                "offset": 0,
                "has_more": False,
            }
            MockService.return_value = mock_service

            response = client.get("/icp/top500?has_phone=true")

            assert response.status_code == 200
            mock_service.get_top500.assert_called_once()
            call_args = mock_service.get_top500.call_args
            assert call_args.kwargs["has_phone"] is True

    def test_get_top500_pagination(self, client, mock_icp_lead):
        """Test top 500 with pagination."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.get_top500.return_value = {
                "leads": [mock_icp_lead],
                "total": 500,
                "limit": 100,
                "offset": 100,
                "has_more": True,
            }
            MockService.return_value = mock_service

            response = client.get("/icp/top500?limit=100&offset=100")

            assert response.status_code == 200
            data = response.json()
            assert data["limit"] == 100
            assert data["offset"] == 100
            assert data["has_more"] is True

    def test_get_top500_empty_result(self, client):
        """Test top 500 with no results."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.get_top500.return_value = {
                "leads": [],
                "total": 0,
                "limit": 500,
                "offset": 0,
                "has_more": False,
            }
            MockService.return_value = mock_service

            response = client.get("/icp/top500")

            assert response.status_code == 200
            data = response.json()
            assert data["leads"] == []
            assert data["total"] == 0


# ============================================================================
# GET /icp/top500/export Tests
# ============================================================================

class TestExportCSV:
    """Test CSV export endpoint."""

    def test_export_csv_success(self, client):
        """Test successful CSV export."""
        csv_content = "Rank,Company,Domain\n1,ACME HVAC,acmehvac.com"

        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.export_csv.return_value = csv_content
            MockService.return_value = mock_service

            response = client.get("/icp/top500/export")

            assert response.status_code == 200
            assert response.headers["content-type"] == "text/csv; charset=utf-8"
            assert "attachment" in response.headers["content-disposition"]
            assert "top500_icp_outreach" in response.headers["content-disposition"]
            assert ".csv" in response.headers["content-disposition"]

    def test_export_csv_with_filters(self, client):
        """Test CSV export with filters."""
        csv_content = "Rank,Company,Domain\n1,ACME HVAC,acmehvac.com"

        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.export_csv.return_value = csv_content
            MockService.return_value = mock_service

            response = client.get("/icp/top500/export?tier=GOLD&state=TX")

            assert response.status_code == 200
            mock_service.export_csv.assert_called_once()
            call_args = mock_service.export_csv.call_args
            assert call_args.kwargs["tier"] == "GOLD"
            assert call_args.kwargs["state"] == "TX"


# ============================================================================
# POST /icp/top500/refresh Tests
# ============================================================================

class TestRefreshView:
    """Test materialized view refresh endpoint."""

    def test_refresh_success(self, client):
        """Test successful view refresh."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.refresh_materialized_view.return_value = {
                "status": "success",
                "refreshed_at": "2026-01-16T10:30:00",
                "duration_ms": 1500,
            }
            MockService.return_value = mock_service

            response = client.post("/icp/top500/refresh")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "refreshed_at" in data
            assert "duration_ms" in data

    def test_refresh_error(self, client):
        """Test view refresh error handling."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.refresh_materialized_view.return_value = {
                "status": "error",
                "error": "Connection timeout",
            }
            MockService.return_value = mock_service

            response = client.post("/icp/top500/refresh")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "error"
            assert "error" in data


# ============================================================================
# GET /icp/top500/stats Tests
# ============================================================================

class TestStats:
    """Test statistics endpoint."""

    def test_get_stats_success(self, client):
        """Test successful stats retrieval."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.get_stats.return_value = {
                "total": 500,
                "with_phone": 350,
                "verified": 400,
                "phone_coverage_pct": 70.0,
                "avg_icp_score": 75.5,
                "avg_total_score": 425.3,
                "hvac_count": 200,
                "mep_count": 150,
                "tier_breakdown": {
                    "PLATINUM": 100,
                    "GOLD": 200,
                    "SILVER": 150,
                    "BRONZE": 50,
                },
                "top_states": [
                    {"state": "TX", "count": 50},
                    {"state": "CA", "count": 45},
                    {"state": "FL", "count": 40},
                ],
            }
            MockService.return_value = mock_service

            response = client.get("/icp/top500/stats")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 500
            assert data["with_phone"] == 350
            assert data["phone_coverage_pct"] == 70.0
            assert "tier_breakdown" in data
            assert data["tier_breakdown"]["PLATINUM"] == 100
            assert "top_states" in data
            assert len(data["top_states"]) == 3


# ============================================================================
# GET /icp/top500/tiers Tests
# ============================================================================

class TestTierBreakdown:
    """Test tier breakdown endpoint."""

    def test_get_tiers_success(self, client):
        """Test successful tier breakdown retrieval."""
        with patch('app.api.icp.ICPService') as MockService:
            mock_service = AsyncMock()
            mock_service.get_tier_breakdown.return_value = {
                "PLATINUM": 100,
                "GOLD": 200,
                "SILVER": 150,
                "BRONZE": 50,
            }
            MockService.return_value = mock_service

            response = client.get("/icp/top500/tiers")

            assert response.status_code == 200
            data = response.json()
            assert "tier_breakdown" in data
            assert data["tier_breakdown"]["PLATINUM"] == 100
            assert data["tier_breakdown"]["GOLD"] == 200


# ============================================================================
# Service Unit Tests
# ============================================================================

class TestICPService:
    """Test ICP service methods."""

    @pytest.mark.asyncio
    async def test_get_top500_builds_correct_query(self):
        """Test that get_top500 builds correct SQL query."""
        from app.services.icp_service import ICPService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        service = ICPService(mock_db)
        result = await service.get_top500(tier="GOLD", state="TX", has_phone=True)

        assert result["leads"] == []
        assert result["total"] == 0
        assert mock_db.execute.call_count == 2  # Count + data queries

    @pytest.mark.asyncio
    async def test_export_csv_format(self):
        """Test CSV export format is correct."""
        from app.services.icp_service import ICPService

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 0
        mock_result.fetchall.return_value = []
        mock_db.execute.return_value = mock_result

        service = ICPService(mock_db)
        csv_content = await service.export_csv()

        # Should contain header row
        assert "Rank" in csv_content
        assert "Company" in csv_content
        assert "ATL Name" in csv_content
        assert "ATL Email" in csv_content

    @pytest.mark.asyncio
    async def test_refresh_view_success(self):
        """Test materialized view refresh."""
        from app.services.icp_service import ICPService

        mock_db = AsyncMock()
        mock_db.execute.return_value = None
        mock_db.commit.return_value = None

        service = ICPService(mock_db)
        result = await service.refresh_materialized_view()

        assert result["status"] == "success"
        assert "refreshed_at" in result
        assert "duration_ms" in result

    @pytest.mark.asyncio
    async def test_refresh_view_error(self):
        """Test materialized view refresh error handling."""
        from app.services.icp_service import ICPService

        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("Database error")

        service = ICPService(mock_db)
        result = await service.refresh_materialized_view()

        assert result["status"] == "error"
        assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
