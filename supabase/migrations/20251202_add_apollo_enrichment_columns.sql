-- Migration: Add Apollo enrichment tracking columns
-- Created: 2025-12-02
-- Purpose: Track Apollo FREE enrichment status and store Apollo company data

-- Add Apollo enrichment timestamp
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS apollo_enriched_at TIMESTAMPTZ;

COMMENT ON COLUMN dim_companies.apollo_enriched_at IS
'Timestamp of when Apollo FREE enrichment was last performed on this company record';

-- Add industry column (if not exists)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS industry VARCHAR(255);

COMMENT ON COLUMN dim_companies.industry IS
'Company industry from Apollo enrichment (e.g., "HVAC", "Electrical Contracting")';

-- Add LinkedIn URL column for companies (if not exists)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500);

COMMENT ON COLUMN dim_companies.linkedin_url IS
'Company LinkedIn page URL from Apollo enrichment';

-- Add country column (if not exists)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS country VARCHAR(100);

COMMENT ON COLUMN dim_companies.country IS
'Company country from Apollo enrichment';

-- Index for finding companies needing Apollo enrichment
CREATE INDEX IF NOT EXISTS idx_companies_apollo_enriched
ON dim_companies (apollo_enriched_at DESC NULLS LAST);

-- Index for finding companies by industry
CREATE INDEX IF NOT EXISTS idx_companies_industry
ON dim_companies (industry)
WHERE industry IS NOT NULL;

-- Verification
DO $$
DECLARE
    missing_columns TEXT[];
BEGIN
    SELECT ARRAY_AGG(column_name)
    INTO missing_columns
    FROM (
        SELECT 'apollo_enriched_at' AS column_name
        UNION SELECT 'industry'
        UNION SELECT 'linkedin_url'
        UNION SELECT 'country'
    ) expected
    WHERE NOT EXISTS (
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'dim_companies'
        AND column_name = expected.column_name
    );
    
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE EXCEPTION 'Missing columns: %', array_to_string(missing_columns, ', ');
    END IF;
END $$;

