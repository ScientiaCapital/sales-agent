-- Migration: Add ICP enrichment columns to dim_companies
-- Created: 2025-12-02
-- Purpose: Store industries served, company age, employee count, certifications, emergency services

-- Industries Served (from website "Industries Served" pages)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS industries_served JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN dim_companies.industries_served IS
'Array of industries served (e.g., ["Oil/Gas", "Mining", "Renewable Energy", "Agriculture"])';

-- Years in Business (extracted from "Since YYYY" or "Established YYYY")
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS years_in_business INT;

COMMENT ON COLUMN dim_companies.years_in_business IS
'Years in business calculated from founding year (e.g., 75 for "Since 1950")';

-- Founding Year (raw value)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS founded_year INT;

COMMENT ON COLUMN dim_companies.founded_year IS
'Year company was founded (e.g., 1950)';

-- Employee Count (as text to handle ranges like "200+", "50-100")
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS employee_count TEXT;

COMMENT ON COLUMN dim_companies.employee_count IS
'Employee count as text (e.g., "200+", "50-100", "15")';

-- Number of Locations
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS location_count INT;

COMMENT ON COLUMN dim_companies.location_count IS
'Number of office/branch locations';

-- Certifications (EASA, NATE, Siemens warranty center, etc.)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS certifications JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN dim_companies.certifications IS
'Array of certifications and partnerships (e.g., ["EASA accredited", "Siemens warranty center"])';

-- Emergency Services flag
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS has_emergency_services BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN dim_companies.has_emergency_services IS
'True if company offers 24/7 or emergency services';

-- Emergency Phone (separate from main phone)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS emergency_phone TEXT;

COMMENT ON COLUMN dim_companies.emergency_phone IS
'Emergency/after-hours phone number if different from main';

-- Equipment Keywords (transformers, motors, generators, etc.)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS equipment_keywords JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN dim_companies.equipment_keywords IS
'Equipment types mentioned on website (e.g., ["transformers", "motors", "generators"])';

-- Events/Trade Shows (for finding them at conferences)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS events_attended JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN dim_companies.events_attended IS
'Trade shows and events mentioned (e.g., ["RE+ 2025", "AHR Expo"])';

-- Index for finding companies by industry
CREATE INDEX IF NOT EXISTS idx_companies_industries
ON dim_companies USING gin (industries_served);

-- Index for finding companies with emergency services
CREATE INDEX IF NOT EXISTS idx_companies_emergency
ON dim_companies (has_emergency_services)
WHERE has_emergency_services = TRUE;

-- Index for finding established companies
CREATE INDEX IF NOT EXISTS idx_companies_years_business
ON dim_companies (years_in_business DESC NULLS LAST)
WHERE years_in_business IS NOT NULL;

-- Verification
DO $$
DECLARE
    missing_columns TEXT[];
BEGIN
    SELECT ARRAY_AGG(column_name)
    INTO missing_columns
    FROM (
        SELECT unnest(ARRAY[
            'industries_served',
            'years_in_business',
            'founded_year',
            'employee_count',
            'location_count',
            'certifications',
            'has_emergency_services',
            'emergency_phone',
            'equipment_keywords',
            'events_attended'
        ]) AS column_name
    ) expected
    WHERE column_name NOT IN (
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'dim_companies'
    );

    IF array_length(missing_columns, 1) > 0 THEN
        RAISE NOTICE 'Missing columns: %', array_to_string(missing_columns, ', ');
    ELSE
        RAISE NOTICE 'All ICP enrichment columns added successfully';
    END IF;
END $$;
