-- Add Apollo phone reveal columns to dim_contacts
-- This enables the webhook to update contact phone numbers

ALTER TABLE dim_contacts
ADD COLUMN IF NOT EXISTS apollo_person_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS phone_source VARCHAR(50),
ADD COLUMN IF NOT EXISTS phone_verified_at TIMESTAMPTZ;

-- Index for fast lookup when Apollo webhook arrives
CREATE INDEX IF NOT EXISTS idx_dim_contacts_apollo_person_id
ON dim_contacts(apollo_person_id);

-- Comment for documentation
COMMENT ON COLUMN dim_contacts.apollo_person_id IS 'Apollo person ID for webhook reconciliation';
COMMENT ON COLUMN dim_contacts.phone_source IS 'Source of phone number (apollo_reveal, hunter, vlm, etc)';
COMMENT ON COLUMN dim_contacts.phone_verified_at IS 'Timestamp when phone was verified/added';
