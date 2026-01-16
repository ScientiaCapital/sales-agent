-- =============================================================================
-- MATERIALIZED VIEW: mv_top500_icp (Jan 16, 2026)
-- =============================================================================
-- Top 500 ICP companies with ATL contacts for Q1 outreach campaign.
-- Pre-computed for fast dashboard queries and CSV exports.
-- =============================================================================

-- Drop existing view if exists (for idempotency)
DROP MATERIALIZED VIEW IF EXISTS mv_top500_icp CASCADE;

-- Create materialized view for top 500 ICP leads with ATL contacts
CREATE MATERIALIZED VIEW mv_top500_icp AS
WITH ranked_contacts AS (
    -- Rank ATL contacts per company by quality
    SELECT
        ct.contact_id,
        ct.company_id,
        ct.full_name,
        ct.first_name,
        ct.last_name,
        ct.title,
        ct.email,
        ct.phone,
        ct.linkedin_url,
        ct.is_atl,
        ct.confidence,
        ct.source,
        ct.validated,
        ROW_NUMBER() OVER (
            PARTITION BY ct.company_id
            ORDER BY
                (CASE WHEN ct.phone IS NOT NULL THEN 1 ELSE 0 END) DESC,
                (CASE WHEN ct.validated THEN 1 ELSE 0 END) DESC,
                COALESCE(ct.confidence, 50) DESC,
                ct.created_at ASC
        ) as contact_rank
    FROM dim_contacts ct
    WHERE ct.is_atl = TRUE
      AND ct.email IS NOT NULL
      AND ct.email != ''
),
company_contact_stats AS (
    -- Aggregate contact stats per company
    SELECT
        company_id,
        COUNT(*) as atl_count,
        SUM(CASE WHEN phone IS NOT NULL THEN 1 ELSE 0 END) as atl_with_phone,
        SUM(CASE WHEN validated THEN 1 ELSE 0 END) as atl_verified
    FROM ranked_contacts
    GROUP BY company_id
),
scored_companies AS (
    -- Calculate composite score for ranking
    SELECT
        c.company_id,
        c.company_name,
        c.domain,
        c.website,
        c.phone as company_phone,
        c.city,
        c.state,
        c.icp_score,
        c.icp_tier,
        c.has_hvac_trade,
        c.is_mep_contractor,
        c.has_commercial,
        c.has_industrial,
        c.has_residential,
        c.is_multi_trade,
        c.trade_count,
        c.oem_count,
        c.intent_score,
        ccs.atl_count,
        ccs.atl_with_phone,
        ccs.atl_verified,
        -- Composite scoring (industry + phone + ATL quality)
        (
            COALESCE(c.icp_score, 0) +
            CASE WHEN c.has_hvac_trade THEN 200 ELSE 0 END +
            CASE WHEN c.is_mep_contractor THEN 150 ELSE 0 END +
            CASE WHEN c.is_multi_trade THEN 100 ELSE 0 END +
            CASE WHEN c.has_commercial THEN 50 ELSE 0 END +
            CASE WHEN c.has_industrial THEN 50 ELSE 0 END +
            CASE WHEN c.has_residential THEN 25 ELSE 0 END +
            CASE WHEN ccs.atl_with_phone > 0 THEN 150 ELSE 0 END +
            LEAST(ccs.atl_verified * 20, 50)
        ) as total_score
    FROM dim_companies c
    INNER JOIN company_contact_stats ccs ON c.company_id = ccs.company_id
    WHERE (c.close_lead_id IS NULL OR c.close_lead_id = '')
      AND c.became_customer_at IS NULL
      AND (c.is_excluded IS NULL OR c.is_excluded = FALSE)
)
SELECT
    sc.company_id,
    sc.company_name,
    sc.domain,
    sc.website,
    sc.company_phone,
    sc.city,
    sc.state,
    sc.icp_score,
    sc.icp_tier,
    sc.total_score,
    sc.atl_count,
    sc.atl_with_phone > 0 as has_phone,
    sc.has_hvac_trade,
    sc.is_mep_contractor,
    sc.has_commercial,
    sc.has_industrial,
    sc.has_residential,
    sc.is_multi_trade,
    sc.trade_count,
    sc.oem_count,
    sc.intent_score,
    -- Best contact info (rank 1)
    rc.contact_id,
    COALESCE(rc.full_name, CONCAT(rc.first_name, ' ', rc.last_name)) as atl_name,
    rc.title as atl_title,
    rc.email as atl_email,
    rc.phone as atl_phone,
    rc.linkedin_url as atl_linkedin,
    rc.validated as atl_verified,
    rc.confidence as atl_confidence,
    rc.source as atl_source,
    ROW_NUMBER() OVER (ORDER BY sc.total_score DESC) as rank
FROM scored_companies sc
LEFT JOIN ranked_contacts rc ON sc.company_id = rc.company_id AND rc.contact_rank = 1
ORDER BY sc.total_score DESC
LIMIT 500;

-- Create unique index for fast lookups and refresh
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_top500_contact ON mv_top500_icp(contact_id);
CREATE INDEX IF NOT EXISTS idx_mv_top500_company ON mv_top500_icp(company_id);
CREATE INDEX IF NOT EXISTS idx_mv_top500_rank ON mv_top500_icp(rank);
CREATE INDEX IF NOT EXISTS idx_mv_top500_tier ON mv_top500_icp(icp_tier);
CREATE INDEX IF NOT EXISTS idx_mv_top500_state ON mv_top500_icp(state);

-- Add comment for documentation
COMMENT ON MATERIALIZED VIEW mv_top500_icp IS
'Top 500 ICP companies with ATL contacts for outreach.
Criteria: Email required, Phone preferred, Not in Close CRM, Not customers.
Refresh with: REFRESH MATERIALIZED VIEW CONCURRENTLY mv_top500_icp;';

-- Grant read access (adjust role as needed)
-- GRANT SELECT ON mv_top500_icp TO authenticated;
