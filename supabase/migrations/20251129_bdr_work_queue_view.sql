-- BDR Work Queue Materialized View
-- Created: 2025-11-29
-- Purpose: Tim's prioritized work queue with recommended actions
-- Source: dim_companies + dim_contacts
--
-- NOTE: This migration is a BACKUP COPY. The view already exists in Supabase
-- and was created via the Supabase Dashboard. This file documents the schema
-- for version control purposes.
--
-- EXISTING VIEW SCHEMA (as of 2025-11-29):
-- - 100 records
-- - 24 leads with direct phone numbers
-- - Columns: rank, company_id, company_name, recommended_action, action_reason,
--   best_contact_name, best_contact_phone, best_contact_email, best_contact_title,
--   best_contact_linkedin, icp_tier, icp_score, total_touches, days_since_activity,
--   days_in_pipeline, opportunity_value, enrichment_age_days, close_lead_url

-- ============================================================================
-- MATERIALIZED VIEW: mv_bdr_work_queue (REFERENCE - DO NOT RUN)
-- The actual view was created via Supabase Dashboard
-- ============================================================================

-- This SQL matches the PRODUCTION schema for documentation purposes:
/*
DROP MATERIALIZED VIEW IF EXISTS mv_bdr_work_queue;

CREATE MATERIALIZED VIEW mv_bdr_work_queue AS
WITH company_contacts AS (
    -- Get best ATL contact per company (prefer contacts with phone)
    SELECT DISTINCT ON (company_id)
        company_id,
        full_name as best_contact_name,
        title as best_contact_title,
        email as best_contact_email,
        phone as best_contact_phone,
        linkedin_url as best_contact_linkedin
    FROM dim_contacts
    WHERE is_atl = TRUE AND email IS NOT NULL
    ORDER BY company_id,
             CASE WHEN phone IS NOT NULL THEN 0 ELSE 1 END,
             created_at DESC
)
SELECT
    ROW_NUMBER() OVER (ORDER BY
        CASE
            WHEN c.icp_tier = 'PLATINUM' AND cc.best_contact_phone IS NOT NULL THEN 1
            WHEN c.icp_tier = 'GOLD' AND cc.best_contact_phone IS NOT NULL THEN 2
            WHEN c.icp_tier = 'PLATINUM' THEN 3
            WHEN c.icp_tier = 'GOLD' THEN 4
            ELSE 5
        END,
        c.icp_score DESC
    ) as rank,
    c.company_id,
    c.company_name,

    -- Recommended action with emoji
    CASE
        WHEN c.icp_tier IN ('PLATINUM', 'GOLD') AND cc.best_contact_phone IS NOT NULL
        THEN '📞
  First Call - ATL Decision Maker'
        WHEN c.updated_at < NOW() - INTERVAL '30 days'
        THEN '🔄 Re-enrich - Check for New
  Contacts'
        ELSE '📋 Update Status - Review & Categorize'
    END as recommended_action,

    -- Action reason
    'New qualified lead with ATL contact' as action_reason,

    -- Contact info
    cc.best_contact_name,
    cc.best_contact_phone,
    cc.best_contact_email,
    cc.best_contact_title,
    cc.best_contact_linkedin,

    -- ICP data
    c.icp_tier,
    c.icp_score,

    -- Activity placeholders (populated when close_activities exists)
    0 as total_touches,
    0 as days_since_activity,
    0 as days_in_pipeline,
    NULL::numeric as opportunity_value,
    EXTRACT(EPOCH FROM (NOW() - c.updated_at)) / 86400 as enrichment_age_days,
    NULL::text as close_lead_url

FROM dim_companies c
LEFT JOIN company_contacts cc ON c.company_id = cc.company_id

WHERE c.icp_tier IN ('PLATINUM', 'GOLD', 'SILVER', 'BRONZE')
  AND cc.best_contact_email IS NOT NULL  -- Only leads with ATL contacts

ORDER BY rank
LIMIT 100;

-- Indexes (non-unique for materialized views)
CREATE INDEX idx_mv_bdr_workqueue_company ON mv_bdr_work_queue(company_id);
CREATE INDEX idx_mv_bdr_workqueue_action ON mv_bdr_work_queue(recommended_action);
CREATE INDEX idx_mv_bdr_workqueue_rank ON mv_bdr_work_queue(rank);
CREATE INDEX idx_mv_bdr_workqueue_tier ON mv_bdr_work_queue(icp_tier);
*/

-- ============================================================================
-- FUNCTION: refresh_bdr_work_queue (SAFE TO RUN)
-- Refresh the materialized view
-- ============================================================================
CREATE OR REPLACE FUNCTION refresh_bdr_work_queue()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW mv_bdr_work_queue;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION refresh_bdr_work_queue IS 'Refresh BDR work queue materialized view. Call every 15 minutes.';
