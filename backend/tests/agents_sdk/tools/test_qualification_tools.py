"""Test qualification MCP tools."""
import pytest
from unittest.mock import AsyncMock, patch, Mock, MagicMock
import sys
import importlib.machinery

# Workaround for openai.__spec__ issue in transformers package
# This needs to happen before any langchain imports
try:
    import openai
    if openai.__spec__ is None:
        # Create a proper spec
        spec = importlib.machinery.ModuleSpec(
            name='openai',
            loader=None,
            origin=openai.__file__ if hasattr(openai, '__file__') else None
        )
        openai.__spec__ = spec
except (ImportError, ValueError, AttributeError):
    pass


@pytest.mark.asyncio
async def test_qualify_lead_tool_success():
    """Test qualify_lead tool calls QualificationAgent successfully."""
    # Create mock result before importing the tool
    # This avoids triggering the QualificationAgent import chain
    from unittest.mock import MagicMock

    mock_result = MagicMock()
    mock_result.qualification_score = 85.0
    mock_result.tier = "hot"
    mock_result.qualification_reasoning = "Multi-state contractor with strong ICP fit"
    mock_result.fit_assessment = "Excellent company size and industry match"
    mock_result.contact_quality = "Decision-maker level contact"
    mock_result.sales_potential = "High - recent expansion signals"
    mock_result.recommendations = None

    # Patch at the module level where it's imported in the function
    with patch('app.services.langgraph.agents.qualification_agent.QualificationAgent') as MockAgent:
        mock_agent = MockAgent.return_value
        mock_agent.qualify = AsyncMock(return_value=(mock_result, 633, {}))

        # Import after patching
        from app.agents_sdk.tools.qualification_tools import qualify_lead_tool

        # Call tool
        result = await qualify_lead_tool.invoke({
            "company_name": "Acme Corp",
            "industry": "Construction"
        })

        # Verify
        assert result["status"] == "success"
        assert result["data"]["score"] == 85.0
        assert result["data"]["tier"] == "hot"
        assert "latency_ms" in result


@pytest.mark.asyncio
async def test_qualify_lead_tool_fallback():
    """Test tool falls back to Claude when Cerebras fails."""
    from unittest.mock import MagicMock

    # Create mock error class
    class MockCerebrasAPIError(Exception):
        pass

    # Create mock result for Claude fallback
    mock_result = MagicMock()
    mock_result.qualification_score = 80.0
    mock_result.tier = "hot"
    mock_result.qualification_reasoning = "Good fit"
    mock_result.fit_assessment = "Good"
    mock_result.contact_quality = "Good"
    mock_result.sales_potential = "Good"
    mock_result.recommendations = None

    # Patch both QualificationAgent and CerebrasAPIError
    with patch('app.core.exceptions.CerebrasAPIError', MockCerebrasAPIError):
        with patch('app.services.langgraph.agents.qualification_agent.QualificationAgent') as MockAgent:
            # Create two different mock agents
            mock_agent_cerebras = Mock()
            mock_agent_cerebras.qualify = AsyncMock(
                side_effect=MockCerebrasAPIError("Cerebras unavailable")
            )

            mock_agent_claude = Mock()
            mock_agent_claude.qualify = AsyncMock(return_value=(mock_result, 4000, {}))

            # Setup mock to return different instances on each call
            MockAgent.side_effect = [mock_agent_cerebras, mock_agent_claude]

            # Import after patching
            from app.agents_sdk.tools.qualification_tools import qualify_lead_tool

            # Call tool
            result = await qualify_lead_tool.invoke({"company_name": "Test Corp"})

            # Verify fallback worked
            assert result["status"] == "success_fallback"
            assert result["data"]["score"] == 80.0
