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

# LangSmith tracing configuration - READ FROM .env
# Set LANGCHAIN_TRACING_V2=true in .env to enable tracing
# Your LangSmith API key should be in LANGSMITH_API_KEY
langsmith_enabled = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
os.environ["LANGCHAIN_TRACING_V2"] = "true" if langsmith_enabled else "false"
os.environ["LANGSMITH_TRACING"] = "true" if langsmith_enabled else "false"
os.environ["LANGCHAIN_TRACING"] = "true" if langsmith_enabled else "false"

# Suppress LangSmith warning logs when tracing is disabled
import logging
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)
from celery import Celery, signals
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
        "app.tasks.icp_tasks",
        "app.tasks.prediction_tasks",
        "app.tasks.close_sync",
        "app.tasks.briefing_tasks",
        "app.tasks.scout_tasks",
        "app.tasks.ranking_tasks",
        "app.tasks.sync_tasks",
        "app.tasks.dropin_tasks",
        "app.tasks.enrichment_tasks",  # Website enrichment
        "app.tasks.elite_team_tasks",  # Trifecta Hunter Elite Squad
        "app.tasks.intake_commander_tasks",  # IntakeCommander (separate from elite_team_tasks)
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
        # ICP Checker tasks
        "app.tasks.icp_tasks.run_icp_checker_task": {"queue": "default"},
        "app.tasks.icp_tasks.recheck_icp_for_company_task": {"queue": "default"},
        "app.tasks.icp_tasks.get_icp_stats_task": {"queue": "default"},
        # Prediction Market tasks
        "app.tasks.prediction_tasks.run_prediction_market_task": {"queue": "default"},
        "app.tasks.prediction_tasks.run_morning_briefing_task": {"queue": "workflows"},  # OLD - kept for backward compat
        "app.tasks.prediction_tasks.log_lead_signal_task": {"queue": "default"},
        "app.tasks.prediction_tasks.get_prediction_stats_task": {"queue": "default"},
        # Briefing tasks
        "app.tasks.briefing_tasks.run_morning_briefing_task": {"queue": "workflows"},  # NEW consolidated briefing
        # Scout tasks (Phase 1 consolidation)
        "app.tasks.scout_tasks.run_scout_cycle": {"queue": "default"},
        "app.tasks.scout_tasks.run_scout_for_company": {"queue": "default"},
        "app.tasks.scout_tasks.run_scout_batch": {"queue": "default"},
        # Ranking tasks (Phase 1 consolidation)
        "app.tasks.ranking_tasks.run_ranking_cycle_task": {"queue": "default"},
        "app.tasks.ranking_tasks.run_ranking_for_company_task": {"queue": "default"},
        "app.tasks.ranking_tasks.get_ranking_stats": {"queue": "default"},
        # Sync tasks (Phase 1 consolidation)
        "run_sync_cycle": {"queue": "crm_sync"},
        "sync_single_activity": {"queue": "crm_sync"},
        # Drop-in tasks (on-demand only, no schedule)
        "app.tasks.dropin_tasks.run_dropin_enrichment": {"queue": "enrichment"},
        "app.tasks.dropin_tasks.run_dropin_batch": {"queue": "enrichment"},
        # Website enrichment tasks (scheduled)
        "app.tasks.enrichment_tasks.run_website_enrichment_batch": {"queue": "enrichment"},
        "app.tasks.enrichment_tasks.run_priority_enrichment": {"queue": "enrichment"},
        # Close CRM sync tasks
        "app.tasks.close_sync.sync_close_activities": {"queue": "crm_sync"},
        "app.tasks.close_sync.poll_email_replies": {"queue": "crm_sync"},
        "app.tasks.close_sync.advance_sequences": {"queue": "workflows"},
        # Elite Team tasks - Trifecta Hunter Squad
        "app.tasks.elite_team_tasks.run_signal_scout": {"queue": "default"},
        "app.tasks.elite_team_tasks.run_deep_hunter": {"queue": "workflows"},
        "app.tasks.elite_team_tasks.run_intake_commander": {"queue": "default"},
        "app.tasks.elite_team_tasks.process_scraping_order": {"queue": "workflows"},
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
        # ========== PHASE 1 CONSOLIDATED AGENTS ==========
        # Scout Agent - autonomous discovery every 30 minutes
        "scout-agent-every-30-min": {
            "task": "app.tasks.scout_tasks.run_scout_cycle",
            "schedule": 1800.0,  # 30 minutes in seconds
            "args": (10, True, None),  # limit=10, require_domain=True, icp_tier=None
            "options": {"queue": "default"},
        },
        # Ranking Agent - re-rank leads every 10 minutes
        "ranking-agent-every-10-min": {
            "task": "app.tasks.ranking_tasks.run_ranking_cycle_task",
            "schedule": 600.0,  # 10 minutes in seconds
            "args": (100,),  # Re-rank up to 100 companies per cycle
            "options": {"queue": "default"},
        },
        # Sync Agent - sync Close CRM activities every 5 minutes
        "sync-agent-every-5-min": {
            "task": "run_sync_cycle",
            "schedule": 300.0,  # 5 minutes in seconds
            "options": {"queue": "crm_sync"},
        },
        # Briefing Agent - 7:30 AM EST (12:30 UTC)
        "briefing-agent-730am-est": {
            "task": "app.tasks.briefing_tasks.run_morning_briefing_task",
            "schedule": crontab(hour=12, minute=30),  # 7:30 AM EST = 12:30 UTC
            "args": (10,),  # Top 10 leads
            "options": {"queue": "workflows"},
        },
        # ========== OLD SCHEDULES (COMMENTED FOR BACKWARD COMPAT) ==========
        # OLD: Lead Scout - replaced by scout-agent-every-30-min
        # "lead-scout-every-30-min": {
        #     "task": "run_lead_scout",
        #     "schedule": 1800.0,
        #     "args": (10, True, None),
        #     "options": {"queue": "default"},
        # },
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
        # ========== ICP CHECKER SCHEDULE ==========
        # ICP Checker - every 15 minutes
        # Recalculates ICP scores for companies with updated data
        "icp-checker-every-15-min": {
            "task": "run_icp_checker",
            "schedule": 900.0,  # 15 minutes in seconds
            "args": (100,),  # Check up to 100 companies per run
            "options": {"queue": "default"},
        },
        # ========== PREDICTION AGENT SCHEDULE ==========
        # PredictionAgent - every 12 hours (was 5 min, too heavy)
        # Ranks leads by call-worthiness for Sr. BDR cold outbound
        "prediction-agent-twice-daily": {
            "task": "run_prediction_market",  # Task name kept for backward compat
            "schedule": crontab(hour="6,18", minute=0),  # 6 AM and 6 PM CST
            "args": (1000,),  # Rank up to 1000 companies per run
            "options": {"queue": "default"},
        },
        # ========== WEBSITE ENRICHMENT SCHEDULE ==========
        # Continuous website enrichment - every 5 minutes
        # Scrapes contractor websites for ATL contacts, OEMs, service areas
        "website-enrichment-continuous": {
            "task": "run_website_enrichment_batch",
            "schedule": 300.0,  # 5 minutes in seconds
            "args": (5,),  # 5 companies per batch
            "options": {"queue": "enrichment"},
        },
        # ========== CONSOLIDATED BRIEFING SCHEDULE ==========
        # OLD: Morning Briefing - replaced by briefing-agent-730am-est above
        # "morning-briefing-730am-est": {
        #     "task": "run_morning_briefing",
        #     "schedule": crontab(hour=12, minute=30),
        #     "args": (10,),
        #     "options": {"queue": "workflows"},
        # },
        # ========== CLOSE CRM AUTOMATION SCHEDULES ==========
        # Sync Close activities (emails, SMS, calls) every 15 minutes
        "sync-close-activities-every-15-min": {
            "task": "sync_close_activities",
            "schedule": crontab(minute="*/15"),  # Every 15 minutes
            "options": {"queue": "crm_sync"},
        },
        # Poll for email replies every 5 minutes (fallback to webhook)
        "poll-email-replies-every-5-min": {
            "task": "poll_email_replies",
            "schedule": crontab(minute="*/5"),  # Every 5 minutes
            "options": {"queue": "crm_sync"},
        },
        # Advance sequences every hour at :00
        "advance-sequences-hourly": {
            "task": "advance_sequences",
            "schedule": crontab(minute=0),  # Every hour at :00
            "options": {"queue": "workflows"},
        },
        # ========== ELITE TEAM SCHEDULES - Trifecta Hunter Squad ==========
        # Signal Scout - detect market signals hourly at :15
        "elite-signal-scout-hourly": {
            "task": "run_signal_scout",
            "schedule": crontab(minute=15),  # :15 past each hour
            "options": {"queue": "default"},
        },
        # Intake Commander - process incoming leads every 60 seconds
        "elite-intake-commander-continuous": {
            "task": "run_intake_commander",
            "schedule": 60.0,  # Every 60 seconds
            "args": (100,),  # Process up to 100 items per cycle
            "options": {"queue": "default"},
        },
        # Deep Hunter is event-driven (triggered by Signal Scout orders)
        # No scheduled task - runs via process_scraping_order when orders arrive
    },
)


