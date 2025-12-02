-- Migration: Add AI enrichment columns to dim_companies
-- Created: 2025-12-02
-- Purpose: Support AI Command Center enrichment pipeline
-- Task: 1.2 from AI Command Center implementation plan

-- Add AI enrichment columns to dim_companies table
-- Using IF NOT EXISTS for safe re-run capability

-- Timestamp of when AI enrichment was performed
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS ai_enriched_at TIMESTAMPTZ;

COMMENT ON COLUMN dim_companies.ai_enriched_at IS
'Timestamp of when AI enrichment was last performed on this company record';

-- Personal hooks: Array of personalization angles for BDR outreach
-- Example: ["Founded by former HVAC technician", "Family-owned since 1985", "Active in community solar projects"]
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS ai_personal_hooks JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN dim_companies.ai_personal_hooks IS
'Array of personal hooks and humanizing details extracted by AI for BDR personalization. Examples: founder story, community involvement, unique differentiators';

-- Company story: AI-generated narrative about the company
-- Used for context in outreach and understanding company positioning
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS ai_company_story TEXT;

COMMENT ON COLUMN dim_companies.ai_company_story IS
'AI-generated narrative describing company history, positioning, and unique attributes based on website content and available data';

-- Pain points: Array of inferred challenges this company faces
-- Example: ["Struggling with technician recruitment", "Manual dispatch processes", "Limited service area coverage"]
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS ai_pain_points JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN dim_companies.ai_pain_points IS
'Array of inferred pain points and business challenges identified by AI analysis. Used to tailor solution positioning';

-- Buying signals: Array of indicators showing readiness to buy
-- Example: ["Recently expanded to new market", "Job postings for growth roles", "Website mentions modernization"]
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS ai_buying_signals JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN dim_companies.ai_buying_signals IS
'Array of buying signals and readiness indicators detected by AI. Examples: expansion plans, hiring activity, technology adoption mentions';

-- Confidence score: 0-1 float indicating AI confidence in enrichment quality
-- Used to prioritize human review and re-enrichment
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS ai_confidence FLOAT DEFAULT 0;

-- Add CHECK constraint for ai_confidence range (0-1)
ALTER TABLE dim_companies
ADD CONSTRAINT IF NOT EXISTS chk_ai_confidence_range
CHECK (ai_confidence >= 0 AND ai_confidence <= 1);

COMMENT ON COLUMN dim_companies.ai_confidence IS
'AI confidence score (0.0 to 1.0) indicating quality and reliability of enrichment data. Low scores flag records for human review';

-- Index for efficiently finding companies that need AI enrichment
-- Only indexes companies with domains (requirement for enrichment)
CREATE INDEX IF NOT EXISTS idx_companies_not_ai_enriched
ON dim_companies (domain)
WHERE ai_enriched_at IS NULL AND domain IS NOT NULL;

COMMENT ON INDEX idx_companies_not_ai_enriched IS
'Efficiently finds companies with domains that have not yet been AI enriched. Critical for batch enrichment pipeline performance';

-- Index for finding low-confidence enrichments that need review
CREATE INDEX IF NOT EXISTS idx_companies_low_ai_confidence
ON dim_companies (ai_confidence)
WHERE ai_enriched_at IS NOT NULL AND ai_confidence < 0.7;

COMMENT ON INDEX idx_companies_low_ai_confidence IS
'Finds AI-enriched companies with low confidence scores (<0.7) that may need human review or re-enrichment';

-- Verify columns were added successfully
DO $$
DECLARE
    missing_columns TEXT[];
    col TEXT;
BEGIN
    -- Check for missing columns
    SELECT ARRAY_AGG(column_name)
    INTO missing_columns
    FROM (
        SELECT unnest(ARRAY[
            'ai_enriched_at',
            'ai_personal_hooks',
            'ai_company_story',
            'ai_pain_points',
            'ai_buying_signals',
            'ai_confidence'
        ]) AS column_name
    ) expected
    WHERE column_name NOT IN (
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'dim_companies'
    );

    -- Raise notice if any columns are missing
    IF array_length(missing_columns, 1) > 0 THEN
        RAISE NOTICE 'Missing columns in dim_companies: %', array_to_string(missing_columns, ', ');
    ELSE
        RAISE NOTICE 'All AI enrichment columns successfully added to dim_companies';
    END IF;
END $$;
