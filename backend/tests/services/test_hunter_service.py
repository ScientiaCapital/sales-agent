import pytest
import os
from app.services.hunter_service import HunterService


def test_hunter_service_initialization():
    """Test HunterService initializes with API key from environment"""
    # Set test API key
    os.environ["HUNTER_API_KEY"] = "test_key_123"

    service = HunterService()

    assert service.api_key == "test_key_123"
    assert service.base_url == "https://api.hunter.io/v2"
    assert service.timeout == 10
