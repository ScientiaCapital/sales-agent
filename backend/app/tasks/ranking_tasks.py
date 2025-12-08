"""
RankingAgent Celery Tasks
==========================
Celery tasks for unified ICP scoring + prediction ranking.

This consolidates:
- icp_tasks.py (ICP scoring)
- prediction_tasks.py (prediction market ranking)

Schedule:
- run_ranking_cycle: Every 10 min (consolidated from 15 min + 5 min)

Event Triggers:
- run_ranking_for_company: Triggered by company_enriched event

Emits:
- tier_upgraded: When ICP tier improves (Slack notification)

Author: Claude + Tim (Agent Consolidation Phase 1)
Date: Dec 7, 2025
"""
# LangSmith tracing is configured centrally in celery_app.py
# Do NOT override here - let the central config control tracing
import os
import logging

# Suppress LangSmith warning logs when tracing is disabled
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

import asyncio
from typing import Dict, Any
from uuid import UUID

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ============================================================================
# RANKING CYCLE TASKS
# ============================================================================

@celery_app.task(name="run_ranking_cycle", bind=True, max_retries=2, soft_time_limit=600)
def run_ranking_cycle_task(self, limit: int = 100):
    """
    Scheduled task: Run unified ICP + prediction ranking cycle.

    This task runs every 10 minutes via Celery Beat and:
    1. Queries companies where updated_at > icp_last_checked
    2. Recalculates ICP score and tier for each
    3. Recalculates prediction score for each
    4. Sorts by prediction score and assigns global ranks
    5. Sends Slack alert for tier upgrades

    Consolidates:
    - run_icp_checker (15 min schedule)
    - run_prediction_market (5 min schedule)

    Args:
        limit: Maximum number of companies to rank per run (default: 100)

    Returns:
        Dict with ranking results:
        {
            "status": "success",
            "processed": int,
            "changed": int,
            "upgrades": int,
            "top_10": List[{company_id, company_name, rank, score}]
        }
    """
    try:
        logger.info(f"Starting RankingAgent cycle: limit={limit}")

        from app.services.langgraph.agents.ranking_agent import RankingAgent

        # Run async ranking
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent = RankingAgent()
            result = loop.run_until_complete(agent.rank_batch(limit))
        finally:
            loop.close()

        logger.info(
            f"RankingAgent cycle completed: {result.total_processed} processed, "
            f"{result.total_changed} changed, {result.total_upgrades} upgrades"
        )

        # Send Slack notification for tier upgrades
        if result.upgrades:
            _send_tier_upgrade_notifications(result.upgrades)

        return {
            "status": "success",
            "processed": result.total_processed,
            "changed": result.total_changed,
            "upgrades": result.total_upgrades,
            "top_10": result.top_10
        }

    except SoftTimeLimitExceeded:
        logger.warning("RankingAgent cycle soft time limit exceeded (10 minutes)")
        raise

    except Exception as exc:
        logger.error(f"Error in RankingAgent cycle: {exc}", exc_info=True)
        countdown = 60 * (2 ** self.request.retries)  # 1 min, 2 min backoff
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="run_ranking_for_company", max_retries=3)
def run_ranking_for_company_task(company_id: str):
    """
    Event-driven task: Rank a specific company after enrichment.

    Triggered by:
    - EnrichmentAgent after discovering new contacts/data
    - BDRAgent after manual updates
    - Any agent emitting company_enriched event

    This task:
    1. Recalculates ICP score and tier
    2. Recalculates prediction score
    3. Updates dim_companies
    4. Emits tier_upgraded event if tier improved

    Usage:
        from app.tasks.ranking_tasks import run_ranking_for_company_task
        run_ranking_for_company_task.delay(str(company_id))

    Args:
        company_id: UUID string of the company to rank

    Returns:
        Dict with ranking result:
        {
            "status": "success",
            "company_id": str,
            "company_name": str,
            "old_tier": str,
            "new_tier": str,
            "tier_upgraded": bool,
            "event": "tier_upgraded" (if tier upgraded to HOT)
        }
    """
    try:
        logger.info(f"Ranking company_id={company_id} (event-triggered)")

        from app.services.langgraph.agents.ranking_agent import RankingAgent

        # Run async ranking
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent = RankingAgent()
            result = loop.run_until_complete(agent.rank_company(UUID(company_id)))
        finally:
            loop.close()

        logger.info(
            f"Ranking complete for {company_id}: "
            f"{result.old_icp_score} ({result.old_icp_tier}) → "
            f"{result.new_icp_score} ({result.new_icp_tier})"
            f"{' UPGRADED!' if result.tier_upgraded else ''}"
        )

        response = {
            "status": "success",
            "company_id": result.company_id,
            "company_name": result.company_name,
            "old_score": result.old_icp_score,
            "new_score": result.new_icp_score,
            "old_tier": result.old_icp_tier,
            "new_tier": result.new_icp_tier,
            "prediction_score": result.prediction_score,
            "tier_upgraded": result.tier_upgraded
        }

        # Send Slack notification for tier upgrade
        if result.tier_upgraded:
            _send_tier_upgrade_notifications([{
                'company_id': result.company_id,
                'company_name': result.company_name,
                'old_tier': result.old_icp_tier,
                'new_tier': result.new_icp_tier,
                'old_score': result.old_icp_score,
                'new_score': result.new_icp_score
            }])

            # Emit tier_upgraded event if upgraded to HOT tiers
            if result.new_icp_tier in ['PLATINUM', 'GOLD']:
                response['event'] = 'tier_upgraded'
                logger.info(f"Emitting tier_upgraded event for {result.company_name} ({result.new_icp_tier})")

        return response

    except Exception as exc:
        logger.error(f"Error ranking company {company_id}: {exc}", exc_info=True)
        raise


