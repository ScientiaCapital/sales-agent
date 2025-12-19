-- Migration: Enhance enrichment_status tracking in dim_companies
-- Date: 2025-12-19
-- Purpose: Expand enrichment_status to track progressive pipeline stages
--
-- EXISTING COLUMN: enrichment_status (currently has: NULL, 'enriched', 'found_page_no_contacts')
--
-- NEW VALUES (progressive pipeline):
--   - 'pending': Needs enrichment (default for NULL)
--   - 'free_enriched': After free enrichment (Hunter.io free, BeautifulSoup)
--   - 'paid_enriched': After paid enrichment (Apollo, Browserbase, LinkedIn)
--   - 'enriched': Full enrichment complete (legacy value - keep for compatibility)
--   - 'failed': Enrichment failed
--   - 'found_page_no_contacts': Page found but no contacts extracted (existing)
--
-- TRACKING COLUMNS (already exist):
--   - last_enriched_at: Timestamp of last enrichment
--   - ai_enriched_at: AI/website enrichment timestamp
--   - hunter_enriched_at: Hunter.io enrichment timestamp
--   - apollo_paid_enriched_at: Apollo paid enrichment timestamp

-- ============================================
-- 1. Update NULL enrichment_status to 'pending'
-- ============================================
UPDATE dim_companies
SET enrichment_status = 'pending'
WHERE enrichment_status IS NULL;

-- ============================================
-- 2. Update already enriched records
-- ============================================
-- Mark as 'free_enriched' if has last_enriched_at but no paid enrichment
UPDATE dim_companies
SET enrichment_status = 'free_enriched'
WHERE last_enriched_at IS NOT NULL
  AND apollo_paid_enriched_at IS NULL
  AND enrichment_status IN ('pending', 'enriched');

-- Mark as 'paid_enriched' if has apollo_paid_enriched_at
UPDATE dim_companies
SET enrichment_status = 'paid_enriched'
WHERE apollo_paid_enriched_at IS NOT NULL
  AND enrichment_status NOT IN ('paid_enriched');

-- ============================================
-- 3. Create index for fast filtering (if not exists)
-- ============================================
CREATE INDEX IF NOT EXISTS idx_dim_companies_enrichment_status
ON dim_companies(enrichment_status);

-- Composite index for enrichment queries
CREATE INDEX IF NOT EXISTS idx_dim_companies_enrichment_domain
ON dim_companies(enrichment_status, domain)
WHERE domain IS NOT NULL;

-- ============================================
-- 4. Add comment for documentation
-- ============================================
COMMENT ON COLUMN dim_companies.enrichment_status IS
'Enrichment pipeline status: pending → free_enriched → paid_enriched → enriched (complete)';

-- ============================================
-- 5. Verification queries (run manually)
-- ============================================
-- SELECT enrichment_status, COUNT(*) as count
-- FROM dim_companies
-- GROUP BY enrichment_status
-- ORDER BY CASE enrichment_status
--     WHEN 'pending' THEN 1
--     WHEN 'free_enriched' THEN 2
--     WHEN 'paid_enriched' THEN 3
--     WHEN 'enriched' THEN 4
--     WHEN 'failed' THEN 5
--     WHEN 'found_page_no_contacts' THEN 6
-- END;

-- Companies ready for FREE enrichment:
-- SELECT company_id, company_name, domain
-- FROM dim_companies
-- WHERE domain IS NOT NULL
--   AND enrichment_status = 'pending'
-- ORDER BY icp_score DESC NULLS LAST;
