"""Test base agent functionality."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.mark.asyncio
async def test_base_agent_initialization():
    """Test BaseAgent can be initialized."""
    from app.agents_sdk.agents.base_agent import BaseAgent, AgentConfig

    # Create concrete subclass for testing
    class TestAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return "Test agent"

        def get_tools(self) -> list:
            return []

    config = AgentConfig(
        name="test_agent",
        description="Test agent for unit tests"
    )

    agent = TestAgent(config)
    assert agent.name == "test_agent"
    assert agent.config.description == "Test agent for unit tests"


@pytest.mark.asyncio
async def test_base_agent_session_management():
    """Test agent can create and manage sessions."""
    from app.agents_sdk.agents.base_agent import BaseAgent, AgentConfig

    class TestAgent(BaseAgent):
        def get_system_prompt(self) -> str:
            return "Test"

        def get_tools(self) -> list:
            return []

    config = AgentConfig(name="test", description="Test")
    agent = TestAgent(config)

    # Mock session store
    with patch('app.agents_sdk.agents.base_agent.RedisSessionStore') as MockStore:
        mock_store = AsyncMock()
        mock_store.create_session = AsyncMock(return_value="sess_123")
        MockStore.create = AsyncMock(return_value=mock_store)

        # Initialize session store
        await agent._init_session_store()

        # Create session
        session_id = await agent.create_session("user_123")
        assert session_id == "sess_123"
        mock_store.create_session.assert_called_once()
