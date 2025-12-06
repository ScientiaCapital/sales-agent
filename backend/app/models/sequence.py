"""
Sequence model for managing multi-step email campaigns
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Index
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from .database import Base


class Sequence(Base):
    """
    Sequence model representing multi-step email campaigns.
    Steps are stored as JSON array with delay, subject, and body templates.
    """
    __tablename__ = "dim_sequences"

    # Table-level constraints and indexes
    __table_args__ = (
        # Composite index for active sequence queries
        Index('idx_sequences_active_created', 'is_active', 'created_at'),
    )

    id = Column(Integer, primary_key=True, index=True)

    # Sequence Identification
    sequence_id = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # Sequence Settings
    stop_on_reply = Column(Boolean, default=True, nullable=False)
    stop_on_bounce = Column(Boolean, default=True, nullable=False)
    daily_limit_per_mailbox = Column(Integer, default=50, nullable=False)

    # Steps Configuration (JSON Array)
    steps = Column(JSON, nullable=False)
    # Example structure:
    # [
    #   {
    #     "step_number": 0,
    #     "delay_days": 0,
    #     "subject": "Quick question about {{company}}",
    #     "body": "Hi {{first_name}},\n\n..."
    #   },
    #   {
    #     "step_number": 1,
    #     "delay_days": 3,
    #     "subject": "Re: Quick question about {{company}}",
    #     "body": "Hi {{first_name}},\n\nFollowing up on my previous email..."
    #   }
    # ]

    # Metadata
    is_active = Column(Boolean, default=True, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    entries = relationship("SequenceEntry", back_populates="sequence", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Sequence(id={self.id}, sequence_id='{self.sequence_id}', name='{self.name}', active={self.is_active})>"

    @property
    def total_steps(self) -> int:
        """Get total number of steps in sequence"""
        return len(self.steps) if self.steps else 0

    @property
    def max_delay_days(self) -> int:
        """Get maximum delay across all steps"""
        if not self.steps:
            return 0
        return max(step.get("delay_days", 0) for step in self.steps)

    @property
    def sequence_summary(self) -> dict:
        """Get summary of sequence configuration"""
        return {
            "sequence_id": self.sequence_id,
            "name": self.name,
            "total_steps": self.total_steps,
            "max_delay_days": self.max_delay_days,
            "stop_on_reply": self.stop_on_reply,
            "stop_on_bounce": self.stop_on_bounce,
            "daily_limit": self.daily_limit_per_mailbox,
            "is_active": self.is_active
        }

    def get_step(self, step_number: int) -> dict:
        """Get a specific step by step number"""
        if not self.steps:
            return None

        for step in self.steps:
            if step.get("step_number") == step_number:
                return step
        return None

    def validate_steps(self) -> tuple[bool, str]:
        """
        Validate sequence steps structure.
        Returns (is_valid, error_message)
        """
        if not self.steps:
            return False, "Sequence must have at least one step"

        if not isinstance(self.steps, list):
            return False, "Steps must be a list"

        required_fields = ["step_number", "delay_days", "subject", "body"]

        for i, step in enumerate(self.steps):
            # Check required fields
            for field in required_fields:
                if field not in step:
                    return False, f"Step {i} missing required field: {field}"

            # Validate step number
            if step["step_number"] != i:
                return False, f"Step {i} has incorrect step_number: {step['step_number']}"

            # Validate delay
            if not isinstance(step["delay_days"], (int, float)) or step["delay_days"] < 0:
                return False, f"Step {i} has invalid delay_days: {step['delay_days']}"

            # Validate subject and body are strings
            if not isinstance(step["subject"], str) or not step["subject"].strip():
                return False, f"Step {i} has invalid subject"

            if not isinstance(step["body"], str) or not step["body"].strip():
                return False, f"Step {i} has invalid body"

        return True, ""
