"""
CloserAgent - Books meetings with qualified leads.

Responsibilities:
1. Propose available meeting times
2. Handle scheduling preferences
3. Confirm meeting details
4. Send video/calendly links via SMS or email
5. Trigger post-call review gate
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path

from ..integrations.action_handler import ActionHandler, ActionType, LeadContext, ActionResult

logger = logging.getLogger(__name__)


@dataclass
class CloseResult:
    """Result of closing attempt."""
    response: str
    action: str  # propose_times, meeting_confirmed, reschedule, declined, send_video, send_calendly, continue
    proposed_times: List[str] = field(default_factory=list)
    meeting_time: Optional[str] = None
    emotion: str = "enthusiastic"
    # Coperniq-specific fields
    demo_type: str = ""  # specific_pain, full_demo, short_demo, video_only
    email: str = ""  # Contact email for calendar invite
    calendly_link: str = "https://calendly.com/coperniq-sales/disco"
    # Action result (when SMS/email sent)
    action_result: Optional[ActionResult] = None


class CloserAgent:
    """
    Books meetings with qualified leads.

    Flow:
    1. Summarize value proposition
    2. Propose 2-3 specific times
    3. Handle their preference
    4. Confirm and set expectations
    5. Send video/calendly links when requested
    """

    def __init__(self, llm_provider: Any, action_handler: Optional[ActionHandler] = None):
        self.llm = llm_provider
        self.action_handler = action_handler or ActionHandler()
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "closer.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        return self._default_prompt()

    def _default_prompt(self) -> str:
        return """You are Tim from Coperniq closing a qualified lead. Book a 15-minute demo.

Calendly: https://calendly.com/coperniq-sales/disco

Closing Framework:
1. SUMMARIZE: Based on their pain, explain what they'll see
   - Dispatch pain: "I'll show you exactly how we handle dispatch for multi-trade shops"
   - QBO sync: "I'll show you how we sync everything to QuickBooks in real-time"
   - Reporting: "I'll show you how to pull reports you actually trust"
   - Full demo: "I'll walk you through projects, dispatch, assets, and QBO sync—15 minutes, no fluff"

2. PROPOSE: "I have Tuesday at 2pm or Wednesday at 10am available. Which works better?"
   - Always offer 2 specific times
   - 15 minutes is the magic number

3. CONFIRM: "Perfect! I've got you down for [day] at [time]. You'll get a calendar invite shortly."
   - Get email if needed: "What's the best email for the invite?"

4. SET EXPECTATIONS: "You'll see a Calendly invite from me. It'll be a quick 15 minutes focused on [their pain]."

If they hesitate: "Look, worst case—you spend 15 minutes and learn we're not for you. Best case—you find the thing that's been breaking. Worth a look?"

If they decline: "Can I send you a 2-minute video instead? No call, no follow-up unless you want one."

