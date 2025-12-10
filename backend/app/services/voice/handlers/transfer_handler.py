"""Transfer Handler for voice calls.

Manages warm transfers to human representatives with proper handoff summaries.
Designed for natural conversation flow with TTS-friendly responses.
"""

import logging
from typing import Dict, List, Optional

from .base import BaseHandler, HandlerResponse
from app.services.voice.intent_classifier import SalesIntent

logger = logging.getLogger(__name__)


# Transfer destinations by department
TRANSFER_DESTINATIONS = {
    "sales": {
        "name": "Sales Team",
        "extension": "1001",
        "description": "For pricing discussions and closing deals"
    },
    "support": {
        "name": "Customer Support",
        "extension": "1002",
        "description": "For technical questions and existing customers"
    },
    "billing": {
        "name": "Billing Department",
        "extension": "1003",
        "description": "For payment and invoice questions"
    },
    "general": {
        "name": "Main Reception",
        "extension": "0",
        "description": "General inquiries"
    }
}


class TransferHandler(BaseHandler):
    """Handler for WARM_TRANSFER intent.

    Manages the warm transfer process:
    1. Acknowledges transfer request
    2. Generates handoff summary for human rep
    3. Announces transfer to caller
    4. Returns transfer metadata

    Example:
        >>> handler = TransferHandler()
        >>> response = handler.handle(
        ...     transcript="Can I speak to someone in sales?",
        ...     conversation_history=[],
        ...     lead_context=None
        ... )
        >>> print(response.response_text)
        Absolutely! Let me connect you with our sales team...
    """

    def __init__(self, cerebras_service=None):
        """Initialize transfer handler.

        Args:
            cerebras_service: Optional CerebrasService for enhanced summaries
        """
        super().__init__(cerebras_service)
        logger.info("TransferHandler initialized")

    def handle(
        self,
        transcript: str,
        conversation_history: List[Dict],
        lead_context: Optional[Dict] = None
    ) -> HandlerResponse:
        """Process transcript and initiate warm transfer.

        Args:
            transcript: Current user speech transcript
            conversation_history: List of conversation turns
            lead_context: Optional lead data from CRM

        Returns:
            HandlerResponse with transfer announcement and handoff data
        """
        logger.info(f"Processing transfer request: '{transcript}'")

        # Determine transfer destination
        destination = self._determine_destination(transcript, conversation_history)

        # Generate handoff summary for human rep
        handoff_summary = self._generate_handoff_summary(
            conversation_history, lead_context
        )

        # Generate announcement for caller
        response_text = self._generate_transfer_announcement(destination)

        return HandlerResponse(
            response_text=response_text,
            next_intent=None,  # Transfer ends AI handling
            should_transfer=True,
            data={
                "transfer_type": "warm",
                "destination": destination,
                "lead_context": lead_context
            },
            metadata={
                "transfer_initiated": True,
                "destination_name": destination.get("name"),
                "destination_extension": destination.get("extension")
            },
            handoff_summary=handoff_summary,
            transfer_destination=destination
        )

    def _determine_destination(
        self,
        transcript: str,
        conversation_history: List[Dict]
    ) -> Dict[str, str]:
        """Determine which department to transfer to.

        Args:
            transcript: Current transcript
            conversation_history: Previous turns

        Returns:
            Dict with destination info (name, extension, description)
        """
        # Combine all text for analysis
        all_text = transcript.lower()
        for turn in conversation_history:
            if turn.get("role") == "user":
                all_text += " " + turn.get("content", "").lower()

        # Check for department keywords
        if any(word in all_text for word in [
            "sales", "pricing", "quote", "buy", "purchase", "deal", "contract"
        ]):
            return TRANSFER_DESTINATIONS["sales"]

        elif any(word in all_text for word in [
            "support", "help", "problem", "issue", "broken", "not working", "bug"
        ]):
            return TRANSFER_DESTINATIONS["support"]

        elif any(word in all_text for word in [
            "billing", "invoice", "payment", "charge", "refund", "subscription"
        ]):
            return TRANSFER_DESTINATIONS["billing"]

        # Default to sales for general transfer requests
        return TRANSFER_DESTINATIONS["sales"]

    def _generate_handoff_summary(
        self,
        conversation_history: List[Dict],
        lead_context: Optional[Dict]
    ) -> str:
        """Generate summary for human representative.

        Args:
            conversation_history: Previous turns
            lead_context: CRM lead data

        Returns:
            Concise summary string for rep
        """
        summary_parts = []

        # Lead info if available
        if lead_context:
            if lead_context.get("contact_name"):
                summary_parts.append(f"Caller: {lead_context.get('contact_name')}")
            if lead_context.get("company"):
                summary_parts.append(f"Company: {lead_context.get('company')}")
            if lead_context.get("email"):
                summary_parts.append(f"Email: {lead_context.get('email')}")

        # Summarize conversation topics
        topics = self._extract_topics(conversation_history)
        if topics:
            summary_parts.append(f"Topics discussed: {', '.join(topics)}")

        # Get last few user messages for context
        recent_messages = []
        for turn in reversed(conversation_history):
            if turn.get("role") == "user":
                recent_messages.append(turn.get("content", ""))
                if len(recent_messages) >= 2:
                    break

        if recent_messages:
            summary_parts.append(f"Recent context: {' | '.join(reversed(recent_messages))}")

        if not summary_parts:
            return "New caller requesting transfer to human representative."

        return " | ".join(summary_parts)

    def _extract_topics(self, conversation_history: List[Dict]) -> List[str]:
        """Extract key topics from conversation.

        Args:
            conversation_history: Previous turns

        Returns:
            List of topic strings
        """
        topics = []

        all_text = " ".join(
            turn.get("content", "").lower()
            for turn in conversation_history
            if turn.get("role") == "user"
        )

        # Topic detection
        topic_keywords = {
            "pricing": ["price", "cost", "pricing", "expensive", "affordable", "quote"],
            "demo": ["demo", "demonstration", "see it", "show me"],
            "features": ["features", "capabilities", "what can", "does it"],
            "integration": ["integrate", "integration", "connect", "api"],
            "support": ["help", "support", "problem", "issue"],
            "timeline": ["when", "timeline", "deadline", "urgently"]
        }

        for topic, keywords in topic_keywords.items():
            if any(word in all_text for word in keywords):
                topics.append(topic)

        return topics[:4]  # Limit to 4 topics

    def _generate_transfer_announcement(self, destination: Dict[str, str]) -> str:
        """Generate TTS-friendly transfer announcement.

        Args:
            destination: Transfer destination info

        Returns:
            Natural announcement text
        """
        dest_name = destination.get("name", "a team member")

        # Vary the announcement slightly
        announcements = [
            f"Absolutely! Let me connect you with our {dest_name}. "
            f"One moment please while I transfer your call.",

            f"Of course! I'll transfer you to our {dest_name} right now. "
            f"Please hold for just a moment.",

            f"Sure thing! I'm connecting you with our {dest_name}. "
            f"They'll be with you shortly."
        ]

        # Use a simple selection based on destination name length
        index = len(dest_name) % len(announcements)
        return announcements[index]

    def get_transfer_destinations(self) -> Dict[str, Dict[str, str]]:
        """Get available transfer destinations.

        Returns:
            Dict of destination configs
        """
        return TRANSFER_DESTINATIONS.copy()
