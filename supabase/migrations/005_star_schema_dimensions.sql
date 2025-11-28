-- =============================================================================
-- STAR SCHEMA: DIMENSION TABLES (Nov 28, 2025)
-- =============================================================================
-- Part of the Star Schema data warehouse redesign for lead analytics.
-- See: .claude/plans/imperative-humming-cocoa.md for full architecture.
-- =============================================================================

-- dim_companies: THE MASTER LEAD LIST (Single Source of Truth)
-- All leads from dealer-scraper, Close CRM, and manual imports go here.
CREATE TABLE IF NOT EXISTS dim_companies (
    company_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Core Identity
    company_name VARCHAR(255) NOT NULL,
    normalized_name VARCHAR(255),  -- Lowercase, no suffixes for dedup
    domain VARCHAR(255),

    -- Contact Info
    phone VARCHAR(50),
    website VARCHAR(500),

    -- Location
    street VARCHAR(255),
    city VARCHAR(100),
    state VARCHAR(50),
    zip VARCHAR(20),

    -- ICP Scoring
    icp_score INTEGER CHECK (icp_score >= 0 AND icp_score <= 100),
    icp_tier VARCHAR(20) CHECK (icp_tier IN ('PLATINUM', 'GOLD', 'SILVER', 'BRONZE')),

    -- OEM/Trade Data
    oem_brands JSONB DEFAULT '[]',
    license_types JSONB DEFAULT '[]',
    oem_count INTEGER DEFAULT 0,
    trade_count INTEGER DEFAULT 0,

    -- Pipeline State
    current_stage VARCHAR(50) DEFAULT 'imported',
    close_lead_id VARCHAR(100),

    -- Source Tracking
    source_type VARCHAR(50),  -- 'dealer_scraper', 'close_crm', 'manual'
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),

    -- Enrichment Tracking
    last_enriched_at TIMESTAMPTZ,

    -- Engagement Tracking (denormalized for fast BDR queries)
    last_activity_at TIMESTAMPTZ,
    total_activities INTEGER DEFAULT 0,
    email_opens INTEGER DEFAULT 0,

    -- Flags
    flagged_for_reenrich BOOLEAN DEFAULT FALSE,
    needs_attention BOOLEAN DEFAULT FALSE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for dim_companies
CREATE INDEX IF NOT EXISTS idx_dim_companies_name ON dim_companies(company_name);
CREATE INDEX IF NOT EXISTS idx_dim_companies_normalized ON dim_companies(normalized_name);
CREATE INDEX IF NOT EXISTS idx_dim_companies_domain ON dim_companies(domain);
CREATE INDEX IF NOT EXISTS idx_dim_companies_tier ON dim_companies(icp_tier);
CREATE INDEX IF NOT EXISTS idx_dim_companies_score ON dim_companies(icp_score DESC);
CREATE INDEX IF NOT EXISTS idx_dim_companies_stage ON dim_companies(current_stage);
CREATE INDEX IF NOT EXISTS idx_dim_companies_close ON dim_companies(close_lead_id);
CREATE INDEX IF NOT EXISTS idx_dim_companies_reenrich ON dim_companies(flagged_for_reenrich) WHERE flagged_for_reenrich = TRUE;
CREATE INDEX IF NOT EXISTS idx_dim_companies_attention ON dim_companies(needs_attention) WHERE needs_attention = TRUE;

-- dim_contacts: People at companies
CREATE TABLE IF NOT EXISTS dim_contacts (
    contact_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES dim_companies(company_id) ON DELETE CASCADE,

    -- Identity
    full_name VARCHAR(255),
    first_name VARCHAR(100),
    last_name VARCHAR(100),

    -- Contact Info
    email VARCHAR(255),
    phone VARCHAR(50),

    -- Role
    title VARCHAR(255),
    is_atl BOOLEAN DEFAULT FALSE,  -- Above The Line (decision maker)
    department VARCHAR(100),
    seniority VARCHAR(50),

    -- Social
    linkedin_url VARCHAR(500),
    twitter_handle VARCHAR(100),

    -- Quality
    confidence INTEGER DEFAULT 50,
    source VARCHAR(50),  -- 'hunter', 'apollo', 'browserbase', 'manual', 're_enrich'
    validated BOOLEAN DEFAULT FALSE,

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dim_contacts_company ON dim_contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_dim_contacts_email ON dim_contacts(email);
CREATE INDEX IF NOT EXISTS idx_dim_contacts_atl ON dim_contacts(is_atl) WHERE is_atl = TRUE;

-- dim_users: Team members (BDRs, AEs)
CREATE TABLE IF NOT EXISTS dim_users (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    close_user_id VARCHAR(100) UNIQUE,

    name VARCHAR(255) NOT NULL,
    email VARCHAR(255),
    role VARCHAR(50),  -- 'BDR', 'AE', 'Manager'

    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pre-populate with known team (Coperniq sales team)
INSERT INTO dim_users (close_user_id, name, email, role) VALUES
    ('user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1', 'Tim Kipper', 'tim@coperniq.io', 'BDR'),
    ('user_lFVhSWUaqu2vff3eQEk5KG6jfkbihC1s1g6VUjn5w44', 'Abdullah Al Zandani', 'abdullah@coperniq.io', 'AE'),
    ('user_mARlgTfFvEkDMgcFflJErBYXNr3AxGxsTNWAVxc75gH', 'Max Kazakov', 'max@coperniq.io', 'AE'),
    ('user_MSAjv3Vr0ZjcXAoGt38JPZFjXnIJUNtw0KYaMqMovET', 'Levi Natividad', 'levi@coperniq.io', 'AE'),
    ('user_8ZClygANhdAJI7Tzn89mDBG3mw6SYFeyAmTbkAKe6sR', 'Jerry McElroy', 'jerry@coperniq.io', 'AE')
ON CONFLICT (close_user_id) DO NOTHING;

-- dim_sources: Data origin tracking
CREATE TABLE IF NOT EXISTS dim_sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name VARCHAR(100) NOT NULL UNIQUE,
    source_type VARCHAR(50),  -- 'scraper', 'crm', 'api', 'manual'
    project VARCHAR(100),  -- 'dealer-scraper-mvp', 'sales-agent', 'close'
    created_at TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO dim_sources (source_name, source_type, project) VALUES
    ('dealer-scraper', 'scraper', 'dealer-scraper-mvp'),
    ('close-crm', 'crm', 'close'),
    ('hunter-io', 'api', 'sales-agent'),
    ('apollo', 'api', 'sales-agent'),
    ('browserbase', 'api', 'sales-agent'),
    ('manual-import', 'manual', 'sales-agent'),
    ('re-enrich', 'api', 'dealer-scraper-mvp')
ON CONFLICT (source_name) DO NOTHING;

-- Enable Row Level Security (optional, can be enabled later)
-- ALTER TABLE dim_companies ENABLE ROW LEVEL SECURITY;
-- ALTER TABLE dim_contacts ENABLE ROW LEVEL SECURITY;
