"""
HubSpot CRM Integration Tests

Comprehensive test suite for HubSpot OAuth, contact operations, sync, and webhooks.
Target: 95%+ code coverage
"""

import pytest
import httpx
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timedelta
import hashlib
import hmac
import json

from app.services.crm.hubspot import HubSpotProvider
from app.services.crm.base import (
    CRMCredentials,
    Contact,
    SyncResult,
    WebhookEvent,
    CRMAuthenticationError,
    CRMRateLimitError,
    CRMNotFoundError,
    CRMValidationError,
    CRMWebhookError,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def hubspot_credentials():
    """Create test HubSpot credentials with encrypted tokens."""
    from app.services.crm.base import CredentialEncryption

    # Generate encrypted test tokens
    access_token_encrypted = CredentialEncryption.encrypt_credential("test_access_token")
    refresh_token_encrypted = CredentialEncryption.encrypt_credential("test_refresh_token")

    return CRMCredentials(
        platform="hubspot",
        user_id=1,
        access_token=access_token_encrypted,
        refresh_token=refresh_token_encrypted,
        token_expires_at=datetime.utcnow() + timedelta(hours=6)
    )


@pytest.fixture
def hubspot_provider(hubspot_credentials):
    """Create HubSpot provider instance."""
    return HubSpotProvider(
        credentials=hubspot_credentials,
        client_id="test_client_id",
        client_secret="test_client_secret",
        redirect_uri="http://localhost:8001/callback",
        redis_client=None
    )


@pytest.fixture
def mock_redis():
    """Create mock Redis client."""
    redis = AsyncMock()
    redis.incr = AsyncMock(return_value=1)
    redis.expire = AsyncMock()
    redis.get = AsyncMock(return_value=0)
    redis.ttl = AsyncMock(return_value=10)
    return redis


@pytest.fixture
def sample_contact():
    """Create sample contact data."""
    return Contact(
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        company="Test Corp",
        title="CTO",
        phone="+1234567890",
        linkedin_url="https://linkedin.com/in/johndoe"
    )


@pytest.fixture
def hubspot_contact_response():
    """Mock HubSpot API contact response."""
    return {
        "id": "12345",
        "properties": {
            "email": "test@example.com",
            "firstname": "John",
            "lastname": "Doe",
            "company": "Test Corp",
            "jobtitle": "CTO",
            "phone": "+1234567890",
            "hs_linkedinid": "johndoe",
            "createdate": "2024-01-01T00:00:00Z",
            "lastmodifieddate": "2024-01-15T00:00:00Z"
        }
    }


# ============================================================================
# OAUTH 2.0 TESTS
# ============================================================================

class TestOAuth:
    """Test OAuth 2.0 authentication flow."""
    
    def test_generate_authorization_url(self, hubspot_provider):
        """Test OAuth authorization URL generation with PKCE."""
        scopes = ["crm.objects.contacts.read", "oauth"]
        auth_url, code_verifier = hubspot_provider.generate_authorization_url(scopes)
        
        # Verify URL structure
        assert "app.hubspot.com/oauth/authorize" in auth_url
        assert "client_id=test_client_id" in auth_url
        assert "scope=crm.objects.contacts.read+oauth" in auth_url
        assert "code_challenge" in auth_url
        assert "code_challenge_method=S256" in auth_url
        assert "state=" in auth_url
        
        # Verify PKCE verifier
        assert len(code_verifier) > 0
        assert isinstance(code_verifier, str)
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_success(self, hubspot_provider):
        """Test successful token exchange."""
        token_response = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_in": 21600
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = token_response
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            result = await hubspot_provider.exchange_code_for_token(
                "auth_code",
                "code_verifier"
            )
            
            assert result["access_token"] == "new_access_token"
            assert result["refresh_token"] == "new_refresh_token"
            assert result["expires_in"] == 21600
            assert hubspot_provider.access_token == "new_access_token"
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_token_failure(self, hubspot_provider):
        """Test token exchange failure."""
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 400
            mock_response.text = "Invalid authorization code"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Bad Request",
                request=Mock(),
                response=mock_response
            )
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(CRMAuthenticationError) as exc_info:
                await hubspot_provider.exchange_code_for_token("bad_code", "verifier")
            
            assert "token exchange failed" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_authenticate_success(self, hubspot_provider):
        """Test successful authentication verification."""
        hubspot_provider.access_token = "valid_token"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = {"results": []}
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            result = await hubspot_provider.authenticate()
            assert result is True
    
    @pytest.mark.asyncio
    async def test_authenticate_no_token(self, hubspot_provider):
        """Test authentication failure with no token."""
        hubspot_provider.access_token = None
        
        with pytest.raises(CRMAuthenticationError) as exc_info:
            await hubspot_provider.authenticate()
        
        assert "no access token" in str(exc_info.value).lower()
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_success(self, hubspot_provider):
        """Test successful token refresh."""
        token_response = {
            "access_token": "refreshed_token",
            "expires_in": 21600
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = token_response
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            new_token = await hubspot_provider.refresh_access_token()
            
            assert new_token == "refreshed_token"
            assert hubspot_provider.access_token == "refreshed_token"
    
    @pytest.mark.asyncio
    async def test_refresh_access_token_no_refresh_token(self):
        """Test refresh failure with no refresh token."""
        credentials = CRMCredentials(platform="hubspot", user_id=1)
        provider = HubSpotProvider(
            credentials,
            "client_id",
            "client_secret",
            "redirect_uri"
        )
        
        with pytest.raises(CRMAuthenticationError) as exc_info:
            await provider.refresh_access_token()
        
        assert "no refresh token" in str(exc_info.value).lower()


# ============================================================================
# CONTACT OPERATIONS TESTS
# ============================================================================

class TestContactOperations:
    """Test contact CRUD operations."""
    
    def test_map_hubspot_to_contact(self, hubspot_provider, hubspot_contact_response):
        """Test mapping HubSpot response to Contact model."""
        contact = hubspot_provider._map_hubspot_to_contact(hubspot_contact_response)
        
        assert contact.email == "test@example.com"
        assert contact.first_name == "John"
        assert contact.last_name == "Doe"
        assert contact.company == "Test Corp"
        assert contact.title == "CTO"
        assert contact.phone == "+1234567890"
        assert contact.linkedin_url == "https://linkedin.com/in/johndoe"
        assert contact.external_ids["hubspot"] == "12345"
        assert contact.source_platform == "hubspot"
    
    def test_map_contact_to_hubspot(self, hubspot_provider, sample_contact):
        """Test mapping Contact model to HubSpot format."""
        hubspot_data = hubspot_provider._map_contact_to_hubspot(sample_contact)
        
        props = hubspot_data["properties"]
        assert props["email"] == "test@example.com"
        assert props["firstname"] == "John"
        assert props["lastname"] == "Doe"
        assert props["company"] == "Test Corp"
        assert props["jobtitle"] == "CTO"
        assert props["phone"] == "+1234567890"
        assert props["hs_linkedinid"] == "johndoe"
    
    def test_linkedin_url_extraction(self, hubspot_provider):
        """Test LinkedIn ID extraction from URL."""
        url = "https://linkedin.com/in/johndoe"
        linkedin_id = hubspot_provider._extract_linkedin_id(url)
        assert linkedin_id == "johndoe"
        
        url_trailing_slash = "https://linkedin.com/in/johndoe/"
        linkedin_id2 = hubspot_provider._extract_linkedin_id(url_trailing_slash)
        assert linkedin_id2 == "johndoe"
        
        invalid_url = "https://example.com"
        assert hubspot_provider._extract_linkedin_id(invalid_url) is None
    
    def test_linkedin_url_construction(self, hubspot_provider):
        """Test LinkedIn URL construction from ID."""
        linkedin_id = "johndoe"
        url = hubspot_provider._construct_linkedin_url(linkedin_id)
        assert url == "https://linkedin.com/in/johndoe"
        
        assert hubspot_provider._construct_linkedin_url(None) is None
    
    @pytest.mark.asyncio
    async def test_get_contact_success(self, hubspot_provider, hubspot_contact_response):
        """Test successful contact retrieval."""
        hubspot_provider.access_token = "valid_token"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = hubspot_contact_response
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            contact = await hubspot_provider.get_contact("12345")
            
            assert contact.email == "test@example.com"
            assert contact.first_name == "John"
    
    @pytest.mark.asyncio
    async def test_get_contact_not_found(self, hubspot_provider):
        """Test contact not found error."""
        hubspot_provider.access_token = "valid_token"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 404
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=Mock(),
                response=mock_response
            )
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(CRMNotFoundError):
                await hubspot_provider.get_contact("99999")
    
    @pytest.mark.asyncio
    async def test_create_contact_success(self, hubspot_provider, sample_contact, hubspot_contact_response):
        """Test successful contact creation."""
        hubspot_provider.access_token = "valid_token"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = hubspot_contact_response
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            created_contact = await hubspot_provider.create_contact(sample_contact)
            
            assert created_contact.email == sample_contact.email
            assert created_contact.external_ids["hubspot"] == "12345"
    
    @pytest.mark.asyncio
    async def test_create_contact_validation_error(self, hubspot_provider, sample_contact):
        """Test contact creation validation error."""
        hubspot_provider.access_token = "valid_token"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 400
            mock_response.text = "Invalid email format"
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Bad Request",
                request=Mock(),
                response=mock_response
            )
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(CRMValidationError):
                await hubspot_provider.create_contact(sample_contact)
    
    @pytest.mark.asyncio
    async def test_update_contact_success(self, hubspot_provider, sample_contact, hubspot_contact_response):
        """Test successful contact update."""
        hubspot_provider.access_token = "valid_token"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = hubspot_contact_response
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.patch = AsyncMock(
                return_value=mock_response
            )
            
            updated_contact = await hubspot_provider.update_contact("12345", sample_contact)
            
            assert updated_contact.email == sample_contact.email
    
    @pytest.mark.asyncio
    async def test_enrich_contact_not_supported(self, hubspot_provider):
        """Test that contact enrichment is not supported."""
        result = await hubspot_provider.enrich_contact("test@example.com")
        assert result is None


