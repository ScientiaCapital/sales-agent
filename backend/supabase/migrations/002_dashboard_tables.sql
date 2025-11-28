-- Dashboard Tables for CEO/CTO + Sr. BDR Lead Lifecycle Dashboard
-- Created: 2025-11-28
-- Purpose: Track lead imports, current state, Close CRM activities, and pipeline alerts

-- ============================================================================
-- TABLE: list_imports
-- Track CSV imports from dealer-scraper-mvp with field availability
-- ============================================================================
CREATE TABLE IF NOT EXISTS list_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_rows INTEGER NOT NULL,

    -- Field availability (what data was included in the import)
    has_company_name BOOLEAN DEFAULT TRUE,
    has_phone BOOLEAN DEFAULT FALSE,
    has_email BOOLEAN DEFAULT FALSE,
    has_website BOOLEAN DEFAULT FALSE,
    has_contact_name BOOLEAN DEFAULT FALSE,
    has_oem_certifications BOOLEAN DEFAULT FALSE,

    -- Source tracking
    source VARCHAR(50) DEFAULT 'dealer-scraper-mvp',
    notes TEXT,

    -- Processing status
    processed_count INTEGER DEFAULT 0,
    qualified_count INTEGER DEFAULT 0,
    enriched_count INTEGER DEFAULT 0,
    exported_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for list_imports
CREATE INDEX IF NOT EXISTS idx_list_imports_date ON list_imports(imported_at DESC);
CREATE INDEX IF NOT EXISTS idx_list_imports_source ON list_imports(source);

COMMENT ON TABLE list_imports IS 'Track CSV imports from dealer-scraper-mvp with field availability and processing status';

-- ============================================================================
-- TABLE: lead_current_state
-- Denormalized current state per lead for fast dashboard queries
-- This is the "read model" in CQRS pattern - derived from lead_audit_log
-- ============================================================================
CREATE TABLE IF NOT EXISTS lead_current_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL UNIQUE,

    -- Link to import batch
    import_id UUID REFERENCES list_imports(id),

    -- Current pipeline stage
    current_stage VARCHAR(50) NOT NULL DEFAULT 'imported',
    -- Values: imported, qualified, enriched, in_close, contacted, meeting_booked, opportunity, won, lost

    -- Qualification data
    qualification_score INTEGER,
    is_atl BOOLEAN DEFAULT FALSE,
    oem_count INTEGER DEFAULT 0,

    -- Close CRM link
    close_lead_id VARCHAR(100),
    close_status VARCHAR(50),  -- Hot ATL, Validated ATL, BTL, etc.

    -- Outreach tracking
    last_contacted_at TIMESTAMPTZ,
    last_contact_method VARCHAR(20),  -- call, email, sms
    total_calls INTEGER DEFAULT 0,
    total_emails INTEGER DEFAULT 0,
    total_sms INTEGER DEFAULT 0,

    -- Alert status
    needs_attention BOOLEAN DEFAULT FALSE,
    attention_reason VARCHAR(255),
    stuck_since TIMESTAMPTZ,

    -- Contact data quality
    has_email BOOLEAN DEFAULT FALSE,
    has_phone BOOLEAN DEFAULT FALSE,
    has_website BOOLEAN DEFAULT FALSE,
    contact_count INTEGER DEFAULT 0,
    atl_contact_count INTEGER DEFAULT 0,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for lead_current_state
