"""Voice routing integration example.

This example shows how to integrate SalesIntentClassifier
into a real voice routing system for sales calls.
"""

from typing import Dict, Callable, Any
from intent_classifier import SalesIntent, SalesIntentClassifier


class VoiceRouter:
    """Routes voice queries to appropriate handlers based on intent.

    Example usage in a sales voice agent:
        router = VoiceRouter()
        response = router.handle_query("Can we schedule a demo?")
    """

    def __init__(self):
        """Initialize the voice router."""
        self.classifier = SalesIntentClassifier()
        self.handlers: Dict[SalesIntent, Callable] = {
            SalesIntent.LEAD_QUALIFICATION: self._handle_lead_qualification,
            SalesIntent.MEETING_SCHEDULE: self._handle_meeting_schedule,
            SalesIntent.PRODUCT_INFO: self._handle_product_info,
            SalesIntent.PRICING_INQUIRY: self._handle_pricing_inquiry,
            SalesIntent.WARM_TRANSFER: self._handle_warm_transfer,
            SalesIntent.OBJECTION: self._handle_objection,
            SalesIntent.GENERAL: self._handle_general,
        }

    def handle_query(self, query: str) -> Dict[str, Any]:
        """Route a voice query to the appropriate handler.

        Args:
            query: The user's voice query text

        Returns:
            Dictionary containing:
                - intent: The classified intent
                - response: The handler's response
                - action: Recommended action (e.g., 'transfer', 'continue', 'schedule')
        """
        # Classify the intent
        intent = self.classifier.classify_intent(query)

        # Get the appropriate handler
        handler = self.handlers.get(intent, self._handle_general)

        # Execute the handler
        result = handler(query)

        return {
            "intent": intent.value,
            "response": result["response"],
            "action": result["action"],
            "metadata": result.get("metadata", {}),
        }

    def _handle_lead_qualification(self, query: str) -> Dict[str, Any]:
        """Handle lead qualification queries."""
        return {
            "response": (
                "Great question! We're a sales acceleration platform that helps "
                "B2B companies close more deals faster. We use AI to automate "
                "prospecting, qualify leads, and schedule meetings. "
                "Can I ask what brings you to us today?"
            ),
            "action": "continue",
            "metadata": {"requires_followup": True},
        }

    def _handle_meeting_schedule(self, query: str) -> Dict[str, Any]:
        """Handle meeting scheduling requests."""
        return {
            "response": (
                "I'd be happy to schedule a demo for you! "
                "I can see availability on Tuesday at 2pm or Thursday at 10am. "
                "Which time works better for you?"
            ),
            "action": "schedule",
            "metadata": {
                "calendar_check": True,
                "available_slots": ["2024-12-12T14:00:00", "2024-12-14T10:00:00"],
            },
        }

    def _handle_product_info(self, query: str) -> Dict[str, Any]:
        """Handle product information queries."""
        return {
            "response": (
                "Our platform has three main features: "
                "1) AI-powered lead scoring to identify your best opportunities, "
                "2) Automated outreach sequences via email and LinkedIn, "
                "3) Real-time analytics and coaching for your sales team. "
                "Which area interests you most?"
            ),
            "action": "continue",
            "metadata": {"send_product_sheet": True},
        }

    def _handle_pricing_inquiry(self, query: str) -> Dict[str, Any]:
        """Handle pricing questions."""
        return {
            "response": (
                "Our pricing is tailored to your team size and needs. "
                "We have plans starting at $500/month for small teams, "
                "and enterprise plans for larger organizations. "
                "To give you an accurate quote, can I ask how many "
                "sales reps you have?"
            ),
            "action": "continue",
            "metadata": {"qualification_needed": True},
        }

    def _handle_warm_transfer(self, query: str) -> Dict[str, Any]:
        """Handle warm transfer requests."""
        return {
            "response": (
                "Of course! I'll connect you with one of our sales specialists "
                "right away. Let me brief them on our conversation. "
                "Please hold for just a moment."
            ),
            "action": "transfer",
            "metadata": {
                "transfer_to": "sales_specialist",
                "priority": "high",
                "context_summary": "Customer requested human interaction",
            },
        }

    def _handle_objection(self, query: str) -> Dict[str, Any]:
        """Handle objections."""
        # Analyze the specific objection
        objection_type = self._identify_objection_type(query)

        responses = {
            "not_interested": (
                "I understand. Before you go, can I ask what specifically "
                "doesn't interest you? It helps us improve."
            ),
            "too_expensive": (
                "I appreciate your concern about cost. Many of our customers "
                "found that the ROI justified the investment. On average, they "
                "see a 3x return within 6 months. Would you like to see a case study?"
            ),
            "already_have": (
                "That's great that you have a solution in place! "
                "What we've found is that our platform integrates well with "
                "existing tools. Could I share how we complement what you're using?"
            ),
            "busy": (
                "I completely understand. When would be a better time to reach "
                "back out? I can send you some quick info via email in the meantime."
            ),
        }

        response = responses.get(
            objection_type,
            "I understand. Is there anything specific that would change your mind?"
        )

        return {
            "response": response,
            "action": "overcome_objection",
            "metadata": {
                "objection_type": objection_type,
                "followup_needed": True,
            },
        }

    def _handle_general(self, query: str) -> Dict[str, Any]:
        """Handle general queries."""
        return {
            "response": (
                "Thanks for reaching out! How can I help you today? "
                "I can tell you about our product, schedule a demo, "
                "or answer any questions you have."
            ),
            "action": "continue",
            "metadata": {},
        }

    def _identify_objection_type(self, query: str) -> str:
        """Identify specific objection type."""
        query_lower = query.lower()
        if "not interested" in query_lower or "no thanks" in query_lower:
            return "not_interested"
        elif "expensive" in query_lower or "cost" in query_lower:
            return "too_expensive"
        elif "already have" in query_lower or "already use" in query_lower:
            return "already_have"
        elif "busy" in query_lower or "call back" in query_lower:
            return "busy"
        return "general"


def demo():
    """Demonstrate the voice router in action."""
    router = VoiceRouter()

    print("=" * 80)
    print("Voice Router Integration Example")
    print("=" * 80)
    print()

    test_queries = [
        "Hi, can you tell me what your company does?",
        "I'd like to schedule a demo",
        "What features does your product have?",
        "How much does it cost?",
        "Can I speak to a sales representative?",
        "This is too expensive for us",
        "Actually, I'm not interested",
        "Hello, how are you?",
    ]

    for query in test_queries:
        print(f"Query: {query}")
        print("-" * 80)

        result = router.handle_query(query)

        print(f"Intent: {result['intent']}")
        print(f"Action: {result['action']}")
        print(f"Response: {result['response']}")

        if result["metadata"]:
            print(f"Metadata: {result['metadata']}")

        print()


if __name__ == "__main__":
    demo()
