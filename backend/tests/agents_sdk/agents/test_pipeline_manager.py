"""Test Pipeline Manager Agent."""
import pytest


@pytest.mark.asyncio
async def test_pipeline_manager_creation():
    """Test Pipeline Manager agent can be instantiated."""
    from app.agents_sdk.agents.pipeline_manager import PipelineManagerAgent

    agent = PipelineManagerAgent()

    assert agent.name == "pipeline_manager"
    assert agent.config is not None
    assert "pipeline" in agent.get_system_prompt().lower()


@pytest.mark.asyncio
async def test_pipeline_manager_has_tools():
    """Test Pipeline Manager agent provides pipeline tools."""
    from app.agents_sdk.agents.pipeline_manager import PipelineManagerAgent

    agent = PipelineManagerAgent()
    tools = agent.get_tools()

    # Should have qualification tool for pipeline validation
    assert len(tools) >= 1
    tool_names = [t.name for t in tools]
    assert "qualify_lead_tool" in tool_names


@pytest.mark.asyncio
async def test_pipeline_manager_system_prompt():
    """Test Pipeline Manager agent system prompt is comprehensive."""
    from app.agents_sdk.agents.pipeline_manager import PipelineManagerAgent

    agent = PipelineManagerAgent()
    prompt = agent.get_system_prompt()

    # Should mention key capabilities
    assert "import" in prompt.lower()
    assert "pipeline" in prompt.lower()
    assert "license" in prompt.lower() or "contractor" in prompt.lower()

    # Should have clear role definition
    assert len(prompt) > 200  # Comprehensive prompt
