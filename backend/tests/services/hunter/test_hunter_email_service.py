"""
Tests for Hunter.io Email Discovery Service

Tests the HunterEmailService class which uses Hunter.io API for:
1. Domain search - find all contacts at a company domain (find_emails)
2. Email finder - find email for a specific person (find_email)

Uses respx for async HTTP mocking following project patterns.
"""

import pytest
import os
import httpx
import respx
from app.services.hunter_email_service import (
    HunterEmailService,
    HunterContact,
    HunterResult,
    HunterEmailFinderResult,
    get_hunter_service,
)


# ==============================================================================
# Fixtures
# ==============================================================================

@pytest.fixture
def hunter_service():
    """Create a fresh HunterEmailService instance with test API key"""
    os.environ["HUNTER_API_KEY"] = "test_key_123"
    return HunterEmailService()


@pytest.fixture
def hunter_service_no_key():
    """Create HunterEmailService without API key"""
    if "HUNTER_API_KEY" in os.environ:
        del os.environ["HUNTER_API_KEY"]
    return HunterEmailService()


# ==============================================================================
# Initialization Tests
# ==============================================================================

def test_hunter_email_service_initialization():
    """Test HunterEmailService initializes with API key from environment"""
    os.environ["HUNTER_API_KEY"] = "test_api_key_456"

    service = HunterEmailService()

    assert service.api_key == "test_api_key_456"
    assert service.base_url == "https://api.hunter.io/v2"
    assert service.timeout == 5.0


def test_hunter_email_service_missing_api_key():
    """Test HunterEmailService handles missing API key gracefully"""
    if "HUNTER_API_KEY" in os.environ:
        del os.environ["HUNTER_API_KEY"]

    service = HunterEmailService()

    assert service.api_key is None


def test_atl_keywords_defined():
    """Test ATL keywords are properly defined"""
    service = HunterEmailService()

    assert "ceo" in service.ATL_KEYWORDS
    assert "vp" in service.ATL_KEYWORDS
    assert "director" in service.ATL_KEYWORDS
    assert "owner" in service.ATL_KEYWORDS
    assert len(service.ATL_KEYWORDS) >= 10  # Should have at least 10 keywords


# ==============================================================================
# Domain Search (find_emails) Tests
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_find_emails_success(hunter_service):
    """Test successful domain search with ATL contacts"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "domain": "techcorp.com",
                    "emails": [
                        {
                            "value": "john.smith@techcorp.com",
                            "first_name": "John",
                            "last_name": "Smith",
                            "position": "CEO",
                            "department": "executive",
                            "confidence": 95
                        },
                        {
                            "value": "jane.doe@techcorp.com",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "position": "VP Sales",
                            "department": "sales",
                            "confidence": 90
                        }
                    ]
                }
            }
        )
    )

    result = await hunter_service.find_emails("techcorp.com", atl_only=True)

    assert result.status == "success"
    assert result.domain == "techcorp.com"
    assert len(result.contacts) == 2
    assert result.contacts[0].email == "john.smith@techcorp.com"
    assert result.contacts[0].first_name == "John"
    assert result.contacts[0].position == "CEO"
    assert result.contacts[0].confidence == 95


@pytest.mark.asyncio
@respx.mock
async def test_find_emails_atl_filtering(hunter_service):
    """Test ATL filtering excludes non-ATL contacts"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "domain": "example.com",
                    "emails": [
                        {
                            "value": "ceo@example.com",
                            "first_name": "Alice",
                            "last_name": "Boss",
                            "position": "CEO",
                            "confidence": 95
                        },
                        {
                            "value": "developer@example.com",
                            "first_name": "Bob",
                            "last_name": "Coder",
                            "position": "Software Developer",  # Not ATL
                            "confidence": 90
                        },
                        {
                            "value": "support@example.com",
                            "first_name": "Carol",
                            "last_name": "Helper",
                            "position": "Customer Support",  # Not ATL
                            "confidence": 85
                        }
                    ]
                }
            }
        )
    )

    result = await hunter_service.find_emails("example.com", atl_only=True)

    assert result.status == "success"
    assert len(result.contacts) == 1  # Only CEO passes ATL filter
    assert result.contacts[0].email == "ceo@example.com"


@pytest.mark.asyncio
@respx.mock
async def test_find_emails_no_atl_filtering(hunter_service):
    """Test returning all contacts when ATL filtering is disabled"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "domain": "example.com",
                    "emails": [
                        {
                            "value": "ceo@example.com",
                            "position": "CEO",
                            "confidence": 95
                        },
                        {
                            "value": "developer@example.com",
                            "position": "Developer",
                            "confidence": 90
                        }
                    ]
                }
            }
        )
    )

    result = await hunter_service.find_emails("example.com", atl_only=False)

    assert result.status == "success"
    assert len(result.contacts) == 2  # Both contacts returned


@pytest.mark.asyncio
@respx.mock
async def test_find_emails_rate_limited(hunter_service):
    """Test handling 429 rate limit response"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(429, json={"errors": [{"id": "rate_limit"}]})
    )

    result = await hunter_service.find_emails("example.com")

    assert result.status == "rate_limited"
    assert result.domain == "example.com"
    assert len(result.contacts) == 0
    assert "rate limit" in result.error_message.lower()


