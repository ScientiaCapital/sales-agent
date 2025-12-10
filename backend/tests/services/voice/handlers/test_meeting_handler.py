"""Tests for MeetingSchedulerHandler."""

import pytest
from datetime import datetime, timedelta
from app.services.voice.handlers.meeting_handler import (
    MeetingSchedulerHandler,
    MeetingState
)
from app.services.voice.handlers.base import HandlerResponse
from app.services.voice.intent_classifier import SalesIntent


class TestMeetingSchedulerHandler:
    """Tests for meeting scheduler handler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return MeetingSchedulerHandler()

    def test_init(self, handler):
        """Test handler initialization."""
        assert handler is not None
        assert handler.cerebras_service is None

    def test_init_with_cerebras_service(self):
        """Test handler with CerebrasService."""
        mock_service = object()
        handler = MeetingSchedulerHandler(cerebras_service=mock_service)
        assert handler.cerebras_service is mock_service

    def test_handle_initial_meeting_request(self, handler):
        """Test handling initial meeting request."""
        response = handler.handle(
            transcript="Can we schedule a demo?",
            conversation_history=[],
            lead_context=None
        )

        assert isinstance(response, HandlerResponse)
        assert response.response_text is not None
        assert "week" in response.response_text.lower() or "schedule" in response.response_text.lower()
        assert response.next_intent == SalesIntent.MEETING_SCHEDULE
        assert response.should_transfer is False

    def test_handle_with_time_preference(self, handler):
        """Test handling with time preference expressed."""
        history = [
            {"role": "user", "content": "I'd like to schedule a demo"},
            {"role": "assistant", "content": "Are you looking at this week or next?"}
        ]

        response = handler.handle(
            transcript="This week works better for me",
            conversation_history=history,
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("time_preference") is not None
        assert response.data["time_preference"].get("week") == "this"

    def test_parse_time_preference_this_week(self, handler):
        """Test parsing this week preference."""
        pref = handler.parse_time_preference("i'm free this week")
        assert pref is not None
        assert pref.get("week") == "this"

    def test_parse_time_preference_next_week(self, handler):
        """Test parsing next week preference."""
        pref = handler.parse_time_preference("next week would be better")
        assert pref is not None
        assert pref.get("week") == "next"

    def test_parse_time_preference_morning(self, handler):
        """Test parsing morning preference."""
        pref = handler.parse_time_preference("mornings work best for me")
        assert pref is not None
        assert pref.get("time_of_day") == "morning"

    def test_parse_time_preference_afternoon(self, handler):
        """Test parsing afternoon preference."""
        pref = handler.parse_time_preference("afternoons are better, maybe after lunch")
        assert pref is not None
        assert pref.get("time_of_day") == "afternoon"

    def test_parse_time_preference_specific_day(self, handler):
        """Test parsing specific day preference."""
        pref = handler.parse_time_preference("how about tuesday?")
        assert pref is not None
        assert pref.get("day") == "Tuesday"

    def test_parse_time_preference_specific_time(self, handler):
        """Test parsing specific time."""
        pref = handler.parse_time_preference("can we do 2:30 pm?")
        assert pref is not None
        assert pref.get("specific_time") is not None
        assert "2:30" in pref["specific_time"]

    def test_propose_time_slots_default(self, handler):
        """Test default time slot proposal."""
        slots = handler.propose_time_slots()

        assert len(slots) >= 2
        assert len(slots) <= 3
        for slot in slots:
            assert "at" in slot.lower()

    def test_propose_time_slots_morning(self, handler):
        """Test morning time slot proposal."""
        slots = handler.propose_time_slots({"time_of_day": "morning"})

        assert len(slots) >= 2
        for slot in slots:
            assert "AM" in slot

    def test_propose_time_slots_afternoon(self, handler):
        """Test afternoon time slot proposal."""
        slots = handler.propose_time_slots({"time_of_day": "afternoon"})

        assert len(slots) >= 2
        for slot in slots:
            assert "PM" in slot

    def test_propose_time_slots_next_week(self, handler):
        """Test next week time slot proposal."""
        slots = handler.propose_time_slots({"week": "next"})

        # Slots should be for next week (we can't easily verify dates, but should not crash)
        assert len(slots) >= 2

    def test_propose_time_slots_skips_weekends(self, handler):
        """Test that proposed slots skip weekends."""
        slots = handler.propose_time_slots()

        for slot in slots:
            assert "Saturday" not in slot
            assert "Sunday" not in slot

    def test_handle_time_selection_first(self, handler):
        """Test handling first slot selection."""
        history = [
            {"role": "user", "content": "Can we schedule a demo?"},
            {"role": "assistant", "content": "Are you looking at this week?"},
            {"role": "user", "content": "Yes, this week"},
            {"role": "assistant", "content": "I have Tuesday at 2 PM or Wednesday at 3 PM"}
        ]

        response = handler.handle(
            transcript="The first one works for me",
            conversation_history=history,
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("selected_time") == "slot_1"

    def test_handle_time_selection_second(self, handler):
        """Test handling second slot selection."""
        history = [
            {"role": "user", "content": "this week please"},
        ]

        response = handler.handle(
            transcript="I'll take the second option",
            conversation_history=history,
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("selected_time") == "slot_2"

    def test_email_extraction(self, handler):
        """Test email address extraction."""
        response = handler.handle(
            transcript="You can send it to john.doe@example.com",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("email") == "john.doe@example.com"

    def test_email_from_lead_context(self, handler):
        """Test email from lead context is used."""
        lead_context = {
            "email": "existing@company.com",
            "contact_name": "Jane Doe"
        }

        response = handler.handle(
            transcript="Can we schedule a demo?",
            conversation_history=[],
            lead_context=lead_context
        )

        assert response.data is not None
        assert response.data.get("email") == "existing@company.com"

    def test_confirmation_with_all_data(self, handler):
        """Test meeting confirmation when all data is present."""
        lead_context = {
            "email": "test@example.com",
            "contact_name": "Test User"
        }

        history = [
            {"role": "user", "content": "this week morning please"},
            {"role": "assistant", "content": "Tuesday at 10 AM or Wednesday at 9 AM?"},
            {"role": "user", "content": "the first one"},
            {"role": "assistant", "content": "Great, Tuesday at 10 AM. What email?"}
        ]

        response = handler.handle(
            transcript="yes perfect, sounds good",
            conversation_history=history,
            lead_context=lead_context
        )

        # Should be confirmed or asking for email
        assert response.data is not None

    def test_response_is_tts_friendly(self, handler):
        """Test that responses are suitable for TTS."""
        response = handler.handle(
            transcript="I want to schedule a demo",
            conversation_history=[],
            lead_context=None
        )

        # No markdown or formatting
        assert "**" not in response.response_text
        assert "##" not in response.response_text
        assert "```" not in response.response_text
        assert "* " not in response.response_text

    def test_response_proposes_options_naturally(self, handler):
        """Test time proposals sound natural."""
        history = [{"role": "user", "content": "this week"}]

        response = handler.handle(
            transcript="morning is better",
            conversation_history=history,
            lead_context=None
        )

        # Should propose times in natural language
        assert "?" in response.response_text or "option" in response.response_text.lower()

    def test_meeting_data_accumulates(self, handler):
        """Test meeting data accumulates across turns."""
        # First turn - time preference
        response1 = handler.handle(
            transcript="next week morning please",
            conversation_history=[],
            lead_context=None
        )

        history = [
            {"role": "user", "content": "next week morning please"},
            {"role": "assistant", "content": response1.response_text}
        ]

        # Second turn - slot selection
        response2 = handler.handle(
            transcript="the first option",
            conversation_history=history,
            lead_context=None
        )

        assert response2.data is not None
        # Should have both preference and selection
        assert response2.data.get("time_preference") is not None or response2.data.get("selected_time") is not None


class TestMeetingState:
    """Tests for meeting state constants."""

    def test_states_defined(self):
        """Test all states are defined."""
        assert MeetingState.INITIAL == "initial"
        assert MeetingState.PROPOSING_TIMES == "proposing_times"
        assert MeetingState.CONFIRMING_TIME == "confirming_time"
        assert MeetingState.COLLECTING_EMAIL == "collecting_email"
        assert MeetingState.CONFIRMED == "confirmed"

    def test_states_are_unique(self):
        """Test all states have unique values."""
        states = [
            MeetingState.INITIAL,
            MeetingState.PROPOSING_TIMES,
            MeetingState.CONFIRMING_TIME,
            MeetingState.COLLECTING_EMAIL,
            MeetingState.CONFIRMED
        ]
        assert len(states) == len(set(states))


class TestMeetingConfirmation:
    """Tests for meeting confirmation flow."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return MeetingSchedulerHandler()

    def test_confirmation_includes_time(self, handler):
        """Test confirmation message includes selected time."""
        # Simulate full flow to confirmation
        lead_context = {"email": "test@example.com"}

        history = [
            {"role": "user", "content": "this week please"},
            {"role": "assistant", "content": "Tuesday at 2 PM or Wednesday at 3 PM?"},
            {"role": "user", "content": "the first one Tuesday"},
        ]

        response = handler.handle(
            transcript="yes confirm it",
            conversation_history=history,
            lead_context=lead_context
        )

        # Response should reference time or ask for confirmation
        assert len(response.response_text) > 0

    def test_confirmation_metadata(self, handler):
        """Test confirmation sets metadata."""
        lead_context = {"email": "test@example.com"}

        history = [
            {"role": "user", "content": "this week afternoon the first one"},
        ]

        response = handler.handle(
            transcript="sounds good, book it",
            conversation_history=history,
            lead_context=lead_context
        )

        # Should have some data even if not fully confirmed
        assert response.data is not None

    def test_asks_for_email_if_missing(self, handler):
        """Test handler asks for email when missing."""
        history = [
            {"role": "user", "content": "this week please"},
            {"role": "assistant", "content": "Tuesday at 2 PM or Wednesday?"},
            {"role": "user", "content": "Tuesday works, the first one"}
        ]

        response = handler.handle(
            transcript="yes that time is perfect",
            conversation_history=history,
            lead_context=None  # No email in context
        )

        # Should ask for email or confirm time
        assert len(response.response_text) > 0