Be enthusiastic but not pushy. Always have a soft exit ready."""

    async def close(
        self,
        transcript: str,
        lead_context: Dict[str, Any],
        available_times: Optional[List[str]] = None,
        pain_points: Optional[List[str]] = None,
    ) -> CloseResult:
        """Attempt to book a meeting.

        Args:
            transcript: What the lead just said
            lead_context: Company info from CRM
            available_times: Optional list of available meeting times
            pain_points: Pain points identified during qualification

        Returns:
            CloseResult with booking status
        """
        company_name = lead_context.get("company_name", "Unknown")
        logger.info(f"Closing lead: {company_name}")

        context = {
            "prompt": self.prompt,
            "transcript": transcript,
            "lead": lead_context,
            "available_times": available_times or [],
            "pain_points": pain_points or [],
            "calendly_link": "https://calendly.com/coperniq-sales/disco",
        }

        result = await self.llm(context)

        action = result.get("action", "propose_times")
        meeting_time = result.get("meeting_time")
        demo_type = result.get("demo_type", "")

        if action == "meeting_confirmed" and meeting_time:
            logger.info(f"Meeting confirmed for {meeting_time} ({demo_type or 'full_demo'})")
        elif action == "send_video":
            logger.info("Sending video instead of meeting")
        elif action == "declined":
            logger.info("Lead declined meeting")

        return CloseResult(
            response=result.get("response", ""),
            action=action,
            proposed_times=result.get("proposed_times", []),
            meeting_time=meeting_time,
            emotion=result.get("emotion", "enthusiastic"),
            demo_type=demo_type,
            email=result.get("email", ""),
        )

    def get_summary_for_pain(self, pain_points: List[str]) -> str:
        """Get the appropriate summary based on identified pain points.

        Args:
            pain_points: List of pain points from qualification

        Returns:
            Tailored summary statement
        """
        if "dispatch" in pain_points:
            return "I'll show you exactly how we handle dispatch for multi-trade shops and nothing else. If it doesn't fit, I'll tell you."
        elif "qbo" in pain_points or "quickbooks" in pain_points:
            return "I'll show you how we sync everything to QuickBooks in real-time—no more daily prayer or manual entry."
        elif "reporting" in pain_points or "reports" in pain_points:
            return "I'll show you how to pull reports you actually trust—no more rebuilding in Excel."
        elif "assets" in pain_points:
            return "I'll show you how to track asset history properly—no more spreadsheets or tribal knowledge."
        else:
            return "I'll walk you through projects, dispatch, assets, and QBO sync—15 minutes, no fluff. If it doesn't fit your world, you can say so."

    async def send_video_link(
        self,
        lead_context: Dict[str, Any],
        channel: str = "sms",
    ) -> ActionResult:
        """Send video link via SMS or email.

        Called when lead asks for video instead of meeting.

        Args:
            lead_context: Lead information (phone, email, name)
            channel: "sms", "email", or "both"

        Returns:
            ActionResult with send status
        """
        lead = self._build_lead_context(lead_context)
        result = await self.action_handler.send_video(lead, channel=channel)
        logger.info(f"Sent video link to {lead.phone_number} via {channel}: {result.success}")
        return result

    async def send_calendly_link(
        self,
        lead_context: Dict[str, Any],
        channel: str = "sms",
    ) -> ActionResult:
        """Send Calendly booking link via SMS or email.

        Called during call when lead wants to book but needs the link.

        Args:
            lead_context: Lead information (phone, email, name)
            channel: "sms", "email", or "both"

        Returns:
            ActionResult with send status
        """
        lead = self._build_lead_context(lead_context)
        result = await self.action_handler.send_calendly(lead, channel=channel)
        logger.info(f"Sent Calendly link to {lead.phone_number} via {channel}: {result.success}")
        return result

    async def send_thank_you(
        self,
        lead_context: Dict[str, Any],
    ) -> ActionResult:
        """Send thank you message after call.

        Args:
            lead_context: Lead information

        Returns:
            ActionResult with send status
        """
        lead = self._build_lead_context(lead_context)
        result = await self.action_handler.execute(ActionType.SEND_THANK_YOU, lead)
        logger.info(f"Sent thank you to {lead.phone_number}: {result.success}")
        return result

    def _build_lead_context(self, lead_context: Dict[str, Any]) -> LeadContext:
        """Build LeadContext from lead dictionary.

        Args:
            lead_context: Raw lead data dict

        Returns:
            LeadContext dataclass
        """
        name = lead_context.get("contact_name", lead_context.get("name", "there"))
        name_parts = name.split() if name else ["there"]

        return LeadContext(
            phone_number=lead_context.get("phone", lead_context.get("phone_number", "")),
            email=lead_context.get("email"),
            first_name=name_parts[0],
            last_name=" ".join(name_parts[1:]) if len(name_parts) > 1 else None,
            company_name=lead_context.get("company_name"),
            pain_points=lead_context.get("pain_points", []),
            demo_type=lead_context.get("demo_type", "full_demo"),
        )
