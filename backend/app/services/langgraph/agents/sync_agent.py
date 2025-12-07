"""
SyncAgent - Close CRM Synchronization & Reply Handling

Consolidates three sync tasks into one unified agent:
1. CloseSyncTask - Sync activities from Close CRM
2. ReplyPollingTask - Poll for email replies
3. SequenceAdvanceTask - Advance multi-step sequences

Schedule: Every 5 minutes
Event Trigger: Close CRM webhook
Emits: reply_received event

Pipeline:
sync_activities → poll_replies → classify_replies → route_to_handler → advance_sequences

Phase: 1 of 6 (Consolidation)
"""

from typing import Dict, List, Any, Optional, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
import logging
import os

# Disable LangSmith tracing BEFORE importing langgraph
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")
os.environ.setdefault("LANGCHAIN_TRACING", "false")

from langgraph.graph import StateGraph, END
from app.services.langgraph.agents.base_agent import BaseAgent
from app.services.crm.close_email import CloseEmailClient
from app.services.crm.close_sequences import CloseSequencesClient
from app.services.outreach.reply_classifier import ReplyClassifier, ReplyIntent
from app.services.outreach.reply_router import ReplyRouter

logger = logging.getLogger(__name__)


# ============================================================================
# STATE DEFINITION
# ============================================================================

class SyncAgentState(BaseModel):
    """State for SyncAgent workflow."""

    # Inputs
    task_name: str = Field(default="sync_agent")
    last_sync_timestamp: Optional[datetime] = None
    trigger_source: Literal["schedule", "webhook", "manual"] = "schedule"
    webhook_event_data: Optional[Dict[str, Any]] = None

    # Activities sync
    activities_synced: int = 0
    emails_synced: int = 0
    sms_synced: int = 0
    calls_synced: int = 0

    # Reply polling
    replies_found: int = 0
    replies_classified: Dict[str, int] = Field(default_factory=lambda: {
        "interested": 0,
        "not_interested": 0,
        "questions": 0,
        "out_of_office": 0,
        "meeting_request": 0,
        "unsubscribe": 0,
        "unknown": 0
    })

    # Sequence advancement
    sequences_advanced: int = 0
    outreach_sent: int = 0
    sequences_completed: int = 0
    sequences_paused: int = 0

    # Events emitted
    events_emitted: List[Dict[str, Any]] = Field(default_factory=list)

    # Error tracking
    errors: List[str] = Field(default_factory=list)

    # Status
    status: Literal["pending", "running", "completed", "failed"] = "pending"

    class Config:
        arbitrary_types_allowed = True


# ============================================================================
# SYNC AGENT
# ============================================================================

