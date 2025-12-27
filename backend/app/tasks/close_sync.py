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

# LangSmith tracing is configured centrally in celery_app.py
# Do NOT override here - let the central config control tracing

# Suppress LangSmith warning logs when tracing is disabled
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

from redis import asyncio as aioredis  # noqa: E402

from app.celery_app import celery_app  # noqa: E402
from app.services.crm.close_email import CloseEmailClient  # noqa: E402
from app.services.crm.close_sequences import CloseSequencesClient  # noqa: E402
from app.services.crm.close_tasks import CloseTaskClient  # noqa: E402
from app.services.outreach.reply_classifier import ReplyClassifier, ReplyIntent  # noqa: E402
from app.services.outreach.reply_router import ReplyRouter  # noqa: E402
from app.core.logging import setup_logging  # noqa: E402

# Supabase for data persistence
try:
    from supabase import create_client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False

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
            f"({result['emails']} emails, {result['sms']} SMS, {result['calls']} calls, "
            f"{result.get('meetings', 0)} meetings), "
            f"tasks: {result.get('tasks_created', 0)} created, {result.get('tasks_completed', 0)} completed "
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

    Fetches email/SMS/call activities from Close CRM and syncs to Supabase
    for analytics and reporting.

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

        # Initialize Close client
        try:
            close_client = CloseEmailClient()
        except ValueError as e:
            logger.error(f"Close client initialization failed: {e}")
            return {
                "status": "error",
                "reason": "close_api_key_missing",
                "activities_synced": 0,
                "emails": 0,
                "sms": 0,
                "calls": 0,
                "errors": 1,
            }

        activities_synced = 0
        emails = 0
        sms = 0
        calls = 0
        meetings = 0
        tasks_created = 0
        tasks_completed = 0
        errors = 0

        # Fetch activities from Close API
        activities = await close_client.get_activities_since(last_sync)
        logger.info(f"[{task_name}] Fetched {len(activities)} activities since {last_sync}")

        # Get Supabase client for syncing
        supabase = None
        if SUPABASE_AVAILABLE:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)

        for activity in activities:
            try:
                activity_type = activity.get("_activity_type", "unknown")
                activity_id = activity.get("id")

                # Sync to Supabase if available
                if supabase:
                    await _sync_activity_to_supabase(supabase, activity)

                activities_synced += 1

                if activity_type == "email":
                    emails += 1
                elif activity_type == "sms":
                    sms += 1
                elif activity_type == "call":
                    calls += 1
                elif activity_type == "meeting":
                    meetings += 1

            except Exception as e:
                logger.error(f"Failed to sync activity {activity.get('id')}: {e}")
                errors += 1

        # Sync tasks from Close API
        try:
            task_client = CloseTaskClient()

            # Get tasks created since last sync
            new_tasks = await task_client.get_tasks_since(last_sync, is_complete=False)
            logger.info(f"[{task_name}] Fetched {len(new_tasks)} new tasks since {last_sync}")

            for task in new_tasks:
                try:
                    if supabase:
                        await _sync_task_to_supabase(supabase, task, is_completed=False)
                    tasks_created += 1
                except Exception as e:
                    logger.error(f"Failed to sync new task {task.get('id')}: {e}")
                    errors += 1

            # Get tasks completed since last sync
            completed_tasks = await task_client.get_tasks_since(last_sync, is_complete=True)
            logger.info(f"[{task_name}] Fetched {len(completed_tasks)} completed tasks since {last_sync}")

            for task in completed_tasks:
                try:
                    if supabase:
                        await _sync_task_to_supabase(supabase, task, is_completed=True)
                    tasks_completed += 1
                except Exception as e:
                    logger.error(f"Failed to sync completed task {task.get('id')}: {e}")
                    errors += 1

            logger.info(
                f"[{task_name}] Task sync: {tasks_created} created, {tasks_completed} completed"
            )

        except ValueError as e:
            logger.warning(f"[{task_name}] Task client init failed (API key?): {e}")
        except Exception as e:
            logger.error(f"[{task_name}] Task sync failed: {e}")
            errors += 1

        # Update last sync timestamp
        await set_last_poll_timestamp(redis, task_name, datetime.utcnow())

        return {
            "status": "success",
            "activities_synced": activities_synced,
            "emails": emails,
            "sms": sms,
            "calls": calls,
            "meetings": meetings,
            "tasks_created": tasks_created,
            "tasks_completed": tasks_completed,
            "errors": errors,
        }

    finally:
        await release_task_lock(redis, task_name)
        await redis.close()


