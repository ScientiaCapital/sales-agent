"""
Reply Classification Service

Classifies incoming email replies using AI to determine intent and sentiment.

Classifications:
- Interested: Positive response, wants more info
- Not Interested: Explicit rejection
- Out of Office: Auto-reply
- Meeting Request: Wants to schedule a call
- Question: Has questions, needs clarification
- Unsubscribe: Wants to be removed
- Spam/Auto-reply: Automated response

AI Provider: Claude (Anthropic) - NOT OpenAI per project rules
Fallback: Heuristic pattern matching when AI unavailable
"""

import os
import logging
from enum import Enum
from typing import Optional
from pydantic import BaseModel

# Anthropic client for Claude-based classification
try:
    from anthropic import AsyncAnthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

logger = logging.getLogger(__name__)


class ReplyIntent(str, Enum):
    """Reply intent classification."""
    INTERESTED = "interested"
    NOT_INTERESTED = "not_interested"
    OUT_OF_OFFICE = "out_of_office"
    MEETING_REQUEST = "meeting_request"
    QUESTION = "question"
    UNSUBSCRIBE = "unsubscribe"
    AUTO_REPLY = "auto_reply"
    UNKNOWN = "unknown"


class ReplySentiment(str, Enum):
    """Reply sentiment."""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class ReplyClassification(BaseModel):
    """Classification result for an email reply."""
    intent: ReplyIntent
    sentiment: ReplySentiment
    confidence: float
    reasoning: Optional[str] = None
    requires_human_review: bool = False


