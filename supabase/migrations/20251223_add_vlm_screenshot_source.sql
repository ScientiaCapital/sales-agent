-- =====================================================================
-- Add vlm_screenshot to fact_enrichment_attempts source constraint
-- =====================================================================
-- Created: 2025-12-23
-- Purpose: Enable VLM screenshot extraction tracking in enrichment attempts
-- =====================================================================

-- Drop the existing constraint
ALTER TABLE fact_enrichment_attempts
DROP CONSTRAINT IF EXISTS fact_enrichment_attempts_source_check;

-- Add new constraint with vlm_screenshot
ALTER TABLE fact_enrichment_attempts
ADD CONSTRAINT fact_enrichment_attempts_source_check
CHECK (source IN (
    'hunter_io',
    'apollo_free',
    'apollo_paid',
    'linkedin',
    'browserbase',
    'ai_enrichment',
    'vlm_screenshot',  -- NEW: VLM-based screenshot contact extraction
    'website_scrape'   -- Generic website scraping
));

-- Also add vlm_screenshot to dim_sources if not exists
INSERT INTO dim_sources (source_name, source_type, project)
VALUES ('vlm_screenshot', 'api', 'sales-agent')
ON CONFLICT (source_name) DO NOTHING;

-- Add comment
COMMENT ON CONSTRAINT fact_enrichment_attempts_source_check ON fact_enrichment_attempts
IS 'Allowed enrichment sources: hunter_io, apollo_free, apollo_paid, linkedin, browserbase, ai_enrichment, vlm_screenshot, website_scrape';
