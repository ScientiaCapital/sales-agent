-- =============================================================================
-- MIGRATION: Enterprise Bidirectional Sync - Complete Field Parity
-- Date: December 7, 2025
-- Purpose: Ensure zero data loss during Close CRM ↔ Supabase sync
-- =============================================================================

-- ============================================================================
-- PART 1: dim_companies - Complete Close Lead Field Parity
-- ============================================================================

-- Core identification
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_lead_id VARCHAR(100) UNIQUE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS display_name VARCHAR(255);

-- Full address fields (Close stores as addresses[] array)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS address_line1 VARCHAR(255);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS address_line2 VARCHAR(255);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS city VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS state VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS postal_code VARCHAR(20);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS country VARCHAR(100);

-- Status tracking
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_status_id VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_status_label VARCHAR(100);

-- User assignment tracking
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_created_by_id VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_updated_by_id VARCHAR(100);

-- Close timestamps
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_created_at TIMESTAMPTZ;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_updated_at TIMESTAMPTZ;

-- Related entities (JSON snapshots for reference without additional API calls)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS opportunities_json JSONB DEFAULT '[]';
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS tasks_json JSONB DEFAULT '[]';
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS contacts_json JSONB DEFAULT '[]';
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS activities_json JSONB DEFAULT '[]';

-- URLs and links
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_html_url VARCHAR(500);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS integration_links JSONB DEFAULT '[]';

-- Custom fields (JSONB for flexibility)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_custom_fields JSONB DEFAULT '{}';

-- Raw data backup (full API response for recovery)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_raw_data JSONB;

-- Sync metadata
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS sync_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS sync_error TEXT;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS sync_direction VARCHAR(50);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS sync_version INTEGER DEFAULT 1;

-- Coperniq-specific enrichment fields
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS qualification_score INTEGER DEFAULT 0;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_atl BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS atl_count INTEGER DEFAULT 0;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS priority_label VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS lead_tier VARCHAR(50);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS employee_count INTEGER;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS annual_revenue DECIMAL(15,2);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS source_campaign VARCHAR(255);

-- ============================================================================
-- PART 2: dim_contacts - Complete Close Contact Field Parity  
-- ============================================================================

-- Close CRM IDs
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_contact_id VARCHAR(100) UNIQUE;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_lead_id VARCHAR(100);

-- Full name handling
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS full_name VARCHAR(255);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS first_name VARCHAR(100);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS last_name VARCHAR(100);

-- All emails (Close stores as emails[] array)
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS email_primary VARCHAR(255);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS email_secondary VARCHAR(255);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS emails_all JSONB DEFAULT '[]';

-- All phones (Close stores as phones[] array)
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS phone_primary VARCHAR(50);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS phone_primary_type VARCHAR(50);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS phone_secondary VARCHAR(50);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS phone_secondary_type VARCHAR(50);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS phones_all JSONB DEFAULT '[]';

-- All URLs (Close stores as urls[] array)
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS twitter_url VARCHAR(500);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS urls_all JSONB DEFAULT '[]';

-- User assignment
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_created_by_id VARCHAR(100);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_updated_by_id VARCHAR(100);

-- Close timestamps
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_created_at TIMESTAMPTZ;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_updated_at TIMESTAMPTZ;

-- Custom fields
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_custom_fields JSONB DEFAULT '{}';

-- Raw data backup
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_raw_data JSONB;

-- Sync metadata
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS sync_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS sync_error TEXT;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS sync_version INTEGER DEFAULT 1;

-- Contact enrichment flags
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS is_atl BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS enrichment_source VARCHAR(100);

-- ============================================================================
-- PART 3: fact_close_activities - Complete Activity Field Parity
-- ============================================================================

