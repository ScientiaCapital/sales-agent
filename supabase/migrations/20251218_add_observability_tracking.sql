-- Migration: Add Observability & Audit Trail
-- Date: 2025-12-18
-- Purpose: Track lead journey from origination through funnel to disposition
-- For: CEO/CTO/Investor visibility

-- ============================================
-- 1. LEAD EVENTS TABLE (Activity Log)
-- ============================================
CREATE TABLE IF NOT EXISTS lead_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Entity references
    company_id UUID REFERENCES dim_companies(company_id),
    contact_id UUID REFERENCES dim_contacts(contact_id),

    -- Event details
    event_type TEXT NOT NULL,
    -- Values: 'scraped', 'enriched_hunter', 'enriched_apollo', 'pushed_to_crm',
    --         'sequence_subscribed', 'email_sent', 'email_opened', 'email_clicked',
    --         'replied', 'called', 'voicemail', 'qualified', 'demo_scheduled',
    --         'proposal_sent', 'closed_won', 'closed_lost', 'nurture_cold', 'nurture_hot'

    event_source TEXT NOT NULL DEFAULT 'sales-agent',
    -- Values: 'sales-agent', 'hunter_io', 'apollo', 'close_crm', 'manual', 'webhook'

    -- Origination tracking
    origination_source TEXT,  -- 'spw_solar_contractor', 'amicus_om', 'amicus_solar', 'dealer-scraper-mvp'
    origination_list TEXT,    -- 'SPW', 'Amicus', 'Dealer'

    -- CRM references
    close_lead_id TEXT,
    close_contact_id TEXT,
    close_sequence_id TEXT,
    close_sequence_name TEXT,

    -- Funnel tracking
    funnel_stage TEXT,
    -- Values: 'new', 'contacted', 'engaged', 'qualified', 'demo', 'proposal', 'negotiation', 'closed_won', 'closed_lost', 'nurture'

    disposition TEXT,
    -- Values: 'nurture_cold', 'nurture_hot', 'closed_won', 'closed_lost', 'not_interested', 'bad_timing', 'no_budget', 'competitor', 'no_response'

    -- Financials
    cost_usd DECIMAL(10,4),        -- Enrichment/API costs
    revenue_usd DECIMAL(12,2),     -- For closed_won

    -- Metadata
    metadata JSONB DEFAULT '{}',
    notes TEXT,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'sales-agent'
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_lead_events_company ON lead_events(company_id);
CREATE INDEX IF NOT EXISTS idx_lead_events_contact ON lead_events(contact_id);
CREATE INDEX IF NOT EXISTS idx_lead_events_type ON lead_events(event_type);
CREATE INDEX IF NOT EXISTS idx_lead_events_created ON lead_events(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_lead_events_funnel ON lead_events(funnel_stage);
CREATE INDEX IF NOT EXISTS idx_lead_events_source ON lead_events(origination_source);

-- ============================================
-- 2. ADD TRACKING COLUMNS TO dim_companies
-- ============================================
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS close_lead_id TEXT,
ADD COLUMN IF NOT EXISTS close_pushed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS funnel_stage TEXT DEFAULT 'new',
ADD COLUMN IF NOT EXISTS disposition TEXT,
ADD COLUMN IF NOT EXISTS total_enrichment_cost_usd DECIMAL(10,4) DEFAULT 0,
ADD COLUMN IF NOT EXISTS first_contact_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS deal_value_usd DECIMAL(12,2),
ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;

-- ============================================
-- 3. ADD TRACKING COLUMNS TO dim_contacts
-- ============================================
ALTER TABLE dim_contacts
ADD COLUMN IF NOT EXISTS close_contact_id TEXT,
ADD COLUMN IF NOT EXISTS close_pushed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS sequence_subscribed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS sequence_name TEXT,
ADD COLUMN IF NOT EXISTS emails_sent INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS emails_opened INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS emails_clicked INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS emails_replied INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS calls_made INT DEFAULT 0,
ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS contact_status TEXT DEFAULT 'new';

-- ============================================
-- 4. FUNNEL METRICS VIEW (For Dashboards)
-- ============================================
CREATE OR REPLACE VIEW v_funnel_metrics AS
SELECT
    origination_list,
    funnel_stage,
    COUNT(DISTINCT company_id) as companies,
    COUNT(DISTINCT contact_id) as contacts
FROM lead_events
WHERE event_type IN ('pushed_to_crm', 'qualified', 'demo_scheduled', 'closed_won', 'closed_lost')
GROUP BY origination_list, funnel_stage;

-- ============================================
-- 5. DAILY ACTIVITY VIEW (For Reporting)
-- ============================================
CREATE OR REPLACE VIEW v_daily_activity AS
SELECT
    DATE(created_at) as activity_date,
    event_type,
    origination_list,
    COUNT(*) as event_count,
    SUM(cost_usd) as total_cost,
    SUM(revenue_usd) as total_revenue
FROM lead_events
GROUP BY DATE(created_at), event_type, origination_list
ORDER BY activity_date DESC;

-- ============================================
-- 6. ROI TRACKING VIEW
-- ============================================
CREATE OR REPLACE VIEW v_roi_by_source AS
SELECT
    origination_list,
    COUNT(DISTINCT company_id) as total_companies,
    COUNT(DISTINCT CASE WHEN funnel_stage = 'closed_won' THEN company_id END) as closed_won,
    SUM(cost_usd) as total_cost,
    SUM(revenue_usd) as total_revenue,
    CASE WHEN SUM(cost_usd) > 0
        THEN ROUND((SUM(revenue_usd) / SUM(cost_usd))::numeric, 2)
        ELSE 0
    END as roi_ratio
FROM lead_events
GROUP BY origination_list;

-- ============================================
-- RLS Policies
-- ============================================
ALTER TABLE lead_events ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all for service role" ON lead_events
    FOR ALL USING (true);

COMMENT ON TABLE lead_events IS 'Audit trail for lead lifecycle tracking - origination through disposition';
