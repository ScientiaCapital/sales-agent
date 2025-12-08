-- =====================================================
-- Close CRM Schema Parity Migration
-- Adds missing fields to match Close CRM completely
-- =====================================================

-- COMPANIES: Add Close CRM metadata fields
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS close_lead_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS close_created_by VARCHAR(100),
ADD COLUMN IF NOT EXISTS close_description TEXT,
ADD COLUMN IF NOT EXISTS close_status_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS close_raw_data JSONB,
ADD COLUMN IF NOT EXISTS close_custom_fields JSONB DEFAULT '{}';

COMMENT ON COLUMN dim_companies.close_lead_url IS
  'URL to lead in Close CRM dashboard (e.g., https://app.close.com/lead/lead_xxx)';
COMMENT ON COLUMN dim_companies.close_created_by IS
  'Close user ID who created this lead (e.g., user_abc123)';
COMMENT ON COLUMN dim_companies.close_description IS
  'Description field from Close CRM - includes priority labels, enrichment notes';
COMMENT ON COLUMN dim_companies.close_status_id IS
  'Close CRM status ID (e.g., stat_abc123) - enables status filtering';
COMMENT ON COLUMN dim_companies.close_raw_data IS
  'Full Close API response for audit trail and data recovery';
COMMENT ON COLUMN dim_companies.close_custom_fields IS
  'Custom field key-value pairs from Close instance (City, State, etc.)';

-- CONTACTS: Add Close CRM metadata fields
ALTER TABLE dim_contacts
ADD COLUMN IF NOT EXISTS close_contact_id VARCHAR(100) UNIQUE,
ADD COLUMN IF NOT EXISTS close_lead_id VARCHAR(100),
ADD COLUMN IF NOT EXISTS phone_secondary VARCHAR(50),
ADD COLUMN IF NOT EXISTS email_secondary VARCHAR(255),
ADD COLUMN IF NOT EXISTS twitter_url VARCHAR(500),
ADD COLUMN IF NOT EXISTS close_raw_data JSONB,
ADD COLUMN IF NOT EXISTS close_custom_fields JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS close_date_created TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS close_date_updated TIMESTAMPTZ;

COMMENT ON COLUMN dim_contacts.close_contact_id IS
  'Close contact ID (e.g., cont_abc123) - primary reference to Close CRM';
COMMENT ON COLUMN dim_contacts.close_lead_id IS
  'Close lead ID this contact belongs to (e.g., lead_abc123)';
COMMENT ON COLUMN dim_contacts.phone_secondary IS
  'Secondary phone if multiple exist in Close contact.phones[]';
COMMENT ON COLUMN dim_contacts.email_secondary IS
  'Secondary email if multiple exist in Close contact.emails[]';
COMMENT ON COLUMN dim_contacts.twitter_url IS
  'Twitter profile URL from Close contact.urls array';
COMMENT ON COLUMN dim_contacts.close_raw_data IS
  'Full Close API response for this contact';
COMMENT ON COLUMN dim_contacts.close_date_created IS
  'When contact was created in Close CRM';
COMMENT ON COLUMN dim_contacts.close_date_updated IS
  'When contact was last updated in Close CRM';

-- Create indexes for Close sync performance
CREATE INDEX IF NOT EXISTS idx_companies_close_status_id
  ON dim_companies(close_status_id) WHERE close_status_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_companies_close_created_by
  ON dim_companies(close_created_by) WHERE close_created_by IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_contacts_close_contact_id
  ON dim_contacts(close_contact_id) WHERE close_contact_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_contacts_close_lead_id
  ON dim_contacts(close_lead_id) WHERE close_lead_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_contacts_email_secondary
  ON dim_contacts(email_secondary) WHERE email_secondary IS NOT NULL;

-- Add GIN index for JSONB custom fields searching
CREATE INDEX IF NOT EXISTS idx_companies_close_custom_fields
  ON dim_companies USING gin(close_custom_fields);

CREATE INDEX IF NOT EXISTS idx_contacts_close_custom_fields
  ON dim_contacts USING gin(close_custom_fields);
