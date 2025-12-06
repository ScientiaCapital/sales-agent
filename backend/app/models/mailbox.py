"""
Mailbox model for managing email accounts used for warming and sending
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class Mailbox(Base):
    """
    Mailbox model representing email accounts for warming and cold email sending.
    Tracks warming status, heat score, and email volume counters.
    """
    __tablename__ = "dim_mailboxes"

    # Table-level constraints and indexes
    __table_args__ = (
        # Composite index for active mailbox queries by status
        Index('idx_mailboxes_status_heat', 'status', 'heat_score'),
        # Index for warming monitoring
        Index('idx_mailboxes_warming_start', 'warming_start_date'),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Email Account Information
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_encrypted = Column(Text, nullable=False)  # Store encrypted in production

    # SMTP/IMAP Settings
    smtp_host = Column(String(255), default="smtp.gmail.com")
    smtp_port = Column(Integer, default=587)
    imap_host = Column(String(255), default="imap.gmail.com")
    imap_port = Column(Integer, default=993)

    # Mailbox Status
    status = Column(String(50), default="warming", nullable=False, index=True)
    # Status values: "warming", "active", "paused", "bounced", "suspended"

    heat_score = Column(Integer, default=50, nullable=False)
    # Heat score 0-100: higher = better reputation

    warming_start_date = Column(DateTime(timezone=True))

    # Email Volume Counters
    total_sent = Column(Integer, default=0, nullable=False)
    total_received = Column(Integer, default=0, nullable=False)
    spam_rescues = Column(Integer, default=0, nullable=False)
    bounce_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    sequence_entries = relationship("SequenceEntry", back_populates="mailbox", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Mailbox(id={self.id}, email='{self.email}', status='{self.status}', heat={self.heat_score})>"

    @property
    def is_ready_for_sending(self) -> bool:
        """Check if mailbox is ready for cold email sending"""
        return self.status == "active" and self.heat_score >= 70

    @property
    def deliverability_score(self) -> float:
        """Calculate deliverability score based on bounce rate and spam rescues"""
        if self.total_sent == 0:
            return 100.0

        bounce_rate = (self.bounce_count / self.total_sent) * 100
        spam_rescue_rate = (self.spam_rescues / self.total_sent) * 100

        # Lower bounce rate = better score
        # Higher spam rescue rate = worse score
        score = 100 - (bounce_rate * 2) - (spam_rescue_rate * 3)
        return max(0.0, min(100.0, score))

    @property
    def engagement_metrics(self) -> dict:
        """Get engagement metrics summary"""
        return {
            "total_sent": self.total_sent,
            "total_received": self.total_received,
            "bounce_count": self.bounce_count,
            "spam_rescues": self.spam_rescues,
            "heat_score": self.heat_score,
            "deliverability_score": round(self.deliverability_score, 2),
            "status": self.status
        }

    def set_password(self, password: str) -> None:
        """
        Encrypt and store password.

        Args:
            password: Plain text password to encrypt and store

        Raises:
            ValueError: If encryption key not configured
        """
        from app.core.encryption import encrypt_password
        self.password_encrypted = encrypt_password(password)

    def get_password(self) -> str:
        """
        Decrypt and return password.

        Returns:
            Plain text password

        Raises:
            ValueError: If encryption key not configured or decryption fails
        """
        from app.core.encryption import decrypt_password
        return decrypt_password(self.password_encrypted)
