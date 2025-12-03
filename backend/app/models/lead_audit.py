"""
Lead Audit Log model for tracking lead lifecycle decisions.

Provides full context for GTM agents:
- What happened to each lead
- Why decisions were made (scores, confidence, match reasons)
- Where data came from (source files, enrichment providers)
- When each event occurred

Event types track the full pipeline:
import → qualification → crm_check → enrichment → deduplication → export
"""
from enum import Enum
from typing import Dict, Any
from uuid import uuid4

from sqlalchemy import Column, String, Integer, DateTime, Numeric, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func

from .database import Base


class LeadAuditEventType(str, Enum):
    """
    Event types for lead audit trail.

    Grouped by pipeline stage for easy filtering.
    """
    # Import Stage
    LEAD_IMPORTED = "lead_imported"
    LEAD_SKIPPED_IMPORT = "lead_skipped_import"  # OEM filter, bad data

    # Qualification Stage
    LEAD_QUALIFIED = "lead_qualified"
    LEAD_DISQUALIFIED = "lead_disqualified"
    WEBSITE_ANALYZED = "website_analyzed"

    # CRM Check Stage
    CRM_MATCH_FOUND = "crm_match_found"
    CRM_NO_MATCH = "crm_no_match"

    # Enrichment Stage
    LEAD_ENRICHED = "lead_enriched"
    ENRICHMENT_FAILED = "enrichment_failed"
    CONTACT_DISCOVERED = "contact_discovered"
    EMAIL_EXTRACTED = "email_extracted"

    # Deduplication Stage
    DEDUP_CREATE_NEW = "dedup_create_new"
    DEDUP_ADD_CONTACT = "dedup_add_contact"
    DEDUP_SKIP_DUPLICATE = "dedup_skip_duplicate"
    DEDUP_UPDATE_EXISTING = "dedup_update_existing"

    # Export Stage
    LEAD_EXPORTED = "lead_exported"
    LEAD_FILTERED_EXPORT = "lead_filtered_export"  # Bad email, etc.

    # Delivery/Staging Stage
    LEAD_STAGED = "lead_staged"  # Marketing content staged in Close CRM as draft
    LEAD_DELIVERED = "lead_delivered"  # Email/SMS actually sent (future)

    # Lifecycle Changes (manual or automated)
    STATUS_CHANGED = "status_changed"
    TIER_CHANGED = "tier_changed"
    REMOVED_FROM_LIST = "removed_from_list"


class LeadAuditStage(str, Enum):
    """Pipeline stages for categorizing audit events."""
    IMPORT = "import"
    QUALIFICATION = "qualification"
    CRM_CHECK = "crm_check"
    ENRICHMENT = "enrichment"
    DEDUPLICATION = "deduplication"
    EXPORT = "export"
    STAGING = "staging"  # Close CRM draft staging (no sends)
    LIFECYCLE = "lifecycle"


class LeadAuditLog(Base):
    """
    Audit trail for lead lifecycle - used by GTM agents for context.

    Tracks every decision made about every lead through the pipeline:
    - Import: Which CSV, which row, OEM filter results
    - Qualification: Score, tier, ATL status, scoring factors
    - CRM Check: Match results, existing contacts found
    - Enrichment: Sources tried, contacts found, costs
    - Deduplication: Recommendation, confidence, match reasons
    - Export: Output file, final status

    Example queries for GTM agents:
    - "What happened to ABC Company?" → filter by company_name
    - "Show all dedup decisions" → filter by event_type LIKE 'dedup_%'
    - "What was processed in session X?" → filter by session_id
    - "Why was this lead skipped?" → check decision_data for reasons
    """
    __tablename__ = "lead_audit_log"

    # Primary Key
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)

    # Lead Identification
    # Note: lead_id is optional - not all events have a DB lead record
    # company_name is denormalized for fast querying without joins
    lead_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    company_name = Column(String(255), nullable=False, index=True)

    # Session Tracking
    # Groups all events from a single pipeline run
    session_id = Column(String(100), nullable=False, index=True)

    # Event Details
    event_type = Column(String(50), nullable=False, index=True)
    stage = Column(String(50), nullable=False)

    # Decision Context (JSONB for flexibility)
    # Structure varies by event_type - see docstrings for examples
    decision_data = Column(JSONB, nullable=False, default=dict)

    # Source Tracking
    source_file = Column(String(255), nullable=True)  # CSV filename
    source_row = Column(Integer, nullable=True)  # Row number in CSV

    # Metadata
    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True
    )
    created_by = Column(String(100), default="system")  # user or agent ID

    # Performance Metrics
    latency_ms = Column(Integer, nullable=True)  # How long this stage took
    cost_usd = Column(Numeric(10, 6), nullable=True)  # API costs

    # Composite indexes for common query patterns
    __table_args__ = (
        # Session + event type for "what happened in this run?"
        Index('idx_lead_audit_session_event', 'session_id', 'event_type'),
        # Company + created for "recent activity for this company"
        Index('idx_lead_audit_company_created', 'company_name', 'created_at'),
    )

    def __repr__(self) -> str:
        return (
            f"<LeadAuditLog("
            f"company='{self.company_name}', "
            f"event='{self.event_type}', "
            f"stage='{self.stage}'"
            f")>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "id": str(self.id) if self.id else None,
            "lead_id": str(self.lead_id) if self.lead_id else None,
            "company_name": self.company_name,
            "session_id": self.session_id,
            "event_type": self.event_type,
            "stage": self.stage,
            "decision_data": self.decision_data,
            "source_file": self.source_file,
            "source_row": self.source_row,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "created_by": self.created_by,
            "latency_ms": self.latency_ms,
            "cost_usd": float(self.cost_usd) if self.cost_usd else None,
        }


# Decision data structure examples for documentation
DECISION_DATA_EXAMPLES = {
    LeadAuditEventType.LEAD_IMPORTED: {
        "source_columns": ["company_name", "phone", "website"],
        "oem_count": 3,
        "coperniq_score": 85,
        "original_tier": "gold"
    },
    LeadAuditEventType.LEAD_QUALIFIED: {
        "score": 85,
        "tier": "gold",
        "is_atl": True,
        "website_found": True,
        "email_extracted": True,
        "oem_brands_matched": ["Generac", "Tesla"],
        "scoring_factors": {
            "oem_count": 20,
            "website_quality": 15,
            "email_found": 10
        }
    },
    LeadAuditEventType.LEAD_ENRICHED: {
        "sources_tried": ["hunter", "apollo", "website_scrape"],
        "sources_succeeded": ["hunter"],
        "contacts_found": 3,
        "atl_contacts": 2,
        "btl_contacts": 1,
        "emails_found": 2,
        "phones_found": 1,
        "linkedin_urls_found": 2
    },
    LeadAuditEventType.DEDUP_SKIP_DUPLICATE: {
        "recommendation": "skip_duplicate",
        "company_confidence": 92,
        "contact_confidence": 100,
        "matched_lead_id": "abc-123-def",
        "matched_company_name": "ABC Corp",
        "match_reasons": ["exact_email_match", "company_name_85%_fuzzy"],
        "existing_contacts": 2
    },
    LeadAuditEventType.LEAD_EXPORTED: {
        "output_file": "MEP_enriched_gold_20251126.csv",
        "row_number": 15,
        "dedup_status": "create_new",
        "final_score": 85,
        "contacts_exported": 2,
        "export_columns": ["company_name", "contact_name", "email", "score"]
    }
}
