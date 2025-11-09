import pytest
import os
import httpx
import respx
from app.services.hunter_service import HunterService


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
