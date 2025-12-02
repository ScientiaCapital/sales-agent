"""
Batch Job models for parallel lead processing

Tracks batch processing jobs and individual lead status for:
- Progress tracking with real-time WebSocket updates
- Error isolation (failed leads don't block others)
- Resume capability for interrupted batches
- Priority queuing based on ICP tier
"""
from sqlalchemy import (
    Column, String, Integer, Float, DateTime, Text,
    JSON, ForeignKey, Index, CheckConstraint, Numeric
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from uuid import uuid4

from .database import Base


class BatchJob(Base):
    """
    Track batch processing jobs for parallel lead enrichment.

    Status Flow:
        pending -> running -> completed
                          -> completed_with_errors (some leads failed)
                          -> failed (critical error)
                -> paused -> running (resume)
                -> cancelled
    """
    __tablename__ = "batch_jobs"

    __table_args__ = (
        Index('idx_batch_jobs_status', 'status'),
        Index('idx_batch_jobs_created_at', 'created_at'),
        Index('idx_batch_jobs_priority_status', 'priority', 'status'),
        CheckConstraint(
            "status IN ('pending', 'running', 'paused', 'completed', "
            "'completed_with_errors', 'failed', 'cancelled')",
            name='check_batch_status'
        ),
        CheckConstraint(
            "priority IN ('high', 'medium', 'low')",
            name='check_batch_priority'
        ),
    )

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Job identification
    name = Column(String(255), nullable=False)
    created_by = Column(String(100), nullable=True)

    # Status tracking
    status = Column(String(50), default='pending', nullable=False, index=True)

    # Progress counters
    total_leads = Column(Integer, nullable=False)
    processed_leads = Column(Integer, default=0, nullable=False)
    successful_leads = Column(Integer, default=0, nullable=False)
    failed_leads = Column(Integer, default=0, nullable=False)
    skipped_leads = Column(Integer, default=0, nullable=False)

    # Configuration
    options_json = Column(JSON, default=dict, nullable=False)
    priority = Column(String(20), default='medium', nullable=False)

    # Timing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Results
    error_message = Column(Text, nullable=True)
    result_summary_json = Column(JSON, nullable=True)

    # Relationships
    leads = relationship(
        "BatchJobLead",
        back_populates="batch_job",
        cascade="all, delete-orphan",
        lazy="dynamic"
    )

    @property
    def percent_complete(self) -> float:
        """Calculate completion percentage."""
        if self.total_leads == 0:
            return 0.0
        return round((self.processed_leads / self.total_leads) * 100, 2)

    @property
    def remaining_leads(self) -> int:
        """Calculate remaining leads to process."""
        return self.total_leads - self.processed_leads

    @property
    def is_complete(self) -> bool:
        """Check if batch has finished processing."""
        return self.status in ('completed', 'completed_with_errors', 'failed', 'cancelled')

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "name": self.name,
            "status": self.status,
            "priority": self.priority,
            "total_leads": self.total_leads,
            "processed_leads": self.processed_leads,
            "successful_leads": self.successful_leads,
            "failed_leads": self.failed_leads,
            "skipped_leads": self.skipped_leads,
            "percent_complete": self.percent_complete,
            "remaining_leads": self.remaining_leads,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
        }

    def __repr__(self):
        return (
            f"<BatchJob(id={self.id}, name='{self.name}', "
            f"status={self.status}, progress={self.processed_leads}/{self.total_leads})>"
        )


class BatchJobLead(Base):
    """
    Track individual lead status within a batch job.

    Status Flow:
        pending -> processing -> completed
                             -> failed (after retries exhausted)
                             -> skipped (e.g., already enriched)
    """
    __tablename__ = "batch_job_leads"

    __table_args__ = (
        Index('idx_batch_job_leads_job_status', 'batch_job_id', 'status'),
        Index('idx_batch_job_leads_company', 'company_id'),
        Index('idx_batch_job_leads_status', 'status'),
        CheckConstraint(
            "status IN ('pending', 'processing', 'completed', 'failed', 'skipped')",
            name='check_lead_status'
        ),
    )

    # Primary key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Foreign keys
    batch_job_id = Column(
        UUID(as_uuid=True),
        ForeignKey('batch_jobs.id', ondelete='CASCADE'),
        nullable=False,
        index=True
    )
    company_id = Column(UUID(as_uuid=True), nullable=False, index=True)

    # Processing state
    status = Column(String(50), default='pending', nullable=False, index=True)

    # Timing
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # Error handling
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)

    # Results
    result_json = Column(JSON, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True)

    # Relationships
    batch_job = relationship("BatchJob", back_populates="leads")

    @property
    def is_terminal(self) -> bool:
        """Check if lead is in a terminal state."""
        return self.status in ('completed', 'failed', 'skipped')

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id),
            "batch_job_id": str(self.batch_job_id),
            "company_id": str(self.company_id),
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "latency_ms": self.latency_ms,
            "cost_usd": float(self.cost_usd) if self.cost_usd else None,
        }

    def __repr__(self):
        return (
            f"<BatchJobLead(id={self.id}, batch={self.batch_job_id}, "
            f"company={self.company_id}, status={self.status})>"
        )
