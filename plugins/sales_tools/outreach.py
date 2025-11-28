"""OutreachTool - Send sales outreach to leads.

Wraps existing outreach services to send emails, SMS, or other
communication channels to qualified leads.

Usage:
    tool = OutreachTool()
    result = await tool.run({
        "lead_id": "lead-abc",
        "channel": "email",
        "template": "intro",  # optional
    })

Integrates with:
- DeliveryService: Direct SMS/email via Twilio/SendGrid
- ColdReachClient: Email sequence enrollment

Rate Limits (built-in protection):
- Twilio SMS: 1 msg/sec (long codes), enforced with 1.1s delay between sends
- SendGrid: 600 req/min (~10/sec), enforced with 0.15s delay
- Both: Exponential backoff on 429 errors (3 retries max)

Sources:
- https://support.twilio.com/hc/en-us/articles/115002943027
- https://www.twilio.com/docs/sendgrid/api-reference/how-to-use-the-sendgrid-v3-api/rate-limits
"""

import os
import time
import threading
from typing import Optional

from plugins.sales_tools.base import BaseTool, ToolCategory, ToolDefinition, ToolResult

# Import actual services (lazy to avoid import errors when services unavailable)
_delivery_service = None
_cold_reach_client = None

# Rate limiting state (thread-safe)
_rate_limit_lock = threading.Lock()
_last_sms_time: float = 0.0
_last_email_time: float = 0.0

# Rate limit configuration (conservative for MVP safety)
SMS_MIN_INTERVAL = 1.1  # 1.1 seconds between SMS (< 1 MPS for long codes)
EMAIL_MIN_INTERVAL = 0.15  # 0.15 seconds between emails (~6.6/sec, well under 600/min)
MAX_RETRIES = 3
BACKOFF_BASE = 2.0  # Exponential backoff base


def _rate_limit_sms() -> float:
    """Enforce SMS rate limit. Returns wait time in seconds."""
    global _last_sms_time
    with _rate_limit_lock:
        now = time.time()
        elapsed = now - _last_sms_time
        if elapsed < SMS_MIN_INTERVAL:
            wait_time = SMS_MIN_INTERVAL - elapsed
            time.sleep(wait_time)
            _last_sms_time = time.time()
            return wait_time
        _last_sms_time = now
        return 0.0


def _rate_limit_email() -> float:
    """Enforce email rate limit. Returns wait time in seconds."""
    global _last_email_time
    with _rate_limit_lock:
        now = time.time()
        elapsed = now - _last_email_time
        if elapsed < EMAIL_MIN_INTERVAL:
            wait_time = EMAIL_MIN_INTERVAL - elapsed
            time.sleep(wait_time)
            _last_email_time = time.time()
            return wait_time
        _last_email_time = now
        return 0.0


def get_delivery_service():
    """Lazy-load DeliveryService to avoid import errors."""
    global _delivery_service
    if _delivery_service is None:
        try:
            from backend.app.services.outreach.delivery_service import DeliveryService
            _delivery_service = DeliveryService()
        except ImportError:
            pass
    return _delivery_service


def get_cold_reach_client():
    """Lazy-load ColdReachClient to avoid import errors."""
    global _cold_reach_client
    if _cold_reach_client is None:
        try:
            from backend.app.services.cold_reach_client import ColdReachClient
            _cold_reach_client = ColdReachClient()
        except ImportError:
            pass
    return _cold_reach_client


VALID_CHANNELS = ["email", "sms", "linkedin", "sequence"]


