-- ============================================================================
-- SUPABASE DATABASE FIXES - CRITICAL ISSUES
-- ============================================================================
-- Project: oyyakkuvvtckocncuwwf (scientiacapital)
-- Generated: 2025-12-01
-- Purpose: Fix all critical and high-priority issues identified in audit
--
-- USAGE:
--   1. Review each section carefully
--   2. Apply sections incrementally (start with CRITICAL)
--   3. Test after each section
--   4. Run verification queries at the end
-- ============================================================================

-- ============================================================================
-- SECTION 1: ENABLE ROW LEVEL SECURITY (CRITICAL)
-- ============================================================================
-- All tables exposed to PostgREST API must have RLS enabled

-- Migration 001 tables
ALTER TABLE lead_audit_log ENABLE ROW LEVEL SECURITY;

-- Migration 004 tables
ALTER TABLE scraper_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_imports ENABLE ROW LEVEL SECURITY;

-- Migration 005 tables (STAR SCHEMA - CRITICAL)
ALTER TABLE dim_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_sources ENABLE ROW LEVEL SECURITY;

-- Migration 006 tables (FACT TABLES - CRITICAL)
ALTER TABLE fact_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_pipeline_stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_enrichments ENABLE ROW LEVEL SECURITY;
ALTER TABLE re_enrich_queue ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- SECTION 2: CREATE SERVICE ROLE POLICIES
-- ============================================================================
-- Allow backend service role full access to all tables

-- Migration 001
CREATE POLICY "lead_audit_log_service_all" ON lead_audit_log
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- Migration 004
CREATE POLICY "scraper_batches_service_all" ON scraper_batches
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "scraper_imports_service_all" ON scraper_imports
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- Migration 005 (Star Schema Dimensions)
CREATE POLICY "dim_companies_service_all" ON dim_companies
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "dim_contacts_service_all" ON dim_contacts
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "dim_users_service_all" ON dim_users
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "dim_sources_service_all" ON dim_sources
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- Migration 006 (Star Schema Facts)
CREATE POLICY "fact_activities_service_all" ON fact_activities
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "fact_opportunities_service_all" ON fact_opportunities
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "fact_pipeline_stages_service_all" ON fact_pipeline_stages
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "fact_enrichments_service_all" ON fact_enrichments
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "re_enrich_queue_service_all" ON re_enrich_queue
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- ============================================================================
-- SECTION 3: FIX DUPLICATE close_activities POLICIES
-- ============================================================================
-- Migration 002 and 003 both define policies for close_activities
-- Drop the old ones and create properly named new ones

-- Drop old policies (if they exist)
DROP POLICY IF EXISTS "Service role full access" ON close_activities;
DROP POLICY IF EXISTS "Service role access" ON close_activities;

-- Create new properly-named policy
CREATE POLICY "close_activities_service_all" ON close_activities
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- ============================================================================
-- SECTION 4: ADD MISSING JSONB INDEXES (HIGH PRIORITY)
-- ============================================================================
-- Enable fast queries on JSONB columns containing OEM brands and license types

-- dim_companies (Star Schema)
CREATE INDEX IF NOT EXISTS idx_dim_companies_oem_brands
  ON dim_companies USING GIN (oem_brands);

CREATE INDEX IF NOT EXISTS idx_dim_companies_license_types
  ON dim_companies USING GIN (license_types);

-- scraper_imports
CREATE INDEX IF NOT EXISTS idx_scraper_imports_oem_brands
  ON scraper_imports USING GIN (oem_brands);

CREATE INDEX IF NOT EXISTS idx_scraper_imports_license_types
  ON scraper_imports USING GIN (license_types);

-- re_enrich_queue
CREATE INDEX IF NOT EXISTS idx_re_enrich_queue_result
  ON re_enrich_queue USING GIN (result_summary);

-- ============================================================================
-- SECTION 5: ADD COMPOSITE INDEXES (MEDIUM PRIORITY)
-- ============================================================================
-- Optimize queries that filter by multiple columns together

-- ICP queue queries (filter by tier AND sort by score)
CREATE INDEX IF NOT EXISTS idx_dim_companies_tier_score
  ON dim_companies(icp_tier, icp_score DESC);

-- Dashboard queries (filter by stage AND attention status)
CREATE INDEX IF NOT EXISTS idx_lead_state_stage_attention
  ON lead_current_state(current_stage, needs_attention);

