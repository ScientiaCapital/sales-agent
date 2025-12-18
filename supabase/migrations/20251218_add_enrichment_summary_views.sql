-- Migration: Add Enrichment Summary Views for Comprehensive Reporting
-- Date: 2025-12-18
-- Purpose: Enable ROI analysis, cost tracking, and enrichment performance metrics
--
-- Views created:
--   1. v_enrichment_summary - Breakdown by lead source with ATL/BTL, costs, coverage
--   2. v_enrichment_totals - Grand totals across all companies
--   3. v_contact_totals - Contact breakdown by source
--   4. v_enrichment_attempt_totals - Attempt success rates and costs by source

-- ============================================
-- 1. v_enrichment_summary
-- ============================================
-- Summary metrics by original_source: total companies, ATL/BTL breakdown, costs, coverage
CREATE OR REPLACE VIEW v_enrichment_summary AS
WITH company_stats AS (
    SELECT
        COALESCE(c.original_source, 'unknown') as original_source,
        COUNT(DISTINCT c.company_id) as total_companies,
        COUNT(DISTINCT c.company_id) FILTER (
            WHERE c.icp_tier IN ('PLATINUM', 'GOLD')
        ) as high_tier_companies,
        COUNT(DISTINCT c.company_id) FILTER (
            WHERE c.icp_tier IN ('SILVER', 'BRONZE')
        ) as low_tier_companies,
        COALESCE(SUM(c.oem_count), 0) as total_oem_relationships,
        COALESCE(SUM(c.trade_count), 0) as total_trade_certifications
    FROM dim_companies c
    GROUP BY COALESCE(c.original_source, 'unknown')
),
contact_stats AS (
    SELECT
        COALESCE(c.original_source, 'unknown') as original_source,
        COUNT(DISTINCT ct.contact_id) as total_contacts,
        COUNT(DISTINCT ct.contact_id) FILTER (
            WHERE ct.is_atl = TRUE
        ) as atl_contacts,
        COUNT(DISTINCT ct.contact_id) FILTER (
            WHERE ct.is_atl = FALSE
        ) as btl_contacts,
        COUNT(DISTINCT ct.contact_id) FILTER (
            WHERE ct.email IS NOT NULL
        ) as contacts_with_email,
        ROUND(
            100.0 * COUNT(DISTINCT ct.contact_id) FILTER (WHERE ct.is_atl = TRUE) /
            NULLIF(COUNT(DISTINCT ct.contact_id), 0),
            2
        ) as atl_ratio_pct
    FROM dim_companies c
    LEFT JOIN dim_contacts ct ON c.company_id = ct.company_id
    GROUP BY COALESCE(c.original_source, 'unknown')
),
enrichment_costs AS (
    SELECT
        COALESCE(fea.source, 'unknown') as source_normalized,
        ROUND(COALESCE(SUM(fea.cost_usd), 0)::numeric, 2) as total_cost_usd,
        COUNT(*) FILTER (
            WHERE fea.success = TRUE
        ) as successful_attempts,
        COUNT(*) FILTER (
            WHERE fea.success = FALSE
        ) as failed_attempts,
        COUNT(*) as total_attempts,
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE fea.success = TRUE) /
            NULLIF(COUNT(*), 0),
            2
        ) as success_rate_pct
    FROM fact_enrichment_attempts fea
    GROUP BY COALESCE(fea.source, 'unknown')
)
SELECT
    cs.original_source,
    cs.total_companies,
    cs.high_tier_companies,
    cs.low_tier_companies,
    ROUND(
        100.0 * COALESCE(cs.high_tier_companies, 0) /
        NULLIF(cs.total_companies, 0),
        2
    ) as high_tier_pct,
    cts.total_contacts,
    cts.atl_contacts,
    cts.btl_contacts,
    cts.contacts_with_email,
    cts.atl_ratio_pct,
    ROUND(
        100.0 * COALESCE(cts.contacts_with_email, 0) /
        NULLIF(cts.total_contacts, 0),
        2
    ) as email_coverage_pct,
    cs.total_oem_relationships,
    cs.total_trade_certifications,
    COALESCE(ec.total_cost_usd, 0) as total_cost_usd,
    COALESCE(ec.successful_attempts, 0) as successful_attempts,
    COALESCE(ec.failed_attempts, 0) as failed_attempts,
    COALESCE(ec.total_attempts, 0) as total_attempts,
    COALESCE(ec.success_rate_pct, 0) as success_rate_pct,
    CASE
        WHEN COALESCE(ec.total_cost_usd, 0) > 0 AND cts.atl_contacts > 0 THEN
            ROUND((COALESCE(ec.total_cost_usd, 0) / cts.atl_contacts)::numeric, 2)
        ELSE 0
    END as cost_per_atl_contact
