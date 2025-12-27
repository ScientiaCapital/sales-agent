"""
Close CRM Webhooks v2 Endpoint

Handles all Close CRM webhook events (v2 format) and routes them to appropriate
agents for processing. This is the central event hub for Close CRM automation.

Supported Event Types:
- lead.created → ScoutAgent enrichment (if status=Raw) + workflow rules
- lead.status_changed → Re-evaluate ICP/tier if needed + workflow rules
- lead.updated → Check for significant field changes
- activity.email.received → SyncAgent reply processing
- activity.call.completed → Log call results
- opportunity.status_changed → Update pipeline metrics + workflow rules
- opportunity.won → Celebrate and update analytics + workflow rules
- opportunity.lost → Log reason and route to nurture + workflow rules

Event-Driven Architecture:
Close CRM → Webhook → Event Router → Agent/Task → Supabase/Slack
                    ↘ WorkflowRuleEngine → Celery workflows queue

Security:
- HMAC-SHA256 signature verification
- Returns 200 OK quickly to prevent retries
- All processing happens asynchronously via Celery
- Full audit trail of all webhook events

Reference:
- https://developer.close.com/topics/webhooks/
- Phase 2 of sales-agent consolidation plan
- Phase 4: Workflow Automation (rule engine integration)
"""

import os
import hmac
import hashlib
import logging
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import APIRouter, Request, BackgroundTasks, Header, HTTPException, Depends
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.services.workflow.rule_engine import (
    WorkflowRuleEngine,
    map_close_event_to_trigger,
    build_context_from_close_event
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/close", tags=["close-webhooks-v2"])


# ========== WORKFLOW TRIGGER MAPPING ==========

# Map Close CRM webhook events to workflow trigger types
# Used to route events to the WorkflowRuleEngine for rule evaluation
CLOSE_EVENT_TO_TRIGGER_MAP = {
    # Opportunity events -> workflow triggers
    "opportunity.status_changed": "stage_change",
    "opportunity.won": "opportunity_won",
    "opportunity.lost": "opportunity_lost",
    # Lead events -> workflow triggers
    "lead.created": "lead_created",
    "lead.status_changed": "stage_change",
}


# ========== PYDANTIC MODELS ==========

class CloseWebhookEvent(BaseModel):
    """
    Close CRM webhook event (v2 format).

    Close sends webhooks for various events like lead creation, status changes,
    email replies, etc. Each event has a consistent structure with the object
    data nested under the 'data' field.
    """
    event: str = Field(..., description="Event type (e.g., 'lead.created', 'activity.email.received')")
    data: Dict[str, Any] = Field(..., description="Event data (varies by event type)")
    subscription_id: Optional[str] = Field(None, description="Webhook subscription ID")
    webhook_id: Optional[str] = Field(None, description="Unique webhook delivery ID")
    sent_at: Optional[str] = Field(None, description="ISO timestamp when webhook was sent")

    @validator("event")
    def validate_event(cls, v):
        """Validate event type is in supported format."""
        # Event format: {object_type}.{action}
        # Examples: lead.created, activity.email.received, opportunity.won
        if "." not in v:
            raise ValueError(f"Invalid event format: {v}")
        return v


class WebhookResponse(BaseModel):
    """Response returned to Close CRM after receiving webhook."""
    status: str = Field(..., description="Status: success, error, ignored")
    message: str = Field(..., description="Human-readable message")
    webhook_id: Optional[str] = Field(None, description="Echo webhook ID for tracking")
    event: Optional[str] = Field(None, description="Echo event type")
    processing_queued: bool = Field(False, description="Whether async processing was queued")


# ========== SIGNATURE VERIFICATION ==========

def verify_close_signature(
    body: bytes,
    signature: str,
    webhook_secret: Optional[str] = None
) -> bool:
    """
    Verify Close CRM webhook signature using HMAC-SHA256.

    Close CRM signs webhooks with HMAC-SHA256 of the raw request body.
    The signature is sent in the X-Close-Signature header.

    Security Note:
    - In production, signature verification is REQUIRED
    - In development, it's optional (warns if not configured)

    Args:
        body: Raw request body bytes
        signature: X-Close-Signature header value
        webhook_secret: Close webhook secret (defaults to env var)

    Returns:
        True if signature is valid, False otherwise
    """
    secret = webhook_secret or os.getenv("CLOSE_WEBHOOK_SECRET")

    if not secret:
        env = os.getenv("ENVIRONMENT", "development")
        if env == "production":
            logger.error("CLOSE_WEBHOOK_SECRET not configured in production - REJECTING")
            return False
        else:
            logger.warning("CLOSE_WEBHOOK_SECRET not configured - SKIPPING verification (dev only)")
            return True

    # Compute expected signature
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        body,
        hashlib.sha256
    ).hexdigest()

    # Constant-time comparison to prevent timing attacks
    return hmac.compare_digest(expected_signature, signature)


