"""
CallInsightsService - AI-powered call analysis orchestrator.

Wraps PostCallAnalyzer (AssemblyAI) and persists results to the
call_insights table. Provides methods for:
- Analyzing call recordings asynchronously
- Retrieving insights for calls/leads
- Calculating call quality scores
"""
import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from sqlalchemy.orm import selectinload

from app.models.call_insight import CallInsight, SentimentLabel, CallOutcome
from app.models.voice_models import VoiceSessionLog
from app.services.calling.analysis.post_call_analyzer import (
    PostCallAnalyzer, CallAnalysis, Sentiment
)

logger = logging.getLogger(__name__)

# Version for tracking analysis changes
ANALYZER_VERSION = "1.0.0"


class CallInsightsService:
    """
    Service for managing call intelligence data.

    Orchestrates:
    1. PostCallAnalyzer for transcription/analysis
    2. Database persistence of results
    3. Query methods for insights retrieval

    Usage:
        service = CallInsightsService(db_session)
        insight = await service.analyze_call(
            voice_session_id="vs_123",
            audio_url="https://recordings.twilio.com/..."
        )
    """

    def __init__(self, db: AsyncSession):
        """Initialize with async database session."""
        self.db = db
        self.analyzer = PostCallAnalyzer()

    async def analyze_call(
        self,
        voice_session_id: str,
        audio_url: str,
        lead_id: Optional[UUID] = None,
    ) -> Optional[CallInsight]:
        """
        Analyze a call recording and persist insights.

        Args:
            voice_session_id: Voice session ID from voice_session_logs
            audio_url: URL to the call recording (Twilio/storage)
            lead_id: Optional lead ID for linking

        Returns:
            CallInsight with analysis results, or None on failure
        """
        logger.info(f"Analyzing call {voice_session_id}")

        # Check if already analyzed
        existing = await self.get_insight_by_session(voice_session_id)
        if existing:
            logger.info(f"Call {voice_session_id} already analyzed")
            return existing

        # Get voice session for lead_id if not provided
        if not lead_id:
            session_result = await self.db.execute(
                select(VoiceSessionLog).where(
                    VoiceSessionLog.id == voice_session_id
                )
            )
            voice_session = session_result.scalar_one_or_none()
            if voice_session and voice_session.lead_id:
                lead_id = UUID(str(voice_session.lead_id))

        # Run analysis
        try:
            analysis = await self.analyzer.analyze_recording(
                audio_url=audio_url,
                call_sid=voice_session_id,
                lead_id=str(lead_id) if lead_id else "",
            )
        except Exception as e:
            logger.error(f"Analysis failed for {voice_session_id}: {e}")
            return None

        # Convert to CallInsight and persist
        insight = self._analysis_to_insight(analysis, voice_session_id, lead_id)

        self.db.add(insight)
        await self.db.commit()
        await self.db.refresh(insight)

        logger.info(f"Saved insight for {voice_session_id}: {insight.outcome}")
        return insight

    async def get_insight_by_session(
        self,
        voice_session_id: str
    ) -> Optional[CallInsight]:
        """Get insight by voice session ID."""
        result = await self.db.execute(
            select(CallInsight).where(
                CallInsight.voice_session_id == voice_session_id
            )
        )
        return result.scalar_one_or_none()

    async def get_insight_by_id(self, insight_id: UUID) -> Optional[CallInsight]:
        """Get insight by primary key."""
        result = await self.db.execute(
            select(CallInsight).where(CallInsight.id == insight_id)
        )
        return result.scalar_one_or_none()

    async def get_insights_for_lead(
        self,
        lead_id: UUID,
        limit: int = 50,
        offset: int = 0,
    ) -> List[CallInsight]:
        """Get all call insights for a lead."""
        result = await self.db.execute(
            select(CallInsight)
            .where(CallInsight.lead_id == lead_id)
            .order_by(CallInsight.analyzed_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_insights_by_outcome(
        self,
        outcome: str,
        limit: int = 100,
    ) -> List[CallInsight]:
        """Get insights filtered by outcome."""
        result = await self.db.execute(
            select(CallInsight)
            .where(CallInsight.outcome == outcome)
            .order_by(CallInsight.analyzed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_insights_by_sentiment(
        self,
        sentiment: str,
        limit: int = 100,
    ) -> List[CallInsight]:
        """Get insights filtered by sentiment."""
        result = await self.db.execute(
            select(CallInsight)
            .where(CallInsight.sentiment_label == sentiment)
            .order_by(CallInsight.analyzed_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def get_recent_insights(
        self,
        limit: int = 50,
        min_score: Optional[int] = None,
    ) -> List[CallInsight]:
        """Get recent insights, optionally filtered by score."""
        query = select(CallInsight).order_by(CallInsight.analyzed_at.desc())

        if min_score is not None:
            query = query.where(CallInsight.call_score >= min_score)

        result = await self.db.execute(query.limit(limit))
        return list(result.scalars().all())

    def _analysis_to_insight(
        self,
        analysis: CallAnalysis,
        voice_session_id: str,
        lead_id: Optional[UUID],
    ) -> CallInsight:
        """Convert PostCallAnalyzer result to CallInsight model."""
        # Calculate call score (0-100)
        call_score = self._calculate_call_score(analysis)

        # Map sentiment
        sentiment_map = {
            Sentiment.POSITIVE: SentimentLabel.POSITIVE.value,
            Sentiment.NEGATIVE: SentimentLabel.NEGATIVE.value,
            Sentiment.NEUTRAL: SentimentLabel.NEUTRAL.value,
        }

        return CallInsight(
            voice_session_id=voice_session_id,
            lead_id=lead_id,
            transcript=analysis.raw_transcript,
            summary=analysis.next_steps,
            sentiment_score=analysis.lead_sentiment_score,
            sentiment_label=sentiment_map.get(
                analysis.overall_sentiment, SentimentLabel.NEUTRAL.value
            ),
            objections=analysis.objections_raised,
            buying_signals=analysis.buying_signals,
            action_items=analysis.action_items,
            competitors_mentioned=analysis.entities.get("competitors", []),
            key_topics=analysis.topics,
            entities=analysis.entities,
            call_score=call_score,
            talk_ratio=analysis.talk_ratio,
            duration_seconds=analysis.duration_seconds,
            outcome=analysis.outcome,
            analyzer_version=ANALYZER_VERSION,
            analyzed_at=datetime.utcnow(),
        )

    def _calculate_call_score(self, analysis: CallAnalysis) -> int:
        """
        Calculate overall call quality score (0-100).

        Factors:
        - Sentiment (positive = +20, neutral = +10, negative = 0)
        - Buying signals count (+5 each, max +25)
        - Objections handled (fewer = better)
        - Talk ratio (0.4-0.6 is optimal)
        - Outcome (meeting_booked = +30, qualified = +20)
        """
        score = 50  # Base score

        # Sentiment contribution
        if analysis.overall_sentiment == Sentiment.POSITIVE:
            score += 20
        elif analysis.overall_sentiment == Sentiment.NEUTRAL:
            score += 10

        # Buying signals (max +25)
        score += min(len(analysis.buying_signals) * 5, 25)

        # Objections penalty (fewer is better)
        score -= min(len(analysis.objections_raised) * 3, 15)

        # Talk ratio (ideal is 40-60% lead talk)
        if 0.4 <= analysis.talk_ratio <= 0.6:
            score += 10
        elif 0.3 <= analysis.talk_ratio <= 0.7:
            score += 5

        # Outcome bonus
        if analysis.outcome == "meeting_booked":
            score += 30
        elif analysis.outcome == "qualified":
            score += 20
        elif analysis.outcome == "callback_scheduled":
            score += 15
        elif analysis.outcome == "not_qualified":
            score -= 10

        # Clamp to 0-100
        return max(0, min(100, score))
