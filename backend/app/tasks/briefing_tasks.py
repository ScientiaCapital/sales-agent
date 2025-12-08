"""
BriefingAgent Celery Tasks
===========================
Celery task for consolidated morning briefing generation.

This task merges the functionality of:
- MorningBriefingAgent (prediction-based "why call now" reasoning)
- MorningReportAgent (overnight scout results + outreach drafts)

Schedule:
- Daily at 7:30 AM EST (12:30 UTC)

Pipeline:
1. Get top 10 leads by prediction rank
2. Generate "why call now" reasoning for each
3. Create outreach drafts (email, SMS, call opener)
4. Compile executive summary
5. Send formatted Slack message to BDR channel

Author: Claude + Tim (GTM Automation Team)
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
from datetime import datetime

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ============================================================================
# MORNING BRIEFING TASK
# ============================================================================

@celery_app.task(name="run_morning_briefing", bind=True, max_retries=2, soft_time_limit=900)
def run_morning_briefing_task(self, top_n: int = 10) -> Dict[str, Any]:
    """
    Scheduled task: Generate consolidated morning briefing.

    This task runs at 7:30 AM EST (12:30 UTC) via Celery Beat and:
    1. Gets top-N leads by prediction rank (call-worthiness)
    2. Generates "why call now" reasoning for each lead
    3. Creates personalized outreach drafts (email, SMS, call opener)
    4. Compiles executive summary with actionable insights
    5. Sends formatted Slack message to BDR channel

    This consolidates the functionality of:
    - MorningBriefingAgent (prediction-based reasoning)
    - MorningReportAgent (overnight scout + drafts)

    Args:
        top_n: Number of leads to include (default: 10)

    Returns:
        Dict with briefing results:
        {
            "status": "success",
            "generated_at": str,
            "leads_count": int,
            "hot_leads": int,
            "warm_leads": int,
            "cold_leads": int,
            "processing_time_ms": int,
            "file_path": str,
            "errors": List[str]
        }
    """
    try:
        logger.info(f"Starting Morning Briefing task: top_n={top_n}")

        from app.services.langgraph.agents.briefing_agent import BriefingAgent

        # Run async briefing generation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            agent = BriefingAgent(provider='cerebras')
            report = loop.run_until_complete(agent.generate_briefing(top_n))

            # Save to file
            file_path = loop.run_until_complete(agent.save_briefing_to_file(report))
        finally:
            loop.close()

        logger.info(
            f"Morning Briefing completed: {len(report.top_leads)} leads, "
            f"{report.hot_leads} HOT, {report.warm_leads} WARM, {report.cold_leads} COLD, "
            f"{report.processing_time_ms}ms"
        )

        # Send to Slack
        _send_briefing_to_slack(report)

        return {
            "status": "success",
            "generated_at": report.generated_at,
            "report_date": report.report_date,
            "leads_count": len(report.top_leads),
            "hot_leads": report.hot_leads,
            "warm_leads": report.warm_leads,
            "cold_leads": report.cold_leads,
            "processing_time_ms": report.processing_time_ms,
            "file_path": file_path,
            "errors": report.errors
        }

    except SoftTimeLimitExceeded:
        logger.warning("Morning Briefing soft time limit exceeded (15 minutes)")
        raise

    except Exception as exc:
        logger.error(f"Error in Morning Briefing task: {exc}", exc_info=True)
        countdown = 120 * (2 ** self.request.retries)  # 2 min, 4 min backoff
        raise self.retry(exc=exc, countdown=countdown)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _send_briefing_to_slack(report):
    """
    Send morning briefing to Slack.

    Formats the briefing as a rich Slack message with:
    - Executive summary
    - Top leads with "why call now" reasoning
    - Outreach draft previews
    - Quick stats

    Args:
        report: BriefingReport from BriefingAgent
    """
    try:
        from app.services.slack_notifier import get_slack_notifier

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            async def send_briefing():
                notifier = get_slack_notifier()

                # Build rich Slack message
                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": f"☀️ Morning Briefing - {report.report_date}",
                            "emoji": True
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"*{report.summary[:500]}*"
                        }
                    },
                    {
                        "type": "divider"
                    },
                    {
                        "type": "section",
                        "fields": [
                            {
                                "type": "mrkdwn",
                                "text": f"*Total Leads:* {report.total_leads}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*🔥 HOT:* {report.hot_leads}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*🌡️ WARM:* {report.warm_leads}"
                            },
                            {
                                "type": "mrkdwn",
                                "text": f"*❄️ COLD:* {report.cold_leads}"
                            }
                        ]
                    },
                    {
                        "type": "divider"
                    }
                ]

                # Add top 5 leads
                for i, lead in enumerate(report.top_leads[:5], 1):
                    blocks.extend([
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": (
                                    f"*#{lead.prediction_rank}: {lead.company_name}*\n"
                                    f"_{lead.city}, {lead.state}_ | "
                                    f"{lead.current_stage} | ICP {lead.icp_score}/100\n\n"
                                    f"*Why call now:*\n{lead.why_call_now[:300]}"
                                )
                            }
                        },
                        {
                            "type": "context",
                            "elements": [
                                {
                                    "type": "mrkdwn",
                                    "text": (
                                        f"📧 {lead.best_contact_email or 'No email'} | "
                                        f"📞 {lead.phone or 'No phone'}"
                                    )
                                }
                            ]
                        },
                        {
                            "type": "section",
                            "text": {
                                "type": "mrkdwn",
                                "text": f"```{lead.email_draft[:300]}...```"
                            }
                        }
                    ])

                    # Don't add divider after last lead
                    if i < min(5, len(report.top_leads)):
                        blocks.append({"type": "divider"})

                # Add footer
                blocks.extend([
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": (
                                    f"Generated in {report.processing_time_ms}ms | "
                                    f"{len(report.errors)} errors" if report.errors else "No errors"
                                )
                            }
                        ]
                    }
                ])

                # Send to Slack webhook
                webhook_url = os.getenv("SLACK_BDR_WEBHOOK")
                if webhook_url:
                    import httpx
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            webhook_url,
                            json={"blocks": blocks},
                            timeout=10.0
                        )
                        response.raise_for_status()
                        logger.info("Morning briefing sent to Slack")
                else:
                    logger.warning("SLACK_BDR_WEBHOOK not set, skipping Slack notification")

            loop.run_until_complete(send_briefing())
        finally:
            loop.close()

    except Exception as e:
        # Don't fail the task if Slack notification fails
        logger.warning(f"Failed to send morning briefing to Slack: {e}")


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "run_morning_briefing_task",
]
