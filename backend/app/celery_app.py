"""
Celery application configuration for async task processing

This module sets up the Celery application for multi-agent workflow orchestration,
lead processing, and background job execution.
"""
import os
from celery import Celery
from celery.signals import task_prerun, task_postrun, task_failure
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Initialize Celery app
celery_app = Celery(
    "sales_agent",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=["app.tasks.agent_tasks"]
)

# Celery configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_track_started=True,  # Track when task starts (not just queued)
    task_time_limit=300,  # Hard timeout: 5 minutes
    task_soft_time_limit=240,  # Soft timeout: 4 minutes (raises SoftTimeLimitExceeded)
    task_acks_late=True,  # Acknowledge task after completion (not before)
    task_reject_on_worker_lost=True,  # Requeue if worker dies
    
    # Worker configuration
    worker_prefetch_multiplier=1,  # Only fetch 1 task at a time (prevents hoarding)
    worker_max_tasks_per_child=1000,  # Restart worker after 1000 tasks (prevent memory leaks)
    worker_disable_rate_limits=False,  # Enable rate limiting
    
    # Result backend
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store more info about tasks
    result_backend_transport_options={
        "master_name": "mymaster",
        "visibility_timeout": 3600,
    },
    
    # Retry configuration
    task_default_max_retries=3,
    task_default_retry_delay=10,  # 10 seconds base delay
    
    # Monitoring
    task_send_sent_event=True,  # Send task-sent events for monitoring
    worker_send_task_events=True,  # Enable Flower monitoring
    
    # Routing
    task_routes={
        "app.tasks.agent_tasks.execute_agent_task": {"queue": "default"},
        "app.tasks.agent_tasks.execute_workflow_task": {"queue": "workflows"},
        "app.tasks.agent_tasks.qualify_lead_async": {"queue": "default"},
        "app.tasks.agent_tasks.enrich_lead_async": {"queue": "enrichment"},
        "app.tasks.agent_tasks.generate_report_async": {"queue": "workflows"},
        "app.tasks.agent_tasks.batch_generate_reports": {"queue": "workflows"},
        "app.tasks.agent_tasks.sync_crm_contacts": {"queue": "crm_sync"},
    },
    
    # Rate limiting (prevent API quota exhaustion)
    task_annotations={
        "app.tasks.agent_tasks.execute_agent_task": {"rate_limit": "10/m"},  # 10 per minute
        "app.tasks.agent_tasks.qualify_lead_async": {"rate_limit": "20/m"},
    },

    # Periodic task schedule (Celery Beat)
    beat_schedule={
        # Close CRM - sync every 2 hours
        "sync-close-hourly": {
            "task": "sync_crm_contacts",
            "schedule": 7200.0,  # 2 hours in seconds
            "args": ("close", "bidirectional", None),
        },
        # Apollo - enrichment sync daily at 2 AM
        "sync-apollo-daily": {
            "task": "sync_crm_contacts",
            "schedule": 86400.0,  # 24 hours in seconds
            "args": ("apollo", "import", None),
        },
        # LinkedIn - profile sync daily at 3 AM
        "sync-linkedin-daily": {
            "task": "sync_crm_contacts",
            "schedule": 86400.0,  # 24 hours in seconds
            "args": ("linkedin", "import", None),
        },
    },
)


# Task lifecycle hooks for logging
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log when a task starts execution"""
    logger.info(f"Task starting: {task.name} (ID: {task_id})")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, **extra):
    """Log when a task completes successfully"""
    logger.info(f"Task completed: {task.name} (ID: {task_id})")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, **extra):
    """Log task failures"""
    logger.error(f"Task failed: {sender.name} (ID: {task_id}) - {str(exception)}", exc_info=True)


if __name__ == "__main__":
    celery_app.start()
