"""
CRM Integration Database Models

SQLAlchemy models for storing CRM credentials, contacts, sync logs, and webhooks.
All sensitive data (tokens, API keys) is encrypted using Fernet symmetric encryption.
"""

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, JSON, Float, Boolean, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from datetime import datetime
from app.models.database import Base


class CRMCredential(Base):
    """
    Encrypted CRM credentials for OAuth and API key authentication.
    
    Supports: HubSpot (OAuth), Apollo (API key), LinkedIn (OAuth sign-in only)
    """
    
    __tablename__ = "crm_credentials"
    
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String(50), nullable=False, index=True)  # "hubspot", "apollo", "linkedin"
    user_id = Column(Integer, nullable=True, index=True)  # Associated user (if applicable)
    
    # OAuth tokens (ENCRYPTED in database using Fernet)
    access_token = Column(Text, nullable=True)  # Encrypted access token
    refresh_token = Column(Text, nullable=True)  # Encrypted refresh token
    token_expires_at = Column(DateTime, nullable=True)
    
    # API keys (ENCRYPTED in database)
    api_key = Column(Text, nullable=True)  # Encrypted API key (for Apollo)
    
    # OAuth metadata
    scopes = Column(JSON, nullable=True)  # List of OAuth scopes granted
    
    # Status tracking
    is_active = Column(Boolean, default=True, index=True)
    last_auth_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    sync_logs = relationship("CRMSyncLog", back_populates="credential", cascade="all, delete-orphan")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_crm_creds_platform_user', 'platform', 'user_id'),
        Index('idx_crm_creds_active', 'is_active', 'platform'),
    )


class CRMContact(Base):
    """
    Unified contact model across all CRM platforms.
    
    Master contact record in PostgreSQL with platform-specific external IDs.
    Supports bi-directional sync with HubSpot and one-way enrichment from Apollo.
    """
    
    __tablename__ = "crm_contacts"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Core contact information
    email = Column(String(255), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    company = Column(String(255), nullable=True, index=True)
    title = Column(String(255), nullable=True)
    phone = Column(String(50), nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    
    # Platform-specific IDs stored as JSON
    # Example: {"hubspot": "12345", "apollo": "67890", "linkedin": "abc123"}
    external_ids = Column(JSON, nullable=False, default=dict)
    
    # Apollo enrichment data (stored as JSON)
    enrichment_data = Column(JSON, nullable=True)
    enrichment_score = Column(Float, nullable=True)  # Apollo confidence score
    
    # Metadata
    source_platform = Column(String(50), nullable=True, index=True)  # Origin platform
    last_synced_at = Column(DateTime, nullable=True)
    sync_status = Column(String(50), default="active", index=True)  # active, archived, error
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_crm_contact_email', 'email'),
        Index('idx_crm_contact_company', 'company'),
        Index('idx_crm_contact_source', 'source_platform'),
        Index('idx_crm_contact_sync_status', 'sync_status'),
        Index('idx_crm_contact_last_synced', 'last_synced_at'),
    )


class CRMSyncLog(Base):
    """
    Audit log for CRM sync operations.
    
    Tracks all sync operations (import, export, bidirectional) with detailed metrics.
    Used for monitoring, debugging, and compliance.
    """
    
    __tablename__ = "crm_sync_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    credential_id = Column(Integer, ForeignKey("crm_credentials.id", ondelete="CASCADE"), nullable=False, index=True)
    
    platform = Column(String(50), nullable=False, index=True)
    operation = Column(String(50), nullable=False)  # "import", "export", "bidirectional"
    
    # Metrics
    contacts_processed = Column(Integer, default=0)
    contacts_created = Column(Integer, default=0)
    contacts_updated = Column(Integer, default=0)
    contacts_failed = Column(Integer, default=0)
    
    # Error tracking
    errors = Column(JSON, nullable=True)  # List of error details
    
    # Performance metrics
    started_at = Column(DateTime, nullable=False, index=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    
    # Status
    status = Column(String(50), default="running", index=True)  # running, completed, failed
    
    # Relationships
    credential = relationship("CRMCredential", back_populates="sync_logs")
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_sync_log_platform_status', 'platform', 'status'),
        Index('idx_sync_log_started', 'started_at'),
    )


class CRMWebhook(Base):
    """
    Webhook event tracking for CRM platforms.

    Stores webhook events for deduplication and audit trail.
    Prevents duplicate processing of the same event.
    """

    __tablename__ = "crm_webhooks"

    id = Column(Integer, primary_key=True, index=True)

    platform = Column(String(50), nullable=False, index=True)
    event_type = Column(String(100), nullable=False, index=True)  # "contact.created", "contact.updated", etc.
    event_id = Column(String(255), unique=True, nullable=False, index=True)  # Platform-specific event ID

    # Contact reference
    contact_id = Column(String(255), nullable=True, index=True)  # External contact ID

    # Webhook payload
    payload = Column(JSON, nullable=False)
    signature = Column(Text, nullable=True)  # Webhook signature for verification

    # Processing status
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime, nullable=True)
    processing_error = Column(Text, nullable=True)

    # Timestamps
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    event_timestamp = Column(DateTime, nullable=False, index=True)  # Timestamp from webhook payload

    # Indexes for common queries and deduplication
    __table_args__ = (
        Index('idx_webhook_event_id', 'event_id'),  # Unique constraint for deduplication
        Index('idx_webhook_platform_type', 'platform', 'event_type'),
        Index('idx_webhook_processed', 'processed', 'received_at'),
    )


