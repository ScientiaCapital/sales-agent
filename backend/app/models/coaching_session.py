"""
Database model for real-time call coaching metrics

Tracks coaching usage per call session for analytics and optimization.
"""

from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Boolean,
    ForeignKey, Index
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from uuid import uuid4

from .database import Base


class CoachingSession(Base):
    """
    Fact table for real-time coaching usage metrics.

    Tracks suggestions and battle cards shown vs used during live calls.
    Used for coaching effectiveness analysis and model improvement.
    """
    __tablename__ = "fact_coaching_usage"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))

    # Call identification
    call_sid = Column(String(64), nullable=False, index=True, unique=True)
    conversation_id = Column(
        String,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True
    )

    # Session timing
    started_at = Column(DateTime, server_default=func.now())
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    # Suggestion metrics
    suggestions_shown = Column(Integer, default=0)
    suggestions_used = Column(Integer, default=0)
    suggestion_acceptance_rate = Column(Float, nullable=True)

    # Battle card metrics
    battle_cards_shown = Column(Integer, default=0)
    battle_cards_used = Column(Integer, default=0)
    battle_card_acceptance_rate = Column(Float, nullable=True)

    # Overall coaching metrics
    total_coaching_events = Column(Integer, default=0)
    coaching_accepted_count = Column(Integer, default=0)
    overall_acceptance_rate = Column(Float, nullable=True)

    # Latency metrics (for performance optimization)
    avg_coaching_latency_ms = Column(Integer, nullable=True)
    max_coaching_latency_ms = Column(Integer, nullable=True)

    # Agent info
    agent_id = Column(String, nullable=True)

    # Status
    is_active = Column(Boolean, default=True)

    # Timestamps
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

    # Relationship to conversation
    conversation = relationship("Conversation", backref="coaching_sessions")

    __table_args__ = (
        Index("ix_fact_coaching_usage_started_at", "started_at"),
        Index("ix_fact_coaching_usage_agent_id", "agent_id"),
        Index("ix_fact_coaching_usage_is_active", "is_active"),
    )

    def calculate_rates(self):
        """Calculate acceptance rates from shown/used counts."""
        if self.suggestions_shown > 0:
            self.suggestion_acceptance_rate = round(
                self.suggestions_used / self.suggestions_shown, 3
            )

        if self.battle_cards_shown > 0:
            self.battle_card_acceptance_rate = round(
                self.battle_cards_used / self.battle_cards_shown, 3
            )

        total_shown = self.suggestions_shown + self.battle_cards_shown
        if total_shown > 0:
            total_used = self.suggestions_used + self.battle_cards_used
            self.overall_acceptance_rate = round(total_used / total_shown, 3)
