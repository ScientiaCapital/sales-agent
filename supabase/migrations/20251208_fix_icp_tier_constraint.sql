-- =====================================================
-- Fix ICP Tier Constraint: Add 'LEAD' Tier
-- =====================================================
-- ISSUE: dim_companies.icp_tier constraint only allows
--        ('PLATINUM', 'GOLD', 'SILVER', 'BRONZE')
--        but code uses 'LEAD' for low-scoring companies
--
-- FIX: Add 'LEAD' to allowed values
-- =====================================================

-- Drop existing constraint
ALTER TABLE dim_companies
DROP CONSTRAINT IF EXISTS dim_companies_icp_tier_check;

-- Add new constraint with 'LEAD' included
ALTER TABLE dim_companies
ADD CONSTRAINT dim_companies_icp_tier_check
CHECK (icp_tier IN ('PLATINUM', 'GOLD', 'SILVER', 'BRONZE', 'LEAD'));

-- Add comment explaining tier meanings
COMMENT ON COLUMN dim_companies.icp_tier IS
  'ICP tier classification:
   PLATINUM (80+): Best leads (ATL + email + phone + OEM certified)
   GOLD (65-79): Strong leads (ATL + email + phone)
   SILVER (50-64): Good leads (ATL + phone)
   BRONZE (35-49): Working pipeline (has phone or email)
   LEAD (<35): Needs enrichment (minimal contact info)';
