"""
LangGraph Base Utilities and Helpers

Provides reusable utilities for building LangGraph agents:
- Redis checkpointing with singleton pattern
- Streaming configuration helpers
- State reducers for concurrent updates
- Error handling wrappers with circuit breaker integration
- Graph construction helpers

Integration:
- Uses existing Redis infrastructure (REDIS_URL env variable)
- Integrates with CircuitBreaker and RetryHandler patterns
- Compatible with LangSmith tracing configuration
"""

import os
import asyncio
import logging
from typing import Any, Dict, Optional, Callable, TypeVar, Literal
from functools import wraps

from langgraph.graph import StateGraph
from langgraph.checkpoint.redis.aio import AsyncRedisSaver
from app.services.circuit_breaker import CircuitBreaker
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Type variable for generic function wrapping
T = TypeVar('T')


# ========== Redis Checkpointer (Singleton Pattern) ==========

# Global checkpointer instance (singleton)
_redis_checkpointer: Optional[AsyncRedisSaver] = None
_checkpointer_initialized: bool = False


async def get_redis_checkpointer() -> AsyncRedisSaver:
    """
    Get or create global AsyncRedisSaver instance for LangGraph checkpointing.

    Uses singleton pattern to reuse Redis connection across all agents.
    Automatically calls asetup() on first initialization to create Redis indices.

    Returns:
        AsyncRedisSaver instance connected to configured Redis

    Example:
        ```python
        checkpointer = await get_redis_checkpointer()
        graph = builder.compile(checkpointer=checkpointer)

        config = {"configurable": {"thread_id": "user_123"}}
        result = await graph.ainvoke(input_data, config)
        ```

    Note:
        - Reads REDIS_URL from environment (default: redis://localhost:6379/0)
        - Connection is persistent across all agent invocations
        - Call close_redis_checkpointer() on application shutdown
    """
    global _redis_checkpointer, _checkpointer_initialized

    if _redis_checkpointer is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        logger.info(f"Initializing AsyncRedisSaver with URL: {redis_url}")

        # Create checkpointer from connection string
        _redis_checkpointer = AsyncRedisSaver.from_conn_string(redis_url)

        # Initialize Redis indices for checkpoint storage
        if not _checkpointer_initialized:
            try:
                await _redis_checkpointer.asetup()
                _checkpointer_initialized = True
                logger.info("✅ Redis checkpointer initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Redis checkpointer: {e}")
                _redis_checkpointer = None
                raise

    return _redis_checkpointer


async def close_redis_checkpointer():
    """
    Close global Redis checkpointer connection.

    Call this on application shutdown to clean up resources.

    Example:
        ```python
        @app.on_event("shutdown")
        async def shutdown():
            await close_redis_checkpointer()
        ```
    """
    global _redis_checkpointer, _checkpointer_initialized

    if _redis_checkpointer:
        try:
            # AsyncRedisSaver uses context manager pattern, close via aexit
            await _redis_checkpointer.__aexit__(None, None, None)
            logger.info("Redis checkpointer closed successfully")
        except Exception as e:
            logger.error(f"Error closing Redis checkpointer: {e}")
        finally:
            _redis_checkpointer = None
            _checkpointer_initialized = False


# ========== Streaming Configuration Helpers ==========

StreamMode = Literal["messages", "updates", "values", "custom"]


def create_streaming_config(
    thread_id: str,
    stream_mode: StreamMode = "messages",
    checkpoint_ns: str = "",
    recursion_limit: int = 25,
    **extra_config
) -> Dict[str, Any]:
    """
    Create standardized streaming configuration for LangGraph execution.

    Args:
        thread_id: Unique identifier for conversation/session (required for checkpointing)
        stream_mode: Streaming mode - "messages" (token-by-token), "updates" (node-level),
                     "values" (full state), "custom" (custom data)
        checkpoint_ns: Optional namespace for filtering checkpoints
        recursion_limit: Maximum graph iterations before termination (default: 25)
        **extra_config: Additional configuration parameters

    Returns:
        Configuration dict ready for graph.stream() or graph.ainvoke()

    Example:
        ```python
        config = create_streaming_config(
            thread_id="user_123_conversation_456",
            stream_mode="messages",  # Token streaming for real-time response
        )

        async for message, metadata in graph.astream(input_data, config):
            if message.content:
                print(message.content, end="", flush=True)
        ```

    Stream Modes:
        - "messages": Token-by-token LLM output (for real-time chat)
        - "updates": Node-level state updates (for progress tracking)
        - "values": Full state snapshots after each node (for debugging)
        - "custom": Custom streaming data via writer()
    """
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": checkpoint_ns,
        },
        "recursion_limit": recursion_limit,
        **extra_config
    }

    # Note: stream_mode is passed as parameter to stream(), not in config dict
    # This function just creates the config dict for thread management
    return config


