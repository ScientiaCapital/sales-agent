import pytest
import os
import httpx
import respx
from app.services.hunter_service import HunterService, extract_domain


def test_hunter_service_initialization():
    """Test HunterService initializes with API key from environment"""
    # Set test API key
    os.environ["HUNTER_API_KEY"] = "test_key_123"

    service = HunterService()

    assert service.api_key == "test_key_123"
    assert service.base_url == "https://api.hunter.io/v2"
    assert service.timeout == 10


@pytest.mark.asyncio
@respx.mock
async def test_find_email_success():
    """Test successful email discovery with high confidence"""
    # Mock Hunter.io API response
    respx.get("https://api.hunter.io/v2/email-finder").mock(return_value=httpx.Response(
        200,
        json={
            "data": {
                "email": "john.smith@example.com",
                "score": 95,
                "sources": [
                    {"uri": "https://example.com/about", "extracted_on": "2024-01-15"}
                ]
            }
        }
    ))

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.find_email("example.com")

    assert result is not None
    assert result["email"] == "john.smith@example.com"
    assert result["score"] == 95
    assert result["cost"] == 0.01
    assert len(result["sources"]) > 0


@pytest.mark.asyncio
@respx.mock
async def test_find_email_low_confidence():
    """Test filtering out low-confidence results (score <= 70)"""
    # Mock Hunter.io returning low confidence result
    respx.get("https://api.hunter.io/v2/email-finder").mock(return_value=httpx.Response(
        200,
        json={
            "data": {
                "email": "generic@example.com",
                "score": 50,  # Low confidence
                "sources": []
            }
        }
    ))

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.find_email("example.com")

    # Should filter out low confidence results
    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_find_email_api_404():
    """Test handling 404 (domain not found)"""
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        return_value=httpx.Response(404, json={"errors": [{"id": "not_found"}]})
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.find_email("nonexistent.com")

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_find_email_api_429():
    """Test handling 429 (rate limit exceeded)"""
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        return_value=httpx.Response(429, json={"errors": [{"id": "rate_limit"}]})
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.find_email("example.com")

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_find_email_timeout():
    """Test handling connection timeout"""
    respx.get("https://api.hunter.io/v2/email-finder").mock(
        side_effect=httpx.TimeoutException("Request timeout")
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.find_email("example.com")

    assert result is None


@pytest.mark.asyncio
async def test_find_email_missing_api_key():
    """Test handling missing API key"""
    # Ensure HUNTER_API_KEY is not set
    if "HUNTER_API_KEY" in os.environ:
        del os.environ["HUNTER_API_KEY"]

    service = HunterService()

    result = await service.find_email("example.com")

    assert result is None


def test_extract_domain_with_https():
    """Test extracting domain from HTTPS URL"""
    assert extract_domain("https://example.com") == "example.com"


def test_extract_domain_with_http():
    """Test extracting domain from HTTP URL"""
    assert extract_domain("http://example.com") == "example.com"


def test_extract_domain_with_path():
    """Test extracting domain from URL with path"""
    assert extract_domain("https://www.example.com/about") == "www.example.com"


def test_extract_domain_with_subdomain():
    """Test extracting domain with subdomain"""
    assert extract_domain("https://blog.example.com") == "blog.example.com"


def test_extract_domain_plain():
    """Test extracting plain domain (no protocol)"""
    assert extract_domain("example.com") == "example.com"


# ==============================================================================
# Email Verification Tests (verify_email)
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_verify_email_valid():
    """Test verifying a valid email address"""
    respx.get("https://api.hunter.io/v2/email-verifier").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "email": "john@example.com",
                    "status": "valid",
                    "score": 100,
                    "disposable": False,
                    "webmail": False,
                    "mx_records": True,
                    "smtp_check": True
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.verify_email("john@example.com")

    assert result is not None
    assert result["email"] == "john@example.com"
    assert result["status"] == "valid"
    assert result["score"] == 100
    assert result["is_deliverable"] is True
    assert result["is_disposable"] is False
    assert result["is_webmail"] is False
    assert result["cost"] == 0.01


@pytest.mark.asyncio
@respx.mock
async def test_verify_email_invalid():
    """Test verifying an invalid email address"""
    respx.get("https://api.hunter.io/v2/email-verifier").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "email": "invalid@nonexistent.com",
                    "status": "invalid",
                    "score": 0,
                    "disposable": False,
                    "webmail": False,
                    "mx_records": False,
                    "smtp_check": False
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.verify_email("invalid@nonexistent.com")

    assert result is not None
    assert result["status"] == "invalid"
    assert result["is_deliverable"] is False


@pytest.mark.asyncio
@respx.mock
async def test_verify_email_accept_all():
    """Test verifying an accept_all email with high score (deliverable)"""
    respx.get("https://api.hunter.io/v2/email-verifier").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "email": "contact@catchall.com",
                    "status": "accept_all",
                    "score": 85,
                    "disposable": False,
                    "webmail": False,
                    "mx_records": True,
                    "smtp_check": True
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.verify_email("contact@catchall.com")

    assert result is not None
    assert result["status"] == "accept_all"
    assert result["is_deliverable"] is True  # accept_all with score >= 70 is deliverable


@pytest.mark.asyncio
@respx.mock
async def test_verify_email_accept_all_low_score():
    """Test verifying an accept_all email with low score (not deliverable)"""
    respx.get("https://api.hunter.io/v2/email-verifier").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "email": "risky@catchall.com",
                    "status": "accept_all",
                    "score": 50,
                    "disposable": False,
                    "webmail": False,
                    "mx_records": True,
                    "smtp_check": False
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.verify_email("risky@catchall.com")

    assert result is not None
    assert result["status"] == "accept_all"
    assert result["is_deliverable"] is False  # accept_all with score < 70 is not deliverable


@pytest.mark.asyncio
@respx.mock
async def test_verify_email_in_progress():
    """Test handling 202 (verification in progress)"""
    respx.get("https://api.hunter.io/v2/email-verifier").mock(
        return_value=httpx.Response(202, json={"data": {}})
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.verify_email("pending@example.com")

    assert result is None  # Returns None for in-progress verification


@pytest.mark.asyncio
@respx.mock
async def test_verify_email_rate_limited():
    """Test handling 429 (rate limit exceeded)"""
    respx.get("https://api.hunter.io/v2/email-verifier").mock(
        return_value=httpx.Response(429, json={"errors": [{"id": "rate_limit"}]})
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.verify_email("test@example.com")

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_verify_email_timeout():
    """Test handling verification timeout"""
    respx.get("https://api.hunter.io/v2/email-verifier").mock(
        side_effect=httpx.TimeoutException("Request timeout")
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.verify_email("test@example.com")

    assert result is None


@pytest.mark.asyncio
async def test_verify_email_missing_api_key():
    """Test verification with missing API key"""
    if "HUNTER_API_KEY" in os.environ:
        del os.environ["HUNTER_API_KEY"]

    service = HunterService()

    result = await service.verify_email("test@example.com")

    assert result is None


@pytest.mark.asyncio
async def test_verify_email_invalid_format():
    """Test verification with invalid email format"""
    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    # Test empty string
    result = await service.verify_email("")
    assert result is None

    # Test no @ symbol
    result = await service.verify_email("invalid-email")
    assert result is None


# ==============================================================================
# Email Count Tests (get_email_count) - FREE ENDPOINT
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_get_email_count_success():
    """Test getting email count for a domain (FREE endpoint)"""
    respx.get("https://api.hunter.io/v2/email-count").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "total": 81,
                    "personal_emails": 65,
                    "generic_emails": 16
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.get_email_count("example.com")

    assert result is not None
    assert result["total"] == 81
    assert result["personal_emails"] == 65
    assert result["generic_emails"] == 16
    assert result["has_data"] is True


@pytest.mark.asyncio
@respx.mock
async def test_get_email_count_no_emails():
    """Test email count for domain with no emails"""
    respx.get("https://api.hunter.io/v2/email-count").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "total": 0,
                    "personal_emails": 0,
                    "generic_emails": 0
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.get_email_count("newstartup.com")

    assert result is not None
    assert result["total"] == 0
    assert result["has_data"] is False


@pytest.mark.asyncio
@respx.mock
async def test_get_email_count_domain_cleaning():
    """Test domain is cleaned from URL format"""
    respx.get("https://api.hunter.io/v2/email-count").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "total": 50,
                    "personal_emails": 40,
                    "generic_emails": 10
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    # Test with full URL including protocol and path
    result = await service.get_email_count("https://www.example.com/about")

    assert result is not None
    assert result["total"] == 50
    assert result["has_data"] is True


@pytest.mark.asyncio
@respx.mock
async def test_get_email_count_api_error():
    """Test handling API error for email count"""
    respx.get("https://api.hunter.io/v2/email-count").mock(
        return_value=httpx.Response(500, json={"error": "Internal Server Error"})
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.get_email_count("example.com")

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_get_email_count_timeout():
    """Test handling timeout for email count"""
    respx.get("https://api.hunter.io/v2/email-count").mock(
        side_effect=httpx.TimeoutException("Request timeout")
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.get_email_count("example.com")

    assert result is None


@pytest.mark.asyncio
async def test_get_email_count_missing_api_key():
    """Test email count with missing API key"""
    if "HUNTER_API_KEY" in os.environ:
        del os.environ["HUNTER_API_KEY"]

    service = HunterService()

    result = await service.get_email_count("example.com")

    assert result is None


# ==============================================================================
# Domain Search Tests (domain_search)
# ==============================================================================

@pytest.mark.asyncio
@respx.mock
async def test_domain_search_success():
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
                            "confidence": 95,
                            "phone_number": "+1-555-0100",
                            "linkedin": "https://linkedin.com/in/johnsmith",
                            "twitter": "@johnsmith",
                            "seniority": "executive",
                            "type": "personal",
                            "verification": {"status": "valid"}
                        },
                        {
                            "value": "jane.doe@techcorp.com",
                            "first_name": "Jane",
                            "last_name": "Doe",
                            "position": "Software Developer",
                            "department": "engineering",
                            "confidence": 90
                        }
                    ]
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.domain_search("techcorp.com", atl_only=True)

    assert result is not None
    assert len(result) == 1  # Only CEO passes ATL filter
    assert result[0]["email"] == "john.smith@techcorp.com"
    assert result[0]["first_name"] == "John"
    assert result[0]["position"] == "CEO"
    assert result[0]["is_atl"] is True
    assert result[0]["phone_number"] == "+1-555-0100"
    assert result[0]["linkedin"] == "https://linkedin.com/in/johnsmith"


@pytest.mark.asyncio
@respx.mock
async def test_domain_search_all_contacts():
    """Test domain search returning all contacts when ATL filter is off"""
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

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.domain_search("example.com", atl_only=False)

    assert result is not None
    assert len(result) == 2  # Both contacts returned


@pytest.mark.asyncio
@respx.mock
async def test_domain_search_rate_limited():
    """Test handling 429 rate limit for domain search"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(429, json={"errors": [{"id": "rate_limit"}]})
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.domain_search("example.com")

    assert result is None


@pytest.mark.asyncio
@respx.mock
async def test_domain_search_no_atl_contacts():
    """Test domain search with no ATL contacts returns None"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "domain": "example.com",
                    "emails": [
                        {
                            "value": "developer@example.com",
                            "position": "Developer",
                            "confidence": 90
                        },
                        {
                            "value": "support@example.com",
                            "position": "Customer Support",
                            "confidence": 85
                        }
                    ]
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    result = await service.domain_search("example.com", atl_only=True)

    assert result is None  # No ATL contacts found


@pytest.mark.asyncio
@respx.mock
async def test_domain_search_null_position():
    """Test domain search handles null position gracefully"""
    respx.get("https://api.hunter.io/v2/domain-search").mock(
        return_value=httpx.Response(
            200,
            json={
                "data": {
                    "domain": "example.com",
                    "emails": [
                        {
                            "value": "unknown@example.com",
                            "first_name": "Unknown",
                            "last_name": "Person",
                            "position": None,  # Null position
                            "confidence": 90
                        }
                    ]
                }
            }
        )
    )

    os.environ["HUNTER_API_KEY"] = "test_key_123"
    service = HunterService()

    # Should not raise an error with None position
    result = await service.domain_search("example.com", atl_only=False)

    assert result is not None
    assert len(result) == 1
    assert result[0]["is_atl"] is False  # Null position is not ATL