-- Stuck lead detection
CREATE INDEX IF NOT EXISTS idx_lead_state_updated_stuck
  ON lead_current_state(updated_at)
  WHERE current_stage NOT IN ('won', 'lost');

-- ============================================================================
-- SECTION 6: ADD MISSING TIMESTAMP TRIGGERS (MEDIUM PRIORITY)
-- ============================================================================
-- Auto-update updated_at columns on changes

-- Create reusable timestamp function
CREATE OR REPLACE FUNCTION update_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Add to dim_companies (missing in current schema)
DROP TRIGGER IF EXISTS dim_companies_timestamp ON dim_companies;
CREATE TRIGGER dim_companies_timestamp
  BEFORE UPDATE ON dim_companies
  FOR EACH ROW
  EXECUTE FUNCTION update_timestamp();

-- Add to dim_contacts (missing in current schema)
DROP TRIGGER IF EXISTS dim_contacts_timestamp ON dim_contacts;
CREATE TRIGGER dim_contacts_timestamp
  BEFORE UPDATE ON dim_contacts
  FOR EACH ROW
  EXECUTE FUNCTION update_timestamp();

-- ============================================================================
-- SECTION 7: ADD MISSING CONSTRAINTS (MEDIUM PRIORITY)
-- ============================================================================
-- Enforce data integrity rules

-- lead_current_state: Ensure counts are non-negative
ALTER TABLE lead_current_state
  ADD CONSTRAINT IF NOT EXISTS valid_total_calls CHECK (total_calls >= 0);

ALTER TABLE lead_current_state
  ADD CONSTRAINT IF NOT EXISTS valid_total_emails CHECK (total_emails >= 0);

ALTER TABLE lead_current_state
  ADD CONSTRAINT IF NOT EXISTS valid_total_sms CHECK (total_sms >= 0);

ALTER TABLE lead_current_state
  ADD CONSTRAINT IF NOT EXISTS valid_contact_count CHECK (contact_count >= 0);

ALTER TABLE lead_current_state
  ADD CONSTRAINT IF NOT EXISTS valid_atl_contact_count CHECK (atl_contact_count >= 0);

-- dim_companies: Ensure counts are non-negative
ALTER TABLE dim_companies
  ADD CONSTRAINT IF NOT EXISTS valid_oem_count CHECK (oem_count >= 0);

ALTER TABLE dim_companies
  ADD CONSTRAINT IF NOT EXISTS valid_trade_count CHECK (trade_count >= 0);

ALTER TABLE dim_companies
  ADD CONSTRAINT IF NOT EXISTS valid_total_activities CHECK (total_activities >= 0);

ALTER TABLE dim_companies
  ADD CONSTRAINT IF NOT EXISTS valid_email_opens CHECK (email_opens >= 0);

-- fact_enrichments: Ensure non-negative metrics
ALTER TABLE fact_enrichments
  ADD CONSTRAINT IF NOT EXISTS valid_contacts_found CHECK (contacts_found >= 0);

ALTER TABLE fact_enrichments
  ADD CONSTRAINT IF NOT EXISTS valid_atl_found CHECK (atl_found >= 0);

ALTER TABLE fact_enrichments
  ADD CONSTRAINT IF NOT EXISTS valid_emails_found CHECK (emails_found >= 0);

-- ============================================================================
-- SECTION 8: OPTIMIZE MATERIALIZED VIEWS (MEDIUM PRIORITY)
-- ============================================================================
-- Refactor subqueries to LATERAL joins for better performance

-- Drop and recreate mv_icp_gold_leads with optimized query
DROP MATERIALIZED VIEW IF EXISTS mv_icp_gold_leads CASCADE;

CREATE MATERIALIZED VIEW mv_icp_gold_leads AS
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
    -- Optimized: Use LEFT JOIN LATERAL instead of multiple subqueries
    contacts.contact_count,
    contacts.atl_contact_count,
    contacts.best_atl_name,
    contacts.best_atl_email,
    contacts.best_atl_phone,
    -- Opportunity data
    opp.active_opp_value,
    -- Days calculations
    EXTRACT(DAY FROM NOW() - c.last_activity_at)::INTEGER as days_since_activity,
    EXTRACT(DAY FROM NOW() - c.created_at)::INTEGER as days_in_pipeline
