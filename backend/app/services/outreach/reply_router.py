"""
Reply Routing Service

Routes classified replies to appropriate handlers based on intent.

Handlers:
- Interested -> Create task for BDR follow-up, Slack alert, CRM update
- Meeting Request -> Send calendar link, Slack alert, create opportunity
- Question -> Queue for human response, Slack alert
- Not Interested -> Mark prospect as unresponsive, stop sequence
- Unsubscribe -> Remove from all sequences, mark as do-not-contact
- Out of Office -> Pause sequence, retry later

Integration:
- SlackNotifier for SDR alerts
- Close CRM for lead status updates
- Supabase for data persistence
"""

import os
import logging
from typing import Optional
from datetime import datetime, timedelta

from app.services.outreach.reply_classifier import (
    ReplyClassification,
    ReplyIntent,
)
from app.services.slack_notifier import get_slack_notifier

logger = logging.getLogger(__name__)


class ReplyRouter:
    """
    Routes classified email replies to appropriate handlers.

    Determines next action based on reply classification.
    Integrates with Slack for SDR alerts and Close CRM for status updates.
    """

    def __init__(self):
        """Initialize reply router with Slack notifier."""
        self.logger = logging.getLogger(f"{__name__}.ReplyRouter")
        self.slack = get_slack_notifier()
        self.calendar_link = os.getenv(
            "CALENDLY_LINK",
            "https://calendly.com/tim-coperniq"
        )

    async def route(
        self,
        classification: ReplyClassification,
        lead_id: Optional[str] = None,
        contact_id: Optional[str] = None,
        prospect_id: Optional[str] = None,
        email_body: Optional[str] = None,
        company_name: Optional[str] = None,
        contact_name: Optional[str] = None,
        from_email: Optional[str] = None
    ) -> dict:
        """
        Route a classified reply to the appropriate handler.

        Args:
            classification: Classification result from ReplyClassifier
            lead_id: Close CRM lead ID
            contact_id: Close CRM contact ID
            prospect_id: Prospect enrollment ID
            email_body: Full email body for context
            company_name: Company name for Slack alerts
            contact_name: Contact name for Slack alerts
            from_email: Sender email address

        Returns:
            dict with action taken and next steps
        """
        self.logger.info(
            f"Routing reply: intent={classification.intent}, "
            f"sentiment={classification.sentiment}, lead_id={lead_id}"
        )

        # Build context for handlers
        ctx = {
            "lead_id": lead_id,
            "contact_id": contact_id,
            "prospect_id": prospect_id,
            "email_body": email_body,
            "company_name": company_name or "Unknown Company",
            "contact_name": contact_name or "Unknown Contact",
            "from_email": from_email,
            "classification": classification,
        }

        # Route based on intent
        handlers = {
            ReplyIntent.INTERESTED: self._handle_interested,
            ReplyIntent.MEETING_REQUEST: self._handle_meeting_request,
            ReplyIntent.QUESTION: self._handle_question,
            ReplyIntent.NOT_INTERESTED: self._handle_not_interested,
            ReplyIntent.UNSUBSCRIBE: self._handle_unsubscribe,
            ReplyIntent.OUT_OF_OFFICE: self._handle_out_of_office,
            ReplyIntent.AUTO_REPLY: self._handle_auto_reply,
            ReplyIntent.UNKNOWN: self._handle_unknown,
        }

        handler = handlers.get(classification.intent, self._handle_unknown)
        return await handler(ctx)

    # ========== Slack Alert Helper ==========

    async def _send_reply_alert(
        self,
        intent: str,
        priority: str,
        message: str,
        company_name: str,
        contact_name: str,
        lead_id: Optional[str] = None,
        email_preview: Optional[str] = None
    ) -> bool:
        """
        Send Slack alert for email reply.

        Args:
            intent: Reply intent type
            priority: Priority emoji/label
            message: Alert message
            company_name: Company name
            contact_name: Contact name
            lead_id: Close CRM lead ID
            email_preview: First 200 chars of email body

        Returns:
            True if alert sent successfully
        """
        # Build Block Kit message for reply alerts
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{priority} Reply: {company_name}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Contact:* {contact_name}"},
                    {"type": "mrkdwn", "text": f"*Intent:* {intent.upper()}"}
                ]
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"💬 {message}"
                }
            }
        ]

        # Add email preview if available
        if email_preview:
            if len(email_preview) > 200:
                preview = email_preview[:200] + "..."
            else:
                preview = email_preview
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{preview}```"
                }
            })

        # Add lead ID context
        if lead_id:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Lead ID: `{lead_id}` | Reply Router"
                    }
                ]
            })

        payload = {
            "blocks": blocks,
            "text": f"{priority} Reply from {company_name}: {message}"
        }

        return await self.slack._send_message(
            payload,
            lead_id or "unknown",
            f"Reply: {company_name}"
        )

    # ========== Intent Handlers ==========

    async def _handle_interested(self, ctx: dict) -> dict:
        """
        Handle interested reply - HIGH PRIORITY.

        Actions:
        1. Send Slack alert to Tim for immediate follow-up
        2. Return action metadata for sequence control
        """
        self.logger.info(
            f"🔥 HOT LEAD: INTERESTED reply for {ctx['company_name']}"
        )

        # Send Slack alert
        slack_sent = await self._send_reply_alert(
            intent="interested",
            priority="🔥 HOT",
            message="Prospect expressed interest! Follow up immediately.",
            company_name=ctx["company_name"],
            contact_name=ctx["contact_name"],
            lead_id=ctx["lead_id"],
            email_preview=ctx.get("email_body")
        )

        return {
            "action": "interested",
            "next_steps": [
                "stop_sequence",
                "create_bdr_task",
                "update_crm_status_engaged"
            ],
            "priority": "high",
            "requires_human_action": True,
            "slack_sent": slack_sent,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _handle_meeting_request(self, ctx: dict) -> dict:
        """
        Handle meeting request - CRITICAL PRIORITY.

        Actions:
        1. Send Slack alert with calendar link
        2. Return action metadata for opportunity creation
        """
        self.logger.info(
            f"📅 MEETING REQUEST from {ctx['company_name']}"
        )

        # Send Slack alert with calendar link
        slack_sent = await self._send_reply_alert(
            intent="meeting_request",
            priority="📅 MEETING",
            message=f"Wants to schedule a call! Calendar: {self.calendar_link}",
            company_name=ctx["company_name"],
            contact_name=ctx["contact_name"],
            lead_id=ctx["lead_id"],
            email_preview=ctx.get("email_body")
        )

        return {
            "action": "meeting_request",
            "next_steps": [
                "stop_sequence",
                "send_calendar_link",
                "create_opportunity",
                "update_crm_status_meeting"
            ],
            "priority": "critical",
            "requires_human_action": True,
            "calendar_link": self.calendar_link,
            "slack_sent": slack_sent,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _handle_question(self, ctx: dict) -> dict:
        """
        Handle question reply - MEDIUM PRIORITY.

        Actions:
        1. Send Slack alert with question context
        2. Pause sequence until answered
        """
        self.logger.info(
            f"❓ QUESTION from {ctx['company_name']}"
        )

        # Send Slack alert with question
        slack_sent = await self._send_reply_alert(
            intent="question",
            priority="❓ QUESTION",
            message="Prospect has questions - needs human response.",
            company_name=ctx["company_name"],
            contact_name=ctx["contact_name"],
            lead_id=ctx["lead_id"],
            email_preview=ctx.get("email_body")
        )

        return {
            "action": "question",
            "next_steps": [
                "pause_sequence",
                "queue_human_response"
            ],
            "priority": "medium",
            "requires_human_action": True,
            "slack_sent": slack_sent,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _handle_not_interested(self, ctx: dict) -> dict:
        """
        Handle not interested reply - LOW PRIORITY.

        Actions:
        1. Stop all sequences
        2. Mark for nurture in 6 months
        """
        self.logger.info(
            f"👎 NOT INTERESTED from {ctx['company_name']}"
        )

        nurture_date = datetime.utcnow() + timedelta(days=180)

        return {
            "action": "not_interested",
            "next_steps": [
                "stop_all_sequences",
                "update_crm_status_unqualified",
                "schedule_nurture"
            ],
            "priority": "low",
            "requires_human_action": False,
            "nurture_date": nurture_date.isoformat(),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _handle_unsubscribe(self, ctx: dict) -> dict:
        """
        Handle unsubscribe request - CRITICAL (COMPLIANCE).

        Actions:
        1. Stop ALL sequences immediately
        2. Add to global suppression list
        3. Update CRM with do-not-contact flag
        """
        self.logger.warning(
            f"🚫 UNSUBSCRIBE from {ctx['company_name']} - COMPLIANCE ACTION"
        )

        return {
            "action": "unsubscribe",
            "next_steps": [
                "stop_all_sequences_immediate",
                "add_to_suppression_list",
                "update_crm_do_not_contact",
                "log_compliance_action"
            ],
            "priority": "critical",
            "requires_human_action": False,
            "compliance_logged": True,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _handle_out_of_office(self, ctx: dict) -> dict:
        """
        Handle out-of-office auto-reply.

        Actions:
        1. Pause sequence for 7 days
        2. Schedule auto-resume
        """
        self.logger.info(
            f"🏖️ OUT OF OFFICE from {ctx['company_name']}"
        )

        resume_date = datetime.utcnow() + timedelta(days=7)

        return {
            "action": "out_of_office",
            "next_steps": [
                "pause_sequence_7d",
                "schedule_auto_resume"
            ],
            "priority": "low",
            "requires_human_action": False,
            "resume_date": resume_date.isoformat(),
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _handle_auto_reply(self, ctx: dict) -> dict:
        """
        Handle generic auto-reply.

        Actions:
        1. Continue sequence (don't count as human response)
        2. Log activity
        """
        self.logger.info(
            f"🤖 AUTO REPLY from {ctx['company_name']} - continuing sequence"
        )

        return {
            "action": "auto_reply",
            "next_steps": [
                "continue_sequence",
                "log_activity"
            ],
            "priority": "low",
            "requires_human_action": False,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _handle_unknown(self, ctx: dict) -> dict:
        """
        Handle unknown reply type.

        Actions:
        1. Pause sequence
        2. Queue for human review
        3. Send Slack notification
        """
        self.logger.warning(
            f"❔ UNKNOWN reply from {ctx['company_name']} - needs review"
        )

        # Send Slack alert for review
        slack_sent = await self._send_reply_alert(
            intent="unknown",
            priority="❔ REVIEW",
            message="Could not classify - needs human review.",
            company_name=ctx["company_name"],
            contact_name=ctx["contact_name"],
            lead_id=ctx["lead_id"],
            email_preview=ctx.get("email_body")
        )

        return {
            "action": "unknown",
            "next_steps": [
                "pause_sequence",
                "queue_human_review"
            ],
            "priority": "medium",
            "requires_human_action": True,
            "slack_sent": slack_sent,
            "timestamp": datetime.utcnow().isoformat()
        }


__all__ = ["ReplyRouter"]
