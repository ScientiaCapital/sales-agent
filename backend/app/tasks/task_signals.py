"""
Celery Task Signals for Agent Tracking

Automatically tracks agent task starts and completions using Celery signals.
This avoids modifying individual tasks and provides centralized tracking.
"""

import asyncio
import logging
from celery.signals import task_prerun, task_postrun, task_failure

logger = logging.getLogger(__name__)

# Task names that should be tracked (GTM agents)
TRACKED_TASKS = {
    "run_lead_scout": "lead_scout",
    "generate_morning_report": "morning_report",
    "run_sales_intel_batch": "sales_intel",
    "run_growth_campaigns": "growth_campaigns",
    "run_bdr_batch": "bdr_outreach",
    "run_icp_checker": "icp_checker",
    "run_prediction_market": "prediction_market",
    "run_morning_briefing": "morning_briefing",
    "sync_close_activities": "close_sync",
    "poll_close_replies": "reply_polling",
    "advance_sequences": "sequence_advance",
}


def _run_async(coro):
    """Run async function from sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Create a new task in the existing loop
            asyncio.ensure_future(coro)
        else:
            loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop - create one
        asyncio.run(coro)


@task_prerun.connect
def track_task_start(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    """
    Called before a task starts executing.

    Records start time and status in Redis via AgentTracker.
    """
    # Get task name (without 'app.tasks.' prefix)
    task_name = sender.name if sender else None

    if not task_name:
        return

    # Check if this is a tracked agent task
    agent_name = TRACKED_TASKS.get(task_name)
    if not agent_name:
        return

    try:
        from app.services.agent_tracker import get_agent_tracker

        async def _track():
            tracker = get_agent_tracker()
            await tracker.record_start(
                agent_name=agent_name,
                task_id=task_id,
                args={"args": args, "kwargs": kwargs} if args or kwargs else None
            )

        _run_async(_track())
        logger.info(f"TaskSignal: Started tracking {agent_name} ({task_id})")

    except Exception as e:
        logger.warning(f"TaskSignal: Failed to track task start: {e}")


@task_postrun.connect
def track_task_completion(sender=None, task_id=None, task=None, args=None, kwargs=None,
                          retval=None, state=None, **extra):
    """
    Called after a task finishes executing (success or failure).

    Records completion time, duration, and result in Redis.
    """
    task_name = sender.name if sender else None

    if not task_name:
        return

    agent_name = TRACKED_TASKS.get(task_name)
    if not agent_name:
        return

    try:
        from app.services.agent_tracker import get_agent_tracker

        # Determine if this was an error
        is_error = state == 'FAILURE'
        error_msg = str(retval) if is_error and retval else None

        # Convert result to dict if possible
        result = None
        if not is_error and retval:
            if isinstance(retval, dict):
                result = retval
            else:
                result = {"result": str(retval)}

        async def _track():
            tracker = get_agent_tracker()
            await tracker.record_completion(
                agent_name=agent_name,
                task_id=task_id,
                result=result,
                error=error_msg
            )

        _run_async(_track())
        logger.info(f"TaskSignal: Completed tracking {agent_name} ({task_id}) - state: {state}")

    except Exception as e:
        logger.warning(f"TaskSignal: Failed to track task completion: {e}")


@task_failure.connect
def track_task_failure(sender=None, task_id=None, exception=None, traceback=None, **extra):
    """
    Called when a task raises an exception.

    Records error details in Redis.
    """
    task_name = sender.name if sender else None

    if not task_name:
        return

    agent_name = TRACKED_TASKS.get(task_name)
    if not agent_name:
        return

    try:
        from app.services.agent_tracker import get_agent_tracker

        error_msg = f"{type(exception).__name__}: {str(exception)}"

        async def _track():
            tracker = get_agent_tracker()
            await tracker.record_completion(
                agent_name=agent_name,
                task_id=task_id,
                error=error_msg
            )

        _run_async(_track())
        logger.error(f"TaskSignal: Tracked failure for {agent_name} ({task_id}): {error_msg}")

    except Exception as e:
        logger.warning(f"TaskSignal: Failed to track task failure: {e}")


def register_signals():
    """
    Explicitly register signals (called from celery_app.py).

    Note: Celery signals auto-register when this module is imported,
    but this function is provided for explicit initialization.
    """
    logger.info("TaskSignal: Agent tracking signals registered")
    logger.info(f"TaskSignal: Tracking {len(TRACKED_TASKS)} agent tasks")
