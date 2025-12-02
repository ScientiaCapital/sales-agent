-- Migration: Add Hunter.io and Apollo PAID enrichment tracking columns
-- Created: 2025-12-02
-- Purpose: Track Hunter.io and Apollo PAID enrichment status

-- Add Hunter.io enrichment timestamp
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS hunter_enriched_at TIMESTAMPTZ;

COMMENT ON COLUMN dim_companies.hunter_enriched_at IS
'Timestamp of when Hunter.io enrichment was last performed on this company record';

-- Add Apollo PAID enrichment timestamp
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS apollo_paid_enriched_at TIMESTAMPTZ;

COMMENT ON COLUMN dim_companies.apollo_paid_enriched_at IS
'Timestamp of when Apollo PAID reveal enrichment was last performed on this company record';

-- Indexes for finding companies needing enrichment
CREATE INDEX IF NOT EXISTS idx_companies_hunter_enriched
ON dim_companies (hunter_enriched_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_companies_apollo_paid_enriched
ON dim_companies (apollo_paid_enriched_at DESC NULLS LAST);

-- Verification
DO $$
DECLARE
    missing_columns TEXT[];
BEGIN
    SELECT ARRAY_AGG(column_name)
    INTO missing_columns
    FROM (
        SELECT 'hunter_enriched_at' AS column_name
        UNION SELECT 'apollo_paid_enriched_at'
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