class CloseOpportunity(Base):
    """
    Close CRM Opportunity model for tracking deals through sales stages.

    Links to Close leads and optionally to local CRMContact records.
    Supports pipeline visibility and revenue forecasting.
    """

    __tablename__ = "crm_opportunities"

    id = Column(Integer, primary_key=True, index=True)

    # Close-specific identifiers
    external_id = Column(String(255), unique=True, nullable=False, index=True)  # Close opportunity ID
    platform = Column(String(50), default="close", nullable=False)
    close_lead_id = Column(String(255), nullable=False, index=True)  # Reference to Close lead

    # Local contact reference (optional)
    contact_id = Column(Integer, ForeignKey("crm_contacts.id", ondelete="SET NULL"), nullable=True, index=True)

    # Opportunity details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Financial data
    amount = Column(Float, nullable=True)  # Deal value
    currency = Column(String(3), default="USD", nullable=False)

    # Stage tracking
    stage = Column(String(50), nullable=False)  # e.g., "prospecting", "proposal", "won", "lost"
    probability = Column(Float, nullable=True)  # 0-100 win chance

    # Dates
    expected_close_date = Column(DateTime, nullable=True)
    actual_close_date = Column(DateTime, nullable=True)

    # Ownership
    owner_id = Column(String(255), nullable=True)  # Close user ID

    # Sync metadata
    last_synced_at = Column(DateTime, nullable=True)
    sync_status = Column(String(50), default="active", nullable=False)  # active, archived, error

    # Raw API response for debugging/auditing
    raw_data = Column(JSON, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    contact = relationship("CRMContact", backref="opportunities")

    # Indexes for common queries
    __table_args__ = (
        Index('idx_opp_external_id', 'external_id', unique=True),
        Index('idx_opp_close_lead_id', 'close_lead_id'),
        Index('idx_opp_stage_expected_close', 'stage', 'expected_close_date'),
        Index('idx_opp_sync_status', 'sync_status'),
    )


class ClosePipeline(Base):
    """
    Close CRM Pipeline model for tracking sales pipeline configurations.

    Stores pipeline stages and their default probabilities.
    Used for opportunity stage validation and forecasting.
    """

    __tablename__ = "crm_pipelines"

    id = Column(Integer, primary_key=True, index=True)

    # Close-specific identifiers
    external_id = Column(String(255), unique=True, nullable=False, index=True)  # Close pipeline ID
    platform = Column(String(50), default="close", nullable=False)

    # Pipeline details
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Stages configuration stored as JSON array
    # Example: [{"name": "Prospecting", "order": 1, "default_probability": 10}, ...]
    stages_json = Column(JSON, nullable=False)

    # Status
    is_active = Column(Boolean, default=True, nullable=False)

    # Metadata
    created_by = Column(String(255), nullable=True)  # Close user ID who created it

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Indexes for common queries
    __table_args__ = (
        Index('idx_pipeline_external_id', 'external_id', unique=True),
        Index('idx_pipeline_active', 'is_active'),
        Index('idx_pipeline_name', 'name'),
    )
