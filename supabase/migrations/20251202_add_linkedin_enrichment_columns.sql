-- Migration: Add LinkedIn enrichment tracking column
-- Created: 2025-12-02
-- Purpose: Track LinkedIn enrichment status

-- Add LinkedIn enrichment timestamp
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS linkedin_enriched_at TIMESTAMPTZ;

COMMENT ON COLUMN dim_companies.linkedin_enriched_at IS
'Timestamp of when LinkedIn enrichment was last performed on this company record';

-- Index for finding companies needing LinkedIn enrichment
CREATE INDEX IF NOT EXISTS idx_companies_linkedin_enriched
ON dim_companies (linkedin_enriched_at DESC NULLS LAST);

-- Verification
DO $$
DECLARE
    missing_columns TEXT[];
BEGIN
    SELECT ARRAY_AGG(column_name)
    INTO missing_columns
    FROM (
        SELECT 'linkedin_enriched_at' AS column_name
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

