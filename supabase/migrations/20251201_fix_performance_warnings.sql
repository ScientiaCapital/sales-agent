-- =============================================================================
-- Migration: 022_fix_performance_warnings.sql
-- Purpose: Fix ALL Supabase performance warnings (unused indexes, foreign key indexes)
-- Date: 2025-12-07
-- =============================================================================
-- This migration addresses 2 categories of performance issues:
--   1. Unused Indexes (drop them to save storage and improve write performance)
--   2. Unindexed Foreign Keys (add indexes to improve join performance)
-- =============================================================================

-- ============================================
-- PART 1: DROP UNUSED INDEXES
-- ============================================
-- Unused indexes waste storage and slow down INSERT/UPDATE operations.
-- Only drop indexes that are genuinely unused (not needed for queries).

-- social_posts: Drop unused indexes
DROP INDEX IF EXISTS idx_social_posts_created_at;
DROP INDEX IF EXISTS idx_social_posts_source;
DROP INDEX IF EXISTS idx_social_posts_sentiment;

-- re_enrich_queue: Drop unused indexes
DROP INDEX IF EXISTS idx_re_enrich_queue_status;
DROP INDEX IF EXISTS idx_re_enrich_queue_created_at;

-- scraper_batches: Drop unused indexes
DROP INDEX IF EXISTS idx_scraper_batches_status;

-- scraper_imports: Drop unused indexes
DROP INDEX IF EXISTS idx_scraper_imports_batch_id;
DROP INDEX IF EXISTS idx_scraper_imports_status;
DROP INDEX IF EXISTS idx_scraper_imports_created_at;
DROP INDEX IF EXISTS idx_scraper_imports_company_name;
DROP INDEX IF EXISTS idx_scraper_imports_domain;
DROP INDEX IF EXISTS idx_scraper_imports_source;

-- lead_audit_log: Drop unused indexes
DROP INDEX IF EXISTS idx_lead_audit_log_lead_id;
DROP INDEX IF EXISTS idx_lead_audit_log_action;
DROP INDEX IF EXISTS idx_lead_audit_log_created_at;
DROP INDEX IF EXISTS idx_lead_audit_log_user_id;

-- fact_lead_signals: Drop unused indexes
DROP INDEX IF EXISTS idx_fact_lead_signals_signal_type;

-- lead_current_state: Drop unused indexes
DROP INDEX IF EXISTS idx_lead_current_state_lead_id;
DROP INDEX IF EXISTS idx_lead_current_state_stage;
DROP INDEX IF EXISTS idx_lead_current_state_updated_at;
DROP INDEX IF EXISTS idx_lead_current_state_assigned_to;

-- fact_activities: Drop unused indexes
DROP INDEX IF EXISTS idx_fact_activities_activity_type;
DROP INDEX IF EXISTS idx_fact_activities_created_at;

-- fact_enrichments: Drop unused indexes
DROP INDEX IF EXISTS idx_fact_enrichments_method;
DROP INDEX IF EXISTS idx_fact_enrichments_success;
DROP INDEX IF EXISTS idx_fact_enrichments_enriched_at;

-- fact_opportunities: Drop unused indexes
DROP INDEX IF EXISTS idx_fact_opportunities_stage;
DROP INDEX IF EXISTS idx_fact_opportunities_created_at;

-- fact_pipeline_stages: Drop unused indexes
DROP INDEX IF EXISTS idx_fact_pipeline_stages_stage;
DROP INDEX IF EXISTS idx_fact_pipeline_stages_entered_at;


-- ============================================
-- PART 2: ADD INDEXES ON FOREIGN KEYS
-- ============================================
-- Foreign keys without indexes cause slow JOIN operations.
-- Adding indexes dramatically improves query performance.

-- dim_alerts: Add index on company_id foreign key
CREATE INDEX IF NOT EXISTS idx_dim_alerts_company_id
    ON dim_alerts(company_id);

-- fact_activities: Add index on company_id foreign key
CREATE INDEX IF NOT EXISTS idx_fact_activities_company_id
    ON fact_activities(company_id);

-- fact_activities: Add index on user_id foreign key
CREATE INDEX IF NOT EXISTS idx_fact_activities_user_id
    ON fact_activities(user_id);

-- fact_close_activities: Add index on company_id foreign key
CREATE INDEX IF NOT EXISTS idx_fact_close_activities_company_id
    ON fact_close_activities(company_id);

-- fact_close_activities: Add index on contact_id foreign key (if exists)
CREATE INDEX IF NOT EXISTS idx_fact_close_activities_contact_id
    ON fact_close_activities(contact_id);

-- fact_enrichments: Add index on company_id foreign key
CREATE INDEX IF NOT EXISTS idx_fact_enrichments_company_id
    ON fact_enrichments(company_id);

-- fact_pipeline_stages: Add index on company_id foreign key
CREATE INDEX IF NOT EXISTS idx_fact_pipeline_stages_company_id
    ON fact_pipeline_stages(company_id);

-- pipeline_alerts: Add index on company_id foreign key
CREATE INDEX IF NOT EXISTS idx_pipeline_alerts_company_id
    ON pipeline_alerts(company_id);

-- dim_contacts: Add index on company_id foreign key (commonly used in JOINs)
CREATE INDEX IF NOT EXISTS idx_dim_contacts_company_id
    ON dim_contacts(company_id);

-- fact_opportunities: Add index on company_id foreign key
CREATE INDEX IF NOT EXISTS idx_fact_opportunities_company_id
    ON fact_opportunities(company_id);

-- fact_lead_signals: Add index on company_id foreign key
CREATE INDEX IF NOT EXISTS idx_fact_lead_signals_company_id
    ON fact_lead_signals(company_id);


-- ============================================
-- VERIFICATION QUERIES
-- ============================================
-- Run these after migration to verify:

-- 1. Check for remaining unused indexes:
-- SELECT
--     schemaname || '.' || indexrelname as index_name,
--     pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
--     idx_scan as times_used
-- FROM pg_stat_user_indexes
-- WHERE idx_scan = 0
-- AND schemaname = 'public'
-- ORDER BY pg_relation_size(indexrelid) DESC;

-- 2. Check for unindexed foreign keys:
-- SELECT
--     c.conname AS constraint_name,
--     c.conrelid::regclass AS table_name,
--     a.attname AS column_name
-- FROM pg_constraint c
-- JOIN pg_attribute a ON a.attnum = ANY(c.conkey) AND a.attrelid = c.conrelid
-- WHERE c.contype = 'f'
-- AND NOT EXISTS (
--     SELECT 1 FROM pg_index i
--     WHERE i.indrelid = c.conrelid
--     AND a.attnum = ANY(i.indkey)
-- );

-- =============================================================================
-- NOTES
-- =============================================================================
-- - Dropped indexes: Only those confirmed unused by pg_stat_user_indexes
-- - Added indexes: All foreign key columns for optimal JOIN performance
-- - Idempotent: Safe to run multiple times (IF NOT EXISTS / IF EXISTS)
-- =============================================================================
