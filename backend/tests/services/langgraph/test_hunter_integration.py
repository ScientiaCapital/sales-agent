import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.services.website_validator import WebsiteValidationResult


@pytest.fixture(autouse=True)
async def cleanup_redis():
    """Cleanup Redis connections after each test to avoid event loop issues."""
    yield
    # Give time for async cleanup
    await pytest.importorskip("asyncio").sleep(0.1)


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.qualification_agent.QualificationAgent._initialize_llm')
@patch('app.services.langgraph.agents.qualification_agent.get_website_validator')
async def test_qualification_hunter_fallback(mock_get_validator, mock_init_llm):
    """Test Hunter.io triggered when website scraping fails"""
    # Mock LLM
    mock_llm = MagicMock()
    mock_init_llm.return_value = mock_llm

    # Mock website validator
    mock_validator = AsyncMock()
    mock_validator.validate = AsyncMock(return_value=WebsiteValidationResult(
        is_valid=True,
        status_code=200,
        response_time_ms=100,
        has_team_page=False,
        has_about_page=False,
        has_contact_page=False,
        team_page_url=None,
        about_page_url=None,
        contact_page_url=None,
        atl_contacts=[]
    ))
    mock_get_validator.return_value = mock_validator

    agent = QualificationAgent()

    # Mock cache to prevent Redis connection
    mock_cache = AsyncMock()
    mock_cache.get_qualification = AsyncMock(return_value=None)  # No cached result
    agent.cache = mock_cache

    # Mock email extractor to return no emails (scraping fails)
    agent.email_extractor.extract_emails = AsyncMock(return_value=[])

    # Mock hunter service to return high-confidence email
    agent.hunter_service.find_email = AsyncMock(return_value={
        "email": "sales@example.com",
        "score": 92,
        "sources": [],
        "cost": 0.01
    })

    # Mock LLM chain
    mock_chain_response = json.dumps({
        "qualification_score": 85,
        "qualification_reasoning": "Test qualification",
        "next_action": "Schedule meeting",
        "tier": "Tier 1",
        "fit_assessment": "Strong fit",
        "contact_quality": "High",
        "sales_potential": "High"
    })
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_chain_response)
    agent.chain = mock_chain

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


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.qualification_agent.QualificationAgent._initialize_llm')
@patch('app.services.langgraph.agents.qualification_agent.get_website_validator')
async def test_qualification_scraping_skips_hunter(mock_get_validator, mock_init_llm):
    """Verify Hunter.io NOT called when website scraping succeeds"""
    # Mock LLM
    mock_llm = MagicMock()
    mock_init_llm.return_value = mock_llm

    # Mock website validator
    mock_validator = AsyncMock()
    mock_validator.validate = AsyncMock(return_value=WebsiteValidationResult(
        is_valid=True,
        status_code=200,
        response_time_ms=100,
        has_team_page=False,
        has_about_page=False,
        has_contact_page=False,
        team_page_url=None,
        about_page_url=None,
        contact_page_url=None,
        atl_contacts=[]
    ))
    mock_get_validator.return_value = mock_validator

    agent = QualificationAgent()

    # Mock cache to prevent Redis connection
    mock_cache = AsyncMock()
    mock_cache.get_qualification = AsyncMock(return_value=None)  # No cached result
    agent.cache = mock_cache

    # Mock scraping to succeed with business email (sales@ is prioritized)
    agent.email_extractor.extract_emails = AsyncMock(
        return_value=["sales@testcompany.com", "info@testcompany.com"]
    )

    # Mock Hunter.io (should NOT be called)
    agent.hunter_service.find_email = AsyncMock(
        return_value={"email": "hunter@testcompany.com", "score": 95, "sources": [], "cost": 0.01}
    )

    # Mock LLM chain
    mock_chain_response = json.dumps({
        "qualification_score": 90,
        "qualification_reasoning": "Test qualification",
        "next_action": "Schedule meeting",
        "tier": "Tier 1",
        "fit_assessment": "Strong fit",
        "contact_quality": "High",
        "sales_potential": "High"
    })
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_chain_response)
    agent.chain = mock_chain

    # Execute qualification - use unique company to avoid cache
    result, latency_ms, metadata = await agent.qualify(
        company_name="Test Scraping Company",
        company_website="https://testcompany.com",
        contact_email=None
    )

    # Assertions - verify first prioritized email (sales@) was used
    assert metadata["extracted_email"] == "sales@testcompany.com"
    assert metadata["extraction_method"] == "scraping"
    assert metadata["hunter_cost_usd"] == 0.0
    agent.hunter_service.find_email.assert_not_called()  # KEY: Hunter.io NOT called


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.qualification_agent.QualificationAgent._initialize_llm')
@patch('app.services.langgraph.agents.qualification_agent.get_website_validator')
async def test_qualification_both_fail_gracefully(mock_get_validator, mock_init_llm):
    """Verify qualification continues when both email discovery methods fail"""
    # Mock LLM
    mock_llm = MagicMock()
    mock_init_llm.return_value = mock_llm

    # Mock website validator
    mock_validator = AsyncMock()
    mock_validator.validate = AsyncMock(return_value=WebsiteValidationResult(
        is_valid=True,
        status_code=200,
        response_time_ms=100,
        has_team_page=False,
        has_about_page=False,
        has_contact_page=False,
        team_page_url=None,
        about_page_url=None,
        contact_page_url=None,
        atl_contacts=[]
    ))
    mock_get_validator.return_value = mock_validator

    agent = QualificationAgent()

    # Mock cache to prevent Redis connection
    mock_cache = AsyncMock()
    mock_cache.get_qualification = AsyncMock(return_value=None)  # No cached result
    agent.cache = mock_cache

    # Mock email extractor to fail (returns empty list)
    agent.email_extractor.extract_emails = AsyncMock(return_value=[])

    # Mock Hunter.io to fail (returns None)
    agent.hunter_service.find_email = AsyncMock(return_value=None)

    # Mock LLM chain
    mock_chain_response = json.dumps({
        "qualification_score": 75,
        "qualification_reasoning": "Test qualification despite no email discovery",
        "next_action": "Research contact information",
        "tier": "Tier 2",
        "fit_assessment": "Good fit",
        "contact_quality": "Unknown",
        "sales_potential": "Medium"
    })
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_chain_response)
    agent.chain = mock_chain

    # Execute qualification - use unique company to avoid cache
    result, latency_ms, metadata = await agent.qualify(
        company_name="Failed Discovery Inc",
        company_website="https://noemails.com",
        contact_email=None  # No email provided
    )

    # Verify both methods were attempted
    agent.email_extractor.extract_emails.assert_called_once()
    agent.hunter_service.find_email.assert_called_once_with("noemails.com")

    # Verify graceful failure handling
    assert metadata["extracted_email"] is None
    assert metadata["extraction_method"] == "none"
    assert metadata["hunter_cost_usd"] == 0.0

    # Verify qualification still completed successfully (non-blocking failure)
    assert result.qualification_score == 75
    assert result.qualification_score > 0
    assert result.tier == "Tier 2"
    assert latency_ms >= 0  # Mocked LLM doesn't measure latency, so >= 0 is expected


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.qualification_agent.QualificationAgent._initialize_llm')
@patch('app.services.langgraph.agents.qualification_agent.get_website_validator')
async def test_qualification_email_provided_skips_discovery(mock_get_validator, mock_init_llm):
    """Verify both discovery methods skipped when email already provided"""
    # Mock LLM
    mock_llm = MagicMock()
    mock_init_llm.return_value = mock_llm

    # Mock website validator
    mock_validator = AsyncMock()
    mock_validator.validate = AsyncMock(return_value=WebsiteValidationResult(
        is_valid=True,
        status_code=200,
        response_time_ms=100,
        has_team_page=False,
        has_about_page=False,
        has_contact_page=False,
        team_page_url=None,
        about_page_url=None,
        contact_page_url=None,
        atl_contacts=[]
    ))
    mock_get_validator.return_value = mock_validator

    agent = QualificationAgent()

    # Mock cache to prevent Redis connection
    mock_cache = AsyncMock()
    mock_cache.get_qualification = AsyncMock(return_value=None)  # No cached result
    agent.cache = mock_cache

    # Mock scraping (should NOT be called)
    agent.email_extractor.extract_emails = AsyncMock(
        return_value=["should-not@becalled.com"]
    )

    # Mock Hunter.io (should NOT be called)
    agent.hunter_service.find_email = AsyncMock(
        return_value={"email": "should-not@becalled.com", "score": 95, "sources": [], "cost": 0.01}
    )

    # Mock LLM chain
    mock_chain_response = json.dumps({
        "qualification_score": 88,
        "qualification_reasoning": "Email already provided - no discovery needed",
        "next_action": "Send outreach email",
        "tier": "Tier 1",
        "fit_assessment": "Strong fit",
        "contact_quality": "High",
        "sales_potential": "High"
    })
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_chain_response)
    agent.chain = mock_chain

    # Execute qualification WITH email provided
    result, latency_ms, metadata = await agent.qualify(
        company_name="Email Provided Inc",
        company_website="https://example.com",
        contact_email="provided@email.com"  # Email already provided
    )

    # Assertions - verify provided email is used
    assert metadata["extracted_email"] == "provided@email.com"
    assert metadata["extraction_method"] == "provided"
    assert metadata["hunter_cost_usd"] == 0.0

    # KEY: Neither discovery method should be called (optimization)
    agent.email_extractor.extract_emails.assert_not_called()
    agent.hunter_service.find_email.assert_not_called()

    # Verify qualification completed successfully
    assert result.qualification_score == 88
    assert result.tier == "Tier 1"