# ========== Agent Tracking Configuration ==========
# Map task names to agent names for BDR Cockpit tracking
TRACKED_AGENTS = {
    # Phase 1 consolidated agents
    "run_scout_cycle": "scout_agent",
    "run_ranking_cycle": "ranking_agent",
    "run_sync_cycle": "sync_agent",
    "run_morning_briefing": "briefing_agent",
    # Legacy agents (kept for backward compatibility)
    "run_lead_scout": "lead_scout",  # OLD - replaced by run_scout_cycle
    "generate_morning_report": "morning_report",  # OLD - legacy task
    "run_sales_intel_batch": "sales_intel",
    "run_growth_campaigns": "growth_campaigns",
    "run_bdr_batch": "bdr_outreach",
    "run_icp_checker": "icp_checker",
    "run_prediction_market": "prediction_agent",  # Renamed from prediction_market
    "sync_close_activities": "close_sync",
    "poll_email_replies": "reply_polling",
    "advance_sequences": "sequence_advance",
    # Elite Team - Trifecta Hunter Squad
    "run_signal_scout": "signal_scout",
    "run_deep_hunter": "deep_hunter",
    "run_intake_commander": "intake_commander",
    "process_scraping_order": "deep_hunter",  # Maps to deep_hunter
}


def _run_async_tracking(coro):
    """Run async tracking without blocking the worker."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        asyncio.run(coro)
    except Exception as e:
        logger.debug(f"Async tracking error (non-blocking): {e}")


# Task lifecycle hooks for logging AND agent tracking
@task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """Log when a task starts execution and track agent starts."""
    task_name = task.name if task else None
    logger.info(f"Task starting: {task_name} (ID: {task_id})")

    # Track agent starts in Redis
    agent_name = TRACKED_AGENTS.get(task_name)
    if agent_name:
        try:
            from app.services.agent_tracker import get_agent_tracker

            async def _track_start():
                tracker = get_agent_tracker()
                await tracker.record_start(
                    agent_name=agent_name,
                    task_id=task_id,
                    args={"args": args, "kwargs": kwargs} if args or kwargs else None
                )

            _run_async_tracking(_track_start())
        except Exception as e:
            logger.debug(f"Failed to track agent start: {e}")


@task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra):
    """Log when a task completes and track agent completions."""
    task_name = task.name if task else None
    logger.info(f"Task completed: {task_name} (ID: {task_id})")

    # Track agent completions in Redis
    agent_name = TRACKED_AGENTS.get(task_name)
    if agent_name:
        try:
            from app.services.agent_tracker import get_agent_tracker

            # Convert result to dict if possible
            result = None
            if retval:
                if isinstance(retval, dict):
                    result = retval
                else:
                    result = {"result": str(retval)[:500]}  # Truncate large results

            async def _track_completion():
                tracker = get_agent_tracker()
                await tracker.record_completion(
                    agent_name=agent_name,
                    task_id=task_id,
                    result=result
                )

            _run_async_tracking(_track_completion())
        except Exception as e:
            logger.debug(f"Failed to track agent completion: {e}")


@task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, **extra):
    """Log task failures and track agent errors."""
    task_name = sender.name if sender else "unknown"
    logger.error(f"Task failed: {task_name} (ID: {task_id}) - {str(exception)}", exc_info=True)

    # Track agent failures in Redis
    agent_name = TRACKED_AGENTS.get(task_name)
    if agent_name:
        try:
            from app.services.agent_tracker import get_agent_tracker

            error_msg = f"{type(exception).__name__}: {str(exception)[:500]}"

            async def _track_failure():
                tracker = get_agent_tracker()
                await tracker.record_completion(
                    agent_name=agent_name,
                    task_id=task_id,
                    error=error_msg
                )

            _run_async_tracking(_track_failure())
        except Exception as e:
            logger.debug(f"Failed to track agent failure: {e}")


# ========== Event-Driven Agent Triggers ==========
# Listen for task success events to trigger dependent agents

@signals.task_success.connect
def handle_task_success(sender=None, result=None, **kwargs):
    """
    Handle task success events to trigger dependent agent workflows.

    Event-driven patterns:
    - company_enriched -> trigger ranking for that company
    - tier_upgraded to PLATINUM/GOLD -> trigger outreach
    """
    if not isinstance(result, dict) or "event" not in result:
        return

    event_type = result.get("event")

    try:
        # Pattern 1: Company enriched -> re-rank immediately
        if event_type == "company_enriched":
            from app.tasks.ranking_tasks import run_ranking_for_company_task
            company_ids = result.get("companies", [])
            for company_id in company_ids:
                logger.info(f"Triggering ranking for enriched company: {company_id}")
                run_ranking_for_company_task.delay(company_id)

        # Pattern 2: Tier upgraded to HOT -> queue outreach
        elif event_type == "tier_upgraded":
            new_tier = result.get("new_tier")
            if new_tier in ["PLATINUM", "GOLD"]:
                # Trigger outreach workflow for HOT leads
                # Note: This assumes outreach_tasks exists - adjust if needed
                try:
                    from app.tasks.agent_tasks import run_bdr_outreach_task
                    company_id = result.get("company_id")
                    logger.info(f"Triggering outreach for HOT lead: {company_id} (tier: {new_tier})")
                    run_bdr_outreach_task.delay(company_id)
                except ImportError:
                    logger.debug("Outreach task not found - skipping outreach trigger")

        # Pattern 3: Research completed -> update intelligence
        elif event_type == "research_completed":
            company_id = result.get("company_id")
            logger.info(f"Research completed for {company_id} - intelligence updated")
            # Future: Trigger sales intel extraction

    except Exception as e:
        logger.error(f"Error in event handler for {event_type}: {e}", exc_info=True)


if __name__ == "__main__":
    celery_app.start()