@celery_app.task(name="get_ranking_stats")
def get_ranking_stats_task():
    """
    Get current ranking statistics (ICP + prediction).

    Returns:
        Dict with ranking stats:
        {
            "status": "success",
            "total_companies": int,
            "icp_tiers": {"PLATINUM": int, "GOLD": int, ...},
            "avg_icp_score": float,
            "avg_prediction_score": float,
            "needs_rerank": int
        }
    """
    try:
        logger.info("Getting ranking stats")

        from app.services.langgraph.agents.ranking_agent import get_supabase_client

        supabase = get_supabase_client()

        # Get total companies
        total_result = supabase.table('dim_companies').select('company_id', count='exact').execute()
        total = total_result.count or 0

        # Get tier distribution
        tier_counts = {}
        for tier in ['PLATINUM', 'GOLD', 'SILVER', 'BRONZE', 'LEAD']:
            tier_result = supabase.table('dim_companies').select(
                'company_id', count='exact'
            ).eq('icp_tier', tier).execute()
            tier_counts[tier] = tier_result.count or 0

        # Get average scores
        score_result = supabase.table('dim_companies').select(
            'icp_score, prediction_score'
        ).execute()

        icp_scores = [c.get('icp_score') or 0 for c in (score_result.data or [])]
        pred_scores = [c.get('prediction_score') or 0 for c in (score_result.data or []) if c.get('prediction_score')]

        avg_icp = sum(icp_scores) / len(icp_scores) if icp_scores else 0
        avg_pred = sum(pred_scores) / len(pred_scores) if pred_scores else 0

        # Get count needing rerank
        rerank_result = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).or_(
            'icp_last_checked.is.null,updated_at.gt.icp_last_checked'
        ).execute()
        needs_rerank = rerank_result.count or 0

        logger.info(
            f"Ranking Stats: {total} total, "
            f"avg ICP {avg_icp:.1f}, avg pred {avg_pred:.1f}, "
            f"{needs_rerank} need rerank"
        )

        return {
            "status": "success",
            "total_companies": total,
            "icp_tiers": tier_counts,
            "avg_icp_score": round(avg_icp, 1),
            "avg_prediction_score": round(avg_pred, 1),
            "needs_rerank": needs_rerank
        }

    except Exception as exc:
        logger.error(f"Error getting ranking stats: {exc}", exc_info=True)
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
