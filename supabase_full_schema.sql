-- =============================================================================
-- SALES-AGENT SUPABASE FULL SCHEMA (FIXED ORDER)
-- =============================================================================
-- Run this in Supabase SQL Editor to initialize the database
-- Order: Dimensions (all) → Facts → Dashboard → Views → RLS
-- Generated: 2025-12-13 (Fixed dependency order)
-- =============================================================================

-- PART 1: DIMENSION TABLES (CREATE ALL FIRST, NO DATA)
-- =============================================================================

-- dim_companies: THE MASTER LEAD LIST (Single Source of Truth)
CREATE TABLE IF NOT EXISTS dim_companies (
    company_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255),
    domain VARCHAR(255),
    phone VARCHAR(50),
    website VARCHAR(500),
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    icp_score INTEGER CHECK (icp_score >= 0 AND icp_score <= 100),
    icp_tier VARCHAR(20) CHECK (icp_tier IN ('PLATINUM', 'GOLD', 'SILVER', 'BRONZE')),
    oem_brands JSONB DEFAULT '[]',
    license_types JSONB DEFAULT '[]',
    oem_count INTEGER DEFAULT 0,
    trade_count INTEGER DEFAULT 0,
    current_stage VARCHAR(50) DEFAULT 'imported',
    close_lead_id VARCHAR(100),
    source_type VARCHAR(50),
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_enriched_at TIMESTAMPTZ,
    last_activity_at TIMESTAMPTZ,
    total_activities INTEGER DEFAULT 0,
    email_opens INTEGER DEFAULT 0,
    flagged_for_reenrich BOOLEAN DEFAULT FALSE,
    needs_attention BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- dim_contacts: People at companies