-- Ensure table exists with proper structure
CREATE TABLE IF NOT EXISTS fact_close_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    close_activity_id VARCHAR(100) UNIQUE,
    activity_type VARCHAR(50) NOT NULL,
    close_lead_id VARCHAR(100),
    close_contact_id VARCHAR(100),
    close_user_id VARCHAR(100),
    direction VARCHAR(20),
    status VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Email-specific fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS subject VARCHAR(500);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS body_text TEXT;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS body_html TEXT;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_to JSONB DEFAULT '[]';
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_cc JSONB DEFAULT '[]';
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_bcc JSONB DEFAULT '[]';
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_from VARCHAR(255);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_envelope JSONB;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_template_id VARCHAR(100);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_attachments JSONB DEFAULT '[]';
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_opens INTEGER DEFAULT 0;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_clicks INTEGER DEFAULT 0;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS email_bounced BOOLEAN DEFAULT FALSE;

-- Note-specific fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS note_content TEXT;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS note_content_html TEXT;

-- Call-specific fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS call_duration INTEGER;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS call_recording_url VARCHAR(500);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS call_voicemail_url VARCHAR(500);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS call_phone VARCHAR(50);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS call_disposition VARCHAR(100);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS call_transferred_from VARCHAR(100);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS call_transferred_to VARCHAR(100);

-- SMS-specific fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS sms_text TEXT;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS sms_phone VARCHAR(50);

-- Meeting-specific fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS meeting_title VARCHAR(255);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS meeting_starts_at TIMESTAMPTZ;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS meeting_ends_at TIMESTAMPTZ;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS meeting_attendees JSONB DEFAULT '[]';
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS meeting_location VARCHAR(255);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS meeting_calendar_link VARCHAR(500);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS meeting_is_recurring BOOLEAN DEFAULT FALSE;

-- Sequence-related fields
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS sequence_id VARCHAR(100);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS sequence_name VARCHAR(255);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS sequence_subscription_id VARCHAR(100);
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS sequence_step INTEGER;

-- Timestamps
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS activity_at TIMESTAMPTZ;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS close_created_at TIMESTAMPTZ;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS close_updated_at TIMESTAMPTZ;

-- Raw data backup
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS close_raw_data JSONB;

-- Sync metadata
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS last_sync_at TIMESTAMPTZ;
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS sync_status VARCHAR(50) DEFAULT 'pending';
ALTER TABLE fact_close_activities ADD COLUMN IF NOT EXISTS sync_version INTEGER DEFAULT 1;

-- ============================================================================
-- PART 4: sync_checkpoints - LangGraph-style State Management
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_checkpoints (
    checkpoint_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    thread_id VARCHAR(100) NOT NULL,
    parent_checkpoint_id UUID REFERENCES sync_checkpoints(checkpoint_id),
    entity_type VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    
    -- Cursors for pagination
    close_cursor VARCHAR(500),
    close_cursor_field VARCHAR(100),
    supabase_cursor VARCHAR(500),
    supabase_cursor_field VARCHAR(100),
    
    -- Counters
    processed_count INTEGER DEFAULT 0,
    created_count INTEGER DEFAULT 0,
    updated_count INTEGER DEFAULT 0,
    deleted_count INTEGER DEFAULT 0,
    skipped_count INTEGER DEFAULT 0,
    error_count INTEGER DEFAULT 0,
    conflict_count INTEGER DEFAULT 0,
    
    -- State data (LangGraph compatible)
    state_data JSONB DEFAULT '{}',
    messages JSONB DEFAULT '[]',
    
    -- Status
    status VARCHAR(50) DEFAULT 'pending',
    error_message TEXT,
    
    -- Timestamps
    started_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Metadata
    metadata JSONB DEFAULT '{}',
    
    CONSTRAINT valid_direction CHECK (direction IN ('close_to_supabase', 'supabase_to_close', 'bidirectional')),
    CONSTRAINT valid_entity CHECK (entity_type IN ('lead', 'contact', 'activity', 'all')),
    CONSTRAINT valid_status CHECK (status IN ('pending', 'running', 'paused', 'completed', 'error', 'cancelled'))
);

-- Create index for checkpoint lookups
CREATE INDEX IF NOT EXISTS idx_sync_checkpoints_thread ON sync_checkpoints(thread_id);
CREATE INDEX IF NOT EXISTS idx_sync_checkpoints_status ON sync_checkpoints(status);
CREATE INDEX IF NOT EXISTS idx_sync_checkpoints_entity ON sync_checkpoints(entity_type);
CREATE INDEX IF NOT EXISTS idx_sync_checkpoints_created ON sync_checkpoints(created_at DESC);

