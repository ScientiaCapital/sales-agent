"""
Pre-Call Review Gate - Slack approval before dialing.
"""
import asyncio
import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass
import httpx

logger = logging.getLogger(__name__)


@dataclass
class ApprovalResult:
    """Result of approval request."""
    approved: bool
    reason: str
    modified_script: Optional[str] = None
    approver: Optional[str] = None


class PreCallGate:
    """Slack-based pre-call approval gate."""

    def __init__(
        self,
        slack_webhook_url: str,
        timeout_seconds: int = 300,
    ):
        self.slack_webhook_url = slack_webhook_url
        self.timeout_seconds = timeout_seconds
        self._pending_approvals: Dict[str, Optional[ApprovalResult]] = {}

    async def request_approval(
        self,
        lead: Dict[str, Any],
        script_preview: str,
        call_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Send Slack notification requesting approval."""
        message = self._build_slack_message(lead, script_preview, call_id)
        logger.info(f"Requesting approval for call {call_id}")

        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    self.slack_webhook_url,
                    json=message,
                    timeout=10.0,
                )
                return {
                    "notification_sent": response.status_code == 200,
                    "call_id": call_id,
                }
            except Exception as e:
                logger.error(f"Failed to send Slack notification: {e}")
                return {"notification_sent": False, "error": str(e)}

    def _build_slack_message(
        self,
        lead: Dict[str, Any],
        script_preview: str,
        call_id: Optional[str],
    ) -> Dict:
        """Build Slack Block Kit message."""
        return {
            "blocks": [
                {"type": "header", "text": {"type": "plain_text", "text": "📞 AI Call Request"}},
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Company:*\n{lead.get('company_name', 'Unknown')}"},
                        {"type": "mrkdwn", "text": f"*Contact:*\n{lead.get('contact_name', 'Unknown')}"},
                        {"type": "mrkdwn", "text": f"*Phone:*\n{lead.get('phone', 'Unknown')}"},
                    ]
                },
                {"type": "section", "text": {"type": "mrkdwn", "text": f"*Script:*\n```{script_preview[:500]}```"}},
                {
                    "type": "actions",
                    "elements": [
                        {"type": "button", "text": {"type": "plain_text", "text": "✅ Approve"}, "style": "primary", "action_id": f"approve_call_{call_id}"},
                        {"type": "button", "text": {"type": "plain_text", "text": "⏭️ Skip"}, "action_id": f"skip_call_{call_id}"},
                    ]
                }
            ]
        }

    async def wait_for_approval(self, call_id: str) -> Dict[str, Any]:
        """Wait for approval with timeout."""
        self._pending_approvals[call_id] = None
        elapsed = 0

        while elapsed < self.timeout_seconds:
            result = await self._check_approval(call_id)
            if result is not None:
                logger.info(f"Call {call_id} {result.reason} by {result.approver}")
                return {"approved": result.approved, "reason": result.reason}
            await asyncio.sleep(1)
            elapsed += 1

        logger.info(f"Call {call_id} timed out waiting for approval")
        return {"approved": False, "reason": "timeout"}

    async def _check_approval(self, call_id: str) -> Optional[ApprovalResult]:
        """Check if approval received."""
        return self._pending_approvals.get(call_id)

    def handle_slack_callback(self, call_id: str, action: str, user: str) -> None:
        """Handle Slack button callback."""
        if action.startswith("approve"):
            self._pending_approvals[call_id] = ApprovalResult(approved=True, reason="approved", approver=user)
        else:
            self._pending_approvals[call_id] = ApprovalResult(approved=False, reason="rejected", approver=user)