# ============================================================================
# SYNC OPERATIONS TESTS
# ============================================================================

class TestSyncOperations:
    """Test contact synchronization."""
    
    @pytest.mark.asyncio
    async def test_sync_contacts_import(self, hubspot_provider):
        """Test contact import from HubSpot."""
        hubspot_provider.access_token = "valid_token"
        
        mock_response_data = {
            "results": [
                {
                    "id": "1",
                    "properties": {
                        "email": "contact1@example.com",
                        "firstname": "Contact",
                        "lastname": "One"
                    }
                }
            ],
            "paging": {}
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.json.return_value = mock_response_data
            mock_response.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            result = await hubspot_provider.sync_contacts(direction="import")
            
            assert result.platform == "hubspot"
            assert result.operation == "import"
            assert result.contacts_processed >= 1
            assert result.completed_at is not None
    
    @pytest.mark.asyncio
    async def test_sync_contacts_invalid_direction(self, hubspot_provider):
        """Test sync with invalid direction."""
        result = await hubspot_provider.sync_contacts(direction="invalid")
        
        assert len(result.errors) > 0
        assert any("Invalid sync direction" in str(err) for err in result.errors)
    
    @pytest.mark.asyncio
    async def test_get_updated_contacts(self, hubspot_provider):
        """Test getting contacts updated since timestamp."""
        hubspot_provider.access_token = "valid_token"
        since = datetime.utcnow() - timedelta(days=7)
        
        mock_response = {
            "results": [
                {
                    "id": "1",
                    "properties": {
                        "email": "updated@example.com",
                        "firstname": "Updated",
                        "lastmodifieddate": datetime.utcnow().isoformat()
                    }
                }
            ]
        }
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_resp = AsyncMock()
            mock_resp.json.return_value = mock_response
            mock_resp.raise_for_status = Mock()
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_resp
            )
            
            contacts = await hubspot_provider.get_updated_contacts(since)
            
            assert len(contacts) == 1
            assert contacts[0].email == "updated@example.com"