-- ============================================================================
-- PART 5: sync_audit_log - Enterprise Audit Trail
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_audit_log (
    entry_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Operation details
    operation VARCHAR(50) NOT NULL,
    entity_type VARCHAR(50) NOT NULL,
    direction VARCHAR(50) NOT NULL,
    
    -- Entity references
    close_id VARCHAR(100),
    supabase_id UUID,
    
    -- User/system tracking
    performed_by VARCHAR(100),
    performed_by_type VARCHAR(50) DEFAULT 'system',
    
    -- Change tracking
    before_data JSONB,
    after_data JSONB,
    before_data_hash VARCHAR(64),
    after_data_hash VARCHAR(64),
    changed_fields JSONB DEFAULT '[]',
    
    -- Result
    status VARCHAR(50) DEFAULT 'success',
    error_message TEXT,
    error_code VARCHAR(50),
    
    -- Metadata
    checkpoint_id UUID REFERENCES sync_checkpoints(checkpoint_id),
    request_id VARCHAR(100),
    correlation_id VARCHAR(100),
    
    -- Timestamps
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    duration_ms INTEGER,
    
    -- Security
    ip_address VARCHAR(50),
    user_agent TEXT,
    
    CONSTRAINT valid_operation CHECK (operation IN (
        'create', 'update', 'delete', 'skip', 'conflict', 'error', 'resolve'
    )),
    CONSTRAINT valid_audit_status CHECK (status IN ('success', 'failure', 'partial'))
);

