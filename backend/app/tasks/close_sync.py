"""
Celery tasks for Close CRM automation

This module defines background tasks for syncing Close CRM activities,
polling for email replies, and advancing multi-step sequences.

Tasks:
    - sync_close_activities: Sync email/SMS/call activities from Close (every 15 min)
    - poll_email_replies: Poll for new email replies (every 5 min, fallback to webhook)
    - advance_sequences: Move leads through multi-step sequences (hourly)
"""
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from celery.exceptions import SoftTimeLimitExceeded
import asyncio
import logging
import os

# Disable LangSmith tracing BEFORE any langchain/langgraph imports
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING", "false")

# Suppress LangSmith warning logs
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

from redis import asyncio as aioredis  # noqa: E402

from app.celery_app import celery_app  # noqa: E402
from app.services.crm.close_email import CloseEmailClient  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402

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


async def get_last_poll_timestamp(redis: aioredis.Redis, task_name: str) -> Optional[datetime]:
    """
    Get last poll timestamp from Redis.

    Args:
        redis: Redis client
        task_name: Task name (e.g., "poll_email_replies")

    Returns:
        Last poll timestamp or None if not found
    """
    try:
        key = f"close_sync:last_poll:{task_name}"
        timestamp_str = await redis.get(key)
        if timestamp_str:
            return datetime.fromisoformat(timestamp_str)
        return None
    except Exception as e:
        logger.error(f"Failed to get last poll timestamp for {task_name}: {e}")
        return None


async def set_last_poll_timestamp(redis: aioredis.Redis, task_name: str, timestamp: datetime):
    """
    Set last poll timestamp in Redis.

    Args:
        redis: Redis client
        task_name: Task name
        timestamp: Timestamp to store
    """
    try:
        key = f"close_sync:last_poll:{task_name}"
        await redis.set(key, timestamp.isoformat(), ex=86400)  # 24 hour expiry
        logger.debug(f"Set last poll timestamp for {task_name}: {timestamp}")
    except Exception as e:
        logger.error(f"Failed to set last poll timestamp for {task_name}: {e}")


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
        key = f"close_sync:lock:{task_name}"
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
        key = f"close_sync:lock:{task_name}"
        await redis.delete(key)
        logger.debug(f"Released lock for {task_name}")
    except Exception as e:
        logger.error(f"Failed to release lock for {task_name}: {e}")


# ============================================================================
# TASK 1: SYNC CLOSE ACTIVITIES
# ============================================================================

@celery_app.task(
    name="sync_close_activities",
    bind=True,
    max_retries=3,
    default_retry_delay=60,  # 1 minute
)
def sync_close_activities(self) -> Dict[str, Any]:
    """
    Sync email/SMS/call activities from Close CRM to local database.

    Schedule: Every 15 minutes

    This task:
    1. Fetches recent activities from Close API (emails, SMS, calls)
    2. Updates local records with delivery status, opens, clicks
    3. Tracks sync metrics (activities synced, errors, timing)
    4. Uses distributed locking to prevent overlapping runs

    Returns:
        Dict with sync results:
        {
            "status": "success",
            "activities_synced": 42,
            "emails": 30,
            "sms": 8,
            "calls": 4,
            "errors": 0,
            "duration_ms": 1234
        }

    Raises:
        SoftTimeLimitExceeded: If task exceeds soft time limit
    """
    start_time = datetime.utcnow()
    task_name = "sync_close_activities"

    logger.info(f"[{task_name}] Starting Close CRM activity sync")

    try:
        # Run async function in sync context
        result = asyncio.run(_sync_close_activities_async(task_name))

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            f"[{task_name}] Completed: {result['activities_synced']} activities "
            f"({result['emails']} emails, {result['sms']} SMS, {result['calls']} calls) "
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


