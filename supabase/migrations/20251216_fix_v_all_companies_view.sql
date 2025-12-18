-- Migration: Fix v_all_companies view to include original_source column
-- Date: 2025-12-16
-- Problem: View was created BEFORE original_source column was added to tables
-- Solution: Drop and recreate the view to pick up the new column

-- Must drop first - CREATE OR REPLACE fails when column structure changes
DROP VIEW IF EXISTS v_all_companies;

-- Recreate the unified view (will now include original_source)
CREATE VIEW v_all_companies AS
SELECT *, 'close_archive'::text as table_source FROM dim_companies_close
UNION ALL
SELECT *, 'pipeline'::text as table_source FROM dim_companies;

-- Verify the column exists:
-- SELECT column_name FROM information_schema.columns
-- WHERE table_name = 'v_all_companies' AND column_name = 'original_source';
