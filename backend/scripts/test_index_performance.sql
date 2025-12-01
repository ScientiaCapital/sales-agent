-- ============================================================================
-- QUERY PERFORMANCE TESTING SCRIPT
-- ============================================================================
-- Purpose: Verify performance improvements from 016_star_schema_performance migration
-- Run this BEFORE and AFTER applying the migration to measure impact
--
-- Usage:
--   1. Enable timing: \timing on
--   2. Run all queries BEFORE migration
--   3. Apply migration: alembic upgrade 016_star_schema_performance
--   4. Run all queries AFTER migration
--   5. Compare execution times
-- ============================================================================

\timing on
\echo '============================================================================'
\echo 'PERFORMANCE TEST SUITE - Star Schema Indexes'
\echo '============================================================================'
\echo ''

-- ============================================================================
-- TEST 1: JSONB GIN Index Performance
-- ============================================================================
\echo 'TEST 1: JSONB Containment Queries (oem_brands)'
\echo 'Expected improvement: 10-100x faster with GIN index'
\echo ''

EXPLAIN ANALYZE
SELECT company_id, company_name, oem_count
FROM dim_companies
WHERE oem_brands @> '["Cummins"]'::jsonb
LIMIT 100;

\echo ''
\echo 'TEST 2: JSONB Existence Queries (license_types)'
\echo 'Expected improvement: 10-100x faster with GIN index'
\echo ''

EXPLAIN ANALYZE
SELECT company_id, company_name, license_types
FROM dim_companies
WHERE license_types ? 'Class A'
LIMIT 100;

-- ============================================================================
-- TEST 3: Foreign Key Join Performance
-- ============================================================================
\echo ''
\echo 'TEST 3: Activity Join on contact_id (Foreign Key)'
\echo 'Expected improvement: 5-20x faster with index'
\echo ''

EXPLAIN ANALYZE
SELECT
    c.company_name,
    ct.full_name,
    a.activity_type,
    a.activity_at
FROM fact_activities a
JOIN dim_contacts ct ON a.contact_id = ct.contact_id
JOIN dim_companies c ON ct.company_id = c.company_id
WHERE a.activity_at > NOW() - INTERVAL '30 days'
ORDER BY a.activity_at DESC
LIMIT 100;

-- ============================================================================
-- TEST 4: Work Queue Processing (Composite Index)
-- ============================================================================
\echo ''
\echo 'TEST 4: Re-enrichment Queue Priority Processing'
\echo 'Expected improvement: 2-10x faster with composite index'
\echo ''

EXPLAIN ANALYZE
SELECT id, company_name, priority, created_at
FROM re_enrich_queue
WHERE status = 'pending'
ORDER BY priority, created_at
LIMIT 50;

-- ============================================================================
-- TEST 5: ICP Queue Query (Composite Index)
-- ============================================================================
\echo ''
\echo 'TEST 5: Top ICP Leads (Tier + Score Composite)'
\echo 'Expected improvement: 2-5x faster with composite index'
\echo ''

EXPLAIN ANALYZE
SELECT company_id, company_name, icp_tier, icp_score
FROM dim_companies
WHERE icp_tier IN ('PLATINUM', 'GOLD')
ORDER BY icp_score DESC
LIMIT 100;

-- ============================================================================
-- TEST 6: Enrichment Staleness Detection
-- ============================================================================
\echo ''
\echo 'TEST 6: Stale Enrichment Detection (Timestamp Index)'
\echo 'Expected improvement: 5-10x faster with partial index'
\echo ''

EXPLAIN ANALYZE
SELECT company_id, company_name, last_enriched_at
FROM dim_companies
WHERE last_enriched_at < NOW() - INTERVAL '30 days'
   OR last_enriched_at IS NULL
LIMIT 100;

-- ============================================================================
-- TEST 7: Multi-Column Activity Query (Composite Index)
-- ============================================================================
\echo ''
\echo 'TEST 7: Company Activity Timeline (Composite Index)'
\echo 'Expected improvement: 2-5x faster with composite index'
\echo ''

