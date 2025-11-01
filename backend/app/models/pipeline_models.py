"""
Pipeline Testing Database Models

Models for tracking end-to-end pipeline test executions.
"""

from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, JSON, Text, Index
from sqlalchemy.sql import func
from datetime import datetime

from app.models.database import Base


class PipelineTestExecution(Base):
    """
    Track end-to-end pipeline test executions.

    Stores results from testing leads through the complete qualification →
    enrichment → deduplication → close CRM pipeline.
    """
    __tablename__ = "pipeline_test_executions"

    id = Column(Integer, primary_key=True, index=True)

    # Lead identification
    lead_name = Column(String(255), nullable=False, index=True)
    lead_email = Column(String(255), nullable=True)
    lead_phone = Column(String(50), nullable=True)
    csv_index = Column(Integer, nullable=True)  # Index in source CSV if applicable

    # Execution results
    success = Column(Boolean, nullable=False, index=True)
    error_stage = Column(String(50), nullable=True)  # Which stage failed (if any)
    error_message = Column(Text, nullable=True)

    # Performance metrics
    total_latency_ms = Column(Integer, nullable=True)
    total_cost_usd = Column(Float, nullable=True)

    # Stage-by-stage results (JSON)
    stages_json = Column(JSON, nullable=True)  # Detailed results per stage

    # Pipeline configuration
    stop_on_duplicate = Column(Boolean, default=True)
    skip_enrichment = Column(Boolean, default=False)
    create_in_crm = Column(Boolean, default=True)
    dry_run = Column(Boolean, default=False)

    # Timing
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    def __repr__(self):
        return f"<PipelineTestExecution(id={self.id}, lead='{self.lead_name}', success={self.success})>"


# Indexes for performance optimization
Index('idx_pipeline_test_lead_created', PipelineTestExecution.lead_name, PipelineTestExecution.created_at)
Index('idx_pipeline_test_success', PipelineTestExecution.success, PipelineTestExecution.created_at)
