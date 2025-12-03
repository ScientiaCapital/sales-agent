"""
Celery application configuration for async task processing

This module sets up the Celery application for multi-agent workflow orchestration,
lead processing, and background job execution.

Queue Structure:
    - default: General tasks
    - workflows: Multi-agent workflows
    - enrichment: Lead enrichment tasks
    - crm_sync: CRM synchronization
    - batch_priority_high: High priority batch leads (ICP Platinum/Gold)
    - batch_priority_medium: Medium priority batch leads (ICP Silver)
    - batch_priority_low: Low priority batch leads (ICP Bronze)
    - batch_dlq: Dead letter queue for failed batch leads
"""
# Load environment variables FIRST
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env', override=True)

import os
from celery import Celery
from celery.schedules import crontab
from celery.signals import task_prerun, task_postrun, task_failure
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Initialize Celery app
celery_app = Celery(
    "sales_agent",
    broker=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    backend=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
    include=[
        "app.tasks.agent_tasks",
        "app.tasks.batch_tasks",
    ]
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
        # Agent tasks
        "app.tasks.agent_tasks.execute_agent_task": {"queue": "default"},
        "app.tasks.agent_tasks.execute_workflow_task": {"queue": "workflows"},
        "app.tasks.agent_tasks.qualify_lead_async": {"queue": "default"},
        "app.tasks.agent_tasks.enrich_lead_async": {"queue": "enrichment"},
        "app.tasks.agent_tasks.generate_report_async": {"queue": "workflows"},
        "app.tasks.agent_tasks.batch_generate_reports": {"queue": "workflows"},
        "app.tasks.agent_tasks.sync_crm_contacts": {"queue": "crm_sync"},
        "app.tasks.agent_tasks.run_lead_scout_task": {"queue": "default"},
        # SalesIntel + Growth agent tasks
        "app.tasks.agent_tasks.run_sales_intel_batch_task": {"queue": "workflows"},
        "app.tasks.agent_tasks.run_growth_campaigns_task": {"queue": "workflows"},
        # BDR agent tasks - human-in-loop with Slack
        "app.tasks.agent_tasks.run_bdr_outreach_task": {"queue": "workflows"},
        "app.tasks.agent_tasks.resume_bdr_outreach_task": {"queue": "workflows"},
        "app.tasks.agent_tasks.run_bdr_batch_task": {"queue": "workflows"},
        # Batch tasks - routed by priority
        "app.tasks.batch_tasks.start_batch": {"queue": "default"},
        "app.tasks.batch_tasks.process_single_lead": {"queue": "batch_priority_medium"},
        "app.tasks.batch_tasks.batch_finalize": {"queue": "default"},
        "app.tasks.batch_tasks.pause_batch": {"queue": "default"},
        "app.tasks.batch_tasks.resume_batch": {"queue": "default"},
        "app.tasks.batch_tasks.cancel_batch": {"queue": "default"},
    },

    # Rate limiting (prevent API quota exhaustion)
    task_annotations={
        "app.tasks.agent_tasks.execute_agent_task": {"rate_limit": "10/m"},  # 10 per minute
        "app.tasks.agent_tasks.qualify_lead_async": {"rate_limit": "20/m"},
        # Batch tasks - strict rate limits to protect Apollo/Hunter quotas
        "app.tasks.batch_tasks.process_single_lead": {"rate_limit": "5/m"},  # 5 leads per minute max
    },

    # Queue definitions for batch processing
    task_queues={
        "default": {},
        "workflows": {},
        "enrichment": {},
        "crm_sync": {},
        "batch_priority_high": {"x-max-priority": 10},
        "batch_priority_medium": {"x-max-priority": 5},
        "batch_priority_low": {"x-max-priority": 1},
        "batch_dlq": {},
    },

    # Periodic task schedule (Celery Beat)
    beat_schedule={
        # Lead Scout - autonomous discovery every 30 minutes
        "lead-scout-every-30-min": {
            "task": "run_lead_scout",
            "schedule": 1800.0,  # 30 minutes in seconds
            "args": (10, True, None),  # limit=10, require_domain=True, icp_tier=None
            "options": {"queue": "default"},
        },
        # Morning Report - daily at 9 AM EST (14:00 UTC)
        "morning-report-9am-est": {
            "task": "generate_morning_report",
            "schedule": crontab(hour=14, minute=0),  # 9 AM EST = 14:00 UTC
            "args": (24, 10, True),  # hours_back=24, top_n=10, save_to_file=True
            "options": {"queue": "workflows"},
        },
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
        # ========== NEW AGENT SCHEDULES ==========
        # SalesIntel - extract personal hooks hourly at :30
        # Runs on leads with ai_company_story but no ai_personal_hooks
        "sales-intel-hourly": {
            "task": "run_sales_intel_batch",
            "schedule": crontab(minute=30),  # :30 past each hour
            "args": (10,),  # 10 leads per run
            "options": {"queue": "workflows"},
        },
        # Growth Campaigns - daily at 10 AM EST (15:00 UTC)
        # Runs 5-cycle campaigns for HOT leads with ICP score >= 75
        "growth-campaigns-daily": {
            "task": "run_growth_campaigns",
            "schedule": crontab(hour=15, minute=0),  # 10 AM EST = 15:00 UTC
            "args": ("book_meeting", 5),  # goal=book_meeting, max_leads=5
            "options": {"queue": "workflows"},
        },
        # BDR Outreach - every hour on the hour
        # Drafts emails for HOT leads, sends Slack notifications for approval
        "bdr-outreach-hourly": {
            "task": "run_bdr_batch",
            "schedule": crontab(minute=0),  # Top of each hour
            "args": (3,),  # 3 leads per hour
            "options": {"queue": "workflows"},
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
