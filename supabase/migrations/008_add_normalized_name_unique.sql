-- =============================================================================
-- ADD UNIQUE CONSTRAINT ON normalized_name (Nov 29, 2025)
-- =============================================================================
-- Required for upsert operations when syncing Gold Standard leads.
-- This enables "ON CONFLICT (normalized_name) DO UPDATE" pattern.
-- =============================================================================

-- First, deduplicate: Keep the most recently created record for each normalized_name
-- Delete older duplicates (keeping the one with the highest id/latest created_at)
DELETE FROM dim_companies
WHERE company_id IN (
    SELECT company_id FROM (
        SELECT company_id,
               ROW_NUMBER() OVER (
                   PARTITION BY normalized_name
                   ORDER BY created_at DESC NULLS LAST, company_id DESC
               ) as rn
        FROM dim_companies
        WHERE normalized_name IS NOT NULL
    ) ranked
    WHERE rn > 1
);

-- Now add the unique constraint (will succeed after dedup)
ALTER TABLE dim_companies
DROP CONSTRAINT IF EXISTS uq_dim_companies_normalized_name;

ALTER TABLE dim_companies
ADD CONSTRAINT uq_dim_companies_normalized_name UNIQUE (normalized_name);

-- Also add unique constraint on email for dim_contacts (for upsert contacts)
-- First dedupe contacts by email
DELETE FROM dim_contacts
WHERE contact_id IN (
    SELECT contact_id FROM (
        SELECT contact_id,
               ROW_NUMBER() OVER (
                   PARTITION BY email
                   ORDER BY created_at DESC NULLS LAST, contact_id DESC
               ) as rn
        FROM dim_contacts
        WHERE email IS NOT NULL
    ) ranked
    WHERE rn > 1
);

ALTER TABLE dim_contacts
DROP CONSTRAINT IF EXISTS uq_dim_contacts_email;

ALTER TABLE dim_contacts
ADD CONSTRAINT uq_dim_contacts_email UNIQUE (email);

-- Report dedup results
DO $$
BEGIN
    RAISE NOTICE 'Deduplication complete. Unique constraints added.';
END $$;
