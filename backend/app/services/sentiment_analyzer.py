"""
Real-time sentiment analysis service using Cerebras AI

Analyzes conversation turns for sentiment, emotions, and engagement signals.
"""

import logging
import time
from typing import Dict, Any, List, Optional
from .cerebras import CerebrasService
from app.core.exceptions import MissingAPIKeyError

logger = logging.getLogger(__name__)


class SentimentAnalyzer:
    """
    Fast sentiment analysis using Cerebras for real-time conversation intelligence.

    Provides sentiment classification, emotion detection, and engagement scoring.
    """

    def __init__(self):
        """Initialize sentiment analyzer with Cerebras service."""
        # Initialize Cerebras service (optional - may fail if SDK not installed)
        try:
            self.cerebras = CerebrasService()
        except (ImportError, MissingAPIKeyError):
            self.cerebras = None
            logger.warning("CerebrasService unavailable. Sentiment analysis features will be limited.")

        # Performance tracking
        self.total_analyses = 0
        self.total_latency_ms = 0

    async def analyze_sentiment(
        self,
        text: str,
        speaker: str = "prospect",
        context: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        Analyze sentiment of a conversation turn.

        Args:
            text: Text to analyze
            speaker: Speaker role (agent or prospect)
            context: Optional list of previous messages for context

        Returns:
            Dictionary containing:
            - sentiment: Classification (positive, negative, neutral, mixed)
            - score: Sentiment score (-1.0 to 1.0)
            - confidence: Confidence in classification (0.0 to 1.0)
            - emotions: List of detected emotions
            - is_objection: Whether text contains an objection
            - is_question: Whether text is a question
            - is_commitment: Whether text signals buying intent
            - engagement_level: Engagement score (0.0 to 1.0)
            - latency_ms: Processing time
        """
        start_time = time.time()

        try:
            # Build prompt for sentiment analysis
            prompt = self._build_sentiment_prompt(text, speaker, context)

            # Use Cerebras for fast inference
            response = self.cerebras.client.chat.completions.create(
                model=self.cerebras.default_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=300,
                temperature=0.3,  # Lower temp for more consistent analysis
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Parse response
            analysis_text = response.choices[0].message.content
            result = self._parse_sentiment_response(analysis_text)

            # Add metadata
            result["latency_ms"] = latency_ms
            result["timestamp"] = time.time()

            # Update metrics
            self.total_analyses += 1
            self.total_latency_ms += latency_ms

            logger.info(f"Sentiment analysis completed: {result['sentiment']} ({result['score']:.2f}) in {latency_ms}ms")

            return result

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Sentiment analysis failed after {latency_ms}ms: {e}")

            # Return neutral result on error
            return self._get_neutral_result(latency_ms)

    def _build_sentiment_prompt(
        self,
        text: str,
        speaker: str,
        context: Optional[List[str]] = None,
    ) -> str:
        """Build prompt for sentiment analysis."""
        prompt = f"""Analyze the sentiment and characteristics of this {speaker}'s message in a sales conversation.

Message: "{text}"
"""

        if context:
            prompt += f"\nPrevious context:\n" + "\n".join(f"- {msg}" for msg in context[-3:])

        prompt += """

Provide your analysis in this EXACT format:
SENTIMENT: [positive/negative/neutral/mixed]
SCORE: [number from -1.0 to 1.0]
CONFIDENCE: [number from 0.0 to 1.0]
EMOTIONS: [comma-separated list: excited, interested, skeptical, frustrated, confused, satisfied, etc.]
IS_OBJECTION: [yes/no]
IS_QUESTION: [yes/no]
IS_COMMITMENT: [yes/no]
ENGAGEMENT: [number from 0.0 to 1.0]

Be concise and accurate."""

        return prompt

    def _parse_sentiment_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Cerebras response into structured sentiment data."""
        result = {
            "sentiment": "neutral",
            "score": 0.0,
            "confidence": 0.5,
            "emotions": [],
            "is_objection": False,
            "is_question": False,
            "is_commitment": False,
            "engagement_level": 0.5,
        }

        try:
            lines = response_text.strip().split('\n')

            for line in lines:
                line = line.strip()
                if not line:
                    continue

                if line.startswith("SENTIMENT:"):
                    sentiment = line.split(":", 1)[1].strip().lower()
                    if sentiment in ["positive", "negative", "neutral", "mixed"]:
                        result["sentiment"] = sentiment

                elif line.startswith("SCORE:"):
                    try:
                        score = float(line.split(":", 1)[1].strip())
                        result["score"] = max(-1.0, min(1.0, score))
                    except ValueError:
                        pass

                elif line.startswith("CONFIDENCE:"):
                    try:
                        confidence = float(line.split(":", 1)[1].strip())
                        result["confidence"] = max(0.0, min(1.0, confidence))
                    except ValueError:
                        pass

                elif line.startswith("EMOTIONS:"):
                    emotions_str = line.split(":", 1)[1].strip()
                    result["emotions"] = [e.strip() for e in emotions_str.split(",") if e.strip()]

                elif line.startswith("IS_OBJECTION:"):
                    result["is_objection"] = "yes" in line.lower()

                elif line.startswith("IS_QUESTION:"):
                    result["is_question"] = "yes" in line.lower() or "?" in line

                elif line.startswith("IS_COMMITMENT:"):
                    result["is_commitment"] = "yes" in line.lower()

                elif line.startswith("ENGAGEMENT:"):
                    try:
                        engagement = float(line.split(":", 1)[1].strip())
                        result["engagement_level"] = max(0.0, min(1.0, engagement))
                    except ValueError:
                        pass

        except Exception as e:
            logger.error(f"Error parsing sentiment response: {e}")

        return result

    def _get_neutral_result(self, latency_ms: int) -> Dict[str, Any]:
        """Get neutral sentiment result (fallback)."""
        return {
            "sentiment": "neutral",
            "score": 0.0,
            "confidence": 0.0,
            "emotions": [],
            "is_objection": False,
            "is_question": False,
            "is_commitment": False,
            "engagement_level": 0.5,
            "latency_ms": latency_ms,
            "timestamp": time.time(),
        }

    async def analyze_conversation_trend(
        self,
        turns: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze sentiment trend across multiple conversation turns.

        Args:
            turns: List of conversation turns with sentiment data

        Returns:
            Dictionary with trend analysis:
            - trend: improving, declining, stable
            - average_score: Average sentiment score
            - volatility: Standard deviation of scores
            - overall_sentiment: Overall conversation sentiment
        """
        if not turns:
            return {
                "trend": "stable",
                "average_score": 0.0,
                "volatility": 0.0,
                "overall_sentiment": "neutral",
            }

        scores = [turn.get("sentiment_score", 0.0) for turn in turns if "sentiment_score" in turn]

        if not scores:
            return {
                "trend": "stable",
                "average_score": 0.0,
                "volatility": 0.0,
                "overall_sentiment": "neutral",
            }

        average_score = sum(scores) / len(scores)

        # Calculate trend (compare first half vs second half)
        if len(scores) >= 4:
            mid = len(scores) // 2
            first_half_avg = sum(scores[:mid]) / mid
            second_half_avg = sum(scores[mid:]) / (len(scores) - mid)

            diff = second_half_avg - first_half_avg

            if diff > 0.2:
                trend = "improving"
            elif diff < -0.2:
                trend = "declining"
            else:
                trend = "stable"
        else:
            trend = "stable"

        # Calculate volatility (standard deviation)
        if len(scores) > 1:
            variance = sum((s - average_score) ** 2 for s in scores) / len(scores)
            volatility = variance ** 0.5
        else:
            volatility = 0.0

        # Determine overall sentiment
        if average_score > 0.3:
            overall_sentiment = "positive"
        elif average_score < -0.3:
            overall_sentiment = "negative"
        else:
            overall_sentiment = "neutral"

        return {
            "trend": trend,
            "average_score": round(average_score, 2),
            "volatility": round(volatility, 2),
            "overall_sentiment": overall_sentiment,
            "num_turns_analyzed": len(scores),
        }

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        if self.total_analyses == 0:
            return {
                "total_analyses": 0,
                "average_latency_ms": 0,
            }

        return {
            "total_analyses": self.total_analyses,
            "average_latency_ms": self.total_latency_ms // self.total_analyses,
        }

    def reset_metrics(self):
        """Reset performance metrics."""
        self.total_analyses = 0
        self.total_latency_ms = 0
        logger.info("Sentiment analyzer metrics reset")


# Global instance
_sentiment_analyzer = None


def get_sentiment_analyzer() -> SentimentAnalyzer:
    """Get or create global sentiment analyzer instance."""
    global _sentiment_analyzer
    if _sentiment_analyzer is None:
        _sentiment_analyzer = SentimentAnalyzer()
    return _sentiment_analyzer
