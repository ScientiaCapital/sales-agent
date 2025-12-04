"""
ICP Checker Celery Tasks
========================
Celery tasks for automatic ICP score recalculation and tier updates.

Triggered by:
- Celery Beat schedule (every 15 minutes)
- Event-driven from other agents after enrichment

Author: Claude + Tim
Date: Dec 3, 2025
"""
# Disable LangSmith tracing BEFORE any langchain/langgraph imports
import os
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING", "false")

# Suppress LangSmith warning logs
import logging
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

import asyncio
from typing import Dict, Any

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ============================================================================
# ICP CHECKER TASKS
# ============================================================================

@celery_app.task(name="run_icp_checker", bind=True, max_retries=2, soft_time_limit=300)
def run_icp_checker_task(self, limit: int = 100):
    """
    Scheduled task: Check ICP for recently modified companies.

    This task runs every 15 minutes via Celery Beat and:
    1. Queries companies where updated_at > icp_last_checked (or never checked)
    2. Recalculates ICP score using the scoring algorithm
    3. Updates dim_companies with new score and tier
    4. Sends Slack alert for tier upgrades (e.g., BRONZE → SILVER)

    Args:
        limit: Maximum number of companies to check per run (default: 100)

    Returns:
        Dict with check results:
        {
            "status": "success",
            "checked": int,
            "changed": int,
            "upgrades": List[{company_id, company_name, old_tier, new_tier}]
        }
    """
    try:
        logger.info(f"Starting ICP Checker task: limit={limit}")

        # Import async service
        from app.services.icp_scorer import batch_check_icp

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(batch_check_icp(limit))
        finally:
            loop.close()

        logger.info(
            f"ICP Checker completed: {result['checked']} checked, "
            f"{result['changed']} changed, {len(result['upgrades'])} upgrades"
        )

        # Send Slack notification for tier upgrades
        if result['upgrades']:
            _send_tier_upgrade_notifications(result['upgrades'])

        return {
            "status": "success",
            "checked": result['checked'],
            "changed": result['changed'],
            "upgrades": result['upgrades']
        }

    except SoftTimeLimitExceeded:
        logger.warning("ICP Checker soft time limit exceeded (5 minutes)")
        raise

    except Exception as exc:
        logger.error(f"Error in ICP Checker task: {exc}", exc_info=True)
        countdown = 60 * (2 ** self.request.retries)  # 1 min, 2 min backoff
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="recheck_icp_for_company", max_retries=3)
def recheck_icp_for_company_task(company_id: str):
    """
    Event-driven task: Recheck ICP for a specific company.

    Called by other agents after enrichment to immediately recalculate
    ICP score when new data (phone, email, contacts) is discovered.

    Usage:
        from app.tasks.icp_tasks import recheck_icp_for_company_task
        recheck_icp_for_company_task.delay(str(company_id))

    Args:
        company_id: UUID string of the company to check

    Returns:
        Dict with check result:
        {
            "status": "success",
            "changed": bool,
            "old_score": float,
            "new_score": float,
            "old_tier": str,
            "new_tier": str,
            "tier_upgraded": bool
        }
    """
    try:
        logger.info(f"Rechecking ICP for company_id={company_id}")

        from uuid import UUID
        from app.services.icp_scorer import check_and_update_icp

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(check_and_update_icp(UUID(company_id)))
        finally:
            loop.close()

        if result.get('error'):
            logger.warning(f"ICP recheck error for {company_id}: {result['error']}")
            return {"status": "error", "error": result['error']}

        logger.info(
            f"ICP recheck for {company_id}: "
            f"{result['old_score']} ({result['old_tier']}) → "
            f"{result['new_score']} ({result['new_tier']})"
            f"{' UPGRADED!' if result.get('tier_upgraded') else ''}"
        )

        # Send Slack notification for tier upgrade
        if result.get('tier_upgraded'):
            _send_tier_upgrade_notifications([{
                'company_id': company_id,
                'company_name': result.get('company_name', 'Unknown'),
                'old_tier': result['old_tier'],
                'new_tier': result['new_tier'],
                'old_score': result['old_score'],
                'new_score': result['new_score']
            }])

        return {
            "status": "success",
            **result
        }

    except Exception as exc:
        logger.error(f"Error in ICP recheck for {company_id}: {exc}", exc_info=True)
        raise


@celery_app.task(name="get_icp_stats")
def get_icp_stats_task():
    """
    Get current ICP tier distribution and stats.

    Returns:
        Dict with ICP statistics:
        {
            "total": int,
            "by_tier": {"PLATINUM": int, "GOLD": int, ...},
            "avg_score": float,
            "needs_recheck": int
        }
    """
    try:
        logger.info("Getting ICP stats")

        from app.services.icp_scorer import get_icp_stats

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(get_icp_stats())
        finally:
            loop.close()

        logger.info(
            f"ICP Stats: {result['total']} total, "
            f"avg score {result['avg_score']}, "
            f"{result['needs_recheck']} need recheck"
        )

        return {"status": "success", **result}

    except Exception as exc:
        logger.error(f"Error getting ICP stats: {exc}", exc_info=True)
        raise


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _send_tier_upgrade_notifications(upgrades: list):
    """
    Send Slack notifications for tier upgrades.

    Args:
        upgrades: List of upgrade dicts with company_id, company_name, old_tier, new_tier
    """
    try:
        from app.services.slack_notifier import get_slack_notifier

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def send_notifications():
                notifier = get_slack_notifier()
                for upgrade in upgrades:
                    await notifier.send_icp_upgrade_alert(
                        company_id=upgrade['company_id'],
                        company_name=upgrade['company_name'],
                        old_tier=upgrade['old_tier'],
                        new_tier=upgrade['new_tier'],
                        old_score=upgrade.get('old_score'),
                        new_score=upgrade.get('new_score')
                    )

            loop.run_until_complete(send_notifications())
        finally:
            loop.close()

        logger.info(f"Sent {len(upgrades)} tier upgrade notifications")

    except Exception as e:
        # Don't fail the task if Slack notification fails
        logger.warning(f"Failed to send tier upgrade notifications: {e}")
