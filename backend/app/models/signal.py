"""
Signal model for tracking incoming email signals (replies, bounces, OOO)
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON, ForeignKey, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class Signal(Base):
    """
    Signal model representing incoming email signals from prospects.
    Tracks replies, bounces, out-of-office messages, and other email events.
    """
    __tablename__ = "dim_signals"

    # Table-level constraints and indexes
    __table_args__ = (
        # Composite index for unprocessed signals
        Index('idx_signals_processed_received', 'processed', 'received_at'),
        # Index for finding signals by type
        Index('idx_signals_type_priority', 'signal_type', 'priority'),
        # Index for finding signals by intent
        Index('idx_signals_intent_processed', 'intent', 'processed'),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Foreign Key
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)

    # Signal Type
    signal_type = Column(String(50), nullable=False, index=True)
    # Signal types: "email_reply", "bounce", "out_of_office", "unsubscribe", "complaint"

    mailbox_email = Column(String(255), index=True)

    # Email Content
    subject = Column(String(500))
    content = Column(Text)

    # Classification (from AI analysis)
    intent = Column(String(50), index=True)
    # Intent values: "interested", "not_interested", "neutral", "meeting_request",
    #                "question", "pricing_request", "demo_request", "unsubscribe"

    priority = Column(Integer, default=3, nullable=False)
    # Priority: 1 (urgent) to 5 (low)

    # Email Metadata
    message_id = Column(String(255), index=True)
    thread_id = Column(String(255), index=True)
    raw_headers = Column(JSON, default=dict)

    # Processing State
    processed = Column(Boolean, default=False, nullable=False, index=True)
    processed_at = Column(DateTime(timezone=True))
    routed_to = Column(String(100))
    # routed_to values: "sales_agent", "vozlux_call", "human_review", "auto_reply", "ignored"

    # Timestamps
    received_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    lead = relationship("Lead", foreign_keys=[lead_id])

    def __repr__(self):
        return (
            f"<Signal(id={self.id}, type='{self.signal_type}', "
            f"intent='{self.intent}', processed={self.processed})>"
        )

    @property
    def is_positive_signal(self) -> bool:
        """Check if signal indicates positive intent"""
        positive_intents = ["interested", "meeting_request", "question", "pricing_request", "demo_request"]
        return self.intent in positive_intents

    @property
    def is_negative_signal(self) -> bool:
        """Check if signal indicates negative intent"""
        negative_intents = ["not_interested", "unsubscribe", "complaint"]
        return self.intent in negative_intents or self.signal_type in ["bounce", "unsubscribe", "complaint"]

    @property
    def requires_human_attention(self) -> bool:
        """Check if signal requires human review"""
        return (
            self.priority <= 2 or
            self.is_positive_signal or
            self.signal_type in ["complaint", "unsubscribe"]
        )

    @property
    def should_trigger_call(self) -> bool:
        """Check if signal should trigger a VozLux call"""
        call_trigger_intents = ["interested", "meeting_request", "pricing_request", "demo_request"]
        return self.intent in call_trigger_intents and not self.processed

    @property
    def signal_summary(self) -> dict:
        """Get summary of signal information"""
        return {
            "id": self.id,
            "lead_id": self.lead_id,
            "signal_type": self.signal_type,
            "intent": self.intent,
            "priority": self.priority,
            "processed": self.processed,
            "routed_to": self.routed_to,
            "is_positive": self.is_positive_signal,
            "is_negative": self.is_negative_signal,
            "requires_attention": self.requires_human_attention,
            "should_trigger_call": self.should_trigger_call,
            "received_at": self.received_at.isoformat() if self.received_at else None
        }

    def mark_processed(self, routed_to: str = None):
        """Mark signal as processed"""
        self.processed = True
        self.processed_at = func.now()
        if routed_to:
            self.routed_to = routed_to

    def classify_intent(self, intent: str, priority: int = None):
        """Classify the signal with AI-detected intent"""
        self.intent = intent
        if priority is not None:
            self.priority = priority

    @staticmethod
    def get_priority_from_intent(intent: str) -> int:
        """Get recommended priority based on intent"""
        priority_map = {
            "interested": 1,
            "meeting_request": 1,
            "demo_request": 1,
            "pricing_request": 2,
            "question": 2,
            "complaint": 1,
            "unsubscribe": 2,
            "neutral": 3,
            "not_interested": 4,
            "out_of_office": 5
        }
        return priority_map.get(intent, 3)
