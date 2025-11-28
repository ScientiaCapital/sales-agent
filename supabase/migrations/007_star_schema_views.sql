-- =============================================================================
-- STAR SCHEMA: MATERIALIZED VIEWS (Nov 28, 2025)
-- =============================================================================
-- Pre-computed views for fast dashboard queries.
-- Refresh every 15 minutes via pg_cron or after batch imports.
-- =============================================================================

-- mv_icp_gold_leads: Gold+ tier leads with aggregated metrics
-- Used by: /api/icp-queue endpoint, dashboard ICP Queue section
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
    c.close_lead_id,
    c.oem_count,
    c.trade_count,
    c.last_activity_at,
    c.total_activities,
    c.email_opens,
    c.flagged_for_reenrich,
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
  AND c.current_stage NOT IN ('won', 'lost', 'junk', 'do_not_contact');

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_icp_gold_company ON mv_icp_gold_leads(company_id);

-- mv_bdr_work_queue: Tim's daily driver with recommended actions
-- Used by: /api/workqueue endpoint, BDR Work Queue dashboard section
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
    WHERE c.current_stage NOT IN ('won', 'lost', 'junk', 'do_not_contact')
)
SELECT
    ROW_NUMBER() OVER (ORDER BY
        CASE
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
    -- Recommended Action (9 action types)
    CASE
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
    -- Action Reason (human-readable explanation)
    CASE
        WHEN opens >= 3 AND days_stale >= 2 THEN opens || ' email opens, no call in ' || days_stale || ' days'
        WHEN activities = 0 AND atl_count > 0 THEN 'New qualified lead with ATL contact'
        WHEN last_activity_type = 'email' AND opens > 0 THEN 'Email opened ' || opens || ' times'
        WHEN last_activity_type = 'call' AND days_stale < 7 THEN 'Called ' || days_stale || ' days ago, no response yet'
        WHEN enrichment_age > 30 THEN 'Last enriched ' || enrichment_age || ' days ago'
        WHEN flagged_for_reenrich THEN 'Manually flagged for re-enrichment'
        WHEN atl_count = 0 THEN 'No ATL contacts found yet'
        ELSE 'Review lead status'
    END as action_reason,
    -- Best contact info for immediate action
    best_contact_name,
    best_contact_phone,
    best_contact_email,
    best_contact_title,
    best_contact_linkedin,
    -- Lead context
    icp_tier,
    icp_score,
    activities as total_touches,
    days_stale as days_since_activity,
    EXTRACT(DAY FROM NOW() - created_at)::INTEGER as days_in_pipeline,
    opp_value as opportunity_value,
    enrichment_age as enrichment_age_days,
    -- Direct link to Close CRM
    CASE WHEN close_lead_id IS NOT NULL
        THEN 'https://app.close.com/lead/' || close_lead_id
        ELSE NULL
    END as close_lead_url
FROM company_metrics
ORDER BY rank
LIMIT 100;

CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_bdr_queue_company ON mv_bdr_work_queue(company_id);

-- Function to refresh all star schema materialized views
CREATE OR REPLACE FUNCTION refresh_star_schema_views()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_icp_gold_leads;
    REFRESH MATERIALIZED VIEW CONCURRENTLY mv_bdr_work_queue;
END;
$$ LANGUAGE plpgsql;

-- Helper view: Companies needing re-enrichment (for pg_cron auto-queue)
CREATE OR REPLACE VIEW v_stale_enrichments AS
SELECT
    company_id,
    company_name,
    domain,
    last_enriched_at,
    EXTRACT(DAY FROM NOW() - COALESCE(last_enriched_at, '2020-01-01'::TIMESTAMPTZ))::INTEGER as days_since_enrichment
FROM dim_companies
WHERE (last_enriched_at IS NULL OR last_enriched_at < NOW() - INTERVAL '30 days')
  AND icp_tier IN ('PLATINUM', 'GOLD')
  AND current_stage NOT IN ('won', 'lost', 'junk', 'do_not_contact')
  AND flagged_for_reenrich = FALSE
ORDER BY icp_score DESC NULLS LAST
LIMIT 50;

-- Helper view: Funnel metrics for dashboard
CREATE OR REPLACE VIEW v_pipeline_funnel AS
SELECT
    current_stage,
    COUNT(*) as count,
    AVG(icp_score) as avg_score,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '7 days') as count_7d,
    COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '30 days') as count_30d
FROM dim_companies
GROUP BY current_stage
ORDER BY
    CASE current_stage
        WHEN 'imported' THEN 1
        WHEN 'qualified' THEN 2
        WHEN 'contacted' THEN 3
        WHEN 'meeting_booked' THEN 4
        WHEN 'opportunity' THEN 5
        WHEN 'won' THEN 6
        WHEN 'lost' THEN 7
        ELSE 8
    END;

-- Helper view: Activity summary by user
CREATE OR REPLACE VIEW v_activity_summary AS
SELECT
    u.name as user_name,
    u.role,
    fa.activity_type,
    COUNT(*) as total_count,
    COUNT(*) FILTER (WHERE fa.activity_at > NOW() - INTERVAL '7 days') as count_7d,
    COUNT(*) FILTER (WHERE fa.activity_at > NOW() - INTERVAL '30 days') as count_30d,
    AVG(fa.duration_seconds) FILTER (WHERE fa.activity_type = 'call') as avg_call_duration
FROM fact_activities fa
JOIN dim_users u ON fa.user_id = u.user_id
GROUP BY u.name, u.role, fa.activity_type
ORDER BY u.name, fa.activity_type;

-- Helper view: Enrichment cost summary
CREATE OR REPLACE VIEW v_enrichment_costs AS
SELECT
    DATE_TRUNC('day', enriched_at) as date,
    method,
    COUNT(*) as total_attempts,
    COUNT(*) FILTER (WHERE success = TRUE) as successful,
    SUM(contacts_found) as total_contacts,
    SUM(atl_found) as total_atl,
    SUM(cost_usd) as total_cost,
    AVG(latency_ms) as avg_latency_ms
FROM fact_enrichments
WHERE enriched_at > NOW() - INTERVAL '30 days'
GROUP BY DATE_TRUNC('day', enriched_at), method
ORDER BY date DESC, method;

-- Schedule refresh every 15 minutes (requires pg_cron extension)
-- Run this manually after enabling pg_cron:
-- SELECT cron.schedule('refresh-star-views', '*/15 * * * *', 'SELECT refresh_star_schema_views()');

-- Grant permissions (adjust as needed)
-- GRANT SELECT ON mv_icp_gold_leads TO authenticated;
-- GRANT SELECT ON mv_bdr_work_queue TO authenticated;
-- GRANT SELECT ON v_pipeline_funnel TO authenticated;
-- GRANT SELECT ON v_activity_summary TO authenticated;
-- GRANT SELECT ON v_enrichment_costs TO authenticated;
