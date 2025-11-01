"""Cost-optimized LLM provider with unified tracking."""
from typing import Optional, Dict, Any, Literal
from dataclasses import dataclass


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
