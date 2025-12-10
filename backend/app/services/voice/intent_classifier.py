"""Sales intent classification for voice routing.

This module provides pattern-based intent classification for sales voice queries.
No ML/LLM required - uses simple keyword matching.
"""

from enum import Enum
from typing import Dict, List


class SalesIntent(str, Enum):
    """Sales intent types for voice routing."""

    LEAD_QUALIFICATION = "lead_qualification"
    MEETING_SCHEDULE = "meeting_schedule"
    PRODUCT_INFO = "product_info"
    PRICING_INQUIRY = "pricing_inquiry"
    WARM_TRANSFER = "warm_transfer"
    OBJECTION = "objection"
    GENERAL = "general"


# Define patterns for each intent type (excluding GENERAL which is the fallback)
SALES_INTENT_PATTERNS: Dict[SalesIntent, List[str]] = {
    SalesIntent.LEAD_QUALIFICATION: [
        "tell me about your company",
        "what do you do",
        "who are you",
        "what's your role",
        "company name",
        "business",
        "what type of business",
    ],
    SalesIntent.MEETING_SCHEDULE: [
        "book",
        "schedule",
        "meeting",
        "call",
        "demo",
        "appointment",
        "what times",
        "calendar",
        "availability",
        "set up",
    ],
    SalesIntent.PRODUCT_INFO: [
        "product",
        "service",
        "features",
        "what do you offer",
        "how does it work",
        "tell me more",
    ],
    SalesIntent.PRICING_INQUIRY: [
        "price",
        "cost",
        "how much",
        "pricing",
        "budget",
        "afford",
    ],
    SalesIntent.WARM_TRANSFER: [
        "speak to someone",
        "transfer",
        "human",
        "representative",
        "talk to a person",
        "manager",
    ],
    SalesIntent.OBJECTION: [
        "not interested",
        "no thanks",
        "too expensive",
        "already have",
        "don't need",
        "busy",
        "call back later",
    ],
}

# Define priority order for intent matching
# When multiple patterns match, the first one in this list wins
INTENT_PRIORITY: List[SalesIntent] = [
    SalesIntent.OBJECTION,  # Highest priority - need to handle objections first
    SalesIntent.WARM_TRANSFER,  # Second - customer wants human interaction
    SalesIntent.MEETING_SCHEDULE,  # Third - booking intent is strong signal
    SalesIntent.PRICING_INQUIRY,  # Fourth - pricing questions are important
    SalesIntent.LEAD_QUALIFICATION,  # Fifth - understanding customer
    SalesIntent.PRODUCT_INFO,  # Sixth - general product questions
]


class SalesIntentClassifier:
    """Pattern-based intent classifier for sales voice queries.

    Uses keyword matching to classify user queries into sales intent categories.
    No ML/LLM required - fast and deterministic.

    Example:
        >>> classifier = SalesIntentClassifier()
        >>> intent = classifier.classify_intent("Can we schedule a demo?")
        >>> print(intent)
        SalesIntent.MEETING_SCHEDULE
    """

    def __init__(self):
        """Initialize the intent classifier."""
        self.patterns = SALES_INTENT_PATTERNS
        self.priority = INTENT_PRIORITY

    def classify_intent(self, query: str) -> SalesIntent:
        """Classify a voice query into a sales intent category.

        Args:
            query: The user's voice query text

        Returns:
            The classified SalesIntent. Returns GENERAL if no patterns match.

        Examples:
            >>> classifier = SalesIntentClassifier()
            >>> classifier.classify_intent("Tell me about your company")
            SalesIntent.LEAD_QUALIFICATION

            >>> classifier.classify_intent("How much does it cost?")
            SalesIntent.PRICING_INQUIRY

            >>> classifier.classify_intent("Hello there")
            SalesIntent.GENERAL
        """
        # Normalize the query: lowercase and strip whitespace
        normalized = query.lower().strip()

        # Return GENERAL for empty queries
        if not normalized:
            return SalesIntent.GENERAL

        # Check each intent in priority order
        for intent in self.priority:
            patterns = self.patterns.get(intent, [])
            for pattern in patterns:
                if pattern in normalized:
                    return intent

        # Default fallback
        return SalesIntent.GENERAL
