"""Tests for SalesIntentClassifier following TDD approach.

Test cases:
1. SalesIntent enum has all expected values
2. classify_intent() correctly identifies each intent type
3. classify_intent() returns GENERAL for empty/unknown queries
4. classify_intent() is case-insensitive
5. classify_intent() handles whitespace correctly
6. classify_intent() respects intent priority order
"""

import sys
import importlib.util
from pathlib import Path

import pytest

# Direct import to bypass app.services.__init__.py which has dependencies
module_path = Path(__file__).parent.parent.parent.parent / "app" / "services" / "voice" / "intent_classifier.py"
spec = importlib.util.spec_from_file_location("intent_classifier", module_path)
intent_classifier_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(intent_classifier_module)

SalesIntent = intent_classifier_module.SalesIntent
SalesIntentClassifier = intent_classifier_module.SalesIntentClassifier


class TestSalesIntent:
    """Test SalesIntent enum values."""

    def test_enum_has_all_expected_values(self):
        """Test that SalesIntent enum has all expected intent types."""
        expected_intents = {
            "LEAD_QUALIFICATION",
            "MEETING_SCHEDULE",
            "PRODUCT_INFO",
            "PRICING_INQUIRY",
            "WARM_TRANSFER",
            "OBJECTION",
            "GENERAL",
        }
        actual_intents = {intent.name for intent in SalesIntent}
        assert actual_intents == expected_intents

    def test_enum_values_are_lowercase_snake_case(self):
        """Test that enum values follow lowercase snake_case convention."""
        for intent in SalesIntent:
            assert intent.value == intent.name.lower()


