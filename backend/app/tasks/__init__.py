"""
Celery tasks package

This package contains all async task definitions for the sales agent platform,
including agent execution, workflow orchestration, and background processing.
"""
from app.tasks.agent_tasks import (
    execute_agent_task,
    execute_workflow_task,
    qualify_lead_async,
    enrich_lead_async,
    ping_task
)
from app.tasks.close_sync import (
    sync_close_activities,
    poll_email_replies,
    advance_sequences
)

__all__ = [
    "execute_agent_task",
    "execute_workflow_task",
    "qualify_lead_async",
    "enrich_lead_async",
    "ping_task",
    "sync_close_activities",
    "poll_email_replies",
    "advance_sequences"
]
