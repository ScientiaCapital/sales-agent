# Voice Intent Classification

Pattern-based intent classification for sales voice routing. No ML/LLM required.

## Overview

The `SalesIntentClassifier` uses keyword matching to classify user voice queries into sales intent categories, enabling smart routing to appropriate handlers.

## Features

- **Fast & Deterministic**: Pattern-based matching (no ML/LLM overhead)
- **7 Intent Types**: Lead qualification, meeting scheduling, product info, pricing, warm transfer, objections, and general
- **Priority-Based Matching**: When multiple patterns match, highest priority intent wins
- **Case-Insensitive**: Works with any capitalization
- **Whitespace Tolerant**: Handles extra spaces and newlines
- **Zero Dependencies**: Only uses Python standard library (enum, typing)

## Intent Types

### SalesIntent Enum

```python
class SalesIntent(str, Enum):
    LEAD_QUALIFICATION = "lead_qualification"  # "Tell me about your company"
    MEETING_SCHEDULE = "meeting_schedule"      # "Book a demo", "Schedule a call"
    PRODUCT_INFO = "product_info"              # "What does your product do?"
    PRICING_INQUIRY = "pricing_inquiry"        # "How much does it cost?"
    WARM_TRANSFER = "warm_transfer"            # "Can I speak to someone?"
    OBJECTION = "objection"                    # "Not interested", "Too expensive"
    GENERAL = "general"                        # Everything else (fallback)
```

## Priority Order

When multiple patterns match, intents are prioritized in this order:

1. **OBJECTION** (highest priority) - Handle objections first
2. **WARM_TRANSFER** - Customer wants human interaction
3. **MEETING_SCHEDULE** - Booking intent is strong signal
4. **PRICING_INQUIRY** - Pricing questions are important
5. **LEAD_QUALIFICATION** - Understanding customer
6. **PRODUCT_INFO** - General product questions
7. **GENERAL** (fallback) - Default for unmatched queries

## Usage

### Basic Classification

```python
from app.services.voice.intent_classifier import SalesIntent, SalesIntentClassifier

classifier = SalesIntentClassifier()

# Example queries
intent = classifier.classify_intent("Can we schedule a demo?")
print(intent)  # SalesIntent.MEETING_SCHEDULE

intent = classifier.classify_intent("How much does it cost?")
print(intent)  # SalesIntent.PRICING_INQUIRY

intent = classifier.classify_intent("Not interested")
print(intent)  # SalesIntent.OBJECTION
```

### Voice Routing Example

```python
from app.services.voice.intent_classifier import SalesIntent, SalesIntentClassifier

class VoiceRouter:
    def __init__(self):
        self.classifier = SalesIntentClassifier()
        self.handlers = {
            SalesIntent.LEAD_QUALIFICATION: self.handle_lead_qualification,
            SalesIntent.MEETING_SCHEDULE: self.handle_meeting_schedule,
            SalesIntent.PRODUCT_INFO: self.handle_product_info,
            SalesIntent.PRICING_INQUIRY: self.handle_pricing,
            SalesIntent.WARM_TRANSFER: self.handle_warm_transfer,
            SalesIntent.OBJECTION: self.handle_objection,
            SalesIntent.GENERAL: self.handle_general,
        }

    def route_query(self, query: str):
        intent = self.classifier.classify_intent(query)
        handler = self.handlers.get(intent)
        return handler(query) if handler else self.handle_general(query)

    def handle_lead_qualification(self, query: str):
        return "Let me tell you about our company..."

    def handle_meeting_schedule(self, query: str):
        return "I'd be happy to schedule a meeting. What time works for you?"

    # ... other handlers
```

## Pattern Matching Details

### Lead Qualification Patterns
- "tell me about your company"
- "what do you do"
- "who are you"
- "what's your role"
- "company name"
- "business"

### Meeting Schedule Patterns
- "book", "schedule", "meeting"
- "call", "demo", "appointment"
- "what times", "calendar", "availability"

### Product Info Patterns
- "product", "service", "features"
- "what do you offer"
- "how does it work"
- "tell me more"

### Pricing Inquiry Patterns
- "price", "cost", "how much"
- "pricing", "budget", "afford"

### Warm Transfer Patterns
- "speak to someone", "transfer"
- "human", "representative"
- "talk to a person", "manager"

### Objection Patterns
- "not interested", "no thanks"
- "too expensive", "already have"
- "don't need", "busy"
- "call back later"

## Testing

Run the comprehensive test suite:

```bash
cd backend
python3 -m pytest tests/services/voice/test_intent_classifier.py -v
```

### Test Coverage

The test suite includes:
- ✅ Enum value validation
- ✅ Each intent type classification
- ✅ Empty/unknown query handling
- ✅ Case-insensitivity
- ✅ Whitespace handling
- ✅ Intent priority order
- ✅ Partial pattern matching

All 14 tests pass with 100% coverage.

## Example Output

Run the example script to see the classifier in action:

```bash
cd backend/app/services/voice
python3 example_usage.py
```

Example output:
```
Query: Can we book a demo?
Intent: meeting_schedule (MEETING_SCHEDULE)
Handler: MeetingScheduleHandler

Query: How much does it cost?
Intent: pricing_inquiry (PRICING_INQUIRY)
Handler: PricingHandler

Query: Not interested, thanks
Intent: objection (OBJECTION)
Handler: ObjectionHandler
```

## Design Principles

1. **TDD Approach**: Tests written first, implementation follows
2. **No External Dependencies**: Uses only Python standard library
3. **No API Keys Required**: Pattern-based, not ML/LLM-based
4. **Fast**: O(n*m) complexity where n=patterns, m=query length
5. **Deterministic**: Same input always produces same output
6. **Extensible**: Easy to add new patterns or intents

## Adding New Patterns

To add new patterns to an existing intent:

```python
# In intent_classifier.py
SALES_INTENT_PATTERNS = {
    SalesIntent.MEETING_SCHEDULE: [
        "book",
        "schedule",
        # Add your new pattern here
        "set up a time",
    ],
    # ... other intents
}
```

To add a new intent type:

1. Add to `SalesIntent` enum
2. Add patterns to `SALES_INTENT_PATTERNS`
3. Add to `INTENT_PRIORITY` list (if not using GENERAL)
4. Write tests for the new intent

## Performance

- **Initialization**: O(1) - instant
- **Classification**: O(n*m) where n=total patterns, m=query length
- **Memory**: Minimal - just pattern strings in memory

For a typical query with ~50 total patterns and 10-word query:
- Classification time: <0.001 seconds
- Memory usage: <1KB

## Future Enhancements

Potential improvements (without breaking TDD/pattern-based approach):

1. **Fuzzy Matching**: Levenshtein distance for typo tolerance
2. **Multi-Intent Detection**: Return top N intents with confidence scores
3. **Context Awareness**: Track conversation state for better routing
4. **Analytics**: Log intent distribution for pattern optimization
5. **Dynamic Patterns**: Load patterns from configuration file

## Files

- `intent_classifier.py` - Core implementation
- `test_intent_classifier.py` - Test suite (14 tests)
- `example_usage.py` - Demonstration script
- `README.md` - This file

## License

Part of the sales-agent project. See main project README for license details.
