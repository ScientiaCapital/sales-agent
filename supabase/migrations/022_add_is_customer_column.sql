-- =====================================================
-- Add is_customer column to dim_companies
-- Purpose: Filter out existing customers from BDR prospecting views
-- Author: Claude
-- Date: Dec 7, 2025
-- =====================================================

-- Add is_customer column to dim_companies
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS is_customer BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.is_customer IS
  'True if company is already a customer (exclude from prospecting queues)';

-- Create index for efficient customer filtering
CREATE INDEX IF NOT EXISTS idx_companies_is_customer
  ON dim_companies(is_customer) WHERE is_customer = TRUE;

-- Mark known customers
-- Future Energy Today and Terra Energy mentioned by user as customers
UPDATE dim_companies
SET is_customer = TRUE
WHERE company_name ILIKE '%future energy today%'
   OR company_name ILIKE '%terra energy%';

-- Show updated records
SELECT company_name, is_customer
FROM dim_companies
WHERE is_customer = TRUE;