def get_checkpoint_config(thread_id: str, checkpoint_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Create configuration dict for checkpoint retrieval.

    Args:
        thread_id: Thread identifier
        checkpoint_id: Optional specific checkpoint ID to retrieve

    Returns:
        Config dict for checkpoint operations

    Example:
        ```python
        # Get latest checkpoint for thread
        config = get_checkpoint_config("user_123")
        checkpointer = await get_redis_checkpointer()
        checkpoint = await checkpointer.aget(config)

        # Get specific checkpoint
        config = get_checkpoint_config("user_123", "checkpoint_abc")
        checkpoint = await checkpointer.aget(config)
        ```
    """
    config = {
        "configurable": {
            "thread_id": thread_id,
            "checkpoint_ns": "",
        }
    }

    if checkpoint_id:
        config["configurable"]["checkpoint_id"] = checkpoint_id

    return config


# ========== State Reducers ==========

def merge_metadata(existing: Dict[str, Any], new: Dict[str, Any]) -> Dict[str, Any]:
    """
    Custom reducer for merging metadata dicts without overwriting.

    Merging strategy:
    - Numeric values (int, float): Sum together
    - Lists: Concatenate
    - Other types: New value overwrites existing

    Args:
        existing: Current metadata dict
        new: New metadata dict to merge

    Returns:
        Merged metadata dict

    Example:
        ```python
        from typing import Annotated
        from typing_extensions import TypedDict

        class AgentState(TypedDict):
            metadata: Annotated[Dict[str, Any], merge_metadata]

        # When nodes update metadata concurrently:
        # Node A: {"total_cost_usd": 0.001, "models": ["cerebras"]}
        # Node B: {"total_cost_usd": 0.002, "models": ["claude"]}
        # Result: {"total_cost_usd": 0.003, "models": ["cerebras", "claude"]}
        ```

    Note:
        For most use cases, add_messages reducer (built-in) and operator.add
        are sufficient. Use this for custom metadata merging logic.
    """
    merged = existing.copy()

    for key, value in new.items():
        if key in merged:
            existing_value = merged[key]

            # Sum numeric values (e.g., costs, token counts)
            if isinstance(existing_value, (int, float)) and isinstance(value, (int, float)):
                merged[key] = existing_value + value

            # Concatenate lists (e.g., model names, tool calls)
            elif isinstance(existing_value, list) and isinstance(value, list):
                merged[key] = existing_value + value

            # Overwrite for other types (dicts, strings, etc.)
            else:
                merged[key] = value
        else:
            # New key, add it
            merged[key] = value

    return merged


# ========== Error Handling Wrappers ==========

def wrap_node_with_resilience(
    func: Callable,
    circuit_breaker: Optional[CircuitBreaker] = None,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0
) -> Callable:
    """
    Wrap a LangGraph node function with circuit breaker and exponential backoff retry.

    Integrates existing resilience patterns (CircuitBreaker, RetryHandler) with
    LangGraph node execution. Useful for nodes that call external APIs.

    Args:
        func: Async node function to wrap (must accept state dict)
        circuit_breaker: Optional CircuitBreaker instance for fault isolation
        max_retries: Maximum retry attempts (default: 3)
        base_delay: Base delay in seconds for exponential backoff (default: 1.0)
        max_delay: Maximum delay between retries (default: 60.0)

    Returns:
        Wrapped async function with resilience patterns

    Example:
        ```python
        from app.services.circuit_breaker import CircuitBreaker

        # Create circuit breaker for external API
        apollo_breaker = CircuitBreaker(
            name="apollo_api",
            failure_threshold=5,
            recovery_timeout=60
        )

        async def enrich_with_apollo(state):
            # Call Apollo API
            result = await apollo_client.enrich(state["email"])
            return {"enriched_data": result}

        # Wrap node with resilience
        resilient_enrich = wrap_node_with_resilience(
            enrich_with_apollo,
            circuit_breaker=apollo_breaker,
            max_retries=3
        )

        # Add to graph
        builder.add_node("enrich", resilient_enrich)
        ```

    Behavior:
        1. If circuit breaker provided: Execute via circuit_breaker.call()
           - Automatic state management (CLOSED/OPEN/HALF_OPEN transitions)
           - Fail-fast when circuit is OPEN
        2. If no circuit breaker: Manual retry logic with exponential backoff
        3. Retry on failure up to max_retries attempts
        4. Raise exception after all retries exhausted
    """
    @wraps(func)
    async def wrapped(state: Dict[str, Any]) -> Dict[str, Any]:
        if circuit_breaker:
            # Use circuit breaker with manual retry logic
            last_exception = None

            for attempt in range(max_retries):
                try:
                    # Execute via circuit breaker (handles state checking and recording)
                    result = await circuit_breaker.call(func, state)
                    logger.debug(f"Node {func.__name__} succeeded on attempt {attempt + 1}")
                    return result

                except Exception as e:
                    last_exception = e

                    # Check if we should retry
                    if attempt < max_retries - 1:
                        # Calculate exponential backoff delay
                        delay = min(base_delay * (2 ** attempt), max_delay)

                        logger.warning(
                            f"Node {func.__name__} failed on attempt {attempt + 1}/{max_retries}: {str(e)}. "
                            f"Retrying after {delay}s..."
                        )

                        await asyncio.sleep(delay)
                    else:
                        # Final attempt failed
                        logger.error(
                            f"Node {func.__name__} failed after {max_retries} attempts: {str(e)}",
                            exc_info=True
                        )

            # All retries exhausted
            raise last_exception

        else:
            # Manual retry logic without circuit breaker
            last_exception = None

            for attempt in range(max_retries):
                try:
                    result = await func(state)
                    logger.debug(f"Node {func.__name__} succeeded on attempt {attempt + 1}")
                    return result

                except Exception as e:
                    last_exception = e

                    if attempt < max_retries - 1:
                        delay = min(base_delay * (2 ** attempt), max_delay)

                        logger.warning(
                            f"Node {func.__name__} failed on attempt {attempt + 1}/{max_retries}: {str(e)}. "
                            f"Retrying after {delay}s..."
                        )

                        await asyncio.sleep(delay)
                    else:
                        logger.error(
                            f"Node {func.__name__} failed after {max_retries} attempts: {str(e)}",
                            exc_info=True
                        )

            # All retries exhausted
            raise last_exception

    return wrapped


# ========== Graph Construction Helpers ==========

def create_agent_graph(state_schema: type) -> StateGraph:
    """
    Create a new StateGraph with the given state schema.

    Simple factory function for consistent graph initialization.

    Args:
        state_schema: TypedDict class defining the agent state structure

    Returns:
        New StateGraph instance ready for node/edge configuration

    Example:
        ```python
        from app.services.langgraph.state_schemas import QualificationAgentState
        from langgraph.graph import START, END

        # Create graph
        graph = create_agent_graph(QualificationAgentState)

        # Add nodes and edges
        graph.add_node("qualify", qualify_node)
        graph.add_edge(START, "qualify")
        graph.add_edge("qualify", END)

        # Compile with checkpointing
        checkpointer = await get_redis_checkpointer()
        compiled = graph.compile(checkpointer=checkpointer)
        ```
    """
    return StateGraph(state_schema)


async def compile_agent_graph(
    builder: StateGraph,
    enable_checkpointing: bool = True
) -> Any:
    """
    Compile a StateGraph with optional checkpointing.

    Args:
        builder: StateGraph instance with nodes and edges configured
        enable_checkpointing: Whether to enable Redis checkpointing (default: True)

    Returns:
        Compiled graph ready for invocation

    Example:
        ```python
        builder = create_agent_graph(QualificationAgentState)
        # ... add nodes and edges ...

        # Compile with checkpointing
        graph = await compile_agent_graph(builder, enable_checkpointing=True)

        # Or compile without checkpointing (for testing)
        graph = await compile_agent_graph(builder, enable_checkpointing=False)
        ```
    """
    if enable_checkpointing:
        checkpointer = await get_redis_checkpointer()
        return builder.compile(checkpointer=checkpointer)
    else:
        return builder.compile()


# ========== Utility Functions ==========

def get_thread_id_for_lead(lead_id: int, session_id: Optional[str] = None) -> str:
    """
    Generate consistent thread ID for lead-based conversations.

    Args:
        lead_id: Lead database ID
        session_id: Optional session identifier for multiple conversations

    Returns:
        Thread ID string for checkpointing

    Example:
        ```python
        # Single conversation per lead
        thread_id = get_thread_id_for_lead(lead_id=123)
        # Result: "lead_123"

        # Multiple sessions per lead
        thread_id = get_thread_id_for_lead(lead_id=123, session_id="call_456")
        # Result: "lead_123_call_456"
        ```
    """
    if session_id:
        return f"lead_{lead_id}_{session_id}"
    else:
        return f"lead_{lead_id}"


def validate_stream_mode(mode: str) -> bool:
    """
    Validate stream mode parameter.

    Args:
        mode: Stream mode string to validate

    Returns:
        True if valid, False otherwise

    Valid Modes:
        - "messages" - Token-by-token LLM streaming
        - "updates" - Node-level state updates
        - "values" - Full state snapshots
        - "custom" - Custom streaming data
    """
    valid_modes = {"messages", "updates", "values", "custom"}
    return mode in valid_modes


# ========== Exports ==========

__all__ = [
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
