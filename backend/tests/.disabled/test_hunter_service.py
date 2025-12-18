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
