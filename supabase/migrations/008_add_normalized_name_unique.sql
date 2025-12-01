-- =============================================================================
-- ADD UNIQUE CONSTRAINT ON normalized_name (Nov 29, 2025)
-- =============================================================================
-- Required for upsert operations when syncing Gold Standard leads.
-- This enables "ON CONFLICT (normalized_name) DO UPDATE" pattern.
-- =============================================================================

-- Add unique constraint on normalized_name for dedup/upsert
ALTER TABLE dim_companies
ADD CONSTRAINT uq_dim_companies_normalized_name UNIQUE (normalized_name);

-- Also add unique constraint on email for dim_contacts (for upsert contacts)
ALTER TABLE dim_contacts
ADD CONSTRAINT uq_dim_contacts_email UNIQUE (email);
