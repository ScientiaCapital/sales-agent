-- =============================================================================
-- MIGRATION: Complete Pipeline Tracking for Scientia Stack Attribution
-- =============================================================================
-- Purpose: Track every lead from dealer-scraper → enrichment → demo → customer
-- This enables end-to-end ROI proof for the Scientia Capital GTM stack
-- =============================================================================

-- Step 1: Drop dependent views (they reference current_stage)
DROP VIEW IF EXISTS v_pipeline_funnel CASCADE;
DROP VIEW IF EXISTS v_scientia_stack_roi CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_icp_gold_leads CASCADE;
DROP MATERIALIZED VIEW IF EXISTS mv_bdr_work_queue CASCADE;

-- Step 2: Add new tracking columns to dim_companies
-- (keeping current_stage as-is, adding new fields for full attribution)

ALTER TABLE dim_companies 
ADD COLUMN IF NOT EXISTS demo_scheduled_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS demo_scheduled_by VARCHAR(100),
ADD COLUMN IF NOT EXISTS demo_completed_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS demo_outcome VARCHAR(50),
ADD COLUMN IF NOT EXISTS demo_notes TEXT,
ADD COLUMN IF NOT EXISTS became_customer_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS coperniq_workspace_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS arr_usd DECIMAL(12, 2),
ADD COLUMN IF NOT EXISTS seats_count INTEGER,
ADD COLUMN IF NOT EXISTS source_attribution JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS stage_history JSONB DEFAULT '[]';

-- Step 3: Add constraint for demo_outcome values
DO $$ 
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_demo_outcome'
    ) THEN
        ALTER TABLE dim_companies 
        ADD CONSTRAINT check_demo_outcome CHECK (
            demo_outcome IS NULL OR demo_outcome IN (
                'qualified',        -- Good fit, moving forward
                'not_qualified',    -- Not a fit
                'timing_bad',       -- Right fit, wrong time
                'competitor',       -- Using competitor
                'no_show',          -- Didn't attend
                'rescheduled',      -- Moved to new date
                'proposal_sent',    -- Demo done, proposal out
                'verbal_commit',    -- Said yes, pending paperwork
                'closed_won',       -- Deal done
                'closed_lost'       -- Deal lost
            )
        );
    END IF;
END $$;

-- Step 4: Add indexes for funnel analysis
CREATE INDEX IF NOT EXISTS idx_companies_demo_scheduled ON dim_companies(demo_scheduled_at) 
    WHERE demo_scheduled_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_demo_completed ON dim_companies(demo_completed_at) 
    WHERE demo_completed_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_became_customer ON dim_companies(became_customer_at) 
    WHERE became_customer_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_companies_arr ON dim_companies(arr_usd) 
    WHERE arr_usd IS NOT NULL;

-- Step 5: Recreate v_pipeline_funnel with original schema (backward compatible)
CREATE OR REPLACE VIEW v_pipeline_funnel AS
SELECT
    current_stage,
    COUNT(*) as total_companies,
    COUNT(*) FILTER (WHERE created_at >= NOW() - INTERVAL '7 days') as new_last_7d,
    COUNT(*) FILTER (WHERE created_at >= DATE_TRUNC('month', NOW())) as new_mtd,
    COUNT(*) FILTER (WHERE last_activity_at >= NOW() - INTERVAL '7 days') as active_last_7d
FROM dim_companies
GROUP BY current_stage
ORDER BY
    CASE current_stage
        WHEN 'imported' THEN 1
        WHEN 'enriched' THEN 2
        WHEN 'contacted' THEN 3
        WHEN 'engaged' THEN 4
        WHEN 'qualified' THEN 5
        WHEN 'demo_scheduled' THEN 6
        WHEN 'proposal' THEN 7
        WHEN 'negotiating' THEN 8
        WHEN 'won' THEN 9
        WHEN 'lost' THEN 10
        WHEN 'nurture' THEN 11
        ELSE 99
    END;

