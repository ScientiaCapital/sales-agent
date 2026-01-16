-- Scraper Imports Table - Source of Truth for dealer-scraper-mvp data
-- Created: 2025-11-28
-- Purpose: Capture all OEM/license contractor lists from dealer-scraper with full audit trail

-- Drop existing objects if re-running migration
DROP TABLE IF EXISTS scraper_imports CASCADE;
DROP TABLE IF EXISTS scraper_batches CASCADE;

-- Batch tracking table (groups related imports)
CREATE TABLE scraper_batches (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Batch Identification
    batch_name VARCHAR(255) NOT NULL,       -- e.g., "cummins_browserbase_20251128"
    source_type VARCHAR(50) NOT NULL,       -- "oem_dealer", "license_contractor", "mep_list"

    -- Source File Info
    source_file VARCHAR(500),               -- Original CSV filename
    source_project VARCHAR(100) DEFAULT 'dealer-scraper-mvp',

    -- Batch Stats
    total_records INTEGER DEFAULT 0,
    imported_records INTEGER DEFAULT 0,
    duplicate_records INTEGER DEFAULT 0,
    error_records INTEGER DEFAULT 0,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) DEFAULT 'pending',   -- pending, processing, completed, failed

    -- Checksum for dedup
    file_hash VARCHAR(64)                   -- MD5 hash of source file to prevent re-imports
);

-- Individual lead records from scraper
CREATE TABLE scraper_imports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Link to batch
    batch_id UUID REFERENCES scraper_batches(id) ON DELETE CASCADE,

    -- Company Data (from dealer-scraper CSV)
    company_name VARCHAR(255) NOT NULL,
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),
    phone VARCHAR(50),
    email VARCHAR(255),
    website VARCHAR(500),
    domain VARCHAR(255),

    -- Source Classification
    source VARCHAR(100),                    -- "oem_dealer", "license_contractor", "mep_list"
    tier VARCHAR(20),                       -- "GOLD", "SILVER", "BRONZE"

    -- OEM/License Specific
    oem_brands JSONB,                       -- ["Cummins", "Carrier", "Trane"]
    license_types JSONB,                    -- ["HVAC", "Electrical", "Plumbing"]
    license_number VARCHAR(100),
    license_state VARCHAR(10),

    -- Processing Status
    status VARCHAR(50) DEFAULT 'imported',  -- imported, qualified, enriched, exported, skipped
    processed_at TIMESTAMPTZ,

    -- Deduplication
    is_duplicate BOOLEAN DEFAULT FALSE,
    duplicate_of UUID,                      -- Reference to existing lead if duplicate

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_number INTEGER,                     -- Original row in CSV for audit
    raw_data JSONB                          -- Full original row for reference
);

-- Indexes for common queries
-- Query: "What batches came in today?"
CREATE INDEX idx_scraper_batches_created ON scraper_batches(created_at DESC);

-- Query: "Find all imports from a batch"
CREATE INDEX idx_scraper_imports_batch ON scraper_imports(batch_id);

-- Query: "Find company by name"
CREATE INDEX idx_scraper_imports_company ON scraper_imports(company_name);

-- Query: "Find all GOLD tier leads"
CREATE INDEX idx_scraper_imports_tier ON scraper_imports(tier);

-- Query: "Find all OEM dealers"
CREATE INDEX idx_scraper_imports_source ON scraper_imports(source);

-- Query: "Find unprocessed imports"
CREATE INDEX idx_scraper_imports_status ON scraper_imports(status);

-- Query: "Find by domain for dedup"
CREATE INDEX idx_scraper_imports_domain ON scraper_imports(domain);

-- Unique constraint to prevent exact duplicates
CREATE UNIQUE INDEX idx_scraper_imports_unique
ON scraper_imports(company_name, domain, batch_id)
WHERE domain IS NOT NULL;

-- Table comments
COMMENT ON TABLE scraper_batches IS 'Batch tracking for dealer-scraper imports - tracks source files and import status';
COMMENT ON TABLE scraper_imports IS 'Individual lead records imported from dealer-scraper-mvp with full audit trail';
COMMENT ON COLUMN scraper_imports.raw_data IS 'Full original CSV row as JSONB for reference and debugging';
COMMENT ON COLUMN scraper_batches.file_hash IS 'MD5 hash of source file to prevent duplicate imports';

-- Enable Row Level Security (optional, can be added later)
-- ALTER TABLE scraper_batches ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE scraper_imports ENABLE ROW LEVEL SECURITY;

-- Verify creation
SELECT 'scraper_imports and scraper_batches tables created successfully' AS status;
