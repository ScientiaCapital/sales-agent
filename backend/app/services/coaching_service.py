"""
Real-time Call Coaching Service

Provides <200ms coaching recommendations by combining suggestion engine
and battle card retrieval for live sales calls.
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from sqlalchemy.orm import Session

from app.services.suggestion_engine import get_suggestion_engine
from app.services.battle_card_service import BattleCardService

logger = logging.getLogger(__name__)


@dataclass
class CoachingResult:
    """Real-time coaching response container."""
    suggestions: List[str] = field(default_factory=list)
    battle_cards: List[Dict[str, Any]] = field(default_factory=list)
    detected_topics: List[str] = field(default_factory=list)
    urgency: str = "medium"
    latency_ms: int = 0
    timestamp: float = 0.0


class CoachingService:
    """
    Orchestrates real-time coaching for live sales calls.

    Combines suggestion engine (next-best-action) and battle cards
    (objection handling) with target latency <200ms.
    """

    def __init__(self, db: Session):
        """
        Initialize coaching service.

        Args:
            db: Database session for battle card lookups
        """
        self.suggestion_engine = get_suggestion_engine()
        self.battle_card_service = BattleCardService(db)
        self._total_calls = 0
        self._total_latency_ms = 0

    async def get_real_time_coaching(
        self,
        transcript: str,
        conversation_history: List[Dict[str, Any]],
        lead_context: Optional[Dict[str, Any]] = None,
        sentiment_data: Optional[Dict[str, Any]] = None,
    ) -> CoachingResult:
        """Generate real-time coaching with <200ms target latency."""
        start_time = time.perf_counter()

        try:
            # Run suggestion generation and keyword detection in parallel
            suggestions_task = asyncio.create_task(
                self._get_suggestions(
                    transcript,
                    conversation_history,
                    lead_context,
                    sentiment_data,
                )
            )

            trigger_keywords = self.suggestion_engine.detect_battle_card_triggers(
                transcript, sentiment_data
            )

            # Wait for suggestions
            suggestion_result = await suggestions_task

            # Get battle cards based on detected triggers
            battle_cards = self._get_battle_cards(
                transcript,
                suggestion_result.get("detected_topics", []),
                trigger_keywords,
            )

            latency_ms = int((time.perf_counter() - start_time) * 1000)

            # Update metrics
            self._total_calls += 1
            self._total_latency_ms += latency_ms

            result = CoachingResult(
                suggestions=suggestion_result.get("suggestions", []),
                battle_cards=battle_cards,
                detected_topics=suggestion_result.get("detected_topics", []),
                urgency=suggestion_result.get("urgency", "medium"),
                latency_ms=latency_ms,
                timestamp=time.time(),
            )

            logger.info(
                f"Coaching generated in {latency_ms}ms: "
                f"{len(result.suggestions)} suggestions, "
                f"{len(result.battle_cards)} battle cards"
            )

            return result

        except Exception as e:
            latency_ms = int((time.perf_counter() - start_time) * 1000)
            logger.error(f"Coaching generation failed after {latency_ms}ms: {e}")

            return CoachingResult(
                suggestions=["Continue the conversation naturally"],
                urgency="low",
                latency_ms=latency_ms,
                timestamp=time.time(),
            )

    async def _get_suggestions(
        self,
        transcript: str,
        conversation_history: List[Dict[str, Any]],
        lead_context: Optional[Dict[str, Any]],
        sentiment_data: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Get suggestions from the suggestion engine."""
        return await self.suggestion_engine.generate_suggestions(
            current_text=transcript,
            speaker="prospect",
            conversation_history=conversation_history,
            sentiment_data=sentiment_data,
            lead_data=lead_context,
        )

    def _get_battle_cards(
        self,
        transcript: str,
        detected_topics: List[str],
        trigger_keywords: List[str],
    ) -> List[Dict[str, Any]]:
        """Retrieve matching battle cards synchronously (fast lookup)."""
        try:
            templates = self.battle_card_service.find_matching_templates(
                text=transcript,
                detected_topics=detected_topics,
                trigger_keywords=trigger_keywords,
            )

            return [
                {
                    "id": str(template.id),
                    "type": template.card_type.value,
                    "title": template.title,
                    "content": template.content,
                    "talking_points": template.talking_points or [],
                    "response_template": template.response_template,
                }
                for template in templates
            ]

        except Exception as e:
            logger.error(f"Battle card retrieval failed: {e}")
            return []

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get coaching service performance metrics."""
        avg_latency = 0
        if self._total_calls > 0:
            avg_latency = self._total_latency_ms // self._total_calls

        return {
            "total_coaching_calls": self._total_calls,
            "average_latency_ms": avg_latency,
            "target_latency_ms": 200,
            "within_target": avg_latency <= 200,
        }


# Singleton pattern for service reuse
_coaching_services: Dict[int, CoachingService] = {}


def get_coaching_service(db: Session) -> CoachingService:
    """Get or create CoachingService for the database session."""
    session_id = id(db)
    if session_id not in _coaching_services:
        _coaching_services[session_id] = CoachingService(db)
    return _coaching_services[session_id]
