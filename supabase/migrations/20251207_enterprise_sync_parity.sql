-- =============================================================================
-- MIGRATION: Full Field Parity with Close CRM (Dec 7, 2025)
-- =============================================================================
-- Adds all missing columns required for bidirectional sync with Close CRM.
-- Ensures no data loss during sync operations.
-- Based on Close API: https://developer.close.com/resources/
-- =============================================================================

-- ============================================================================
-- PART 1: dim_companies (Close Leads) - Additional Fields
-- ============================================================================

-- Display name (may differ from company_name)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS display_name VARCHAR(255);

-- Description/notes
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS description TEXT;

-- Close status tracking
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_status_id VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_status_label VARCHAR(100);

-- Full address fields
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS country VARCHAR(100);

-- User assignment tracking
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_created_by_id VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_updated_by_id VARCHAR(100);

-- Close timestamps
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_created_at TIMESTAMPTZ;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_updated_at TIMESTAMPTZ;

-- Opportunities and tasks (JSON snapshots)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS opportunities_json JSONB DEFAULT '[]';
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS tasks_json JSONB DEFAULT '[]';

-- HTML URL for direct linking
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_html_url VARCHAR(500);

-- Integration links
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS integration_links JSONB DEFAULT '[]';

-- Custom fields parity (Coperniq-specific)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS qualification_score INTEGER DEFAULT 0;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_atl BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS priority_label VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS lead_tier VARCHAR(50);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS employee_count INTEGER;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS annual_revenue DECIMAL(15,2);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS source_campaign VARCHAR(255);

-- Sync metadata
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS sync_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS sync_error TEXT;

-- Indexes for new fields
CREATE INDEX IF NOT EXISTS idx_dim_companies_status_id ON dim_companies(close_status_id);
CREATE INDEX IF NOT EXISTS idx_dim_companies_created_by ON dim_companies(close_created_by_id);
CREATE INDEX IF NOT EXISTS idx_dim_companies_qualification ON dim_companies(qualification_score DESC);
CREATE INDEX IF NOT EXISTS idx_dim_companies_sync_status ON dim_companies(sync_status);

-- ============================================================================
-- PART 2: dim_contacts (Close Contacts) - Additional Fields  
-- ============================================================================

-- Close CRM IDs
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_contact_id VARCHAR(100);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_lead_id VARCHAR(100);

-- All emails (JSON array - Close stores multiple)
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS emails_all JSONB DEFAULT '[]';

-- All phones (JSON array - Close stores multiple)
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS phones_all JSONB DEFAULT '[]';

-- All URLs (JSON array)
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS urls_all JSONB DEFAULT '[]';

-- User assignment
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_created_by_id VARCHAR(100);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_updated_by_id VARCHAR(100);

-- Close timestamps
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_created_at TIMESTAMPTZ;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_updated_at TIMESTAMPTZ;

-- Sync metadata
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS sync_status VARCHAR(50) DEFAULT 'pending';

-- Indexes
CREATE INDEX IF NOT EXISTS idx_dim_contacts_close_id ON dim_contacts(close_contact_id);
CREATE INDEX IF NOT EXISTS idx_dim_contacts_close_lead ON dim_contacts(close_lead_id);

-- ============================================================================
-- PART 3: fact_close_activities - Additional Fields
-- ============================================================================

-- Note fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS note_content TEXT;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS note_content_html TEXT;

-- Email additional fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_envelope JSONB;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_template_id VARCHAR(100);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_attachments JSONB DEFAULT '[]';

-- Call additional fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS call_transferred_from VARCHAR(100);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS call_transferred_to VARCHAR(100);

-- Meeting additional fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS meeting_calendar_link VARCHAR(500);

-- Timestamps
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS activity_at TIMESTAMPTZ;

-- Sequence additional fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS sequence_subscription_id VARCHAR(100);

