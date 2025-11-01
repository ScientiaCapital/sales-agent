"""Integration tests for email extraction in qualification."""
import json
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.langgraph.agents.qualification_agent import QualificationAgent


@pytest.fixture(autouse=True)
async def cleanup_redis():
    """Cleanup Redis connections after each test to avoid event loop issues."""
    yield
    # Give time for async cleanup
    await pytest.importorskip("asyncio").sleep(0.1)


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.qualification_agent.QualificationAgent._initialize_llm')
async def test_qualification_extracts_email_when_missing(mock_init_llm):
    """Test email extraction when contact_email not provided."""
    # Mock LLM initialization
    mock_llm = MagicMock()
    mock_init_llm.return_value = mock_llm

    agent = QualificationAgent()

    # Mock email extractor
    mock_extractor = AsyncMock()
    mock_extractor.extract_emails = AsyncMock(return_value=[
        'john.doe@example.com',
        'sales@example.com'
    ])
    agent.email_extractor = mock_extractor

    # Mock LLM chain to avoid real API call
    mock_chain_response = json.dumps({
        "qualification_score": 85,
        "qualification_reasoning": "Test qualification reasoning",
        "next_action": "Schedule meeting",
        "tier": "Tier 1",
        "fit_assessment": "Strong fit",
        "contact_quality": "High",
        "sales_potential": "High"
    })
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_chain_response)
    agent.chain = mock_chain

    # Qualify lead without email
    result, latency, metadata = await agent.qualify(
        company_name="Test Corp",
        company_website="https://example.com",
        industry="Construction"
    )

    # Verify email extraction was called
    mock_extractor.extract_emails.assert_called_once_with("https://example.com")

    # Verify result includes qualification data
    assert result.qualification_score >= 0
    assert result.qualification_score <= 100


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.qualification_agent.QualificationAgent._initialize_llm')
async def test_qualification_skips_extraction_when_email_provided(mock_init_llm):
    """Test email extraction skipped when contact_email provided."""
    # Mock LLM initialization
    mock_llm = MagicMock()
    mock_init_llm.return_value = mock_llm

    agent = QualificationAgent()

    # Mock email extractor (should not be called)
    mock_extractor = AsyncMock()
    agent.email_extractor = mock_extractor

    # Mock LLM chain to avoid real API call
    mock_chain_response = json.dumps({
        "qualification_score": 75,
        "qualification_reasoning": "Test qualification reasoning",
        "next_action": "Schedule meeting",
        "tier": "Tier 2",
        "fit_assessment": "Good fit",
        "contact_quality": "Medium",
        "sales_potential": "Medium"
    })
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_chain_response)
    agent.chain = mock_chain

    # Qualify lead WITH email
    result, latency, metadata = await agent.qualify(
        company_name="Test Corp",
        contact_email="provided@example.com",
        industry="Construction"
    )

    # Verify email extraction was NOT called
    mock_extractor.extract_emails.assert_not_called()


@pytest.mark.asyncio
@patch('app.services.langgraph.agents.qualification_agent.QualificationAgent._initialize_llm')
async def test_qualification_continues_without_email(mock_init_llm):
    """Test qualification proceeds even if no emails found."""
    # Mock LLM initialization
    mock_llm = MagicMock()
    mock_init_llm.return_value = mock_llm

    agent = QualificationAgent()

    # Mock email extractor returning empty list
    mock_extractor = AsyncMock()
    mock_extractor.extract_emails = AsyncMock(return_value=[])
    agent.email_extractor = mock_extractor

    # Mock LLM chain to avoid real API call
    mock_chain_response = json.dumps({
        "qualification_score": 65,
        "qualification_reasoning": "Test qualification reasoning",
        "next_action": "Research more",
        "tier": "Tier 3",
        "fit_assessment": "Moderate fit",
        "contact_quality": "Low",
        "sales_potential": "Low"
    })
    mock_chain = AsyncMock()
    mock_chain.ainvoke = AsyncMock(return_value=mock_chain_response)
    agent.chain = mock_chain

    # Qualify lead
    result, latency, metadata = await agent.qualify(
        company_name="Test Corp",
        company_website="https://example.com"
    )

    # Should still complete successfully
    assert result.qualification_score >= 0