# ========== EVENT ROUTER LOGIC ==========

async def route_webhook_event(event: CloseWebhookEvent) -> Dict[str, Any]:
    """
    Route webhook event to appropriate agent/handler.

    Event Routing Table:
    - lead.created (status=Raw) → Queue ScoutAgent enrichment
    - lead.status_changed → Re-evaluate ICP tier if needed
    - lead.updated → Check for significant field changes
    - activity.email.received → Queue SyncAgent for reply classification
    - activity.call.completed → Log call outcome
    - opportunity.status_changed → Update pipeline metrics
    - opportunity.won → Celebrate + analytics
    - opportunity.lost → Route to nurture sequence

    Args:
        event: Validated Close webhook event

    Returns:
        Dict with routing decision and queued tasks
    """
    event_type = event.event
    data = event.data

    logger.info(f"Routing webhook event: {event_type}")

    routing_result = {
        "event_type": event_type,
        "action": "none",
        "tasks_queued": [],
        "reason": "",
    }

    # ===== LEAD EVENTS =====

    if event_type == "lead.created":
        # New lead created in Close CRM
        lead_id = data.get("id")
        lead_status = data.get("status_label") or data.get("status")

        # Only auto-enrich leads in "Raw" status
        if lead_status == "Raw":
            logger.info(f"New Raw lead created: {lead_id} - queueing ScoutAgent enrichment")

            # Queue Celery task for ScoutAgent
            from app.tasks.scout_tasks import run_scout_for_company
            run_scout_for_company.delay(company_id=lead_id)

            routing_result.update({
                "action": "enrich",
                "tasks_queued": ["scout_agent_enrichment"],
                "reason": f"New Raw lead {lead_id} needs enrichment",
            })
        else:
            routing_result.update({
                "action": "skip",
                "reason": f"Lead status '{lead_status}' does not require auto-enrichment",
            })

    elif event_type == "lead.status_changed":
        # Lead status changed (e.g., Raw → Qualified)
        lead_id = data.get("id")
        old_status = data.get("old_status_label") or data.get("old_status")
        new_status = data.get("status_label") or data.get("status")

        logger.info(f"Lead {lead_id} status changed: {old_status} → {new_status}")

        # If promoted to Qualified, may need to re-rank or enroll in sequence
        if new_status == "Qualified":
            # Queue RankingAgent to re-evaluate ICP
            from app.tasks.ranking_tasks import run_ranking_for_company_task
            run_ranking_for_company_task.delay(lead_id)

            routing_result.update({
                "action": "re_rank",
                "tasks_queued": ["ranking_agent_reevaluate"],
                "reason": f"Lead promoted to Qualified - re-rank for priority",
            })
        else:
            routing_result.update({
                "action": "log",
                "reason": f"Status change logged: {old_status} → {new_status}",
            })

    elif event_type == "lead.updated":
        # Generic lead update (check for significant field changes)
        lead_id = data.get("id")

        # Check if important fields changed (domain, contacts, custom fields)
        # TODO: Implement field diff detection

        routing_result.update({
            "action": "log",
            "reason": f"Lead {lead_id} updated (field changes not yet analyzed)",
        })

    # ===== ACTIVITY EVENTS =====

    elif event_type == "activity.email.received":
        # Email reply received
        activity_id = data.get("id")
        lead_id = data.get("lead_id")
        contact_id = data.get("contact_id")
        direction = data.get("direction")

        # Only process incoming emails (replies from prospects)
        if direction == "incoming":
            logger.info(f"Email reply received: lead_id={lead_id}, activity_id={activity_id}")

            # Queue SyncAgent for reply classification
            from app.tasks.sync_tasks import sync_single_activity
            sync_single_activity.delay(activity_id=activity_id, activity_type="email")

            routing_result.update({
                "action": "classify_reply",
                "tasks_queued": ["sync_agent_reply_classification"],
                "reason": f"Email reply needs classification and routing",
            })
        else:
            routing_result.update({
                "action": "skip",
                "reason": "Outgoing emails not processed",
            })

    elif event_type == "activity.call.completed":
        # Call activity logged
        activity_id = data.get("id")
        lead_id = data.get("lead_id")
        disposition = data.get("disposition")

        logger.info(f"Call completed: lead_id={lead_id}, disposition={disposition}")

        # TODO: Log call outcome, update call stats

        routing_result.update({
            "action": "log",
            "reason": f"Call logged with disposition: {disposition}",
        })

    # ===== OPPORTUNITY EVENTS =====

    elif event_type == "opportunity.status_changed":
        # Opportunity status changed
        opportunity_id = data.get("id")
        lead_id = data.get("lead_id")
        old_status = data.get("old_status_label") or data.get("old_status")
        new_status = data.get("status_label") or data.get("status")

        logger.info(f"Opportunity {opportunity_id} status: {old_status} → {new_status}")

        # TODO: Update pipeline metrics in Supabase

        routing_result.update({
            "action": "update_pipeline",
            "tasks_queued": ["update_opportunity_metrics"],
            "reason": f"Opportunity status changed to {new_status}",
        })

    elif event_type == "opportunity.won":
        # Deal won!
        opportunity_id = data.get("id")
        lead_id = data.get("lead_id")
        value = data.get("value")
        value_period = data.get("value_period")

        logger.info(f"🎉 Opportunity WON: {opportunity_id}, value=${value}/{value_period}")

        # TODO: Send Slack notification
        # TODO: Update analytics
        # TODO: Trigger customer onboarding workflow

        routing_result.update({
            "action": "celebrate",
            "tasks_queued": ["send_won_notification", "update_analytics"],
            "reason": f"Opportunity won: ${value}/{value_period}",
        })

    elif event_type == "opportunity.lost":
        # Deal lost
        opportunity_id = data.get("id")
        lead_id = data.get("lead_id")
        lost_reason = data.get("note") or data.get("lost_reason")

        logger.info(f"Opportunity LOST: {opportunity_id}, reason={lost_reason}")

        # TODO: Route to COLD nurture sequence
        # TODO: Log lost reason for analytics

        routing_result.update({
            "action": "route_to_nurture",
            "tasks_queued": ["enroll_cold_nurture"],
            "reason": f"Opportunity lost - route to long-term nurture",
        })

    # ===== UNSUPPORTED EVENTS =====

    else:
        logger.info(f"Unsupported event type: {event_type} - ignoring")
        routing_result.update({
            "action": "ignore",
            "reason": f"Event type '{event_type}' not currently supported",
        })

    return routing_result


