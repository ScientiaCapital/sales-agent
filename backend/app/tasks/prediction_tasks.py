"""
PredictionAgent Celery Tasks
=============================
Celery tasks for lead ranking updates and morning briefings.

This agent supports the Sr. BDR on outreach motion and cold outbound by:
- Ranking leads by "call-worthiness" every 5 minutes
- Generating "why call now" reasoning daily at 7 AM EST

Schedule:
- PredictionAgent: Every 5 minutes (ranks 1000 leads)
- Morning Briefing: Daily at 7 AM EST (12:00 UTC)

Author: Claude + Tim (GTM Automation Team)
Date: Dec 3, 2025
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
# PREDICTION MARKET TASKS
# ============================================================================

@celery_app.task(name="run_prediction_market", bind=True, max_retries=2, soft_time_limit=300)
def run_prediction_market_task(self, limit: int = 1000):
    """
    Scheduled task: Update prediction rankings for all active leads.

    This task runs every 5 minutes via Celery Beat and:
    1. Calculates prediction scores for all leads with ICP scores
    2. Assigns prediction ranks based on scores
    3. Sends Slack alert for significant rank changes (3+ spots)

    Args:
        limit: Maximum number of companies to rank (default: 1000)

    Returns:
        Dict with ranking results:
        {
            "status": "success",
            "updated": int,
            "top_10": List[{company_id, company_name, rank, score}]
        }
    """
    try:
        logger.info(f"Starting PredictionAgent task: limit={limit}")

        from app.services.prediction_market import update_rankings

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(update_rankings(limit))
        finally:
            loop.close()

        logger.info(
            f"PredictionAgent completed: {result['updated']} companies ranked, "
            f"top lead: {result['top_10'][0]['company_name'] if result['top_10'] else 'None'}"
        )

        return {
            "status": "success",
            "updated": result['updated'],
            "top_10": result['top_10']
        }

    except SoftTimeLimitExceeded:
        logger.warning("PredictionAgent soft time limit exceeded (5 minutes)")
        raise

    except Exception as exc:
        logger.error(f"Error in PredictionAgent task: {exc}", exc_info=True)
        countdown = 60 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="run_morning_briefing", bind=True, max_retries=2, soft_time_limit=600)
def run_morning_briefing_task(self, top_n: int = 10):
    """
    Scheduled task: Generate morning briefing with LLM "why call now" reasoning.

    This task runs at 7 AM EST (12:00 UTC) via Celery Beat and:
    1. Gets top-N leads by prediction rank
    2. Generates personalized "why call now" reasoning for each
    3. Saves reasoning to dim_companies.prediction_why_now
    4. Sends formatted Slack message with briefing

    Args:
        top_n: Number of leads to include (default: 10)

    Returns:
        Dict with briefing results:
        {
            "status": "success",
            "generated_at": str,
            "leads_count": int,
            "processing_time_ms": int
        }
    """
    try:
        logger.info(f"Starting Morning Briefing task: top_n={top_n}")

        from app.services.langgraph.agents.lead_prediction_agent import LeadPredictionAgent

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent = LeadPredictionAgent()
            result = loop.run_until_complete(agent.generate_morning_briefing(top_n))
        finally:
            loop.close()

        logger.info(
            f"Morning Briefing completed: {len(result.top_leads)} leads, "
            f"{result.processing_time_ms}ms"
        )

        # Send to Slack
        _send_morning_briefing_to_slack(result)

        return {
            "status": "success",
            "generated_at": result.generated_at,
            "leads_count": len(result.top_leads),
            "processing_time_ms": result.processing_time_ms
        }

    except SoftTimeLimitExceeded:
        logger.warning("Morning Briefing soft time limit exceeded (10 minutes)")
        raise

    except Exception as exc:
        logger.error(f"Error in Morning Briefing task: {exc}", exc_info=True)
        countdown = 120 * (2 ** self.request.retries)
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="log_lead_signal")
def log_lead_signal_task(
    company_id: str,
    signal_type: str,
    signal_value: dict = None,
    weight: float = 1.0
):
    """
    Event-driven task: Log a momentum signal for a company.

    Called by other agents after significant events to update
    momentum scoring for the prediction market.

    Signal types:
    - 'phone_added': Direct phone discovered (weight 2.0)
    - 'email_added': Email discovered (weight 1.5)
    - 'stage_change': Lead progressed (weight 1.5)
    - 'enrichment': New data from any agent (weight 1.0)
    - 'bdr_note': Manual BDR activity (weight 1.2)
    - 'email_open': Outreach engagement (weight 1.3)
    - 'tier_upgrade': ICP tier improved (weight 1.8)

    Args:
        company_id: UUID string of the company
        signal_type: Type of signal
        signal_value: Additional signal data (optional)
        weight: Custom weight multiplier (default 1.0)

    Returns:
        Dict confirming signal logged
    """
    try:
        logger.info(f"Logging signal '{signal_type}' for company_id={company_id}")

        from app.services.prediction_market import log_signal

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                log_signal(
                    company_id=UUID(company_id),
                    signal_type=signal_type,
                    signal_value=signal_value or {},
                    weight=weight
                )
            )
        finally:
            loop.close()

        return {
            "status": "success",
            "company_id": company_id,
            "signal_type": signal_type
        }

    except Exception as exc:
        logger.error(f"Error logging signal for {company_id}: {exc}", exc_info=True)
        raise


@celery_app.task(name="get_prediction_stats")
def get_prediction_stats_task():
    """
    Get current prediction market statistics.

    Returns:
        Dict with prediction stats:
        {
            "total_ranked": int,
            "avg_score": float,
            "top_score": float,
            "last_update": str
        }
    """
    try:
        logger.info("Getting prediction stats")

        from app.services.prediction_market import get_prediction_stats

        # Run async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(get_prediction_stats())
        finally:
            loop.close()

        logger.info(
            f"Prediction Stats: {result['total_ranked']} ranked, "
            f"avg score {result['avg_score']}, top {result['top_score']}"
        )

        return {"status": "success", **result}

    except Exception as exc:
        logger.error(f"Error getting prediction stats: {exc}", exc_info=True)
        raise


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _send_morning_briefing_to_slack(result):
    """
    Send morning briefing to Slack.

    Args:
        result: MorningBriefingResult from LeadPredictionAgent
    """
    try:
        from app.services.slack_notifier import get_slack_notifier

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def send_briefing():
                notifier = get_slack_notifier()
                await notifier.send_morning_briefing(
                    leads=result.top_leads,
                    summary=result.summary
                )

            loop.run_until_complete(send_briefing())
        finally:
            loop.close()

        logger.info(f"Morning briefing sent to Slack")

    except Exception as e:
        # Don't fail the task if Slack notification fails
        logger.warning(f"Failed to send morning briefing to Slack: {e}")
