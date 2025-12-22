-- Add Missing Enrichment Columns to dim_companies
-- =============================================================================
-- This migration adds all columns that enrichment scripts expect but don't exist
-- Fixes the Apollo token loss issue and enables full enrichment pipeline
-- Created: 2025-12-22

-- Add Apollo enrichment tracking
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS apollo_enriched_at TIMESTAMPTZ;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS apollo_paid_enriched_at TIMESTAMPTZ;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS hunter_enriched_at TIMESTAMPTZ;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS ai_enriched_at TIMESTAMPTZ;

-- Add company profile data (from Apollo/AI)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS company_story TEXT;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS company_vertical VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS industry VARCHAR(100);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS employee_count VARCHAR(50);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS founded_year INTEGER;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500);

-- Add signals (from website scraping)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS is_hiring BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS has_maintenance_plan BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS service_areas JSONB DEFAULT '[]';

-- Add ICP tracking (for ICP scorer)
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS icp_last_checked TIMESTAMPTZ;

-- Add Close CRM sync tracking
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS close_pushed_at TIMESTAMPTZ;
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS first_contact_at TIMESTAMPTZ;

-- Add disposition and deal tracking
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS disposition VARCHAR(50);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS deal_value_usd NUMERIC(12, 2);
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS closed_at TIMESTAMPTZ;

-- Add team page tracking
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS team_page_url VARCHAR(500);

-- Add country for international support
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS country VARCHAR(100) DEFAULT 'USA';

-- Create indexes for new columns
CREATE INDEX IF NOT EXISTS idx_dim_companies_apollo_enriched ON dim_companies(apollo_enriched_at) WHERE apollo_enriched_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dim_companies_ai_enriched ON dim_companies(ai_enriched_at) WHERE ai_enriched_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dim_companies_is_hiring ON dim_companies(is_hiring) WHERE is_hiring = TRUE;
CREATE INDEX IF NOT EXISTS idx_dim_companies_vertical ON dim_companies(company_vertical);
CREATE INDEX IF NOT EXISTS idx_dim_companies_icp_last_checked ON dim_companies(icp_last_checked);

-- Add missing columns to dim_contacts
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS linkedin_url VARCHAR(500);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS department VARCHAR(100);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS seniority VARCHAR(50);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS twitter_handle VARCHAR(100);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_contact_id VARCHAR(100);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS close_pushed_at TIMESTAMPTZ;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS sequence_subscribed_at TIMESTAMPTZ;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS sequence_name VARCHAR(100);
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMPTZ;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE dim_contacts ADD COLUMN IF NOT EXISTS phone_verified BOOLEAN DEFAULT FALSE;

-- Create indexes for new contact columns
CREATE INDEX IF NOT EXISTS idx_dim_contacts_linkedin ON dim_contacts(linkedin_url) WHERE linkedin_url IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dim_contacts_close_id ON dim_contacts(close_contact_id);
CREATE INDEX IF NOT EXISTS idx_dim_contacts_sequence ON dim_contacts(sequence_name) WHERE sequence_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_dim_contacts_email_verified ON dim_contacts(email_verified) WHERE email_verified = TRUE;
CREATE INDEX IF NOT EXISTS idx_dim_contacts_phone_verified ON dim_contacts(phone_verified) WHERE phone_verified = TRUE;

-- Add comments for documentation
COMMENT ON COLUMN dim_companies.apollo_enriched_at IS 'Timestamp when Apollo FREE enrichment completed';
COMMENT ON COLUMN dim_companies.apollo_paid_enriched_at IS 'Timestamp when Apollo PAID reveal (phone/email) completed';
COMMENT ON COLUMN dim_companies.ai_enriched_at IS 'Timestamp when AI enrichment (company_story, vertical) completed';
COMMENT ON COLUMN dim_companies.company_story IS 'AI-generated company description for agent context';
COMMENT ON COLUMN dim_companies.company_vertical IS 'Industry vertical (e.g., HVAC, Plumbing, Electrical)';
COMMENT ON COLUMN dim_companies.is_hiring IS 'TRUE if hiring signals detected on website';
COMMENT ON COLUMN dim_companies.icp_last_checked IS 'Last time ICP scorer ran on this company';