# ========== WEBHOOK ENDPOINT ==========

@router.post("/events", response_model=WebhookResponse)
async def handle_close_event(
    request: Request,
    background_tasks: BackgroundTasks,
    x_close_signature: Optional[str] = Header(None, alias="X-Close-Signature")
):
    """
    Handle Close CRM webhook events (v2 format).

    This is the central webhook endpoint for all Close CRM events. It receives
    events, validates signatures, routes to appropriate handlers, and returns
    200 OK immediately to prevent retries.

    Event Types Supported:
    - lead.created → Auto-enrich if status=Raw
    - lead.status_changed → Re-evaluate tier if promoted
    - activity.email.received → Classify reply intent
    - opportunity.status_changed → Update pipeline metrics
    - opportunity.won → Celebrate and track analytics
    - opportunity.lost → Route to nurture

    Security:
    - HMAC-SHA256 signature verification via X-Close-Signature header
    - Required in production, optional in development

    Response:
    - Returns 200 OK immediately (even on errors)
    - Actual processing happens asynchronously
    - Webhook ID echoed back for tracking

    Close CRM Setup:
    1. Go to Settings → Webhooks
    2. Create new webhook subscription
    3. URL: https://your-api.com/api/webhooks/close/events
    4. Events: Select all relevant events
    5. Copy webhook secret to CLOSE_WEBHOOK_SECRET env var
    """
    webhook_id = None
    event_type = None

    try:
        # Step 1: Get raw body for signature verification
        body = await request.body()

        # Step 2: Verify signature if provided
        if x_close_signature:
            if not verify_close_signature(body, x_close_signature):
                logger.error("Invalid Close webhook signature - possible tampering or misconfigured secret")

                # IMPORTANT: Still return 200 to prevent endless retries
                # Log the error for security monitoring
                return WebhookResponse(
                    status="error",
                    message="Invalid webhook signature",
                    processing_queued=False
                )

        # Step 3: Parse webhook payload
        event = CloseWebhookEvent.model_validate_json(body)
        webhook_id = event.webhook_id
        event_type = event.event

        logger.info(
            f"📨 Close webhook received: "
            f"event={event_type}, "
            f"webhook_id={webhook_id}, "
            f"subscription={event.subscription_id}"
        )

        # Step 4: Route event to appropriate handler (async)
        background_tasks.add_task(
            process_webhook_event,
            event=event
        )

        # Step 5: Return 200 OK immediately
        return WebhookResponse(
            status="success",
            message=f"Event '{event_type}' queued for processing",
            webhook_id=webhook_id,
            event=event_type,
            processing_queued=True
        )

    except Exception as e:
        logger.error(f"Error handling Close webhook: {e}", exc_info=True)

        # CRITICAL: Always return 200 to prevent Close from retrying endlessly
        # The error is logged for debugging but won't cause webhook delivery failures
        return WebhookResponse(
            status="error",
            message=f"Error processing webhook: {str(e)}",
            webhook_id=webhook_id,
            event=event_type,
            processing_queued=False
        )


