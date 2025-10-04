"""
Multi-agent system models for tracking agent executions, workflows, and enriched data
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, JSON, BigInteger, ForeignKey, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from .database import Base


class AgentExecution(Base):
    """
    Track individual agent executions within multi-agent workflows
    """
    __tablename__ = "agent_executions"

    id = Column(Integer, primary_key=True, index=True)
    agent_type = Column(String(50), nullable=False, index=True)  # 'search', 'enrichment', 'campaign', 'booking'
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    workflow_id = Column(UUID(as_uuid=True), index=True)  # Groups related agent executions
    status = Column(
        SQLEnum('pending', 'running', 'success', 'failed', name='agent_execution_status'),
        nullable=False,
        index=True
    )
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    latency_ms = Column(Integer)
    
    # AI Model tracking
    model_used = Column(String(100))
    prompt_tokens = Column(Integer)
    completion_tokens = Column(Integer)
    cost_usd = Column(Float)
    
    # Output and error handling
    output_data = Column(JSON)
    error_message = Column(Text)
    retry_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<AgentExecution(id={self.id}, type='{self.agent_type}', status='{self.status}')>"


class AgentWorkflow(Base):
    """
    Track end-to-end multi-agent workflows for lead processing
    """
    __tablename__ = "agent_workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(200), nullable=False)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True)
    current_step = Column(String(50))  # Current step in workflow
    status = Column(
        SQLEnum('pending', 'running', 'completed', 'failed', name='agent_workflow_status'),
        nullable=False,
        index=True
    )
    
    # Performance metrics
    total_latency_ms = Column(Integer)
    total_cost_usd = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(DateTime(timezone=True))
    
    def __repr__(self):
        return f"<AgentWorkflow(id={self.id}, name='{self.name}', status='{self.status}')>"


class EnrichedLead(Base):
    """
    Store enriched lead data from external sources
    """
    __tablename__ = "enriched_leads"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), unique=True, nullable=False, index=True)
    
    # Company enrichment data
    employee_count = Column(Integer)
    annual_revenue = Column(BigInteger)
    funding_total = Column(BigInteger)
    tech_stack = Column(JSON)  # List of technologies used
    decision_makers = Column(JSON)  # Array of decision maker profiles
    
    # Enrichment metadata
    enrichment_source = Column(String(50))  # 'apollo', 'clearbit', 'zoominfo', etc.
    confidence_score = Column(Float)  # 0-1 confidence in enrichment data
    enriched_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<EnrichedLead(id={self.id}, lead_id={self.lead_id}, source='{self.enrichment_source}')>"


class MarketingCampaign(Base):
    """
    AI-generated marketing campaigns and outreach sequences
    """
    __tablename__ = "marketing_campaigns"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True, nullable=False)
    campaign_type = Column(String(50), nullable=False, index=True)  # 'email', 'linkedin', 'multi-channel'
    
    # Campaign content
    subject_lines = Column(JSON)  # Array of subject line variations
    email_sequences = Column(JSON)  # Array of email templates
    linkedin_messages = Column(JSON)  # Array of LinkedIn message templates
    
    # Predicted performance
    predicted_open_rate = Column(Float)
    predicted_reply_rate = Column(Float)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<MarketingCampaign(id={self.id}, lead_id={self.lead_id}, type='{self.campaign_type}')>"


class BookedMeeting(Base):
    """
    Track successfully booked meetings with leads
    """
    __tablename__ = "booked_meetings"

    id = Column(Integer, primary_key=True, index=True)
    lead_id = Column(Integer, ForeignKey("leads.id"), index=True, nullable=False)
    
    # Meeting details
    calendar_link = Column(String(500))
    scheduled_time = Column(DateTime(timezone=True), index=True)
    timezone = Column(String(50))
    duration_minutes = Column(Integer)
    meeting_type = Column(String(50))  # 'discovery', 'demo', 'proposal', etc.
    
    # Integration IDs
    hubspot_meeting_id = Column(String(100), index=True)
    calendly_event_id = Column(String(100), index=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    def __repr__(self):
        return f"<BookedMeeting(id={self.id}, lead_id={self.lead_id}, scheduled={self.scheduled_time})>"
