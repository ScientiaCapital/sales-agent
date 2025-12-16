-- Migration: Separate Close CRM leads from pipeline
-- Date: 2025-12-15
-- Purpose: Protect discovered leads from Close CRM sync deletions
--
-- Architecture:
--   dim_companies_close  -> Archive of Close CRM leads (frozen, read-only)
--   dim_companies        -> YOUR pipeline (dealer-scraper + enrichment)
--   v_all_companies      -> View when you need to see everything

-- Step 1: Create archive table for Close CRM leads
-- This copies the entire table structure including all columns
CREATE TABLE IF NOT EXISTS dim_companies_close AS
SELECT * FROM dim_companies
WHERE close_lead_id IS NOT NULL;

-- Step 2: Add primary key to archive table
ALTER TABLE dim_companies_close
ADD PRIMARY KEY (company_id);

-- Step 3: Add indexes to archive table (match original)
CREATE INDEX IF NOT EXISTS idx_close_archive_close_lead_id
ON dim_companies_close(close_lead_id);

CREATE INDEX IF NOT EXISTS idx_close_archive_company_name
ON dim_companies_close(company_name);

CREATE INDEX IF NOT EXISTS idx_close_archive_icp_tier
ON dim_companies_close(icp_tier);

-- Step 4: Remove Close CRM leads from main pipeline table
-- This leaves dim_companies clean for YOUR discovered leads
DELETE FROM dim_companies
WHERE close_lead_id IS NOT NULL;

-- Step 5: Create unified view for when you need everything
CREATE OR REPLACE VIEW v_all_companies AS
SELECT *, 'close_archive'::text as table_source FROM dim_companies_close
UNION ALL
SELECT *, 'pipeline'::text as table_source FROM dim_companies;

-- Step 6: Add original_source column to track lead origin
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS original_source TEXT;

ALTER TABLE dim_companies_close
ADD COLUMN IF NOT EXISTS original_source TEXT;

-- Step 7: Backfill original_source for Close archive
UPDATE dim_companies_close
SET original_source = 'close_crm'
WHERE original_source IS NULL;

-- Step 8: Enable RLS on archive table (same policy as dim_companies)
ALTER TABLE dim_companies_close ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access to close archive"
ON dim_companies_close
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Verification queries (run manually):
-- SELECT 'close_archive' as table, COUNT(*) FROM dim_companies_close;
-- SELECT 'pipeline' as table, COUNT(*) FROM dim_companies;
-- SELECT COUNT(*) FROM v_all_companies;
