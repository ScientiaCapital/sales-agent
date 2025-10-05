"""
Tests for Apollo.io contact enrichment service and API endpoints.

Tests both the ApolloService class and the FastAPI endpoints for:
- Single contact enrichment
- Company enrichment  
- Bulk contact enrichment (up to 10)
- Credit balance checking

Mocks Apollo.io API responses to avoid actual API calls during testing.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from fastapi.testclient import TestClient
from httpx import AsyncClient, Response
import json

from app.main import app
from app.services.apollo import ApolloService
from app.schemas.contact import Contact
from app.core.exceptions import (
    MissingAPIKeyError,
    ValidationError,
    APIAuthenticationError,
    APIRateLimitError,
    APIConnectionError,
    ExternalAPIException
)


@pytest.fixture
def mock_apollo_api_key(monkeypatch):
    """Provide mock Apollo API key."""
    monkeypatch.setenv("APOLLO_API_KEY", "test_apollo_api_key")
    return "test_apollo_api_key"


@pytest.fixture
def apollo_service(mock_apollo_api_key):
    """Create ApolloService instance with mocked API key."""
    return ApolloService(api_key=mock_apollo_api_key)


@pytest.fixture
def mock_person_response():
    """Mock Apollo person enrichment response."""
    return {
        "person": {
            "id": "apollo_12345",
            "first_name": "John",
            "last_name": "Doe",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "personal_email": "john.personal@gmail.com",
            "email_status": "verified",
            "title": "VP of Engineering",
            "headline": "Engineering leader with 15+ years experience",
            "phone_number": "+1-555-0123",
            "linkedin_url": "https://linkedin.com/in/johndoe",
            "employment_history": [
                {
                    "organization_name": "Example Corp",
                    "title": "VP of Engineering",
                    "start_date": "2020-01-01",
                    "current": True
                },
                {
                    "organization_name": "Previous Corp",
                    "title": "Senior Engineer",
                    "start_date": "2015-01-01",
                    "end_date": "2019-12-31",
                    "current": False
                }
            ],
            "city": "San Francisco",
            "state": "California",
            "country": "United States"
        }
    }


@pytest.fixture
def mock_company_response():
    """Mock Apollo company enrichment response."""
    return {
        "organization": {
            "id": "org_67890",
            "name": "Example Corp",
            "primary_domain": "example.com",
            "industry": "Software",
            "estimated_num_employees": 250,
            "founded_year": 2010,
            "publicly_traded_symbol": None,
            "phone": "+1-555-9999",
            "linkedin_url": "https://linkedin.com/company/example-corp",
            "twitter_url": "https://twitter.com/examplecorp",
            "facebook_url": None,
            "city": "San Francisco",
            "state": "CA",
            "country": "US",
            "annual_revenue": 50000000,
            "total_funding": 25000000,
            "description": "Leading software company",
            "technologies": ["AWS", "Python", "React"]
        }
    }


@pytest.fixture
def mock_bulk_response():
    """Mock Apollo bulk enrichment response."""
    return {
        "matches": [
            {
                "person": {
                    "id": "apollo_1",
                    "first_name": "Alice",
                    "last_name": "Smith",
                    "email": "alice@example.com",
                    "title": "CTO",
                    "employment_history": [
                        {
                            "organization_name": "Tech Corp",
                            "title": "CTO",
                            "current": True
                        }
                    ]
                }
            },
            {
                "person": {
                    "id": "apollo_2",
                    "first_name": "Bob",
                    "last_name": "Johnson",
                    "email": "bob@example.com",
                    "title": "CEO",
                    "employment_history": [
                        {
                            "organization_name": "Business Inc",
                            "title": "CEO",
                            "current": True
                        }
                    ]
                }
            }
        ]
    }


class TestApolloService:
    """Test suite for ApolloService class."""
    
    def test_init_with_api_key(self, mock_apollo_api_key):
        """Test service initialization with API key."""
        service = ApolloService(api_key=mock_apollo_api_key)
        assert service.api_key == mock_apollo_api_key
        assert service.client is not None
        assert service.client.headers["x-api-key"] == mock_apollo_api_key
    
    def test_init_without_api_key(self, monkeypatch):
        """Test service initialization fails without API key."""
        monkeypatch.delenv("APOLLO_API_KEY", raising=False)
        
        with pytest.raises(MissingAPIKeyError) as exc_info:
            ApolloService()
        
        assert "APOLLO_API_KEY" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_enrich_contact_success(self, apollo_service, mock_person_response):
        """Test successful contact enrichment."""
        # Mock httpx response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_person_response
        
        with patch.object(apollo_service.client, 'post', return_value=mock_response):
            contact = await apollo_service.enrich_contact(
                email="john.doe@example.com",
                reveal_personal_email=True
            )
            
            assert isinstance(contact, Contact)
            assert contact.email == "john.doe@example.com"
            assert contact.first_name == "John"
            assert contact.last_name == "Doe"
            assert contact.title == "VP of Engineering"
            assert contact.company == "Example Corp"
            assert contact.phone == "+1-555-0123"
            assert contact.linkedin_url == "https://linkedin.com/in/johndoe"
            assert contact.source_platform == "apollo"
            assert contact.external_ids["apollo"] == "apollo_12345"
    
    @pytest.mark.asyncio
    async def test_enrich_contact_validation_error(self, apollo_service):
        """Test contact enrichment fails without required fields."""
        with pytest.raises(ValidationError) as exc_info:
            await apollo_service.enrich_contact()
        
        assert "Must provide" in str(exc_info.value)
    
    @pytest.mark.asyncio
    async def test_enrich_contact_rate_limit(self, apollo_service):
        """Test rate limit handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 429
        mock_response.json.return_value = {"error": "Rate limit exceeded"}
        
        with patch.object(apollo_service.client, 'post', return_value=mock_response):
            with pytest.raises(APIRateLimitError):
                await apollo_service.enrich_contact(email="test@example.com")
    
    @pytest.mark.asyncio
    async def test_enrich_contact_authentication_error(self, apollo_service):
        """Test authentication error handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 401
        mock_response.json.return_value = {"error": "Invalid API key"}
        
        with patch.object(apollo_service.client, 'post', return_value=mock_response):
            with pytest.raises(APIAuthenticationError):
                await apollo_service.enrich_contact(email="test@example.com")
    
    @pytest.mark.asyncio
    async def test_enrich_contact_not_found(self, apollo_service):
        """Test contact not found handling."""
        mock_response = AsyncMock()
        mock_response.status_code = 404
        mock_response.json.return_value = {"error": "Person not found"}
        
        with patch.object(apollo_service.client, 'post', return_value=mock_response):
            with pytest.raises(ExternalAPIException) as exc_info:
                await apollo_service.enrich_contact(email="notfound@example.com")
            
            assert "not found" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_enrich_company_success(self, apollo_service, mock_company_response):
        """Test successful company enrichment."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_company_response
        
        with patch.object(apollo_service.client, 'post', return_value=mock_response):
            company = await apollo_service.enrich_company(domain="example.com")
            
            assert company["id"] == "org_67890"
            assert company["name"] == "Example Corp"
            assert company["domain"] == "example.com"
            assert company["industry"] == "Software"
            assert company["employee_count"] == 250
    
    @pytest.mark.asyncio
    async def test_enrich_company_domain_cleaning(self, apollo_service, mock_company_response):
        """Test domain cleaning (removes www. and @)."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_company_response
        
        with patch.object(apollo_service.client, 'post', return_value=mock_response) as mock_post:
            # Test with www.
            await apollo_service.enrich_company(domain="www.example.com")
            call_args = mock_post.call_args
            assert call_args[1]["params"]["domain"] == "example.com"
            
            # Test with @
            await apollo_service.enrich_company(domain="@example.com")
            call_args = mock_post.call_args
            assert call_args[1]["params"]["domain"] == "example.com"
    
    @pytest.mark.asyncio
    async def test_bulk_enrich_contacts_success(self, apollo_service, mock_bulk_response):
        """Test successful bulk enrichment."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_bulk_response
        
        contacts_to_enrich = [
            {"email": "alice@example.com"},
            {"email": "bob@example.com"}
        ]
        
        with patch.object(apollo_service.client, 'post', return_value=mock_response):
            contacts = await apollo_service.bulk_enrich_contacts(contacts_to_enrich)
            
            assert len(contacts) == 2
            assert contacts[0].first_name == "Alice"
            assert contacts[1].first_name == "Bob"
    
    @pytest.mark.asyncio
    async def test_bulk_enrich_contacts_limit(self, apollo_service):
        """Test bulk enrichment enforces 10-contact limit."""
        contacts = [{"email": f"user{i}@example.com"} for i in range(11)]
        
        with pytest.raises(ValidationError) as exc_info:
            await apollo_service.bulk_enrich_contacts(contacts)
        
        assert "limited to 10" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_close_client(self, apollo_service):
        """Test HTTP client cleanup."""
        with patch.object(apollo_service.client, 'aclose', new_callable=AsyncMock) as mock_close:
            await apollo_service.close()
            mock_close.assert_called_once()


