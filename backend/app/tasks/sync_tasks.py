"""
Celery Tasks for SyncAgent

Provides Celery task wrappers for SyncAgent operations:
1. run_sync_cycle - Scheduled sync task (every 5 min)
2. handle_close_webhook - Webhook event handler

Consolidates functionality from:
- close_sync.py (sync_close_activities, poll_email_replies, advance_sequences)

Schedule:
- run_sync_cycle: Every 5 minutes
- handle_close_webhook: Event-driven (Close CRM webhook trigger)

Phase: 1 of 6 (Consolidation)
"""

from typing import Dict, Any
from datetime import datetime, timedelta
from celery.exceptions import SoftTimeLimitExceeded
import asyncio
import logging
import os

# LangSmith tracing is configured centrally in celery_app.py
# Do NOT override here - let the central config control tracing

# Suppress LangSmith warning logs when tracing is disabled
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

from redis import asyncio as aioredis

from app.celery_app import celery_app
from app.services.langgraph.agents.sync_agent import get_sync_agent
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ============================================================================
# REDIS STATE MANAGEMENT
# ============================================================================

async def get_redis_client() -> aioredis.Redis:
    """
    Get Redis client for state tracking.

    Returns:
        Redis client instance
    """
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    redis = await aioredis.from_url(
        redis_url,
        encoding="utf-8",
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5
    )
    return redis


async def get_last_sync_timestamp(redis: aioredis.Redis, task_name: str) -> datetime:
    """
    Get last sync timestamp from Redis.

    Args:
        redis: Redis client
        task_name: Task name (e.g., "sync_agent")

    Returns:
        Last sync timestamp or 5 minutes ago if not found
    """
    try:
        key = f"sync_agent:last_sync:{task_name}"
        timestamp_str = await redis.get(key)
        if timestamp_str:
            return datetime.fromisoformat(timestamp_str)
        # Default to 5 minutes ago
        return datetime.utcnow() - timedelta(minutes=5)
    except Exception as e:
        logger.error(f"Failed to get last sync timestamp for {task_name}: {e}")
        return datetime.utcnow() - timedelta(minutes=5)


async def set_last_sync_timestamp(redis: aioredis.Redis, task_name: str, timestamp: datetime):
    """
    Set last sync timestamp in Redis.

    Args:
        redis: Redis client
        task_name: Task name
        timestamp: Timestamp to store
    """
    try:
        key = f"sync_agent:last_sync:{task_name}"
        await redis.set(key, timestamp.isoformat(), ex=86400)  # 24 hour expiry
        logger.debug(f"Set last sync timestamp for {task_name}: {timestamp}")
    except Exception as e:
        logger.error(f"Failed to set last sync timestamp for {task_name}: {e}")


async def acquire_task_lock(redis: aioredis.Redis, task_name: str, timeout: int = 300) -> bool:
    """
    Acquire distributed lock for task to prevent overlapping runs.

    Args:
        redis: Redis client
        task_name: Task name
        timeout: Lock timeout in seconds (default 5 min)

    Returns:
        True if lock acquired, False if already locked
    """
    try:
        key = f"sync_agent:lock:{task_name}"
        # Use SET NX EX for atomic lock acquisition
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
    """
    Release distributed lock.

    Args:
        redis: Redis client
        task_name: Task name
    """
    try:
        key = f"sync_agent:lock:{task_name}"
        await redis.delete(key)
        logger.debug(f"Released lock for {task_name}")
    except Exception as e:
        logger.error(f"Failed to release lock for {task_name}: {e}")


# ============================================================================
# TASK 1: RUN SYNC CYCLE
# ============================================================================

@celery_app.task(
    name="run_sync_cycle",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute
)
def run_sync_cycle(self) -> Dict[str, Any]:
    """
    Run SyncAgent sync cycle.

    Schedule: Every 5 minutes

    This task:
    1. Syncs activities from Close CRM (emails, SMS, calls)
    2. Polls for new email replies
    3. Classifies replies with AI (Claude Haiku)
    4. Routes replies to appropriate handlers
    5. Advances multi-step sequences
    6. Emits events for downstream agents

    Returns:
        Dict with sync results:
        {
            "status": "success",
            "activities_synced": 42,
            "replies_found": 5,
            "replies_classified": {
                "interested": 2,
                "not_interested": 1,
                "questions": 2
            },
            "sequences_advanced": 10,
            "events_emitted": [
                {"event": "reply_received", "lead_id": "...", ...}
            ],
            "errors": [],
            "duration_ms": 1234
        }

    Raises:
        SoftTimeLimitExceeded: If task exceeds soft time limit
    """
    start_time = datetime.utcnow()
    task_name = "run_sync_cycle"

    logger.info(f"[{task_name}] Starting SyncAgent sync cycle")

    try:
        # Run async function in sync context
        result = asyncio.run(_run_sync_cycle_async(task_name))

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            f"[{task_name}] Completed: "
            f"{result['activities_synced']} activities, "
            f"{result['replies_found']} replies, "
            f"{result['sequences_advanced']} sequences advanced "
            f"in {duration_ms}ms"
        )

        return result

    except SoftTimeLimitExceeded:
        logger.error(f"[{task_name}] Soft time limit exceeded")
        raise
    except Exception as e:
        logger.error(f"[{task_name}] Failed: {e}", exc_info=True)
        # Retry with exponential backoff
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


