-- =====================================================================
-- Add Standard Signal Columns to dim_companies
-- =====================================================================
-- These are the 6 standard signals discovered during manual validation
-- that were missing from the initial enrichment migration.
--
-- Created: 2025-12-22
-- Purpose: Complete the signal tracking before adding HIGH-VALUE signals
-- =====================================================================

-- Generators (sales/installation)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_generators BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_generators IS
'Company sells/installs generators (Generac, Kohler, etc.)';

-- Commercial Services
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_commercial BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_commercial IS
'Company serves commercial clients (offices, retail, multi-family)';

-- Industrial Services (HIGH VALUE)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_industrial BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_industrial IS
'Company serves industrial clients (factories, plants, manufacturing) - HIGH VALUE';

-- Membership/MVP Programs (recurring revenue)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_membership BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_membership IS
'Company offers membership/MVP programs (recurring revenue indicator)';

-- Specials/Promotions (active marketing)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_specials BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_specials IS
'Company has active specials/promotions (marketing activity)';

-- Financing Options (mature company indicator)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_financing BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_financing IS
'Company offers financing options (mature business indicator)';

-- =====================================================================
-- Verification Query
-- =====================================================================
-- Run this to verify all signal columns exist:
--
-- SELECT column_name, data_type
-- FROM information_schema.columns
-- WHERE table_name = 'dim_companies'
--   AND column_name LIKE 'has_%'
-- ORDER BY column_name;
-- =====================================================================
