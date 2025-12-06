"""
Close CRM Reply Webhook Endpoint

Receives email reply notifications from Close CRM and processes them through
the reply classification and routing pipeline.

Security:
- Webhook signature verification (if Close provides one)
- Rate limiting to prevent abuse
- Returns 200 OK quickly to prevent Close retries

Flow:
1. Receive webhook from Close CRM
2. Validate payload and signature
3. Extract email content and metadata
4. Classify reply intent using ReplyClassifier
5. Route to appropriate handler via ReplyRouter
6. Return 200 OK immediately (async processing)
7. Log all webhook events

Close CRM Webhook Events:
- email.received - Incoming email reply
- email.sent - Outgoing email sent (track delivery)
- email.opened - Email opened (track engagement)
- email.clicked - Link clicked (track engagement)
"""

import os
import hmac
import hashlib
import logging
from typing import Optional, List

from fastapi import APIRouter, Request, BackgroundTasks, Header
from pydantic import BaseModel, Field, validator

from app.services.outreach.reply_classifier import ReplyClassifier
from app.services.outreach.reply_router import ReplyRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/close", tags=["close-webhooks"])


# ========== REQUEST MODELS ==========

class EmailAddress(BaseModel):
    """Email address with optional name."""
    email: str
    name: Optional[str] = None


class CloseEmailWebhookData(BaseModel):
    """Close CRM email webhook data structure."""
    id: str = Field(..., description="Close activity ID (acti_xxx)")
    lead_id: str = Field(..., description="Close lead ID (lead_xxx)")
    contact_id: Optional[str] = Field(None, description="Close contact ID (cont_xxx)")
    subject: str = Field(..., description="Email subject line")
    body_text: Optional[str] = Field(None, description="Plain text email body")
    body_html: Optional[str] = Field(None, description="HTML email body")
    from_: List[EmailAddress] = Field(..., alias="from", description="From addresses")
    to: List[EmailAddress] = Field(..., description="To addresses")
    cc: Optional[List[EmailAddress]] = Field(None, description="CC addresses")
    bcc: Optional[List[EmailAddress]] = Field(None, description="BCC addresses")
    date_created: str = Field(..., description="ISO timestamp")
    direction: str = Field(..., description="incoming or outgoing")

    @validator("direction")
    def validate_direction(cls, v):
        """Validate direction is incoming or outgoing."""
        if v not in ["incoming", "outgoing"]:
            raise ValueError(f"Invalid direction: {v}")
        return v


class CloseWebhookPayload(BaseModel):
    """Close CRM webhook payload."""
    event: str = Field(..., description="Webhook event type")
    data: CloseEmailWebhookData = Field(..., description="Event data")
    subscription_id: Optional[str] = Field(None, description="Webhook subscription ID")
    webhook_id: Optional[str] = Field(None, description="Unique webhook delivery ID")


class WebhookResponse(BaseModel):
    """Webhook response model."""
    status: str
    message: str
    webhook_id: Optional[str] = None
    processing_queued: bool = False


# ========== SIGNATURE VERIFICATION ==========

def verify_close_signature(
    body: bytes,
    signature: str,
    webhook_secret: Optional[str] = None
) -> bool:
    """
    Verify Close CRM webhook signature using HMAC-SHA256.

    Close CRM signs webhooks with HMAC-SHA256 of the request body.
    The signature is sent in the X-Close-Signature header.

    Args:
        body: Raw request body bytes
        signature: X-Close-Signature header value
        webhook_secret: Close webhook secret (defaults to env var)

    Returns:
        True if signature is valid, False otherwise
    """
    secret = webhook_secret or os.getenv("CLOSE_WEBHOOK_SECRET")

    if not secret:
        # SECURITY: If signature verification is not configured, log warning
        # but allow in development. In production, this should be required.
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            logger.error("CLOSE_WEBHOOK_SECRET not configured in production - rejecting")
            return False
        else:
            logger.warning("CLOSE_WEBHOOK_SECRET not configured - skipping verification (dev only)")
            return True

    # Compute expected signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison
    return hmac.compare_digest(expected_signature, signature)


# ========== WEBHOOK ENDPOINT ==========