async def _run_sync_cycle_async(task_name: str) -> Dict[str, Any]:
    """
    Async implementation of sync cycle.

    Args:
        task_name: Task name for locking

    Returns:
        Sync results dict
    """
    redis = await get_redis_client()

    try:
        # Acquire lock to prevent overlapping runs
        if not await acquire_task_lock(redis, task_name):
            return {
                "status": "skipped",
                "reason": "already_running",
                "activities_synced": 0,
                "replies_found": 0,
                "replies_classified": {},
                "sequences_advanced": 0,
                "events_emitted": [],
                "errors": [],
            }

        # Get last sync timestamp
        last_sync = await get_last_sync_timestamp(redis, task_name)

        # Get SyncAgent instance
        sync_agent = get_sync_agent()

        # Run sync cycle
        result = await sync_agent.run_sync_cycle(
            last_sync_timestamp=last_sync,
            trigger_source="schedule"
        )

        # Update last sync timestamp
        await set_last_sync_timestamp(redis, task_name, datetime.utcnow())

        return result

    finally:
        await release_task_lock(redis, task_name)
        await redis.close()


# ============================================================================
# TASK 2: HANDLE CLOSE WEBHOOK
# ============================================================================

@celery_app.task(
    name="handle_close_webhook",
    bind=True,
    max_retries=3,
    default_retry_delay=30,  # 30 seconds
)
def handle_close_webhook(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle Close CRM webhook event.

    Event Trigger: Close CRM webhook (real-time)

    This task:
    1. Receives webhook event from Close CRM
    2. Routes to SyncAgent.handle_webhook()
    3. Processes event based on type:
       - lead.created -> Delegate to ScoutAgent
       - activity.email.created -> Process as reply
       - activity.email.received -> Process as reply
    4. Returns processing result

    Args:
        event_data: Webhook event payload from Close CRM
            {
                "event": "activity.email.created",
                "data": {...},
                "timestamp": "2025-12-07T12:00:00Z"
            }

    Returns:
        Dict with webhook processing result:
        {
            "status": "success",
            "event_type": "activity.email.created",
            "message": "Reply processed and routed",
            "duration_ms": 567
        }

    Raises:
        SoftTimeLimitExceeded: If task exceeds soft time limit
    """
    start_time = datetime.utcnow()
    task_name = "handle_close_webhook"

    event_type = event_data.get("event", "unknown")
    logger.info(f"[{task_name}] Handling Close CRM webhook: {event_type}")

    try:
        result = asyncio.run(_handle_close_webhook_async(event_data))

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            f"[{task_name}] Completed webhook {event_type}: "
            f"status={result['status']} in {duration_ms}ms"
        )

        return result

    except SoftTimeLimitExceeded:
        logger.error(f"[{task_name}] Soft time limit exceeded")
        raise
    except Exception as e:
        logger.error(f"[{task_name}] Failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))


async def _handle_close_webhook_async(event_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Async implementation of webhook handler.

    Args:
        event_data: Webhook event data

    Returns:
        Processing result dict
    """
    event_type = event_data.get("event", "unknown")

    # Get SyncAgent instance
    sync_agent = get_sync_agent()

    # Handle webhook
    result = await sync_agent.handle_webhook(
        event_type=event_type,
        event_data=event_data.get("data", {})
    )

    return result


# ============================================================================
# HELPER: CLASSIFY REPLY (Standalone function for testing)
# ============================================================================

async def classify_reply(
    subject: str,
    body_text: str,
    from_email: str
) -> Dict[str, Any]:
    """
    Classify an email reply (standalone helper).

    Args:
        subject: Email subject line
        body_text: Email body text
        from_email: Sender email address

    Returns:
        Classification result:
        {
            "intent": "interested",  # interested, not_interested, question, etc.
            "sentiment": "positive",  # positive, neutral, negative
            "confidence": 0.85,
            "reasoning": "AI classification",
            "requires_human_review": True
        }
    """
    sync_agent = get_sync_agent()

    classification = await sync_agent.reply_classifier.classify(
        subject=subject,
        body_text=body_text,
        from_email=from_email
    )

    return {
        "intent": classification.intent.value,
        "sentiment": classification.sentiment.value,
        "confidence": classification.confidence,
        "reasoning": classification.reasoning,
        "requires_human_review": classification.requires_human_review
    }


__all__ = [
    "run_sync_cycle",
    "handle_close_webhook",
    "classify_reply"
]
