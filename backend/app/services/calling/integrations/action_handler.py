"""
Action Handler for AI Calling System.

Executes actions triggered by agents during calls:
- Send SMS with video/Calendly link
- Send email follow-up
- Book Calendly meeting
- Update CRM (Close)

This is the glue between agent decisions and real-world actions.
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum

from .sms import SMSSender, SMSMessage
from .email import EmailSender, EmailMessage
from .calendly import CalendlyClient, CalendlyBooking, get_calendly_link

logger = logging.getLogger(__name__)


class ActionType(str, Enum):
    """Types of actions agents can trigger."""
    SEND_VIDEO_SMS = "send_video_sms"
    SEND_VIDEO_EMAIL = "send_video_email"
    SEND_CALENDLY_SMS = "send_calendly_sms"
    SEND_CALENDLY_EMAIL = "send_calendly_email"
    BOOK_MEETING = "book_meeting"
    SEND_THANK_YOU = "send_thank_you"
    SEND_NOT_INTERESTED = "send_not_interested"
    UPDATE_CRM = "update_crm"


@dataclass
class ActionResult:
    """Result of executing an action."""
    action_type: ActionType
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class LeadContext:
    """Context about the lead for personalization."""
    phone_number: str
    email: Optional[str] = None
    first_name: str = "there"
    last_name: Optional[str] = None
    company_name: Optional[str] = None
    pain_points: List[str] = field(default_factory=list)
    demo_type: str = "full_demo"

    @property
    def full_name(self) -> str:
        if self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name


class ActionHandler:
    """
    Executes actions during and after calls.

    Usage:
        handler = ActionHandler()

        # During call - lead asks for video
        result = await handler.send_video(
            lead=LeadContext(
                phone_number="+15551234567",
                email="john@company.com",
                first_name="John"
            ),
            channel="sms"  # or "email" or "both"
        )

        # After call - lead wants to book
        result = await handler.send_calendly(
            lead=lead_context,
            channel="sms"
        )
    """

    def __init__(
        self,
        sms_sender: Optional[SMSSender] = None,
        email_sender: Optional[EmailSender] = None,
        calendly_client: Optional[CalendlyClient] = None,
    ):
        self.sms = sms_sender or SMSSender()
        self.email = email_sender or EmailSender()
        self.calendly = calendly_client or CalendlyClient()

        logger.info("ActionHandler initialized")

    async def execute(
        self,
        action_type: ActionType,
        lead: LeadContext,
        **kwargs,
    ) -> ActionResult:
        """
        Execute an action based on type.

        Args:
            action_type: Type of action to execute
            lead: Lead context for personalization
            **kwargs: Additional action-specific parameters

        Returns:
            ActionResult with success status
        """
        try:
            if action_type == ActionType.SEND_VIDEO_SMS:
                return await self._send_video_sms(lead, **kwargs)
            elif action_type == ActionType.SEND_VIDEO_EMAIL:
                return await self._send_video_email(lead, **kwargs)
            elif action_type == ActionType.SEND_CALENDLY_SMS:
                return await self._send_calendly_sms(lead, **kwargs)
            elif action_type == ActionType.SEND_CALENDLY_EMAIL:
                return await self._send_calendly_email(lead, **kwargs)
            elif action_type == ActionType.BOOK_MEETING:
                return await self._book_meeting(lead, **kwargs)
            elif action_type == ActionType.SEND_THANK_YOU:
                return await self._send_thank_you(lead, **kwargs)
            elif action_type == ActionType.SEND_NOT_INTERESTED:
                return await self._send_not_interested(lead, **kwargs)
            else:
                return ActionResult(
                    action_type=action_type,
                    success=False,
                    error=f"Unknown action type: {action_type}",
                )
        except Exception as e:
            logger.error(f"Action {action_type} failed: {e}")
            return ActionResult(
                action_type=action_type,
                success=False,
                error=str(e),
            )

    async def send_video(
        self,
        lead: LeadContext,
        channel: str = "sms",
        video_url: Optional[str] = None,
    ) -> ActionResult:
        """
        Send video link via preferred channel.

        Args:
            lead: Lead context
            channel: "sms", "email", or "both"
            video_url: Custom video URL

        Returns:
            ActionResult
        """
        if channel == "both":
            sms_result = await self.execute(
                ActionType.SEND_VIDEO_SMS, lead, video_url=video_url
            )
            email_result = await self.execute(
                ActionType.SEND_VIDEO_EMAIL, lead, video_url=video_url
            )
            return ActionResult(
                action_type=ActionType.SEND_VIDEO_SMS,
                success=sms_result.success or email_result.success,
                details={"sms": sms_result, "email": email_result},
            )
        elif channel == "email" and lead.email:
            return await self.execute(
                ActionType.SEND_VIDEO_EMAIL, lead, video_url=video_url
            )
        else:
            return await self.execute(
                ActionType.SEND_VIDEO_SMS, lead, video_url=video_url
            )

    async def send_calendly(
        self,
        lead: LeadContext,
        channel: str = "sms",
    ) -> ActionResult:
        """
        Send Calendly booking link via preferred channel.

        Args:
            lead: Lead context
            channel: "sms", "email", or "both"

        Returns:
            ActionResult
        """
        if channel == "both":
            sms_result = await self.execute(ActionType.SEND_CALENDLY_SMS, lead)
            email_result = await self.execute(ActionType.SEND_CALENDLY_EMAIL, lead)
            return ActionResult(
                action_type=ActionType.SEND_CALENDLY_SMS,
                success=sms_result.success or email_result.success,
                details={"sms": sms_result, "email": email_result},
            )
        elif channel == "email" and lead.email:
            return await self.execute(ActionType.SEND_CALENDLY_EMAIL, lead)
        else:
            return await self.execute(ActionType.SEND_CALENDLY_SMS, lead)

    # Private action implementations

    async def _send_video_sms(
        self,
        lead: LeadContext,
        video_url: Optional[str] = None,
    ) -> ActionResult:
        """Send video link via SMS."""
        result = await self.sms.send_video_link(
            to_number=lead.phone_number,
            lead_name=lead.first_name,
            video_url=video_url,
        )

        return ActionResult(
            action_type=ActionType.SEND_VIDEO_SMS,
            success=result.status != "failed",
            message_id=result.sid,
            error=result.error,
        )

    async def _send_video_email(
        self,
        lead: LeadContext,
        video_url: Optional[str] = None,
    ) -> ActionResult:
        """Send video link via email."""
        if not lead.email:
            return ActionResult(
                action_type=ActionType.SEND_VIDEO_EMAIL,
                success=False,
                error="No email address available",
            )

        result = await self.email.send_video_link(
            to_email=lead.email,
            to_name=lead.full_name,
            video_url=video_url,
        )

        return ActionResult(
            action_type=ActionType.SEND_VIDEO_EMAIL,
            success=result.status == "sent",
            message_id=result.message_id,
            error=result.error,
        )

    async def _send_calendly_sms(self, lead: LeadContext) -> ActionResult:
        """Send Calendly link via SMS."""
        result = await self.sms.send_calendly_link(
            to_number=lead.phone_number,
            lead_name=lead.first_name,
            lead_email=lead.email,
        )

        return ActionResult(
            action_type=ActionType.SEND_CALENDLY_SMS,
            success=result.status != "failed",
            message_id=result.sid,
            error=result.error,
        )

    async def _send_calendly_email(self, lead: LeadContext) -> ActionResult:
        """Send Calendly link via email."""
        if not lead.email:
            return ActionResult(
                action_type=ActionType.SEND_CALENDLY_EMAIL,
                success=False,
                error="No email address available",
            )

        # Build demo focus from pain points
        demo_focus = self._get_demo_focus(lead.pain_points)

        result = await self.email.send_calendly_link(
            to_email=lead.email,
            to_name=lead.full_name,
            demo_focus=demo_focus,
        )

        return ActionResult(
            action_type=ActionType.SEND_CALENDLY_EMAIL,
            success=result.status == "sent",
            message_id=result.message_id,
            error=result.error,
        )

    async def _book_meeting(
        self,
        lead: LeadContext,
        start_time: Optional[str] = None,
    ) -> ActionResult:
        """Book a meeting via Calendly API."""
        if not lead.email:
            # Can't book without email - send link instead
            return await self._send_calendly_sms(lead)

        # Get pre-filled booking link
        booking_link = get_calendly_link(
            lead_name=lead.full_name,
            lead_email=lead.email,
        )

        # For full API booking (enterprise Calendly), you'd use:
        # booking = await self.calendly.create_booking(...)

        return ActionResult(
            action_type=ActionType.BOOK_MEETING,
            success=True,
            details={
                "booking_link": booking_link,
                "method": "link",  # vs "api" for direct booking
            },
        )

    async def _send_thank_you(self, lead: LeadContext) -> ActionResult:
        """Send thank you message after call."""
        # Try SMS first (more likely to be read)
        result = await self.sms.send_thank_you(
            to_number=lead.phone_number,
            lead_name=lead.first_name,
        )

        return ActionResult(
            action_type=ActionType.SEND_THANK_YOU,
            success=result.status != "failed",
            message_id=result.sid,
            error=result.error,
        )

    async def _send_not_interested(self, lead: LeadContext) -> ActionResult:
        """Send graceful exit email when not interested."""
        if not lead.email:
            # Just SMS thank you
            return await self._send_thank_you(lead)

        result = await self.email.send_not_interested(
            to_email=lead.email,
            to_name=lead.full_name,
        )

        return ActionResult(
            action_type=ActionType.SEND_NOT_INTERESTED,
            success=result.status == "sent",
            message_id=result.message_id,
            error=result.error,
        )

    def _get_demo_focus(self, pain_points: List[str]) -> str:
        """Get demo focus text from pain points."""
        if "dispatch" in pain_points:
            return "how we handle dispatch for multi-trade shops"
        elif "qbo" in pain_points or "quickbooks" in pain_points:
            return "how we sync everything to QuickBooks in real-time"
        elif "reporting" in pain_points or "reports" in pain_points:
            return "how to pull reports you actually trust"
        elif "assets" in pain_points:
            return "how to track asset history properly"
        else:
            return "how Coperniq can streamline your operations"


# Convenience function for agents to use
async def handle_agent_action(
    action: str,
    lead_phone: str,
    lead_name: str,
    lead_email: Optional[str] = None,
    pain_points: Optional[List[str]] = None,
    **kwargs,
) -> ActionResult:
    """
    Handle an action from an agent decision.

    This is the main entry point for agent-triggered actions.

    Args:
        action: Action string from agent (e.g., "send_video", "send_calendly")
        lead_phone: Lead's phone number
        lead_name: Lead's name
        lead_email: Lead's email (optional)
        pain_points: Identified pain points
        **kwargs: Additional parameters

    Returns:
        ActionResult
    """
    handler = ActionHandler()

    lead = LeadContext(
        phone_number=lead_phone,
        email=lead_email,
        first_name=lead_name.split()[0] if lead_name else "there",
        last_name=" ".join(lead_name.split()[1:]) if lead_name and len(lead_name.split()) > 1 else None,
        pain_points=pain_points or [],
    )

    # Map agent action strings to action types
    action_map = {
        "send_video": lambda: handler.send_video(lead, channel=kwargs.get("channel", "sms")),
        "send_calendly": lambda: handler.send_calendly(lead, channel=kwargs.get("channel", "sms")),
        "book_meeting": lambda: handler.execute(ActionType.BOOK_MEETING, lead, **kwargs),
        "send_thank_you": lambda: handler.execute(ActionType.SEND_THANK_YOU, lead),
        "not_interested": lambda: handler.execute(ActionType.SEND_NOT_INTERESTED, lead),
    }

    if action in action_map:
        return await action_map[action]()
    else:
        return ActionResult(
            action_type=ActionType.UPDATE_CRM,
            success=False,
            error=f"Unknown action: {action}",
        )
