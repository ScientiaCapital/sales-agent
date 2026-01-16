-- =============================================================================
-- Test Script: Verify Policy Consolidation
-- Created: 2025-12-01
-- Purpose: Test and benchmark the policy consolidation changes
-- =============================================================================

-- =============================================================================
-- TEST 1: Check for Duplicate Policies (BEFORE migration)
-- =============================================================================
-- Expected: Should show close_activities with 2 policies
SELECT
    tablename,
    policyname,
    cmd,
    permissive,
    roles::text
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
      'close_activities', 'list_imports', 'lead_current_state',
      'pipeline_alerts', 'close_opportunities', 'hot_nurture_leads',
      'icp_gold_leads'
  )
ORDER BY tablename, policyname;

-- =============================================================================
-- TEST 2: Find Duplicate Policies per Table/Role/Action
-- =============================================================================
-- Expected: Should show at least 1 row for close_activities
SELECT
    tablename,
    cmd as command,
    roles::text,
    COUNT(*) as policy_count,
    array_agg(policyname ORDER BY policyname) as policy_names
FROM pg_policies
WHERE schemaname = 'public'
  AND permissive = 'PERMISSIVE'
  AND tablename IN (
      'close_activities', 'list_imports', 'lead_current_state',
      'pipeline_alerts', 'close_opportunities', 'hot_nurture_leads',
      'icp_gold_leads'
  )
GROUP BY tablename, roles::text, cmd
HAVING COUNT(*) > 1
ORDER BY tablename;

-- =============================================================================
-- TEST 3: Performance Benchmark - Policy Evaluation Time
-- =============================================================================
-- Test query execution time with duplicate policies
EXPLAIN (ANALYZE, BUFFERS, TIMING ON)
SELECT COUNT(*)
FROM close_activities
WHERE close_activity_id IS NOT NULL;

-- =============================================================================
-- TEST 4: Check Policy Names for Consistency
-- =============================================================================
-- Expected BEFORE: Generic names like "Service role full access"
-- Expected AFTER: Table-specific names like "close_activities_service_all"
SELECT
    tablename,
    policyname,
    CASE
        WHEN policyname LIKE '%_service_all' THEN 'GOOD: Table-specific'
        WHEN policyname IN ('Service role full access', 'Service role access') THEN 'BAD: Generic name'
        ELSE 'UNKNOWN'
    END as naming_quality
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
      'close_activities', 'list_imports', 'lead_current_state',
      'pipeline_alerts', 'close_opportunities', 'hot_nurture_leads',
      'icp_gold_leads'
  )
ORDER BY naming_quality, tablename;

-- =============================================================================
-- TEST 5: Verify All Tables Have Exactly One Service Role Policy
-- =============================================================================
-- Expected AFTER migration: All tables should have exactly 1 policy
SELECT
    tablename,
    COUNT(*) as policy_count,
    array_agg(policyname) as policies
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
      'close_activities', 'list_imports', 'lead_current_state',
      'pipeline_alerts', 'close_opportunities', 'hot_nurture_leads',
      'icp_gold_leads'
  )
  AND roles::text LIKE '%service_role%'
GROUP BY tablename
ORDER BY tablename;

-- =============================================================================
-- TEST 6: Verify Policy Logic Remains Unchanged
-- =============================================================================
-- All policies should still allow full access to service_role
SELECT
    tablename,
    policyname,
    cmd,
    qual as using_expression,
    with_check as with_check_expression
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
      'close_activities', 'list_imports', 'lead_current_state',
      'pipeline_alerts', 'close_opportunities', 'hot_nurture_leads',
      'icp_gold_leads'
  )
ORDER BY tablename;

-- =============================================================================
-- TEST 7: Count Total Policies Before/After
-- =============================================================================
SELECT
    'Total policies on affected tables' as metric,
    COUNT(*) as count
FROM pg_policies
WHERE schemaname = 'public'
  AND tablename IN (
      'close_activities', 'list_imports', 'lead_current_state',
      'pipeline_alerts', 'close_opportunities', 'hot_nurture_leads',
      'icp_gold_leads'
  );

-- =============================================================================
-- PERFORMANCE TEST: Run AFTER Migration
-- =============================================================================
-- Compare execution time with consolidated policies
-- Expected: Slightly faster policy evaluation (5-10% improvement)

-- Test 1: Simple SELECT
EXPLAIN (ANALYZE, BUFFERS, TIMING ON)
SELECT * FROM close_activities LIMIT 100;

-- Test 2: JOIN query (multiple table policies evaluated)
EXPLAIN (ANALYZE, BUFFERS, TIMING ON)
SELECT
    ca.activity_type,
    lcs.company_name,
    COUNT(*) as activity_count
FROM close_activities ca
JOIN lead_current_state lcs ON ca.close_lead_id = lcs.close_lead_id
GROUP BY ca.activity_type, lcs.company_name
LIMIT 20;

-- Test 3: INSERT performance
EXPLAIN (ANALYZE, BUFFERS, TIMING ON)
INSERT INTO close_activities (id, activity_type, direction, synced_at)
VALUES (
    gen_random_uuid()::text,
    'call',
    'outbound',
    NOW()
);

-- Cleanup test data
DELETE FROM close_activities WHERE activity_type = 'call' AND direction = 'outbound' AND synced_at > NOW() - INTERVAL '1 minute';

-- =============================================================================
-- SUMMARY QUERY: Policy Health Check
-- =============================================================================
WITH policy_stats AS (
    SELECT
        tablename,
        COUNT(*) as policy_count,
        COUNT(DISTINCT cmd) as unique_commands,
        COUNT(DISTINCT roles::text) as unique_roles,
        array_agg(DISTINCT policyname) as policy_names
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename IN (
          'close_activities', 'list_imports', 'lead_current_state',
          'pipeline_alerts', 'close_opportunities', 'hot_nurture_leads',
          'icp_gold_leads'
      )
    GROUP BY tablename
)
SELECT
    tablename,
    policy_count,
    unique_commands,
    unique_roles,
    CASE
        WHEN policy_count = 1 THEN '✓ OPTIMAL'
        WHEN policy_count > 1 THEN '✗ DUPLICATE'
        ELSE '? NO POLICY'
    END as status,
    policy_names
FROM policy_stats
ORDER BY policy_count DESC, tablename;

-- =============================================================================
-- Expected Results Summary:
--
-- BEFORE Migration 009:
-- - close_activities: 2 policies (DUPLICATE)
-- - Other tables: 1 policy each with generic names
--
-- AFTER Migration 009:
-- - All tables: Exactly 1 policy with table-specific names
-- - Naming convention: {table}_service_all
-- - Performance: 5-10% improvement in policy evaluation
-- =============================================================================
