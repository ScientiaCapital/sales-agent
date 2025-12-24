-- =============================================================================
-- MIGRATION: Constraints + Error Logging Table
-- =============================================================================
-- Run this AFTER garbage cleanup and deduplication have been done via Python
-- =============================================================================

-- Step 1: Create fact_enrichment_errors table for save verification logging

CREATE TABLE IF NOT EXISTS fact_enrichment_errors (
    error_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES dim_companies(company_id),
    entity_type TEXT NOT NULL,  -- 'contact', 'signal', 'company'
    entity_id UUID,
    error_type TEXT NOT NULL,   -- 'validation', 'readback_failed', 'data_corruption', 'insert_exception'
    error_message TEXT NOT NULL,
    source TEXT,                -- 'vlm_screenshot', 'hunter_io', 'apollo', etc.
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_enrichment_errors_company ON fact_enrichment_errors(company_id);
CREATE INDEX IF NOT EXISTS idx_enrichment_errors_type ON fact_enrichment_errors(error_type);
CREATE INDEX IF NOT EXISTS idx_enrichment_errors_created ON fact_enrichment_errors(created_at DESC);

-- Step 2: Enable RLS on fact_enrichment_errors

ALTER TABLE fact_enrichment_errors ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role full access on fact_enrichment_errors"
ON fact_enrichment_errors FOR ALL
USING (true)
WITH CHECK (true);

-- Step 3: Create unique constraint to prevent duplicate contacts per company
-- Uses LOWER(TRIM()) to catch "John Smith" vs "john smith" duplicates

CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_unique_per_company
ON dim_contacts (company_id, LOWER(TRIM(full_name)))
WHERE full_name IS NOT NULL AND full_name != '';

-- Step 4: Add NOT NULL constraint on company_id (must have a parent company)

ALTER TABLE dim_contacts
ALTER COLUMN company_id SET NOT NULL;

-- Step 5: Add CHECK constraint for minimum name length

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'check_contact_name_length'
    ) THEN
        ALTER TABLE dim_contacts
        ADD CONSTRAINT check_contact_name_length CHECK (
            full_name IS NOT NULL AND LENGTH(TRIM(full_name)) >= 3
        );
    END IF;
END $$;

-- Step 6: Create index for dedup queries (used by save verification)

CREATE INDEX IF NOT EXISTS idx_contacts_company_source
ON dim_contacts (company_id, source);

-- Step 7: Create index for fast lookups by source (for cleanup/audit)

CREATE INDEX IF NOT EXISTS idx_contacts_source
ON dim_contacts (source);

-- Step 8: Add created_at NOT NULL with default

ALTER TABLE dim_contacts
ALTER COLUMN created_at SET DEFAULT NOW();

ALTER TABLE dim_contacts
ALTER COLUMN created_at SET NOT NULL;

-- =============================================================================
-- VERIFICATION: Run these to confirm constraints are in place
-- =============================================================================
--
-- Check unique constraint exists:
-- SELECT indexname FROM pg_indexes WHERE tablename = 'dim_contacts' AND indexname = 'idx_contacts_unique_per_company';
--
-- Check NOT NULL constraints:
-- SELECT column_name, is_nullable FROM information_schema.columns
-- WHERE table_name = 'dim_contacts' AND column_name IN ('company_id', 'created_at');
--
-- =============================================================================
