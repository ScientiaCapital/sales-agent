"""
Delivery Service - Sends messages via Twilio SMS and SendGrid Email

This service handles the actual delivery of generated marketing content
to leads via SMS and email channels.

Usage:
    from app.services.outreach.delivery_service import DeliveryService

    service = DeliveryService()

    # Send SMS
    result = await service.send_sms(
        to_phone="+1234567890",
        message="Hello from Sales Agent!"
    )

    # Send Email
    result = await service.send_email(
        to_email="lead@company.com",
        subject="Solar solutions for your business",
        body_html="<p>Hello...</p>"
    )
"""

import os
from typing import Optional, Dict, Any, List
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class DeliveryChannel(str, Enum):
    SMS = "sms"
    EMAIL = "email"
    LINKEDIN = "linkedin"  # For future implementation


class DeliveryStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"  # Dry run or disabled
    INVALID = "invalid"  # Invalid recipient


@dataclass
class DeliveryResult:
    """Result of a delivery attempt"""
    channel: DeliveryChannel
    status: DeliveryStatus
    recipient: str
    message_id: Optional[str] = None
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    cost_usd: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "channel": self.channel.value,
            "status": self.status.value,
            "recipient": self.recipient,
            "message_id": self.message_id,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "cost_usd": self.cost_usd
        }


