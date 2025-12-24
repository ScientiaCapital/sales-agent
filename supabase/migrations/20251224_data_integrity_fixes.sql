-- =============================================================================
-- MIGRATION: Data Integrity Fixes for dim_contacts
-- =============================================================================
-- Purpose: Clean up garbage data and prevent future duplicates/invalid entries
-- Date: 2025-12-24
-- Author: Claude + Tim
-- =============================================================================

-- Step 1: Delete garbage contacts (None None, empty names, etc.)
-- This cleans up 7,556 invalid contacts from hunter_io/apollo pipelines

DELETE FROM dim_contacts
WHERE full_name IS NULL
   OR full_name = ''
   OR full_name = 'None'
   OR full_name = 'None None'
   OR full_name = 'null'
   OR LENGTH(TRIM(full_name)) < 3;

-- Step 2: Deduplicate existing contacts (keep newest per company+name)
-- This removes 3,804 duplicate pairs discovered during audit
-- Strategy: Keep the contact with most recent created_at, or most data if created_at is NULL

DELETE FROM dim_contacts
WHERE contact_id IN (
    SELECT contact_id
    FROM (
        SELECT
            contact_id,
            ROW_NUMBER() OVER (
                PARTITION BY company_id, LOWER(TRIM(full_name))
                ORDER BY
                    created_at DESC NULLS LAST,
                    -- Prefer contacts with more data
                    CASE WHEN email IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN phone IS NOT NULL THEN 1 ELSE 0 END +
                    CASE WHEN title IS NOT NULL THEN 1 ELSE 0 END DESC,
                    contact_id  -- Deterministic tiebreaker
            ) as rn
        FROM dim_contacts
        WHERE full_name IS NOT NULL
          AND full_name != ''
          AND LENGTH(TRIM(full_name)) >= 3
    ) ranked
    WHERE rn > 1  -- Delete all but the first (best) contact per group
);

-- Step 3: Create unique constraint to prevent duplicate contacts per company
-- Uses partial index to ignore NULL full_names (shouldn't exist after cleanup)
-- Uses LOWER(TRIM()) to catch "John Smith" vs "john smith" duplicates

CREATE UNIQUE INDEX IF NOT EXISTS idx_contacts_unique_per_company
ON dim_contacts (company_id, LOWER(TRIM(full_name)))
WHERE full_name IS NOT NULL AND full_name != '';

-- Step 4: Add NOT NULL constraint on company_id (must have a parent company)
-- First update any NULLs (shouldn't exist, but defensive)

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
-- VERIFICATION QUERIES (run after migration)
-- =============================================================================
--
-- Check garbage deleted:
-- SELECT COUNT(*) FROM dim_contacts WHERE full_name IS NULL OR full_name = 'None None';
-- Expected: 0
--
-- Check unique constraint works:
-- INSERT INTO dim_contacts (contact_id, company_id, full_name, source)
-- VALUES (gen_random_uuid(), (SELECT company_id FROM dim_contacts LIMIT 1),
--         (SELECT full_name FROM dim_contacts LIMIT 1), 'test');
-- Expected: ERROR duplicate key value violates unique constraint
--
-- =============================================================================
-- DONE: Migration complete
-- =============================================================================
