"""Example usage of SalesIntentClassifier.

This script demonstrates how to use the SalesIntentClassifier
for routing voice queries to appropriate handlers.
"""

from intent_classifier import SalesIntent, SalesIntentClassifier


def main():
    """Demonstrate SalesIntentClassifier usage."""
    classifier = SalesIntentClassifier()

    # Example queries for each intent type
    example_queries = [
        # Lead qualification
        "Hi, tell me about your company",
        "What do you do?",
        "Can you explain what type of business you're in?",

        # Meeting scheduling
        "Can we book a demo?",
        "I'd like to schedule a call",
        "What times are you available for a meeting?",

        # Product information
        "What does your product do?",
        "Tell me about your service offerings",
        "How does your solution work?",

        # Pricing inquiries
        "How much does it cost?",
        "What's your pricing model?",
        "Can you send me pricing information?",

        # Warm transfer requests
        "Can I speak to someone?",
        "Transfer me to a human representative",
        "I'd like to talk to your manager",

        # Objections
        "Not interested, thanks",
        "This is too expensive for us",
        "We already have a solution in place",
        "I'm too busy right now",

        # General queries
        "Hello there",
        "How are you doing today?",
        "What's the weather like?",
    ]

    print("=" * 80)
    print("SalesIntentClassifier Example Usage")
    print("=" * 80)
    print()

    for query in example_queries:
        intent = classifier.classify_intent(query)
        print(f"Query: {query}")
        print(f"Intent: {intent.value} ({intent.name})")
        print(f"Handler: {get_handler_name(intent)}")
        print("-" * 80)
        print()


def get_handler_name(intent: SalesIntent) -> str:
    """Map intent to handler name for demonstration purposes.

    Args:
        intent: The classified SalesIntent

    Returns:
        Handler name for the intent
    """
    handler_map = {
        SalesIntent.LEAD_QUALIFICATION: "LeadQualificationHandler",
        SalesIntent.MEETING_SCHEDULE: "MeetingScheduleHandler",
        SalesIntent.PRODUCT_INFO: "ProductInfoHandler",
        SalesIntent.PRICING_INQUIRY: "PricingHandler",
        SalesIntent.WARM_TRANSFER: "WarmTransferHandler",
        SalesIntent.OBJECTION: "ObjectionHandler",
        SalesIntent.GENERAL: "GeneralConversationHandler",
    }
    return handler_map.get(intent, "UnknownHandler")


if __name__ == "__main__":
    main()
