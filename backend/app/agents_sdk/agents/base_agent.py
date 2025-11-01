"""Base agent class for Agent SDK agents with cost-optimized LLM provider."""
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.cost_optimized_llm import CostOptimizedLLMProvider, LLMConfig
from app.core.logging import setup_logging

logger = setup_logging(__name__)


@dataclass
class AgentConfig:
    """Configuration for an Agent SDK agent."""
    name: str
    description: str
    temperature: float = 0.7
    max_tokens: int = 2000


class BaseAgent(ABC):
    """
    Base class for all Agent SDK agents with cost-optimized LLM integration.

    This base class provides:
    - Smart routing for cost optimization (mode="smart_router")
    - Automatic cost tracking to ai_cost_tracking table
    - Session and user context tracking
    - Unified LLM interface across all agents

    Subclasses must implement:
    - get_system_prompt(): Return agent-specific system prompt
    """

    def __init__(self, config: AgentConfig, db: Session):
        """
        Initialize base agent.

        Args:
            config: Agent configuration
            db: Database session for cost tracking
        """
        self.config = config
        self.name = config.name
        self.db = db

        # Initialize cost-optimized LLM provider
        self.llm = CostOptimizedLLMProvider(db)

        logger.info(f"Initialized {self.name} agent with smart routing enabled")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get agent-specific system prompt.

        Returns:
            System prompt string defining agent's role and capabilities
        """
        pass

    def _build_prompt(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Build complete prompt with system prompt and user message.

        Args:
            message: User message
            context: Optional context (lead data, session history, etc.)

        Returns:
            Complete prompt string
        """
        system_prompt = self.get_system_prompt()

        # Build prompt with system context and user message
        prompt_parts = [
            f"# System\n{system_prompt}",
            ""
        ]

        # Add context if provided
        if context:
            prompt_parts.append("# Context")
            for key, value in context.items():
                prompt_parts.append(f"{key}: {value}")
            prompt_parts.append("")

        # Add user message
        prompt_parts.append(f"# User Message\n{message}")

        return "\n".join(prompt_parts)

    async def chat(
        self,
        message: str,
        session_id: str,
        user_id: Optional[str] = None,
        lead_id: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Chat with agent using smart routing for cost optimization.

        Args:
            message: User message
            session_id: Session ID for tracking conversation
            user_id: User ID (optional)
            lead_id: Lead ID if conversation is about a specific lead (optional)
            context: Additional context (optional)

        Returns:
            Agent response text

        Raises:
            ValueError: If session_id is None
        """
        if not session_id:
            raise ValueError("session_id is required for Agent SDK agents")

        # Build complete prompt
        prompt = self._build_prompt(message, context)

        # Use cost-optimized provider with smart routing
        result = await self.llm.complete(
            prompt=prompt,
            config=LLMConfig(
                agent_type=self.name,
                session_id=session_id,
                user_id=user_id,
                lead_id=lead_id,
                mode="smart_router"  # Smart routing for intelligent cost optimization
            ),
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature
        )

        logger.info(
            f"{self.name}: Completed chat for session {session_id} "
            f"using {result['provider']}/{result['model']} "
            f"(cost: ${result['cost_usd']:.6f}, latency: {result['latency_ms']}ms)"
        )

        return result["response"]