FROM company_stats cs
LEFT JOIN contact_stats cts ON cs.original_source = cts.original_source
LEFT JOIN enrichment_costs ec ON cs.original_source = ec.source_normalized
ORDER BY cs.total_companies DESC;

COMMENT ON VIEW v_enrichment_summary IS
'Summary of enrichment metrics by lead source. Shows company counts by tier, contact breakdown (ATL/BTL),
coverage percentages, and cost metrics. Used for ROI analysis and source performance comparison.';

-- ============================================
-- 2. v_enrichment_totals
-- ============================================
-- Grand totals across all companies and sources
CREATE OR REPLACE VIEW v_enrichment_totals AS
WITH all_companies AS (
    SELECT
        COUNT(DISTINCT company_id) as total_companies,
        COUNT(DISTINCT company_id) FILTER (
            WHERE icp_tier = 'PLATINUM'
        ) as platinum_companies,
        COUNT(DISTINCT company_id) FILTER (
            WHERE icp_tier = 'GOLD'
        ) as gold_companies,
        COUNT(DISTINCT company_id) FILTER (
            WHERE icp_tier = 'SILVER'
        ) as silver_companies,
        COUNT(DISTINCT company_id) FILTER (
            WHERE icp_tier = 'BRONZE'
        ) as bronze_companies,
        COUNT(DISTINCT company_id) FILTER (
            WHERE icp_tier IS NULL
        ) as unscored_companies,
        ROUND(AVG(NULLIF(icp_score, 0))::numeric, 2) as avg_icp_score,
        COUNT(DISTINCT company_id) FILTER (
            WHERE flagged_for_reenrich = TRUE
        ) as flagged_for_reenrich,
        COUNT(DISTINCT company_id) FILTER (
            WHERE last_enriched_at IS NOT NULL
        ) as enriched_companies
    FROM dim_companies
),
all_contacts AS (
    SELECT
        COUNT(DISTINCT contact_id) as total_contacts,
        COUNT(DISTINCT contact_id) FILTER (
            WHERE is_atl = TRUE
        ) as total_atl_contacts,
        COUNT(DISTINCT contact_id) FILTER (
            WHERE is_atl = FALSE
        ) as total_btl_contacts,
        COUNT(DISTINCT contact_id) FILTER (
            WHERE email IS NOT NULL
        ) as contacts_with_email,
        COUNT(DISTINCT contact_id) FILTER (
            WHERE phone IS NOT NULL
        ) as contacts_with_phone,
        COUNT(DISTINCT contact_id) FILTER (
            WHERE validated = TRUE
        ) as validated_contacts,
        ROUND(
            100.0 * COUNT(DISTINCT contact_id) FILTER (WHERE is_atl = TRUE) /
            NULLIF(COUNT(DISTINCT contact_id), 0),
            2
        ) as atl_ratio_pct
    FROM dim_contacts
),
all_enrichment_costs AS (
    SELECT
        ROUND(COALESCE(SUM(cost_usd), 0)::numeric, 2) as total_cost_usd,
        COUNT(*) FILTER (WHERE success = TRUE) as total_successful_attempts,
        COUNT(*) FILTER (WHERE success = FALSE) as total_failed_attempts,
        COUNT(*) as total_enrichment_attempts,
        ROUND(
            100.0 * COUNT(*) FILTER (WHERE success = TRUE) /
            NULLIF(COUNT(*), 0),
            2
        ) as overall_success_rate_pct
    FROM fact_enrichment_attempts
)
SELECT
    ac.total_companies,
    ac.platinum_companies,
    ac.gold_companies,
    ac.silver_companies,
    ac.bronze_companies,
    ac.unscored_companies,
    ac.avg_icp_score,
    ac.flagged_for_reenrich,
    ac.enriched_companies,
    ROUND(
        100.0 * COALESCE(ac.enriched_companies, 0) /
        NULLIF(ac.total_companies, 0),
        2
    ) as enrichment_coverage_pct,
    cts.total_contacts,
    cts.total_atl_contacts,
    cts.total_btl_contacts,
    cts.contacts_with_email,
    cts.contacts_with_phone,
    cts.validated_contacts,
    cts.atl_ratio_pct,
    ROUND(
        100.0 * COALESCE(cts.contacts_with_email, 0) /
        NULLIF(cts.total_contacts, 0),
        2
    ) as email_coverage_pct,
    COALESCE(ec.total_cost_usd, 0) as total_cost_usd,
    COALESCE(ec.total_successful_attempts, 0) as total_successful_attempts,
    COALESCE(ec.total_failed_attempts, 0) as total_failed_attempts,
    COALESCE(ec.total_enrichment_attempts, 0) as total_enrichment_attempts,
    COALESCE(ec.overall_success_rate_pct, 0) as overall_success_rate_pct,
    CASE
        WHEN COALESCE(ec.total_cost_usd, 0) > 0 AND cts.total_atl_contacts > 0 THEN
            ROUND((COALESCE(ec.total_cost_usd, 0) / cts.total_atl_contacts)::numeric, 2)
        ELSE 0
    END as cost_per_atl_contact
