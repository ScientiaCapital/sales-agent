"""
Integration tests for Hunter.io in the supervised pipeline.

These tests verify Hunter.io integrates correctly with the supervised
enrichment pipeline without requiring langchain or other optional dependencies.
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

# Import pipeline components that don't require langchain
from app.services.supervised_pipeline.stages.hunter import HunterStage
from app.services.supervised_pipeline.base import StageResult
from app.services.hunter_service import HunterService, extract_domain


class TestHunterServiceIntegration:
    """Test HunterService as standalone component."""

    @pytest.mark.asyncio
    async def test_domain_search_returns_atl_contacts(self):
        """Test domain_search correctly filters ATL contacts."""
        with patch.object(HunterService, '__init__', lambda self: None):
            service = HunterService()
            service.api_key = "test_key"
            service.base_url = "https://api.hunter.io/v2"
            service.timeout = 10

            # Mock httpx client
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "data": {
                    "domain": "example.com",
                    "emails": [
                        {
                            "value": "ceo@example.com",
                            "first_name": "John",
                            "last_name": "CEO",
                            "position": "Chief Executive Officer",
                            "confidence": 95
                        },
                        {
                            "value": "dev@example.com",
                            "first_name": "Jane",
                            "last_name": "Dev",
                            "position": "Software Developer",
                            "confidence": 90
                        }
                    ]
                }
            }

            with patch('httpx.AsyncClient') as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_response)
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock(return_value=None)
                MockClient.return_value = mock_client

                result = await service.domain_search("example.com", atl_only=True)

                assert result is not None
                assert len(result) == 1  # Only CEO is ATL
                assert result[0]["email"] == "ceo@example.com"
                assert result[0]["is_atl"] is True


class TestHunterStageIntegration:
    """Test HunterStage in pipeline context."""

    @pytest.mark.asyncio
    async def test_stage_returns_stage_result(self):
        """Verify HunterStage returns proper StageResult."""
        with patch('app.services.supervised_pipeline.stages.hunter.HunterService') as MockService:
            mock_service = MagicMock()
            mock_service.get_email_count = AsyncMock(return_value={
                "total": 10,
                "has_data": True
            })
            mock_service.domain_search = AsyncMock(return_value=[
                {"email": "ceo@test.com", "position": "CEO", "is_atl": True}
            ])
            MockService.return_value = mock_service

            stage = HunterStage()
            result = await stage.execute({"domain": "test.com"})

            assert isinstance(result, StageResult)
            assert result.success is True
            assert result.cost_usd == 0.01

    @pytest.mark.asyncio
    async def test_stage_cost_tracking(self):
        """Verify proper cost tracking for pipeline."""
        with patch('app.services.supervised_pipeline.stages.hunter.HunterService') as MockService:
            mock_service = MagicMock()
            mock_service.get_email_count = AsyncMock(return_value={
                "total": 5,
                "has_data": True
            })
            mock_service.domain_search = AsyncMock(return_value=[])
            MockService.return_value = mock_service

            stage = HunterStage()

            # Execute for multiple companies
            results = []
            for domain in ["a.com", "b.com", "c.com"]:
                result = await stage.execute({"domain": domain})
                results.append(result)

            total_cost = sum(r.cost_usd for r in results)
            assert total_cost == 0.03  # $0.01 * 3 = $0.03


class TestDomainExtraction:
    """Test domain extraction utility."""

    def test_extract_from_https_url(self):
        assert extract_domain("https://example.com") == "example.com"

    def test_extract_from_http_url(self):
        assert extract_domain("http://example.com") == "example.com"

    def test_extract_from_url_with_path(self):
        assert extract_domain("https://example.com/about") == "example.com"

    def test_extract_from_www_subdomain(self):
        assert extract_domain("https://www.example.com") == "www.example.com"

    def test_extract_plain_domain(self):
        assert extract_domain("example.com") == "example.com"

    def test_extract_empty_string(self):
        assert extract_domain("") == ""


class TestHunterCostOptimization:
    """Test cost optimization features in pipeline."""

    @pytest.mark.asyncio
    async def test_free_endpoint_prevents_paid_calls(self):
        """Verify get_email_count gates expensive domain_search calls."""
        with patch('app.services.supervised_pipeline.stages.hunter.HunterService') as MockService:
            mock_service = MagicMock()
            mock_service.get_email_count = AsyncMock(return_value={
                "total": 0,
                "has_data": False
            })
            mock_service.domain_search = AsyncMock()
            MockService.return_value = mock_service

            stage = HunterStage()
            result = await stage.execute({"domain": "nodata.com"})

            assert result.success is True
            assert result.cost_usd == 0.0  # No paid call
            mock_service.domain_search.assert_not_called()

    @pytest.mark.asyncio
    async def test_paid_call_made_when_data_exists(self):
        """Verify domain_search called when email_count shows data."""
        with patch('app.services.supervised_pipeline.stages.hunter.HunterService') as MockService:
            mock_service = MagicMock()
            mock_service.get_email_count = AsyncMock(return_value={
                "total": 25,
                "has_data": True
            })
            mock_service.domain_search = AsyncMock(return_value=[
                {"email": "test@hasdata.com", "is_atl": True}
            ])
            MockService.return_value = mock_service

            stage = HunterStage()
            result = await stage.execute({"domain": "hasdata.com"})

            assert result.success is True
            assert result.cost_usd == 0.01  # Paid call made
            mock_service.domain_search.assert_called_once()


class TestHunterErrorHandling:
    """Test error handling in Hunter pipeline integration."""

    @pytest.mark.asyncio
    async def test_graceful_api_failure(self):
        """Test graceful handling of API failures."""
        with patch('app.services.supervised_pipeline.stages.hunter.HunterService') as MockService:
            mock_service = MagicMock()
            mock_service.get_email_count = AsyncMock(
                side_effect=Exception("API connection failed")
            )
            MockService.return_value = mock_service

            stage = HunterStage()
            result = await stage.execute({"domain": "failing.com"})

            assert result.success is False
            assert "API connection failed" in result.error

    @pytest.mark.asyncio
    async def test_missing_domain(self):
        """Test handling of missing domain."""
        stage = HunterStage()
        result = await stage.execute({})

        assert result.success is False
        assert "No domain" in result.error
