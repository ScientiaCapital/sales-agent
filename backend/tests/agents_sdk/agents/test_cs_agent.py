"""Test Customer Success Agent."""
import pytest


@pytest.mark.asyncio
async def test_cs_agent_creation():
    """Test Customer Success agent can be instantiated."""
    from app.agents_sdk.agents.cs_agent import CustomerSuccessAgent

    agent = CustomerSuccessAgent()

    assert agent.name == "customer_success"
    assert agent.config is not None
    assert "customer" in agent.get_system_prompt().lower() or "onboarding" in agent.get_system_prompt().lower()


@pytest.mark.asyncio
async def test_cs_agent_has_tools():
    """Test Customer Success agent provides tools."""
    from app.agents_sdk.agents.cs_agent import CustomerSuccessAgent

    agent = CustomerSuccessAgent()
    tools = agent.get_tools()

    # Should have at least qualification tool for customer validation
    assert len(tools) >= 1


@pytest.mark.asyncio
async def test_cs_agent_system_prompt():
    """Test Customer Success agent system prompt is comprehensive."""
    from app.agents_sdk.agents.cs_agent import CustomerSuccessAgent

    agent = CustomerSuccessAgent()
    prompt = agent.get_system_prompt()

    # Should mention key capabilities
    assert "customer" in prompt.lower() or "onboarding" in prompt.lower()
    assert "help" in prompt.lower() or "support" in prompt.lower()

    # Should have clear role definition
    assert len(prompt) > 200  # Comprehensive prompt