FROM all_companies ac, all_contacts cts, all_enrichment_costs ec;

COMMENT ON VIEW v_enrichment_totals IS
'Grand totals across entire pipeline: company counts by ICP tier, total contacts (ATL/BTL),
email/phone coverage, and enrichment costs. Single row showing portfolio overview.';

-- ============================================
-- 3. v_contact_totals
-- ============================================
-- Contact breakdown by enrichment source (hunter, apollo, linkedin, browserbase, manual)
CREATE OR REPLACE VIEW v_contact_totals AS
WITH contact_sources AS (
    SELECT
        COALESCE(ct.source, 'unknown') as contact_source,
        COUNT(DISTINCT ct.contact_id) as total_contacts,
        COUNT(DISTINCT ct.contact_id) FILTER (
            WHERE ct.is_atl = TRUE
        ) as atl_contacts,
        COUNT(DISTINCT ct.contact_id) FILTER (
            WHERE ct.is_atl = FALSE
        ) as btl_contacts,
        COUNT(DISTINCT ct.contact_id) FILTER (
            WHERE ct.email IS NOT NULL
        ) as contacts_with_email,
        COUNT(DISTINCT ct.contact_id) FILTER (
            WHERE ct.phone IS NOT NULL
        ) as contacts_with_phone,
        COUNT(DISTINCT ct.contact_id) FILTER (
            WHERE ct.validated = TRUE
        ) as validated_contacts,
        ROUND(AVG(NULLIF(ct.confidence, 0))::numeric, 2) as avg_confidence_score,
        COUNT(DISTINCT ct.contact_id) FILTER (
            WHERE ct.is_atl = TRUE
        )::float / NULLIF(COUNT(DISTINCT ct.contact_id)::float, 0) as atl_ratio
    FROM dim_contacts ct
    GROUP BY COALESCE(ct.source, 'unknown')
)
SELECT
    contact_source,
    total_contacts,
    atl_contacts,
    btl_contacts,
    contacts_with_email,
    contacts_with_phone,
    validated_contacts,
    ROUND(100.0 * atl_ratio, 2) as atl_ratio_pct,
    ROUND(
        100.0 * COALESCE(contacts_with_email, 0) /
        NULLIF(total_contacts, 0),
        2
    ) as email_coverage_pct,
    ROUND(
        100.0 * COALESCE(validated_contacts, 0) /
        NULLIF(total_contacts, 0),
        2
    ) as validation_rate_pct,
    avg_confidence_score
FROM contact_sources
ORDER BY total_contacts DESC;

COMMENT ON VIEW v_contact_totals IS
'Contact totals by enrichment source (hunter, apollo, linkedin, browserbase, manual).
Shows quality metrics: ATL ratio, email coverage, validation rate, and average confidence score.
Use for evaluating enrichment source quality and prioritizing contact sources.';

