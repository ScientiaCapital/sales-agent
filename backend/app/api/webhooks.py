"""
Webhook Handlers for External Services

Handles incoming webhooks from:
- Slack: Interactive message button callbacks (BDR approval workflow)
- Future: Apollo, Close CRM, etc.

Security:
- Slack signature verification using SLACK_SIGNING_SECRET
- Request timestamp validation to prevent replay attacks

Endpoints:
- POST /webhooks/slack/bdr-approval - Handle BDR draft approve/reject buttons
"""

import os
import hmac
import hashlib
import time
import json
import logging
import uuid as uuid_module
from typing import Optional
from urllib.parse import parse_qs

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ========== Slack Signature Verification ==========

def verify_slack_signature(
    body: bytes,
    timestamp: str,
    signature: str,
    signing_secret: Optional[str] = None
) -> bool:
    """
    Verify that the request came from Slack using HMAC-SHA256.

    Args:
        body: Raw request body bytes
        timestamp: X-Slack-Request-Timestamp header
        signature: X-Slack-Signature header
        signing_secret: Slack signing secret (defaults to env var)

    Returns:
        True if signature is valid, False otherwise
    """
    secret = signing_secret or os.getenv("SLACK_SIGNING_SECRET")

    if not secret:
        # SECURITY: Never skip verification - reject if secret not configured
        logger.error("SLACK_SIGNING_SECRET not configured - rejecting request for security")
        return False

    # Check timestamp to prevent replay attacks (5 minute window)
    try:
        request_timestamp = int(timestamp)
        current_timestamp = int(time.time())
        if abs(current_timestamp - request_timestamp) > 300:
            logger.warning("Slack request timestamp too old")
            return False
    except ValueError:
        logger.warning("Invalid Slack timestamp")
        return False

    # Compute expected signature
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    expected_signature = "v0=" + hmac.new(
        secret.encode('utf-8'),
        sig_basestring.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(expected_signature, signature)


# ========== Slack BDR Approval Webhook ==========

@router.post("/slack/bdr-approval")
async def handle_slack_bdr_approval(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Handle Slack interactive message callbacks for BDR draft approval.

    This endpoint receives callbacks when users click Approve/Reject/Edit
    buttons on BDR draft notifications in Slack.

    Actions:
    - approve_draft: Resume BDR agent to send the email
    - reject_draft: Mark draft as rejected, notify in Slack
    - edit_draft: Open edit modal (future) or mark for revision

    Returns:
        Slack expects a 200 response with optional message update
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify Slack signature
        timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
        signature = request.headers.get("X-Slack-Signature", "")

        if not verify_slack_signature(body, timestamp, signature):
            raise HTTPException(status_code=401, detail="Invalid Slack signature")

        # Parse the payload (Slack sends as form-encoded with 'payload' key)
        body_str = body.decode('utf-8')

        # Slack interactive payloads come as form-encoded
        if body_str.startswith("payload="):
            parsed = parse_qs(body_str)
            payload_str = parsed.get("payload", ["{}"])[0]
            payload = json.loads(payload_str)
        else:
            # Direct JSON (for testing)
            payload = json.loads(body_str)

        # Extract action details
        actions = payload.get("actions", [])
        if not actions:
            logger.warning("No actions in Slack payload")
            return JSONResponse({"text": "No action received"})

        action = actions[0]
        action_id = action.get("action_id")
        draft_id = action.get("value")

        # Validate draft_id is a valid UUID
        if not draft_id:
            logger.warning("No draft_id in Slack action")
            return JSONResponse({"text": "Invalid action: missing draft ID"})

        try:
            uuid_module.UUID(draft_id)
        except ValueError:
            logger.warning(f"Invalid UUID format in Slack action: {draft_id}")
            return JSONResponse({"text": "Invalid action: malformed draft ID"})

        user = payload.get("user", {})
        user_name = user.get("name", "Unknown")

        logger.info(f"Slack BDR action: {action_id} for draft {draft_id} by {user_name}")

        # Handle the action
        if action_id == "approve_draft":
            # Queue the resume task to send the email
            background_tasks.add_task(
                resume_bdr_with_approval,
                draft_id=draft_id,
                action="approve",
                user_name=user_name
            )

            # Immediate response to Slack
            return JSONResponse({
                "response_type": "in_channel",
                "replace_original": True,
                "text": f"✅ *Draft approved by {user_name}!* Sending email...",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✅ *Draft approved by {user_name}!*\nSending email now..."
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Draft ID: `{draft_id[:8]}...`"
                            }
                        ]
                    }
                ]
            })

        elif action_id == "reject_draft":
            # Queue the rejection handling
            background_tasks.add_task(
                resume_bdr_with_approval,
                draft_id=draft_id,
                action="reject",
                user_name=user_name,
                feedback="Rejected by user"
            )

            return JSONResponse({
                "response_type": "in_channel",
                "replace_original": True,
                "text": f"❌ *Draft rejected by {user_name}.*",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"❌ *Draft rejected by {user_name}.*\nDraft has been archived."
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Draft ID: `{draft_id[:8]}...`"
                            }
                        ]
                    }
                ]
            })

        elif action_id == "edit_draft":
            # Queue revision request
            background_tasks.add_task(
                resume_bdr_with_approval,
                draft_id=draft_id,
                action="revise",
                user_name=user_name,
                feedback="Please revise the draft"
            )

            return JSONResponse({
                "response_type": "in_channel",
                "replace_original": True,
                "text": f"✏️ *Revision requested by {user_name}.*",
                "blocks": [
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"✏️ *Revision requested by {user_name}.*\nBDR agent is revising the draft..."
                        }
                    },
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": f"Draft ID: `{draft_id[:8]}...`"
                            }
                        ]
                    }
                ]
            })

        else:
            logger.warning(f"Unknown Slack action: {action_id}")
            return JSONResponse({"text": f"Unknown action: {action_id}"})

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Slack payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    except Exception as e:
        logger.error(f"Error handling Slack webhook: {e}", exc_info=True)
        # Still return 200 to Slack to prevent retries
        return JSONResponse({
            "response_type": "ephemeral",
            "text": f"⚠️ Error processing action: {str(e)}"
        })


