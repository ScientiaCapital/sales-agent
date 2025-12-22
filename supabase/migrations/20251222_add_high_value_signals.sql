-- =====================================================================
-- Add HIGH-VALUE Signal Columns to dim_companies
-- =====================================================================
-- These signals indicate premium, mature companies with advanced
-- capabilities that command higher ICP scores (10+ points each)
--
-- Created: 2025-12-22
-- Purpose: Capture advanced capabilities discovered during manual
--          validation of companies like Denron Hall, Raymond Plumbing
-- =====================================================================

-- OEM Partnerships (Carrier, Generac, Bradford White, etc.)
-- Signal: Certified installer = higher quality, brand trust
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_oem_partnerships BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_oem_partnerships IS
'OEM partnerships (Carrier, Generac, etc.) - certified installer status';

-- Emergency Service (24/7 availability)
-- Signal: Mature operations, established business
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_emergency_service BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_emergency_service IS
'24/7 emergency service - mature operations indicator';

-- Design-Build Capability (HIGH VALUE)
-- Signal: Integrated design + construction = larger projects
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_design_build BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_design_build IS
'Design-build capability - integrated design + construction (HIGH VALUE)';

-- In-House Engineering/CAD (HIGH VALUE)
-- Signal: Technical expertise, licensed engineers
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_engineering BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_engineering IS
'In-house engineering/CAD department - technical expertise (HIGH VALUE)';

-- Medical/Healthcare Specialization (HIGH VALUE)
-- Signal: Regulated work, medical gas piping, healthcare facilities
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_medical_specialization BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_medical_specialization IS
'Medical gas/healthcare specialization - regulated/complex work (HIGH VALUE)';

-- Building Automation/Controls (HIGH VALUE)
-- Signal: Smart buildings, BMS/BAS systems, advanced HVAC controls
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_building_automation BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_building_automation IS
'Building automation/controls - smart buildings (HIGH VALUE)';

-- Awards/Recognition
-- Signal: Social proof, industry recognition, credibility
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_awards BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_awards IS
'Awards/recognition - social proof and credibility';

-- =====================================================================
-- Index for filtering by high-value signals
-- =====================================================================
CREATE INDEX IF NOT EXISTS idx_companies_high_value_signals
ON dim_companies (has_design_build, has_engineering, has_medical_specialization, has_building_automation)
WHERE has_design_build = TRUE
   OR has_engineering = TRUE
   OR has_medical_specialization = TRUE
   OR has_building_automation = TRUE;

-- =====================================================================
-- Verification Query
-- =====================================================================
-- Run this to verify migration applied successfully:
--
-- SELECT
--     column_name,
--     data_type,
--     column_default,
--     is_nullable
-- FROM information_schema.columns
-- WHERE table_name = 'dim_companies'
--   AND column_name LIKE 'has_%'
-- ORDER BY column_name;
-- =====================================================================
