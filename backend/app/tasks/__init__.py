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
from app.tasks.dropin_tasks import (
    run_dropin_enrichment,
    run_dropin_batch
)
from app.tasks.linkedin_tasks import (
    send_linkedin_connection,
    send_linkedin_message,
    react_to_linkedin_post,
    comment_on_linkedin_post,
    run_linkedin_daily_actions,
    queue_linkedin_connection,
    queue_linkedin_message
)

__all__ = [
    "execute_agent_task",
    "execute_workflow_task",
    "qualify_lead_async",
    "enrich_lead_async",
    "ping_task",
    "sync_close_activities",
    "poll_email_replies",
    "advance_sequences",
    "run_dropin_enrichment",
    "run_dropin_batch",
    "send_linkedin_connection",
    "send_linkedin_message",
    "react_to_linkedin_post",
    "comment_on_linkedin_post",
    "run_linkedin_daily_actions",
    "queue_linkedin_connection",
    "queue_linkedin_message"
]