# ============================================================================
# WEBHOOK TESTS
# ============================================================================

class TestWebhooks:
    """Test webhook handling."""
    
    @pytest.mark.asyncio
    async def test_verify_webhook_signature_success(self, hubspot_provider):
        """Test successful webhook signature verification."""
        payload = b'{"test": "data"}'
        
        # Generate valid signature
        expected_signature = hmac.new(
            hubspot_provider.client_secret.encode(),
            payload,
            hashlib.sha256
        ).hexdigest()
        
        result = await hubspot_provider.verify_webhook_signature(payload, expected_signature)
        assert result is True
    
    @pytest.mark.asyncio
    async def test_verify_webhook_signature_failure(self, hubspot_provider):
        """Test webhook signature verification failure."""
        payload = b'{"test": "data"}'
        invalid_signature = "invalid_signature_12345"
        
        with pytest.raises(CRMWebhookError):
            await hubspot_provider.verify_webhook_signature(payload, invalid_signature)
    
    @pytest.mark.asyncio
    async def test_handle_webhook_contact_creation(self, hubspot_provider):
        """Test webhook contact creation event handling."""
        event = WebhookEvent(
            platform="hubspot",
            event_type="contact.creation",
            event_id="evt_123",
            contact_id="12345",
            payload={"objectId": "12345"},
            timestamp=datetime.utcnow()
        )
        
        # Should not raise error
        await hubspot_provider.handle_webhook(event)
    
    @pytest.mark.asyncio
    async def test_handle_webhook_contact_update(self, hubspot_provider):
        """Test webhook contact update event handling."""
        event = WebhookEvent(
            platform="hubspot",
            event_type="contact.propertyChange",
            event_id="evt_124",
            contact_id="12345",
            payload={"objectId": "12345"},
            timestamp=datetime.utcnow()
        )
        
        await hubspot_provider.handle_webhook(event)
    
    @pytest.mark.asyncio
    async def test_handle_webhook_contact_deletion(self, hubspot_provider):
        """Test webhook contact deletion event handling."""
        event = WebhookEvent(
            platform="hubspot",
            event_type="contact.deletion",
            event_id="evt_125",
            contact_id="12345",
            payload={"objectId": "12345"},
            timestamp=datetime.utcnow()
        )
        
        await hubspot_provider.handle_webhook(event)


