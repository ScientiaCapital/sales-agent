"""
BaseAgent - Unified Agent Base Class with DeepAgents + Cerebras Patterns

Combines patterns from:
- LangChain DeepAgents: Middleware composition, subagent spawning
- Cerebras Cookbook: Ultra-fast inference, agent transfers, grounding

Supports all cost-optimized providers:
- Cerebras: Ultra-fast (633ms), ultra-cheap ($0.000006/call)
- DeepSeek: Cost-effective reasoning ($0.00027/call)
- Claude: Premium reasoning when needed ($0.001743/call)
- Ollama: Free local inference ($0/call)

Features:
- Automatic provider selection based on task requirements
- Agent transfer tools for multi-agent workflows
- Context management from files (prevent hallucinations)
- Cost tracking integration
- Redis-based caching support
- Communication hub integration

Usage:
    ```python
    from app.services.langgraph.agents.base_agent import BaseAgent, AgentConfig

    # Quick agent for speed-critical tasks
    config = AgentConfig(
        name="qualification",
        provider="cerebras",
        model="llama3.1-8b",
        optimize_for="speed"
    )
    agent = BaseAgent(config)

    # Cost-optimized agent for batch tasks
    config = AgentConfig(
        name="growth_analysis",
        provider="deepseek",
        model="deepseek-chat",
        optimize_for="cost"
    )
    agent = BaseAgent(config)
    ```
"""

import os
import time
from typing import Dict, Any, List, Optional, Literal, Union, Callable
from dataclasses import dataclass, field
from enum import Enum
from abc import ABC, abstractmethod

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import BaseTool
from langchain_cerebras import ChatCerebras
from langchain_anthropic import ChatAnthropic  # Used for Claude AND DeepSeek (Anthropic-compatible API)
from langchain_community.chat_models import ChatOllama
from langchain_core.language_models import BaseChatModel
from langgraph.prebuilt import create_react_agent
from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field

from app.core.logging import setup_logging
from app.services.cache.base import get_redis_client
from app.services.cost_tracking import get_cost_optimizer

logger = setup_logging(__name__)


# ========== Configuration Models ==========

class OptimizationTarget(str, Enum):
    """What to optimize for."""
    SPEED = "speed"  # Cerebras (633ms)
    COST = "cost"  # DeepSeek ($0.00027)
    QUALITY = "quality"  # Claude Sonnet ($0.001743)
    LOCAL = "local"  # Ollama ($0)


class ProviderType(str, Enum):
    """Supported LLM providers."""
    CEREBRAS = "cerebras"
    DEEPSEEK = "deepseek"
    CLAUDE = "claude"
    OLLAMA = "ollama"
    AUTO = "auto"  # Automatically select based on optimization target


@dataclass
class AgentConfig:
    """Configuration for agent initialization."""
    # Identity
    name: str
    description: str = ""

    # LLM settings
    provider: ProviderType = ProviderType.AUTO
    model: Optional[str] = None  # Auto-selects if None
    temperature: float = 0.3
    max_tokens: int = 2000

    # Optimization
    optimize_for: OptimizationTarget = OptimizationTarget.COST

    # Features
    use_cache: bool = True
    enable_transfers: bool = True  # Allow agent-to-agent transfers
    enable_communication_hub: bool = True  # Connect to communication hub

    # Context & Grounding
    context_files: List[str] = field(default_factory=list)  # Files to load as context
    grounding_strategy: Literal["strict", "moderate", "permissive"] = "strict"

    # Tools
    custom_tools: List[BaseTool] = field(default_factory=list)

    # Cost tracking
    track_costs: bool = True
    cost_budget_usd: Optional[float] = None  # Alert if exceeded


# ========== Provider Cost Matrix ==========

PROVIDER_COSTS = {
    "cerebras": {
        "llama3.1-8b": {"per_m_tokens": 0.10, "avg_latency_ms": 500},
        "llama3.1-70b": {"per_m_tokens": 0.60, "avg_latency_ms": 800},
        "llama-3.3-70b": {"per_m_tokens": 0.60, "avg_latency_ms": 633},
    },
    "deepseek": {
        "deepseek-chat": {"per_m_tokens": 0.27, "avg_latency_ms": 3000},
    },
    "claude": {
        "claude-3-haiku-20240307": {"per_m_tokens": 1.25, "avg_latency_ms": 2000},
        "claude-3-5-haiku-20241022": {"per_m_tokens": 1.25, "avg_latency_ms": 2000},
        "claude-3-5-sonnet-20241022": {"per_m_tokens": 4.50, "avg_latency_ms": 4000},
    },
    "ollama": {
        "*": {"per_m_tokens": 0.0, "avg_latency_ms": 1000},
    }
}