-- ============================================
-- 4. v_enrichment_attempt_totals
-- ============================================
-- Enrichment attempt success rates and costs by source
CREATE OR REPLACE VIEW v_enrichment_attempt_totals AS
SELECT
    COALESCE(fea.source, 'unknown') as enrichment_source,
    COUNT(*) as total_attempts,
    COUNT(*) FILTER (
        WHERE fea.success = TRUE
    ) as successful_attempts,
    COUNT(*) FILTER (
        WHERE fea.success = FALSE
    ) as failed_attempts,
    ROUND(
        100.0 * COUNT(*) FILTER (WHERE fea.success = TRUE) /
        NULLIF(COUNT(*), 0),
        2
    ) as success_rate_pct,
    COUNT(DISTINCT fea.company_id) as companies_processed,
    COALESCE(SUM(fea.contacts_found), 0) as total_contacts_found,
    COALESCE(SUM(fea.atl_found), 0) as total_atl_found,
    COALESCE(SUM(fea.btl_found), 0) as total_btl_found,
    COALESCE(SUM(fea.emails_found), 0) as total_emails_found,
    COALESCE(SUM(fea.phones_found), 0) as total_phones_found,
    ROUND(COALESCE(SUM(fea.cost_usd), 0)::numeric, 2) as total_cost_usd,
    ROUND(
        COALESCE(AVG(NULLIF(fea.cost_usd, 0)), 0)::numeric,
        6
    ) as avg_cost_per_attempt,
    CASE
        WHEN COALESCE(SUM(fea.cost_usd), 0) > 0 AND COALESCE(SUM(fea.atl_found), 0) > 0 THEN
            ROUND((COALESCE(SUM(fea.cost_usd), 0) / COALESCE(SUM(fea.atl_found), 0))::numeric, 2)
        ELSE 0
    END as cost_per_atl_contact,
    CASE
        WHEN COALESCE(SUM(fea.cost_usd), 0) > 0 AND COALESCE(SUM(fea.contacts_found), 0) > 0 THEN
            ROUND((COALESCE(SUM(fea.cost_usd), 0) / COALESCE(SUM(fea.contacts_found), 0))::numeric, 2)
        ELSE 0
    END as cost_per_contact,
    COALESCE(SUM(fea.api_credits_used), 0) as total_api_credits_used,
    ROUND(
        COALESCE(AVG(NULLIF(fea.latency_ms, 0)), 0)::numeric,
        2
    ) as avg_latency_ms,
    COUNT(DISTINCT DATE(fea.attempted_at)) as days_with_activity,
    MAX(fea.attempted_at) as last_attempt_at
FROM fact_enrichment_attempts fea
GROUP BY COALESCE(fea.source, 'unknown')
ORDER BY total_attempts DESC;

COMMENT ON VIEW v_enrichment_attempt_totals IS
'Enrichment API attempt metrics by source: success rates, contact yields, costs, and performance.
Shows cost per ATL contact and cost per total contact for ROI analysis.
Use for identifying cost-effective enrichment sources and diagnosing API failures.';

-- ============================================
-- 5. Create indexes for view performance
-- ============================================
CREATE INDEX IF NOT EXISTS idx_fact_enrichment_attempts_source_success
ON fact_enrichment_attempts(source, success);

CREATE INDEX IF NOT EXISTS idx_fact_enrichment_attempts_source_cost
ON fact_enrichment_attempts(source, cost_usd);

CREATE INDEX IF NOT EXISTS idx_dim_contacts_source_atl
ON dim_contacts(source, is_atl) WHERE is_atl = TRUE;

CREATE INDEX IF NOT EXISTS idx_dim_companies_original_source_tier
ON dim_companies(original_source, icp_tier);

-- ============================================
-- 6. Verification queries (run manually to validate)
-- ============================================
-- SELECT * FROM v_enrichment_summary;
-- SELECT * FROM v_enrichment_totals;
-- SELECT * FROM v_contact_totals;
-- SELECT * FROM v_enrichment_attempt_totals;
--
-- -- Validate contacts add up
-- -- SELECT
-- --     SUM(total_contacts) as all_contacts_from_view,
-- --     (SELECT COUNT(*) FROM dim_contacts) as actual_contacts
-- -- FROM v_contact_totals;
--
-- -- Validate no overlapping counts
-- -- SELECT original_source, SUM(total_companies) FROM v_enrichment_summary GROUP BY 1;