-- Step 6: Create new view for Scientia Stack ROI (the main dashboard view)
CREATE OR REPLACE VIEW v_scientia_stack_roi AS
SELECT 
    original_source,
    
    -- Funnel Counts
    COUNT(*) as total_leads,
    COUNT(*) FILTER (WHERE current_stage NOT IN ('imported', 'raw')) as enriched,
    COUNT(*) FILTER (WHERE icp_tier IN ('GOLD', 'PLATINUM')) as qualified,
    COUNT(*) FILTER (WHERE demo_scheduled_at IS NOT NULL) as demos_scheduled,
    COUNT(*) FILTER (WHERE demo_completed_at IS NOT NULL) as demos_completed,
    COUNT(*) FILTER (WHERE became_customer_at IS NOT NULL) as customers,
    
    -- Revenue Metrics
    SUM(arr_usd) FILTER (WHERE became_customer_at IS NOT NULL) as total_arr,
    AVG(arr_usd) FILTER (WHERE became_customer_at IS NOT NULL) as avg_deal_size,
    SUM(seats_count) FILTER (WHERE became_customer_at IS NOT NULL) as total_seats,
    
    -- Conversion Rates
    ROUND(100.0 * COUNT(*) FILTER (WHERE current_stage NOT IN ('imported', 'raw')) / NULLIF(COUNT(*), 0), 2) as enrichment_rate,
    ROUND(100.0 * COUNT(*) FILTER (WHERE demo_scheduled_at IS NOT NULL) / NULLIF(COUNT(*) FILTER (WHERE current_stage NOT IN ('imported', 'raw')), 0), 2) as demo_rate,
    ROUND(100.0 * COUNT(*) FILTER (WHERE became_customer_at IS NOT NULL) / NULLIF(COUNT(*) FILTER (WHERE demo_completed_at IS NOT NULL), 0), 2) as win_rate,
    
    -- Unit Economics
    ROUND(SUM(arr_usd) FILTER (WHERE became_customer_at IS NOT NULL) / NULLIF(COUNT(*), 0), 2) as revenue_per_lead,
    
    -- Time Metrics (days)
    ROUND(AVG(EXTRACT(EPOCH FROM (demo_scheduled_at - created_at)) / 86400) FILTER (WHERE demo_scheduled_at IS NOT NULL), 1) as avg_days_to_demo,
    ROUND(AVG(EXTRACT(EPOCH FROM (became_customer_at - demo_completed_at)) / 86400) FILTER (WHERE became_customer_at IS NOT NULL), 1) as avg_days_demo_to_close
    
FROM dim_companies
WHERE original_source IS NOT NULL
  AND original_source != 'unknown'
GROUP BY original_source
ORDER BY total_arr DESC NULLS LAST, total_leads DESC;

-- Step 7: Create view for source attribution detail
CREATE OR REPLACE VIEW v_source_attribution_detail AS
SELECT 
    company_id,
    company_name,
    domain,
    original_source,
    current_stage,
    icp_tier,
    icp_score,
    
    -- Contact Info
    (SELECT COUNT(*) FROM dim_contacts dc WHERE dc.company_id = c.company_id) as total_contacts,
    (SELECT COUNT(*) FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE) as atl_contacts,
    
    -- Timeline
    created_at,
    last_enriched_at,
    demo_scheduled_at,
    demo_completed_at,
    demo_outcome,
    became_customer_at,
    
    -- Revenue
    arr_usd,
    seats_count,
    coperniq_workspace_id,
    
    -- Days in pipeline
    EXTRACT(DAY FROM NOW() - created_at)::INTEGER as days_in_pipeline,
    EXTRACT(DAY FROM COALESCE(demo_scheduled_at, NOW()) - created_at)::INTEGER as days_to_demo,
    
    -- Full attribution chain
    source_attribution
    
