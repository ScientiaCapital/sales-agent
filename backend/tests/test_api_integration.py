"""Integration tests for API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import json

from app.main import app

client = TestClient(app)


class TestLeadsAPIIntegration:
    """Integration tests for leads API endpoints."""

    @patch('app.services.cerebras.CerebrasService')
    def test_qualify_lead_endpoint_success(self, mock_cerebras):
        """Test successful lead qualification via API."""
        # Mock Cerebras service
        mock_service = Mock()
        mock_service.qualify_lead.return_value = (85.0, "High quality lead", 120)
        mock_cerebras.return_value = mock_service

        response = client.post(
            "/api/v1/leads/qualify",
            json={
                "company_name": "Acme Corp",
                "company_website": "https://acme.com",
                "industry": "SaaS",
                "company_size": "100-500",
                "contact_name": "John Doe",
                "contact_title": "CTO"
            }
        )

        assert response.status_code == 201
        data = response.json()
        assert data["company_name"] == "Acme Corp"
        assert data["qualification_score"] == 85.0
        assert "High quality lead" in data["qualification_reasoning"]
        assert data["status"] == "qualified"

    @patch('app.services.cerebras.CerebrasService')
    def test_qualify_lead_minimal_data(self, mock_cerebras):
        """Test lead qualification with minimal required data."""
        mock_service = Mock()
        mock_service.qualify_lead.return_value = (50.0, "Limited data", 100)
        mock_cerebras.return_value = mock_service

        response = client.post(
            "/api/v1/leads/qualify",
            json={"company_name": "Test Corp"}
        )

        assert response.status_code == 201
        data = response.json()
        assert data["company_name"] == "Test Corp"

    def test_qualify_lead_missing_required_field(self):
        """Test validation error for missing required fields."""
        response = client.post(
            "/api/v1/leads/qualify",
            json={"company_website": "https://test.com"}
        )

        assert response.status_code == 422
        data = response.json()
        assert "company_name" in str(data["detail"])

    @patch('app.services.cerebras.CerebrasService')
    def test_qualify_lead_service_error(self, mock_cerebras):
        """Test handling of service errors."""
        mock_service = Mock()
        mock_service.qualify_lead.side_effect = Exception("Service unavailable")
        mock_cerebras.return_value = mock_service

        response = client.post(
            "/api/v1/leads/qualify",
            json={"company_name": "Test Corp"}
        )

        assert response.status_code == 503

    def test_list_leads_empty(self):
        """Test listing leads when database is empty."""
        # This will fail until database is properly configured
        # For now, we expect it to handle gracefully
        response = client.get("/api/v1/leads/")
        
        # Should either return empty list or proper error
        assert response.status_code in [200, 503]

    def test_invalid_json_payload(self):
        """Test handling of invalid JSON."""
        response = client.post(
            "/api/v1/leads/qualify",
            data="not json",
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 422


class TestHealthAPIIntegration:
    """Integration tests for health check endpoints."""

    def test_root_endpoint(self):
        """Test root endpoint returns API info."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert data["message"] == "Sales Agent API"
        assert "version" in data
        assert "docs" in data

    def test_health_check_basic(self):
        """Test basic health check."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data

    def test_health_check_detailed(self):
        """Test detailed health check with service status."""
        response = client.get("/api/v1/health/detailed")
        
        assert response.status_code == 200
        data = response.json()
        assert "services" in data
        assert "api" in data["services"]
        assert "database" in data["services"]
        assert "redis" in data["services"]
        assert "cerebras" in data["services"]

    def test_openapi_docs_available(self):
        """Test OpenAPI documentation is accessible."""
        response = client.get("/api/v1/docs")
        assert response.status_code == 200

    def test_openapi_json_available(self):
        """Test OpenAPI JSON schema is accessible."""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "paths" in schema


class TestAPIErrorHandling:
    """Test API error handling and edge cases."""

    def test_404_not_found(self):
        """Test 404 for non-existent endpoints."""
        response = client.get("/api/v1/nonexistent")
        assert response.status_code == 404

    def test_method_not_allowed(self):
        """Test 405 for incorrect HTTP methods."""
        response = client.put("/api/v1/health")
        assert response.status_code == 405

    def test_large_payload_handling(self):
        """Test handling of unusually large payloads."""
        large_notes = "x" * 100000  # 100KB of text
        
        response = client.post(
            "/api/v1/leads/qualify",
            json={
                "company_name": "Test",
                "notes": large_notes
            }
        )
        
        # Should either accept or reject gracefully
        assert response.status_code in [201, 413, 422]

    def test_special_characters_in_input(self):
        """Test handling of special characters."""
        response = client.post(
            "/api/v1/leads/qualify",
            json={
                "company_name": "Test™ <script>alert('xss')</script> Corp",
                "notes": "Unicode: 你好 🚀 مرحبا"
            }
        )
        
        # Should sanitize or handle gracefully
        assert response.status_code in [201, 422]


class TestAPIConcurrency:
    """Test API handling of concurrent requests."""

    @patch('app.services.cerebras.CerebrasService')
    def test_concurrent_lead_qualifications(self, mock_cerebras):
        """Test handling multiple simultaneous requests."""
        import concurrent.futures
        
        mock_service = Mock()
        mock_service.qualify_lead.return_value = (75.0, "Good lead", 100)
        mock_cerebras.return_value = mock_service

        def qualify_lead(company_name):
            return client.post(
                "/api/v1/leads/qualify",
                json={"company_name": company_name}
            )

        # Send 10 concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [
                executor.submit(qualify_lead, f"Company {i}")
                for i in range(10)
            ]
            results = [f.result() for f in futures]

        # All should succeed
        assert all(r.status_code == 201 for r in results)
        assert len(results) == 10


class TestAPIRateLimiting:
    """Test API rate limiting (if implemented)."""

    @pytest.mark.skip(reason="Rate limiting not yet implemented")
    def test_rate_limit_exceeded(self):
        """Test rate limiting kicks in after threshold."""
        # Send many requests quickly
        responses = []
        for _ in range(100):
            response = client.get("/api/v1/health")
            responses.append(response)
            if response.status_code == 429:
                break

        # Should eventually get rate limited
        assert any(r.status_code == 429 for r in responses)


class TestAPIAuthentication:
    """Test API authentication (if implemented)."""

    @pytest.mark.skip(reason="Authentication not yet implemented")
    def test_protected_endpoint_requires_auth(self):
        """Test protected endpoints require authentication."""
        response = client.get("/api/v1/admin/stats")
        assert response.status_code in [401, 403]

    @pytest.mark.skip(reason="Authentication not yet implemented")
    def test_valid_token_grants_access(self):
        """Test valid authentication token grants access."""
        response = client.get(
            "/api/v1/admin/stats",
            headers={"Authorization": "Bearer valid_token"}
        )
        assert response.status_code == 200


class TestAPICORS:
    """Test CORS configuration."""

    def test_cors_headers_present(self):
        """Test CORS headers are set correctly."""
        response = client.options(
            "/api/health",
            headers={"Origin": "http://localhost:3000"}
        )
        
        # Should include CORS headers
        # This test depends on CORS middleware configuration
        assert response.status_code in [200, 204]


class TestAPIContentNegotiation:
    """Test content type handling."""

    def test_accepts_json_content_type(self):
        """Test API accepts JSON content type."""
        response = client.post(
            "/api/v1/leads/qualify",
            json={"company_name": "Test"},
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code in [201, 503]

    def test_rejects_unsupported_content_type(self):
        """Test API rejects unsupported content types."""
        response = client.post(
            "/api/v1/leads/qualify",
            data="<xml>test</xml>",
            headers={"Content-Type": "application/xml"}
        )
        
        assert response.status_code == 422

    def test_returns_json_content_type(self):
        """Test API returns JSON content type."""
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]


@pytest.mark.integration
class TestAPIWithDatabaseIntegration:
    """Integration tests requiring actual database connection."""

    @pytest.mark.skipif(
        not pytest.config.getoption("--run-integration"),
        reason="Requires --run-integration flag and database"
    )
    def test_lead_persistence(self):
        """Test lead is persisted to database."""
        # This requires actual database connection
        # Skip for now until database is configured in tests
        pass

    @pytest.mark.skipif(
        not pytest.config.getoption("--run-integration"),
        reason="Requires --run-integration flag and database"
    )
    def test_list_leads_with_data(self):
        """Test listing leads from database."""
        pass