class OutreachTool(BaseTool):
    """Send outreach messages to leads.

    Supports multiple channels:
    - email: Send direct email via SendGrid ($0.00025/email)
    - sms: Send SMS via Twilio ($0.0079/segment)
    - linkedin: Queue LinkedIn connection/message (manual)
    - sequence: Enroll in cold-reach email sequence (automated drip)
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="outreach_send",
            description=(
                "Send sales outreach to a lead via email, SMS, LinkedIn, or email sequence. "
                "Email/SMS use SendGrid/Twilio. Sequence enrolls in automated drip campaigns."
            ),
            category=ToolCategory.SALES,
            parameters={
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "string",
                        "description": "Lead ID to send outreach to",
                    },
                    "channel": {
                        "type": "string",
                        "enum": VALID_CHANNELS,
                        "description": "Channel: email (direct), sms, linkedin, sequence (drip)",
                    },
                    "email": {
                        "type": "string",
                        "description": "Recipient email (required for email/sequence)",
                    },
                    "phone": {
                        "type": "string",
                        "description": "Recipient phone (required for sms, format: +1XXXXXXXXXX)",
                    },
                    "company_name": {
                        "type": "string",
                        "description": "Company name for personalization",
                    },
                    "template": {
                        "type": "string",
                        "description": "Template name (e.g., 'intro', 'followup', 'demo_request')",
                    },
                    "sequence_name": {
                        "type": "string",
                        "description": "For sequence channel: 'high_priority_solar', 'standard_solar_intro', 'nurture_sequence'",
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject (for direct email)",
                    },
                    "custom_message": {
                        "type": "string",
                        "description": "Custom message content (overrides template)",
                    },
                    "tier": {
                        "type": "string",
                        "enum": ["A", "B", "C", "D"],
                        "description": "Lead tier for sequence selection (A=hot, B=warm, C=nurture, D=skip)",
                    },
                },
                "required": ["lead_id", "channel"],
            },
            requires_approval=True,  # Outreach needs approval
        )

    def _send_email(
        self,
        to_email: str,
        subject: str,
        body: str,
        lead_id: str,
    ) -> dict:
        """Send direct email via SendGrid with rate limiting.

        Rate limit: 0.15s between emails (~6.6/sec, well under 600/min API limit)
        Retry: 3 attempts with exponential backoff on 429 errors

        Args:
            to_email: Recipient email
            subject: Email subject
            body: Email body (HTML supported)
            lead_id: Lead ID for tracking

        Returns:
            Send result with message_id and status
        """
        delivery = get_delivery_service()
        if delivery is None:
            return {
                "status": "service_unavailable",
                "error": "DeliveryService not available - check imports",
                "fallback": True,
            }

        # Apply rate limiting before API call
        wait_time = _rate_limit_email()

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                result = delivery.send_email(
                    to_email=to_email,
                    subject=subject,
                    body=body,
                )
                # Check for rate limit response (429)
                if result.get("status_code") == 429:
                    backoff = BACKOFF_BASE ** attempt
                    time.sleep(backoff)
                    continue

                return {
                    "message_id": result.get("message_id", f"email-{lead_id[:8]}"),
                    "channel": "email",
                    "status": "sent" if result.get("success") else "failed",
                    "cost_usd": 0.00025,  # SendGrid cost per email
                    "rate_limit_wait_ms": int(wait_time * 1000),
                }
            except Exception as e:
                last_error = str(e)
                if "429" in str(e) or "rate" in str(e).lower():
                    backoff = BACKOFF_BASE ** attempt
                    time.sleep(backoff)
                    continue
                break

        return {
            "status": "failed",
            "error": last_error or "Max retries exceeded",
            "channel": "email",
            "retries": MAX_RETRIES,
        }

    def _send_sms(
        self,
        to_phone: str,
        body: str,
        lead_id: str,
    ) -> dict:
        """Send SMS via Twilio with rate limiting.

        Rate limit: 1.1s between SMS (long codes limited to 1 MPS)
        Retry: 3 attempts with exponential backoff on 429/14107 errors

        Args:
            to_phone: Recipient phone (+1XXXXXXXXXX format)
            body: SMS message (160 chars = 1 segment)
            lead_id: Lead ID for tracking

        Returns:
            Send result with message_id and status
        """
        delivery = get_delivery_service()
        if delivery is None:
            return {
                "status": "service_unavailable",
                "error": "DeliveryService not available - check imports",
                "fallback": True,
            }

        # Apply rate limiting before API call (critical for Twilio long codes)
        wait_time = _rate_limit_sms()

        segments = (len(body) // 160) + 1

        # Retry loop with exponential backoff
        last_error = None
        for attempt in range(MAX_RETRIES):
            try:
                result = delivery.send_sms(
                    to_phone=to_phone,
                    body=body,
                )
                # Check for rate limit (429) or Twilio error 14107
                status_code = result.get("status_code", 200)
                error_code = result.get("error_code")
                if status_code == 429 or error_code == 14107:
                    backoff = BACKOFF_BASE ** attempt
                    time.sleep(backoff)
                    continue

                return {
                    "message_id": result.get("sid", f"sms-{lead_id[:8]}"),
                    "channel": "sms",
                    "status": "sent" if result.get("success") else "failed",
                    "segments": segments,
                    "cost_usd": 0.0079 * segments,  # Twilio cost per segment
                    "rate_limit_wait_ms": int(wait_time * 1000),
                }
            except Exception as e:
                last_error = str(e)
                # Check for rate limit errors in exception
                if "429" in str(e) or "14107" in str(e) or "rate" in str(e).lower():
                    backoff = BACKOFF_BASE ** attempt
                    time.sleep(backoff)
                    continue
                break

        return {
            "status": "failed",
            "error": last_error or "Max retries exceeded",
            "channel": "sms",
            "retries": MAX_RETRIES,
        }

    def _enroll_sequence(
        self,
        email: str,
        company_name: str,
        tier: str,
        lead_id: str,
        sequence_name: Optional[str] = None,
    ) -> dict:
        """Enroll lead in cold-reach email sequence.

        Args:
            email: Lead email
            company_name: Company name for personalization
            tier: Lead tier (A/B/C/D) for sequence selection
            lead_id: Lead ID for tracking
            sequence_name: Override sequence (optional)

        Returns:
            Enrollment result
        """
        cold_reach = get_cold_reach_client()
        if cold_reach is None:
            return {
                "status": "service_unavailable",
                "error": "ColdReachClient not available - check imports",
                "fallback": True,
            }

        # Map tier to sequence if not specified
        tier_sequences = {
            "A": "high_priority_solar",
            "B": "standard_solar_intro",
            "C": "nurture_sequence",
            "D": None,  # Skip tier D
        }

        final_sequence = sequence_name or tier_sequences.get(tier, "standard_solar_intro")

        if final_sequence is None:
            return {
                "status": "skipped",
                "reason": f"Tier {tier} leads are not enrolled in sequences",
                "channel": "sequence",
            }

        result = cold_reach.enroll_lead(
            email=email,
            company_name=company_name,
            sequence_name=final_sequence,
            lead_id=lead_id,
        )
        return {
            "enrollment_id": result.get("id", f"seq-{lead_id[:8]}"),
            "channel": "sequence",
            "sequence_name": final_sequence,
            "status": "enrolled" if result.get("success") else "failed",
        }

    def _queue_linkedin(self, lead_id: str, company_name: str, message: str) -> dict:
        """Queue LinkedIn outreach (manual action required).

        LinkedIn automation requires manual approval due to TOS.
        This queues the action for human review.

        Args:
            lead_id: Lead ID
            company_name: Company for personalization
            message: Connection request message

        Returns:
            Queue result
        """
        # LinkedIn requires manual action - just queue it
        return {
            "queue_id": f"li-{lead_id[:8]}",
            "channel": "linkedin",
            "status": "queued",
            "action_required": "manual",
            "message_preview": message[:100] if message else None,
            "note": "LinkedIn outreach queued for manual execution",
        }

    async def run(self, arguments: dict) -> ToolResult:
        """Execute outreach send.

        Args:
            arguments: Must contain 'lead_id' and 'channel'

        Returns:
            ToolResult with outreach status
        """
        start_time = time.time()

        lead_id = arguments.get("lead_id", "")
        channel = arguments.get("channel", "")
        email = arguments.get("email")
        phone = arguments.get("phone")
        company_name = arguments.get("company_name", "")
        template = arguments.get("template")
        sequence_name = arguments.get("sequence_name")
        subject = arguments.get("subject", "Quick question")
        custom_message = arguments.get("custom_message")
        tier = arguments.get("tier", "B")

        try:
            # Validate channel
            if channel not in VALID_CHANNELS:
                return ToolResult(
                    tool_name="outreach_send",
                    success=False,
                    result=None,
                    execution_time_ms=0,
                    error=f"Invalid channel: {channel}. Use: {', '.join(VALID_CHANNELS)}",
                )

            # Route to appropriate service
            if channel == "email":
                if not email:
                    return ToolResult(
                        tool_name="outreach_send",
                        success=False,
                        result=None,
                        execution_time_ms=0,
                        error="Email required for email channel",
                    )
                body = custom_message or f"Hi {company_name} team, {template or 'intro'} template content here."
                result = self._send_email(email, subject, body, lead_id)

            elif channel == "sms":
                if not phone:
                    return ToolResult(
                        tool_name="outreach_send",
                        success=False,
                        result=None,
                        execution_time_ms=0,
                        error="Phone required for sms channel (format: +1XXXXXXXXXX)",
                    )
                body = custom_message or f"Hi from {company_name or 'us'}! Quick follow up on our services."
                result = self._send_sms(phone, body, lead_id)

            elif channel == "sequence":
                if not email:
                    return ToolResult(
                        tool_name="outreach_send",
                        success=False,
                        result=None,
                        execution_time_ms=0,
                        error="Email required for sequence enrollment",
                    )
                result = self._enroll_sequence(email, company_name, tier, lead_id, sequence_name)

            elif channel == "linkedin":
                message = custom_message or f"Hi! I'd love to connect regarding {company_name or 'your company'}."
                result = self._queue_linkedin(lead_id, company_name, message)

            else:
                result = {"error": f"Unknown channel: {channel}"}

            execution_time = int((time.time() - start_time) * 1000)

            return ToolResult(
                tool_name="outreach_send",
                success=result.get("status") not in ["failed", "service_unavailable"],
                result=result,
                execution_time_ms=execution_time,
            )

        except Exception as e:
            execution_time = int((time.time() - start_time) * 1000)
            return ToolResult(
                tool_name="outreach_send",
                success=False,
                result=None,
                execution_time_ms=execution_time,
                error=f"Outreach failed: {str(e)}",
            )