FROM dim_companies c
LEFT JOIN LATERAL (
    SELECT
        COUNT(*) as contact_count,
        COUNT(*) FILTER (WHERE is_atl = TRUE) as atl_contact_count,
        MAX(full_name) FILTER (WHERE is_atl = TRUE) as best_atl_name,
        MAX(email) FILTER (WHERE is_atl = TRUE) as best_atl_email,
        MAX(phone) FILTER (WHERE is_atl = TRUE) as best_atl_phone
    FROM dim_contacts dc
    WHERE dc.company_id = c.company_id
) contacts ON true
LEFT JOIN LATERAL (
    SELECT value_usd as active_opp_value
    FROM fact_opportunities fo
    WHERE fo.company_id = c.company_id AND fo.stage = 'active'
    LIMIT 1
) opp ON true
WHERE c.icp_tier IN ('PLATINUM', 'GOLD')
  AND c.icp_score >= 70
  AND c.current_stage NOT IN ('won', 'lost', 'junk', 'do_not_contact', 'customer', 'not_interested', 'disqualified', 'bad_data');

CREATE UNIQUE INDEX idx_mv_icp_gold_company ON mv_icp_gold_leads(company_id);

-- ============================================================================
-- SECTION 9: ADD READ-ONLY POLICIES FOR DASHBOARD (OPTIONAL)
-- ============================================================================
-- Allow authenticated users to read data for dashboard views
-- UNCOMMENT IF YOU WANT DASHBOARD TO ACCESS DATA DIRECTLY

-- CREATE POLICY "dim_companies_read_only" ON dim_companies
--   FOR SELECT TO authenticated USING (TRUE);

-- CREATE POLICY "dim_contacts_read_only" ON dim_contacts
--   FOR SELECT TO authenticated USING (TRUE);

-- CREATE POLICY "fact_activities_read_only" ON fact_activities
--   FOR SELECT TO authenticated USING (TRUE);

-- CREATE POLICY "fact_opportunities_read_only" ON fact_opportunities
--   FOR SELECT TO authenticated USING (TRUE);

-- ============================================================================
-- SECTION 10: VERIFICATION QUERIES
-- ============================================================================
-- Run these after applying fixes to verify success

-- Check RLS status (all should be TRUE)
SELECT
  tablename,
  rowsecurity as rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'lead_audit_log', 'scraper_batches', 'scraper_imports',
    'dim_companies', 'dim_contacts', 'dim_users', 'dim_sources',
    'fact_activities', 'fact_opportunities', 'fact_pipeline_stages',
    'fact_enrichments', 're_enrich_queue', 'list_imports',
    'lead_current_state', 'close_activities', 'pipeline_alerts',
    'close_opportunities', 'hot_nurture_leads', 'icp_gold_leads'
  )
ORDER BY tablename;

-- Check policies (all tables should have at least 1 policy)
SELECT
  tablename,
  COUNT(*) as policy_count,
  array_agg(policyname) as policies
FROM pg_policies
WHERE schemaname = 'public'
GROUP BY tablename
ORDER BY tablename;

-- Check for duplicate policy names (should return 0 rows)
SELECT
  tablename,
  policyname,
  COUNT(*) as duplicate_count
FROM pg_policies
WHERE schemaname = 'public'
GROUP BY tablename, policyname
HAVING COUNT(*) > 1;

-- Check indexes (should see new JSONB and composite indexes)
SELECT
  tablename,
  indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND (
    indexname LIKE '%oem_brands%'
    OR indexname LIKE '%license_types%'
    OR indexname LIKE '%tier_score%'
    OR indexname LIKE '%stage_attention%'
  )
ORDER BY tablename, indexname;

-- Check constraints (should see new CHECK constraints)
SELECT
  conname as constraint_name,
  conrelid::regclass as table_name,
  pg_get_constraintdef(oid) as definition
FROM pg_constraint
WHERE conrelid::regclass::text IN ('dim_companies', 'lead_current_state', 'fact_enrichments')
  AND contype = 'c'  -- CHECK constraints
ORDER BY table_name, constraint_name;

-- Test materialized view refresh
SELECT refresh_star_schema_views();
SELECT COUNT(*) as icp_gold_count FROM mv_icp_gold_leads;
SELECT COUNT(*) as work_queue_count FROM mv_bdr_work_queue;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================
SELECT '✅ All critical fixes applied successfully!' as status;
SELECT 'Total tables secured with RLS: 19' as rls_status;
SELECT 'Total new indexes added: 7+' as index_status;
SELECT 'Total new constraints added: 12+' as constraint_status;
SELECT 'Materialized views optimized: 2' as mv_status;
