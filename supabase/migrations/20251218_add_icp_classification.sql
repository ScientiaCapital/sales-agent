-- Migration: Add ICP Classification Columns
-- Date: 2025-12-18
-- Purpose: Enable lead segmentation and scoring for targeted enrichment

-- ============================================
-- 1. ADD ICP COLUMNS TO dim_companies
-- ============================================
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS company_vertical TEXT,
-- Values: 'pure_solar', 'solar_plus', 'solar_generators', 'electrical_generators', 'mep_only', 'unknown'

ADD COLUMN IF NOT EXISTS is_service_based BOOLEAN DEFAULT FALSE,
-- True = recurring revenue potential (service contracts, maintenance)

ADD COLUMN IF NOT EXISTS is_multi_location BOOLEAN DEFAULT FALSE,
-- True = multiple office/service locations (scale indicator)

ADD COLUMN IF NOT EXISTS is_srec_state BOOLEAN DEFAULT FALSE,
-- True = located in SREC state (NJ, MA, MD, DC, PA, IL)

ADD COLUMN IF NOT EXISTS icp_score INT DEFAULT 0;
-- Composite score 0-100 based on vertical, service, location, state

-- ============================================
-- 2. CREATE ICP SCORING VIEW
-- ============================================
CREATE OR REPLACE VIEW v_icp_leads AS
SELECT
    c.company_id,
    c.company_name,
    c.domain,
    c.state,
    c.original_source,
    c.company_vertical,
    c.is_service_based,
    c.is_multi_location,
    c.is_srec_state,
    c.icp_score,
    c.icp_tier,
    c.last_enriched_at,
    COUNT(DISTINCT ct.contact_id) as contact_count,
    COUNT(DISTINCT CASE WHEN ct.email IS NOT NULL THEN ct.contact_id END) as contacts_with_email
FROM dim_companies c
LEFT JOIN dim_contacts ct ON c.company_id = ct.company_id
GROUP BY c.company_id, c.company_name, c.domain, c.state, c.original_source,
         c.company_vertical, c.is_service_based, c.is_multi_location,
         c.is_srec_state, c.icp_score, c.icp_tier, c.last_enriched_at
ORDER BY c.icp_score DESC NULLS LAST;

-- ============================================
-- 3. INDEX FOR FAST ICP QUERIES
-- ============================================
CREATE INDEX IF NOT EXISTS idx_dim_companies_icp_score ON dim_companies(icp_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_dim_companies_vertical ON dim_companies(company_vertical);
CREATE INDEX IF NOT EXISTS idx_dim_companies_srec ON dim_companies(is_srec_state) WHERE is_srec_state = TRUE;

COMMENT ON COLUMN dim_companies.company_vertical IS 'Business vertical: pure_solar, solar_plus, solar_generators, electrical_generators, mep_only';
COMMENT ON COLUMN dim_companies.icp_score IS 'ICP score 0-100: higher = better fit for sales outreach';
