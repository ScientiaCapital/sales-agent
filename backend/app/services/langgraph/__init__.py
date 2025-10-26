"""
LangGraph Integration Module

Provides LangGraph agents, state schemas, utilities, and tools for the sales-agent platform.

Modules:
- state_schemas: TypedDict state definitions for all agents
- graph_utils: Helper functions for graph construction, checkpointing, and streaming
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

from .graph_utils import (
    # Redis Checkpointing
    get_redis_checkpointer,
    close_redis_checkpointer,

    # Streaming Configuration
    create_streaming_config,
    get_checkpoint_config,
    StreamMode,

    # State Reducers
    merge_metadata,

    # Error Handling
    wrap_node_with_resilience,

    # Graph Construction
    create_agent_graph,
    compile_agent_graph,

    # Utilities
    get_thread_id_for_lead,
    validate_stream_mode,
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

    # State Schema Utilities
    "create_initial_state",
    "get_latest_message",
    "get_messages_by_role",

    # Redis Checkpointing
    "get_redis_checkpointer",
    "close_redis_checkpointer",

    # Streaming Configuration
    "create_streaming_config",
    "get_checkpoint_config",
    "StreamMode",

    # State Reducers
    "merge_metadata",

    # Error Handling
    "wrap_node_with_resilience",

    # Graph Construction
    "create_agent_graph",
    "compile_agent_graph",

    # Utilities
    "get_thread_id_for_lead",
    "validate_stream_mode",
]
