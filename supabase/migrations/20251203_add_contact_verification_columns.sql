-- Migration: Add verification columns to dim_contacts for Apollo enrichment tracking
-- Date: 2025-12-03
-- Purpose: Track which emails/phones are verified by Apollo paid reveal vs scraped

-- Add email verification flag
ALTER TABLE dim_contacts
ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;

-- Add phone verification flag
ALTER TABLE dim_contacts
ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE;

-- Add Apollo enrichment timestamp (contact-level, not just company-level)
ALTER TABLE dim_contacts
ADD COLUMN IF NOT EXISTS apollo_enriched_at TIMESTAMPTZ;

-- Add Apollo person ID for matching webhook callbacks
ALTER TABLE dim_contacts
ADD COLUMN IF NOT EXISTS apollo_person_id VARCHAR(100);

-- Comments for documentation
COMMENT ON COLUMN dim_contacts.email_verified IS 'True if email was verified by Apollo paid reveal (not just scraped)';
COMMENT ON COLUMN dim_contacts.phone_verified IS 'True if phone was verified by Apollo paid reveal via webhook';
COMMENT ON COLUMN dim_contacts.apollo_enriched_at IS 'Timestamp when contact was enriched via Apollo paid API';
COMMENT ON COLUMN dim_contacts.apollo_person_id IS 'Apollo internal person ID for matching async webhook callbacks';

-- Index for finding contacts needing enrichment
CREATE INDEX IF NOT EXISTS idx_dim_contacts_apollo_enriched
ON dim_contacts(apollo_enriched_at)
WHERE apollo_enriched_at IS NULL;

-- Index for Apollo person ID lookups (webhook matching)
CREATE INDEX IF NOT EXISTS idx_dim_contacts_apollo_person_id
ON dim_contacts(apollo_person_id)
WHERE apollo_person_id IS NOT NULL;
