"""
Slack Notification Service for BDR Agent Approval Workflow

Sends interactive Slack messages with Approve/Reject buttons for BDR email drafts.
When a button is clicked, Slack sends a webhook to our callback URL which triggers
the BDR agent to resume with the decision.

Usage:
    notifier = SlackNotifier()
    await notifier.send_bdr_approval_request(
        draft_id="abc-123",
        company_name="Acme HVAC",
        contact_name="John Smith",
        subject="Quick question about your Carrier certification",
        body_preview="Hi John, I noticed Acme HVAC has been a Carrier dealer..."
    )

Environment Variables:
    SLACK_BDR_WEBHOOK: Slack Incoming Webhook URL for BDR channel
    WEBHOOK_BASE_URL: Base URL for Slack callbacks (e.g., https://your-domain.com)
"""

import os
import logging
from typing import Optional
import httpx

logger = logging.getLogger(__name__)


class SlackNotifier:
    """
    Slack notification service for BDR approval workflow.

    Sends rich Block Kit messages with interactive buttons for
    draft approval, rejection, and editing.
    """

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize SlackNotifier with webhook URL.

        Args:
            webhook_url: Slack Incoming Webhook URL (defaults to env var)
        """
        self.webhook_url = webhook_url or os.getenv("SLACK_BDR_WEBHOOK")
        self.callback_base = os.getenv("WEBHOOK_BASE_URL", "http://localhost:8001")

        if not self.webhook_url:
            logger.warning(
                "SLACK_BDR_WEBHOOK not configured. Slack notifications will be logged only."
            )

    async def send_bdr_approval_request(
        self,
        draft_id: str,
        company_name: str,
        contact_name: str,
        contact_title: Optional[str] = None,
        subject: str = "",
        body_preview: str = "",
        research_summary: Optional[str] = None,
        personal_hooks: Optional[list] = None
    ) -> bool:
        """
        Send Slack notification with Approve/Reject buttons for a BDR email draft.

        Args:
            draft_id: UUID of the draft in dim_ai_drafts
            company_name: Name of the target company
            contact_name: Name of the contact person
            contact_title: Title of the contact (optional)
            subject: Email subject line
            body_preview: First 500 chars of email body
            research_summary: AI research summary (optional)
            personal_hooks: List of extracted personal hooks (optional)

        Returns:
            True if notification sent successfully, False otherwise
        """
        # Truncate body preview if too long
        if len(body_preview) > 500:
            body_preview = body_preview[:497] + "..."

        # Build the Slack Block Kit message
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📧 New BDR Draft for {company_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*To:* {contact_name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Title:* {contact_title or 'N/A'}"
                    }
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Subject:* {subject}"
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{body_preview}```"
                }
            }
        ]

        # Add research summary if available
        if research_summary:
            research_preview = research_summary[:300] + "..." if len(research_summary) > 300 else research_summary
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🔍 *Research:* {research_preview}"
                    }
                ]
            })

        # Add personal hooks if available
        if personal_hooks:
            hooks_text = " | ".join([h.get("category", "") for h in personal_hooks[:3]])
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"🎯 *Hooks:* {hooks_text}"
                    }
                ]
            })

        # Add action buttons
        blocks.append({
            "type": "actions",
            "block_id": f"bdr_actions_{draft_id}",
            "elements": [
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✅ Approve & Send",
                        "emoji": True
                    },
                    "style": "primary",
                    "action_id": "approve_draft",
                    "value": draft_id
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "❌ Reject",
                        "emoji": True
                    },
                    "style": "danger",
                    "action_id": "reject_draft",
                    "value": draft_id
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "✏️ Request Edit",
                        "emoji": True
                    },
                    "action_id": "edit_draft",
                    "value": draft_id
                }
            ]
        })

        # Add footer with draft ID
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Draft ID: `{draft_id[:8]}...` | Click a button to respond"
                }
            ]
        })

        payload = {
            "blocks": blocks,
            "text": f"New BDR Draft for {company_name} - {contact_name}"  # Fallback
        }

        return await self._send_message(payload, draft_id, company_name)

    async def send_status_update(
        self,
        draft_id: str,
        company_name: str,
        status: str,
        message: str
    ) -> bool:
        """
        Send a status update notification (e.g., email sent, draft revised).

        Args:
            draft_id: UUID of the draft
            company_name: Name of the target company
            status: Status type (sent, revised, rejected)
            message: Status message

        Returns:
            True if notification sent successfully
        """
        emoji_map = {
            "sent": "✅",
            "revised": "✏️",
            "rejected": "❌",
            "error": "⚠️"
        }
        emoji = emoji_map.get(status, "📧")

        payload = {
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{emoji} *{company_name}*: {message}"
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
            ],
            "text": f"{status.upper()}: {company_name} - {message}"
        }

        return await self._send_message(payload, draft_id, company_name)

    async def send_batch_summary(
        self,
        drafts_created: int,
        companies: list,
        errors: int = 0
    ) -> bool:
        """
        Send a summary notification for a batch of BDR drafts.

        Args:
            drafts_created: Number of drafts created
            companies: List of company names
            errors: Number of errors encountered

        Returns:
            True if notification sent successfully
        """
        company_list = "\n".join([f"• {c}" for c in companies[:10]])
        if len(companies) > 10:
            company_list += f"\n• ...and {len(companies) - 10} more"

        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"📬 BDR Batch Complete: {drafts_created} Drafts Ready",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Companies:*\n{company_list}"
                    }
                }
            ],
            "text": f"BDR Batch: {drafts_created} drafts ready for review"
        }

        if errors > 0:
            payload["blocks"].append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"⚠️ {errors} errors encountered"
                    }
                ]
            })

        return await self._send_message(payload, "batch", "Batch Summary")

    async def _send_message(
        self,
        payload: dict,
        draft_id: str,
        context: str
    ) -> bool:
        """
        Send message to Slack webhook.

        Args:
            payload: Slack Block Kit payload
            draft_id: Draft ID for logging
            context: Context for logging

        Returns:
            True if sent successfully
        """
        if not self.webhook_url:
            # Log the message if no webhook configured
            logger.info(
                f"[SLACK MOCK] BDR notification for {context} (draft: {draft_id}): "
                f"{payload.get('text', 'No text')}"
            )
            return True

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    self.webhook_url,
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )

                if response.status_code == 200:
                    logger.info(f"Slack notification sent for {context} (draft: {draft_id})")
                    return True
                else:
                    logger.error(
                        f"Slack notification failed: {response.status_code} - {response.text}"
                    )
                    return False

        except httpx.TimeoutException:
            logger.error(f"Slack notification timeout for {context}")
            return False
        except Exception as e:
            logger.error(f"Slack notification error: {e}")
            return False


# Singleton instance for convenience
_notifier_instance: Optional[SlackNotifier] = None


def get_slack_notifier() -> SlackNotifier:
    """Get or create the singleton SlackNotifier instance."""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = SlackNotifier()
    return _notifier_instance


__all__ = ["SlackNotifier", "get_slack_notifier"]
