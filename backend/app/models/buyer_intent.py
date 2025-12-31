"""
BuyerIntentSignal model for tracking engagement signals.

Tracks signals that indicate buyer interest:
- Email engagement (opens, clicks, replies)
- Response timing and sentiment
- Call scheduling and meetings

Used by IntentScoringService to calculate lead intent scores.
"""
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional
from uuid import uuid4

from sqlalchemy import Column, String, Float, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from app.models.database import Base


class IntentSignalType(str, Enum):
    """Types of buyer intent signals."""

    # Email engagement
    EMAIL_OPENED = "email_opened"
    EMAIL_OPENED_2X = "email_opened_2x"
    EMAIL_OPENED_3X = "email_opened_3x"
    LINK_CLICKED = "link_clicked"

    # Reply signals
    REPLY_POSITIVE = "reply_positive"
    REPLY_NEUTRAL = "reply_neutral"
    REPLY_QUESTION = "reply_question"
    REPLY_PRICING = "reply_pricing"
    REPLY_NEGATIVE = "reply_negative"

    # Timing signals
    RESPONSE_UNDER_1H = "response_under_1h"
    RESPONSE_UNDER_4H = "response_under_4h"
    RESPONSE_SAME_DAY = "response_same_day"

    # Call signals
    CALL_SCHEDULED = "call_scheduled"
    CALL_COMPLETED = "call_completed"
    DEMO_REQUESTED = "demo_requested"
    MEETING_BOOKED = "meeting_booked"

    # Website signals
    WEBSITE_VISIT = "website_visit"
    PRICING_PAGE_VIEW = "pricing_page_view"
    MULTIPLE_PAGE_VIEWS = "multiple_page_views"

    # Social signals
    LINKEDIN_CONNECTION = "linkedin_connection"
    LINKEDIN_PROFILE_VIEW = "linkedin_profile_view"


class IntentSignalSource(str, Enum):
    """Sources of intent signals."""
    EMAIL = "email"
    WEBSITE = "website"
    LINKEDIN = "linkedin"
    CALL = "call"
    MEETING = "meeting"
    CRM = "crm"
    MANUAL = "manual"


# Signal weights for intent scoring
# Higher weight = stronger buying intent signal
INTENT_SIGNAL_WEIGHTS: Dict[str, float] = {
    # Email engagement (moderate signals)
    IntentSignalType.EMAIL_OPENED.value: 1.0,
    IntentSignalType.EMAIL_OPENED_2X.value: 2.0,
    IntentSignalType.EMAIL_OPENED_3X.value: 3.0,
    IntentSignalType.LINK_CLICKED.value: 4.0,

    # Reply signals (strong signals)
    IntentSignalType.REPLY_POSITIVE.value: 5.0,
    IntentSignalType.REPLY_NEUTRAL.value: 2.0,
    IntentSignalType.REPLY_QUESTION.value: 3.5,
    IntentSignalType.REPLY_PRICING.value: 4.5,
    IntentSignalType.REPLY_NEGATIVE.value: -2.0,

    # Timing signals (urgency indicators)
    IntentSignalType.RESPONSE_UNDER_1H.value: 2.0,
    IntentSignalType.RESPONSE_UNDER_4H.value: 1.0,
    IntentSignalType.RESPONSE_SAME_DAY.value: 0.5,

    # Call signals (strongest signals)
    IntentSignalType.CALL_SCHEDULED.value: 5.0,
    IntentSignalType.CALL_COMPLETED.value: 6.0,
    IntentSignalType.DEMO_REQUESTED.value: 7.0,
    IntentSignalType.MEETING_BOOKED.value: 8.0,

    # Website signals (passive interest)
    IntentSignalType.WEBSITE_VISIT.value: 0.5,
    IntentSignalType.PRICING_PAGE_VIEW.value: 2.0,
    IntentSignalType.MULTIPLE_PAGE_VIEWS.value: 1.5,

    # Social signals (relationship building)
    IntentSignalType.LINKEDIN_CONNECTION.value: 1.5,
    IntentSignalType.LINKEDIN_PROFILE_VIEW.value: 0.5,
}


class BuyerIntentSignal(Base):
    """
    Individual intent signal from a lead.

    Signals are weighted and time-decayed to calculate an overall
    intent score for the lead.
    """
    __tablename__ = "buyer_intent_signals"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign key to dim_companies
    lead_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dim_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Signal classification
    signal_type = Column(String(50), nullable=False, index=True)
    signal_weight = Column(Float, nullable=False)
    source = Column(String(50), nullable=False, index=True)

    # Additional context
    metadata = Column(JSONB, nullable=False, default=dict)

    # Timestamp
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to API-friendly dictionary."""
        return {
            "id": str(self.id),
            "lead_id": str(self.lead_id),
            "signal_type": self.signal_type,
            "signal_weight": self.signal_weight,
            "source": self.source,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def get_weight(cls, signal_type: str) -> float:
        """Get the default weight for a signal type."""
        return INTENT_SIGNAL_WEIGHTS.get(signal_type, 1.0)

    @property
    def is_positive_signal(self) -> bool:
        """Check if this is a positive intent signal."""
        return self.signal_weight > 0

    @property
    def is_strong_signal(self) -> bool:
        """Check if this is a strong intent signal (weight >= 4)."""
        return self.signal_weight >= 4.0

    def __repr__(self) -> str:
        return (
            f"<BuyerIntentSignal("
            f"lead_id={self.lead_id}, "
            f"type={self.signal_type}, "
            f"weight={self.signal_weight})>"
        )
