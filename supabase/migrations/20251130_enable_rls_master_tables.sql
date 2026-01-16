-- =============================================================================
-- Migration: 020_enable_rls_master_tables.sql
-- Purpose: Enable Row Level Security on master dimension tables
-- Policy: Service role only (backend server access, no multi-tenant user access)
-- Date: 2025-12-06
-- =============================================================================
-- Context: Security audit found RLS disabled on master tables.
-- This migration enables RLS with service_role policies for backend access.
-- =============================================================================

-- ============================================
-- 1. ENABLE RLS ON MASTER TABLES
-- ============================================

-- dim_companies (master lead list - 8,891 company records)
ALTER TABLE IF EXISTS dim_companies ENABLE ROW LEVEL SECURITY;

-- dim_contacts (ATL/BTL contacts - 584 contact records)
ALTER TABLE IF EXISTS dim_contacts ENABLE ROW LEVEL SECURITY;

-- scraper_batches (scraping job metadata)
ALTER TABLE IF EXISTS scraper_batches ENABLE ROW LEVEL SECURITY;

-- scraper_imports (import history)
ALTER TABLE IF EXISTS scraper_imports ENABLE ROW LEVEL SECURITY;

-- ============================================
-- 2. SERVICE ROLE POLICIES (Full Access)
-- ============================================
-- These policies allow the backend (FastAPI) to access master tables via
-- the service_role key without row-level restrictions.
-- This is the intended access pattern for backend servers.

-- dim_companies: Service role full access
DROP POLICY IF EXISTS "service_role_all_dim_companies" ON dim_companies;
CREATE POLICY "service_role_all_dim_companies"
    ON dim_companies
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- dim_contacts: Service role full access
DROP POLICY IF EXISTS "service_role_all_dim_contacts" ON dim_contacts;
CREATE POLICY "service_role_all_dim_contacts"
    ON dim_contacts
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- scraper_batches: Service role full access
DROP POLICY IF EXISTS "service_role_all_scraper_batches" ON scraper_batches;
CREATE POLICY "service_role_all_scraper_batches"
    ON scraper_batches
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- scraper_imports: Service role full access
DROP POLICY IF EXISTS "service_role_all_scraper_imports" ON scraper_imports;
CREATE POLICY "service_role_all_scraper_imports"
    ON scraper_imports
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- ============================================
-- 3. VERIFICATION QUERIES (Run Manually)
-- ============================================
-- After migration completes, verify RLS is enabled:
--
-- SELECT tablename, rowsecurity FROM pg_tables
-- WHERE schemaname = 'public'
-- AND tablename IN ('dim_companies', 'dim_contacts', 'scraper_batches', 'scraper_imports')
-- ORDER BY tablename;
--
-- Expected output:
--   tablename         | rowsecurity
--   ──────────────────┼────────────
--   dim_companies     | t
--   dim_contacts      | t
--   scraper_batches   | t
--   scraper_imports   | t
--
-- Verify policies are in place:
--
-- SELECT schemaname, tablename, policyname, permissive, roles
-- FROM pg_policies
-- WHERE tablename IN ('dim_companies', 'dim_contacts', 'scraper_batches', 'scraper_imports')
-- ORDER BY tablename, policyname;
--
-- Test service_role access (via psql):
--   SELECT COUNT(*) FROM dim_companies;  -- Should work with service_role
--
-- ============================================
-- 4. MIGRATION NOTES
-- ============================================
-- - Idempotent: Safe to run multiple times (DROP IF EXISTS clauses)
-- - Service role is the Supabase backend server role
-- - No public/authenticated user access to these tables (via policies)
-- - Future: Add specific policies if multi-tenant features needed
-- - Rollback: Disable RLS with ALTER TABLE ... DISABLE ROW LEVEL SECURITY
-- =============================================================================
