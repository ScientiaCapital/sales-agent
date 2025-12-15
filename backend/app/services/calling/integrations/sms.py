"""
SMS Sender using Twilio for AI Calling System.

Send SMS during calls when lead asks for:
- Video link
- More info
- Calendly link
- Follow-up materials

Uses the same Twilio account as voice calls.
"""
import logging
import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

try:
    from twilio.rest import Client as TwilioClient
    TWILIO_AVAILABLE = True
except ImportError:
    TwilioClient = None
    TWILIO_AVAILABLE = False


class SMSTemplate(str, Enum):
    """Pre-built SMS templates for common scenarios."""
    VIDEO_LINK = "video_link"
    CALENDLY_LINK = "calendly_link"
    FOLLOW_UP = "follow_up"
    THANK_YOU = "thank_you"


@dataclass
class SMSMessage:
    """SMS message configuration."""
    to_number: str
    body: str
    from_number: Optional[str] = None
    # Result fields
    sid: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None


# Pre-built message templates
SMS_TEMPLATES = {
    SMSTemplate.VIDEO_LINK: """Hey {name}! Here's that 2-minute Coperniq video I mentioned: {video_url}

No pressure - just wanted to make sure you had it. - Tim""",

    SMSTemplate.CALENDLY_LINK: """Hey {name}! Here's my calendar to grab that 15 minutes: {calendly_url}

Pick whatever works for you. - Tim""",

    SMSTemplate.FOLLOW_UP: """Hey {name}! Tim from Coperniq here. Great chatting - here's that info I promised: {info_url}

Let me know if you have any questions! - Tim""",

    SMSTemplate.THANK_YOU: """Hey {name}! Thanks for your time today. If anything changes or you want to revisit, you've got my number. - Tim (Coperniq)""",
}


class SMSSender:
    """
    Send SMS messages via Twilio during calls.

    Usage:
        sender = SMSSender(
            account_sid="your_sid",
            auth_token="your_token",
            from_number="+14154309465"
        )

        # Send video link during call
        result = await sender.send_video_link(
            to_number="+15551234567",
            lead_name="John",
            video_url="https://..."
        )

        # Send Calendly link
        result = await sender.send_calendly_link(
            to_number="+15551234567",
            lead_name="John"
        )
    """

    # Default URLs
    DEFAULT_VIDEO_URL = "https://www.loom.com/share/coperniq-demo"  # Replace with actual
    DEFAULT_CALENDLY_URL = "https://calendly.com/coperniq-sales/disco"

    def __init__(
        self,
        account_sid: Optional[str] = None,
        auth_token: Optional[str] = None,
        from_number: Optional[str] = None,
    ):
        self.account_sid = account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.from_number = from_number or os.getenv("TWILIO_FROM_NUMBER", "+14154309465")

        self.available = TWILIO_AVAILABLE and self.account_sid and self.auth_token

        if self.available:
            self.client = TwilioClient(self.account_sid, self.auth_token)
            logger.info("SMSSender initialized with Twilio")
        else:
            self.client = None
            if not TWILIO_AVAILABLE:
                logger.warning("Twilio SDK not installed: pip install twilio")
            else:
                logger.warning("Twilio credentials not configured")

    async def send(self, message: SMSMessage) -> SMSMessage:
        """
        Send an SMS message.

        Args:
            message: SMSMessage with to_number and body

        Returns:
            SMSMessage with status and sid populated
        """
        if not self.available:
            message.error = "Twilio not available"
            message.status = "failed"
            logger.error("Cannot send SMS: Twilio not configured")
            return message

        try:
            # Twilio client is sync, but we wrap for async interface
            result = self.client.messages.create(
                body=message.body,
                from_=message.from_number or self.from_number,
                to=message.to_number,
            )

            message.sid = result.sid
            message.status = result.status
            logger.info(f"SMS sent to {message.to_number}: {result.sid}")

        except Exception as e:
            message.error = str(e)
            message.status = "failed"
            logger.error(f"Failed to send SMS to {message.to_number}: {e}")

        return message

    async def send_video_link(
        self,
        to_number: str,
        lead_name: str,
        video_url: Optional[str] = None,
    ) -> SMSMessage:
        """
        Send video link SMS during call.

        Args:
            to_number: Phone number to send to
            lead_name: Lead's first name for personalization
            video_url: URL to the video (uses default if not provided)

        Returns:
            SMSMessage with send status
        """
        url = video_url or self.DEFAULT_VIDEO_URL
        body = SMS_TEMPLATES[SMSTemplate.VIDEO_LINK].format(
            name=lead_name,
            video_url=url,
        )

        message = SMSMessage(to_number=to_number, body=body)
        return await self.send(message)

    async def send_calendly_link(
        self,
        to_number: str,
        lead_name: str,
        calendly_url: Optional[str] = None,
        lead_email: Optional[str] = None,
    ) -> SMSMessage:
        """
        Send Calendly booking link via SMS.

        Args:
            to_number: Phone number to send to
            lead_name: Lead's first name
            calendly_url: Custom Calendly URL (uses default if not provided)
            lead_email: Optional email to pre-fill

        Returns:
            SMSMessage with send status
        """
        url = calendly_url or self.DEFAULT_CALENDLY_URL

        # Add pre-fill params if we have email
        if lead_email:
            url += f"?email={lead_email}&name={lead_name.replace(' ', '%20')}"
        elif lead_name:
            url += f"?name={lead_name.replace(' ', '%20')}"

        body = SMS_TEMPLATES[SMSTemplate.CALENDLY_LINK].format(
            name=lead_name,
            calendly_url=url,
        )

        message = SMSMessage(to_number=to_number, body=body)
        return await self.send(message)

    async def send_follow_up(
        self,
        to_number: str,
        lead_name: str,
        info_url: str,
    ) -> SMSMessage:
        """
        Send follow-up info via SMS.

        Args:
            to_number: Phone number
            lead_name: Lead's first name
            info_url: URL to relevant info/resources

        Returns:
            SMSMessage with send status
        """
        body = SMS_TEMPLATES[SMSTemplate.FOLLOW_UP].format(
            name=lead_name,
            info_url=info_url,
        )

        message = SMSMessage(to_number=to_number, body=body)
        return await self.send(message)

    async def send_thank_you(
        self,
        to_number: str,
        lead_name: str,
    ) -> SMSMessage:
        """
        Send thank you SMS after call ends.

        Args:
            to_number: Phone number
            lead_name: Lead's first name

        Returns:
            SMSMessage with send status
        """
        body = SMS_TEMPLATES[SMSTemplate.THANK_YOU].format(name=lead_name)

        message = SMSMessage(to_number=to_number, body=body)
        return await self.send(message)

    async def send_custom(
        self,
        to_number: str,
        body: str,
    ) -> SMSMessage:
        """
        Send a custom SMS message.

        Args:
            to_number: Phone number
            body: Message body

        Returns:
            SMSMessage with send status
        """
        message = SMSMessage(to_number=to_number, body=body)
        return await self.send(message)


# Helper for quick sends
async def send_video_sms(
    to_number: str,
    lead_name: str,
    video_url: Optional[str] = None,
) -> SMSMessage:
    """Quick helper to send video link SMS."""
    sender = SMSSender()
    return await sender.send_video_link(to_number, lead_name, video_url)


async def send_calendly_sms(
    to_number: str,
    lead_name: str,
) -> SMSMessage:
    """Quick helper to send Calendly link SMS."""
    sender = SMSSender()
    return await sender.send_calendly_link(to_number, lead_name)
