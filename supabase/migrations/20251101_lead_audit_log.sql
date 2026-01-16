-- Lead Audit Trail for GTM Agent Context
-- Tracks every decision made about every lead
-- Created: 2025-11-26

-- Drop existing objects if re-running migration
DROP TABLE IF EXISTS lead_audit_log CASCADE;

CREATE TABLE lead_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Lead Identification
    lead_id UUID,  -- Optional reference to leads table
    company_name VARCHAR(255) NOT NULL,  -- Denormalized for fast querying

    -- Session Tracking (ties to pipeline run)
    session_id VARCHAR(100) NOT NULL,

    -- Event Details
    event_type VARCHAR(50) NOT NULL,
    -- Values: lead_imported, lead_qualified, lead_enriched, dedup_create_new,
    --         dedup_add_contact, dedup_skip_duplicate, dedup_update_existing,
    --         lead_exported, status_changed, etc.

    stage VARCHAR(50) NOT NULL,
    -- Values: import, qualification, crm_check, enrichment, deduplication, export

    -- Decision Context (JSON for flexibility)
    decision_data JSONB NOT NULL DEFAULT '{}',
    -- Examples:
    -- qualification: {"score": 85, "tier": "gold", "is_atl": true, "oem_count": 3}
    -- enrichment: {"source": "hunter", "emails_found": 2, "phones_found": 1}
    -- dedup: {"action": "skip_duplicate", "matched_lead_id": "uuid", "confidence": 92}

    -- Source Tracking
    source_file VARCHAR(255),         -- CSV filename
    source_row INTEGER,               -- Row number in CSV

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',  -- user or agent identifier

    -- Performance Metrics
    latency_ms INTEGER,               -- How long this stage took
    cost_usd DECIMAL(10, 6)           -- API costs for this operation
);

-- Indexes for GTM agent queries
-- Query pattern: "What happened to this company?"
CREATE INDEX idx_lead_audit_company ON lead_audit_log(company_name);

-- Query pattern: "What happened in this pipeline run?"
CREATE INDEX idx_lead_audit_session ON lead_audit_log(session_id);

-- Query pattern: "Show me all dedup decisions"
CREATE INDEX idx_lead_audit_event ON lead_audit_log(event_type);

-- Query pattern: "What happened recently?"
CREATE INDEX idx_lead_audit_created ON lead_audit_log(created_at DESC);

-- Query pattern: "Get audit trail for specific lead"
CREATE INDEX idx_lead_audit_lead_id ON lead_audit_log(lead_id);

-- Composite index for session + event type queries
CREATE INDEX idx_lead_audit_session_event ON lead_audit_log(session_id, event_type);

-- GIN index for JSONB queries (e.g., find all leads with score > 80)
CREATE INDEX idx_lead_audit_decision_data ON lead_audit_log USING GIN (decision_data);

-- Table comment for documentation
COMMENT ON TABLE lead_audit_log IS 'Audit trail for lead lifecycle - used by GTM agents for context on lead history, dedup decisions, and processing status';

-- Column comments
COMMENT ON COLUMN lead_audit_log.decision_data IS 'JSONB containing stage-specific decision context (scores, sources, match reasons)';
COMMENT ON COLUMN lead_audit_log.session_id IS 'Pipeline execution session ID - groups all events from one batch import';
COMMENT ON COLUMN lead_audit_log.event_type IS 'Type of audit event (lead_imported, lead_qualified, dedup_*, lead_exported, etc.)';

-- Verify creation
SELECT 'lead_audit_log table created successfully' AS status;