FROM dim_companies c
WHERE original_source IN ('dealer-scraper-mvp', 'spw_solar_contractor', 'amicus_om', 'amicus_solar')
ORDER BY 
    CASE 
        WHEN became_customer_at IS NOT NULL THEN 1
        WHEN demo_completed_at IS NOT NULL THEN 2
        WHEN demo_scheduled_at IS NOT NULL THEN 3
        WHEN icp_tier = 'PLATINUM' THEN 4
        WHEN icp_tier = 'GOLD' THEN 5
        ELSE 6
    END,
    icp_score DESC NULLS LAST;

-- Step 8: Recreate mv_icp_gold_leads (materialized view for dashboard performance)
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_icp_gold_leads AS
SELECT
    c.company_id,
    c.company_name,
    c.domain,
    c.phone,
    c.city,
    c.state,
    c.icp_score,
    c.icp_tier,
    c.current_stage,
    c.original_source,
    c.close_lead_id,
    c.oem_count,
    c.trade_count,
    c.last_activity_at,
    c.total_activities,
    c.email_opens,
    c.flagged_for_reenrich,
    c.demo_scheduled_at,
    c.demo_completed_at,
    c.demo_outcome,
    c.became_customer_at,
    c.arr_usd,
    -- Computed: enrichment staleness
    CASE WHEN c.last_enriched_at IS NULL OR c.last_enriched_at < NOW() - INTERVAL '30 days'
        THEN TRUE ELSE FALSE
    END as enrichment_stale,
    -- Aggregated contact info
    (SELECT COUNT(*) FROM dim_contacts dc WHERE dc.company_id = c.company_id) as contact_count,
    (SELECT COUNT(*) FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE) as atl_contact_count,
    -- Best ATL contact
    (SELECT full_name FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE ORDER BY dc.confidence DESC LIMIT 1) as best_atl_name,
    (SELECT email FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE ORDER BY dc.confidence DESC LIMIT 1) as best_atl_email,
    (SELECT phone FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE ORDER BY dc.confidence DESC LIMIT 1) as best_atl_phone,
    -- Opportunity data
    (SELECT value_usd FROM fact_opportunities fo WHERE fo.company_id = c.company_id AND fo.stage = 'active' LIMIT 1) as active_opp_value,
    -- Days calculations
    EXTRACT(DAY FROM NOW() - c.last_activity_at)::INTEGER as days_since_activity,
    EXTRACT(DAY FROM NOW() - c.created_at)::INTEGER as days_in_pipeline
FROM dim_companies c
WHERE c.icp_tier IN ('PLATINUM', 'GOLD')
  AND c.icp_score >= 70
  AND c.current_stage NOT IN ('won', 'lost', 'junk', 'do_not_contact', 'customer', 'not_interested', 'disqualified', 'bad_data');

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_icp_gold_company ON mv_icp_gold_leads(company_id);

