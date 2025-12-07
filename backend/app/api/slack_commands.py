"""
Slack /enrich Command Handler

Handles Slack slash commands for lead enrichment via DropInAgent.

Architecture:
    User types: /enrich https://acme-hvac.com
         │
         ▼
    Slack → POST /slack/commands/enrich
         │
         ▼
    Return 200 within 3s: "🔍 Enriching..."
         │
         ▼
    Queue Celery task (run_dropin_enrichment)
         │
         ▼
    DropInAgent → Close dedup → ScoutAgent → QualificationAgent
         │
         ▼
    Post result to response_url:
    - "⚠️ Already in Close: [link]" (duplicate)
    - "✅ Enriched: [company] - ICP: [tier]" (new lead)
    - "❌ Error: [message]" (failure)

Usage:
    # In Slack workspace, configure:
    # Command: /enrich
    # Request URL: https://api.example.com/api/v1/slack/commands/enrich
    # Short Description: Enrich a lead from URL, name, or Close ID

    # Examples:
    /enrich https://acme-hvac.com
    /enrich "Acme HVAC"
    /enrich lead_abc123

Critical Rules:
    - MUST respond within 3 seconds (Slack requirement)
    - Use Celery for actual work (async background task)
    - Post result to response_url when done (delayed response)
    - Parse application/x-www-form-urlencoded (not JSON)
"""

import os
import httpx
from typing import Optional
from fastapi import APIRouter, Form, BackgroundTasks
from pydantic import BaseModel

from app.core.logging import setup_logging
from app.tasks.dropin_tasks import run_dropin_enrichment

logger = setup_logging(__name__)

router = APIRouter(prefix="/slack", tags=["slack"])


# ========== Models ==========

class SlackCommandPayload(BaseModel):
    """Slack slash command payload (parsed from form data)."""
    command: str  # e.g., "/enrich"
    text: str  # User input after command
    user_id: str  # Slack user ID (e.g., U123ABC)
    user_name: str  # Slack username
    channel_id: str  # Slack channel ID (e.g., C123ABC)
    channel_name: str  # Slack channel name
    team_id: str  # Slack workspace ID
    response_url: str  # Webhook URL for delayed responses


# ========== Background Tasks ==========

async def post_result_to_slack(response_url: str, result: dict):
    """
    Post enrichment result to Slack via response_url.

    Args:
        response_url: Slack webhook URL for delayed response
        result: Celery task result dict
    """
    try:
        # Extract result data
        status = result.get("status")
        source = result.get("source", "slack")

        if status == "success":
            enrichment = result.get("result", {})
            exists = enrichment.get("exists_in_close", False)

            if exists:
                # Duplicate found in Close CRM
                existing = enrichment.get("existing_lead", {})
                company = existing.get("company_name", "Unknown")
                close_url = existing.get("close_url", "")
                confidence = existing.get("confidence", 0.0)

                message = (
                    f"⚠️ *Lead Already Exists in Close CRM*\n\n"
                    f"*Company:* {company}\n"
                    f"*Confidence:* {confidence:.1f}%\n"
                    f"*Link:* <{close_url}|View in Close>"
                )
            else:
                # New lead enriched
                company = enrichment.get("company_name", "Unknown")
                domain = enrichment.get("domain", "N/A")
                icp_score = enrichment.get("icp_score", 0)
                icp_tier = enrichment.get("icp_tier", "UNKNOWN")
                priority = enrichment.get("priority", "COLD")
                duration_ms = enrichment.get("duration_ms", 0)

                # Priority emoji
                priority_emoji = {
                    "HOT": "🔥",
                    "WARM": "🌡️",
                    "COLD": "❄️"
                }.get(priority, "⬜")

                message = (
                    f"✅ *Lead Enriched Successfully*\n\n"
                    f"*Company:* {company}\n"
                    f"*Domain:* {domain}\n"
                    f"*ICP Score:* {icp_score}/100\n"
                    f"*ICP Tier:* {icp_tier}\n"
                    f"*Priority:* {priority_emoji} {priority}\n"
                    f"*Processing Time:* {duration_ms}ms"
                )
        else:
            # Error
            error = result.get("error", "Unknown error")
            input_str = result.get("input", "Unknown")
            message = (
                f"❌ *Enrichment Failed*\n\n"
                f"*Input:* {input_str}\n"
                f"*Error:* {error}"
            )

        # Post to Slack via response_url
        async with httpx.AsyncClient() as client:
            response = await client.post(
                response_url,
                json={
                    "response_type": "in_channel",  # Public response
                    "text": message,
                    "mrkdwn": True
                },
                timeout=10.0
            )

            if response.status_code == 200:
                logger.info(f"Posted result to Slack: {status}")
            else:
                logger.error(
                    f"Failed to post to Slack: {response.status_code} - {response.text}"
                )

    except Exception as e:
        logger.error(f"Error posting result to Slack: {e}")


