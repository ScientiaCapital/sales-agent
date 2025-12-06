"""
SequenceEntry model for tracking prospect progress through email sequences
"""
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class SequenceEntry(Base):
    """
    SequenceEntry model tracking a lead's progress through an email sequence.
    Manages state, step progression, and reply tracking.
    """
    __tablename__ = "dim_sequence_entries"

    # Table-level constraints and indexes
    __table_args__ = (
        # Composite index for finding entries by prospect and sequence
        Index('idx_entries_lead_sequence', 'lead_id', 'sequence_id'),
        # Index for filtering by status
        Index('idx_entries_status_updated', 'status', 'updated_at'),
        # Index for finding active entries
        Index('idx_entries_status_current_step', 'status', 'current_step'),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Foreign Keys
    lead_id = Column(Integer, ForeignKey("leads.id"), nullable=False, index=True)
    sequence_id = Column(Integer, ForeignKey("dim_sequences.id"), nullable=False, index=True)
    mailbox_id = Column(Integer, ForeignKey("dim_mailboxes.id"), nullable=False, index=True)

    # State Tracking
    status = Column(String(50), default="pending", nullable=False, index=True)
    # Status values: "pending", "active", "paused", "replied", "bounced", "completed", "unsubscribed"

    current_step = Column(Integer, default=0, nullable=False)

    # Timestamps
    started_at = Column(DateTime(timezone=True))
    last_email_sent = Column(DateTime(timezone=True))
    reply_received = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))

    # Reply Information
    reply_intent = Column(String(50))
    # Intent values: "interested", "not_interested", "neutral", "out_of_office", "unsubscribe"

    # Engagement Tracking
    emails_sent = Column(Integer, default=0, nullable=False)
    opens = Column(Integer, default=0, nullable=False)
    clicks = Column(Integer, default=0, nullable=False)

    # Email Threading
    thread_id = Column(String(255))
    message_ids = Column(JSON, default=list)
    # List of Message-ID headers for threading

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    lead = relationship("Lead", foreign_keys=[lead_id])
    sequence = relationship("Sequence", back_populates="entries")
    mailbox = relationship("Mailbox", back_populates="sequence_entries")

    def __repr__(self):
        return (
            f"<SequenceEntry(id={self.id}, lead_id={self.lead_id}, "
            f"sequence_id={self.sequence_id}, status='{self.status}', step={self.current_step})>"
        )

    @property
    def is_active(self) -> bool:
        """Check if entry is actively progressing"""
        return self.status in ["pending", "active"]

    @property
    def is_completed(self) -> bool:
        """Check if entry has finished (any terminal state)"""
        return self.status in ["replied", "bounced", "completed", "unsubscribed"]

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate (opens + clicks) / emails_sent"""
        if self.emails_sent == 0:
            return 0.0
        return ((self.opens + self.clicks) / self.emails_sent) * 100

    @property
    def open_rate(self) -> float:
        """Calculate open rate"""
        if self.emails_sent == 0:
            return 0.0
        return (self.opens / self.emails_sent) * 100

    @property
    def click_rate(self) -> float:
        """Calculate click rate"""
        if self.emails_sent == 0:
            return 0.0
        return (self.clicks / self.emails_sent) * 100

    @property
    def entry_summary(self) -> dict:
        """Get summary of sequence entry metrics"""
        return {
            "lead_id": self.lead_id,
            "sequence_id": self.sequence_id,
            "status": self.status,
            "current_step": self.current_step,
            "emails_sent": self.emails_sent,
            "opens": self.opens,
            "clicks": self.clicks,
            "open_rate": round(self.open_rate, 2),
            "click_rate": round(self.click_rate, 2),
            "engagement_rate": round(self.engagement_rate, 2),
            "reply_intent": self.reply_intent,
            "is_active": self.is_active,
            "is_completed": self.is_completed
        }

    def add_message_id(self, message_id: str):
        """Add a message ID to the threading list"""
        if self.message_ids is None:
            self.message_ids = []
        if message_id not in self.message_ids:
            self.message_ids.append(message_id)

    def advance_step(self):
        """Move to the next step in the sequence"""
        self.current_step += 1
        if self.status == "pending":
            self.status = "active"

    def mark_replied(self, intent: str = None):
        """Mark entry as replied with optional intent"""
        self.status = "replied"
        self.reply_received = func.now()
        if intent:
            self.reply_intent = intent

    def mark_bounced(self):
        """Mark entry as bounced"""
        self.status = "bounced"
        self.completed_at = func.now()

    def mark_completed(self):
        """Mark entry as completed (all steps sent)"""
        self.status = "completed"
        self.completed_at = func.now()

    def mark_unsubscribed(self):
        """Mark entry as unsubscribed"""
        self.status = "unsubscribed"
        self.completed_at = func.now()