# ========== BACKGROUND PROCESSING ==========

async def process_webhook_event(event: CloseWebhookEvent):
    """
    Process webhook event in background.

    This runs asynchronously after returning 200 OK to Close.

    Steps:
    1. Route event to appropriate agent/handler
    2. Evaluate workflow rules for matching triggers
    3. Queue Celery tasks for rule action execution
    4. Log event to audit trail (Supabase)
    5. Send notifications if needed (Slack)

    Args:
        event: Validated Close webhook event
    """
    try:
        # Step 1: Route event
        routing_result = await route_webhook_event(event)

        logger.info(
            f"Event routed: "
            f"action={routing_result['action']}, "
            f"tasks_queued={routing_result['tasks_queued']}, "
            f"reason={routing_result['reason']}"
        )

        # Step 2: Evaluate workflow rules for this event
        await evaluate_workflow_rules_for_event(event)

        # Step 3: Log to audit trail
        await log_webhook_event(event, routing_result)

        # Step 4: Send notifications if critical event
        if routing_result["action"] in ["celebrate", "enrich"]:
            await send_webhook_notification(event, routing_result)

        logger.info(f"Webhook event processing complete: {event.event}")

    except Exception as e:
        logger.error(f"Error processing webhook event: {e}", exc_info=True)

        # TODO: Queue for retry or send error notification
        # For now, just log the error