class TestSalesIntentClassifier:
    """Test SalesIntentClassifier intent classification."""

    @pytest.fixture
    def classifier(self):
        """Create a SalesIntentClassifier instance."""
        return SalesIntentClassifier()

    # Test LEAD_QUALIFICATION intent
    def test_classifies_lead_qualification_intent(self, classifier):
        """Test classification of lead qualification queries."""
        queries = [
            "Tell me about your company",
            "What do you do?",
            "Who are you?",
            "What's your role?",
            "Can you tell me your company name?",
            "What type of business are you in?",
        ]
        for query in queries:
            result = classifier.classify_intent(query)
            assert result == SalesIntent.LEAD_QUALIFICATION, f"Failed for: {query}"

    # Test MEETING_SCHEDULE intent
    def test_classifies_meeting_schedule_intent(self, classifier):
        """Test classification of meeting scheduling queries."""
        queries = [
            "Can we book a meeting?",
            "Schedule a call with me",
            "Let's set up a demo",
            "What times work for you?",
            "Check your calendar availability",
            "I'd like to schedule an appointment",
        ]
        for query in queries:
            result = classifier.classify_intent(query)
            assert result == SalesIntent.MEETING_SCHEDULE, f"Failed for: {query}"

    # Test PRODUCT_INFO intent
    def test_classifies_product_info_intent(self, classifier):
        """Test classification of product information queries."""
        queries = [
            "What does your product do?",
            "Tell me about your service",
            "What features do you offer?",
            "How does it work?",
            "Tell me more about what you offer",
        ]
        for query in queries:
            result = classifier.classify_intent(query)
            assert result == SalesIntent.PRODUCT_INFO, f"Failed for: {query}"

    # Test PRICING_INQUIRY intent
    def test_classifies_pricing_inquiry_intent(self, classifier):
        """Test classification of pricing queries."""
        queries = [
            "How much does it cost?",
            "What's the price?",
            "What's your pricing model?",
            "Can I afford this?",
            "What's the budget requirement?",
        ]
        for query in queries:
            result = classifier.classify_intent(query)
            assert result == SalesIntent.PRICING_INQUIRY, f"Failed for: {query}"

    # Test WARM_TRANSFER intent
    def test_classifies_warm_transfer_intent(self, classifier):
        """Test classification of warm transfer queries."""
        queries = [
            "Can I speak to someone?",
            "Transfer me to a person",
            "I want to talk to a human",
            "Connect me with a representative",
            "Can I speak with your manager?",
        ]
        for query in queries:
            result = classifier.classify_intent(query)
            assert result == SalesIntent.WARM_TRANSFER, f"Failed for: {query}"

    # Test OBJECTION intent
    def test_classifies_objection_intent(self, classifier):
        """Test classification of objection queries."""
        queries = [
            "Not interested",
            "No thanks",
            "Too expensive for us",
            "We already have a solution",
            "Don't need this",
            "I'm busy right now",
            "Call back later please",
        ]
        for query in queries:
            result = classifier.classify_intent(query)
            assert result == SalesIntent.OBJECTION, f"Failed for: {query}"

    # Test GENERAL intent (default fallback)
    def test_classifies_general_intent_for_unknown_queries(self, classifier):
        """Test that unknown queries return GENERAL intent."""
        queries = [
            "Hello",
            "How are you?",
            "What's the weather like?",
            "Random question here",
            "This doesn't match any pattern",
        ]
        for query in queries:
            result = classifier.classify_intent(query)
            assert result == SalesIntent.GENERAL, f"Failed for: {query}"

    def test_classifies_empty_query_as_general(self, classifier):
        """Test that empty queries return GENERAL intent."""
        assert classifier.classify_intent("") == SalesIntent.GENERAL
        assert classifier.classify_intent("   ") == SalesIntent.GENERAL

    # Test case insensitivity
    def test_classification_is_case_insensitive(self, classifier):
        """Test that classification is case-insensitive."""
        queries = [
            ("WHAT DO YOU DO?", SalesIntent.LEAD_QUALIFICATION),
            ("Book A Meeting", SalesIntent.MEETING_SCHEDULE),
            ("HOW MUCH DOES IT COST?", SalesIntent.PRICING_INQUIRY),
            ("not interested", SalesIntent.OBJECTION),
            ("TeLl Me AbOuT yOuR pRoDuCt", SalesIntent.PRODUCT_INFO),
        ]
        for query, expected_intent in queries:
            result = classifier.classify_intent(query)
            assert result == expected_intent, f"Failed for: {query}"

    # Test whitespace handling
    def test_handles_extra_whitespace(self, classifier):
        """Test that classification handles extra whitespace correctly."""
        queries = [
            ("  Tell me about your company  ", SalesIntent.LEAD_QUALIFICATION),
            ("\t\nSchedule a meeting\n\t", SalesIntent.MEETING_SCHEDULE),
            ("   How much does it   cost?   ", SalesIntent.PRICING_INQUIRY),
        ]
        for query, expected_intent in queries:
            result = classifier.classify_intent(query)
            assert result == expected_intent, f"Failed for: {query}"

    # Test intent priority (if multiple patterns match, first one wins)
    def test_respects_intent_priority_order(self, classifier):
        """Test that when multiple patterns match, priority order is respected."""
        # This query could match multiple intents, but should match the highest priority one
        # "schedule" matches MEETING_SCHEDULE
        # "product" matches PRODUCT_INFO
        # Should prioritize MEETING_SCHEDULE if it comes first in priority
        query = "Can you schedule a demo of your product?"
        result = classifier.classify_intent(query)
        # This should match MEETING_SCHEDULE since "schedule" and "demo" are in that pattern
        assert result == SalesIntent.MEETING_SCHEDULE

    def test_partial_pattern_matching(self, classifier):
        """Test that patterns match within larger queries."""
        queries = [
            ("I was wondering if you could tell me about your company", SalesIntent.LEAD_QUALIFICATION),
            ("Would it be possible to book a quick meeting sometime?", SalesIntent.MEETING_SCHEDULE),
            ("Just curious, how much does this cost approximately?", SalesIntent.PRICING_INQUIRY),
            ("Sorry, but we're already have a solution in place", SalesIntent.OBJECTION),
        ]
        for query, expected_intent in queries:
            result = classifier.classify_intent(query)
            assert result == expected_intent, f"Failed for: {query}"