# Auto-selection mapping
OPTIMIZATION_DEFAULTS = {
    OptimizationTarget.SPEED: ("cerebras", "llama3.1-8b"),
    OptimizationTarget.COST: ("deepseek", "deepseek-chat"),
    OptimizationTarget.QUALITY: ("claude", "claude-3-5-sonnet-20241022"),
    OptimizationTarget.LOCAL: ("ollama", "llama3.1:8b"),
}


# ========== Base Agent ==========

class BaseAgent(ABC):
    """
    Unified agent base class combining DeepAgents and Cerebras patterns.

    Provides:
    - Multi-provider LLM support with auto-selection
    - Agent transfer tools for multi-agent workflows
    - Context loading and grounding strategies
    - Cost tracking and budget management
    - Redis caching integration
    - Communication hub connectivity

    Subclasses should implement:
    - get_system_prompt(): Return agent-specific system instructions
    - get_tools(): Return agent-specific tools
    - process_result(): Post-process LLM outputs
    """

    def __init__(self, config: AgentConfig):
        """Initialize agent with configuration."""
        self.config = config
        self.name = config.name

        # Auto-select provider/model if needed
        if config.provider == ProviderType.AUTO or config.model is None:
            provider_str, model = OPTIMIZATION_DEFAULTS[config.optimize_for]
            self.provider = ProviderType(provider_str)
            self.model = config.model or model
        else:
            self.provider = config.provider
            self.model = config.model

        # Initialize LLM
        self.llm = self._initialize_llm()

        # Load context files for grounding
        self.context = self._load_context()

        # Initialize cache if enabled
        self.cache = None
        if config.use_cache:
            self._init_cache()

        # Cost tracking
        self.total_cost_usd = 0.0
        self.total_calls = 0
        self.cost_optimizer = None  # Lazy init on first use

        # Communication hub connection (lazy init)
        self.hub = None

        logger.info(
            f"✅ {self.name} agent initialized: "
            f"provider={self.provider.value}, model={self.model}, "
            f"optimize_for={config.optimize_for.value}"
        )

    def _initialize_llm(self) -> BaseChatModel:
        """Initialize LLM based on provider."""
        if self.provider == ProviderType.CEREBRAS:
            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                raise ValueError("CEREBRAS_API_KEY environment variable not set")

            return ChatCerebras(
                model=self.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=api_key
            )

        elif self.provider == ProviderType.DEEPSEEK:
            # DeepSeek supports Anthropic-compatible API (no OpenAI dependency!)
            # https://api-docs.deepseek.com/guides/anthropic_api
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            return ChatAnthropic(
                model=self.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=api_key,
                base_url="https://api.deepseek.com"  # Anthropic-compatible endpoint
            )

        elif self.provider == ProviderType.CLAUDE:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            return ChatAnthropic(
                model=self.model,
                temperature=self.config.temperature,
                max_tokens=self.config.max_tokens,
                api_key=api_key
            )

        elif self.provider == ProviderType.OLLAMA:
            return ChatOllama(
                model=self.model,
                temperature=self.config.temperature,
                num_predict=self.config.max_tokens
            )

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _load_context(self) -> str:
        """Load context files for grounding."""
        if not self.config.context_files:
            return ""

        context_parts = []
        for file_path in self.config.context_files:
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                    context_parts.append(f"=== {file_path} ===\n{content}\n")
            except Exception as e:
                logger.warning(f"Failed to load context file {file_path}: {e}")

        return "\n".join(context_parts)

    def _init_cache(self):
        """Initialize cache (implemented by subclasses if needed)."""
        pass

    async def _init_cost_optimizer(self):
        """Initialize cost optimizer client (lazy initialization)."""
        if not self.config.track_costs:
            return

        if self.cost_optimizer is None:
            try:
                self.cost_optimizer = await get_cost_optimizer()
                logger.debug(f"{self.name} connected to cost optimizer")
            except Exception as e:
                logger.warning(f"Failed to init cost optimizer: {e}. Continuing without cost tracking.")
                self.cost_optimizer = None

    def _get_grounding_instructions(self) -> str:
        """Get grounding instructions based on strategy."""
        if self.config.grounding_strategy == "strict":
            return """
CRITICAL GROUNDING RULES:
- ONLY use information from the provided context
- DO NOT make up prices, features, dates, or any other details
- If asked about something not in the context, say "I don't have that information"
- Quote context directly when possible
- Never hallucinate or assume information
"""
        elif self.config.grounding_strategy == "moderate":
            return """
GROUNDING GUIDELINES:
- Prefer information from the provided context
- Clearly distinguish between context-based and inferred information
- If making assumptions, explicitly state them
- Default to "I don't know" for missing information
"""
        else:  # permissive
            return """
CONTEXT GUIDELINES:
- Use provided context as primary reference
- You may use general knowledge when context is insufficient
- Be transparent about information sources
"""

    def get_cost_estimate(self, text_length: int) -> float:
        """Estimate cost for processing text."""
        estimated_tokens = text_length * 1.3  # rough estimate
        cost_per_m = PROVIDER_COSTS.get(self.provider.value, {}).get(
            self.model,
            PROVIDER_COSTS.get(self.provider.value, {}).get("*", {"per_m_tokens": 0})
        )["per_m_tokens"]

        return (estimated_tokens / 1_000_000) * cost_per_m

    def track_cost(self, cost_usd: float):
        """Track cost and check budget."""
        self.total_cost_usd += cost_usd
        self.total_calls += 1

        if self.config.cost_budget_usd and self.total_cost_usd > self.config.cost_budget_usd:
            logger.warning(
                f"⚠️ {self.name} agent exceeded cost budget: "
                f"${self.total_cost_usd:.4f} > ${self.config.cost_budget_usd:.4f}"
            )

    async def log_llm_call(
        self,
        prompt: str,
        response: str,
        tokens_in: int,
        tokens_out: int,
        latency_ms: int,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log LLM call with costs to ai-cost-optimizer.

        Args:
            prompt: Input prompt
            response: Model response
            tokens_in: Input token count
            tokens_out: Output token count
            latency_ms: Execution time
            metadata: Additional context
        """
        if not self.config.track_costs:
            return

        # Initialize cost optimizer if needed
        if self.cost_optimizer is None:
            await self._init_cost_optimizer()

        if self.cost_optimizer is None:
            return  # Failed to initialize, skip logging

        # Calculate cost
        cost_per_m = PROVIDER_COSTS.get(self.provider.value, {}).get(
            self.model,
            PROVIDER_COSTS.get(self.provider.value, {}).get("*", {"per_m_tokens": 0})
        )["per_m_tokens"]

        total_tokens = tokens_in + tokens_out
        cost_usd = (total_tokens / 1_000_000) * cost_per_m

        # Track locally
        self.track_cost(cost_usd)

        # Log to ai-cost-optimizer
        try:
            await self.cost_optimizer.log_llm_call(
                provider=self.provider.value,
                model=self.model,
                prompt=prompt,
                response=response,
                tokens_in=tokens_in,
                tokens_out=tokens_out,
                cost_usd=cost_usd,
                agent_name=self.name,
                metadata={
                    "latency_ms": latency_ms,
                    "optimization_target": self.config.optimize_for.value,
                    **(metadata or {})
                }
            )
            logger.debug(
                f"💰 Logged LLM call: {self.name} "
                f"({self.provider.value}/{self.model}, ${cost_usd:.6f})"
            )
        except Exception as e:
            logger.error(f"Failed to log LLM call to optimizer: {e}")

    async def log_agent_execution(
        self,
        agent_type: str,
        latency_ms: int,
        success: bool = True,
        error_message: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """
        Log complete agent execution to ai-cost-optimizer.

        Args:
            agent_type: Type of agent (qualification, enrichment, etc.)
            latency_ms: Total execution time
            success: Whether execution succeeded
            error_message: Error message if failed
            metadata: Additional context
        """
        if not self.config.track_costs:
            return

        # Initialize cost optimizer if needed
        if self.cost_optimizer is None:
            await self._init_cost_optimizer()

        if self.cost_optimizer is None:
            return

        try:
            await self.cost_optimizer.log_agent_execution(
                agent_name=self.name,
                agent_type=agent_type,
                latency_ms=latency_ms,
                cost_usd=self.total_cost_usd,
                success=success,
                error_message=error_message,
                metadata=metadata or {}
            )
        except Exception as e:
            logger.error(f"Failed to log agent execution: {e}")

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get agent-specific system prompt. Must be implemented by subclasses."""
        pass

    @abstractmethod
    def get_tools(self) -> List[BaseTool]:
        """Get agent-specific tools. Must be implemented by subclasses."""
        pass

    def process_result(self, result: Any) -> Any:
        """Post-process LLM result. Can be overridden by subclasses."""
        return result

    async def transfer_to_agent(self, target_agent: str, context: Dict[str, Any]) -> Any:
        """
        Transfer control to another agent (Cerebras cookbook pattern).

        Args:
            target_agent: Name of target agent
            context: Context to pass to target agent

        Returns:
            Result from target agent
        """
        if not self.config.enable_transfers:
            raise ValueError(f"Agent transfers disabled for {self.name}")

        logger.info(f"🔄 {self.name} transferring to {target_agent}")

        # TODO: Implement agent registry lookup and transfer
        # This will integrate with the orchestrator and communication hub
        raise NotImplementedError("Agent transfers not yet implemented")

    def get_stats(self) -> Dict[str, Any]:
        """Get agent statistics."""
        return {
            "agent_name": self.name,
            "provider": self.provider.value,
            "model": self.model,
            "total_calls": self.total_calls,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "avg_cost_per_call_usd": round(
                self.total_cost_usd / self.total_calls if self.total_calls > 0 else 0,
                6
            ),
            "cache_enabled": self.config.use_cache,
            "optimization_target": self.config.optimize_for.value,
        }
