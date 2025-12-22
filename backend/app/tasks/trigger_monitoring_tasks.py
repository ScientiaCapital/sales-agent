"""
Trigger Event Monitoring Celery Tasks
======================================
Celery tasks for automated trigger event detection (buying signals).

Runs hourly to detect:
- Funding rounds (TechCrunch, Crunchbase scraping)
- Hiring activity (careers page scraping)
- News/press releases (Google News RSS)
- Executive changes
- Tech stack changes

Priority: ICP companies (PLATINUM/GOLD/SILVER) with enriched contacts (phone + email)

Author: Claude + Tim
Date: Dec 22, 2025
"""
import os
import logging

# Suppress LangSmith warning logs when tracing is disabled
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

import asyncio
from typing import Dict, Any, List
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ============================================================================
# TRIGGER EVENT MONITORING TASKS
# ============================================================================

@celery_app.task(name="monitor_trigger_events_hourly", bind=True, max_retries=2, soft_time_limit=600)
def monitor_trigger_events_task(self, limit: int = 50):
    """
    Scheduled task: Monitor trigger events for ICP companies with enriched contacts.

    This task runs hourly via Celery Beat and:
    1. Queries companies WHERE:
       - icp_tier IN ('PLATINUM', 'GOLD', 'SILVER')
       - enrichment_status IN ('paid_enriched', 'enriched')
       - Has at least 1 contact with email AND phone
    2. Runs TriggerEventDetector for each company
    3. Saves new events to trigger_events table (deduplication via content_hash)
    4. Sends Slack alerts for high-priority events (signal_strength >= 8)

    Args:
        limit: Maximum number of companies to check per run (default: 50)

    Returns:
        Dict with detection results:
        {
            "status": "success",
            "companies_checked": int,
            "events_detected": int,
            "high_priority_events": int,
            "companies_with_events": List[str]
        }
    """
    try:
        logger.info(f"Starting Trigger Event Monitor task: limit={limit}")

        # Import async service
        from app.services.trigger_event_detector import get_trigger_event_detector
        from supabase import create_client

        # Initialize Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL or SUPABASE_SERVICE_KEY not configured")

        supabase = create_client(supabase_url, supabase_key)

        # Query ICP companies with enriched contacts (phone + email)
        logger.info(f"Querying ICP companies with enriched contacts (limit={limit})")
        result = (
            supabase.table("dim_companies")
            .select("company_id, company_name, domain, icp_tier, icp_score, dim_contacts!inner(contact_id, phone, email)")
            .in_("icp_tier", ["PLATINUM", "GOLD", "SILVER"])
            .in_("enrichment_status", ["paid_enriched", "enriched"])
            .not_.is_("dim_contacts.phone", "null")
            .not_.is_("dim_contacts.email", "null")
            .order("icp_score", desc=True)
            .limit(limit)
            .execute()
        )

        if not result.data:
            logger.info("No companies found matching criteria")
            return {
                "status": "success",
                "companies_checked": 0,
                "events_detected": 0,
                "high_priority_events": 0,
                "companies_with_events": []
            }

        companies = result.data
        logger.info(f"Found {len(companies)} companies to monitor")

        # Run async detection
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            detection_result = loop.run_until_complete(
                _detect_trigger_events_for_companies(companies)
            )
        finally:
            loop.close()

        logger.info(
            f"Trigger Event Monitor completed: {detection_result['companies_checked']} checked, "
            f"{detection_result['events_detected']} events detected, "
            f"{detection_result['high_priority_events']} high-priority"
        )

        # Send Slack notifications for high-priority events
        if detection_result['high_priority_events'] > 0:
            _send_trigger_event_notifications(detection_result['hot_events'])

        return {
            "status": "success",
            **detection_result
        }

    except SoftTimeLimitExceeded:
        logger.warning("Trigger Event Monitor soft time limit exceeded (10 minutes)")
        raise

    except Exception as exc:
        logger.error(f"Error in Trigger Event Monitor task: {exc}", exc_info=True)
        countdown = 60 * (2 ** self.request.retries)  # 1 min, 2 min backoff
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="detect_trigger_events_for_company", max_retries=3)
def detect_trigger_events_for_company_task(
    company_id: str,
    company_name: str,
    domain: str = None
):
    """
    Event-driven task: Detect trigger events for a specific company.

    Called on-demand when you want to check a single company immediately
    (e.g., after ICP upgrade, after enrichment completes).

    Usage:
        from app.tasks.trigger_monitoring_tasks import detect_trigger_events_for_company_task
        detect_trigger_events_for_company_task.delay(
            str(company_id),
            "Acme HVAC",
            "acmehvac.com"
        )

    Args:
        company_id: UUID string of the company
        company_name: Company name for searches
        domain: Company domain for website scraping (optional)

    Returns:
        Dict with detection results:
        {
            "status": "success",
            "events_detected": int,
            "events": List[dict]
        }
    """
    try:
        logger.info(f"Detecting trigger events for company_id={company_id} ({company_name})")

        from uuid import UUID
        from app.services.trigger_event_detector import get_trigger_event_detector

        # Run async detection
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def detect():
                detector = await get_trigger_event_detector()
                events = await detector.detect_all_signals(
                    UUID(company_id),
                    company_name,
                    domain
                )
                return events

            events = loop.run_until_complete(detect())
        finally:
            loop.close()

        logger.info(
            f"Detected {len(events)} trigger events for {company_name}"
        )

        # Send Slack notification for high-priority events
        hot_events = [e for e in events if e.signal_strength >= 8]
        if hot_events:
            _send_trigger_event_notifications(hot_events)

        return {
            "status": "success",
            "events_detected": len(events),
            "events": [
                {
                    "event_type": e.event_type,
                    "title": e.title,
                    "signal_strength": e.signal_strength,
                    "source_url": e.source_url
                }
                for e in events
            ]
        }

    except Exception as exc:
        logger.error(f"Error detecting trigger events for {company_id}: {exc}", exc_info=True)
        raise


