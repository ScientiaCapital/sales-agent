"""Test SR/BDR Agent."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_sr_bdr_agent_creation():
    """Test SR/BDR agent can be instantiated."""
    from app.agents_sdk.agents.sr_bdr import SRBDRAgent

    agent = SRBDRAgent()

    assert agent.name == "sr_bdr"
    assert agent.config is not None
    assert "sales" in agent.get_system_prompt().lower()


@pytest.mark.asyncio
async def test_sr_bdr_agent_has_tools():
    """Test SR/BDR agent provides qualification tools."""
    from app.agents_sdk.agents.sr_bdr import SRBDRAgent

    agent = SRBDRAgent()
    tools = agent.get_tools()

    # Should have at least qualify_lead and search_leads tools
    assert len(tools) >= 2
    tool_names = [t.name for t in tools]
    assert "qualify_lead_tool" in tool_names
    assert "search_leads_tool" in tool_names


@pytest.mark.asyncio
async def test_sr_bdr_agent_system_prompt():
    """Test SR/BDR agent system prompt is comprehensive."""
    from app.agents_sdk.agents.sr_bdr import SRBDRAgent

    agent = SRBDRAgent()
    prompt = agent.get_system_prompt()

    # Should mention key capabilities
    assert "sales" in prompt.lower()
    assert "lead" in prompt.lower()
    assert "qualify" in prompt.lower()

    # Should have clear role definition
    assert len(prompt) > 200  # Comprehensive prompt
