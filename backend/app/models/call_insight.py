"""
CallInsight model for AI-analyzed call recordings.

Stores structured insights extracted from call recordings using
PostCallAnalyzer (AssemblyAI integration):
- Sentiment analysis (per-turn and overall)
- Objection detection and categorization
- Buying signal identification
- Action item extraction
- Entity recognition (competitors, products)
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import uuid4
import enum

from sqlalchemy import (
    Column, String, Float, Integer, Text, DateTime, ForeignKey, Index
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from .database import Base


class SentimentLabel(str, enum.Enum):
    """Sentiment classification labels."""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"


class CallOutcome(str, enum.Enum):
    """Possible call outcomes."""
    MEETING_BOOKED = "meeting_booked"
    CALLBACK_SCHEDULED = "callback_scheduled"
    QUALIFIED = "qualified"
    NOT_QUALIFIED = "not_qualified"
    NEEDS_NURTURING = "needs_nurturing"
    FOLLOW_UP_REQUIRED = "follow_up_required"


class CallInsight(Base):
    """
    AI-analyzed call recording insights.

    Links to voice_session_logs for call metadata and dim_companies for
    lead context. Populated by CallInsightsService after call completion.

    Key features:
    - Sentiment tracking (score + label)
    - JSONB columns for flexible insight storage
    - Call scoring for quality assessment
    - Outcome classification for pipeline automation
    """
    __tablename__ = "call_insights"

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    voice_session_id = Column(String(255), ForeignKey(
        "voice_session_logs.id", ondelete="SET NULL"), nullable=True)
    lead_id = Column(UUID(as_uuid=True), ForeignKey(
        "dim_companies.id", ondelete="SET NULL"), nullable=True)

    # Analysis results
    transcript = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    sentiment_score = Column(Float, nullable=True)  # -1.0 to 1.0
    sentiment_label = Column(String(20), nullable=True)  # positive/negative/neutral

    # Extracted insights (JSONB for flexibility)
    objections = Column(JSONB, nullable=False, default=list)
    buying_signals = Column(JSONB, nullable=False, default=list)
    action_items = Column(JSONB, nullable=False, default=list)
    competitors_mentioned = Column(JSONB, nullable=False, default=list)
    key_topics = Column(JSONB, nullable=False, default=list)
    entities = Column(JSONB, nullable=False, default=dict)

    # Scoring metrics
    call_score = Column(Integer, nullable=True)  # 0-100
    talk_ratio = Column(Float, nullable=True)  # 0.0-1.0 (lead talk time ratio)
    duration_seconds = Column(Integer, nullable=True)
    outcome = Column(String(50), nullable=True)

    # Metadata
    analyzer_version = Column(String(20), nullable=True)
    analyzed_at = Column(DateTime(timezone=True), server_default=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    voice_session = relationship("VoiceSessionLog", backref="insights")
    lead = relationship("Lead", backref="call_insights")

    # Indexes for performance
    __table_args__ = (
        Index("idx_call_insights_voice_session", "voice_session_id"),
        Index("idx_call_insights_lead", "lead_id"),
        Index("idx_call_insights_sentiment", "sentiment_label"),
        Index("idx_call_insights_outcome", "outcome"),
        Index("idx_call_insights_analyzed_at", "analyzed_at"),
        Index("idx_call_insights_call_score", "call_score"),
    )

    @property
    def is_positive(self) -> bool:
        """Check if call had positive sentiment."""
        return self.sentiment_label == SentimentLabel.POSITIVE.value

    @property
    def is_qualified(self) -> bool:
        """Check if call outcome indicates qualified lead."""
        return self.outcome in [
            CallOutcome.MEETING_BOOKED.value,
            CallOutcome.QUALIFIED.value,
            CallOutcome.CALLBACK_SCHEDULED.value,
        ]

    @property
    def has_objections(self) -> bool:
        """Check if call had objections raised."""
        return bool(self.objections)

    @property
    def objection_count(self) -> int:
        """Count of objections raised."""
        return len(self.objections) if self.objections else 0

    @property
    def buying_signal_count(self) -> int:
        """Count of buying signals detected."""
        return len(self.buying_signals) if self.buying_signals else 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "voice_session_id": self.voice_session_id,
            "lead_id": str(self.lead_id) if self.lead_id else None,
            "transcript": self.transcript,
            "summary": self.summary,
            "sentiment_score": self.sentiment_score,
            "sentiment_label": self.sentiment_label,
            "objections": self.objections or [],
            "buying_signals": self.buying_signals or [],
            "action_items": self.action_items or [],
            "competitors_mentioned": self.competitors_mentioned or [],
            "key_topics": self.key_topics or [],
            "entities": self.entities or {},
            "call_score": self.call_score,
            "talk_ratio": self.talk_ratio,
            "duration_seconds": self.duration_seconds,
            "outcome": self.outcome,
            "analyzed_at": self.analyzed_at.isoformat() if self.analyzed_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self) -> str:
        return (
            f"<CallInsight(id={self.id}, session={self.voice_session_id}, "
            f"sentiment={self.sentiment_label}, outcome={self.outcome})>"
        )