async def _sync_close_activities_async(task_name: str) -> Dict[str, Any]:
    """
    Async implementation of activity sync.

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
                "emails": 0,
                "sms": 0,
                "calls": 0,
                "errors": 0,
            }

        # Get last sync timestamp
        last_sync = await get_last_poll_timestamp(redis, task_name)
        if not last_sync:
            # Default to last 24 hours on first run
            last_sync = datetime.utcnow() - timedelta(hours=24)

        # Initialize Close client (will be used when TODO is implemented)
        # close_client = CloseEmailClient()

        # TODO: Implement activity fetching from Close API
        # For now, return mock results
        # Once Close SDK has activity endpoints, fetch like this:
        # close_client = CloseEmailClient()
        # activities = await close_client.get_activities_since(last_sync)

        activities_synced = 0
        emails = 0
        sms = 0
        calls = 0
        errors = 0

        # TODO: Fetch activities from Close API
        # activities = await _fetch_close_activities(close_client, last_sync)
        # for activity in activities:
        #     try:
        #         await _sync_activity_to_db(activity)
        #         activities_synced += 1
        #         if activity['type'] == 'email':
        #             emails += 1
        #         elif activity['type'] == 'sms':
        #             sms += 1
        #         elif activity['type'] == 'call':
        #             calls += 1
        #     except Exception as e:
        #         logger.error(f"Failed to sync activity {activity.get('id')}: {e}")
        #         errors += 1

        # Update last sync timestamp
        await set_last_poll_timestamp(redis, task_name, datetime.utcnow())

        return {
            "status": "success",
            "activities_synced": activities_synced,
            "emails": emails,
            "sms": sms,
            "calls": calls,
            "errors": errors,
        }

    finally:
        await release_task_lock(redis, task_name)
        await redis.close()


# ============================================================================
# TASK 2: POLL EMAIL REPLIES
# ============================================================================

@celery_app.task(
    name="poll_email_replies",
    bind=True,
    max_retries=3,
    default_retry_delay=30,  # 30 seconds
)
def poll_email_replies(self) -> Dict[str, Any]:
    """
    Poll Close CRM for new email replies (fallback to webhook).

    Schedule: Every 5 minutes

    This task:
    1. Queries Close API for incoming emails since last poll
    2. For each new reply, calls ReplyClassifier to categorize (interested/not/question)
    3. Routes replies to appropriate handler via ReplyRouter
    4. Tracks last_poll_timestamp in Redis

    Returns:
        Dict with polling results:
        {
            "status": "success",
            "replies_found": 5,
            "interested": 2,
            "not_interested": 1,
            "questions": 2,
            "errors": 0,
            "duration_ms": 567
        }

    Raises:
        SoftTimeLimitExceeded: If task exceeds soft time limit
    """
    start_time = datetime.utcnow()
    task_name = "poll_email_replies"

    logger.info(f"[{task_name}] Starting email reply polling")

    try:
        result = asyncio.run(_poll_email_replies_async(task_name))

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            f"[{task_name}] Completed: {result['replies_found']} replies "
            f"({result['interested']} interested, {result['not_interested']} not interested, "
            f"{result['questions']} questions) in {duration_ms}ms"
        )

        return result

    except SoftTimeLimitExceeded:
        logger.error(f"[{task_name}] Soft time limit exceeded")
        raise
    except Exception as e:
        logger.error(f"[{task_name}] Failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))


async def _poll_email_replies_async(task_name: str) -> Dict[str, Any]:
    """
    Async implementation of email reply polling.

    Args:
        task_name: Task name for locking

    Returns:
        Polling results dict
    """
    redis = await get_redis_client()

    try:
        # Acquire lock
        if not await acquire_task_lock(redis, task_name):
            return {
                "status": "skipped",
                "reason": "already_running",
                "replies_found": 0,
                "interested": 0,
                "not_interested": 0,
                "questions": 0,
                "errors": 0,
            }

        # Get last poll timestamp
        last_poll = await get_last_poll_timestamp(redis, task_name)
        if not last_poll:
            # Default to last 1 hour on first run
            last_poll = datetime.utcnow() - timedelta(hours=1)

        # Initialize Close client (will be used when TODO is implemented)
        # close_client = CloseEmailClient()

        replies_found = 0
        interested = 0
        not_interested = 0
        questions = 0
        errors = 0

        # TODO: Fetch incoming emails from Close API
        # Once Close SDK has inbox endpoints, fetch like this:
        # close_client = CloseEmailClient()
        # incoming_emails = await close_client.get_incoming_emails_since(last_poll)

        # TODO: Process each reply with ReplyClassifier and ReplyRouter
        # for email in incoming_emails:
        #     try:
        #         # Classify reply sentiment
        #         # from app.services.outreach.reply_classifier import ReplyClassifier
        #         # classifier = ReplyClassifier()
        #         # classification = await classifier.classify(email['body'])
        #
        #         # Route reply to appropriate handler
        #         # from app.services.outreach.reply_router import ReplyRouter
        #         # router = ReplyRouter()
        #         # await router.route_reply(email, classification)
        #
        #         replies_found += 1
        #         # if classification == 'interested':
        #         #     interested += 1
        #         # elif classification == 'not_interested':
        #         #     not_interested += 1
        #         # elif classification == 'question':
        #         #     questions += 1
        #     except Exception as e:
        #         logger.error(f"Failed to process reply {email.get('id')}: {e}")
        #         errors += 1

        # Update last poll timestamp
        await set_last_poll_timestamp(redis, task_name, datetime.utcnow())

        return {
            "status": "success",
            "replies_found": replies_found,
            "interested": interested,
            "not_interested": not_interested,
            "questions": questions,
            "errors": errors,
        }

    finally:
        await release_task_lock(redis, task_name)
        await redis.close()


# ============================================================================
# TASK 3: ADVANCE SEQUENCES
# ============================================================================

@celery_app.task(
    name="advance_sequences",
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes
)
def advance_sequences(self) -> Dict[str, Any]:
    """
    Advance leads through multi-step email/SMS sequences.

    Schedule: Every hour at :00

    This task:
    1. Checks for leads due for next sequence step
    2. Triggers next outreach action via OutreachAgent
    3. Handles sequence completion and graduation
    4. Tracks sequence performance metrics

    Returns:
        Dict with sequence advancement results:
        {
            "status": "success",
            "sequences_advanced": 15,
            "outreach_sent": 15,
            "sequences_completed": 3,
            "errors": 0,
            "duration_ms": 2345
        }

    Raises:
        SoftTimeLimitExceeded: If task exceeds soft time limit
    """
    start_time = datetime.utcnow()
    task_name = "advance_sequences"

    logger.info(f"[{task_name}] Starting sequence advancement")

    try:
        result = asyncio.run(_advance_sequences_async(task_name))

        duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        result["duration_ms"] = duration_ms

        logger.info(
            f"[{task_name}] Completed: {result['sequences_advanced']} sequences advanced, "
            f"{result['outreach_sent']} outreach sent, "
            f"{result['sequences_completed']} completed in {duration_ms}ms"
        )

        return result

    except SoftTimeLimitExceeded:
        logger.error(f"[{task_name}] Soft time limit exceeded")
        raise
    except Exception as e:
        logger.error(f"[{task_name}] Failed: {e}", exc_info=True)
        raise self.retry(exc=e, countdown=300 * (2 ** self.request.retries))


async def _advance_sequences_async(task_name: str) -> Dict[str, Any]:
    """
    Async implementation of sequence advancement.

    Args:
        task_name: Task name for locking

    Returns:
        Advancement results dict
    """
    redis = await get_redis_client()

    try:
        # Acquire lock
        if not await acquire_task_lock(redis, task_name):
            return {
                "status": "skipped",
                "reason": "already_running",
                "sequences_advanced": 0,
                "outreach_sent": 0,
                "sequences_completed": 0,
                "errors": 0,
            }

        sequences_advanced = 0
        outreach_sent = 0
        sequences_completed = 0
        errors = 0

        # TODO: Implement sequence advancement logic
        # 1. Query database for leads due for next step
        # 2. For each lead, trigger OutreachAgent to send next message
        # 3. Update sequence state in database
        # 4. Handle completion/graduation

        # Example flow:
        # from app.services.outreach.campaign_service import CampaignService
        # campaign_service = CampaignService()
        #
        # # Get leads due for next step
        # leads_due = await campaign_service.get_leads_due_for_step()
        #
        # for lead in leads_due:
        #     try:
        #         # Trigger next step
        #         result = await campaign_service.advance_sequence(lead['id'])
        #         sequences_advanced += 1
        #
        #         if result['action'] == 'send_outreach':
        #             outreach_sent += 1
        #         elif result['status'] == 'completed':
        #             sequences_completed += 1
        #     except Exception as e:
        #         logger.error(f"Failed to advance sequence for lead {lead['id']}: {e}")
        #         errors += 1

        logger.info(
            f"[{task_name}] Processed sequences: "
            f"{sequences_advanced} advanced, "
            f"{sequences_completed} completed"
        )

        return {
            "status": "success",
            "sequences_advanced": sequences_advanced,
            "outreach_sent": outreach_sent,
            "sequences_completed": sequences_completed,
            "errors": errors,
        }

    finally:
        await release_task_lock(redis, task_name)
        await redis.close()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

async def _fetch_close_activities(
    close_client: CloseEmailClient,
    since: datetime,
) -> List[Dict[str, Any]]:
    """
    Fetch activities from Close API since a given timestamp.

    Args:
        close_client: Close API client
        since: Fetch activities since this timestamp

    Returns:
        List of activity dicts
    """
    # TODO: Implement once Close SDK has activity endpoints
    # This will fetch emails, SMS, calls since the last sync
    return []


async def _sync_activity_to_db(activity: Dict[str, Any]):
    """
    Sync a Close activity to local database.

    Args:
        activity: Activity dict from Close API
    """
    # TODO: Implement database sync logic
    # Update local records with delivery status, opens, clicks
    pass