@pytest.mark.asyncio
@respx.mock
async def test_find_emails_api_error(hunter_service):
    """Test handling HTTP 500 error"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(500, json={"error": "Internal Server Error"})
    )

    result = await hunter_service.find_emails("example.com")

    assert result.status == "error"
    assert "500" in result.error_message


@pytest.mark.asyncio
@respx.mock
async def test_find_emails_timeout(hunter_service):
    """Test handling request timeout"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        side_effect=httpx.TimeoutException("Connection timeout")
    )

    result = await hunter_service.find_emails("example.com")

    assert result.status == "error"
    assert "timeout" in result.error_message.lower()


@pytest.mark.asyncio
async def test_find_emails_missing_api_key(hunter_service_no_key):
    """Test find_emails returns error when API key is missing"""
    result = await hunter_service_no_key.find_emails("example.com")

    assert result.status == "error"
    assert "not configured" in result.error_message.lower()
    assert len(result.contacts) == 0


@pytest.mark.asyncio
@respx.mock
async def test_find_emails_empty_results(hunter_service):
    """Test handling domain with no emails"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "domain": "newstartup.com",
                    "emails": []
                }
            }
        )
    )

    result = await hunter_service.find_emails("newstartup.com")

    assert result.status == "success"
    assert len(result.contacts) == 0
    assert result.total_emails == 0


@pytest.mark.asyncio
@respx.mock
async def test_find_emails_domain_cleaning(hunter_service):
    """Test domain is cleaned from URL format"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(
            200,
            json={"data": {"domain": "example.com", "emails": []}}
        )
    )

    # Test with full URL
    result = await hunter_service.find_emails("https://www.example.com/about")

    assert result.domain == "www.example.com"
    assert result.status == "success"


# ==============================================================================
# Email Finder (find_email) Tests
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_find_email_success(hunter_service):
    """Test successful email lookup for a specific person"""
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "email": "john.smith@acme.com",
                    "score": 92,
                    "first_name": "John",
                    "last_name": "Smith",
                    "domain": "acme.com"
                }
            }
        )
    )

    result = await hunter_service.find_email("John", "Smith", "acme.com")

    assert result.status == "success"
    assert result.email == "john.smith@acme.com"
    assert result.first_name == "John"
    assert result.last_name == "Smith"
    assert result.domain == "acme.com"
    assert result.confidence == 92


@pytest.mark.asyncio
@respx.mock
async def test_find_email_not_found(hunter_service):
    """Test when no email can be found for a person"""
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {}  # Empty data means not found
            }
        )
    )

    result = await hunter_service.find_email("John", "Doe", "unknowncompany.com")

    assert result.status == "not_found"
    assert result.email is None
    assert result.first_name == "John"
    assert result.last_name == "Doe"


@pytest.mark.asyncio
@respx.mock
async def test_find_email_rate_limited(hunter_service):
    """Test handling 429 rate limit for email finder"""
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        return_value=httpx.Response(429, json={"errors": [{"id": "rate_limit"}]})
    )

    result = await hunter_service.find_email("John", "Smith", "example.com")

    assert result.status == "rate_limited"
    assert result.email is None
    assert "rate limit" in result.error_message.lower()


@pytest.mark.asyncio
@respx.mock
async def test_find_email_api_error(hunter_service):
    """Test handling HTTP error for email finder"""
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        return_value=httpx.Response(403, json={"error": "Forbidden"})
    )

    result = await hunter_service.find_email("John", "Smith", "example.com")

    assert result.status == "error"
    assert "403" in result.error_message


@pytest.mark.asyncio
@respx.mock
async def test_find_email_timeout(hunter_service):
    """Test handling timeout for email finder"""
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        side_effect=httpx.TimeoutException("Request timeout")
    )

    result = await hunter_service.find_email("John", "Smith", "example.com")

    assert result.status == "error"
    assert "timeout" in result.error_message.lower()


@pytest.mark.asyncio
async def test_find_email_missing_api_key(hunter_service_no_key):
    """Test find_email returns error when API key is missing"""
    result = await hunter_service_no_key.find_email("John", "Smith", "example.com")

    assert result.status == "error"
    assert "not configured" in result.error_message.lower()