-- Step 9: Recreate mv_bdr_work_queue with new fields
CREATE MATERIALIZED VIEW IF NOT EXISTS mv_bdr_work_queue AS
WITH company_metrics AS (
    SELECT
        c.*,
        COALESCE(c.total_activities, 0) as activities,
        COALESCE(c.email_opens, 0) as opens,
        EXTRACT(DAY FROM NOW() - COALESCE(c.last_activity_at, c.created_at))::INTEGER as days_stale,
        EXTRACT(DAY FROM NOW() - COALESCE(c.last_enriched_at, '2020-01-01'::TIMESTAMPTZ))::INTEGER as enrichment_age,
        (SELECT COUNT(*) FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE) as atl_count,
        (SELECT full_name FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE ORDER BY dc.confidence DESC LIMIT 1) as best_contact_name,
        (SELECT phone FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE ORDER BY dc.confidence DESC LIMIT 1) as best_contact_phone,
        (SELECT email FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE ORDER BY dc.confidence DESC LIMIT 1) as best_contact_email,
        (SELECT title FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE ORDER BY dc.confidence DESC LIMIT 1) as best_contact_title,
        (SELECT linkedin_url FROM dim_contacts dc WHERE dc.company_id = c.company_id AND dc.is_atl = TRUE ORDER BY dc.confidence DESC LIMIT 1) as best_contact_linkedin,
        (SELECT activity_type FROM fact_activities fa WHERE fa.company_id = c.company_id ORDER BY fa.activity_at DESC LIMIT 1) as last_activity_type,
        (SELECT value_usd FROM fact_opportunities fo WHERE fo.company_id = c.company_id AND fo.stage = 'active' LIMIT 1) as opp_value
    FROM dim_companies c
    WHERE c.current_stage NOT IN ('won', 'lost', 'junk', 'do_not_contact', 'customer', 'not_interested', 'disqualified', 'bad_data')
)
SELECT
    ROW_NUMBER() OVER (ORDER BY
        CASE
            WHEN demo_scheduled_at IS NOT NULL AND demo_completed_at IS NULL THEN 0  -- Upcoming demo
            WHEN opens >= 3 AND days_stale >= 2 THEN 1  -- Hot intent
            WHEN activities = 0 AND atl_count > 0 THEN 2  -- New ATL
            WHEN days_stale >= 7 THEN 3  -- Stale
            ELSE 4
        END,
        icp_score DESC NULLS LAST,
        days_stale DESC
    ) as rank,
    company_id,
    company_name,
    original_source,
    demo_scheduled_at,
    demo_outcome,
    -- Recommended Action (updated with demo-aware logic)
    CASE
        WHEN demo_scheduled_at IS NOT NULL AND demo_completed_at IS NULL THEN '🎯 PREP DEMO - Demo scheduled'
        WHEN demo_completed_at IS NOT NULL AND demo_outcome = 'proposal_sent' THEN '📋 FOLLOW UP - Proposal outstanding'
        WHEN opens >= 3 AND days_stale >= 2 THEN '🔥 CALL NOW - Hot Intent'
        WHEN activities = 0 AND best_contact_phone IS NOT NULL AND atl_count > 0 THEN '📞 First Call - ATL Decision Maker'
        WHEN last_activity_type = 'email' AND opens > 0 THEN '📞 Call - They Read Your Email'
        WHEN last_activity_type = 'call' AND days_stale < 7 THEN '📧 Follow-up Email'
        WHEN best_contact_linkedin IS NOT NULL AND activities > 2 AND days_stale >= 3 THEN '💼 LinkedIn Connection'
        WHEN opp_value IS NOT NULL OR (icp_score >= 80 AND activities >= 3) THEN '🤝 Warm Handoff to AE'
        WHEN enrichment_age > 30 OR flagged_for_reenrich THEN '🔄 Re-enrich - Check for New Contacts'
        WHEN atl_count = 0 AND domain IS NOT NULL THEN '🔍 Research - Find Decision Maker'
        ELSE '📋 Update Status - Review & Categorize'
    END as recommended_action,
    current_stage,
    icp_score,
    icp_tier,
    domain,
    city,
    state,
    activities,
    opens as email_opens,
    days_stale,
    atl_count,
    best_contact_name,
    best_contact_phone,
    best_contact_email,
    best_contact_title,
    best_contact_linkedin
FROM company_metrics
WHERE icp_tier IN ('PLATINUM', 'GOLD', 'SILVER')
   OR demo_scheduled_at IS NOT NULL
   OR activities > 0
ORDER BY rank
LIMIT 500;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_bdr_work_queue_company ON mv_bdr_work_queue(company_id);

-- Step 10: Create helper function to update pipeline stage with history
CREATE OR REPLACE FUNCTION update_pipeline_stage(
    p_company_id UUID,
    p_new_stage VARCHAR(50),
    p_metadata JSONB DEFAULT '{}'
)
RETURNS VOID AS $$
DECLARE
    v_current_stage VARCHAR(50);
    v_stage_entry JSONB;
