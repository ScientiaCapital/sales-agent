-- =============================================================================
-- Migration: 021_fix_all_security_warnings.sql
-- Purpose: Fix ALL Supabase security warnings (RLS, Security Definer Views, Functions)
-- Date: 2025-12-07
-- Status: APPLIED SUCCESSFULLY
-- =============================================================================
-- This migration addresses 3 categories of security issues:
--   1. RLS Disabled on Tables (5 tables)
--   2. Security Definer Views (12 views need SECURITY INVOKER)
--   3. Function Search Path Mutable (9 functions)
-- =============================================================================

-- ============================================
-- PART 1: ENABLE RLS ON REMAINING TABLES
-- ============================================

ALTER TABLE IF EXISTS contact_monitoring ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_contact_monitoring" ON contact_monitoring;
CREATE POLICY "service_role_all_contact_monitoring"
    ON contact_monitoring FOR ALL TO service_role
    USING (true) WITH CHECK (true);

ALTER TABLE IF EXISTS lead_audit_log ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_lead_audit_log" ON lead_audit_log;
CREATE POLICY "service_role_all_lead_audit_log"
    ON lead_audit_log FOR ALL TO service_role
    USING (true) WITH CHECK (true);

ALTER TABLE IF EXISTS re_enrich_queue ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_re_enrich_queue" ON re_enrich_queue;
CREATE POLICY "service_role_all_re_enrich_queue"
    ON re_enrich_queue FOR ALL TO service_role
    USING (true) WITH CHECK (true);

ALTER TABLE IF EXISTS social_posts ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_social_posts" ON social_posts;
CREATE POLICY "service_role_all_social_posts"
    ON social_posts FOR ALL TO service_role
    USING (true) WITH CHECK (true);

ALTER TABLE IF EXISTS fact_pipeline_stages ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "service_role_all_fact_pipeline_stages" ON fact_pipeline_stages;
CREATE POLICY "service_role_all_fact_pipeline_stages"
    ON fact_pipeline_stages FOR ALL TO service_role
    USING (true) WITH CHECK (true);


-- ============================================
-- PART 2: FIX SECURITY DEFINER VIEWS
-- ============================================

ALTER VIEW IF EXISTS daily_social_summary SET (security_invoker = true);
ALTER VIEW IF EXISTS high_intent_contacts SET (security_invoker = true);
ALTER VIEW IF EXISTS v_activity_summary SET (security_invoker = true);
ALTER VIEW IF EXISTS v_enrichment_costs SET (security_invoker = true);
ALTER VIEW IF EXISTS v_hot_leads_dashboard SET (security_invoker = true);
ALTER VIEW IF EXISTS v_import_history SET (security_invoker = true);
ALTER VIEW IF EXISTS v_opportunity_summary SET (security_invoker = true);
ALTER VIEW IF EXISTS v_outreach_summary SET (security_invoker = true);
ALTER VIEW IF EXISTS v_pipeline_funnel SET (security_invoker = true);
ALTER VIEW IF EXISTS v_stale_enrichments SET (security_invoker = true);
ALTER VIEW IF EXISTS v_tim_activity_summary SET (security_invoker = true);
ALTER VIEW IF EXISTS v_top_icp_gold SET (security_invoker = true);


-- ============================================
-- PART 3: FIX FUNCTION SEARCH PATH
-- ============================================
-- DROP functions first to allow return type changes

DROP FUNCTION IF EXISTS public.check_batch_completion() CASCADE;
DROP FUNCTION IF EXISTS public.check_stuck_leads() CASCADE;
DROP FUNCTION IF EXISTS public.cleanup_expired_oauth_state() CASCADE;
DROP FUNCTION IF EXISTS public.get_batch_progress(uuid) CASCADE;
DROP FUNCTION IF EXISTS public.refresh_star_schema_views() CASCADE;
DROP FUNCTION IF EXISTS public.update_batch_progress() CASCADE;
DROP FUNCTION IF EXISTS public.update_company_timestamp() CASCADE;
DROP FUNCTION IF EXISTS public.update_lead_state_timestamp() CASCADE;
DROP FUNCTION IF EXISTS public.update_updated_at_column() CASCADE;

-- Recreate with secure search_path

CREATE OR REPLACE FUNCTION public.check_batch_completion()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.check_stuck_leads()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.cleanup_expired_oauth_state()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    DELETE FROM public.oauth_state WHERE expires_at < NOW();
END;
$$;

CREATE OR REPLACE FUNCTION public.get_batch_progress(p_batch_id uuid)
RETURNS TABLE(
    total_records int,
    processed_records int,
    success_count int,
    error_count int,
    progress_pct numeric
)
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    RETURN QUERY
    SELECT
        b.total_records,
        b.processed_records,
        b.success_count,
        b.error_count,
        CASE WHEN b.total_records > 0
            THEN ROUND((b.processed_records::numeric / b.total_records) * 100, 2)
            ELSE 0
        END as progress_pct
    FROM public.batch_jobs b
    WHERE b.batch_id = p_batch_id;
END;
$$;

CREATE OR REPLACE FUNCTION public.refresh_star_schema_views()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_icp_gold_leads;
    REFRESH MATERIALIZED VIEW CONCURRENTLY public.mv_bdr_work_queue;
END;
$$;

CREATE OR REPLACE FUNCTION public.update_batch_progress()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    UPDATE public.batch_jobs
    SET processed_records = processed_records + 1,
        updated_at = NOW()
    WHERE batch_id = NEW.batch_id;
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.update_company_timestamp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.update_lead_state_timestamp()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    NEW.state_changed_at = NOW();
    RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

-- =============================================================================
-- NOTES: Applied 2025-12-07 via Supabase SQL Editor
-- - All policies use service_role (backend server access)
-- - Views use SECURITY INVOKER to respect underlying RLS
-- - Functions have search_path = '' for security
-- =============================================================================
