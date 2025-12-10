"""Meeting Scheduler Handler for voice calls.

Proposes meeting times, parses preferences, and confirms bookings.
Designed for natural conversation flow with TTS-friendly responses.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .base import BaseHandler, HandlerResponse
from app.services.voice.intent_classifier import SalesIntent

logger = logging.getLogger(__name__)


# Meeting scheduling flow states
class MeetingState:
    INITIAL = "initial"
    PROPOSING_TIMES = "proposing_times"
    CONFIRMING_TIME = "confirming_time"
    COLLECTING_EMAIL = "collecting_email"
    CONFIRMED = "confirmed"


class MeetingSchedulerHandler(BaseHandler):
    """Handler for MEETING_SCHEDULE intent.

    Manages meeting scheduling through natural conversation:
    1. Proposes 2-3 time slots based on preferences
    2. Parses user's time selection
    3. Collects contact info for calendar invite
    4. Generates confirmation summary

    Example:
        >>> handler = MeetingSchedulerHandler()
        >>> response = handler.handle(
        ...     transcript="Can we schedule a demo?",
        ...     conversation_history=[],
        ...     lead_context=None
        ... )
        >>> print(response.response_text)
        I'd be happy to schedule a demo for you! Are you looking at this week or next?
    """

    def __init__(self, cerebras_service=None):
        """Initialize meeting scheduler handler.

        Args:
            cerebras_service: Optional CerebrasService for enhanced responses
        """
        super().__init__(cerebras_service)
        logger.info("MeetingSchedulerHandler initialized")

    def handle(
        self,
        transcript: str,
        conversation_history: List[Dict],
        lead_context: Optional[Dict] = None
    ) -> HandlerResponse:
        """Process transcript and manage meeting scheduling flow.

        Args:
            transcript: Current user speech transcript
            conversation_history: List of conversation turns
            lead_context: Optional lead data from CRM

        Returns:
            HandlerResponse with scheduling response and meeting data
        """
        logger.info(f"Processing meeting request: '{transcript}'")

        # Determine current state in scheduling flow
        meeting_data = self._extract_meeting_data(transcript, conversation_history, lead_context)
        state = self._determine_state(meeting_data)

        logger.info(f"Meeting state: {state}")

        if state == MeetingState.INITIAL:
            return self._handle_initial(transcript, meeting_data)

        elif state == MeetingState.PROPOSING_TIMES:
            return self._handle_time_proposal(transcript, meeting_data)

        elif state == MeetingState.CONFIRMING_TIME:
            return self._handle_time_confirmation(transcript, meeting_data)

        elif state == MeetingState.COLLECTING_EMAIL:
            return self._handle_email_collection(transcript, meeting_data)

        elif state == MeetingState.CONFIRMED:
            return self._handle_confirmation(meeting_data)

        # Fallback
        return self._handle_initial(transcript, meeting_data)

    def _determine_state(self, meeting_data: Dict) -> str:
        """Determine current state in scheduling flow.

        Args:
            meeting_data: Extracted meeting data

        Returns:
            MeetingState string
        """
        if meeting_data.get("confirmed"):
            return MeetingState.CONFIRMED

        if meeting_data.get("email"):
            # Have email, just need to confirm
            return MeetingState.CONFIRMING_TIME

        if meeting_data.get("selected_time"):
            return MeetingState.COLLECTING_EMAIL

        if meeting_data.get("time_preference"):
            return MeetingState.PROPOSING_TIMES

        return MeetingState.INITIAL

    def _extract_meeting_data(
        self,
        transcript: str,
        conversation_history: List[Dict],
        lead_context: Optional[Dict]
    ) -> Dict:
        """Extract meeting data from conversation.

        Args:
            transcript: Current transcript
            conversation_history: Previous turns
            lead_context: CRM lead data

        Returns:
            Dict with meeting scheduling data
        """
        data = {}

        # Get email from lead context
        if lead_context:
            data["email"] = lead_context.get("email")
            data["contact_name"] = lead_context.get("contact_name")

        # Combine all text
        all_text = transcript
        for turn in conversation_history:
            if turn.get("role") == "user":
                all_text += " " + turn.get("content", "")

        all_text_lower = all_text.lower()

        # Extract time preferences
        time_pref = self.parse_time_preference(all_text_lower)
        if time_pref:
            data["time_preference"] = time_pref

        # Check for specific time selection
        selected = self._extract_selected_time(all_text_lower)
        if selected:
            data["selected_time"] = selected

        # Extract email from conversation
        email = self._extract_email(all_text)
        if email:
            data["email"] = email

        # Check for confirmation signals
        if any(word in all_text_lower for word in ["yes", "perfect", "sounds good", "confirm", "book it"]):
            if data.get("selected_time") and data.get("email"):
                data["confirmed"] = True

        return data

    def parse_time_preference(self, text: str) -> Optional[Dict]:
        """Extract time preference from transcript.

        Args:
            text: User transcript (lowercased)

        Returns:
            Dict with week, day_preference, time_of_day, or None
        """
        pref = {}

        # Week preference
        if any(word in text for word in ["this week", "earlier", "soon"]):
            pref["week"] = "this"
        elif any(word in text for word in ["next week", "later"]):
            pref["week"] = "next"

        # Day preference
        days = {
            "monday": "Monday", "tuesday": "Tuesday", "wednesday": "Wednesday",
            "thursday": "Thursday", "friday": "Friday"
        }
        for day_lower, day_cap in days.items():
            if day_lower in text:
                pref["day"] = day_cap
                break

        # Time of day preference
        if any(word in text for word in ["morning", "am", "early"]):
            pref["time_of_day"] = "morning"
        elif any(word in text for word in ["afternoon", "pm", "after lunch"]):
            pref["time_of_day"] = "afternoon"
        elif any(word in text for word in ["evening", "late", "end of day"]):
            pref["time_of_day"] = "evening"

        # Specific time
        time_match = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)?', text)
        if time_match:
            hour = int(time_match.group(1))
            minutes = time_match.group(2) or "00"
            period = time_match.group(3) or ("pm" if hour < 8 else "am")
            pref["specific_time"] = f"{hour}:{minutes} {period}"

        return pref if pref else None

    def _extract_selected_time(self, text: str) -> Optional[str]:
        """Extract selected time slot from text.

        Args:
            text: User transcript (lowercased)

        Returns:
            Selected time string or None
        """
        # Look for "the first one", "second option", etc.
        if any(word in text for word in ["first", "option one", "1st", "earlier"]):
            return "slot_1"
        elif any(word in text for word in ["second", "option two", "2nd", "later"]):
            return "slot_2"
        elif any(word in text for word in ["third", "option three", "3rd", "last"]):
            return "slot_3"

        # Look for specific time mentions that match proposed slots
        # This would be enhanced with actual proposed slots tracking

        return None

    def _extract_email(self, text: str) -> Optional[str]:
        """Extract email address from text.

        Args:
            text: User transcript

        Returns:
            Email string or None
        """
        # Email regex pattern
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        match = re.search(email_pattern, text)
        return match.group() if match else None

    def propose_time_slots(self, preferences: Optional[Dict] = None) -> List[str]:
        """Generate available time slots based on preferences.

        For MVP, returns mock slots. In production, would integrate
        with calendar API.

        Args:
            preferences: User's time preferences

        Returns:
            List of 2-3 time slot strings
        """
        # Calculate base date (next business day)
        now = datetime.now()
        base = now + timedelta(days=1)

        # Skip to Monday if weekend
        while base.weekday() >= 5:
            base += timedelta(days=1)

        # Generate slots based on preferences
        slots = []

        week = preferences.get("week", "this") if preferences else "this"
        time_of_day = preferences.get("time_of_day", "afternoon") if preferences else "afternoon"

        if week == "next":
            base += timedelta(days=7)

        # Generate 3 slots
        if time_of_day == "morning":
            times = ["9:00 AM", "10:30 AM", "11:00 AM"]
        else:  # afternoon/evening
            times = ["2:00 PM", "3:30 PM", "4:00 PM"]

        for i, time in enumerate(times):
            day = base + timedelta(days=i)
            if day.weekday() >= 5:  # Skip weekends
                day += timedelta(days=2)
            day_name = day.strftime("%A")
            slots.append(f"{day_name} at {time}")

        return slots[:3]

    def _handle_initial(self, transcript: str, meeting_data: Dict) -> HandlerResponse:
        """Handle initial meeting request.

        Args:
            transcript: User transcript
            meeting_data: Extracted data

        Returns:
            HandlerResponse asking about timing preference
        """
        response_text = (
            "I'd be happy to schedule a demo for you! "
            "Are you looking at this week or next?"
        )

        return HandlerResponse(
            response_text=response_text,
            next_intent=SalesIntent.MEETING_SCHEDULE,
            should_transfer=False,
            data=meeting_data
        )

    def _handle_time_proposal(self, transcript: str, meeting_data: Dict) -> HandlerResponse:
        """Propose specific time slots.

        Args:
            transcript: User transcript
            meeting_data: Extracted data with preferences

        Returns:
            HandlerResponse with time options
        """
        slots = self.propose_time_slots(meeting_data.get("time_preference"))
        meeting_data["proposed_slots"] = slots

        # Format slots for speech
        if len(slots) >= 2:
            response_text = (
                f"Great! I have a few options for you. "
                f"I can offer {slots[0]}, or {slots[1]}. "
                f"Which works better for you?"
            )
        else:
            response_text = f"I have {slots[0]} available. Does that work for you?"

        return HandlerResponse(
            response_text=response_text,
            next_intent=SalesIntent.MEETING_SCHEDULE,
            should_transfer=False,
            data=meeting_data
        )

    def _handle_time_confirmation(self, transcript: str, meeting_data: Dict) -> HandlerResponse:
        """Confirm selected time slot.

        Args:
            transcript: User transcript
            meeting_data: Extracted data with selection

        Returns:
            HandlerResponse confirming time and asking for email
        """
        # Get the selected slot
        slots = meeting_data.get("proposed_slots", self.propose_time_slots())
        selection = meeting_data.get("selected_time", "slot_1")

        slot_index = {"slot_1": 0, "slot_2": 1, "slot_3": 2}.get(selection, 0)
        selected_slot = slots[min(slot_index, len(slots) - 1)]

        meeting_data["confirmed_time"] = selected_slot

        if meeting_data.get("email"):
            # Already have email, confirm directly
            return self._handle_confirmation(meeting_data)

        response_text = (
            f"Perfect, I'll book you for {selected_slot}. "
            f"What email should I send the calendar invite to?"
        )

        return HandlerResponse(
            response_text=response_text,
            next_intent=SalesIntent.MEETING_SCHEDULE,
            should_transfer=False,
            data=meeting_data
        )

    def _handle_email_collection(self, transcript: str, meeting_data: Dict) -> HandlerResponse:
        """Collect email for calendar invite.

        Args:
            transcript: User transcript (may contain email)
            meeting_data: Extracted data

        Returns:
            HandlerResponse with email request or confirmation
        """
        email = self._extract_email(transcript)

        if email:
            meeting_data["email"] = email
            meeting_data["confirmed"] = True
            return self._handle_confirmation(meeting_data)

        # Need to ask for email
        response_text = (
            "I didn't catch your email. "
            "Could you spell it out for me?"
        )

        return HandlerResponse(
            response_text=response_text,
            next_intent=SalesIntent.MEETING_SCHEDULE,
            should_transfer=False,
            data=meeting_data
        )

    def _handle_confirmation(self, meeting_data: Dict) -> HandlerResponse:
        """Generate meeting confirmation.

        Args:
            meeting_data: Complete meeting data

        Returns:
            HandlerResponse with confirmation summary
        """
        time = meeting_data.get("confirmed_time", "your selected time")
        email = meeting_data.get("email", "your email")
        contact = meeting_data.get("contact_name", "")

        greeting = f"Thank you{', ' + contact if contact else ''}!"

        response_text = (
            f"{greeting} "
            f"Your demo is confirmed for {time}. "
            f"I'll send a calendar invite to {email}. "
            f"Is there anything else I can help you with?"
        )

        return HandlerResponse(
            response_text=response_text,
            next_intent=SalesIntent.GENERAL,  # Done scheduling
            should_transfer=False,
            data={
                **meeting_data,
                "confirmed": True,
                "status": "booked"
            },
            metadata={
                "meeting_booked": True,
                "meeting_time": time,
                "invite_email": email
            }
        )
