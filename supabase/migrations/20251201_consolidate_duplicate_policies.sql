-- =============================================================================
-- Migration 009: Consolidate Duplicate RLS Policies
-- Created: 2025-12-01
-- Purpose: Fix duplicate permissive policies causing performance degradation
-- Issue: Multiple permissive policies on same tables for same role/action
-- =============================================================================
-- PROBLEM IDENTIFIED:
-- - close_activities table has 2 policies for service role (migrations 002 & 003)
-- - Multiple tables have generic "Service role full access" policies
-- - Duplicate policies cause unnecessary policy evaluation overhead
--
-- SOLUTION:
-- - Drop duplicate policies, keeping only one per table/role/action
-- - Standardize policy naming: {table}_{role}_{action}
-- - Keep only specific, well-named policies
-- =============================================================================

-- =============================================================================
-- SECTION 1: close_activities - CRITICAL FIX (Confirmed Duplicate)
-- =============================================================================
-- Migration 002 line 349: "Service role full access"
-- Migration 003 line 228: "Service role access"
-- Both are permissive FOR ALL policies for service role - one must go!

-- Drop the duplicate policy from migration 003
DROP POLICY IF EXISTS "Service role access" ON close_activities;

-- Keep the policy from migration 002 but rename it for clarity
DROP POLICY IF EXISTS "Service role full access" ON close_activities;
CREATE POLICY "close_activities_service_all"
    ON close_activities
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- =============================================================================
-- SECTION 2: list_imports - Standardize Policy Name
-- =============================================================================
-- Migration 002 line 347: Generic "Service role full access"
-- Rename to table-specific policy name

DROP POLICY IF EXISTS "Service role full access" ON list_imports;
CREATE POLICY "list_imports_service_all"
    ON list_imports
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- =============================================================================
-- SECTION 3: lead_current_state - Standardize Policy Name
-- =============================================================================
-- Migration 002 line 348: Generic "Service role full access"
-- Rename to table-specific policy name

DROP POLICY IF EXISTS "Service role full access" ON lead_current_state;
CREATE POLICY "lead_current_state_service_all"
    ON lead_current_state
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- =============================================================================
-- SECTION 4: pipeline_alerts - Standardize Policy Name
-- =============================================================================
-- Migration 002 line 350: Generic "Service role full access"
-- Rename to table-specific policy name

DROP POLICY IF EXISTS "Service role full access" ON pipeline_alerts;
CREATE POLICY "pipeline_alerts_service_all"
    ON pipeline_alerts
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- =============================================================================
-- SECTION 5: close_opportunities - Standardize Policy Name
-- =============================================================================
-- Migration 003 line 229: Generic "Service role access"
-- Rename to table-specific policy name

DROP POLICY IF EXISTS "Service role access" ON close_opportunities;
CREATE POLICY "close_opportunities_service_all"
    ON close_opportunities
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- =============================================================================
-- SECTION 6: hot_nurture_leads - Standardize Policy Name
-- =============================================================================
-- Migration 003 line 230: Generic "Service role access"
-- Rename to table-specific policy name

DROP POLICY IF EXISTS "Service role access" ON hot_nurture_leads;
CREATE POLICY "hot_nurture_leads_service_all"
    ON hot_nurture_leads
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- =============================================================================
-- SECTION 7: icp_gold_leads - Standardize Policy Name
-- =============================================================================
-- Migration 003 line 231: Generic "Service role access"
-- Rename to table-specific policy name

DROP POLICY IF EXISTS "Service role access" ON icp_gold_leads;
CREATE POLICY "icp_gold_leads_service_all"
    ON icp_gold_leads
    FOR ALL
    TO service_role
    USING (TRUE)
    WITH CHECK (TRUE);

-- =============================================================================
-- VERIFICATION: Check for remaining duplicate policies
-- =============================================================================
-- This query should return 0 rows after this migration runs
DO $$
DECLARE
    duplicate_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO duplicate_count
    FROM (
        SELECT
            schemaname,
            tablename,
            cmd,
            roles::text,
            COUNT(*) as policy_count
        FROM pg_policies
        WHERE schemaname = 'public'
          AND permissive = 'PERMISSIVE'
          AND tablename IN (
              'close_activities', 'list_imports', 'lead_current_state',
              'pipeline_alerts', 'close_opportunities', 'hot_nurture_leads',
              'icp_gold_leads'
          )
        GROUP BY schemaname, tablename, roles::text, cmd
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_count > 0 THEN
        RAISE WARNING 'Still found % duplicate policies after migration!', duplicate_count;
    ELSE
        RAISE NOTICE 'Migration successful: No duplicate policies detected';
    END IF;
END $$;

-- =============================================================================
-- MIGRATION SUMMARY
-- =============================================================================
-- Tables Fixed:
-- 1. close_activities      - Removed duplicate policy (migration 003)
-- 2. list_imports          - Renamed to table-specific name
-- 3. lead_current_state    - Renamed to table-specific name
-- 4. pipeline_alerts       - Renamed to table-specific name
-- 5. close_opportunities   - Renamed to table-specific name
-- 6. hot_nurture_leads     - Renamed to table-specific name
-- 7. icp_gold_leads        - Renamed to table-specific name
--
-- Total Issues Fixed: 8 (1 duplicate + 7 renamed for consistency)
--
-- Expected Performance Improvement:
-- - Reduced policy evaluation time (fewer policies to check)
-- - Clearer audit trail (explicit table names in policy names)
-- - Easier policy management (unique, descriptive names)
-- =============================================================================

-- Success message
SELECT
    'Migration 009 completed successfully' AS status,
    COUNT(*) AS policies_created
FROM pg_policies
WHERE schemaname = 'public'
  AND policyname LIKE '%_service_all';
