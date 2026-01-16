-- =============================================================================
-- STAR SCHEMA: FACT TABLES (Nov 28, 2025)
-- =============================================================================
-- Part of the Star Schema data warehouse redesign for lead analytics.
-- Fact tables store measurable events that reference dimension tables.
-- =============================================================================

-- fact_activities: Calls, Emails, SMS, Meetings from Close CRM
CREATE TABLE IF NOT EXISTS fact_activities (
    activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    close_activity_id VARCHAR(100) UNIQUE,

    -- Dimension Keys
    company_id UUID REFERENCES dim_companies(company_id),
    contact_id UUID REFERENCES dim_contacts(contact_id),
    user_id UUID REFERENCES dim_users(user_id),

    -- Activity Details
    activity_type VARCHAR(50) NOT NULL,  -- 'call', 'email', 'sms', 'meeting'
    direction VARCHAR(20),  -- 'inbound', 'outbound'
    outcome VARCHAR(100),  -- 'connected', 'voicemail', 'no_answer', 'meeting_booked'

    -- Metrics
    duration_seconds INTEGER,

    -- Content
    subject VARCHAR(500),
    body_preview TEXT,

    -- Timestamps
    activity_at TIMESTAMPTZ NOT NULL,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_activities_company ON fact_activities(company_id);
CREATE INDEX IF NOT EXISTS idx_fact_activities_user ON fact_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_fact_activities_type ON fact_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_fact_activities_date ON fact_activities(activity_at DESC);
CREATE INDEX IF NOT EXISTS idx_fact_activities_outcome ON fact_activities(outcome);

-- fact_opportunities: Deals, Pipeline, Won/Lost from Close CRM
CREATE TABLE IF NOT EXISTS fact_opportunities (
    opportunity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    close_opportunity_id VARCHAR(100) UNIQUE,

    -- Dimension Keys
    company_id UUID REFERENCES dim_companies(company_id),
    user_id UUID REFERENCES dim_users(user_id),  -- AE owner

    -- Opportunity Details
    stage VARCHAR(50),  -- 'active', 'won', 'lost'
    value_usd DECIMAL(12, 2),
    confidence INTEGER,

    -- Lost Analysis (for win-back campaigns)
    lost_reason VARCHAR(255),
    competitor VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMPTZ,
    closed_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_opportunities_company ON fact_opportunities(company_id);
CREATE INDEX IF NOT EXISTS idx_fact_opportunities_user ON fact_opportunities(user_id);
CREATE INDEX IF NOT EXISTS idx_fact_opportunities_stage ON fact_opportunities(stage);
CREATE INDEX IF NOT EXISTS idx_fact_opportunities_value ON fact_opportunities(value_usd DESC);

-- fact_pipeline_stages: Stage changes over time (SCD Type 2 pattern)
-- Tracks every stage transition for funnel analysis
CREATE TABLE IF NOT EXISTS fact_pipeline_stages (
    stage_change_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Dimension Keys
    company_id UUID REFERENCES dim_companies(company_id),
    changed_by UUID REFERENCES dim_users(user_id),

    -- Stage Transition
    from_stage VARCHAR(50),  -- NULL if first entry
    to_stage VARCHAR(50) NOT NULL,

    -- Timestamps
    changed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_pipeline_company ON fact_pipeline_stages(company_id);
CREATE INDEX IF NOT EXISTS idx_fact_pipeline_date ON fact_pipeline_stages(changed_at DESC);
CREATE INDEX IF NOT EXISTS idx_fact_pipeline_to ON fact_pipeline_stages(to_stage);
CREATE INDEX IF NOT EXISTS idx_fact_pipeline_from ON fact_pipeline_stages(from_stage);

-- fact_enrichments: Discovery & enrichment events
-- Tracks every enrichment attempt for cost/ROI analysis
CREATE TABLE IF NOT EXISTS fact_enrichments (
    enrichment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Dimension Keys
    company_id UUID REFERENCES dim_companies(company_id),
    source_id UUID REFERENCES dim_sources(source_id),

    -- Method Details
    method VARCHAR(50) NOT NULL,  -- 'hunter', 'apollo', 'browserbase', 'website_scrape', 'review_scrape'

    -- Results
    contacts_found INTEGER DEFAULT 0,
    atl_found INTEGER DEFAULT 0,
    emails_found INTEGER DEFAULT 0,

    -- Cost & Performance
    cost_usd DECIMAL(10, 6) DEFAULT 0,
    latency_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,

    -- Timestamps
    enriched_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fact_enrichments_company ON fact_enrichments(company_id);
CREATE INDEX IF NOT EXISTS idx_fact_enrichments_method ON fact_enrichments(method);
CREATE INDEX IF NOT EXISTS idx_fact_enrichments_date ON fact_enrichments(enriched_at DESC);
CREATE INDEX IF NOT EXISTS idx_fact_enrichments_success ON fact_enrichments(success);

-- re_enrich_queue: Cross-project automation table
-- BDR can flag leads for re-enrichment, dealer-scraper processes the queue
CREATE TABLE IF NOT EXISTS re_enrich_queue (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES dim_companies(company_id),
    company_name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),

    -- Trigger Info
    trigger_type VARCHAR(50) NOT NULL,  -- 'time_based', 'manual_flag', 'new_info_found'
    triggered_by VARCHAR(100) DEFAULT 'system',  -- 'system', 'tim', etc.
    priority INTEGER DEFAULT 2,  -- 1=high, 2=medium, 3=low
    notes TEXT,

    -- Processing Status
    status VARCHAR(50) DEFAULT 'pending',  -- 'pending', 'processing', 'completed', 'failed'
    result_summary JSONB,  -- {"contacts_found": 2, "new_contacts": 1, "atl_found": 1}

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    processed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_reenrich_status ON re_enrich_queue(status) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_reenrich_priority ON re_enrich_queue(priority, created_at);
CREATE INDEX IF NOT EXISTS idx_reenrich_company ON re_enrich_queue(company_id);

-- Trigger to update dim_companies.updated_at on contact changes
CREATE OR REPLACE FUNCTION update_company_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE dim_companies SET updated_at = NOW() WHERE company_id = NEW.company_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to dim_contacts
DROP TRIGGER IF EXISTS trigger_update_company_on_contact ON dim_contacts;
CREATE TRIGGER trigger_update_company_on_contact
    AFTER INSERT OR UPDATE ON dim_contacts
    FOR EACH ROW
    EXECUTE FUNCTION update_company_timestamp();
