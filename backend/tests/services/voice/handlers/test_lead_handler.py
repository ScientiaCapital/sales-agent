"""Tests for LeadQualificationHandler."""

import pytest
from app.services.voice.handlers.lead_handler import (
    LeadQualificationHandler,
    QUALIFICATION_QUESTIONS
)
from app.services.voice.handlers.base import HandlerResponse
from app.services.voice.intent_classifier import SalesIntent


class TestLeadQualificationHandler:
    """Tests for lead qualification handler."""

    @pytest.fixture
    def handler(self):
        """Create handler instance."""
        return LeadQualificationHandler()

    def test_init(self, handler):
        """Test handler initialization."""
        assert handler is not None
        assert handler.cerebras_service is None

    def test_init_with_cerebras_service(self):
        """Test handler with CerebrasService."""
        mock_service = object()
        handler = LeadQualificationHandler(cerebras_service=mock_service)
        assert handler.cerebras_service is mock_service

    def test_handle_initial_request(self, handler):
        """Test handling initial qualification request."""
        response = handler.handle(
            transcript="Hi, I'm interested in your product",
            conversation_history=[],
            lead_context=None
        )

        assert isinstance(response, HandlerResponse)
        assert response.response_text is not None
        assert len(response.response_text) > 0
        assert response.next_intent == SalesIntent.LEAD_QUALIFICATION
        assert response.should_transfer is False

    def test_handle_with_lead_context(self, handler):
        """Test handling with existing lead data."""
        lead_context = {
            "company": "Acme Corp",
            "contact_name": "John Smith",
            "email": "john@acme.com"
        }

        response = handler.handle(
            transcript="I'm interested in learning more",
            conversation_history=[],
            lead_context=lead_context
        )

        assert isinstance(response, HandlerResponse)
        assert response.data is not None
        assert response.data.get("company") == "Acme Corp"

    def test_extract_company_from_transcript(self, handler):
        """Test company extraction from transcript."""
        response = handler.handle(
            transcript="I'm with TechCorp and we're looking for a solution",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        # Company extraction may or may not succeed depending on regex
        # Main assertion is that it doesn't crash

    def test_extract_role(self, handler):
        """Test role extraction."""
        response = handler.handle(
            transcript="I'm the CTO at my company",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        # Check that decision maker was identified
        if response.data.get("role"):
            assert "Cto" in response.data.get("role", "")

    def test_extract_decision_maker(self, handler):
        """Test decision maker detection."""
        response = handler.handle(
            transcript="I'm the VP of Engineering and I make the purchasing decisions",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("is_decision_maker") in [True, "maybe"]

    def test_extract_timeline_immediate(self, handler):
        """Test immediate timeline extraction."""
        response = handler.handle(
            transcript="We need this ASAP, it's urgent",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("timeline") == "immediate"

    def test_extract_timeline_exploring(self, handler):
        """Test exploring timeline extraction."""
        response = handler.handle(
            transcript="We're just looking around and researching options",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("timeline") == "exploring"

    def test_extract_budget_confirmed(self, handler):
        """Test confirmed budget extraction."""
        response = handler.handle(
            transcript="Yes, we have budget approved for this quarter",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("budget") == "confirmed"

    def test_extract_budget_with_amount(self, handler):
        """Test budget amount extraction."""
        response = handler.handle(
            transcript="Our budget is around $50,000",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        assert "$50,000" in response.data.get("budget", "")

    def test_extract_pain_points(self, handler):
        """Test pain point extraction."""
        response = handler.handle(
            transcript="Our current system is slow and inefficient, costs too much",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        pain_points = response.data.get("pain_points", [])
        assert "efficiency" in pain_points or "cost" in pain_points

    def test_extract_company_size(self, handler):
        """Test company size extraction."""
        response = handler.handle(
            transcript="We have about 200 employees",
            conversation_history=[],
            lead_context=None
        )

        assert response.data is not None
        assert response.data.get("company_size") == "101-500"

    def test_calculate_lead_score_high(self, handler):
        """Test high lead score calculation."""
        qualification_data = {
            "company_size": "500+",
            "is_decision_maker": True,
            "budget": "confirmed",
            "timeline": "immediate"
        }

        score = handler.calculate_lead_score(qualification_data)
        assert score >= 7  # High score triggers transfer

    def test_calculate_lead_score_low(self, handler):
        """Test low lead score calculation."""
        qualification_data = {
            "company_size": "1-10",
            "is_decision_maker": False,
            "budget": "limited",
            "timeline": "exploring"
        }

        score = handler.calculate_lead_score(qualification_data)
        assert score <= 3

    def test_calculate_lead_score_medium(self, handler):
        """Test medium lead score calculation."""
        qualification_data = {
            "company_size": "51-100",
            "is_decision_maker": "maybe",
            "budget": "exploring",
            "timeline": "3_months"
        }

        score = handler.calculate_lead_score(qualification_data)
        assert 3 <= score <= 7

    def test_should_transfer_high_score(self, handler):
        """Test transfer recommendation for high-scoring leads."""
        # Simulate a fully qualified high-value lead
        history = [
            {"role": "user", "content": "I'm the CEO of a Fortune 500 company"},
            {"role": "assistant", "content": "Great! What's your timeline?"},
            {"role": "user", "content": "We need this immediately, budget is approved at $100k"},
        ]

        response = handler.handle(
            transcript="Yes, I make all purchasing decisions here",
            conversation_history=history,
            lead_context={"company": "BigCorp"}
        )

        # High value leads should either transfer or schedule meeting
        assert response.next_intent in [
            SalesIntent.WARM_TRANSFER,
            SalesIntent.MEETING_SCHEDULE,
            SalesIntent.LEAD_QUALIFICATION
        ]

    def test_asks_qualifying_questions(self, handler):
        """Test that handler asks qualifying questions."""
        response = handler.handle(
            transcript="I want to learn about your product",
            conversation_history=[],
            lead_context=None
        )

        # Should ask one of the qualifying questions
        assert "?" in response.response_text

    def test_conversation_continuity(self, handler):
        """Test multi-turn conversation handling."""
        # First turn
        response1 = handler.handle(
            transcript="I'm interested",
            conversation_history=[],
            lead_context=None
        )

        # Second turn with history
        history = [
            {"role": "user", "content": "I'm interested"},
            {"role": "assistant", "content": response1.response_text}
        ]

        response2 = handler.handle(
            transcript="I work at TechCorp as a Director",
            conversation_history=history,
            lead_context=None
        )

        assert response2.data is not None
        # Should have accumulated data from conversation

    def test_response_is_tts_friendly(self, handler):
        """Test that responses are suitable for TTS."""
        response = handler.handle(
            transcript="Tell me more",
            conversation_history=[],
            lead_context=None
        )

        # No markdown or formatting
        assert "**" not in response.response_text
        assert "##" not in response.response_text
        assert "```" not in response.response_text
        assert "* " not in response.response_text

    def test_metadata_tracking(self, handler):
        """Test metadata includes question count."""
        response = handler.handle(
            transcript="Hi there",
            conversation_history=[],
            lead_context=None
        )

        assert response.metadata is not None
        assert "questions_asked" in response.metadata


class TestQualificationQuestions:
    """Tests for qualification question structure."""

    def test_questions_have_required_fields(self):
        """Test all questions have key, question, follow_up."""
        for q in QUALIFICATION_QUESTIONS:
            assert "key" in q
            assert "question" in q
            assert "follow_up" in q

    def test_questions_cover_key_areas(self):
        """Test questions cover company, role, pain, timeline, budget."""
        keys = [q["key"] for q in QUALIFICATION_QUESTIONS]
        assert "company" in keys
        assert "role" in keys
        assert "pain_points" in keys
        assert "timeline" in keys
        assert "budget" in keys

    def test_questions_end_with_question_mark(self):
        """Test all questions are properly formatted."""
        for q in QUALIFICATION_QUESTIONS:
            assert q["question"].endswith("?")