EXPLAIN ANALYZE
SELECT company_id, activity_type, activity_at, outcome
FROM fact_activities
WHERE company_id IN (
    SELECT company_id FROM dim_companies
    WHERE icp_tier = 'PLATINUM'
    LIMIT 10
)
  AND activity_type = 'call'
ORDER BY activity_at DESC;

-- ============================================================================
-- TEST 8: BDR Activity Report (User + Date Composite)
-- ============================================================================
\echo ''
\echo 'TEST 8: BDR Activity Report (User + Date Range)'
\echo 'Expected improvement: 2-5x faster with composite index'
\echo ''

EXPLAIN ANALYZE
SELECT
    u.name,
    a.activity_type,
    COUNT(*) as activity_count,
    DATE(a.activity_at) as activity_date
FROM fact_activities a
JOIN dim_users u ON a.user_id = u.user_id
WHERE a.activity_at > NOW() - INTERVAL '7 days'
GROUP BY u.name, a.activity_type, DATE(a.activity_at)
ORDER BY u.name, activity_date DESC;

-- ============================================================================
-- TEST 9: Enrichment Cost Analysis (Method + Success)
-- ============================================================================
\echo ''
\echo 'TEST 9: Enrichment ROI by Method (Composite Index)'
\echo 'Expected improvement: 2-5x faster with composite index'
\echo ''

EXPLAIN ANALYZE
SELECT
    method,
    success,
    COUNT(*) as attempts,
    SUM(cost_usd) as total_cost,
    AVG(contacts_found) as avg_contacts,
    AVG(atl_found) as avg_atl
FROM fact_enrichments
WHERE enriched_at > NOW() - INTERVAL '30 days'
GROUP BY method, success
ORDER BY method, success;

-- ============================================================================
-- INDEX USAGE VERIFICATION
-- ============================================================================
\echo ''
\echo '============================================================================'
\echo 'INDEX USAGE VERIFICATION'
\echo '============================================================================'
\echo ''

-- Check if indexes exist
SELECT
    schemaname,
    tablename,
    indexname,
    indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND (
    indexname LIKE '%oem_brands%'
    OR indexname LIKE '%license_types%'
    OR indexname LIKE '%linkedin_data%'
    OR indexname LIKE '%contact_id%'
    OR indexname LIKE '%tier_score%'
    OR indexname LIKE '%priority_created%'
    OR indexname LIKE '%enrichment_data%'
    OR indexname LIKE '%result%'
  )
ORDER BY tablename, indexname;

-- ============================================================================
-- INDEX SIZE AND BLOAT ANALYSIS
-- ============================================================================
\echo ''
\echo '============================================================================'
\echo 'INDEX SIZE ANALYSIS'
\echo '============================================================================'
\echo ''

SELECT
    schemaname,
    tablename,
    indexname,
    pg_size_pretty(pg_relation_size(indexname::regclass)) as index_size
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('dim_companies', 'dim_contacts', 'fact_activities', 're_enrich_queue', 'fact_enrichments')
ORDER BY pg_relation_size(indexname::regclass) DESC;

-- ============================================================================
-- QUERY PLAN COMPARISON TEMPLATE
-- ============================================================================
\echo ''
\echo '============================================================================'
\echo 'PERFORMANCE TEST COMPLETE'
\echo '============================================================================'
\echo ''
\echo 'Compare the execution times and query plans from before/after migration.'
\echo 'Look for these improvements:'
\echo '  - "Index Scan" instead of "Seq Scan" in EXPLAIN output'
\echo '  - Lower execution time (actual time in EXPLAIN ANALYZE)'
\echo '  - Lower number of rows scanned'
\echo '  - Use of bitmap index scans for complex queries'
\echo ''
\echo 'Save results to compare:'
\echo '  Before: psql -f test_index_performance.sql > before_results.txt'
\echo '  After:  psql -f test_index_performance.sql > after_results.txt'
\echo '  Compare: diff -u before_results.txt after_results.txt'
\echo ''
