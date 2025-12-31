"""LangGraph API helper functions."""

from app.api.langgraph.schemas import InvokeAgentRequest
from app.services.langgraph import get_thread_id_for_lead


async def get_or_create_thread_id(request: InvokeAgentRequest) -> str:
    """
    Get thread ID from request or generate one.

    Args:
        request: Agent invocation request

    Returns:
        Thread ID string
    """
    if request.thread_id:
        return request.thread_id

    if request.lead_id:
        return get_thread_id_for_lead(request.lead_id)

    from uuid import uuid4
    return f"thread_{uuid4().hex[:16]}"


# Valid agent types for validation
VALID_AGENTS = [
    "qualification",
    "enrichment",
    "growth",
    "marketing",
    "bdr",
    "conversation"
]