class DeliveryService:
    """
    Multi-channel delivery service for SMS and Email.

    Supports:
    - Twilio SMS (requires TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER)
    - SendGrid Email (requires SENDGRID_API_KEY, SENDGRID_FROM_EMAIL)
    - Dry-run mode for testing without sending

    Costs:
    - Twilio SMS: ~$0.0079/segment (160 chars)
    - SendGrid Email: Free tier up to 100/day, then ~$0.00025/email
    """

    # Cost estimates per message
    SMS_COST_PER_SEGMENT = 0.0079  # Twilio US SMS
    EMAIL_COST_PER_MESSAGE = 0.00025  # SendGrid

    def __init__(self, dry_run: bool = False):
        """
        Initialize delivery service.

        Args:
            dry_run: If True, logs messages but doesn't send
        """
        self.dry_run = dry_run

        # Twilio config
        self.twilio_sid = os.getenv("TWILIO_ACCOUNT_SID")
        self.twilio_token = os.getenv("TWILIO_AUTH_TOKEN")
        self.twilio_phone = os.getenv("TWILIO_PHONE_NUMBER")
        self.twilio_enabled = all([self.twilio_sid, self.twilio_token, self.twilio_phone])

        # SendGrid config
        self.sendgrid_key = os.getenv("SENDGRID_API_KEY")
        self.sendgrid_from = os.getenv("SENDGRID_FROM_EMAIL", "noreply@coperniq.io")
        self.sendgrid_from_name = os.getenv("SENDGRID_FROM_NAME", "Coperniq Solar")
        self.sendgrid_enabled = bool(self.sendgrid_key)

        # Lazy load clients
        self._twilio_client = None
        self._sendgrid_client = None

        logger.info(
            f"DeliveryService initialized: "
            f"twilio={'enabled' if self.twilio_enabled else 'disabled'}, "
            f"sendgrid={'enabled' if self.sendgrid_enabled else 'disabled'}, "
            f"dry_run={dry_run}"
        )

    @property
    def twilio_client(self):
        """Lazy-load Twilio client"""
        if self._twilio_client is None and self.twilio_enabled:
            from twilio.rest import Client
            self._twilio_client = Client(self.twilio_sid, self.twilio_token)
        return self._twilio_client

    @property
    def sendgrid_client(self):
        """Lazy-load SendGrid client"""
        if self._sendgrid_client is None and self.sendgrid_enabled:
            from sendgrid import SendGridAPIClient
            self._sendgrid_client = SendGridAPIClient(self.sendgrid_key)
        return self._sendgrid_client

    def _validate_phone(self, phone: str) -> Optional[str]:
        """
        Validate and normalize phone number.

        Args:
            phone: Phone number to validate

        Returns:
            Normalized phone (E.164 format) or None if invalid
        """
        if not phone:
            return None

        # Remove common formatting
        cleaned = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")

        # Ensure starts with +
        if not cleaned.startswith("+"):
            # Assume US number
            if len(cleaned) == 10:
                cleaned = "+1" + cleaned
            elif len(cleaned) == 11 and cleaned.startswith("1"):
                cleaned = "+" + cleaned
            else:
                return None

        # Basic validation
        if len(cleaned) < 10 or len(cleaned) > 15:
            return None

        return cleaned

    def _validate_email(self, email: str) -> Optional[str]:
        """
        Validate email address.

        Args:
            email: Email to validate

        Returns:
            Normalized email or None if invalid
        """
        if not email:
            return None

        email = email.strip().lower()

        # Basic validation
        if "@" not in email or "." not in email.split("@")[-1]:
            return None

        return email

    async def send_sms(
        self,
        to_phone: str,
        message: str,
        contact_name: Optional[str] = None
    ) -> DeliveryResult:
        """
        Send SMS via Twilio.

        Args:
            to_phone: Recipient phone number
            message: SMS message content (max 1600 chars)
            contact_name: Optional contact name for logging

        Returns:
            DeliveryResult with status and message_id
        """
        # Validate phone
        phone = self._validate_phone(to_phone)
        if not phone:
            logger.warning(f"Invalid phone number: {to_phone}")
            return DeliveryResult(
                channel=DeliveryChannel.SMS,
                status=DeliveryStatus.INVALID,
                recipient=to_phone,
                error="Invalid phone number format"
            )

        # Calculate cost (SMS segments)
        segments = (len(message) + 159) // 160
        estimated_cost = segments * self.SMS_COST_PER_SEGMENT

        # Dry run mode
        if self.dry_run:
            logger.info(
                f"[DRY RUN] SMS to {phone}: {message[:50]}... "
                f"(segments={segments}, cost=${estimated_cost:.4f})"
            )
            return DeliveryResult(
                channel=DeliveryChannel.SMS,
                status=DeliveryStatus.SKIPPED,
                recipient=phone,
                message_id="dry_run",
                cost_usd=0.0
            )

        # Check if Twilio enabled
        if not self.twilio_enabled:
            logger.warning("Twilio not configured - SMS skipped")
            return DeliveryResult(
                channel=DeliveryChannel.SMS,
                status=DeliveryStatus.SKIPPED,
                recipient=phone,
                error="Twilio not configured"
            )

        try:
            # Send via Twilio
            twilio_message = self.twilio_client.messages.create(
                body=message,
                from_=self.twilio_phone,
                to=phone
            )

            logger.info(
                f"SMS sent to {phone} ({contact_name or 'unknown'}): "
                f"sid={twilio_message.sid}, segments={segments}, cost=${estimated_cost:.4f}"
            )

            return DeliveryResult(
                channel=DeliveryChannel.SMS,
                status=DeliveryStatus.SUCCESS,
                recipient=phone,
                message_id=twilio_message.sid,
                cost_usd=estimated_cost
            )

        except Exception as e:
            logger.error(f"SMS delivery failed to {phone}: {e}")
            return DeliveryResult(
                channel=DeliveryChannel.SMS,
                status=DeliveryStatus.FAILED,
                recipient=phone,
                error=str(e)
            )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        contact_name: Optional[str] = None,
        reply_to: Optional[str] = None
    ) -> DeliveryResult:
        """
        Send email via SendGrid.

        Args:
            to_email: Recipient email address
            subject: Email subject line
            body_html: HTML email body
            body_text: Plain text body (auto-generated if not provided)
            contact_name: Optional recipient name
            reply_to: Optional reply-to address

        Returns:
            DeliveryResult with status and message_id
        """
        # Validate email
        email = self._validate_email(to_email)
        if not email:
            logger.warning(f"Invalid email address: {to_email}")
            return DeliveryResult(
                channel=DeliveryChannel.EMAIL,
                status=DeliveryStatus.INVALID,
                recipient=to_email,
                error="Invalid email address format"
            )

        # Generate plain text from HTML if not provided
        if not body_text:
            import re
            body_text = re.sub(r'<[^>]+>', '', body_html)

        # Dry run mode
        if self.dry_run:
            logger.info(
                f"[DRY RUN] Email to {email} ({contact_name or 'unknown'}): "
                f"subject='{subject[:50]}...'"
            )
            return DeliveryResult(
                channel=DeliveryChannel.EMAIL,
                status=DeliveryStatus.SKIPPED,
                recipient=email,
                message_id="dry_run",
                cost_usd=0.0
            )

        # Check if SendGrid enabled
        if not self.sendgrid_enabled:
            logger.warning("SendGrid not configured - email skipped")
            return DeliveryResult(
                channel=DeliveryChannel.EMAIL,
                status=DeliveryStatus.SKIPPED,
                recipient=email,
                error="SendGrid not configured"
            )

        try:
            from sendgrid.helpers.mail import (
                Mail, Email, To, Content, Personalization
            )

            # Build email
            message = Mail()
            message.from_email = Email(self.sendgrid_from, self.sendgrid_from_name)

            # Add recipient
            personalization = Personalization()
            to_obj = To(email, contact_name) if contact_name else To(email)
            personalization.add_to(to_obj)
            message.add_personalization(personalization)

            # Set subject and content
            message.subject = subject
            message.add_content(Content("text/plain", body_text))
            message.add_content(Content("text/html", body_html))

            # Optional reply-to
            if reply_to:
                message.reply_to = Email(reply_to)

            # Send via SendGrid
            response = self.sendgrid_client.send(message)

            # Get message ID from headers
            message_id = response.headers.get("X-Message-Id", "unknown")

            logger.info(
                f"Email sent to {email} ({contact_name or 'unknown'}): "
                f"status={response.status_code}, id={message_id}"
            )

            return DeliveryResult(
                channel=DeliveryChannel.EMAIL,
                status=DeliveryStatus.SUCCESS,
                recipient=email,
                message_id=message_id,
                cost_usd=self.EMAIL_COST_PER_MESSAGE
            )

        except Exception as e:
            logger.error(f"Email delivery failed to {email}: {e}")
            return DeliveryResult(
                channel=DeliveryChannel.EMAIL,
                status=DeliveryStatus.FAILED,
                recipient=email,
                error=str(e)
            )

    async def deliver_marketing_content(
        self,
        contact: Dict[str, Any],
        marketing_content: Dict[str, Any]
    ) -> Dict[str, DeliveryResult]:
        """
        Deliver generated marketing content to a contact via all available channels.

        Args:
            contact: Contact dict with email, phone, first_name, last_name
            marketing_content: Dict with email_content, sms_content from MarketingAgent

        Returns:
            Dict mapping channel to DeliveryResult
        """
        results = {}

        contact_name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()

        # Send email if content and email available
        if marketing_content.get("email_content") and contact.get("email"):
            email_content = marketing_content["email_content"]
            results["email"] = await self.send_email(
                to_email=contact["email"],
                subject=email_content.get("subject", "Opportunity for your business"),
                body_html=email_content.get("body", email_content.get("html", "")),
                contact_name=contact_name
            )

        # Send SMS if content and phone available
        if marketing_content.get("sms_content") and contact.get("phone"):
            sms_content = marketing_content["sms_content"]
            sms_body = sms_content.get("body", sms_content) if isinstance(sms_content, dict) else str(sms_content)
            results["sms"] = await self.send_sms(
                to_phone=contact["phone"],
                message=sms_body[:1600],  # Twilio limit
                contact_name=contact_name
            )

        return results

    async def deliver_batch(
        self,
        contacts: List[Dict[str, Any]],
        marketing_content: Dict[str, Any],
        delay_seconds: float = 1.0
    ) -> List[Dict[str, Any]]:
        """
        Deliver marketing content to a batch of contacts.

        Args:
            contacts: List of contact dicts
            marketing_content: Marketing content from MarketingAgent
            delay_seconds: Delay between sends to avoid rate limits

        Returns:
            List of delivery results per contact
        """
        import asyncio

        results = []

        for i, contact in enumerate(contacts):
            contact_results = await self.deliver_marketing_content(contact, marketing_content)

            results.append({
                "contact": contact,
                "delivery": {k: v.to_dict() for k, v in contact_results.items()}
            })

            # Delay between contacts (except last)
            if i < len(contacts) - 1 and delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

        # Summary
        email_success = sum(1 for r in results if r.get("delivery", {}).get("email", {}).get("status") == "success")
        sms_success = sum(1 for r in results if r.get("delivery", {}).get("sms", {}).get("status") == "success")

        logger.info(
            f"Batch delivery complete: {len(contacts)} contacts, "
            f"{email_success} emails sent, {sms_success} SMS sent"
        )

        return results


# Exports
__all__ = ["DeliveryService", "DeliveryResult", "DeliveryChannel", "DeliveryStatus"]
