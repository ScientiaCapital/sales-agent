-- =============================================================================
-- Add team_page_url tracking to dim_companies
-- =============================================================================
-- This enables smarter Browserbase targeting:
-- - BeautifulSoup records the team page URL it found (200 OK)
-- - Browserbase only targets companies WITH team_page_url but WITHOUT contacts
-- - No more wasting Browserbase sessions on sites with no team pages
-- =============================================================================

-- Add team page URL column
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS team_page_url TEXT;

-- Add enrichment status to track what happened
-- 'found_contacts' = BeautifulSoup found contacts
-- 'found_page_no_contacts' = Found team page but no contacts (Browserbase candidate!)
-- 'no_team_page' = No team page exists (skip Browserbase)
-- 'needs_js_render' = Explicitly flagged for Browserbase
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS enrichment_status VARCHAR(50);

-- Index for Browserbase targeting
CREATE INDEX IF NOT EXISTS idx_dim_companies_team_page
ON dim_companies(team_page_url)
WHERE team_page_url IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_dim_companies_enrichment_status
ON dim_companies(enrichment_status);

-- Comment
COMMENT ON COLUMN dim_companies.team_page_url IS 'URL of team/about page discovered by BeautifulSoup (200 OK response)';
COMMENT ON COLUMN dim_companies.enrichment_status IS 'found_contacts | found_page_no_contacts | no_team_page | needs_js_render';