class SyncAgent(BaseAgent):
    """
    Unified agent for Close CRM synchronization and reply handling.

    Consolidates:
    - Activity sync (emails, SMS, calls)
    - Reply polling and classification
    - Sequence advancement

    Features:
    - Event-driven architecture (webhook + polling fallback)
    - AI-powered reply classification (Claude Haiku)
    - Automatic sequence control (pause on reply, advance on schedule)
    - Emits reply_received events for downstream agents
    """

    def __init__(self):
        """Initialize SyncAgent with Close CRM clients and classifiers."""
        super().__init__(agent_name="SyncAgent")

        # Close CRM clients
        self.email_client = CloseEmailClient()
        self.sequences_client = CloseSequencesClient()

        # Reply processing
        self.reply_classifier = ReplyClassifier(use_ai=True)  # Claude Haiku
        self.reply_router = ReplyRouter()

        # Build LangGraph workflow
        self.graph = self._build_graph()

        logger.info("SyncAgent initialized - consolidating 3 sync tasks")

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph workflow for sync pipeline.

        Flow:
        sync_activities → poll_replies → classify_replies →
        route_replies → advance_sequences → finalize
        """
        workflow = StateGraph(SyncAgentState)

        # Step 1: Sync activities from Close CRM
        workflow.add_node("sync_activities", self._sync_activities)

        # Step 2: Poll for new email replies
        workflow.add_node("poll_replies", self._poll_replies)

        # Step 3: Classify replies with AI
        workflow.add_node("classify_replies", self._classify_replies)

        # Step 4: Route replies to handlers
        workflow.add_node("route_replies", self._route_replies)

        # Step 5: Advance sequences
        workflow.add_node("advance_sequences", self._advance_sequences)

        # Step 6: Finalize and emit events
        workflow.add_node("finalize", self._finalize)

        # Define edges (sequential pipeline)
        workflow.set_entry_point("sync_activities")
        workflow.add_edge("sync_activities", "poll_replies")
        workflow.add_edge("poll_replies", "classify_replies")
        workflow.add_edge("classify_replies", "route_replies")
        workflow.add_edge("route_replies", "advance_sequences")
        workflow.add_edge("advance_sequences", "finalize")
        workflow.add_edge("finalize", END)

        return workflow.compile()

    # ========================================================================
    # STEP 1: SYNC ACTIVITIES
    # ========================================================================

    async def _sync_activities(self, state: SyncAgentState) -> SyncAgentState:
        """
        Sync email/SMS/call activities from Close CRM.

        Fetches recent activities since last sync timestamp.
        Updates local database with delivery status, opens, clicks.
        """
        logger.info("[SyncAgent] Step 1: Syncing activities from Close CRM")

        try:
            # TODO: Implement activity fetching from Close API
            # Once Close SDK has activity endpoints, fetch like this:
            # activities = await self.email_client.get_activities_since(state.last_sync_timestamp)

            # For now, return mock results
            state.activities_synced = 0
            state.emails_synced = 0
            state.sms_synced = 0
            state.calls_synced = 0

            logger.info(
                f"[SyncAgent] Activities synced: {state.activities_synced} "
                f"({state.emails_synced} emails, {state.sms_synced} SMS, "
                f"{state.calls_synced} calls)"
            )

        except Exception as e:
            error_msg = f"Failed to sync activities: {e}"
            logger.error(f"[SyncAgent] {error_msg}")
            state.errors.append(error_msg)

        return state

    # ========================================================================
    # STEP 2: POLL REPLIES
    # ========================================================================

    async def _poll_replies(self, state: SyncAgentState) -> SyncAgentState:
        """
        Poll Close CRM for new email replies.

        Queries Close API for incoming emails since last poll.
        Fallback to webhook - polling ensures no replies missed.
        """
        logger.info("[SyncAgent] Step 2: Polling for email replies")

        try:
            # Handle webhook trigger (skip polling if webhook provided data)
            if state.trigger_source == "webhook" and state.webhook_event_data:
                logger.info("[SyncAgent] Webhook trigger - processing single reply")
                # TODO: Process webhook event data
                state.replies_found = 1
                return state

            # Polling mode: fetch incoming emails
            # TODO: Implement email polling from Close API
            # Once Close SDK has inbox endpoints, fetch like this:
            # incoming_emails = await self.email_client.get_incoming_emails_since(
            #     state.last_sync_timestamp
            # )

            state.replies_found = 0

            logger.info(f"[SyncAgent] Found {state.replies_found} new replies")

        except Exception as e:
            error_msg = f"Failed to poll replies: {e}"
            logger.error(f"[SyncAgent] {error_msg}")
            state.errors.append(error_msg)

        return state

    # ========================================================================
    # STEP 3: CLASSIFY REPLIES
    # ========================================================================

    async def _classify_replies(self, state: SyncAgentState) -> SyncAgentState:
        """
        Classify email replies using AI.

        Uses Claude Haiku for fast, cheap classification:
        - Interested, Not Interested, Question
        - Out of Office, Meeting Request, Unsubscribe
        """
        logger.info("[SyncAgent] Step 3: Classifying replies with AI")

        if state.replies_found == 0:
            logger.info("[SyncAgent] No replies to classify - skipping")
            return state

        try:
            # TODO: Iterate through replies and classify each
            # For each reply:
            #   classification = await self.reply_classifier.classify(
            #       subject=reply['subject'],
            #       body_text=reply['body'],
            #       from_email=reply['from']
            #   )
            #
            #   # Track classification counts
            #   intent = classification.intent.value
            #   state.replies_classified[intent] = state.replies_classified.get(intent, 0) + 1

            logger.info(
                f"[SyncAgent] Classified {state.replies_found} replies: "
                f"{state.replies_classified}"
            )

        except Exception as e:
            error_msg = f"Failed to classify replies: {e}"
            logger.error(f"[SyncAgent] {error_msg}")
            state.errors.append(error_msg)

        return state

    # ========================================================================
    # STEP 4: ROUTE REPLIES
    # ========================================================================

    async def _route_replies(self, state: SyncAgentState) -> SyncAgentState:
        """
        Route classified replies to appropriate handlers.

        Handlers:
        - Interested -> Emit reply_received event, stop sequence, Slack alert
        - Meeting Request -> Send calendar link, create opportunity
        - Question -> Pause sequence, queue human response
        - Not Interested -> Stop sequences, schedule nurture
        - Unsubscribe -> Stop all, add to suppression list (COMPLIANCE)
        - Out of Office -> Pause sequence 7 days
        """
        logger.info("[SyncAgent] Step 4: Routing replies to handlers")

        if state.replies_found == 0:
            logger.info("[SyncAgent] No replies to route - skipping")
            return state

        try:
            # TODO: Route each classified reply
            # For each reply:
            #   route_result = await self.reply_router.route(
            #       classification=classification,
            #       lead_id=reply['lead_id'],
            #       contact_id=reply['contact_id'],
            #       email_body=reply['body'],
            #       company_name=reply.get('company_name'),
            #       contact_name=reply.get('contact_name'),
            #       from_email=reply['from']
            #   )
            #
            #   # Emit events for downstream agents
            #   if classification.intent in [ReplyIntent.INTERESTED, ReplyIntent.MEETING_REQUEST]:
            #       state.events_emitted.append({
            #           "event": "reply_received",
            #           "lead_id": reply['lead_id'],
            #           "classification": classification.intent.value,
            #           "action": route_result["action"],
            #           "priority": route_result["priority"],
            #           "timestamp": datetime.utcnow().isoformat()
            #       })

            logger.info(
                f"[SyncAgent] Routed {state.replies_found} replies, "
                f"emitted {len(state.events_emitted)} events"
            )

        except Exception as e:
            error_msg = f"Failed to route replies: {e}"
            logger.error(f"[SyncAgent] {error_msg}")
            state.errors.append(error_msg)

        return state

    # ========================================================================
    # STEP 5: ADVANCE SEQUENCES
    # ========================================================================

    async def _advance_sequences(self, state: SyncAgentState) -> SyncAgentState:
        """
        Advance leads through multi-step email sequences.

        Checks for leads due for next step.
        Triggers OutreachAgent to send next message.
        Handles sequence completion and graduation.
        """
        logger.info("[SyncAgent] Step 5: Advancing sequences")

        try:
            # TODO: Implement sequence advancement
            # 1. Query database for leads due for next step
            # 2. For each lead, trigger OutreachAgent to send next message
            # 3. Update sequence state in database
            # 4. Handle completion/graduation

            # Example flow:
            # leads_due = await self._get_leads_due_for_step()
            #
            # for lead in leads_due:
            #     try:
            #         # Get lead's active sequence subscription
            #         subscriptions = await self.sequences_client.get_contact_subscriptions(
            #             contact_id=lead['contact_id'],
            #             active_only=True
            #         )
            #
            #         for sub in subscriptions:
            #             # Check if due for next step
            #             # Advance sequence
            #             state.sequences_advanced += 1
            #             state.outreach_sent += 1
            #     except Exception as e:
            #         logger.error(f"Failed to advance sequence for lead {lead['id']}: {e}")
            #         state.errors.append(str(e))

            state.sequences_advanced = 0
            state.outreach_sent = 0
            state.sequences_completed = 0

            logger.info(
                f"[SyncAgent] Sequences: {state.sequences_advanced} advanced, "
                f"{state.sequences_completed} completed, "
                f"{state.outreach_sent} outreach sent"
            )

        except Exception as e:
            error_msg = f"Failed to advance sequences: {e}"
            logger.error(f"[SyncAgent] {error_msg}")
            state.errors.append(error_msg)

        return state

    # ========================================================================
    # STEP 6: FINALIZE
    # ========================================================================

    async def _finalize(self, state: SyncAgentState) -> SyncAgentState:
        """
        Finalize sync cycle and update state.

        Sets final status, logs summary metrics.
        """
        logger.info("[SyncAgent] Step 6: Finalizing sync cycle")

        # Determine final status
        if state.errors:
            state.status = "failed" if len(state.errors) > 3 else "completed"
        else:
            state.status = "completed"

        # Log summary
        logger.info(
            f"[SyncAgent] Sync cycle complete: "
            f"status={state.status}, "
            f"activities={state.activities_synced}, "
            f"replies={state.replies_found}, "
            f"sequences={state.sequences_advanced}, "
            f"events={len(state.events_emitted)}, "
            f"errors={len(state.errors)}"
        )

        return state

    # ========================================================================
    # PUBLIC API
    # ========================================================================

    async def run_sync_cycle(
        self,
        last_sync_timestamp: Optional[datetime] = None,
        trigger_source: Literal["schedule", "webhook", "manual"] = "schedule",
        webhook_event_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Run complete sync cycle.

        Args:
            last_sync_timestamp: Timestamp of last sync (defaults to 5 min ago)
            trigger_source: Source of trigger (schedule, webhook, manual)
            webhook_event_data: Webhook event data if triggered by webhook

        Returns:
            Dict with sync results including events emitted
        """
        # Initialize state
        if last_sync_timestamp is None:
            last_sync_timestamp = datetime.utcnow() - timedelta(minutes=5)

        initial_state = SyncAgentState(
            task_name="sync_agent",
            last_sync_timestamp=last_sync_timestamp,
            trigger_source=trigger_source,
            webhook_event_data=webhook_event_data,
            status="running"
        )

        # Run graph
        logger.info(
            f"[SyncAgent] Starting sync cycle (source={trigger_source})"
        )
        final_state = await self.graph.ainvoke(initial_state)

        # Return results
        return {
            "status": final_state.status,
            "activities_synced": final_state.activities_synced,
            "emails": final_state.emails_synced,
            "sms": final_state.sms_synced,
            "calls": final_state.calls_synced,
            "replies_found": final_state.replies_found,
            "replies_classified": final_state.replies_classified,
            "sequences_advanced": final_state.sequences_advanced,
            "outreach_sent": final_state.outreach_sent,
            "sequences_completed": final_state.sequences_completed,
            "events_emitted": final_state.events_emitted,
            "errors": final_state.errors,
        }

    async def handle_webhook(
        self,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Handle Close CRM webhook event.

        Args:
            event_type: Event type (e.g., "lead.created", "activity.email.created")
            event_data: Event payload from webhook

        Returns:
            Processing result
        """
        logger.info(f"[SyncAgent] Handling webhook: {event_type}")

        # Route webhook to appropriate handler
        if event_type in ["activity.email.created", "activity.email.received"]:
            # Email activity (potential reply)
            return await self.run_sync_cycle(
                trigger_source="webhook",
                webhook_event_data=event_data
            )
        elif event_type == "lead.created":
            # New lead created - trigger enrichment (not sync)
            logger.info(f"[SyncAgent] New lead created: {event_data.get('id')}")
            return {
                "status": "delegated",
                "message": "New lead event - delegating to ScoutAgent",
                "event_type": event_type
            }
        else:
            logger.warning(f"[SyncAgent] Unhandled webhook type: {event_type}")
            return {
                "status": "ignored",
                "message": f"Event type {event_type} not handled by SyncAgent",
                "event_type": event_type
            }


# Singleton instance
_sync_agent_instance: Optional[SyncAgent] = None


def get_sync_agent() -> SyncAgent:
    """Get or create singleton SyncAgent instance."""
    global _sync_agent_instance
    if _sync_agent_instance is None:
        _sync_agent_instance = SyncAgent()
    return _sync_agent_instance


__all__ = ["SyncAgent", "SyncAgentState", "get_sync_agent"]