BEGIN
    -- Get current stage
    SELECT current_stage INTO v_current_stage
    FROM dim_companies
    WHERE company_id = p_company_id;
    
    -- Build stage history entry
    v_stage_entry := jsonb_build_object(
        'from_stage', v_current_stage,
        'to_stage', p_new_stage,
        'changed_at', NOW(),
        'metadata', p_metadata
    );
    
    -- Update company with new stage and append to history
    UPDATE dim_companies
    SET 
        current_stage = p_new_stage,
        updated_at = NOW(),
        stage_history = COALESCE(stage_history, '[]'::jsonb) || v_stage_entry,
        -- Auto-set timestamps based on stage
        demo_scheduled_at = CASE 
            WHEN p_new_stage = 'demo_scheduled' AND demo_scheduled_at IS NULL 
            THEN NOW() 
            ELSE demo_scheduled_at 
        END,
        demo_scheduled_by = CASE 
            WHEN p_new_stage = 'demo_scheduled' 
            THEN COALESCE(p_metadata->>'scheduled_by', demo_scheduled_by)
            ELSE demo_scheduled_by 
        END,
        demo_completed_at = CASE 
            WHEN p_new_stage IN ('proposal', 'negotiating', 'won', 'lost') AND demo_completed_at IS NULL 
            THEN NOW() 
            ELSE demo_completed_at 
        END,
        demo_outcome = CASE 
            WHEN p_metadata->>'demo_outcome' IS NOT NULL 
            THEN p_metadata->>'demo_outcome'
            ELSE demo_outcome 
        END,
        became_customer_at = CASE 
            WHEN p_new_stage = 'won' AND became_customer_at IS NULL 
            THEN NOW() 
            ELSE became_customer_at 
        END,
        arr_usd = CASE 
            WHEN (p_metadata->>'arr_usd')::DECIMAL IS NOT NULL 
            THEN (p_metadata->>'arr_usd')::DECIMAL
            ELSE arr_usd 
        END,
        seats_count = CASE 
            WHEN (p_metadata->>'seats_count')::INTEGER IS NOT NULL 
            THEN (p_metadata->>'seats_count')::INTEGER
            ELSE seats_count 
        END,
        coperniq_workspace_id = CASE 
            WHEN p_metadata->>'workspace_id' IS NOT NULL 
            THEN p_metadata->>'workspace_id'
            ELSE coperniq_workspace_id 
        END
    WHERE company_id = p_company_id;
END;
$$ LANGUAGE plpgsql;

-- Step 11: Grant permissions
GRANT SELECT ON v_pipeline_funnel TO authenticated;
GRANT SELECT ON v_scientia_stack_roi TO authenticated;
GRANT SELECT ON v_source_attribution_detail TO authenticated;
GRANT SELECT ON mv_icp_gold_leads TO authenticated;
GRANT SELECT ON mv_bdr_work_queue TO authenticated;

-- Step 12: Comments for documentation
COMMENT ON VIEW v_scientia_stack_roi IS 'Executive dashboard: dealer-scraper → enrichment → demo → customer with ROI metrics by source';
COMMENT ON VIEW v_source_attribution_detail IS 'Detailed lead-level view with full attribution chain for each company';
COMMENT ON FUNCTION update_pipeline_stage IS 'Helper function to update pipeline stage with automatic timestamp management and history tracking';

COMMENT ON COLUMN dim_companies.demo_scheduled_at IS 'When a demo was first scheduled with this company';
COMMENT ON COLUMN dim_companies.demo_outcome IS 'Outcome of the demo: qualified, not_qualified, timing_bad, etc.';
COMMENT ON COLUMN dim_companies.became_customer_at IS 'When this company became a paying Coperniq customer';
COMMENT ON COLUMN dim_companies.arr_usd IS 'Annual recurring revenue from this customer';
COMMENT ON COLUMN dim_companies.coperniq_workspace_id IS 'Coperniq workspace ID for attribution tracking';
COMMENT ON COLUMN dim_companies.source_attribution IS 'Full attribution chain: source → enrichment → sequence → AE';
COMMENT ON COLUMN dim_companies.stage_history IS 'JSONB array of all stage transitions with timestamps';

-- =============================================================================
-- DONE: Migration complete
-- =============================================================================
-- To refresh materialized views after bulk updates:
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_icp_gold_leads;
-- REFRESH MATERIALIZED VIEW CONCURRENTLY mv_bdr_work_queue;
-- =============================================================================