async def resume_bdr_with_approval(
    draft_id: str,
    action: str,
    user_name: str,
    feedback: Optional[str] = None
):
    """
    Resume BDR agent after Slack approval/rejection.

    This runs as a background task after responding to Slack immediately.

    Args:
        draft_id: UUID of the draft
        action: Action type (approve, reject, revise)
        user_name: Slack user who took the action
        feedback: Optional feedback for revision
    """
    try:
        # Import here to avoid circular imports
        from app.tasks.agent_tasks import resume_bdr_outreach_task

        # Trigger the Celery task to resume the BDR agent
        task = resume_bdr_outreach_task.delay(
            draft_id=draft_id,
            action=action,
            feedback=feedback,
            approved_by=user_name
        )

        logger.info(f"BDR resume task queued: {task.id} for draft {draft_id} (action: {action})")

    except Exception as e:
        logger.error(f"Failed to queue BDR resume task: {e}", exc_info=True)

        # Send error notification to Slack
        from app.services.slack_notifier import get_slack_notifier
        notifier = get_slack_notifier()
        await notifier.send_status_update(
            draft_id=draft_id,
            company_name="Unknown",
            status="error",
            message=f"Failed to process {action}: {str(e)}"
        )


# ========== Health Check for Webhooks ==========

@router.get("/health")
async def webhook_health():
    """
    Health check for webhook endpoints.

    Returns status of webhook configuration.
    """
    slack_configured = bool(os.getenv("SLACK_BDR_WEBHOOK"))
    signing_configured = bool(os.getenv("SLACK_SIGNING_SECRET"))

    return {
        "status": "healthy",
        "slack": {
            "webhook_configured": slack_configured,
            "signing_configured": signing_configured
        }
    }


# ========== Exports ==========

__all__ = ["router"]
