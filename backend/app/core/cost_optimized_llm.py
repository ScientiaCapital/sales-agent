"""Cost-optimized LLM provider with unified tracking."""
from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession
import time
import logging

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

    def __init__(self, db_session: AsyncSession):
        """
        Initialize provider.

        Args:
            db_session: SQLAlchemy async session for cost tracking
        """
        self.db = db_session
        # Initialize router (will be configured from ai-cost-optimizer)
        # For now, create a minimal router instance
        try:
            # Import from the app directory in ai-cost-optimizer
            import sys
            import os
            ai_cost_opt_path = os.path.join(os.path.dirname(__file__), '../../lib/ai-cost-optimizer')
            if ai_cost_opt_path not in sys.path:
                sys.path.insert(0, ai_cost_opt_path)
            from app.router import Router
            self.router = Router(providers={})
        except Exception as e:
            # Fallback if ai-cost-optimizer not available
            import warnings
            warnings.warn(f"Router initialization failed: {e}. Using fallback.")
            self.router = object()  # Placeholder object

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

        if config.mode == "passthrough":
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
        # Simplified implementation - in production this would call actual providers
        # For now, return mock data with correct structure
        logger.info(f"Passthrough call to {provider}/{model}")

        # Estimate tokens (rough approximation: 1 token ~ 4 characters)
        tokens_in = len(prompt) // 4
        tokens_out = min(max_tokens, 100)  # Simplified

        # Calculate cost based on provider
        cost_usd = self._calculate_cost(provider, model, tokens_in, tokens_out)

        return {
            "response": f"Mock response from {provider}",
            "provider": provider,
            "model": model,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "cost_usd": cost_usd,
            "cache_hit": False
        }

    async def _smart_router_call(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float
    ) -> Dict[str, Any]:
        """Execute call using smart router (Task 7)."""
        logger.info("Smart router call")

        # Simplified complexity analysis
        complexity = "simple" if len(prompt) < 100 else "complex"

        # Route based on complexity
        if complexity == "simple":
            provider, model = "gemini", "gemini-1.5-flash"
        else:
            provider, model = "claude", "claude-3-haiku-20240307"

        # Use passthrough for actual call
        return await self._passthrough_call(
            prompt=prompt,
            provider=provider,
            model=model,
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

        self.db.add(tracking)
        await self.db.commit()

        logger.info(f"Tracked cost: ${result['cost_usd']:.6f} for {config.agent_type}")
