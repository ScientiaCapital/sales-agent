-- ============================================
-- Close CRM Sync Tables for Dashboard
-- Created: 2025-11-28
-- Purpose: Store synced activity, opportunity, and lead data
-- ============================================

-- 1. Close Activities (calls, emails, SMS, meetings)
CREATE TABLE IF NOT EXISTS close_activities (
    id TEXT PRIMARY KEY,
    activity_type TEXT NOT NULL CHECK (activity_type IN ('call', 'email', 'sms', 'meeting')),
    user_id TEXT,
    lead_id TEXT,
    contact_id TEXT,
    direction TEXT CHECK (direction IN ('inbound', 'outbound')),
    duration_seconds INTEGER,
    status TEXT,
    outcome TEXT,
    created_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_close_activities_type ON close_activities(activity_type);
CREATE INDEX IF NOT EXISTS idx_close_activities_user ON close_activities(user_id);
CREATE INDEX IF NOT EXISTS idx_close_activities_created ON close_activities(created_at);

-- 2. Close Opportunities (pipeline, won, lost)
CREATE TABLE IF NOT EXISTS close_opportunities (
    id TEXT PRIMARY KEY,
    lead_id TEXT,
    lead_name TEXT,
    status_type TEXT CHECK (status_type IN ('active', 'won', 'lost')),
    status_label TEXT,
    value INTEGER DEFAULT 0,  -- In cents
    value_period TEXT DEFAULT 'one_time',
    confidence INTEGER DEFAULT 0,
    owner_id TEXT,
    owner_name TEXT,  -- Abdullah, Max, etc.
    date_won TIMESTAMPTZ,
    date_lost TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_close_opportunities_status ON close_opportunities(status_type);
CREATE INDEX IF NOT EXISTS idx_close_opportunities_owner ON close_opportunities(owner_name);
CREATE INDEX IF NOT EXISTS idx_close_opportunities_created ON close_opportunities(created_at);

-- 3. Hot Nurture Leads (90-day conversion window)
CREATE TABLE IF NOT EXISTS hot_nurture_leads (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    status_label TEXT,
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    high_intent_flag TEXT DEFAULT 'No',
    last_activity_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ,
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_hot_nurture_intent ON hot_nurture_leads(high_intent_flag);
CREATE INDEX IF NOT EXISTS idx_hot_nurture_activity ON hot_nurture_leads(last_activity_at);

-- 4. ICP Gold Leads (MEP+Energy, 3-4 trades = premium)
-- These are Tim's highest priority prospects
CREATE TABLE IF NOT EXISTS icp_gold_leads (
    id TEXT PRIMARY KEY,
    company_name TEXT NOT NULL,
    status_label TEXT,

    -- Trade capabilities (MEP+Energy focus)
    has_hvac BOOLEAN DEFAULT FALSE,
    has_plumbing BOOLEAN DEFAULT FALSE,
    has_electrical BOOLEAN DEFAULT FALSE,
    has_solar BOOLEAN DEFAULT FALSE,
    has_energy BOOLEAN DEFAULT FALSE,
    trade_count INTEGER GENERATED ALWAYS AS (
        (CASE WHEN has_hvac THEN 1 ELSE 0 END) +
        (CASE WHEN has_plumbing THEN 1 ELSE 0 END) +
        (CASE WHEN has_electrical THEN 1 ELSE 0 END) +
        (CASE WHEN has_solar THEN 1 ELSE 0 END) +
        (CASE WHEN has_energy THEN 1 ELSE 0 END)
    ) STORED,

    -- ICP scoring
    icp_tier TEXT CHECK (icp_tier IN ('gold', 'silver', 'bronze')),
    coperniq_score INTEGER,
    qualification_score INTEGER,

    -- Contact info
    contact_name TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    contact_title TEXT,
    is_atl BOOLEAN DEFAULT FALSE,

    -- Source tracking
    source TEXT,  -- CSV import, scraper, etc.
    close_lead_id TEXT,

    -- Timestamps
    last_contacted_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    synced_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_icp_gold_tier ON icp_gold_leads(icp_tier);
CREATE INDEX IF NOT EXISTS idx_icp_gold_trades ON icp_gold_leads(trade_count);
CREATE INDEX IF NOT EXISTS idx_icp_gold_score ON icp_gold_leads(coperniq_score);

-- 5. View: Top ICP Gold (3-4 trades, sorted by score)
CREATE OR REPLACE VIEW v_top_icp_gold AS
SELECT
    id,
    company_name,
    status_label,
    trade_count,
    has_hvac,
    has_plumbing,
    has_electrical,
    has_solar,
    has_energy,
    icp_tier,
    coperniq_score,
    qualification_score,
    contact_name,
    contact_title,
    is_atl,
    last_contacted_at,
    created_at
FROM icp_gold_leads
WHERE trade_count >= 3
ORDER BY
    trade_count DESC,
    coperniq_score DESC NULLS LAST,
    qualification_score DESC NULLS LAST
LIMIT 50;

-- 6. View: Opportunity Summary (for CEO/CTO view)
CREATE OR REPLACE VIEW v_opportunity_summary AS
SELECT
    status_type,
    owner_name,
    COUNT(*) as count,
    SUM(value) / 100.0 as total_value,  -- Convert cents to dollars
    AVG(confidence) as avg_confidence,
    MIN(created_at) as earliest,
    MAX(created_at) as latest
FROM close_opportunities
WHERE created_at >= NOW() - INTERVAL '6 months'
GROUP BY status_type, owner_name
ORDER BY status_type, owner_name;

-- 7. View: Tim's Activity Summary (for BDR view)
CREATE OR REPLACE VIEW v_tim_activity_summary AS
SELECT
    activity_type,
    direction,
    DATE_TRUNC('day', created_at) as activity_date,
    COUNT(*) as count,
    AVG(duration_seconds) as avg_duration
FROM close_activities
WHERE user_id = 'user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1'
  AND created_at >= NOW() - INTERVAL '90 days'
GROUP BY activity_type, direction, DATE_TRUNC('day', created_at)
ORDER BY activity_date DESC, activity_type;

-- 8. View: Hot Leads Dashboard (combines hot nurture + ICP gold)
CREATE OR REPLACE VIEW v_hot_leads_dashboard AS
SELECT
    'nurture' as lead_type,
    id,
    company_name,
    status_label,
    contact_name,
    NULL::INTEGER as trade_count,
    high_intent_flag,
    last_activity_at,
    synced_at
FROM hot_nurture_leads
WHERE high_intent_flag = 'Yes'

UNION ALL

SELECT
    'icp_gold' as lead_type,
    id,
    company_name,
    status_label,
    contact_name,
    trade_count,
    CASE WHEN trade_count >= 4 THEN 'Yes' ELSE 'No' END as high_intent_flag,
    last_contacted_at as last_activity_at,
    synced_at
FROM icp_gold_leads
WHERE icp_tier = 'gold' AND trade_count >= 3

ORDER BY
    high_intent_flag DESC,
    trade_count DESC NULLS LAST,
    last_activity_at DESC NULLS LAST;

-- 9. View: Outreach Summary (for API endpoint)
CREATE OR REPLACE VIEW v_outreach_summary AS
WITH activity_stats AS (
    SELECT
        activity_type,
        direction,
        COUNT(*) as total_count,
        COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') as count_7d,
        COUNT(*) FILTER (WHERE DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())) as count_mtd,
        AVG(duration_seconds) FILTER (WHERE activity_type = 'call') as avg_call_duration
    FROM close_activities
    WHERE created_at >= NOW() - INTERVAL '90 days'
    GROUP BY activity_type, direction
)
SELECT * FROM activity_stats;

-- Enable RLS
ALTER TABLE close_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE close_opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE hot_nurture_leads ENABLE ROW LEVEL SECURITY;
ALTER TABLE icp_gold_leads ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY "Service role access" ON close_activities FOR ALL USING (true);
CREATE POLICY "Service role access" ON close_opportunities FOR ALL USING (true);
CREATE POLICY "Service role access" ON hot_nurture_leads FOR ALL USING (true);
CREATE POLICY "Service role access" ON icp_gold_leads FOR ALL USING (true);

-- ============================================
-- Summary:
-- close_activities: Tim's calls, emails, SMS, meetings
-- close_opportunities: Abdullah + Max opportunities (won/lost/pipeline)
-- hot_nurture_leads: 90-day conversion window leads
-- icp_gold_leads: MEP+Energy contractors with 3-4 trades
-- v_top_icp_gold: Top 50 ICP gold leads sorted by trade count + score
-- v_opportunity_summary: CEO view of pipeline health
-- v_tim_activity_summary: BDR view of Tim's activity
-- v_hot_leads_dashboard: Combined hot leads for Tim's smart view
-- ============================================
