-- Migration: Add Google reviews columns to dim_companies
-- Date: 2025-12-03
-- Purpose: Track Google review ratings and counts from website scraping

-- Add Google rating (1.0 - 5.0 scale)
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS google_rating DECIMAL(2,1);

-- Add Google review count
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS google_review_count INTEGER;

-- Comments for documentation
COMMENT ON COLUMN dim_companies.google_rating IS 'Google star rating (1.0-5.0) scraped from company website';
COMMENT ON COLUMN dim_companies.google_review_count IS 'Number of Google reviews scraped from company website';

-- Note: events_attended column already exists in dim_companies
