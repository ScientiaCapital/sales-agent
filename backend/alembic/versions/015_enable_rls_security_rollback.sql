-- ============================================================================
-- ROLLBACK SCRIPT: Disable RLS Security on 16 Public Tables
-- ============================================================================
-- Project: oyyakkuvvtckocncuwwf (scientiacapital)
-- Migration: 015_enable_rls_security
-- Date: 2025-12-01
--
-- WARNING: This will re-expose sensitive data to PostgREST API!
-- Only use this rollback in development/testing environments.
-- ============================================================================

-- ============================================================================
-- SECTION 1: DROP ALL SERVICE ROLE POLICIES
-- ============================================================================

-- Migration 001
DROP POLICY IF EXISTS "lead_audit_log_service_all" ON lead_audit_log;

-- Migration 004
DROP POLICY IF EXISTS "scraper_batches_service_all" ON scraper_batches;
DROP POLICY IF EXISTS "scraper_imports_service_all" ON scraper_imports;

-- Migration 005 (Star Schema Dimensions)
DROP POLICY IF EXISTS "dim_companies_service_all" ON dim_companies;
DROP POLICY IF EXISTS "dim_contacts_service_all" ON dim_contacts;
DROP POLICY IF EXISTS "dim_users_service_all" ON dim_users;
DROP POLICY IF EXISTS "dim_sources_service_all" ON dim_sources;

-- Migration 006 (Star Schema Facts)
DROP POLICY IF EXISTS "fact_activities_service_all" ON fact_activities;
DROP POLICY IF EXISTS "fact_opportunities_service_all" ON fact_opportunities;
DROP POLICY IF EXISTS "fact_pipeline_stages_service_all" ON fact_pipeline_stages;
DROP POLICY IF EXISTS "fact_enrichments_service_all" ON fact_enrichments;
DROP POLICY IF EXISTS "re_enrich_queue_service_all" ON re_enrich_queue;

-- Migration 003 (Close CRM)
DROP POLICY IF EXISTS "close_activities_service_all" ON close_activities;
DROP POLICY IF EXISTS "close_opportunities_service_all" ON close_opportunities;

-- Materialized Views (if supported)
DROP POLICY IF EXISTS "mv_icp_gold_leads_service_all" ON mv_icp_gold_leads;
DROP POLICY IF EXISTS "mv_bdr_work_queue_service_all" ON mv_bdr_work_queue;

-- ============================================================================
-- SECTION 2: DISABLE ROW LEVEL SECURITY
-- ============================================================================
-- WARNING: This re-exposes all data to PostgREST API!

-- Migration 001
ALTER TABLE lead_audit_log DISABLE ROW LEVEL SECURITY;

-- Migration 004
ALTER TABLE scraper_batches DISABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_imports DISABLE ROW LEVEL SECURITY;

-- Migration 005 (Star Schema Dimensions)
ALTER TABLE dim_companies DISABLE ROW LEVEL SECURITY;
ALTER TABLE dim_contacts DISABLE ROW LEVEL SECURITY;
ALTER TABLE dim_users DISABLE ROW LEVEL SECURITY;
ALTER TABLE dim_sources DISABLE ROW LEVEL SECURITY;

-- Migration 006 (Star Schema Facts)
ALTER TABLE fact_activities DISABLE ROW LEVEL SECURITY;
ALTER TABLE fact_opportunities DISABLE ROW LEVEL SECURITY;
ALTER TABLE fact_pipeline_stages DISABLE ROW LEVEL SECURITY;
ALTER TABLE fact_enrichments DISABLE ROW LEVEL SECURITY;
ALTER TABLE re_enrich_queue DISABLE ROW LEVEL SECURITY;

-- Migration 003 (Close CRM)
ALTER TABLE close_activities DISABLE ROW LEVEL SECURITY;
ALTER TABLE close_opportunities DISABLE ROW LEVEL SECURITY;

-- Materialized Views (if supported)
-- Note: Some PostgreSQL versions don't support RLS on materialized views
-- These commands may fail, which is expected
DO $$
BEGIN
    ALTER MATERIALIZED VIEW mv_icp_gold_leads DISABLE ROW LEVEL SECURITY;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not disable RLS on mv_icp_gold_leads (may not be supported)';
END $$;

DO $$
BEGIN
    ALTER MATERIALIZED VIEW mv_bdr_work_queue DISABLE ROW LEVEL SECURITY;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'Could not disable RLS on mv_bdr_work_queue (may not be supported)';
END $$;

-- ============================================================================
-- VERIFICATION QUERY
-- ============================================================================
-- Check that RLS is now disabled on all tables

SELECT
    tablename,
    rowsecurity as rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
    AND tablename IN (
        'lead_audit_log', 'scraper_batches', 'scraper_imports',
        'dim_companies', 'dim_contacts', 'dim_users', 'dim_sources',
        'fact_activities', 'fact_opportunities', 'fact_pipeline_stages',
        'fact_enrichments', 're_enrich_queue',
        'close_activities', 'close_opportunities'
    )
ORDER BY tablename;

-- ============================================================================
-- SUCCESS MESSAGE
-- ============================================================================
SELECT '⚠️  WARNING: RLS security has been DISABLED on 16 tables!' as status;
SELECT 'All sensitive data is now EXPOSED to PostgREST API!' as warning;
SELECT 'This rollback should ONLY be used in development/testing!' as important;
