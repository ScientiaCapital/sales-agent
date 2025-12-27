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
import re
import logging
from typing import Optional
from datetime import date, datetime, timedelta

from app.services.outreach.reply_classifier import (
    ReplyClassification,
    ReplyIntent,
)
from app.services.slack_notifier import get_slack_notifier
from app.services.crm.close_calling import CloseCallingClient
from app.services.crm.close_tasks import CloseTaskClient

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

    # ========== Task Creation Helper ==========

    async def _create_follow_up_task(
        self,
        lead_id: str,
        task_text: str,
        due_date: date,
        intent: ReplyIntent,
        contact_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Create a follow-up task in Close CRM and return task ID.

        Used by intent handlers to automatically create follow-up tasks
        based on reply classification.

        Args:
            lead_id: Close lead ID (required)
            task_text: Task description
            due_date: Task due date
            intent: Reply intent for context
            contact_id: Close contact ID (optional)

        Returns:
            Task ID if created successfully, None otherwise
        """
        if not lead_id:
            self.logger.warning(
                f"Cannot create task without lead_id for intent {intent.value}"
            )
            return None

        try:
            task_client = CloseTaskClient()
            result = await task_client.create_task(
                lead_id=lead_id,
                text=task_text,
                due_date=due_date,
                contact_id=contact_id,
                task_type="follow-up",
            )

            if result.get("status") == "disabled":
                self.logger.warning(
                    f"Task creation disabled for {intent.value} intent"
                )
                return None

            task_id = result.get("id")
            self.logger.info(
                f"Created follow-up task {task_id} for {intent.value}: "
                f"{task_text[:50]}... (due: {due_date})"
            )
            return task_id

        except Exception as e:
            self.logger.error(
                f"Failed to create follow-up task for {intent.value}: {e}"
            )
            return None

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
        1. Extract meeting time from email if available
        2. Create Close meeting activity
        3. Send Slack alert with calendar link
        4. Return action metadata for opportunity creation
        """
        self.logger.info(
            f"📅 MEETING REQUEST from {ctx['company_name']}"
        )

        # Extract meeting time from email body (if available)
        meeting_time = self._extract_meeting_time(ctx.get("email_body", ""))

        # Create meeting in Close CRM
        meeting_created = None
        meeting_id = None
        if ctx.get("lead_id") and ctx.get("contact_id"):
            try:
                close_client = CloseCallingClient()
                meeting_result = await close_client.create_meeting(
                    lead_id=ctx["lead_id"],
                    contact_id=ctx["contact_id"],
                    scheduled_at=meeting_time,
                    duration_minutes=30,
                    title=f"Discovery Call - {ctx['company_name']}",
                    note=f"Meeting requested via email reply from {ctx['contact_name']}",
                )

                if meeting_result.get("status") != "disabled":
                    meeting_created = True
                    meeting_id = meeting_result.get("id")
                    self.logger.info(
                        f"Created Close meeting {meeting_id} for {ctx['company_name']} "
                        f"at {meeting_time}"
                    )
                else:
                    meeting_created = False
                    self.logger.warning(
                        f"Close meeting creation disabled for {ctx['company_name']}"
                    )
            except Exception as e:
                self.logger.error(
                    f"Failed to create Close meeting for {ctx['company_name']}: {e}"
                )
                meeting_created = False

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

        # Create follow-up task for day after meeting
        task_id = None
        if meeting_created and meeting_time:
            # Task due day after meeting
            follow_up_date = (meeting_time + timedelta(days=1)).date()
            task_text = f"Send follow-up after meeting with {ctx['contact_name']} ({ctx['company_name']})"
            task_id = await self._create_follow_up_task(
                lead_id=ctx.get("lead_id"),
                task_text=task_text,
                due_date=follow_up_date,
                intent=ReplyIntent.MEETING_REQUEST,
                contact_id=ctx.get("contact_id"),
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
            "meeting_created": meeting_created,
            "meeting_id": meeting_id,
            "meeting_scheduled_at": meeting_time.isoformat() if meeting_time else None,
            "follow_up_task_id": task_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    def _extract_meeting_time(self, email_body: str) -> datetime:
        """
        Extract meeting time from email body using regex patterns.

        Looks for common date/time patterns in the email.
        Falls back to next business day at 2pm if no time found.

        Args:
            email_body: The email body text to search

        Returns:
            datetime object for the meeting time
        """
        if not email_body:
            return self._get_next_business_day_2pm()

        # Common time patterns to look for
        # Pattern: "Monday at 2pm", "Tuesday at 3:00 PM", etc.
        day_time_pattern = r'(monday|tuesday|wednesday|thursday|friday)\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'

        # Pattern: "12/27 at 2pm", "1/5 at 3:00"
        date_time_pattern = r'(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'

        # Pattern: "January 5th at 2pm", "Dec 27 at 3:00 PM"
        month_date_pattern = r'(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)\s+(\d{1,2})(?:st|nd|rd|th)?\s+(?:at\s+)?(\d{1,2})(?::(\d{2}))?\s*(am|pm)?'

        email_lower = email_body.lower()

        # Try day + time pattern first (e.g., "Monday at 2pm")
        day_match = re.search(day_time_pattern, email_lower, re.IGNORECASE)
        if day_match:
            day_name = day_match.group(1).lower()
            hour = int(day_match.group(2))
            minute = int(day_match.group(3)) if day_match.group(3) else 0
            am_pm = day_match.group(4)

            # Convert to 24-hour format
            if am_pm and am_pm.lower() == 'pm' and hour != 12:
                hour += 12
            elif am_pm and am_pm.lower() == 'am' and hour == 12:
                hour = 0

            # Find the next occurrence of that day
            days_map = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2,
                'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6
            }
            target_day = days_map.get(day_name)
            if target_day is not None:
                today = datetime.utcnow().date()
                days_ahead = target_day - today.weekday()
                if days_ahead <= 0:  # Target day already passed this week
                    days_ahead += 7
                meeting_date = today + timedelta(days=days_ahead)
                return datetime(meeting_date.year, meeting_date.month, meeting_date.day, hour, minute)

        # Try month + date pattern (e.g., "January 5th at 2pm")
        month_match = re.search(month_date_pattern, email_lower, re.IGNORECASE)
        if month_match:
            month_names = {
                'jan': 1, 'january': 1, 'feb': 2, 'february': 2,
                'mar': 3, 'march': 3, 'apr': 4, 'april': 4,
                'may': 5, 'jun': 6, 'june': 6, 'jul': 7, 'july': 7,
                'aug': 8, 'august': 8, 'sep': 9, 'september': 9,
                'oct': 10, 'october': 10, 'nov': 11, 'november': 11,
                'dec': 12, 'december': 12
            }
            month = month_names.get(month_match.group(1).lower())
            day = int(month_match.group(2))
            hour = int(month_match.group(3))
            minute = int(month_match.group(4)) if month_match.group(4) else 0
            am_pm = month_match.group(5)

            if am_pm and am_pm.lower() == 'pm' and hour != 12:
                hour += 12
            elif am_pm and am_pm.lower() == 'am' and hour == 12:
                hour = 0

            year = datetime.utcnow().year
            # If the date is in the past, assume next year
            proposed_date = datetime(year, month, day, hour, minute)
            if proposed_date < datetime.utcnow():
                proposed_date = datetime(year + 1, month, day, hour, minute)
            return proposed_date

        # Try numeric date pattern (e.g., "12/27 at 2pm")
        date_match = re.search(date_time_pattern, email_lower, re.IGNORECASE)
        if date_match:
            month = int(date_match.group(1))
            day = int(date_match.group(2))
            year = int(date_match.group(3)) if date_match.group(3) else datetime.utcnow().year
            if year < 100:  # Two-digit year
                year += 2000
            hour = int(date_match.group(4))
            minute = int(date_match.group(5)) if date_match.group(5) else 0
            am_pm = date_match.group(6)

            if am_pm and am_pm.lower() == 'pm' and hour != 12:
                hour += 12
            elif am_pm and am_pm.lower() == 'am' and hour == 12:
                hour = 0

            return datetime(year, month, day, hour, minute)

        # No time found, use default
        return self._get_next_business_day_2pm()

    def _get_next_business_day_2pm(self) -> datetime:
        """
        Get next business day at 2pm UTC.

        If today is a weekday and before 2pm, return today at 2pm.
        Otherwise, return next business day at 2pm.

        Returns:
            datetime for next business day at 2pm
        """
        now = datetime.utcnow()

        # Start with tomorrow
        next_day = now + timedelta(days=1)

        # Skip weekends
        while next_day.weekday() >= 5:  # 5=Saturday, 6=Sunday
            next_day += timedelta(days=1)

        # Set to 2pm (14:00)
        return datetime(next_day.year, next_day.month, next_day.day, 14, 0)

    async def _handle_question(self, ctx: dict) -> dict:
        """
        Handle question reply - MEDIUM PRIORITY.

        Actions:
        1. Create task "Review reply from [contact]" due tomorrow
        2. Send Slack alert with question context
        3. Pause sequence until answered
        """
        self.logger.info(
            f"❓ QUESTION from {ctx['company_name']}"
        )

        # Create follow-up task due tomorrow
        tomorrow = date.today() + timedelta(days=1)
        task_text = f"Review reply from {ctx['contact_name']} ({ctx['company_name']}) - has questions"
        task_id = await self._create_follow_up_task(
            lead_id=ctx.get("lead_id"),
            task_text=task_text,
            due_date=tomorrow,
            intent=ReplyIntent.QUESTION,
            contact_id=ctx.get("contact_id"),
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
            "task_created": task_id is not None,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _handle_not_interested(self, ctx: dict) -> dict:
        """
        Handle not interested reply - LOW PRIORITY.

        Actions:
        1. Stop all sequences
        2. Create task "6-month nurture check" due 6 months out
        3. Mark for nurture
        """
        self.logger.info(
            f"👎 NOT INTERESTED from {ctx['company_name']}"
        )

        # Create 6-month nurture check task
        nurture_date = date.today() + timedelta(days=180)
        task_text = f"6-month nurture check - {ctx['contact_name']} ({ctx['company_name']}) - was not interested"
        task_id = await self._create_follow_up_task(
            lead_id=ctx.get("lead_id"),
            task_text=task_text,
            due_date=nurture_date,
            intent=ReplyIntent.NOT_INTERESTED,
            contact_id=ctx.get("contact_id"),
        )

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
            "nurture_task_id": task_id,
            "timestamp": datetime.utcnow().isoformat()
        }

    async def _handle_unsubscribe(self, ctx: dict) -> dict:
        """
        Handle unsubscribe request - CRITICAL (COMPLIANCE).

        Actions:
        1. Stop ALL sequences immediately
        2. Add to global suppression list
        3. Update CRM with do-not-contact flag
        4. Create "Compliance review" task due today
        """
        self.logger.warning(
            f"🚫 UNSUBSCRIBE from {ctx['company_name']} - COMPLIANCE ACTION"
        )

        # Create compliance review task due today
        today = date.today()
        task_text = f"Compliance review - UNSUBSCRIBE request from {ctx['contact_name']} ({ctx['company_name']})"
        task_id = await self._create_follow_up_task(
            lead_id=ctx.get("lead_id"),
            task_text=task_text,
            due_date=today,
            intent=ReplyIntent.UNSUBSCRIBE,
            contact_id=ctx.get("contact_id"),
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
            "compliance_task_id": task_id,
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
