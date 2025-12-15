"""
Post-Call Review Gate - Meeting confirmation before calendar event.
"""
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)


@dataclass
class MeetingConfirmation:
    """Confirmation result."""
    confirmed: bool
    calendar_event_id: Optional[str] = None
    reschedule_requested: bool = False
    notes: Optional[str] = None
    reviewer: Optional[str] = None


class PostCallGate:
    """Post-call review and meeting confirmation."""

    def __init__(self, slack_webhook_url: str):
        self.slack_webhook_url = slack_webhook_url
        self._pending_confirmations: Dict[str, MeetingConfirmation] = {}

    async def request_meeting_confirmation(
        self,
        call_summary: Dict[str, Any],
        proposed_meeting: Dict[str, Any],
        call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send Slack notification for meeting confirmation."""
        message = self._build_confirmation_message(call_summary, proposed_meeting, call_id)
        logger.info(f"Requesting meeting confirmation for call {call_id}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.slack_webhook_url,
                    json=message,
                    timeout=10.0,
                )
                return {"notification_sent": response.status_code == 200}
            except Exception as e:
                logger.error(f"Failed to send confirmation request: {e}")
                return {"notification_sent": False, "error": str(e)}

    def _build_confirmation_message(
        self,
        call_summary: Dict[str, Any],
        proposed_meeting: Dict[str, Any],
        call_id: Optional[str],
    ) -> Dict:
        """Build Slack message for meeting confirmation."""
        duration_min = call_summary.get("duration_seconds", 0) // 60
        return {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": "📅 Meeting Booked - Confirm?"}},
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Company:*\n{call_summary.get('company_name')}"},
                        {"type": "mrkdwn", "text": f"*Contact:*\n{call_summary.get('contact_name')}"},
                        {"type": "mrkdwn", "text": f"*Call Duration:*\n{duration_min} min"},
                        {"type": "mrkdwn", "text": f"*Outcome:*\n{call_summary.get('outcome')}"},
                    ]
                },
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": f"*Meeting:*\n{proposed_meeting.get('datetime')} ({proposed_meeting.get('duration_minutes', 30)} min)"}
                },
                {
                    "type": "actions",
                    "elements": [
                        {"type": "button", "text": {"type": "plain_text", "text": "✅ Confirm"}, "style": "primary", "action_id": f"confirm_meeting_{call_id}"},
                        {"type": "button", "text": {"type": "plain_text", "text": "🔄 Reschedule"}, "action_id": f"reschedule_meeting_{call_id}"},
                        {"type": "button", "text": {"type": "plain_text", "text": "❌ Reject"}, "style": "danger", "action_id": f"reject_meeting_{call_id}"},
                    ]
                }
            ]
        }

    async def confirm_meeting(
        self,
        call_id: str,
        meeting_time: str,
        attendee_email: str,
    ) -> Dict[str, Any]:
        """Confirm meeting and create calendar event."""
        logger.info(f"Confirming meeting for call {call_id}")
        event = await self._create_calendar_event(
            meeting_time=meeting_time,
            attendee_email=attendee_email,
            call_id=call_id,
        )
        return {
            "calendar_event_created": event is not None,
            "event_id": event.get("event_id") if event else None,
        }

    async def _create_calendar_event(
        self,
        meeting_time: str,
        attendee_email: str,
        call_id: str,
    ) -> Optional[Dict]:
        """Create Google Calendar event (placeholder for integration)."""
        # TODO: Integrate with Google Calendar API
        logger.info(f"Creating calendar event for {attendee_email} at {meeting_time}")
        return {"event_id": f"gcal_{call_id}"}

    def handle_slack_callback(self, call_id: str, action: str, user: str) -> None:
        """Handle Slack button callback."""
        if action.startswith("confirm"):
            self._pending_confirmations[call_id] = MeetingConfirmation(confirmed=True, reviewer=user)
        elif action.startswith("reschedule"):
            self._pending_confirmations[call_id] = MeetingConfirmation(confirmed=False, reschedule_requested=True, reviewer=user)
        else:
            self._pending_confirmations[call_id] = MeetingConfirmation(confirmed=False, reviewer=user)