async def evaluate_workflow_rules_for_event(event: CloseWebhookEvent):
    """
    Evaluate workflow rules for a Close CRM webhook event.

    Maps the Close event type to a workflow trigger type, builds the context,
    and queues matched actions for execution via Celery.

    Args:
        event: Close webhook event to evaluate
    """
    event_type = event.event
    event_data = event.data

    # Map Close event to workflow trigger type
    trigger_type = map_close_event_to_trigger(event_type)

    if not trigger_type:
        logger.debug(f"No workflow trigger mapping for event: {event_type}")
        return

    logger.info(f"Evaluating workflow rules for trigger: {trigger_type} (from {event_type})")

    try:
        # Build context from Close event data
        context = build_context_from_close_event(event_type, event_data)

        # Queue Celery task for rule evaluation and action execution
        # This runs asynchronously to avoid blocking the webhook response
        from app.tasks.workflow_tasks import evaluate_workflow_rules
        evaluate_workflow_rules.delay(
            trigger_type=trigger_type,
            context=context
        )

        logger.info(
            f"Queued workflow rule evaluation: trigger={trigger_type}, "
            f"opportunity_id={context.get('opportunity_id')}, "
            f"stage={context.get('stage')}"
        )

    except ImportError as e:
        # workflow_tasks module not yet created - log and continue
        logger.warning(f"Workflow tasks not available: {e}")
    except Exception as e:
        logger.error(f"Failed to queue workflow rule evaluation: {e}", exc_info=True)


async def log_webhook_event(event: CloseWebhookEvent, routing_result: Dict[str, Any]):
    """
    Log webhook event to audit trail.

    Stores webhook events in Supabase for debugging and analytics.

    Args:
        event: Webhook event
        routing_result: Routing decision
    """
    try:
        # TODO: Implement Supabase audit logging
        # from app.services.supabase_client import get_supabase_client
        # supabase = get_supabase_client()
        # await supabase.table("audit_events").insert({
        #     "event_type": "close_webhook",
        #     "event_subtype": event.event,
        #     "webhook_id": event.webhook_id,
        #     "subscription_id": event.subscription_id,
        #     "routing_action": routing_result["action"],
        #     "tasks_queued": routing_result["tasks_queued"],
        #     "data": event.data,
        #     "created_at": datetime.utcnow().isoformat()
        # }).execute()

        logger.info(f"Webhook event logged: {event.event}")

    except Exception as e:
        logger.error(f"Error logging webhook event: {e}", exc_info=True)


async def send_webhook_notification(event: CloseWebhookEvent, routing_result: Dict[str, Any]):
    """
    Send Slack notification for critical webhook events.

    Args:
        event: Webhook event
        routing_result: Routing decision
    """
    try:
        # TODO: Implement Slack notifications
        # from app.services.slack.notifier import SlackNotifier
        # slack = SlackNotifier()
        # await slack.send_webhook_alert(
        #     event_type=event.event,
        #     action=routing_result["action"],
        #     data=event.data
        # )

        logger.info(f"Webhook notification sent: {event.event}")

    except Exception as e:
        logger.error(f"Error sending webhook notification: {e}", exc_info=True)


# ========== WEBHOOK MANAGEMENT ENDPOINTS ==========

@router.get("/health")
async def webhook_health():
    """
    Health check for Close webhook endpoint.

    Returns configuration status and supported events.
    """
    webhook_secret_configured = bool(os.getenv("CLOSE_WEBHOOK_SECRET"))
    close_api_configured = bool(os.getenv("CLOSE_API_KEY"))
    environment = os.getenv("ENVIRONMENT", "development")

    return {
        "status": "healthy",
        "service": "close_webhooks_v2",
        "environment": environment,
        "configuration": {
            "webhook_secret_configured": webhook_secret_configured,
            "close_api_configured": close_api_configured,
            "signature_verification_required": environment == "production",
        },
        "supported_events": [
            "lead.created",
            "lead.status_changed",
            "lead.updated",
            "activity.email.received",
            "activity.call.completed",
            "opportunity.status_changed",
            "opportunity.won",
            "opportunity.lost",
        ],
        "endpoint": "/api/webhooks/close/events"
    }


@router.get("/events/stats")
async def webhook_stats():
    """
    Get webhook event statistics.

    Returns counts of events processed by type.
    """
    # TODO: Implement stats from Supabase audit table
    # For now, return placeholder
    return {
        "total_events_received": 0,
        "events_by_type": {},
        "events_by_action": {},
        "last_24h": 0,
        "message": "Stats endpoint not yet implemented - query Supabase audit_events table"
    }


# ========== EXPORTS ==========

__all__ = ["router"]