class ReplyClassifier:
    """
    Classifies email replies to determine intent and next action.

    Uses Claude AI to analyze email content and classify the response type.
    Falls back to heuristics if AI unavailable.
    """

    # Claude classification prompt
    CLASSIFICATION_PROMPT = """You are an email reply classifier for a B2B sales system.
Analyze the email below and classify the intent and sentiment.

INTENTS (choose one):
- interested: Prospect shows interest, wants more info, positive response
- not_interested: Explicit rejection, decline, not a fit
- out_of_office: Auto-reply indicating absence (vacation, leave, away)
- meeting_request: Wants to schedule a call/meeting
- question: Has questions, needs clarification before deciding
- unsubscribe: Requests removal from mailing list, do-not-contact
- auto_reply: Automated response (not OOO), delivery confirmation, etc.
- unknown: Cannot determine intent with confidence

SENTIMENTS:
- positive: Favorable, encouraging, interested tone
- neutral: Informational, neither positive nor negative
- negative: Unfavorable, annoyed, dismissive tone

Respond in this exact JSON format (no markdown, just JSON):
{{"intent": "string", "sentiment": "string", "confidence": 0.0-1.0, "reasoning": "why"}}

EMAIL SUBJECT: {subject}

EMAIL BODY:
{body}

JSON RESPONSE:"""

    def __init__(self, use_ai: bool = True):
        """
        Initialize reply classifier.

        Args:
            use_ai: Whether to use Claude AI for classification (default: True)
        """
        self.logger = logging.getLogger(f"{__name__}.ReplyClassifier")
        self.use_ai = use_ai and ANTHROPIC_AVAILABLE
        self.anthropic_client = None

        # Initialize Anthropic client if available
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if self.use_ai and api_key:
            self.anthropic_client = AsyncAnthropic(api_key=api_key)
            self.logger.info("ReplyClassifier initialized with Claude AI")
        else:
            self.logger.warning(
                f"ReplyClassifier using heuristics (AI={ANTHROPIC_AVAILABLE}, "
                f"key={'set' if api_key else 'missing'})"
            )

    async def classify(
        self,
        subject: str,
        body_text: str,
        body_html: Optional[str] = None,
        from_email: Optional[str] = None
    ) -> ReplyClassification:
        """
        Classify an email reply.

        Args:
            subject: Email subject line
            body_text: Plain text body
            body_html: HTML body (optional)
            from_email: Sender email address

        Returns:
            Classification result with intent and sentiment
        """
        self.logger.info(f"Classifying reply from {from_email}: {subject}")

        # Try Claude AI classification first (if available)
        if self.anthropic_client:
            ai_result = await self._classify_with_claude(subject, body_text)
            if ai_result:
                return ai_result
            self.logger.warning("Claude failed, using heuristics")

        # Fallback to heuristics

        # Check for out-of-office patterns
        if self._is_out_of_office(subject, body_text):
            return ReplyClassification(
                intent=ReplyIntent.OUT_OF_OFFICE,
                sentiment=ReplySentiment.NEUTRAL,
                confidence=0.95,
                reasoning="Auto-reply detected with out-of-office pattern",
                requires_human_review=False
            )

        # Check for auto-reply patterns
        if self._is_auto_reply(subject, body_text):
            return ReplyClassification(
                intent=ReplyIntent.AUTO_REPLY,
                sentiment=ReplySentiment.NEUTRAL,
                confidence=0.90,
                reasoning="Auto-reply detected",
                requires_human_review=False
            )

        # Check for unsubscribe intent
        if self._is_unsubscribe(body_text):
            return ReplyClassification(
                intent=ReplyIntent.UNSUBSCRIBE,
                sentiment=ReplySentiment.NEGATIVE,
                confidence=0.95,
                reasoning="Unsubscribe request detected",
                requires_human_review=False
            )

        # Check for meeting request
        if self._is_meeting_request(body_text):
            return ReplyClassification(
                intent=ReplyIntent.MEETING_REQUEST,
                sentiment=ReplySentiment.POSITIVE,
                confidence=0.85,
                reasoning="Meeting request keywords detected",
                requires_human_review=True
            )

        # Check for positive interest
        if self._is_interested(body_text):
            return ReplyClassification(
                intent=ReplyIntent.INTERESTED,
                sentiment=ReplySentiment.POSITIVE,
                confidence=0.80,
                reasoning="Positive interest keywords detected",
                requires_human_review=True
            )

        # Check for explicit rejection
        if self._is_not_interested(body_text):
            return ReplyClassification(
                intent=ReplyIntent.NOT_INTERESTED,
                sentiment=ReplySentiment.NEGATIVE,
                confidence=0.85,
                reasoning="Rejection keywords detected",
                requires_human_review=False
            )

        # Default: unknown, requires review
        return ReplyClassification(
            intent=ReplyIntent.UNKNOWN,
            sentiment=ReplySentiment.NEUTRAL,
            confidence=0.50,
            reasoning="Could not classify with confidence",
            requires_human_review=True
        )

    def _is_out_of_office(self, subject: str, body: str) -> bool:
        """Check if reply is an out-of-office auto-reply."""
        ooo_patterns = [
            "out of office",
            "out of the office",
            "automatic reply",
            "away from my desk",
            "on vacation",
            "on leave",
            "currently away",
            "returning on",
        ]
        text = f"{subject} {body}".lower()
        return any(pattern in text for pattern in ooo_patterns)

    def _is_auto_reply(self, subject: str, body: str) -> bool:
        """Check if reply is an automated response."""
        auto_patterns = [
            "automatic response",
            "auto-reply",
            "autoreply",
            "this is an automated",
            "do not reply to this",
            "noreply@",
        ]
        text = f"{subject} {body}".lower()
        return any(pattern in text for pattern in auto_patterns)

    def _is_unsubscribe(self, body: str) -> bool:
        """Check if reply is an unsubscribe request."""
        unsub_patterns = [
            "unsubscribe",
            "remove me",
            "take me off",
            "stop emailing",
            "don't email me",
            "do not contact",
            "cease and desist",
        ]
        text = body.lower()
        return any(pattern in text for pattern in unsub_patterns)

    def _is_meeting_request(self, body: str) -> bool:
        """Check if reply requests a meeting."""
        meeting_patterns = [
            "schedule a call",
            "schedule a meeting",
            "let's talk",
            "set up a time",
            "calendar link",
            "when are you available",
            "book a call",
            "calendly",
        ]
        text = body.lower()
        return any(pattern in text for pattern in meeting_patterns)

    def _is_interested(self, body: str) -> bool:
        """Check if reply shows interest."""
        interest_patterns = [
            "interested",
            "tell me more",
            "more information",
            "sounds good",
            "looks interesting",
            "would like to know",
            "can you share",
            "send me",
        ]
        text = body.lower()
        return any(pattern in text for pattern in interest_patterns)

    def _is_not_interested(self, body: str) -> bool:
        """Check if reply is a rejection."""
        reject_patterns = [
            "not interested",
            "no thank you",
            "not a good fit",
            "not right now",
            "already have",
            "we're all set",
            "pass on this",
            "decline",
        ]
        text = body.lower()
        return any(pattern in text for pattern in reject_patterns)

    async def _classify_with_claude(
        self,
        subject: str,
        body_text: str
    ) -> Optional[ReplyClassification]:
        """
        Classify email reply using Claude AI.

        Args:
            subject: Email subject line
            body_text: Plain text email body

        Returns:
            Classification result or None if AI classification fails
        """
        import json

        try:
            # Build prompt with email content
            prompt = self.CLASSIFICATION_PROMPT.format(
                subject=subject[:200],  # Truncate subject
                body=body_text[:2000]   # Truncate body to avoid token limits
            )

            # Call Claude API (using haiku for cost efficiency)
            response = await self.anthropic_client.messages.create(
                model="claude-3-haiku-20240307",  # Fast + cheap for classification
                max_tokens=256,
                temperature=0.0,  # Deterministic for classification
                messages=[{"role": "user", "content": prompt}]
            )

            # Parse JSON response
            response_text = response.content[0].text.strip()
            self.logger.debug(f"Claude raw response: {response_text}")

            # Handle potential markdown wrapping
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
                response_text = response_text.strip()

            result = json.loads(response_text)

            # Map to enum values
            intent_map = {
                "interested": ReplyIntent.INTERESTED,
                "not_interested": ReplyIntent.NOT_INTERESTED,
                "out_of_office": ReplyIntent.OUT_OF_OFFICE,
                "meeting_request": ReplyIntent.MEETING_REQUEST,
                "question": ReplyIntent.QUESTION,
                "unsubscribe": ReplyIntent.UNSUBSCRIBE,
                "auto_reply": ReplyIntent.AUTO_REPLY,
                "unknown": ReplyIntent.UNKNOWN,
            }

            sentiment_map = {
                "positive": ReplySentiment.POSITIVE,
                "neutral": ReplySentiment.NEUTRAL,
                "negative": ReplySentiment.NEGATIVE,
            }

            raw_intent = result.get("intent", "unknown")
            raw_sentiment = result.get("sentiment", "neutral")
            intent = intent_map.get(raw_intent, ReplyIntent.UNKNOWN)
            sentiment = sentiment_map.get(raw_sentiment, ReplySentiment.NEUTRAL)
            confidence = float(result.get("confidence", 0.7))
            reasoning = result.get("reasoning", "AI classification")

            # Determine if human review needed based on intent/confidence
            hot_intents = [
                ReplyIntent.INTERESTED,
                ReplyIntent.MEETING_REQUEST,
                ReplyIntent.QUESTION
            ]
            requires_human_review = intent in hot_intents or confidence < 0.7

            self.logger.info(
                f"Claude classified reply: intent={intent.value}, "
                f"sentiment={sentiment.value}, confidence={confidence:.2f}"
            )

            return ReplyClassification(
                intent=intent,
                sentiment=sentiment,
                confidence=confidence,
                reasoning=f"[AI] {reasoning}",
                requires_human_review=requires_human_review
            )

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse Claude JSON response: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Claude classification error: {e}")
            return None


__all__ = ["ReplyClassifier", "ReplyClassification", "ReplyIntent", "ReplySentiment"]
