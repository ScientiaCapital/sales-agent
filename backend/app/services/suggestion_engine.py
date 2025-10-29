"""
Real-time suggestion engine for sales conversations

Provides context-aware recommendations and triggers battle cards based on conversation flow.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from .cerebras import CerebrasService
from app.core.exceptions import MissingAPIKeyError

logger = logging.getLogger(__name__)


class SuggestionEngine:
    """
    Context-aware suggestion engine for real-time sales conversation assistance.

    Generates next-best-action recommendations and triggers battle cards based on
    conversation context, sentiment, and detected keywords/topics.
    """

    def __init__(self):
        """Initialize suggestion engine with Cerebras service."""
        # Initialize Cerebras service (optional - may fail if SDK not installed)
        try:
            self.cerebras = CerebrasService()
        except (ImportError, MissingAPIKeyError):
            self.cerebras = None
            logger.warning("CerebrasService unavailable. Suggestion features will be limited.")

        # Performance tracking
        self.total_suggestions_generated = 0
        self.total_latency_ms = 0

    async def generate_suggestions(
        self,
        current_text: str,
        speaker: str,
        conversation_history: List[Dict[str, Any]],
        sentiment_data: Optional[Dict[str, Any]] = None,
        lead_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate real-time suggestions for the sales agent.

        Args:
            current_text: Current conversation turn text
            speaker: Current speaker (agent or prospect)
            conversation_history: Recent conversation turns
            sentiment_data: Sentiment analysis of current turn
            lead_data: Lead/prospect information

        Returns:
            Dictionary containing:
            - suggestions: List of actionable suggestions
            - battle_card_triggers: List of triggered battle card keywords
            - detected_topics: Topics detected in current turn
            - urgency: Urgency level (low, medium, high)
            - latency_ms: Processing time
        """
        start_time = time.time()

        try:
            # Build context-aware prompt
            prompt = self._build_suggestion_prompt(
                current_text,
                speaker,
                conversation_history,
                sentiment_data,
                lead_data,
            )

            # Use Cerebras for fast suggestion generation
            response = self.cerebras.client.chat.completions.create(
                model=self.cerebras.default_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
                temperature=0.5,  # Balance creativity and consistency
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Parse response
            suggestion_text = response.choices[0].message.content
            result = self._parse_suggestion_response(suggestion_text)

            # Add metadata
            result["latency_ms"] = latency_ms
            result["timestamp"] = time.time()

            # Update metrics
            self.total_suggestions_generated += 1
            self.total_latency_ms += latency_ms

            logger.info(f"Generated {len(result['suggestions'])} suggestions in {latency_ms}ms")

            return result

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Suggestion generation failed after {latency_ms}ms: {e}")

            # Return empty suggestions on error
            return self._get_empty_result(latency_ms)

    def _build_suggestion_prompt(
        self,
        current_text: str,
        speaker: str,
        conversation_history: List[Dict[str, Any]],
        sentiment_data: Optional[Dict[str, Any]],
        lead_data: Optional[Dict[str, Any]],
    ) -> str:
        """Build prompt for suggestion generation."""
        prompt = f"""You are a sales conversation assistant. Provide real-time suggestions for the sales agent.

CURRENT MESSAGE ({speaker}): "{current_text}"
"""

        # Add conversation context
        if conversation_history:
            prompt += "\nRECENT CONVERSATION:\n"
            for turn in conversation_history[-5:]:  # Last 5 turns
                speaker_label = turn.get("speaker", "unknown")
                text = turn.get("text", "")
                prompt += f"{speaker_label}: {text}\n"

        # Add sentiment context
        if sentiment_data:
            sentiment = sentiment_data.get("sentiment", "neutral")
            score = sentiment_data.get("score", 0.0)
            emotions = sentiment_data.get("emotions", [])
            prompt += f"\nCURRENT SENTIMENT: {sentiment} (score: {score:.2f})"
            if emotions:
                prompt += f", emotions: {', '.join(emotions)}"
            if sentiment_data.get("is_objection"):
                prompt += " [OBJECTION DETECTED]"
            if sentiment_data.get("is_question"):
                prompt += " [QUESTION ASKED]"
            if sentiment_data.get("is_commitment"):
                prompt += " [BUYING SIGNAL]"

        # Add lead context
        if lead_data:
            prompt += f"\n\nLEAD INFO:"
            if lead_data.get("company_name"):
                prompt += f"\nCompany: {lead_data['company_name']}"
            if lead_data.get("industry"):
                prompt += f"\nIndustry: {lead_data['industry']}"
            if lead_data.get("company_size"):
                prompt += f"\nSize: {lead_data['company_size']}"

        prompt += """

Provide your response in this EXACT format:

SUGGESTIONS:
1. [First actionable suggestion]
2. [Second actionable suggestion]
3. [Third actionable suggestion]

BATTLE_CARDS: [comma-separated keywords: pricing, competitor, feature, security, integration, etc.]
TOPICS: [comma-separated topics detected]
URGENCY: [low/medium/high]

Focus on actionable next steps. Be concise."""

        return prompt

    def _parse_suggestion_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Cerebras response into structured suggestion data."""
        result = {
            "suggestions": [],
            "battle_card_triggers": [],
            "detected_topics": [],
            "urgency": "medium",
        }

        try:
            lines = response_text.strip().split('\n')
            current_section = None

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("SUGGESTIONS:"):
                    current_section = "suggestions"
                    continue

                elif line.startswith("BATTLE_CARDS:"):
                    current_section = "battle_cards"
                    battle_cards_str = line.split(":", 1)[1].strip()
                    if battle_cards_str and battle_cards_str.lower() not in ["none", "n/a", "-"]:
                        result["battle_card_triggers"] = [bc.strip() for bc in battle_cards_str.split(",") if bc.strip()]
                    continue

                elif line.startswith("TOPICS:"):
                    current_section = "topics"
                    topics_str = line.split(":", 1)[1].strip()
                    if topics_str and topics_str.lower() not in ["none", "n/a", "-"]:
                        result["detected_topics"] = [t.strip() for t in topics_str.split(",") if t.strip()]
                    continue

                elif line.startswith("URGENCY:"):
                    urgency = line.split(":", 1)[1].strip().lower()
                    if urgency in ["low", "medium", "high"]:
                        result["urgency"] = urgency
                    continue

                # Parse content based on current section
                if current_section == "suggestions":
                    # Extract numbered suggestions
                    if line[0].isdigit() and '.' in line[:3]:
                        suggestion = line.split('.', 1)[1].strip()
                        if suggestion:
                            result["suggestions"].append(suggestion)

        except Exception as e:
            logger.error(f"Error parsing suggestion response: {e}")

        # Ensure at least one suggestion
        if not result["suggestions"]:
            result["suggestions"] = ["Continue building rapport and asking discovery questions"]

        return result

    def _get_empty_result(self, latency_ms: int) -> Dict[str, Any]:
        """Get empty result (fallback)."""
        return {
            "suggestions": ["Continue the conversation naturally"],
            "battle_card_triggers": [],
            "detected_topics": [],
            "urgency": "low",
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        }

    def detect_battle_card_triggers(
        self,
        text: str,
        sentiment_data: Optional[Dict[str, Any]] = None,
    ) -> List[str]:
        """
        Detect keywords that should trigger battle cards.

        Uses pattern matching for fast keyword detection.

        Args:
            text: Text to analyze
            sentiment_data: Optional sentiment data for context

        Returns:
            List of triggered battle card keywords
        """
        text_lower = text.lower()
        triggers = []

        # Pricing triggers
        pricing_keywords = ["price", "cost", "expensive", "budget", "afford", "discount", "pricing"]
        if any(keyword in text_lower for keyword in pricing_keywords):
            triggers.append("pricing")

        # Competitor triggers
        competitor_keywords = ["competitor", "alternative", "other options", "vs", "versus", "comparison"]
        if any(keyword in text_lower for keyword in competitor_keywords):
            triggers.append("competitor")

        # Feature triggers
        feature_keywords = ["feature", "functionality", "capability", "can it", "does it support"]
        if any(keyword in text_lower for keyword in feature_keywords):
            triggers.append("feature")

        # Security triggers
        security_keywords = ["security", "secure", "encryption", "compliance", "gdpr", "hipaa", "soc2"]
        if any(keyword in text_lower for keyword in security_keywords):
            triggers.append("security")

        # Integration triggers
        integration_keywords = ["integrate", "integration", "api", "connect", "sync"]
        if any(keyword in text_lower for keyword in integration_keywords):
            triggers.append("integration")

        # Objection triggers (based on sentiment)
        if sentiment_data and sentiment_data.get("is_objection"):
            if "objection" not in triggers:
                triggers.append("objection")

        return triggers

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        if self.total_suggestions_generated == 0:
            return {
                "total_suggestions_generated": 0,
                "average_latency_ms": 0,
            }

        return {
            "total_suggestions_generated": self.total_suggestions_generated,
            "average_latency_ms": self.total_latency_ms // self.total_suggestions_generated,
        }

    def reset_metrics(self):
        """Reset performance metrics."""
        self.total_suggestions_generated = 0
        self.total_latency_ms = 0
        logger.info("Suggestion engine metrics reset")


# Global instance
_suggestion_engine = None


def get_suggestion_engine() -> SuggestionEngine:
    """Get or create global suggestion engine instance."""
    global _suggestion_engine
    if _suggestion_engine is None:
        _suggestion_engine = SuggestionEngine()
    return _suggestion_engine