# ============================================================================
# RATE LIMITING TESTS
# ============================================================================

class TestRateLimiting:
    """Test rate limiting functionality."""
    
    @pytest.mark.asyncio
    async def test_rate_limit_10_second_window(self, hubspot_credentials, mock_redis):
        """Test 10-second rate limit enforcement."""
        provider = HubSpotProvider(
            hubspot_credentials,
            "client_id",
            "client_secret",
            "redirect_uri",
            redis_client=mock_redis
        )
        
        # First call should succeed
        await provider._check_rate_limit()
        assert mock_redis.incr.called
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_10s(self, hubspot_credentials, mock_redis):
        """Test rate limit exceeded in 10-second window."""
        mock_redis.incr = AsyncMock(return_value=101)  # Exceeds 100 limit
        
        provider = HubSpotProvider(
            hubspot_credentials,
            "client_id",
            "client_secret",
            "redirect_uri",
            redis_client=mock_redis
        )
        
        with pytest.raises(CRMRateLimitError) as exc_info:
            await provider._check_rate_limit()
        
        assert "10 seconds" in str(exc_info.value)
        assert exc_info.value.retry_after == 10
    
    @pytest.mark.asyncio
    async def test_rate_limit_exceeded_daily(self, hubspot_credentials):
        """Test daily rate limit exceeded."""
        mock_redis = AsyncMock()
        mock_redis.incr = AsyncMock(side_effect=[50, 250001])  # 10s OK, daily exceeded
        mock_redis.expire = AsyncMock()
        
        provider = HubSpotProvider(
            hubspot_credentials,
            "client_id",
            "client_secret",
            "redirect_uri",
            redis_client=mock_redis
        )
        
        with pytest.raises(CRMRateLimitError) as exc_info:
            await provider._check_rate_limit()
        
        assert "daily limit" in str(exc_info.value).lower()
        assert exc_info.value.retry_after == 86400
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_status(self, hubspot_credentials, mock_redis):
        """Test rate limit status check."""
        provider = HubSpotProvider(
            hubspot_credentials,
            "client_id",
            "client_secret",
            "redirect_uri",
            redis_client=mock_redis
        )
        
        status = await provider.check_rate_limit()
        
        assert "remaining" in status
        assert "limit" in status
        assert "reset_at" in status
        assert "retry_after" in status
        assert status["limit"] == 100
    
    @pytest.mark.asyncio
    async def test_rate_limit_without_redis(self, hubspot_provider):
        """Test rate limiting disabled without Redis."""
        # Should not raise error when Redis is None
        await hubspot_provider._check_rate_limit()
        
        status = await hubspot_provider.check_rate_limit()
        assert status["remaining"] == 100
        assert status["reset_at"] is None


# ============================================================================
# EDGE CASES AND ERROR HANDLING
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error scenarios."""
    
    def test_parse_hubspot_date_valid(self, hubspot_provider):
        """Test parsing valid HubSpot date string."""
        date_str = "2024-01-15T10:30:00Z"
        result = hubspot_provider._parse_hubspot_date(date_str)
        
        assert isinstance(result, datetime)
        assert result.year == 2024
        assert result.month == 1
    
    def test_parse_hubspot_date_invalid(self, hubspot_provider):
        """Test parsing invalid date string."""
        invalid_date = "not-a-date"
        result = hubspot_provider._parse_hubspot_date(invalid_date)
        
        assert result is None
    
    def test_parse_hubspot_date_none(self, hubspot_provider):
        """Test parsing None date."""
        result = hubspot_provider._parse_hubspot_date(None)
        assert result is None
    
    @pytest.mark.asyncio
    async def test_get_contact_rate_limit_error(self, hubspot_provider):
        """Test rate limit error during contact retrieval."""
        hubspot_provider.access_token = "valid_token"
        
        with patch('httpx.AsyncClient') as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 429
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Too Many Requests",
                request=Mock(),
                response=mock_response
            )
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )
            
            with pytest.raises(CRMRateLimitError):
                await hubspot_provider.get_contact("12345")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=app.services.crm.hubspot", "--cov-report=term-missing"])