async def _sync_activity_to_supabase(supabase, activity: Dict[str, Any]):
    """
    Sync a Close activity to Supabase lead_audit_log table.

    Args:
        supabase: Supabase client
        activity: Activity dict from Close API
    """
    activity_type = activity.get("_activity_type", "unknown")
    activity_id = activity.get("id")
    lead_id = activity.get("lead_id")

    # Map activity type to event_type for audit log
    event_type_map = {
        "email": "email_activity",
        "sms": "sms_activity",
        "call": "call_activity",
        "meeting": "meeting_activity",
    }
    event_type = event_type_map.get(activity_type, "activity_sync")

    # Build audit log entry
    audit_entry = {
        "event_type": event_type,
        "close_lead_id": lead_id,
        "close_activity_id": activity_id,
        "activity_type": activity_type,
        "direction": activity.get("direction", "outbound"),
        "status": activity.get("status"),
        "created_at": activity.get("date_created"),
        "metadata": {
            "subject": activity.get("subject"),
            "to": activity.get("to"),
            "from": activity.get("sender"),
            "duration": activity.get("duration"),  # For calls
            "starts_at": activity.get("starts_at"),  # For meetings
            "ends_at": activity.get("ends_at"),  # For meetings
            "title": activity.get("title"),  # For meetings
        }
    }

    # Upsert to audit log (avoid duplicates)
    try:
        supabase.table("lead_audit_log").upsert(
            audit_entry,
            on_conflict="close_activity_id"
        ).execute()
    except Exception as e:
        # If upsert fails (e.g., column doesn't exist), just insert
        logger.debug(f"Upsert failed, trying insert: {e}")
        supabase.table("lead_audit_log").insert(audit_entry).execute()


