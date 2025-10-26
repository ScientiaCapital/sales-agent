"""
LangGraph Integration Module

Provides LangGraph agents, state schemas, utilities, and tools for the sales-agent platform.

Modules:
- state_schemas: TypedDict state definitions for all agents
- graph_utils: Helper functions for graph construction (coming soon)
- tools/: LangChain tools for CRM, Apollo, LinkedIn, etc. (coming soon)
"""

from .state_schemas import (
    # Base
    BaseAgentState,

    # Agent States
    QualificationAgentState,
    EnrichmentAgentState,
    GrowthAgentState,
    MarketingAgentState,
    BDRAgentState,
    ConversationAgentState,

    # Utilities
    create_initial_state,
    get_latest_message,
    get_messages_by_role,
)

__all__ = [
    # Base
    "BaseAgentState",

    # Agent States
    "QualificationAgentState",
    "EnrichmentAgentState",
    "GrowthAgentState",
    "MarketingAgentState",
    "BDRAgentState",
    "ConversationAgentState",

    # Utilities
    "create_initial_state",
    "get_latest_message",
    "get_messages_by_role",
]