@pytest.mark.asyncio
@respx.mock
async def test_find_email_domain_cleaning(hunter_service):
    """Test domain is cleaned from URL format for email finder"""
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "email": "john@example.com",
                    "score": 85
                }
            }
        )
    )

    # Test with full URL including path
    result = await hunter_service.find_email(
        "John", "Doe", "https://www.example.com/contact"
    )

    assert result.status == "success"
    assert result.domain == "www.example.com"


# ==============================================================================
# ATL Title Detection Tests
# ==============================================================================

def test_is_atl_title_ceo(hunter_service):
    """Test CEO is recognized as ATL"""
    assert hunter_service._is_atl_title("CEO") is True
    assert hunter_service._is_atl_title("Chief Executive Officer") is True
    assert hunter_service._is_atl_title("ceo") is True


def test_is_atl_title_vp(hunter_service):
    """Test VP variations are recognized as ATL"""
    assert hunter_service._is_atl_title("VP Sales") is True
    assert hunter_service._is_atl_title("Vice President of Engineering") is True
    assert hunter_service._is_atl_title("VP") is True


def test_is_atl_title_director(hunter_service):
    """Test Director is recognized as ATL"""
    assert hunter_service._is_atl_title("Director of Sales") is True
    assert hunter_service._is_atl_title("IT Director") is True
    assert hunter_service._is_atl_title("Director") is True


def test_is_atl_title_owner(hunter_service):
    """Test Owner/Founder variations are recognized as ATL"""
    assert hunter_service._is_atl_title("Owner") is True
    assert hunter_service._is_atl_title("Founder") is True
    assert hunter_service._is_atl_title("Co-founder") is True
    assert hunter_service._is_atl_title("Co-Founder and CEO") is True


def test_is_atl_title_president(hunter_service):
    """Test President is recognized as ATL"""
    assert hunter_service._is_atl_title("President") is True
    assert hunter_service._is_atl_title("President & CEO") is True


def test_is_atl_title_not_atl(hunter_service):
    """Test non-ATL titles are correctly rejected"""
    assert hunter_service._is_atl_title("Software Developer") is False
    assert hunter_service._is_atl_title("Customer Support") is False
    assert hunter_service._is_atl_title("Sales Representative") is False
    assert hunter_service._is_atl_title("Project Manager") is False
    assert hunter_service._is_atl_title("Accountant") is False


def test_is_atl_title_empty(hunter_service):
    """Test empty/None titles return False"""
    assert hunter_service._is_atl_title("") is False
    assert hunter_service._is_atl_title(None) is False


# ==============================================================================
# Singleton Pattern Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_get_hunter_service_singleton():
    """Test get_hunter_service returns singleton instance"""
    os.environ["HUNTER_API_KEY"] = "test_key_singleton"

    # Reset singleton for test
    import app.services.hunter_email_service as hes
    hes._hunter_service = None

    service1 = await get_hunter_service()
    service2 = await get_hunter_service()

    assert service1 is service2  # Same instance


@pytest.mark.asyncio
async def test_get_hunter_service_creates_instance():
    """Test get_hunter_service creates new instance if none exists"""
    os.environ["HUNTER_API_KEY"] = "test_key_create"

    # Reset singleton
    import app.services.hunter_email_service as hes
    hes._hunter_service = None

    service = await get_hunter_service()

    assert service is not None
    assert isinstance(service, HunterEmailService)


# ==============================================================================
# Pydantic Model Tests
# ==============================================================================

def test_hunter_contact_model():
    """Test HunterContact Pydantic model validation"""
    contact = HunterContact(
        email="test@example.com",
        first_name="John",
        last_name="Doe",
        position="CEO",
        department="Executive",
        confidence=95
    )

    assert contact.email == "test@example.com"
    assert contact.source == "hunter"  # Default value
    assert contact.confidence == 95


def test_hunter_result_model():
    """Test HunterResult Pydantic model"""
    result = HunterResult(
        domain="example.com",
        contacts=[],
        total_emails=0,
        status="success"
    )

    assert result.domain == "example.com"
    assert result.status == "success"
    assert result.error_message is None


def test_hunter_email_finder_result_model():
    """Test HunterEmailFinderResult Pydantic model"""
    result = HunterEmailFinderResult(
        email="john@example.com",
        first_name="John",
        last_name="Doe",
        domain="example.com",
        confidence=90,
        status="success"
    )

    assert result.email == "john@example.com"
    assert result.confidence == 90
    assert result.status == "success"


def test_hunter_email_finder_result_not_found():
    """Test HunterEmailFinderResult for not found case"""
    result = HunterEmailFinderResult(
        first_name="Unknown",
        last_name="Person",
        domain="mystery.com",
        confidence=0,
        status="not_found",
        error_message="No email found"
    )

    assert result.email is None
    assert result.status == "not_found"
    assert result.confidence == 0
