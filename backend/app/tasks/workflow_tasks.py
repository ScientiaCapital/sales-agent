"""
Celery tasks for Workflow Automation

This module defines background tasks for evaluating workflow rules
and detecting stage changes via polling (fallback to webhooks).

Tasks:
    - evaluate_workflow_rules: Evaluate rules for a triggered event
    - poll_stage_changes: Poll for opportunity stage changes (every 15 min)

Part of Phase 4: Workflow Automation for the Close CRM Enhancements project.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from celery.exceptions import SoftTimeLimitExceeded
import asyncio
import logging
import os

from redis import asyncio as aioredis

from app.celery_app import celery_app
from app.core.logging import setup_logging

# Supabase for data persistence
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

logger = setup_logging(__name__)


# ============================================================================
# REDIS STATE MANAGEMENT (reuse pattern from close_sync.py)
# ============================================================================

async def get_redis_client() -> aioredis.Redis:
    """Get Redis client for state tracking."""
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis = await aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    return redis


async def get_last_poll_timestamp(redis: aioredis.Redis, task_name: str) -> Optional[datetime]:
    """Get last poll timestamp from Redis."""
    try:
        key = f"workflow:last_poll:{task_name}"
        timestamp_str = await redis.get(key)
        if timestamp_str:
            return datetime.fromisoformat(timestamp_str)
        return None
    except Exception as e:
        logger.error(f"Failed to get last poll timestamp for {task_name}: {e}")
        return None


async def set_last_poll_timestamp(redis: aioredis.Redis, task_name: str, timestamp: datetime):
    """Set last poll timestamp in Redis."""
    try:
        key = f"workflow:last_poll:{task_name}"
        await redis.set(key, timestamp.isoformat(), ex=86400)  # 24 hour expiry
        logger.debug(f"Set last poll timestamp for {task_name}: {timestamp}")
    except Exception as e:
        logger.error(f"Failed to set last poll timestamp for {task_name}: {e}")


async def acquire_task_lock(redis: aioredis.Redis, task_name: str, timeout: int = 300) -> bool:
    """Acquire distributed lock for task to prevent overlapping runs."""
    try:
        key = f"workflow:lock:{task_name}"
        acquired = await redis.set(key, "locked", ex=timeout, nx=True)
        if acquired:
            logger.debug(f"Acquired lock for {task_name}")
            return True
        else:
            logger.warning(f"Lock already held for {task_name}, skipping run")
            return False
    except Exception as e:
        logger.error(f"Failed to acquire lock for {task_name}: {e}")
        return False


async def release_task_lock(redis: aioredis.Redis, task_name: str):
    """Release distributed lock."""
    try:
        key = f"workflow:lock:{task_name}"
        await redis.delete(key)
        logger.debug(f"Released lock for {task_name}")
    except Exception as e:
        logger.error(f"Failed to release lock for {task_name}: {e}")


# ============================================================================
# TASK 1: EVALUATE WORKFLOW RULES
# ============================================================================

@celery_app.task(
    name="evaluate_workflow_rules",
    bind=True,
    max_retries=3,
    default_retry_delay=30,  # 30 seconds
)
def evaluate_workflow_rules(
    self,
    trigger_type: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Evaluate workflow rules for a triggered event.

    This task is called when an event occurs (via webhook or polling)
    that may trigger workflow rules. It evaluates all active rules
    for the trigger type and queues actions for matched rules.

    Args:
        trigger_type: The type of trigger (e.g., "stage_change", "opportunity_won")
        context: Event context for rule evaluation

    Returns:
        Dict with evaluation results:
        {
            "status": "success",
            "trigger_type": "stage_change",
            "rules_evaluated": 5,
            "rules_matched": 2,
            "actions_queued": 2,
            "duration_ms": 123
        }

    Raises:
        SoftTimeLimitExceeded: If task exceeds soft time limit
    """
    start_time = datetime.utcnow()
    task_name = "evaluate_workflow_rules"

    logger.info(f"[{task_name}] Evaluating rules for trigger: {trigger_type}")
    logger.debug(f"[{task_name}] Context: {context}")

    try:
        result = asyncio.run(_evaluate_workflow_rules_async(trigger_type, context))

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            f"[{task_name}] Completed: {result['rules_matched']}/{result['rules_evaluated']} "
            f"rules matched, {result['actions_queued']} actions queued in {duration_ms}ms"
        )

        return result

    except SoftTimeLimitExceeded:
        logger.error(f"[{task_name}] Soft time limit exceeded")
        raise
    except Exception as e:
        logger.error(f"[{task_name}] Failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))


async def _evaluate_workflow_rules_async(
    trigger_type: str,
    context: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Async implementation of workflow rule evaluation.

    Args:
        trigger_type: The type of trigger
        context: Event context for rule evaluation

    Returns:
        Evaluation results dict
    """
    from app.models.database import SessionLocal
    from app.services.workflow.rule_engine import WorkflowRuleEngine

    db = SessionLocal()
    try:
        engine = WorkflowRuleEngine(db)

        # Evaluate rules
        actions = await engine.evaluate_event(trigger_type, context)

        # Queue action execution for each matched rule
        actions_queued = 0
        for action in actions:
            try:
                # Queue the action for execution
                # Note: execute_workflow_action task will be created in Plan 04-03
                # For now, we log the action and mark it as queued
                logger.info(
                    f"Action queued: {action['action_type']} from rule '{action['rule_name']}' "
                    f"(rule_id={action['rule_id']})"
                )

                # Record the execution attempt
                await engine.record_execution(action["rule_id"])
                actions_queued += 1

            except Exception as e:
                logger.error(f"Failed to queue action for rule {action['rule_id']}: {e}")

        # Count total rules evaluated
        rules_evaluated = len(await engine.get_active_rules(trigger_type))

        return {
            "status": "success",
            "trigger_type": trigger_type,
            "rules_evaluated": rules_evaluated,
            "rules_matched": len(actions),
            "actions_queued": actions_queued,
            "matched_rules": [
                {"rule_id": a["rule_id"], "rule_name": a["rule_name"], "action_type": a["action_type"]}
                for a in actions
            ],
        }

    finally:
        db.close()


# ============================================================================
# TASK 2: POLL STAGE CHANGES
# ============================================================================

@celery_app.task(
    name="poll_stage_changes",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute
)
def poll_stage_changes(self) -> Dict[str, Any]:
    """
    Poll for opportunity stage changes since last check.

    Fallback mechanism when webhooks are delayed/missed.
    Runs every 15 minutes via Celery Beat.

    This task:
    1. Gets last poll timestamp from Redis
    2. Queries crm_opportunities for updated_at > last_poll
    3. Compares current stage vs previous stage (from raw_data)
    4. For each change, evaluates workflow rules
    5. Updates last poll timestamp

    Returns:
        Dict with polling results:
        {
            "status": "success",
            "opportunities_checked": 50,
            "stage_changes_detected": 3,
            "rules_triggered": 5,
            "duration_ms": 1234
        }

    Raises:
        SoftTimeLimitExceeded: If task exceeds soft time limit
    """
    start_time = datetime.utcnow()
    task_name = "poll_stage_changes"

    logger.info(f"[{task_name}] Starting stage change polling")

    try:
        result = asyncio.run(_poll_stage_changes_async(task_name))

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            f"[{task_name}] Completed: checked {result['opportunities_checked']} opportunities, "
            f"detected {result['stage_changes_detected']} stage changes, "
            f"triggered {result['rules_triggered']} rules in {duration_ms}ms"
        )

        return result

    except SoftTimeLimitExceeded:
        logger.error(f"[{task_name}] Soft time limit exceeded")
        raise
    except Exception as e:
        logger.error(f"[{task_name}] Failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def _poll_stage_changes_async(task_name: str) -> Dict[str, Any]:
    """
    Async implementation of stage change polling.

    Queries crm_opportunities for changes and triggers workflow rules
    for any detected stage changes.

    Args:
        task_name: Task name for locking

    Returns:
        Polling results dict
    """
    redis = await get_redis_client()

    try:
        # Acquire lock to prevent overlapping runs
        if not await acquire_task_lock(redis, task_name, timeout=900):  # 15 min lock
            return {
                "status": "skipped",
                "reason": "already_running",
                "opportunities_checked": 0,
                "stage_changes_detected": 0,
                "rules_triggered": 0,
            }

        # Get last poll timestamp
        last_poll = await get_last_poll_timestamp(redis, task_name)
        if not last_poll:
            # Default to last 30 minutes on first run
            last_poll = datetime.utcnow() - timedelta(minutes=30)

        logger.info(f"[{task_name}] Polling for changes since {last_poll}")

        # Initialize Supabase client
        if not SUPABASE_AVAILABLE:
            logger.warning(f"[{task_name}] Supabase not available - skipping polling")
            return {
                "status": "error",
                "reason": "supabase_unavailable",
                "opportunities_checked": 0,
                "stage_changes_detected": 0,
                "rules_triggered": 0,
            }

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            logger.warning(f"[{task_name}] Supabase credentials missing - skipping polling")
            return {
                "status": "error",
                "reason": "supabase_credentials_missing",
                "opportunities_checked": 0,
                "stage_changes_detected": 0,
                "rules_triggered": 0,
            }

        supabase = create_client(supabase_url, supabase_key)

        opportunities_checked = 0
        stage_changes_detected = 0
        rules_triggered = 0

        # Query recently updated opportunities
        # Compare current stage with previous stage stored in raw_data
        try:
            result = supabase.table("crm_opportunities").select(
                "id, external_id, close_lead_id, status_label, pipeline_id, "
                "confidence, value, raw_data, updated_at"
            ).gt(
                "updated_at", last_poll.isoformat()
            ).order(
                "updated_at", desc=True
            ).limit(200).execute()

            opportunities = result.data or []
            opportunities_checked = len(opportunities)

            logger.info(f"[{task_name}] Found {opportunities_checked} updated opportunities")

        except Exception as e:
            logger.error(f"[{task_name}] Failed to query opportunities: {e}")
            opportunities = []

        # Check for stage changes
        for opp in opportunities:
            try:
                current_stage = opp.get("status_label")
                raw_data = opp.get("raw_data") or {}
                previous_stage = raw_data.get("_previous_status_label")

                # If we have a previous stage tracked and it differs from current
                if previous_stage and previous_stage != current_stage:
                    stage_changes_detected += 1

                    logger.info(
                        f"[{task_name}] Stage change detected: {opp['external_id']} "
                        f"{previous_stage} -> {current_stage}"
                    )

                    # Build context for rule evaluation
                    context = {
                        "event_type": "opportunity.status_changed",
                        "opportunity_id": opp.get("external_id"),
                        "lead_id": opp.get("close_lead_id"),
                        "stage": current_stage,
                        "to_stage": current_stage,
                        "from_stage": previous_stage,
                        "amount": opp.get("value"),
                        "confidence": opp.get("confidence"),
                        "pipeline_id": opp.get("pipeline_id"),
                        "source": "polling",
                    }

                    # Trigger rule evaluation
                    evaluate_workflow_rules.delay("stage_change", context)
                    rules_triggered += 1

                    # Check for won/lost specific triggers
                    if current_stage and current_stage.lower() in ["won", "closed won"]:
                        evaluate_workflow_rules.delay("opportunity_won", context)
                        rules_triggered += 1
                    elif current_stage and current_stage.lower() in ["lost", "closed lost"]:
                        evaluate_workflow_rules.delay("opportunity_lost", context)
                        rules_triggered += 1

                    # Update raw_data with previous status for next comparison
                    try:
                        updated_raw_data = raw_data.copy()
                        updated_raw_data["_previous_status_label"] = current_stage
                        supabase.table("crm_opportunities").update({
                            "raw_data": updated_raw_data
                        }).eq("id", opp["id"]).execute()
                    except Exception as e:
                        logger.warning(f"Failed to update previous stage tracking: {e}")

                elif not previous_stage:
                    # First time seeing this opportunity - store current stage as baseline
                    try:
                        updated_raw_data = raw_data.copy()
                        updated_raw_data["_previous_status_label"] = current_stage
                        supabase.table("crm_opportunities").update({
                            "raw_data": updated_raw_data
                        }).eq("id", opp["id"]).execute()
                    except Exception as e:
                        logger.debug(f"Failed to initialize stage tracking: {e}")

            except Exception as e:
                logger.error(f"Error processing opportunity {opp.get('external_id')}: {e}")

        # Update last poll timestamp
        await set_last_poll_timestamp(redis, task_name, datetime.utcnow())

        return {
            "status": "success",
            "opportunities_checked": opportunities_checked,
            "stage_changes_detected": stage_changes_detected,
            "rules_triggered": rules_triggered,
        }

    finally:
        await release_task_lock(redis, task_name)
        await redis.close()


# ============================================================================
# CELERY BEAT SCHEDULE NOTES
# ============================================================================
# Add this to celery_app.py beat_schedule:
#
# "poll-stage-changes-every-15-min": {
#     "task": "poll_stage_changes",
#     "schedule": crontab(minute="*/15"),  # Every 15 minutes
#     "options": {"queue": "workflows"},
# },