@celery_app.task(name="get_trigger_event_stats")
def get_trigger_event_stats_task():
    """
    Get current trigger event statistics.

    Returns:
        Dict with trigger event stats:
        {
            "total_events": int,
            "by_type": {"funding": int, "hiring": int, ...},
            "high_priority": int,
            "actioned": int,
            "pending": int
        }
    """
    try:
        logger.info("Getting trigger event stats")

        from supabase import create_client

        # Initialize Supabase
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        supabase = create_client(supabase_url, supabase_key)

        # Query stats using Supabase queries
        all_events = supabase.table("trigger_events").select("event_type, signal_strength, actioned").execute()

        if not all_events.data:
            return {
                "status": "success",
                "total_events": 0,
                "by_type": {},
                "high_priority": 0,
                "actioned": 0,
                "pending": 0
            }

        # Calculate stats in Python
        events = all_events.data
        total_events = len(events)
        high_priority = sum(1 for e in events if e.get('signal_strength', 0) >= 8)
        actioned = sum(1 for e in events if e.get('actioned', False))
        pending = total_events - actioned

        # Group by event_type
        by_type = {}
        for e in events:
            event_type = e.get('event_type', 'unknown')
            by_type[event_type] = by_type.get(event_type, 0) + 1

        stats = {
            'total_events': total_events,
            'high_priority': high_priority,
            'actioned': actioned,
            'pending': pending,
            'by_type': by_type
        }

        logger.info(
            f"Trigger Event Stats: {stats['total_events']} total, "
            f"{stats['high_priority']} high-priority, "
            f"{stats['pending']} pending action"
        )

        return {
            "status": "success",
            **stats
        }

    except Exception as exc:
        logger.error(f"Error getting trigger event stats: {exc}", exc_info=True)
        raise


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

async def _detect_trigger_events_for_companies(companies: List[Dict]) -> Dict[str, Any]:
    """
    Detect trigger events for a batch of companies.

    Args:
        companies: List of company dicts with company_id, company_name, domain

    Returns:
        Dict with detection results
    """
    from app.services.trigger_event_detector import get_trigger_event_detector
    from uuid import UUID

    detector = await get_trigger_event_detector()

    companies_checked = 0
    total_events = 0
    hot_events = []  # signal_strength >= 8
    companies_with_events = []

    for company in companies:
        try:
            company_id = UUID(company['company_id'])
            company_name = company['company_name']
            domain = company.get('domain')

            # Detect events
            events = await detector.detect_all_signals(
                company_id,
                company_name,
                domain
            )

            companies_checked += 1
            total_events += len(events)

            if events:
                companies_with_events.append(company_name)

                # Collect high-priority events for Slack notifications
                for event in events:
                    if event.signal_strength >= 8:
                        hot_events.append({
                            'company_id': str(company_id),
                            'company_name': company_name,
                            'icp_tier': company.get('icp_tier', 'N/A'),
                            'event': event
                        })

            # Add small delay to avoid rate limiting (0.5 seconds per company)
            await asyncio.sleep(0.5)

        except Exception as e:
            logger.error(f"Error detecting events for {company.get('company_name')}: {e}")
            continue

    return {
        "companies_checked": companies_checked,
        "events_detected": total_events,
        "high_priority_events": len(hot_events),
        "companies_with_events": companies_with_events,
        "hot_events": hot_events
    }


def _send_trigger_event_notifications(hot_events: List[Dict]):
    """
    Send Slack notifications for high-priority trigger events.

    Args:
        hot_events: List of dicts with company info and TriggerEvent object
    """
    try:
        from app.services.slack_notifier import get_slack_notifier

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def send_notifications():
                notifier = get_slack_notifier()

                for item in hot_events:
                    event = item['event']
                    company_name = item['company_name']
                    icp_tier = item['icp_tier']

                    # Format as Slack message using TriggerEvent's built-in formatter
                    slack_message = event.to_slack_message()

                    # Add ICP tier context
                    slack_message = f"🎯 *{icp_tier} ICP*\n\n{slack_message}"

                    # Send as status update (reusing existing method)
                    await notifier.send_status_update(
                        draft_id=str(item['company_id']),
                        company_name=company_name,
                        status="trigger",
                        message=slack_message
                    )

            loop.run_until_complete(send_notifications())
        finally:
            loop.close()

        logger.info(f"Sent {len(hot_events)} trigger event notifications to Slack")

    except Exception as e:
        # Don't fail the task if Slack notification fails
        logger.warning(f"Failed to send trigger event notifications: {e}")