CREATE TABLE IF NOT EXISTS dim_contacts (
    contact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES dim_companies(company_id) ON DELETE CASCADE,
    full_name VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    email VARCHAR(255),
    phone VARCHAR(50),
    title VARCHAR(255),
    is_atl BOOLEAN DEFAULT FALSE,
    department VARCHAR(100),
    seniority VARCHAR(50),
    linkedin_url VARCHAR(500),
    twitter_handle VARCHAR(100),
    confidence INTEGER DEFAULT 50,
    source VARCHAR(50),
    validated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- dim_users: Team members (BDRs, AEs)
CREATE TABLE IF NOT EXISTS dim_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    close_user_id VARCHAR(100) UNIQUE,
    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- dim_sources: Data origin tracking
CREATE TABLE IF NOT EXISTS dim_sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name VARCHAR(100) NOT NULL UNIQUE,
    source_type VARCHAR(50),
    project VARCHAR(100),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- PART 2: FACT TABLES (After all dimensions exist)
-- =============================================================================

CREATE TABLE IF NOT EXISTS fact_activities (
    activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    close_activity_id VARCHAR(100) UNIQUE,
    company_id UUID REFERENCES dim_companies(company_id),
    contact_id UUID REFERENCES dim_contacts(contact_id),
    user_id UUID REFERENCES dim_users(user_id),
    activity_type VARCHAR(50) NOT NULL,
    direction VARCHAR(20),
    outcome VARCHAR(100),
    duration_seconds INTEGER,
    subject VARCHAR(500),
    body_preview TEXT,
    activity_at TIMESTAMPTZ NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_opportunities (
    opportunity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    close_opportunity_id VARCHAR(100) UNIQUE,
    company_id UUID REFERENCES dim_companies(company_id),
    user_id UUID REFERENCES dim_users(user_id),
    stage VARCHAR(50),
    value_usd DECIMAL(12, 2),
    confidence INTEGER,
    lost_reason VARCHAR(255),
    competitor VARCHAR(255),
    created_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_pipeline_stages (
    stage_change_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES dim_companies(company_id),
    changed_by UUID REFERENCES dim_users(user_id),
    from_stage VARCHAR(50),
    to_stage VARCHAR(50) NOT NULL,
    changed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS fact_enrichments (
    enrichment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES dim_companies(company_id),
    source_id UUID REFERENCES dim_sources(source_id),
    method VARCHAR(50) NOT NULL,
    contacts_found INTEGER DEFAULT 0,
    atl_found INTEGER DEFAULT 0,
    emails_found INTEGER DEFAULT 0,
    cost_usd DECIMAL(10, 6) DEFAULT 0,
    latency_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    enriched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS re_enrich_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES dim_companies(company_id),
    company_name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    trigger_type VARCHAR(50) NOT NULL,
    triggered_by VARCHAR(100) DEFAULT 'system',
    priority INTEGER DEFAULT 2,
    notes TEXT,
    status VARCHAR(50) DEFAULT 'pending',
    result_summary JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

-- =============================================================================
-- PART 3: AUDIT LOG
-- =============================================================================

CREATE TABLE IF NOT EXISTS lead_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lead_id UUID,
    company_name VARCHAR(255) NOT NULL,
    session_id VARCHAR(100) NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    stage VARCHAR(50) NOT NULL,
    decision_data JSONB NOT NULL DEFAULT '{}',
    source_file VARCHAR(255),
    source_row INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by VARCHAR(100) DEFAULT 'system',
    latency_ms INTEGER,
    cost_usd DECIMAL(10, 6)
);

-- =============================================================================
-- PART 4: DASHBOARD TABLES
-- =============================================================================

CREATE TABLE IF NOT EXISTS list_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(255) NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_rows INTEGER NOT NULL,
    has_company_name BOOLEAN DEFAULT TRUE,
    has_phone BOOLEAN DEFAULT FALSE,
    has_email BOOLEAN DEFAULT FALSE,
    has_website BOOLEAN DEFAULT FALSE,
    has_contact_name BOOLEAN DEFAULT FALSE,
    has_oem_certifications BOOLEAN DEFAULT FALSE,
    source VARCHAR(50) DEFAULT 'dealer-scraper-mvp',
    notes TEXT,
    processed_count INTEGER DEFAULT 0,
    qualified_count INTEGER DEFAULT 0,
    enriched_count INTEGER DEFAULT 0,
    exported_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS lead_current_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL UNIQUE,
    import_id UUID REFERENCES list_imports(id),
    current_stage VARCHAR(50) NOT NULL DEFAULT 'imported',
    qualification_score INTEGER,
    is_atl BOOLEAN DEFAULT FALSE,
    oem_count INTEGER DEFAULT 0,
    close_lead_id VARCHAR(100),
    close_status VARCHAR(50),
    last_contacted_at TIMESTAMPTZ,
    last_contact_method VARCHAR(20),
    total_calls INTEGER DEFAULT 0,
    total_emails INTEGER DEFAULT 0,
    total_sms INTEGER DEFAULT 0,
    needs_attention BOOLEAN DEFAULT FALSE,
    attention_reason VARCHAR(255),
    stuck_since TIMESTAMPTZ,
    has_email BOOLEAN DEFAULT FALSE,
    has_phone BOOLEAN DEFAULT FALSE,
    has_website BOOLEAN DEFAULT FALSE,
    contact_count INTEGER DEFAULT 0,
    atl_contact_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS close_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    close_activity_id VARCHAR(100) UNIQUE NOT NULL,
    close_lead_id VARCHAR(100),
    close_user_id VARCHAR(100),
    activity_type VARCHAR(50) NOT NULL,
    direction VARCHAR(20),
    status VARCHAR(50),
    duration_seconds INTEGER,
    subject VARCHAR(500),
    body_preview TEXT,
    activity_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pipeline_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_name VARCHAR(255) NOT NULL,
    lead_state_id UUID REFERENCES lead_current_state(id),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL,
    message TEXT NOT NULL,
    stage VARCHAR(50),
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    resolved_by VARCHAR(100),
    resolution_notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =============================================================================
-- PART 5: INDEXES (After all tables exist)
-- =============================================================================

-- dim_companies indexes
CREATE INDEX IF NOT EXISTS idx_dim_companies_name ON dim_companies(company_name);
CREATE INDEX IF NOT EXISTS idx_dim_companies_normalized ON dim_companies(normalized_name);
CREATE INDEX IF NOT EXISTS idx_dim_companies_domain ON dim_companies(domain);
CREATE INDEX IF NOT EXISTS idx_dim_companies_tier ON dim_companies(icp_tier);
CREATE INDEX IF NOT EXISTS idx_dim_companies_score ON dim_companies(icp_score DESC);
CREATE INDEX IF NOT EXISTS idx_dim_companies_stage ON dim_companies(current_stage);
CREATE INDEX IF NOT EXISTS idx_dim_companies_close ON dim_companies(close_lead_id);
CREATE INDEX IF NOT EXISTS idx_dim_companies_reenrich ON dim_companies(flagged_for_reenrich) WHERE flagged_for_reenrich = TRUE;
CREATE INDEX IF NOT EXISTS idx_dim_companies_attention ON dim_companies(needs_attention) WHERE needs_attention = TRUE;

-- dim_contacts indexes
CREATE INDEX IF NOT EXISTS idx_dim_contacts_company ON dim_contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_dim_contacts_email ON dim_contacts(email);
CREATE INDEX IF NOT EXISTS idx_dim_contacts_atl ON dim_contacts(is_atl) WHERE is_atl = TRUE;

-- fact_activities indexes
CREATE INDEX IF NOT EXISTS idx_fact_activities_company ON fact_activities(company_id);
CREATE INDEX IF NOT EXISTS idx_fact_activities_user ON fact_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_fact_activities_type ON fact_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_fact_activities_date ON fact_activities(activity_at DESC);
CREATE INDEX IF NOT EXISTS idx_fact_activities_outcome ON fact_activities(outcome);

-- fact_opportunities indexes
CREATE INDEX IF NOT EXISTS idx_fact_opportunities_company ON fact_opportunities(company_id);
CREATE INDEX IF NOT EXISTS idx_fact_opportunities_user ON fact_opportunities(user_id);
CREATE INDEX IF NOT EXISTS idx_fact_opportunities_stage ON fact_opportunities(stage);
CREATE INDEX IF NOT EXISTS idx_fact_opportunities_value ON fact_opportunities(value_usd DESC);

-- fact_pipeline_stages indexes
CREATE INDEX IF NOT EXISTS idx_fact_pipeline_company ON fact_pipeline_stages(company_id);
CREATE INDEX IF NOT EXISTS idx_fact_pipeline_date ON fact_pipeline_stages(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_fact_pipeline_to ON fact_pipeline_stages(to_stage);
CREATE INDEX IF NOT EXISTS idx_fact_pipeline_from ON fact_pipeline_stages(from_stage);

-- fact_enrichments indexes
CREATE INDEX IF NOT EXISTS idx_fact_enrichments_company ON fact_enrichments(company_id);
CREATE INDEX IF NOT EXISTS idx_fact_enrichments_method ON fact_enrichments(method);
CREATE INDEX IF NOT EXISTS idx_fact_enrichments_date ON fact_enrichments(enriched_at DESC);
CREATE INDEX IF NOT EXISTS idx_fact_enrichments_success ON fact_enrichments(success);

-- re_enrich_queue indexes
CREATE INDEX IF NOT EXISTS idx_reenrich_status ON re_enrich_queue(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_reenrich_priority ON re_enrich_queue(priority, created_at);
CREATE INDEX IF NOT EXISTS idx_reenrich_company ON re_enrich_queue(company_id);

-- lead_audit_log indexes
CREATE INDEX IF NOT EXISTS idx_lead_audit_company ON lead_audit_log(company_name);
CREATE INDEX IF NOT EXISTS idx_lead_audit_session ON lead_audit_log(session_id);
CREATE INDEX IF NOT EXISTS idx_lead_audit_event ON lead_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_lead_audit_created ON lead_audit_log(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_audit_lead_id ON lead_audit_log(lead_id);
CREATE INDEX IF NOT EXISTS idx_lead_audit_session_event ON lead_audit_log(session_id, event_type);
CREATE INDEX IF NOT EXISTS idx_lead_audit_decision_data ON lead_audit_log USING GIN (decision_data);

-- list_imports indexes
CREATE INDEX IF NOT EXISTS idx_list_imports_date ON list_imports(imported_at DESC);
CREATE INDEX IF NOT EXISTS idx_list_imports_source ON list_imports(source);

-- lead_current_state indexes
CREATE INDEX IF NOT EXISTS idx_lead_state_stage ON lead_current_state(current_stage);
CREATE INDEX IF NOT EXISTS idx_lead_state_attention ON lead_current_state(needs_attention) WHERE needs_attention = TRUE;
CREATE INDEX IF NOT EXISTS idx_lead_state_close_id ON lead_current_state(close_lead_id) WHERE close_lead_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_lead_state_import ON lead_current_state(import_id);
CREATE INDEX IF NOT EXISTS idx_lead_state_updated ON lead_current_state(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_state_created ON lead_current_state(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_state_score ON lead_current_state(qualification_score DESC NULLS LAST);

-- close_activities indexes
CREATE INDEX IF NOT EXISTS idx_close_activities_lead ON close_activities(close_lead_id) WHERE close_lead_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_close_activities_type ON close_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_close_activities_date ON close_activities(activity_date DESC) WHERE activity_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_close_activities_synced ON close_activities(synced_at DESC);

-- pipeline_alerts indexes
CREATE INDEX IF NOT EXISTS idx_alerts_unresolved ON pipeline_alerts(resolved, severity) WHERE resolved = FALSE;
CREATE INDEX IF NOT EXISTS idx_alerts_type ON pipeline_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_company ON pipeline_alerts(company_name);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON pipeline_alerts(created_at DESC);

-- =============================================================================
-- PART 6: TRIGGERS AND FUNCTIONS
-- =============================================================================

-- Trigger to update dim_companies.updated_at on contact changes
CREATE OR REPLACE FUNCTION update_company_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE dim_companies SET updated_at = NOW() WHERE company_id = NEW.company_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_company_on_contact ON dim_contacts;
CREATE TRIGGER trigger_update_company_on_contact
    AFTER INSERT OR UPDATE ON dim_contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_company_timestamp();

-- Update timestamp trigger for lead_current_state
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

-- =============================================================================
-- PART 7: SEED DATA (After tables exist)
-- =============================================================================

INSERT INTO dim_users (close_user_id, name, email, role) VALUES
    ('user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1', 'Tim Kipper', 'tim@coperniq.io', 'BDR'),
    ('user_lFVhSWUaqu2vff3eQEk5KG6jfkbihC1s1g6VUjn5w44', 'Abdullah Al Zandani', 'abdullah@coperniq.io', 'AE'),
    ('user_mARlgTfFvEkDMgcFflJErBYXNr3AxGxsTNWAVxc75gH', 'Max Kazakov', 'max@coperniq.io', 'AE'),
    ('user_MSAjv3Vr0ZjcXAoGt38JPZFjXnIJUNtw0KYaMqMovET', 'Levi Natividad', 'levi@coperniq.io', 'AE'),
    ('user_8ZClygANhdAJI7Tzn89mDBG3mw6SYFeyAmTbkAKe6sR', 'Jerry McElroy', 'jerry@coperniq.io', 'AE')
ON CONFLICT (close_user_id) DO NOTHING;

INSERT INTO dim_sources (source_name, source_type, project) VALUES
    ('dealer-scraper', 'scraper', 'dealer-scraper-mvp'),
    ('close-crm', 'crm', 'close'),
    ('hunter-io', 'api', 'sales-agent'),
    ('apollo', 'api', 'sales-agent'),
    ('browserbase', 'api', 'sales-agent'),
    ('manual-import', 'manual', 'sales-agent'),
    ('re-enrich', 'api', 'dealer-scraper-mvp')
ON CONFLICT (source_name) DO NOTHING;

-- =============================================================================
-- PART 8: VIEWS
-- =============================================================================

DROP VIEW IF EXISTS v_pipeline_funnel;
CREATE VIEW v_pipeline_funnel AS
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

DROP VIEW IF EXISTS v_outreach_summary;
CREATE VIEW v_outreach_summary AS
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

DROP VIEW IF EXISTS v_import_history;
CREATE VIEW v_import_history AS
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

-- =============================================================================
-- PART 9: ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE dim_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_pipeline_stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_enrichments ENABLE ROW LEVEL SECURITY;
ALTER TABLE re_enrich_queue ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE list_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE lead_current_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE close_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE pipeline_alerts ENABLE ROW LEVEL SECURITY;

-- Service role policies (full access for backend)
CREATE POLICY "Service role full access" ON dim_companies FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON dim_contacts FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON dim_users FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON dim_sources FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON fact_activities FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON fact_opportunities FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON fact_pipeline_stages FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON fact_enrichments FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON re_enrich_queue FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON lead_audit_log FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON list_imports FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON lead_current_state FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON close_activities FOR ALL USING (TRUE) WITH CHECK (TRUE);
CREATE POLICY "Service role full access" ON pipeline_alerts FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- =============================================================================
-- VERIFICATION
-- =============================================================================

SELECT 'Schema created successfully!' AS status;
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_type = 'BASE TABLE'
ORDER BY table_name;
