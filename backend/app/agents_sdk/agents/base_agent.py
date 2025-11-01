"""Base agent class for Claude Agent SDK agents."""
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, AsyncIterator
from dataclasses import dataclass

from app.agents_sdk.sessions.redis_store import RedisSessionStore
from app.agents_sdk.schemas.chat import ChatMessage, SSEChunk
from app.agents_sdk.config import config
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Try to import SDK dependencies
# If not available (e.g., during testing), they will be mocked
try:
    from mcp import create_sdk_mcp_server
except ImportError:
    create_sdk_mcp_server = None  # Will be mocked in tests

try:
    from claude_agent_sdk import ClaudeSDKClient, ClaudeAgentOptions
except ImportError:
    ClaudeSDKClient = None  # Will be mocked in tests
    ClaudeAgentOptions = None  # Will be mocked in tests


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    description: str
    model: str = config.default_model
    temperature: float = config.temperature
    max_tokens: int = config.max_tokens


class BaseAgent(ABC):
    """
    Base class for all Claude Agent SDK agents.

    Provides:
    - Session management (Redis)
    - Tool execution
    - Streaming responses
    - Error handling

    Subclasses must implement:
    - get_system_prompt(): Return agent-specific system prompt
    - get_tools(): Return list of MCP tools
    """

    def __init__(self, config: AgentConfig):
        """Initialize base agent."""
        self.config = config
        self.name = config.name
        self.session_store: Optional[RedisSessionStore] = None

        logger.info(f"Initialized {self.name} agent")

    async def _init_session_store(self):
        """Initialize Redis session store (lazy)."""
        if self.session_store is None:
            self.session_store = await RedisSessionStore.create()
            logger.debug(f"{self.name}: Session store initialized")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get agent-specific system prompt.

        Returns:
            System prompt string
        """
        pass

    @abstractmethod
    def get_tools(self) -> List[Any]:
        """
        Get agent-specific MCP tools.

        Returns:
            List of tool functions decorated with @tool
        """
        pass

    async def create_session(self, user_id: str) -> str:
        """
        Create new conversation session.

        Args:
            user_id: User identifier

        Returns:
            session_id: Generated session ID
        """
        await self._init_session_store()

        session_id = await self.session_store.create_session(
            user_id=user_id,
            agent_type=self.name
        )

        logger.info(f"{self.name}: Created session {session_id} for user {user_id}")
        return session_id

    async def get_or_create_session(
        self,
        user_id: str,
        session_id: Optional[str] = None
    ) -> str:
        """
        Get existing session or create new one.

        Args:
            user_id: User identifier
            session_id: Optional existing session ID

        Returns:
            session_id: Session ID (existing or new)
        """
        await self._init_session_store()

        if session_id:
            # Check if exists
            session = await self.session_store.get_session(session_id)
            if session:
                logger.debug(f"{self.name}: Using existing session {session_id}")
                return session_id

        # Create new session
        return await self.create_session(user_id)

    async def chat(
        self,
        session_id: str,
        message: str
    ) -> AsyncIterator[str]:
        """
        Chat with agent (streaming).

        Args:
            session_id: Session ID
            message: User message

        Yields:
            SSE-formatted chunks
        """
        await self._init_session_store()

        # Load session
        session = await self.session_store.get_session(session_id)
        if session is None:
            raise ValueError(f"Session {session_id} not found")

        # Add user message to session
        user_msg = ChatMessage(role="user", content=message)
        await self.session_store.add_message(session_id, user_msg)

        # Build Claude Agent SDK options
        system_prompt = self.get_system_prompt()
        tools = self.get_tools()

        # Create MCP server with tools
        mcp_server = create_sdk_mcp_server(
            name=f"{self.name}_tools",
            tools=tools
        )

        options = ClaudeAgentOptions(
            system_prompt=system_prompt,
            mcp_servers={self.name: mcp_server},
            model=self.config.model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens
        )

        # Stream response
        try:
            async with ClaudeSDKClient(options=options) as client:
                await client.query(message)

                async for chunk in client.receive_messages():
                    # Format as SSE
                    sse_chunk = SSEChunk(
                        event="message",
                        data={"content": str(chunk)}
                    )
                    yield sse_chunk.format_sse()

                # Add assistant response to session
                # Note: In real implementation, accumulate chunks
                # For now, placeholder
                assistant_msg = ChatMessage(role="assistant", content="[streamed response]")
                await self.session_store.add_message(session_id, assistant_msg)

        except Exception as e:
            logger.error(f"{self.name}: Chat failed: {e}", exc_info=True)

            # Send error chunk
            error_chunk = SSEChunk(
                event="error",
                data={
                    "message": f"Agent error: {str(e)}",
                    "suggestion": "Try rephrasing your question"
                }
            )
            yield error_chunk.format_sse()
