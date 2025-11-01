"""Cost-optimized LLM provider with unified tracking."""
from typing import Optional, Dict, Any, Literal, Union
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
import time
import logging
import os

# LangChain imports for real provider calls
from langchain_core.messages import HumanMessage
from langchain_cerebras import ChatCerebras
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_google_genai import ChatGoogleGenerativeAI

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """
    Configuration for an LLM call.

    Attributes:
        agent_type: Agent making the call (e.g., "qualification", "sr_bdr")
        lead_id: Lead ID for per-lead cost tracking (optional)
        session_id: Session ID for Agent SDK conversations (optional)
        user_id: User ID for per-user tracking (optional)
        mode: "passthrough" (use agent's provider) or "smart_router" (optimize)
        provider: Provider for passthrough mode (e.g., "cerebras", "claude")
        model: Model for passthrough mode (e.g., "llama3.1-8b")
    """
    agent_type: str
    lead_id: Optional[int] = None
    session_id: Optional[str] = None
    user_id: Optional[str] = None
    mode: Literal["passthrough", "smart_router"] = "passthrough"
    provider: Optional[str] = None  # Required for passthrough
    model: Optional[str] = None  # Required for passthrough


class CostOptimizedLLMProvider:
    """
    Unified proxy for all AI calls in sales-agent.

    Two modes:
    - passthrough: Use agent's chosen provider, track cost only
    - smart_router: Use ai-cost-optimizer's intelligent routing

    All calls tracked in ai_cost_tracking table with rich context.
    """

    def __init__(self, db_session: Union[Session, AsyncSession]):
        """
        Initialize provider.

        Args:
            db_session: SQLAlchemy session (sync or async) for cost tracking
        """
        self.db = db_session
        self.is_async = isinstance(db_session, AsyncSession)

        # Initialize router from ai-cost-optimizer
        try:
            # Import Router and complexity scorer from ai-cost-optimizer package
            from ai_cost_optimizer.app.router import Router
            from ai_cost_optimizer.app.complexity import score_complexity
            from ai_cost_optimizer.app.providers import (
                CerebrasProvider, ClaudeProvider, GeminiProvider
            )

            # Initialize providers for the router
            providers = {}

            # Add Cerebras if API key available
            cerebras_key = os.getenv("CEREBRAS_API_KEY")
            if cerebras_key:
                providers["cerebras"] = CerebrasProvider(cerebras_key)

            # Add Claude if API key available
            claude_key = os.getenv("ANTHROPIC_API_KEY")
            if claude_key:
                providers["claude"] = ClaudeProvider(claude_key)

            # Add Gemini if API key available
            gemini_key = os.getenv("GOOGLE_API_KEY")
            if gemini_key:
                providers["gemini"] = GeminiProvider(gemini_key)

            # Initialize router with available providers
            self.router = Router(providers=providers, enable_learning=False)
            self.score_complexity = score_complexity

            logger.info(f"Initialized Router with providers: {list(providers.keys())}")

        except ImportError as e:
            logger.error(f"Failed to import ai-cost-optimizer: {e}")
            raise RuntimeError(
                "ai-cost-optimizer not installed. Run: pip install -e ./lib/ai-cost-optimizer"
            ) from e
        except Exception as e:
            logger.error(f"Router initialization failed: {e}")
            raise

    async def complete(
        self,
        prompt: str,
        config: LLMConfig,
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> Dict[str, Any]:
        """
        Execute LLM completion with cost tracking.

        Args:
            prompt: User prompt text
            config: LLMConfig with mode and context
            max_tokens: Maximum tokens in response
            temperature: Sampling temperature

        Returns:
            Dict with:
                - response: Completion text
                - provider: Provider used
                - model: Model used
                - tokens_in: Input tokens
                - tokens_out: Output tokens
                - cost_usd: Cost in USD
                - latency_ms: Execution time
                - cache_hit: Whether cached
        """
        start_time = time.time()

        # Validate passthrough mode has required parameters
        if config.mode == "passthrough":
            if not config.provider or not config.model:
                raise ValueError(
                    f"Passthrough mode requires provider and model. "
                    f"Got provider={config.provider}, model={config.model}"
                )
            # Task 6: Passthrough mode - use agent's specified provider
            result = await self._passthrough_call(
                prompt=prompt,
                provider=config.provider,
                model=config.model,
                max_tokens=max_tokens,
                temperature=temperature
            )
        else:
            # Task 7: Smart router mode - use ai-cost-optimizer
            result = await self._smart_router_call(
                prompt=prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )

        latency_ms = int((time.time() - start_time) * 1000)

        # Task 8: Track cost to database
        await self._track_cost(config, prompt, result, latency_ms)

        return {**result, "latency_ms": latency_ms}

    async def _passthrough_call(
        self,
        prompt: str,
        provider: str,
        model: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Execute call using specified provider (Task 6)."""
        logger.info(f"Passthrough call to {provider}/{model}")

        try:
            # Instantiate correct LangChain provider
            if provider == "cerebras":
                api_key = os.getenv("CEREBRAS_API_KEY")
                if not api_key:
                    raise ValueError("CEREBRAS_API_KEY not set")
                llm = ChatCerebras(
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=api_key
                )

            elif provider == "claude":
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    raise ValueError("ANTHROPIC_API_KEY not set")
                llm = ChatAnthropic(
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    api_key=api_key
                )

            elif provider == "deepseek":
                # DeepSeek via OpenRouter
                api_key = os.getenv("OPENROUTER_API_KEY")
                if not api_key:
                    raise ValueError("OPENROUTER_API_KEY not set")
                llm = ChatOpenAI(
                    model=model if "/" in model else "deepseek/deepseek-chat",
                    temperature=temperature,
                    max_tokens=max_tokens,
                    openai_api_key=api_key,
                    openai_api_base="https://openrouter.ai/api/v1"
                )

            elif provider == "gemini":
                api_key = os.getenv("GOOGLE_API_KEY")
                if not api_key:
                    raise ValueError("GOOGLE_API_KEY not set")
                llm = ChatGoogleGenerativeAI(
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    google_api_key=api_key
                )

            else:
                raise ValueError(
                    f"Unknown provider: {provider}. "
                    f"Supported: cerebras, claude, deepseek, gemini"
                )

            # Execute actual API call
            response = await llm.ainvoke([HumanMessage(content=prompt)])

            # Extract real token usage from response metadata
            usage = response.response_metadata.get("usage", {})

            # Different providers use different keys for token counts
            if provider == "cerebras":
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)
            elif provider == "claude":
                tokens_in = usage.get("input_tokens", 0)
                tokens_out = usage.get("output_tokens", 0)
            elif provider == "gemini":
                tokens_in = usage.get("prompt_token_count", 0) or usage.get("promptTokenCount", 0)
                tokens_out = usage.get("candidates_token_count", 0) or usage.get("candidatesTokenCount", 0)
            else:
                # OpenRouter/DeepSeek
                tokens_in = usage.get("prompt_tokens", 0)
                tokens_out = usage.get("completion_tokens", 0)

            # Calculate cost based on actual token usage
            cost_usd = self._calculate_cost(provider, model, tokens_in, tokens_out)

            return {
                "response": response.content,
                "provider": provider,
                "model": model,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "cost_usd": cost_usd,
                "cache_hit": False
            }

        except Exception as e:
            logger.error(f"Error in passthrough call to {provider}/{model}: {e}")
            raise

    async def _smart_router_call(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Execute call using smart router (Task 7)."""
        logger.info("Smart router call")

        try:
            # Calculate actual complexity score using ai-cost-optimizer
            complexity = self.score_complexity(prompt)
            logger.info(f"Complexity scored as: {complexity}")

            # Use Router to route and execute the completion
            result = await self.router.route_and_complete(
                prompt=prompt,
                complexity=complexity,
                max_tokens=max_tokens
            )

            # Router returns: response, provider, model, complexity, tokens_in, tokens_out, cost
            # Convert to our expected format
            return {
                "response": result["response"],
                "provider": result["provider"],
                "model": result["model"],
                "tokens_in": result["tokens_in"],
                "tokens_out": result["tokens_out"],
                "cost_usd": result["cost"],
                "complexity": result["complexity"],
                "cache_hit": False
            }

        except Exception as e:
            logger.error(f"Smart router failed: {e}, falling back to Claude Haiku")
            # Fallback to Claude Haiku if router fails
            return await self._passthrough_call(
                prompt=prompt,
                provider="claude",
                model="claude-3-haiku-20240307",
                max_tokens=max_tokens,
                temperature=temperature
            )

    def _calculate_cost(self, provider: str, model: str, tokens_in: int, tokens_out: int) -> float:
        """Calculate cost based on provider pricing."""
        # Cerebras pricing
        if provider == "cerebras":
            return (tokens_in + tokens_out) * 0.000006 / 1000

        # Claude Haiku pricing
        elif provider == "claude" and "haiku" in model.lower():
            return (tokens_in * 0.00025 + tokens_out * 0.00125) / 1000

        # Gemini Flash pricing
        elif provider == "gemini" and "flash" in model.lower():
            return (tokens_in * 0.00001 + tokens_out * 0.00003) / 1000

        # DeepSeek pricing
        elif provider == "deepseek":
            return (tokens_in + tokens_out) * 0.00027 / 1000

        else:
            # Default fallback
            return (tokens_in * 0.0001 + tokens_out * 0.0005) / 1000

    async def _track_cost(
        self,
        config: LLMConfig,
        prompt: str,
        result: Dict[str, Any],
        latency_ms: int
    ):
        """Save cost tracking to database (Task 8)."""
        try:
            from app.models.ai_cost_tracking import AICostTracking
        except Exception as e:
            # If we can't import the model, skip tracking
            logger.warning(f"Could not import AICostTracking: {e}")
            return

        tracking = AICostTracking(
            agent_type=config.agent_type,
            agent_mode=config.mode,
            lead_id=config.lead_id,
            session_id=config.session_id,
            user_id=config.user_id,
            prompt_text=prompt[:1000],  # Truncate for storage
            prompt_tokens=result["tokens_in"],
            prompt_complexity=result.get("complexity"),
            completion_text=result["response"][:1000],  # Truncate
            completion_tokens=result["tokens_out"],
            provider=result["provider"],
            model=result["model"],
            cost_usd=result["cost_usd"],
            latency_ms=latency_ms,
            cache_hit=result.get("cache_hit", False)
        )

        try:
            self.db.add(tracking)

            # Handle both sync and async sessions
            if self.is_async:
                await self.db.commit()
            else:
                self.db.commit()

            logger.info(f"Tracked cost: ${result['cost_usd']:.6f} for {config.agent_type}")
        except Exception as e:
            logger.error(f"Failed to save cost tracking: {e}")

            # Rollback based on session type
            if self.is_async:
                await self.db.rollback()
            else:
                self.db.rollback()

            # Don't raise - tracking failure shouldn't break LLM calls
