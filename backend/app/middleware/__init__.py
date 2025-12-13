"""
Middleware package for cross-cutting concerns.

Includes:
- Audit logging for security events
- AI-Core integration for LangGraph middleware and LangSmith tracing
"""
from .audit import AuditLoggingMiddleware, AuditLoggingRoute, log_security_event
from .ai_core_integration import (
    get_agent_middleware,
    get_tool_middleware,
    get_traced_llm,
    get_cached_llm,
    traced_agent,
    traced_tool,
    get_usage_callback,
    update_token_budget,
)

__all__ = [
    # Audit middleware
    "AuditLoggingMiddleware",
    "AuditLoggingRoute",
    "log_security_event",
    # AI-Core integration
    "get_agent_middleware",
    "get_tool_middleware",
    "get_traced_llm",
    "get_cached_llm",
    "traced_agent",
    "traced_tool",
    "get_usage_callback",
    "update_token_budget",
]