"""
Lang-Core Integration for Sales-Agent.

Provides easy access to lang-core middleware, LangSmith tracing, and multi-provider
LLM selection for LangGraph agents.

Usage:
    from app.middleware.lang_core_integration import (
        get_agent_middleware,
        get_traced_llm,
        traced_agent,
    )

    # Use middleware in agent definition
    middleware = get_agent_middleware(budget=50000)

    # Get LLM with tracing
    llm = get_traced_llm(priority="speed")

    # Decorate agent functions
    @traced_agent("MyAgent", tags=["sales"])
    async def run_my_agent(...):
        ...
"""

import logging
import os
from functools import lru_cache
from typing import Any, Callable

logger = logging.getLogger(__name__)

# Lazy imports to handle case where ai-core is not installed
_lang_core_available = None


def _check_lang_core() -> bool:
    """Check if lang-core is available."""
    global _lang_core_available
    if _lang_core_available is None:
        try:
            import lang_core
            _lang_core_available = True
        except ImportError:
            _lang_core_available = False
            logger.warning("lang-core not installed, middleware features unavailable")
    return _lang_core_available


# =============================================================================
# MIDDLEWARE CONFIGURATION
# =============================================================================


def get_agent_middleware(
    budget: int | None = None,
    enable_retry: bool = True,
    enable_cost_tracking: bool = True,
    enable_safety_filter: bool = True,
) -> list[Callable]:
    """
    Get configured middleware stack for LangGraph agents.

    Args:
        budget: Max tokens allowed (None = use env var or default)
        enable_retry: Enable retry with exponential backoff
        enable_cost_tracking: Enable cost logging to LangSmith
        enable_safety_filter: Enable PII redaction

    Returns:
        List of middleware functions for agent configuration

    Example:
        middleware = get_agent_middleware(budget=50000)
        agent = create_agent(
            model="cerebras/llama3.1-8b",
            middleware=middleware,
        )
    """
    if not _check_lang_core():
        return []

    from lang_core.middleware import (
        budget_enforcement_middleware,
        cost_tracking_middleware,
        retry_middleware,
        safety_filter_before_model,
    )

    middleware = []

    # Budget enforcement (before model call)
    if budget is not None:
        # Create a wrapper that passes the budget parameter
        def budget_check(state, runtime):
            return budget_enforcement_middleware(state, runtime, max_tokens=budget)
        middleware.append(budget_check)
    else:
        middleware.append(budget_enforcement_middleware)

    # Safety filter (PII redaction before model call)
    if enable_safety_filter:
        middleware.append(safety_filter_before_model)

    # Cost tracking (after model call)
    if enable_cost_tracking:
        middleware.append(cost_tracking_middleware)

    return middleware


def get_tool_middleware(
    max_retries: int = 2,
) -> list[Callable]:
    """
    Get middleware for tool calls in LangGraph agents.

    Args:
        max_retries: Maximum retry attempts for failed tools

    Returns:
        List of tool middleware functions
    """
    if not _check_lang_core():
        return []

    from lang_core.middleware import tool_retry_middleware

    def tool_error_handler(request, handler):
        return tool_retry_middleware(request, handler, max_retries=max_retries)

    return [tool_error_handler]


# =============================================================================
# LLM SELECTION WITH TRACING
# =============================================================================


def get_traced_llm(
    priority: str = "speed",
    temperature: float = 0.0,
    model_name: str | None = None,
) -> Any:
    """
    Get an LLM instance with LangSmith tracing and auto-selection.

    Args:
        priority: One of "speed", "cost", "quality", "local"
        temperature: Model temperature (default 0.0 for deterministic)
        model_name: Specific model override (bypasses auto-selection)

    Returns:
        LangChain LLM instance with tracing configured

    Example:
        # Auto-select fastest available LLM
        llm = get_traced_llm(priority="speed")

        # Force specific model
        llm = get_traced_llm(model_name="claude-3-5-sonnet-20241022")
    """
    if not _check_lang_core():
        # Fallback to direct Cerebras if lang-core unavailable
        logger.warning("lang-core unavailable, using direct Cerebras")
        from langchain_cerebras import ChatCerebras
        return ChatCerebras(
            model="llama3.1-8b",
            temperature=temperature,
            api_key=os.getenv("CEREBRAS_API_KEY"),
        )

    from lang_core.providers import get_llm_for_task, LLMPriority
    from lang_core.langsmith import get_usage_callback

    # Map string priority to enum
    priority_map = {
        "speed": LLMPriority.SPEED,
        "cost": LLMPriority.COST,
        "quality": LLMPriority.QUALITY,
        "local": LLMPriority.LOCAL,
    }
    priority_enum = priority_map.get(priority, LLMPriority.SPEED)

    # Get LLM with callbacks for usage tracking
    llm = get_llm_for_task(
        priority=priority_enum,
        temperature=temperature,
        model_name=model_name,
    )

    return llm


@lru_cache(maxsize=4)
def get_cached_llm(priority: str, temperature: float = 0.0) -> Any:
    """
    Get a cached LLM instance (reuse across requests).

    Caches up to 4 LLM configurations to avoid recreation overhead.
    """
    return get_traced_llm(priority=priority, temperature=temperature)


# =============================================================================
# TRACING DECORATORS
# =============================================================================


def traced_agent(name: str, tags: list[str] | None = None):
    """
    Decorator to trace agent executions in LangSmith.

    Args:
        name: Agent name for tracing
        tags: Optional tags for filtering in LangSmith UI

    Example:
        @traced_agent("QualificationAgent", tags=["sales", "qualification"])
        async def run_qualification(lead_data: dict):
            ...
    """
    if not _check_lang_core():
        # No-op decorator if ai-core unavailable
        def decorator(func):
            return func
        return decorator

    from lang_core.langsmith import traced_agent as _traced_agent
    return _traced_agent(name, tags=tags or [])


def traced_tool(name: str):
    """
    Decorator to trace tool executions in LangSmith.

    Args:
        name: Tool name for tracing

    Example:
        @traced_tool("enrich_lead")
        async def enrich_lead_tool(lead_id: str):
            ...
    """
    if not _check_lang_core():
        def decorator(func):
            return func
        return decorator

    from lang_core.langsmith import traced_tool as _traced_tool
    return _traced_tool(name)


# =============================================================================
# USAGE TRACKING
# =============================================================================


def get_usage_callback():
    """
    Get a callback handler for tracking token usage across all LLM calls.

    Returns:
        UsageMetadataCallbackHandler or None if lang-core unavailable

    Example:
        callback = get_usage_callback()
        result = llm.invoke(messages, config={"callbacks": [callback]})
    """
    if not _check_lang_core():
        return None

    from lang_core.langsmith import get_usage_callback as _get_usage_callback
    return _get_usage_callback()


def update_token_budget(state: dict, new_tokens: int) -> dict:
    """
    Update cumulative token count in agent state.

    Call this after LLM calls to track total usage against budget.

    Args:
        state: Agent state dict
        new_tokens: Number of new tokens to add

    Returns:
        State update dict with new cumulative_tokens value
    """
    if not _check_lang_core():
        current = state.get("cumulative_tokens", 0)
        return {"cumulative_tokens": current + new_tokens}

    from lang_core.middleware import update_cumulative_tokens
    return update_cumulative_tokens(state, new_tokens)