class TestApolloAPI:
    """Test suite for Apollo API endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def mock_apollo_service(self, mock_apollo_api_key):
        """Mock ApolloService for API tests."""
        with patch('app.api.apollo.ApolloService') as mock:
            service = AsyncMock()
            service.api_key = mock_apollo_api_key
            mock.return_value = service
            yield service
    
    def test_enrich_contact_endpoint(self, client, mock_apollo_service):
        """Test POST /apollo/enrich/contact endpoint."""
        # Mock service response
        mock_contact = Contact(
            email="john@example.com",
            first_name="John",
            last_name="Doe",
            title="CTO",
            company="Example Corp",
            source_platform="apollo",
            external_ids={"apollo": "12345"}
        )
        mock_apollo_service.enrich_contact.return_value = mock_contact
        mock_apollo_service.close = AsyncMock()
        
        response = client.post(
            "/api/v1/apollo/enrich/contact",
            json={
                "email": "john@example.com",
                "reveal_personal_email": True
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["contact"]["email"] == "john@example.com"
        assert data["contact"]["first_name"] == "John"
        assert data["source"] == "apollo"
    
    def test_enrich_contact_validation_error(self, client, mock_apollo_service):
        """Test contact enrichment with invalid data."""
        mock_apollo_service.enrich_contact.side_effect = ValidationError(
            "Must provide email or name",
            context={}
        )
        mock_apollo_service.close = AsyncMock()
        
        response = client.post(
            "/api/v1/apollo/enrich/contact",
            json={}
        )
        
        assert response.status_code == 400
    
    def test_enrich_contact_rate_limit(self, client, mock_apollo_service):
        """Test rate limit error handling."""
        mock_apollo_service.enrich_contact.side_effect = APIRateLimitError(
            "Rate limit exceeded",
            context={}
        )
        mock_apollo_service.close = AsyncMock()
        
        response = client.post(
            "/api/v1/apollo/enrich/contact",
            json={"email": "test@example.com"}
        )
        
        assert response.status_code == 429
    
    def test_enrich_company_endpoint(self, client, mock_apollo_service):
        """Test POST /apollo/enrich/company endpoint."""
        mock_company = {
            "id": "org_123",
            "name": "Example Corp",
            "domain": "example.com",
            "industry": "Software",
            "employee_count": 250
        }
        mock_apollo_service.enrich_company.return_value = mock_company
        mock_apollo_service.close = AsyncMock()
        
        response = client.post(
            "/api/v1/apollo/enrich/company",
            json={"domain": "example.com"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["company"]["name"] == "Example Corp"
    
    def test_bulk_enrich_contacts_endpoint(self, client, mock_apollo_service):
        """Test POST /apollo/enrich/bulk endpoint."""
        mock_contacts = [
            Contact(
                email=f"user{i}@example.com",
                first_name=f"User{i}",
                last_name="Test",
                source_platform="apollo",
                external_ids={"apollo": f"id_{i}"}
            )
            for i in range(3)
        ]
        mock_apollo_service.bulk_enrich_contacts.return_value = mock_contacts
        mock_apollo_service.close = AsyncMock()
        
        response = client.post(
            "/api/v1/apollo/enrich/bulk",
            json={
                "contacts": [
                    {"email": "user0@example.com"},
                    {"email": "user1@example.com"},
                    {"email": "user2@example.com"}
                ]
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["contacts"]) == 3
    
    def test_bulk_enrich_limit_exceeded(self, client, mock_apollo_service):
        """Test bulk enrichment with > 10 contacts."""
        mock_apollo_service.bulk_enrich_contacts.side_effect = ValidationError(
            "Bulk enrichment limited to 10 contacts",
            context={}
        )
        mock_apollo_service.close = AsyncMock()
        
        contacts = [{"email": f"user{i}@example.com"} for i in range(11)]
        response = client.post(
            "/api/v1/apollo/enrich/bulk",
            json={"contacts": contacts}
        )
        
        assert response.status_code == 400
    
    def test_get_credits_endpoint(self, client, mock_apollo_service):
        """Test GET /apollo/credits endpoint."""
        mock_apollo_service.get_credit_balance.return_value = {
            "total_credits": 1000,
            "used_credits": 250,
            "remaining_credits": 750
        }
        mock_apollo_service.close = AsyncMock()
        
        response = client.get("/api/v1/apollo/credits")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_credits"] == 1000
        assert data["remaining_credits"] == 750


class TestApolloIntegration:
    """Integration tests combining service and API."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.mark.asyncio
    async def test_domain_cleaning_integration(self, mock_apollo_api_key):
        """Test domain cleaning works end-to-end."""
        service = ApolloService(api_key=mock_apollo_api_key)
        
        # Mock response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "organization": {
                "id": "org_123",
                "name": "Test Corp",
                "primary_domain": "test.com"
            }
        }
        
        with patch.object(service.client, 'post', return_value=mock_response) as mock_post:
            await service.enrich_company(domain="www.test.com")
            
            # Verify domain was cleaned
            call_params = mock_post.call_args[1]["params"]
            assert call_params["domain"] == "test.com"
            assert "www." not in call_params["domain"]
    
    @pytest.mark.asyncio
    async def test_contact_mapping_integration(self, mock_apollo_api_key, mock_person_response):
        """Test person data is correctly mapped to Contact model."""
        service = ApolloService(api_key=mock_apollo_api_key)
        
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_person_response
        
        with patch.object(service.client, 'post', return_value=mock_response):
            contact = await service.enrich_contact(email="john@example.com")
            
            # Verify all fields mapped correctly
            assert contact.email == "john.doe@example.com"
            assert contact.first_name == "John"
            assert contact.last_name == "Doe"
            assert contact.title == "VP of Engineering"
            assert contact.company == "Example Corp"
            assert contact.phone == "+1-555-0123"
            assert contact.linkedin_url == "https://linkedin.com/in/johndoe"
            assert contact.source_platform == "apollo"
            
            # Verify custom fields
            assert "headline" in contact.custom_fields
            assert "email_status" in contact.custom_fields
            assert "employment_history" in contact.custom_fields
            assert len(contact.custom_fields["employment_history"]) <= 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
