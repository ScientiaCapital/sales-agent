"""Cost-optimized LLM provider with unified tracking."""
from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass
from sqlalchemy.ext.asyncio import AsyncSession


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
        # TODO: Implement in next tasks
        raise NotImplementedError("Implement in Task 6-8")