-- ============================================================================
-- PART 4: sync_checkpoints - For LangGraph-style State Management
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_checkpoints (
    checkpoint_id VARCHAR(100) PRIMARY KEY,
    thread_id VARCHAR(100) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    last_close_cursor VARCHAR(255),
    last_supabase_cursor VARCHAR(255),
    processed_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    status VARCHAR(50) DEFAULT 'pending',
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_checkpoints_thread ON sync_checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_checkpoints_entity ON sync_checkpoints(entity_type);
CREATE INDEX IF NOT EXISTS idx_checkpoints_status ON sync_checkpoints(status);

-- ============================================================================
-- PART 5: sync_audit_log - Enterprise Audit Trail
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_audit_log (
    entry_id VARCHAR(100) PRIMARY KEY,
    operation VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    close_id VARCHAR(100),
    supabase_id VARCHAR(100),
    user_id VARCHAR(100),
    before_data_hash VARCHAR(100),
    after_data_hash VARCHAR(100),
    changed_fields JSONB DEFAULT '[]',
    metadata JSONB DEFAULT '{}',
    status VARCHAR(50) DEFAULT 'success',
    error_message TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    ip_address VARCHAR(50),
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_audit_operation ON sync_audit_log(operation);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON sync_audit_log(entity_type);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON sync_audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_close_id ON sync_audit_log(close_id);
CREATE INDEX IF NOT EXISTS idx_audit_status ON sync_audit_log(status);

-- Partition by month for performance (optional, for high-volume)
-- CREATE INDEX IF NOT EXISTS idx_audit_month ON sync_audit_log(date_trunc('month', timestamp));

-- ============================================================================
-- PART 6: sync_conflicts - Manual Conflict Resolution Queue
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_conflicts (
    conflict_id VARCHAR(100) PRIMARY KEY,
    entity_type VARCHAR(50) NOT NULL,
    close_id VARCHAR(100) NOT NULL,
    supabase_id VARCHAR(100),
    close_data JSONB NOT NULL,
    supabase_data JSONB NOT NULL,
    conflicting_fields JSONB DEFAULT '[]',
    close_updated_at TIMESTAMPTZ,
    supabase_updated_at TIMESTAMPTZ,
    resolved BOOLEAN DEFAULT FALSE,
    resolution JSONB,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_conflicts_entity ON sync_conflicts(entity_type);
CREATE INDEX IF NOT EXISTS idx_conflicts_resolved ON sync_conflicts(resolved);
CREATE INDEX IF NOT EXISTS idx_conflicts_created ON sync_conflicts(created_at DESC);

-- ============================================================================
-- PART 7: api_keys - API Key Management
-- ============================================================================

CREATE TABLE IF NOT EXISTS api_keys (
    id VARCHAR(100) PRIMARY KEY DEFAULT gen_random_uuid()::text,
    key_hash VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    user_id VARCHAR(100),
    organization_id VARCHAR(100),
    permissions JSONB DEFAULT '["read"]',
    is_active BOOLEAN DEFAULT TRUE,
    expires_at TIMESTAMPTZ,
    last_used_at TIMESTAMPTZ,
    usage_count INTEGER DEFAULT 0,
    rate_limit INTEGER DEFAULT 1000,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_keys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_keys_user ON api_keys(user_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_org ON api_keys(organization_id);
CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(is_active);

-- ============================================================================
-- PART 8: Row Level Security for New Tables
-- ============================================================================

ALTER TABLE sync_checkpoints ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE sync_conflicts ENABLE ROW LEVEL SECURITY;
ALTER TABLE api_keys ENABLE ROW LEVEL SECURITY;

-- Service role policies
CREATE POLICY "Service role full access to checkpoints"
ON sync_checkpoints FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to audit_log"
ON sync_audit_log FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to conflicts"
ON sync_conflicts FOR ALL TO service_role
USING (true) WITH CHECK (true);

CREATE POLICY "Service role full access to api_keys"
ON api_keys FOR ALL TO service_role
USING (true) WITH CHECK (true);

-- Authenticated user read policies
CREATE POLICY "Authenticated read checkpoints"
ON sync_checkpoints FOR SELECT TO authenticated
USING (true);

CREATE POLICY "Authenticated read audit_log"
ON sync_audit_log FOR SELECT TO authenticated
USING (true);

CREATE POLICY "Authenticated read conflicts"
ON sync_conflicts FOR SELECT TO authenticated
USING (true);

-- ============================================================================
-- PART 9: Update Triggers
-- ============================================================================

-- Auto-update updated_at on sync tables
CREATE OR REPLACE FUNCTION update_sync_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_checkpoints_timestamp
    BEFORE UPDATE ON sync_checkpoints
    FOR EACH ROW
    EXECUTE FUNCTION update_sync_timestamp();

CREATE TRIGGER update_api_keys_timestamp
    BEFORE UPDATE ON api_keys
    FOR EACH ROW
    EXECUTE FUNCTION update_sync_timestamp();

-- ============================================================================
-- COMMENTS for Documentation
-- ============================================================================

COMMENT ON TABLE sync_checkpoints IS 'LangGraph-style checkpoints for resumable sync operations';
COMMENT ON TABLE sync_audit_log IS 'Enterprise audit trail for all sync operations';
COMMENT ON TABLE sync_conflicts IS 'Queue for manual conflict resolution';
COMMENT ON TABLE api_keys IS 'API key management with permissions and rate limiting';

COMMENT ON COLUMN dim_companies.close_status_id IS 'Close CRM status ID (stat_xxx)';
COMMENT ON COLUMN dim_companies.qualification_score IS 'ICP qualification score 0-100';
COMMENT ON COLUMN dim_companies.sync_status IS 'Sync status: pending, synced, error';

COMMENT ON COLUMN sync_checkpoints.thread_id IS 'Unique thread identifier for sync session';
COMMENT ON COLUMN sync_checkpoints.metadata IS 'JSON metadata including last_bidirectional_sync timestamp';

COMMENT ON COLUMN sync_audit_log.before_data_hash IS 'SHA-256 hash of data before change';
COMMENT ON COLUMN sync_audit_log.after_data_hash IS 'SHA-256 hash of data after change';