async def poll_and_post_result(
    task_id: str,
    response_url: str,
    max_wait_seconds: int = 300
):
    """
    Poll Celery task result and post to Slack when ready.

    Args:
        task_id: Celery task ID
        response_url: Slack webhook URL
        max_wait_seconds: Max time to wait for result (default: 5 minutes)
    """
    import time
    from celery.result import AsyncResult
    from app.celery_app import celery_app

    start_time = time.time()
    poll_interval = 2  # Poll every 2 seconds

    while True:
        # Check timeout
        if time.time() - start_time > max_wait_seconds:
            logger.error(f"Task {task_id} timeout after {max_wait_seconds}s")
            await post_result_to_slack(
                response_url,
                {
                    "status": "error",
                    "error": f"Enrichment timeout after {max_wait_seconds}s"
                }
            )
            break

        # Check task status
        task_result = AsyncResult(task_id, app=celery_app)

        if task_result.ready():
            # Task completed - get result
            result = task_result.get()
            await post_result_to_slack(response_url, result)
            break

        # Wait before next poll
        await asyncio_sleep(poll_interval)


# ========== Endpoints ==========

@router.post("/commands/enrich")
async def handle_enrich_command(
    background_tasks: BackgroundTasks,
    command: str = Form(...),
    text: str = Form(...),
    user_id: str = Form(...),
    user_name: str = Form(...),
    channel_id: str = Form(...),
    channel_name: str = Form(...),
    team_id: str = Form(...),
    response_url: str = Form(...),
    token: Optional[str] = Form(None),  # Slack verification token
):
    """
    Handle Slack /enrich command.

    Slack sends application/x-www-form-urlencoded data (not JSON).
    Must respond within 3 seconds with immediate acknowledgment.

    Examples:
        /enrich https://acme-hvac.com
        /enrich "Acme HVAC"
        /enrich lead_abc123

    Args:
        command: Slash command (e.g., "/enrich")
        text: User input after command
        user_id: Slack user ID
        user_name: Slack username
        channel_id: Slack channel ID
        channel_name: Slack channel name
        team_id: Slack workspace ID
        response_url: Webhook URL for delayed response
        token: Slack verification token (optional)

    Returns:
        Immediate acknowledgment (within 3s)
        Posts result to response_url when enrichment completes
    """
    try:
        # Validate Slack token (optional - for additional security)
        expected_token = os.getenv("SLACK_VERIFICATION_TOKEN")
        if expected_token and token != expected_token:
            logger.warning(
                f"Invalid Slack token from user {user_name} (team: {team_id})"
            )
            return {
                "response_type": "ephemeral",  # Only visible to user
                "text": "❌ Invalid Slack verification token"
            }

        # Parse input
        input_str = text.strip()
        if not input_str:
            return {
                "response_type": "ephemeral",
                "text": (
                    "❌ *Usage:* `/enrich <url|company|close_id>`\n\n"
                    "*Examples:*\n"
                    "• `/enrich https://acme-hvac.com`\n"
                    "• `/enrich \"Acme HVAC\"`\n"
                    "• `/enrich lead_abc123`"
                )
            }

        logger.info(
            f"Slack /enrich: user={user_name}, channel={channel_name}, "
            f"team={team_id}, input={input_str}"
        )

        # Queue Celery task for background processing
        task = run_dropin_enrichment.delay(
            input=input_str,
            input_type="auto",  # Auto-detect input type
            stage_channels=None,  # No auto-staging from Slack
            auto_trigger=False,
            source="slack"
        )

        logger.info(f"Queued enrichment task: {task.id}")

        # Add background task to poll result and post to Slack
        # Import asyncio.sleep for polling
        import asyncio
        global asyncio_sleep
        asyncio_sleep = asyncio.sleep

        background_tasks.add_task(
            poll_and_post_result,
            task_id=task.id,
            response_url=response_url,
            max_wait_seconds=300  # 5 minutes max
        )

        # Return immediate acknowledgment (within 3s)
        return {
            "response_type": "in_channel",  # Public response
            "text": f"🔍 Enriching: `{input_str}`...\n\n_This may take 10-30 seconds._"
        }

    except Exception as e:
        logger.error(f"Slack /enrich error: {e}")
        return {
            "response_type": "ephemeral",
            "text": f"❌ Error: {str(e)}"
        }


@router.get("/health")
async def slack_health():
    """Slack integration health check."""
    return {
        "status": "healthy",
        "integration": "slack",
        "commands": [
            {
                "command": "/enrich",
                "description": "Enrich lead from URL, name, or Close ID",
                "examples": [
                    "/enrich https://acme-hvac.com",
                    "/enrich \"Acme HVAC\"",
                    "/enrich lead_abc123"
                ]
            }
        ]
    }


# ========== Exports ==========

__all__ = ["router"]
