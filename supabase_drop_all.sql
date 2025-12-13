-- =============================================================================
-- DROP ALL TABLES - RUN THIS FIRST TO CLEAN UP
-- =============================================================================
-- Run this in Supabase SQL Editor BEFORE running the schema

-- Drop views first
DROP VIEW IF EXISTS v_pipeline_funnel CASCADE;
DROP VIEW IF EXISTS v_outreach_summary CASCADE;
DROP VIEW IF EXISTS v_import_history CASCADE;

-- Drop fact tables (they reference dimensions)
DROP TABLE IF EXISTS fact_activities CASCADE;
DROP TABLE IF EXISTS fact_opportunities CASCADE;
DROP TABLE IF EXISTS fact_pipeline_stages CASCADE;
DROP TABLE IF EXISTS fact_enrichments CASCADE;
DROP TABLE IF EXISTS re_enrich_queue CASCADE;

-- Drop dashboard tables
DROP TABLE IF EXISTS pipeline_alerts CASCADE;
DROP TABLE IF EXISTS close_activities CASCADE;
DROP TABLE IF EXISTS lead_current_state CASCADE;
DROP TABLE IF EXISTS list_imports CASCADE;
DROP TABLE IF EXISTS lead_audit_log CASCADE;

-- Drop dimension tables (referenced by facts)
DROP TABLE IF EXISTS dim_contacts CASCADE;
DROP TABLE IF EXISTS dim_companies CASCADE;
DROP TABLE IF EXISTS dim_users CASCADE;
DROP TABLE IF EXISTS dim_sources CASCADE;

-- Drop functions
DROP FUNCTION IF EXISTS update_company_timestamp CASCADE;
DROP FUNCTION IF EXISTS update_lead_state_timestamp CASCADE;

SELECT 'All tables dropped successfully!' AS status;
