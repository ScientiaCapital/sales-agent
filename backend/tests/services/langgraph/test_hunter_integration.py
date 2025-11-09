import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.langgraph.agents.qualification_agent import QualificationAgent


@pytest.mark.asyncio
async def test_qualification_hunter_fallback():
    """Test Hunter.io triggered when website scraping fails"""
    agent = QualificationAgent()

    # Mock email extractor to return no emails (scraping fails)
    agent.email_extractor.extract_emails = AsyncMock(return_value=[])

    # Mock hunter service to return high-confidence email
    agent.hunter_service.find_email = AsyncMock(return_value={
        "email": "sales@example.com",
        "score": 92,
        "sources": [],
        "cost": 0.01
    })

    result, latency_ms, metadata = await agent.qualify(
        company_name="Example Inc",
        company_website="https://example.com",
        contact_email=None  # No email provided
    )

    # Verify Hunter.io was called
    agent.hunter_service.find_email.assert_called_once_with("example.com")

    # Verify email was discovered
    assert metadata["extracted_email"] == "sales@example.com"
    assert metadata["extraction_method"] == "hunter"
    assert metadata["hunter_cost_usd"] == 0.01