async def _sync_task_to_supabase(
    supabase,
    task: Dict[str, Any],
    is_completed: bool = False
):
    """
    Sync a Close task to Supabase fact_activities table.

    Args:
        supabase: Supabase client
        task: Task dict from Close API
        is_completed: Whether this is a completed task sync
    """
    task_id = task.get("id")
    lead_id = task.get("lead_id")
    contact_id = task.get("contact_id")

    # Determine event type based on completion status
    event_type = "task_completed" if is_completed else "task_created"

    # Build activity entry for fact_activities
    activity_entry = {
        "activity_type": "task",
        "close_task_id": task_id,
        "close_lead_id": lead_id,
        "close_contact_id": contact_id,
        "event_type": event_type,
        "task_text": task.get("text"),
        "task_due_date": task.get("date"),
        "is_complete": task.get("is_complete", False),
        "assigned_to": task.get("assigned_to"),
        "created_at": task.get("date_created"),
        "updated_at": task.get("date_updated"),
        "metadata": {
            "task_id": task_id,
            "lead_id": lead_id,
            "is_complete": task.get("is_complete"),
            "completed_at": task.get("date_updated") if is_completed else None,
        }
    }

    # Upsert to fact_activities (avoid duplicates)
    try:
        supabase.table("fact_activities").upsert(
            activity_entry,
            on_conflict="close_task_id"
        ).execute()
    except Exception as e:
        # If upsert fails (e.g., column doesn't exist), try lead_audit_log instead
        logger.debug(f"fact_activities upsert failed, trying lead_audit_log: {e}")
        # Fall back to lead_audit_log
        audit_entry = {
            "event_type": event_type,
            "close_lead_id": lead_id,
            "close_activity_id": task_id,
            "activity_type": "task",
            "status": "completed" if is_completed else "pending",
            "created_at": task.get("date_created"),
            "metadata": activity_entry["metadata"]
        }
        try:
            supabase.table("lead_audit_log").insert(audit_entry).execute()
        except Exception as inner_e:
            logger.debug(f"lead_audit_log insert also failed: {inner_e}")


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

    Fetches incoming emails from Close CRM, classifies them using AI,
    and routes them to appropriate handlers (Slack alerts, sequence control).

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

        # Initialize Close client
        try:
            close_client = CloseEmailClient()
        except ValueError as e:
            logger.error(f"Close client initialization failed: {e}")
            return {
                "status": "error",
                "reason": "close_api_key_missing",
                "replies_found": 0,
                "interested": 0,
                "not_interested": 0,
                "questions": 0,
                "errors": 1,
            }

        replies_found = 0
        interested = 0
        not_interested = 0
        questions = 0
        meeting_requests = 0
        out_of_office = 0
        unsubscribes = 0
        errors = 0

        # Fetch incoming emails from Close API
        incoming_emails = await close_client.get_incoming_emails_since(last_poll)
        logger.info(f"[{task_name}] Found {len(incoming_emails)} incoming emails since {last_poll}")

        if not incoming_emails:
            # No new replies, update timestamp and return
            await set_last_poll_timestamp(redis, task_name, datetime.utcnow())
            return {
                "status": "success",
                "replies_found": 0,
                "interested": 0,
                "not_interested": 0,
                "questions": 0,
                "meeting_requests": 0,
                "out_of_office": 0,
                "unsubscribes": 0,
                "errors": 0,
            }

        # Initialize classifier and router
        classifier = ReplyClassifier(use_ai=True)
        router = ReplyRouter()

        # Process each reply
        for email in incoming_emails:
            try:
                email_id = email.get("id")
                subject = email.get("subject", "")
                body_text = email.get("body_text", "")
                body_html = email.get("body_html")
                lead_id = email.get("lead_id")
                contact_id = email.get("contact_id")
                from_email = None

                # Extract sender email from addresses
                sender_addresses = email.get("addresses", {})
                if sender_addresses:
                    from_addrs = sender_addresses.get("from", [])
                    if from_addrs:
                        from_email = from_addrs[0].get("email")

                # Get company/contact info from Close (if available)
                company_name = email.get("_company_name", "Unknown Company")
                contact_name = email.get("_contact_name", from_email or "Unknown")

                logger.debug(f"Processing reply {email_id} from {from_email}: {subject[:50]}")

                # Classify the reply
                classification = await classifier.classify(
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html,
                    from_email=from_email
                )

                # Route the reply to appropriate handler
                route_result = await router.route(
                    classification=classification,
                    lead_id=lead_id,
                    contact_id=contact_id,
                    email_body=body_text,
                    company_name=company_name,
                    contact_name=contact_name,
                    from_email=from_email
                )

                replies_found += 1

                # Track by intent
                if classification.intent == ReplyIntent.INTERESTED:
                    interested += 1
                elif classification.intent == ReplyIntent.NOT_INTERESTED:
                    not_interested += 1
                elif classification.intent == ReplyIntent.QUESTION:
                    questions += 1
                elif classification.intent == ReplyIntent.MEETING_REQUEST:
                    meeting_requests += 1
                elif classification.intent == ReplyIntent.OUT_OF_OFFICE:
                    out_of_office += 1
                elif classification.intent == ReplyIntent.UNSUBSCRIBE:
                    unsubscribes += 1

                logger.info(
                    f"[{task_name}] Processed reply {email_id}: "
                    f"intent={classification.intent.value}, "
                    f"action={route_result.get('action')}"
                )

            except Exception as e:
                logger.error(f"Failed to process reply {email.get('id')}: {e}", exc_info=True)
                errors += 1

        # Update last poll timestamp
        await set_last_poll_timestamp(redis, task_name, datetime.utcnow())

        return {
            "status": "success",
            "replies_found": replies_found,
            "interested": interested,
            "not_interested": not_interested,
            "questions": questions,
            "meeting_requests": meeting_requests,
            "out_of_office": out_of_office,
            "unsubscribes": unsubscribes,
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

    Close CRM handles the actual sequence step advancement automatically.
    This task focuses on:
    1. Resuming paused subscriptions (e.g., OOO contacts after 7 days)
    2. Tracking subscription status for analytics
    3. Syncing subscription data to Supabase

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
                "subscriptions_resumed": 0,
                "subscriptions_active": 0,
                "subscriptions_paused": 0,
                "errors": 0,
            }

        # Initialize Close sequences client
        try:
            sequences_client = CloseSequencesClient()
        except ValueError as e:
            logger.error(f"Close sequences client initialization failed: {e}")
            return {
                "status": "error",
                "reason": "close_api_key_missing",
                "sequences_advanced": 0,
                "subscriptions_resumed": 0,
                "subscriptions_active": 0,
                "subscriptions_paused": 0,
                "errors": 1,
            }

        subscriptions_resumed = 0
        subscriptions_active = 0
        subscriptions_paused = 0
        subscriptions_finished = 0
        errors = 0

        # Get all sequences
        sequences = await sequences_client.list_sequences(active_only=True)
        logger.info(f"[{task_name}] Found {len(sequences)} active sequences")

        # Get Supabase client for syncing
        supabase = None
        if SUPABASE_AVAILABLE:
            supabase_url = os.getenv("SUPABASE_URL")
            supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
            if supabase_url and supabase_key:
                supabase = create_client(supabase_url, supabase_key)

        # Track Redis key for OOO pause timestamps
        ooo_pause_key_prefix = "close_sync:ooo_pause:"

        for sequence in sequences:
            sequence_id = sequence.get("id")
            sequence_name = sequence.get("name", "Unknown")

            try:
                # Get all subscriptions for this sequence
                # Note: Close API may need pagination for large sequences
                subscriptions = await sequences_client.list_active_subscriptions(
                    sequence_id=sequence_id,
                    limit=200
                )

                for sub in subscriptions:
                    sub_id = sub.get("id")
                    status = sub.get("status")
                    contact_id = sub.get("contact_id")

                    if status == "active":
                        subscriptions_active += 1
                    elif status == "paused":
                        subscriptions_paused += 1

                        # Check if this subscription was paused for OOO
                        # and if the 7-day pause period has expired
                        pause_key = f"{ooo_pause_key_prefix}{sub_id}"
                        pause_timestamp_str = await redis.get(pause_key)

                        if pause_timestamp_str:
                            pause_timestamp = datetime.fromisoformat(pause_timestamp_str)
                            days_paused = (datetime.utcnow() - pause_timestamp).days

                            if days_paused >= 7:
                                # Resume the subscription
                                logger.info(
                                    f"[{task_name}] Resuming OOO subscription {sub_id} "
                                    f"after {days_paused} days"
                                )
                                result = await sequences_client.resume_subscription(sub_id)
                                if result:
                                    subscriptions_resumed += 1
                                    # Clean up the pause tracking key
                                    await redis.delete(pause_key)
                                else:
                                    errors += 1

                    elif status == "finished":
                        subscriptions_finished += 1

                    # Sync subscription status to Supabase (if available)
                    if supabase:
                        try:
                            await _sync_subscription_to_supabase(
                                supabase, sub, sequence_name
                            )
                        except Exception as e:
                            logger.debug(f"Failed to sync subscription {sub_id}: {e}")

            except Exception as e:
                logger.error(
                    f"Failed to process sequence {sequence_id} ({sequence_name}): {e}"
                )
                errors += 1

        logger.info(
            f"[{task_name}] Sequence status: "
            f"{subscriptions_active} active, "
            f"{subscriptions_paused} paused, "
            f"{subscriptions_finished} finished, "
            f"{subscriptions_resumed} resumed"
        )

        return {
            "status": "success",
            "sequences_advanced": len(sequences),
            "subscriptions_resumed": subscriptions_resumed,
            "subscriptions_active": subscriptions_active,
            "subscriptions_paused": subscriptions_paused,
            "subscriptions_finished": subscriptions_finished,
            "errors": errors,
        }

    finally:
        await release_task_lock(redis, task_name)
        await redis.close()


