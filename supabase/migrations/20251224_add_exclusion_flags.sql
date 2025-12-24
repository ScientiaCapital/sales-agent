-- =============================================================================
-- MIGRATION: Add Exclusion Flags for Non-ICP Companies
-- =============================================================================
-- Purpose: Flag companies that don't fit Coperniq ICP so they're excluded
-- from all future lists, queries, and enrichment runs
-- =============================================================================

-- Add exclusion columns
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_excluded BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS exclusion_reason TEXT;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS excluded_at TIMESTAMPTZ;

-- Index for fast filtering
CREATE INDEX IF NOT EXISTS idx_companies_excluded ON dim_companies(is_excluded) WHERE is_excluded = TRUE;
CREATE INDEX IF NOT EXISTS idx_companies_not_excluded ON dim_companies(is_excluded) WHERE is_excluded = FALSE;

-- =============================================================================
-- FLAG NON-ICP COMPANIES
-- =============================================================================

-- 1. No website (can't verify ICP - these are garbage leads)
UPDATE dim_companies
SET
    is_excluded = TRUE,
    exclusion_reason = 'no_website',
    excluded_at = NOW()
WHERE website IS NULL
  AND is_excluded IS NOT TRUE;

-- 2. Wrong industry keywords in company name (obvious non-ICP)
-- NOTE: Roofing is NOT excluded - many roofers do solar!
UPDATE dim_companies
SET
    is_excluded = TRUE,
    exclusion_reason = 'wrong_industry',
    excluded_at = NOW()
WHERE (
    LOWER(company_name) LIKE '%flooring%'
    OR LOWER(company_name) LIKE '%carpet%'
    OR LOWER(company_name) LIKE '%painting%'
    OR LOWER(company_name) LIKE '%landscap%'
    OR LOWER(company_name) LIKE '%lawn%'
    OR LOWER(company_name) LIKE '%pool%'
    OR LOWER(company_name) LIKE '%fence%'
    OR (LOWER(company_name) LIKE '%window%' AND LOWER(company_name) NOT LIKE '%solar%')
    OR LOWER(company_name) LIKE '%garage door%'
    OR LOWER(company_name) LIKE '%pest%'
    OR LOWER(company_name) LIKE '%cleaning%'
    OR LOWER(company_name) LIKE '%maid%'
    OR LOWER(company_name) LIKE '%tree service%'
    OR LOWER(company_name) LIKE '%moving%'
    OR (LOWER(company_name) LIKE '%storage%' AND LOWER(company_name) NOT LIKE '%battery%' AND LOWER(company_name) NOT LIKE '%energy%')
)
AND is_excluded IS NOT TRUE;

-- =============================================================================
-- UPDATE ALL VIEWS TO EXCLUDE FLAGGED COMPANIES
-- =============================================================================

-- Update the main ICP prioritized view
CREATE OR REPLACE VIEW v_icp_prioritized AS
SELECT
    company_id,
    company_name,
    website,
    domain,
    icp_tier,
    icp_score,
    -- Coperniq ICP Core Signals
    is_mep_contractor,
    is_multi_trade,
    is_multi_license,
    is_multi_oem,
    is_self_performing,
    is_asset_centric,
    is_in_icp_size_range,
    trade_count,
    oem_count,
    employee_range,
    revenue_range,
    -- Trade breakdown
    has_electrical_trade,
    has_mechanical_trade,
    has_plumbing_trade,
    has_hvac_trade,
    has_fire_protection,
    -- Capability signals
    has_commercial,
    has_design_build,
    has_engineering,
    has_solar_commercial,
    has_battery_storage,
    has_multi_location,
    has_own_crews,
    has_fleet,
    -- Signal count
    (
        COALESCE(is_mep_contractor::int, 0) +
        COALESCE(is_multi_trade::int, 0) +
        COALESCE(is_multi_license::int, 0) +
        COALESCE(is_multi_oem::int, 0) +
        COALESCE(is_self_performing::int, 0) +
        COALESCE(is_asset_centric::int, 0) +
        COALESCE(is_in_icp_size_range::int, 0) +
        COALESCE(has_electrical_trade::int, 0) +
        COALESCE(has_mechanical_trade::int, 0) +
        COALESCE(has_plumbing_trade::int, 0) +
        COALESCE(has_hvac_trade::int, 0) +
        COALESCE(has_fire_protection::int, 0) +
        COALESCE(has_commercial::int, 0) +
        COALESCE(has_industrial::int, 0) +
        COALESCE(has_design_build::int, 0) +
        COALESCE(has_engineering::int, 0) +
        COALESCE(has_solar_commercial::int, 0) +
        COALESCE(has_battery_storage::int, 0) +
        COALESCE(has_ev_charging::int, 0) +
        COALESCE(has_oem_partnerships::int, 0) +
        COALESCE(has_certifications::int, 0) +
        COALESCE(has_multi_location::int, 0)
    ) AS signal_count,
    enrichment_status,
    last_enriched_at
FROM dim_companies
WHERE
    website IS NOT NULL
    AND (is_excluded IS NULL OR is_excluded = FALSE)  -- EXCLUDE FLAGGED
ORDER BY
    is_in_icp_size_range DESC NULLS LAST,
    (COALESCE(is_mep_contractor::int, 0) + COALESCE(is_multi_trade::int, 0) +
     COALESCE(is_self_performing::int, 0) + COALESCE(is_asset_centric::int, 0)) DESC,
    CASE icp_tier
        WHEN 'PLATINUM' THEN 1
        WHEN 'GOLD' THEN 2
        WHEN 'SILVER' THEN 3
        WHEN 'BRONZE' THEN 4
        ELSE 5
    END,
    icp_score DESC NULLS LAST;

-- Update perfect ICP view
CREATE OR REPLACE VIEW v_coperniq_perfect_icp AS
SELECT *
FROM v_icp_prioritized
WHERE
    is_in_icp_size_range = TRUE
    AND (is_multi_trade = TRUE OR trade_count >= 2)
    AND is_self_performing = TRUE
ORDER BY signal_count DESC, icp_score DESC NULLS LAST;

-- =============================================================================
-- VIEW: Excluded Companies (for audit)
-- =============================================================================

CREATE OR REPLACE VIEW v_excluded_companies AS
SELECT
    company_id,
    company_name,
    website,
    exclusion_reason,
    excluded_at,
    icp_tier
FROM dim_companies
WHERE is_excluded = TRUE
ORDER BY exclusion_reason, company_name;

-- =============================================================================
-- VIEW: Companies needing enrichment (excludes flagged)
-- =============================================================================

CREATE OR REPLACE VIEW v_companies_to_enrich AS
SELECT
    company_id,
    company_name,
    website,
    domain,
    icp_tier,
    icp_score,
    enrichment_status,
    last_enriched_at
FROM dim_companies
WHERE
    website IS NOT NULL
    AND (is_excluded IS NULL OR is_excluded = FALSE)
    AND (enrichment_status IS NULL OR enrichment_status NOT IN ('enriched', 'free_enriched'))
ORDER BY
    CASE icp_tier
        WHEN 'PLATINUM' THEN 1
        WHEN 'GOLD' THEN 2
        WHEN 'SILVER' THEN 3
        WHEN 'BRONZE' THEN 4
        ELSE 5
    END,
    icp_score DESC NULLS LAST;

-- =============================================================================
-- SUMMARY
-- =============================================================================
-- This migration:
-- 1. Adds is_excluded, exclusion_reason, excluded_at columns
-- 2. Flags companies with no website
-- 3. Flags companies with wrong industry keywords
-- 4. Updates all views to exclude flagged companies
-- 5. Creates audit view for excluded companies
-- =============================================================================