-- Indexes for audit queries
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON sync_audit_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_operation ON sync_audit_log(operation);
CREATE INDEX IF NOT EXISTS idx_audit_log_entity ON sync_audit_log(entity_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_close_id ON sync_audit_log(close_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_supabase_id ON sync_audit_log(supabase_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_status ON sync_audit_log(status);
CREATE INDEX IF NOT EXISTS idx_audit_log_correlation ON sync_audit_log(correlation_id);

-- Partial index for errors (query optimization)
CREATE INDEX IF NOT EXISTS idx_audit_log_errors ON sync_audit_log(timestamp DESC) 
WHERE status = 'failure';

-- ============================================================================
-- PART 6: sync_conflicts - Conflict Resolution Queue
-- ============================================================================

CREATE TABLE IF NOT EXISTS sync_conflicts (
    conflict_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    
    -- Entity identification
    entity_type VARCHAR(50) NOT NULL,
    close_id VARCHAR(100) NOT NULL,
    supabase_id UUID,
    
    -- Conflict data
    close_data JSONB NOT NULL,
    supabase_data JSONB NOT NULL,
    conflicting_fields JSONB DEFAULT '[]',
    conflict_type VARCHAR(50) NOT NULL,
    
    -- Timestamps from both systems
    close_updated_at TIMESTAMPTZ,
    supabase_updated_at TIMESTAMPTZ,
    
    -- Resolution tracking
    resolved BOOLEAN DEFAULT FALSE,
    resolution_strategy VARCHAR(50),
    resolution_data JSONB,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    
    -- Priority and tracking
    priority VARCHAR(20) DEFAULT 'normal',
    auto_resolvable BOOLEAN DEFAULT FALSE,
    retry_count INTEGER DEFAULT 0,
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Metadata
    checkpoint_id UUID REFERENCES sync_checkpoints(checkpoint_id),
    audit_entry_id UUID REFERENCES sync_audit_log(entry_id),
    
    CONSTRAINT valid_conflict_type CHECK (conflict_type IN (
        'timestamp', 'delete', 'schema', 'duplicate', 'validation'
    )),
    CONSTRAINT valid_priority CHECK (priority IN ('low', 'normal', 'high', 'critical'))
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_conflicts_resolved ON sync_conflicts(resolved);
CREATE INDEX IF NOT EXISTS idx_conflicts_entity ON sync_conflicts(entity_type);
CREATE INDEX IF NOT EXISTS idx_conflicts_priority ON sync_conflicts(priority) WHERE resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_conflicts_created ON sync_conflicts(created_at DESC);

-- ============================================================================
-- PART 7: Performance Indexes
-- ============================================================================

-- dim_companies sync indexes
CREATE INDEX IF NOT EXISTS idx_companies_close_lead_id ON dim_companies(close_lead_id);
CREATE INDEX IF NOT EXISTS idx_companies_close_status ON dim_companies(close_status_id);
CREATE INDEX IF NOT EXISTS idx_companies_sync_status ON dim_companies(sync_status);
CREATE INDEX IF NOT EXISTS idx_companies_last_sync ON dim_companies(last_sync_at DESC);
CREATE INDEX IF NOT EXISTS idx_companies_close_updated ON dim_companies(close_updated_at DESC);

-- dim_contacts sync indexes
CREATE INDEX IF NOT EXISTS idx_contacts_close_contact_id ON dim_contacts(close_contact_id);
CREATE INDEX IF NOT EXISTS idx_contacts_close_lead_id ON dim_contacts(close_lead_id);
CREATE INDEX IF NOT EXISTS idx_contacts_sync_status ON dim_contacts(sync_status);
CREATE INDEX IF NOT EXISTS idx_contacts_last_sync ON dim_contacts(last_sync_at DESC);
CREATE INDEX IF NOT EXISTS idx_contacts_is_atl ON dim_contacts(is_atl) WHERE is_atl = TRUE;

-- fact_close_activities sync indexes
CREATE INDEX IF NOT EXISTS idx_activities_close_id ON fact_close_activities(close_activity_id);
CREATE INDEX IF NOT EXISTS idx_activities_close_lead ON fact_close_activities(close_lead_id);
CREATE INDEX IF NOT EXISTS idx_activities_type ON fact_close_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_activities_activity_at ON fact_close_activities(activity_at DESC);
CREATE INDEX IF NOT EXISTS idx_activities_sync_status ON fact_close_activities(sync_status);

-- GIN indexes for JSONB columns
CREATE INDEX IF NOT EXISTS idx_companies_custom_fields_gin ON dim_companies USING gin(close_custom_fields);
CREATE INDEX IF NOT EXISTS idx_contacts_emails_all_gin ON dim_contacts USING gin(emails_all);
CREATE INDEX IF NOT EXISTS idx_contacts_phones_all_gin ON dim_contacts USING gin(phones_all);
CREATE INDEX IF NOT EXISTS idx_activities_attachments_gin ON fact_close_activities USING gin(email_attachments);

-- ============================================================================
-- PART 8: Triggers for Updated Timestamps
-- ============================================================================

-- Generic update trigger function
CREATE OR REPLACE FUNCTION update_updated_at_trigger()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply to sync tables
DROP TRIGGER IF EXISTS update_sync_checkpoints_updated ON sync_checkpoints;
CREATE TRIGGER update_sync_checkpoints_updated
    BEFORE UPDATE ON sync_checkpoints
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_trigger();

DROP TRIGGER IF EXISTS update_sync_conflicts_updated ON sync_conflicts;
CREATE TRIGGER update_sync_conflicts_updated
    BEFORE UPDATE ON sync_conflicts
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_trigger();

-- ============================================================================
-- PART 9: Comments for Documentation
-- ============================================================================

-- Table comments
COMMENT ON TABLE sync_checkpoints IS 'LangGraph-compatible checkpoints for resumable sync operations';
COMMENT ON TABLE sync_audit_log IS 'Enterprise audit trail for all sync operations (SOC2 compliant)';
COMMENT ON TABLE sync_conflicts IS 'Queue for manual conflict resolution between Close and Supabase';

-- Column comments for key fields
COMMENT ON COLUMN dim_companies.close_raw_data IS 'Complete Close API response for data recovery';
COMMENT ON COLUMN dim_companies.sync_version IS 'Optimistic locking version for concurrent sync protection';
COMMENT ON COLUMN sync_checkpoints.state_data IS 'LangGraph state data for agent resumption';
COMMENT ON COLUMN sync_checkpoints.messages IS 'LangGraph message history for context';
COMMENT ON COLUMN sync_audit_log.correlation_id IS 'Links related audit entries across distributed operations';