CREATE INDEX IF NOT EXISTS idx_lead_state_stage ON lead_current_state(current_stage);
CREATE INDEX IF NOT EXISTS idx_lead_state_attention ON lead_current_state(needs_attention) WHERE needs_attention = TRUE;
CREATE INDEX IF NOT EXISTS idx_lead_state_close_id ON lead_current_state(close_lead_id) WHERE close_lead_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_lead_state_import ON lead_current_state(import_id);
CREATE INDEX IF NOT EXISTS idx_lead_state_updated ON lead_current_state(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_state_created ON lead_current_state(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_state_score ON lead_current_state(qualification_score DESC NULLS LAST);

COMMENT ON TABLE lead_current_state IS 'Denormalized current state per lead - CQRS read model derived from lead_audit_log events';

-- ============================================================================
-- TABLE: close_activities
-- Synced from Close CRM Activities API
-- ============================================================================
CREATE TABLE IF NOT EXISTS close_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Close CRM identifiers
    close_activity_id VARCHAR(100) UNIQUE NOT NULL,
    close_lead_id VARCHAR(100) NOT NULL,
    close_user_id VARCHAR(100),

    -- Activity details
    activity_type VARCHAR(50) NOT NULL,  -- Call, Email, SMS, Meeting, Note
    direction VARCHAR(20),               -- inbound, outbound
    status VARCHAR(50),                  -- completed, missed, scheduled, sent, received

    -- Activity metadata
    duration_seconds INTEGER,            -- For calls
    subject VARCHAR(500),                -- For emails
    body_preview TEXT,                   -- First 500 chars

    -- Timestamps
    activity_date TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for close_activities
CREATE INDEX IF NOT EXISTS idx_close_activities_lead ON close_activities(close_lead_id);
CREATE INDEX IF NOT EXISTS idx_close_activities_type ON close_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_close_activities_date ON close_activities(activity_date DESC);
CREATE INDEX IF NOT EXISTS idx_close_activities_synced ON close_activities(synced_at DESC);

COMMENT ON TABLE close_activities IS 'Activities synced from Close CRM - calls, emails, SMS, meetings';

-- ============================================================================
-- TABLE: pipeline_alerts
-- Issues needing attention (stuck leads, failures, stale leads)
-- ============================================================================
CREATE TABLE IF NOT EXISTS pipeline_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    lead_state_id UUID REFERENCES lead_current_state(id),

    -- Alert classification
    alert_type VARCHAR(50) NOT NULL,
    -- Values: stuck (>24h in stage), failed (error), stale (no activity 7d), no_contact (qualified but 0 outreach)

    severity VARCHAR(20) NOT NULL,  -- critical, warning, info

    -- Alert details
    message TEXT NOT NULL,
    stage VARCHAR(50),

    -- Resolution tracking
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Indexes for pipeline_alerts
CREATE INDEX IF NOT EXISTS idx_alerts_unresolved ON pipeline_alerts(resolved, severity) WHERE resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_alerts_type ON pipeline_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_company ON pipeline_alerts(company_name);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON pipeline_alerts(created_at DESC);

COMMENT ON TABLE pipeline_alerts IS 'Pipeline issues needing attention - stuck, failed, stale leads';

-- ============================================================================
-- VIEW: v_pipeline_funnel
-- Aggregated funnel metrics by stage
-- ============================================================================
CREATE OR REPLACE VIEW v_pipeline_funnel AS
SELECT
    current_stage,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') as count_7d,
    COUNT(*) FILTER (WHERE created_at >= DATE_TRUNC('month', NOW())) as count_mtd,
    AVG(qualification_score) as avg_score,
    SUM(CASE WHEN needs_attention THEN 1 ELSE 0 END) as attention_count,
    SUM(CASE WHEN is_atl THEN 1 ELSE 0 END) as atl_count
FROM lead_current_state
GROUP BY current_stage
ORDER BY
    CASE current_stage
        WHEN 'imported' THEN 1
        WHEN 'qualified' THEN 2
        WHEN 'enriched' THEN 3
        WHEN 'in_close' THEN 4
        WHEN 'contacted' THEN 5
        WHEN 'meeting_booked' THEN 6
        WHEN 'opportunity' THEN 7
        WHEN 'won' THEN 8
        WHEN 'lost' THEN 9
        ELSE 10
    END;

COMMENT ON VIEW v_pipeline_funnel IS 'Aggregated lead counts by pipeline stage with 7d/MTD breakdowns';

-- ============================================================================
-- VIEW: v_outreach_summary
-- Close CRM activity summary
-- ============================================================================
CREATE OR REPLACE VIEW v_outreach_summary AS
SELECT
    activity_type,
    direction,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE activity_date >= NOW() - INTERVAL '7 days') as count_7d,
    COUNT(*) FILTER (WHERE activity_date >= DATE_TRUNC('month', NOW())) as count_mtd,
    AVG(duration_seconds) FILTER (WHERE activity_type = 'Call') as avg_call_duration
FROM close_activities
GROUP BY activity_type, direction
ORDER BY activity_type, direction;

COMMENT ON VIEW v_outreach_summary IS 'Aggregated Close CRM activity counts by type and direction';

-- ============================================================================
-- VIEW: v_import_history
-- Recent imports with processing progress
-- ============================================================================
CREATE OR REPLACE VIEW v_import_history AS
SELECT
    id,
    filename,
    imported_at,
    total_rows,
    has_company_name,
    has_phone,
    has_email,
    has_website,
    has_contact_name,
    source,
    processed_count,
    qualified_count,
    enriched_count,
    exported_count,
    failed_count,
    ROUND(100.0 * processed_count / NULLIF(total_rows, 0), 1) as progress_pct,
    ROUND(100.0 * qualified_count / NULLIF(processed_count, 0), 1) as qualification_rate
FROM list_imports
ORDER BY imported_at DESC;

COMMENT ON VIEW v_import_history IS 'Import batches with processing progress metrics';

-- ============================================================================
-- FUNCTION: update_lead_state_timestamp
-- Auto-update updated_at on lead_current_state changes
-- ============================================================================
CREATE OR REPLACE FUNCTION update_lead_state_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS lead_state_timestamp ON lead_current_state;
CREATE TRIGGER lead_state_timestamp
    BEFORE UPDATE ON lead_current_state
    FOR EACH ROW
    EXECUTE FUNCTION update_lead_state_timestamp();

-- ============================================================================
-- FUNCTION: check_stuck_leads
-- Find leads stuck in a stage for >24 hours and create alerts
-- Can be called by Celery Beat task
-- ============================================================================
CREATE OR REPLACE FUNCTION check_stuck_leads()
RETURNS INTEGER AS $$
DECLARE
    alert_count INTEGER := 0;
BEGIN
    -- Insert alerts for stuck leads (not already alerted)
    INSERT INTO pipeline_alerts (company_name, lead_state_id, alert_type, severity, message, stage)
    SELECT
        lcs.company_name,
        lcs.id,
        'stuck',
        CASE
            WHEN lcs.updated_at < NOW() - INTERVAL '72 hours' THEN 'critical'
            WHEN lcs.updated_at < NOW() - INTERVAL '48 hours' THEN 'warning'
            ELSE 'info'
        END,
        'Lead stuck in ' || lcs.current_stage || ' stage for ' ||
            EXTRACT(EPOCH FROM (NOW() - lcs.updated_at))/3600 || ' hours',
        lcs.current_stage
    FROM lead_current_state lcs
    WHERE lcs.updated_at < NOW() - INTERVAL '24 hours'
      AND lcs.current_stage NOT IN ('won', 'lost')  -- Ignore terminal states
      AND NOT EXISTS (
          SELECT 1 FROM pipeline_alerts pa
          WHERE pa.lead_state_id = lcs.id
            AND pa.alert_type = 'stuck'
            AND pa.resolved = FALSE
      );

    GET DIAGNOSTICS alert_count = ROW_COUNT;

    -- Update needs_attention flag on lead_current_state
    UPDATE lead_current_state
    SET needs_attention = TRUE,
        attention_reason = 'Stuck in stage > 24 hours',
        stuck_since = COALESCE(stuck_since, updated_at)
    WHERE updated_at < NOW() - INTERVAL '24 hours'
      AND current_stage NOT IN ('won', 'lost')
      AND needs_attention = FALSE;

    RETURN alert_count;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION check_stuck_leads IS 'Check for leads stuck in a stage >24h and create alerts. Called by Celery Beat.';

-- ============================================================================
-- Row Level Security (RLS) - Allow all for service role
-- ============================================================================
ALTER TABLE list_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_current_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE close_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_alerts ENABLE ROW LEVEL SECURITY;

-- Service role policies (full access for backend)
CREATE POLICY "Service role full access" ON list_imports FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON lead_current_state FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON close_activities FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON pipeline_alerts FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- Verify creation
SELECT 'Dashboard tables created successfully' AS status;
SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('list_imports', 'lead_current_state', 'close_activities', 'pipeline_alerts');