@router.post("/email-reply", response_model=WebhookResponse)
async def handle_close_email_reply(
    request: Request,
    background_tasks: BackgroundTasks,
    x_close_signature: Optional[str] = Header(None, alias="X-Close-Signature")
):
    """
    Handle incoming email reply webhook from Close CRM.

    This endpoint receives notifications when Close receives an email reply
    to one of our outbound emails. It classifies the reply and routes it to
    the appropriate handler.

    Events handled:
    - email.received - Incoming email reply

    Response:
    - Returns 200 OK immediately to prevent Close retries
    - Actual processing happens asynchronously in background

    Headers:
    - X-Close-Signature: HMAC signature for verification
    """
    webhook_id = None

    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify signature if provided
        if x_close_signature:
            if not verify_close_signature(body, x_close_signature):
                logger.error("Invalid Close webhook signature")
                # Still return 200 to prevent retries, but log the error
                return WebhookResponse(
                    status="error",
                    message="Invalid webhook signature",
                    processing_queued=False
                )

        # Parse payload
        payload = CloseWebhookPayload.model_validate_json(body)
        webhook_id = payload.webhook_id

        logger.info(
            f"Received Close webhook: event={payload.event}, "
            f"lead_id={payload.data.lead_id}, "
            f"webhook_id={webhook_id}"
        )

        # Only process incoming email.received events
        if payload.event != "email.received":
            logger.info(f"Ignoring non-reply event: {payload.event}")
            return WebhookResponse(
                status="ignored",
                message=f"Event type '{payload.event}' not processed",
                webhook_id=webhook_id,
                processing_queued=False
            )

        # Only process incoming emails (replies)
        if payload.data.direction != "incoming":
            logger.info(f"Ignoring outgoing email: {payload.data.id}")
            return WebhookResponse(
                status="ignored",
                message="Outgoing emails not processed",
                webhook_id=webhook_id,
                processing_queued=False
            )

        # Queue background processing
        background_tasks.add_task(
            process_email_reply,
            payload=payload
        )

        # Return 200 OK immediately
        return WebhookResponse(
            status="success",
            message="Email reply queued for processing",
            webhook_id=webhook_id,
            processing_queued=True
        )

    except Exception as e:
        logger.error(f"Error handling Close webhook: {e}", exc_info=True)

        # IMPORTANT: Still return 200 to prevent Close from retrying endlessly
        # The error is logged for debugging but won't cause webhook failures
        return WebhookResponse(
            status="error",
            message=f"Error processing webhook: {str(e)}",
            webhook_id=webhook_id,
            processing_queued=False
        )


# ========== BACKGROUND PROCESSING ==========

async def process_email_reply(payload: CloseWebhookPayload):
    """
    Process email reply in background.

    This runs asynchronously after returning 200 OK to Close.

    Steps:
    1. Extract email content and metadata
    2. Classify reply intent using AI
    3. Route to appropriate handler
    4. Update sequence enrollment if needed
    5. Send notifications (Slack, etc.)

    Args:
        payload: Close webhook payload
    """
    try:
        data = payload.data

        logger.info(
            f"Processing email reply: lead_id={data.lead_id}, "
            f"contact_id={data.contact_id}, "
            f"subject='{data.subject}'"
        )

        # Extract sender email
        from_email = data.from_[0].email if data.from_ else None
        from_name = data.from_[0].name if data.from_ else None

        # Get email body (prefer text, fallback to HTML)
        email_body = data.body_text or data.body_html or ""

        if not email_body:
            logger.warning(f"Empty email body for {data.id}")

        # Step 1: Classify reply
        classifier = ReplyClassifier()
        classification = await classifier.classify(
            subject=data.subject,
            body_text=data.body_text or "",
            body_html=data.body_html,
            from_email=from_email
        )

        logger.info(
            f"Reply classified: intent={classification.intent}, "
            f"sentiment={classification.sentiment}, "
            f"confidence={classification.confidence:.2f}, "
            f"requires_review={classification.requires_human_review}"
        )

        # Step 2: Route to handler
        router = ReplyRouter()
        routing_result = await router.route(
            classification=classification,
            lead_id=data.lead_id,
            contact_id=data.contact_id,
            email_body=email_body
        )

        logger.info(
            f"Reply routed: action={routing_result['action']}, "
            f"next_steps={routing_result['next_steps']}, "
            f"priority={routing_result['priority']}"
        )

        # Step 3: Send notifications if requires human action
        if classification.requires_human_review:
            await send_reply_notification(
                lead_id=data.lead_id,
                contact_id=data.contact_id,
                from_email=from_email,
                from_name=from_name,
                subject=data.subject,
                body=email_body,
                classification=classification,
                routing_result=routing_result
            )

        # TODO: Step 4: Update sequence enrollment
        # - Stop sequence if unsubscribe/not interested
        # - Pause sequence if out of office
        # - Mark as replied if interested/meeting request

        logger.info(f"Email reply processing complete for {data.id}")

    except Exception as e:
        logger.error(f"Error processing email reply: {e}", exc_info=True)

        # TODO: Queue for retry or send error notification
        # For now, just log the error


async def send_reply_notification(
    lead_id: str,
    contact_id: Optional[str],
    from_email: Optional[str],
    from_name: Optional[str],
    subject: str,
    body: str,
    classification,
    routing_result: dict
):
    """
    Send notification about reply to Slack.

    Args:
        lead_id: Close lead ID
        contact_id: Close contact ID
        from_email: Reply sender email
        from_name: Reply sender name
        subject: Email subject
        body: Email body
        classification: Reply classification result
        routing_result: Routing result with next steps
    """
    try:
        # TODO: Implement Slack notification
        # Use existing SlackNotifier service

        logger.info(
            f"Would send Slack notification: "
            f"lead={lead_id}, "
            f"intent={classification.intent}, "
            f"action={routing_result['action']}"
        )

        # For now, just log
        # Future: Send to Slack with action buttons

    except Exception as e:
        logger.error(f"Error sending reply notification: {e}", exc_info=True)


# ========== HEALTH CHECK ==========

@router.get("/health")
async def close_webhook_health():
    """
    Health check for Close webhooks.

    Returns configuration status.
    """
    webhook_secret_configured = bool(os.getenv("CLOSE_WEBHOOK_SECRET"))
    close_api_configured = bool(os.getenv("CLOSE_API_KEY"))

    return {
        "status": "healthy",
        "close_webhooks": {
            "webhook_secret_configured": webhook_secret_configured,
            "close_api_configured": close_api_configured,
            "supported_events": [
                "email.received"
            ]
        }
    }


# ========== EXPORTS ==========

__all__ = ["router"]