async def _sync_subscription_to_supabase(
    supabase,
    subscription: Dict[str, Any],
    sequence_name: str
):
    """
    Sync a sequence subscription status to Supabase.

    Args:
        supabase: Supabase client
        subscription: Subscription dict from Close API
        sequence_name: Name of the sequence
    """
    sub_id = subscription.get("id")
    contact_id = subscription.get("contact_id")
    status = subscription.get("status")

    # Build audit log entry
    audit_entry = {
        "event_type": "sequence_status",
        "close_subscription_id": sub_id,
        "close_contact_id": contact_id,
        "sequence_name": sequence_name,
        "status": status,
        "current_step": subscription.get("current_step"),
        "metadata": {
            "sequence_id": subscription.get("sequence_id"),
            "paused_at": subscription.get("paused_at"),
            "finished_at": subscription.get("finished_at"),
        }
    }

    # Upsert to audit log
    try:
        supabase.table("lead_audit_log").upsert(
            audit_entry,
            on_conflict="close_subscription_id"
        ).execute()
    except Exception as e:
        # If upsert fails, just insert
        logger.debug(f"Subscription upsert failed, trying insert: {e}")
        supabase.table("lead_audit_log").insert(audit_entry).execute()


# ============================================================================
# CELERY BEAT SCHEDULE (for reference)
# ============================================================================
# Add these to your celery_app.py beat_schedule:
#
# CELERY_BEAT_SCHEDULE = {
#     'sync-close-activities': {
#         'task': 'sync_close_activities',
#         'schedule': crontab(minute='*/15'),  # Every 15 minutes
#     },
#     'poll-email-replies': {
#         'task': 'poll_email_replies',
#         'schedule': crontab(minute='*/5'),  # Every 5 minutes
#     },
#     'advance-sequences': {
#         'task': 'advance_sequences',
#         'schedule': crontab(minute=0),  # Every hour at :00
#     },
# }
