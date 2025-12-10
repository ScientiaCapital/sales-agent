"""SMS Follow-up Handler for voice calls.

Manages SMS follow-ups after calls, missed call notifications,
and human escalation alerts. Integrates with Close CRM SMS client.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class CallOutcome(str, Enum):
    """Possible call outcomes for SMS follow-up logic."""
    ANSWERED = "answered"
    VOICEMAIL = "voicemail"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    FAILED = "failed"
    MEETING_SCHEDULED = "meeting_scheduled"
    TRANSFERRED = "transferred"
    QUALIFIED = "qualified"


class SMSTemplate(str, Enum):
    """SMS template types."""
    POST_CALL_THANKYOU = "post_call_thankyou"
    POST_CALL_MEETING = "post_call_meeting"
    MISSED_CALL = "missed_call"
    VOICEMAIL_FOLLOWUP = "voicemail_followup"
    ESCALATION_ALERT = "escalation_alert"
    CALLBACK_REQUEST = "callback_request"


@dataclass
class SMSFollowupResult:
    """Result of an SMS follow-up operation."""
    success: bool
    sms_id: Optional[str] = None
    phone: Optional[str] = None
    lead_id: Optional[str] = None
    template: Optional[SMSTemplate] = None
    message: Optional[str] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None


# SMS Templates - TTS-friendly, concise messages
SMS_TEMPLATES: Dict[SMSTemplate, str] = {
    SMSTemplate.POST_CALL_THANKYOU: (
        "Hi {name}, thanks for chatting with us today! "
        "If you have any questions, feel free to reply to this message. "
        "- {company}"
    ),
    SMSTemplate.POST_CALL_MEETING: (
        "Hi {name}, your demo is confirmed for {meeting_time}. "
        "You'll receive a calendar invite shortly. "
        "Looking forward to it! - {company}"
    ),
    SMSTemplate.MISSED_CALL: (
        "Hi {name}, we tried to reach you but couldn't connect. "
        "Would you like to schedule a quick call? "
        "Reply with a good time or call us back. - {company}"
    ),
    SMSTemplate.VOICEMAIL_FOLLOWUP: (
        "Hi {name}, just left you a voicemail about {topic}. "
        "Feel free to reply here or call us back when convenient. "
        "- {company}"
    ),
    SMSTemplate.ESCALATION_ALERT: (
        "[PRIORITY] Lead {name} from {lead_company} needs attention. "
        "Reason: {reason}. Call: {phone}"
    ),
    SMSTemplate.CALLBACK_REQUEST: (
        "Hi {name}, we received your callback request. "
        "A team member will reach out within {timeframe}. "
        "- {company}"
    ),
}


class SMSFollowupHandler:
    """Handler for SMS follow-ups after voice calls.

    Integrates with Close CRM SMS client to send contextual
    follow-up messages based on call outcomes.

    Features:
    - Post-call thank you messages
    - Meeting confirmation SMS
    - Missed call notifications
    - Voicemail follow-ups
    - Human escalation alerts
    - Template-based messaging

    Example:
        >>> handler = SMSFollowupHandler(close_sms_client)
        >>> result = await handler.send_post_call_sms(
        ...     lead_id="lead_123",
        ...     call_outcome=CallOutcome.ANSWERED
        ... )
    """

    def __init__(
        self,
        close_sms_client: Optional[Any] = None,
        company_name: Optional[str] = None,
        escalation_phone: Optional[str] = None
    ):
        """Initialize SMS follow-up handler.

        Args:
            close_sms_client: CloseSMSClient instance for sending SMS
            company_name: Company name for templates (or from env)
            escalation_phone: Phone number for escalation alerts
        """
        self.sms_client = close_sms_client
        self.company_name = company_name or os.getenv("COMPANY_NAME", "Our Team")
        self.escalation_phone = escalation_phone or os.getenv("ESCALATION_PHONE")

        logger.info("SMSFollowupHandler initialized")

    def _render_template(
        self,
        template: SMSTemplate,
        context: Dict[str, Any]
    ) -> str:
        """Render SMS template with context values.

        Args:
            template: Template type
            context: Values to substitute

        Returns:
            Rendered message string
        """
        template_str = SMS_TEMPLATES.get(template, "")

        # Add company name to context
        context.setdefault("company", self.company_name)

        # Safe substitution (missing keys stay as placeholders)
        try:
            return template_str.format(**context)
        except KeyError as e:
            logger.warning(f"Missing template variable: {e}")
            # Fallback: replace missing with empty
            for key in ["name", "meeting_time", "topic", "lead_company",
                       "reason", "phone", "timeframe", "company"]:
                if f"{{{key}}}" in template_str and key not in context:
                    context[key] = ""
            return template_str.format(**context)

    async def send_post_call_sms(
        self,
        lead_id: str,
        call_outcome: CallOutcome,
        phone: Optional[str] = None,
        contact_name: Optional[str] = None,
        meeting_time: Optional[str] = None,
        additional_context: Optional[Dict[str, Any]] = None
    ) -> SMSFollowupResult:
        """Send follow-up SMS after a call based on outcome.

        Automatically selects appropriate template based on call outcome
        and sends via Close CRM.

        Args:
            lead_id: Close CRM lead ID
            call_outcome: How the call ended
            phone: Phone number (if not in CRM)
            contact_name: Contact name for personalization
            meeting_time: Meeting time if scheduled
            additional_context: Extra template variables

        Returns:
            SMSFollowupResult with send status
        """
        if not self.sms_client:
            return SMSFollowupResult(
                success=False,
                error="SMS client not configured",
                timestamp=datetime.utcnow()
            )

        # Select template based on outcome
        if call_outcome == CallOutcome.MEETING_SCHEDULED and meeting_time:
            template = SMSTemplate.POST_CALL_MEETING
        elif call_outcome in [CallOutcome.ANSWERED, CallOutcome.QUALIFIED, CallOutcome.TRANSFERRED]:
            template = SMSTemplate.POST_CALL_THANKYOU
        elif call_outcome == CallOutcome.VOICEMAIL:
            template = SMSTemplate.VOICEMAIL_FOLLOWUP
        elif call_outcome in [CallOutcome.NO_ANSWER, CallOutcome.BUSY]:
            template = SMSTemplate.MISSED_CALL
        else:
            # Don't send SMS for failed calls
            logger.info(f"No SMS sent for outcome: {call_outcome}")
            return SMSFollowupResult(
                success=True,
                lead_id=lead_id,
                template=None,
                message="No SMS required for this outcome",
                timestamp=datetime.utcnow()
            )

        # Build context
        context = {
            "name": contact_name or "there",
            "meeting_time": meeting_time or "",
            "topic": additional_context.get("topic", "our conversation") if additional_context else "our conversation",
            **(additional_context or {})
        }

        # Render message
        message = self._render_template(template, context)

        try:
            # Send via Close CRM
            result = await self.sms_client.send_sms(
                phone=phone or "",  # Close will look up from lead_id
                message=message,
                lead_id=lead_id
            )

            logger.info(f"Post-call SMS sent to lead {lead_id}: {template.value}")

            return SMSFollowupResult(
                success=True,
                sms_id=result.get("id"),
                phone=result.get("phone"),
                lead_id=lead_id,
                template=template,
                message=message,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Failed to send post-call SMS: {e}")
            return SMSFollowupResult(
                success=False,
                lead_id=lead_id,
                template=template,
                error=str(e),
                timestamp=datetime.utcnow()
            )

    async def send_missed_call_sms(
        self,
        lead_id: str,
        phone: Optional[str] = None,
        contact_name: Optional[str] = None
    ) -> SMSFollowupResult:
        """Send SMS when call goes unanswered.

        Args:
            lead_id: Close CRM lead ID
            phone: Phone number
            contact_name: Contact name for personalization

        Returns:
            SMSFollowupResult with send status
        """
        return await self.send_post_call_sms(
            lead_id=lead_id,
            call_outcome=CallOutcome.NO_ANSWER,
            phone=phone,
            contact_name=contact_name
        )

    async def send_voicemail_followup_sms(
        self,
        lead_id: str,
        phone: Optional[str] = None,
        contact_name: Optional[str] = None,
        topic: str = "your inquiry"
    ) -> SMSFollowupResult:
        """Send SMS after leaving a voicemail.

        Args:
            lead_id: Close CRM lead ID
            phone: Phone number
            contact_name: Contact name
            topic: Topic of the voicemail

        Returns:
            SMSFollowupResult with send status
        """
        return await self.send_post_call_sms(
            lead_id=lead_id,
            call_outcome=CallOutcome.VOICEMAIL,
            phone=phone,
            contact_name=contact_name,
            additional_context={"topic": topic}
        )

    async def escalate_to_human(
        self,
        lead_id: str,
        reason: str,
        lead_name: Optional[str] = None,
        lead_company: Optional[str] = None,
        lead_phone: Optional[str] = None,
        priority: str = "normal"
    ) -> SMSFollowupResult:
        """Notify human rep via SMS for manual follow-up.

        Sends an escalation alert to the configured escalation phone
        when AI determines human intervention is needed.

        Args:
            lead_id: Close CRM lead ID
            reason: Why escalation is needed
            lead_name: Lead's name
            lead_company: Lead's company
            lead_phone: Lead's phone number
            priority: Priority level (normal, high, urgent)

        Returns:
            SMSFollowupResult with send status
        """
        if not self.escalation_phone:
            logger.warning("Escalation phone not configured")
            return SMSFollowupResult(
                success=False,
                error="Escalation phone not configured",
                timestamp=datetime.utcnow()
            )

        if not self.sms_client:
            return SMSFollowupResult(
                success=False,
                error="SMS client not configured",
                timestamp=datetime.utcnow()
            )

        # Build escalation message
        context = {
            "name": lead_name or "Unknown",
            "lead_company": lead_company or "Unknown Company",
            "reason": reason,
            "phone": lead_phone or "N/A"
        }

        # Add priority prefix for urgent cases
        if priority == "urgent":
            context["name"] = f"[URGENT] {context['name']}"

        message = self._render_template(SMSTemplate.ESCALATION_ALERT, context)

        try:
            # Send to escalation phone (not to lead)
            result = await self.sms_client.send_sms(
                phone=self.escalation_phone,
                message=message,
                lead_id=lead_id  # Track which lead this is for
            )

            logger.info(f"Escalation SMS sent for lead {lead_id}: {reason}")

            return SMSFollowupResult(
                success=True,
                sms_id=result.get("id"),
                phone=self.escalation_phone,
                lead_id=lead_id,
                template=SMSTemplate.ESCALATION_ALERT,
                message=message,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Failed to send escalation SMS: {e}")
            return SMSFollowupResult(
                success=False,
                lead_id=lead_id,
                template=SMSTemplate.ESCALATION_ALERT,
                error=str(e),
                timestamp=datetime.utcnow()
            )

    async def send_callback_confirmation(
        self,
        lead_id: str,
        phone: str,
        contact_name: Optional[str] = None,
        callback_timeframe: str = "24 hours"
    ) -> SMSFollowupResult:
        """Confirm callback request to lead.

        Args:
            lead_id: Close CRM lead ID
            phone: Lead's phone number
            contact_name: Lead's name
            callback_timeframe: Expected callback timeframe

        Returns:
            SMSFollowupResult with send status
        """
        if not self.sms_client:
            return SMSFollowupResult(
                success=False,
                error="SMS client not configured",
                timestamp=datetime.utcnow()
            )

        context = {
            "name": contact_name or "there",
            "timeframe": callback_timeframe
        }

        message = self._render_template(SMSTemplate.CALLBACK_REQUEST, context)

        try:
            result = await self.sms_client.send_sms(
                phone=phone,
                message=message,
                lead_id=lead_id
            )

            logger.info(f"Callback confirmation sent to lead {lead_id}")

            return SMSFollowupResult(
                success=True,
                sms_id=result.get("id"),
                phone=phone,
                lead_id=lead_id,
                template=SMSTemplate.CALLBACK_REQUEST,
                message=message,
                timestamp=datetime.utcnow()
            )

        except Exception as e:
            logger.error(f"Failed to send callback confirmation: {e}")
            return SMSFollowupResult(
                success=False,
                lead_id=lead_id,
                error=str(e),
                timestamp=datetime.utcnow()
            )

    def get_available_templates(self) -> Dict[str, str]:
        """Get all available SMS templates.

        Returns:
            Dict mapping template names to template strings
        """
        return {t.value: SMS_TEMPLATES[t] for t in SMSTemplate}

    async def preview_message(
        self,
        template: SMSTemplate,
        context: Dict[str, Any]
    ) -> str:
        """Preview a rendered SMS message without sending.

        Args:
            template: Template type
            context: Values to substitute

        Returns:
            Rendered message string
        """
        return self._render_template(template, context)
