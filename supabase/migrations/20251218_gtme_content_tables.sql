-- GTME Content Tables
-- Stores campaign sequences, scripts, and resources from coperniq-forge
-- Synced from markdown files via sync_sequences.py

-- ============================================================================
-- DIMENSION: GTME Sequences (Email, SMS, LinkedIn touches)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dim_gtme_sequences (
    sequence_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity (matches markdown filename)
    sequence_key VARCHAR(100) NOT NULL UNIQUE,  -- e.g., 'solar-plus-plus-cold'
    name VARCHAR(255) NOT NULL,                  -- e.g., 'Solar++ Cold Outreach'

    -- Classification
    campaign_type VARCHAR(50) NOT NULL CHECK (campaign_type IN ('solar_plus_plus', 'frankenstack', 'general')),
    sequence_type VARCHAR(50) NOT NULL CHECK (sequence_type IN ('cold', 'warm', 'followup', 'breakup')),

    -- Content
    description TEXT,
    steps JSONB NOT NULL DEFAULT '[]',  -- [{step_number, day, channel, subject, body, delay_days}]

    -- Metadata
    total_steps INTEGER GENERATED ALWAYS AS (jsonb_array_length(steps)) STORED,
    channels_used TEXT[],  -- ['email', 'sms', 'linkedin']

    -- Status
    is_active BOOLEAN DEFAULT TRUE,
    version INTEGER DEFAULT 1,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_from_file VARCHAR(255)  -- Source markdown file path
);

-- ============================================================================
-- DIMENSION: GTME Campaigns (Strategy/Metadata)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dim_gtme_campaigns (
    campaign_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    campaign_key VARCHAR(100) NOT NULL UNIQUE,  -- e.g., 'solar-plus-plus'
    name VARCHAR(255) NOT NULL,

    -- Strategy
    target_segment TEXT,           -- Who we're targeting
    target_signals JSONB,          -- [{signal, description}]
    messaging_framework JSONB,     -- {primary_pain, core_narrative, value_prop}

    -- Battle Cards
    differentiators JSONB,         -- [{pain, solution}]
    objection_handling JSONB,      -- [{objection, response}]

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_from_file VARCHAR(255)
);

-- ============================================================================
-- DIMENSION: GTME Phone Scripts
-- ============================================================================
CREATE TABLE IF NOT EXISTS dim_gtme_scripts (
    script_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    script_key VARCHAR(100) NOT NULL UNIQUE,  -- e.g., 'solar-plus-plus-phone'
    name VARCHAR(255) NOT NULL,
    campaign_key VARCHAR(100) REFERENCES dim_gtme_campaigns(campaign_key) ON DELETE SET NULL,

    -- Script Content
    cold_openers JSONB,      -- [{option, script}]
    warm_opener TEXT,
    response_paths JSONB,    -- [{path_name, trigger, script}]
    voicemail TEXT,

    -- Metadata
    style VARCHAR(100),      -- e.g., 'Challenger + NSTTD'

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_from_file VARCHAR(255)
);

-- ============================================================================
-- DIMENSION: GTME Resources (Value-add content)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dim_gtme_resources (
    resource_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    resource_key VARCHAR(100) NOT NULL UNIQUE,  -- e.g., 'field-to-office-gap'
    title VARCHAR(255) NOT NULL,

    -- Content
    content_markdown TEXT,
    content_html TEXT,        -- Rendered HTML (optional)
    summary TEXT,             -- Short description for agents

    -- Usage
    use_case VARCHAR(100),    -- e.g., 'touch_3_value_add'
    recommended_for TEXT[],   -- ['solar_plus_plus', 'frankenstack']

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_from_file VARCHAR(255)
);

-- ============================================================================
-- DIMENSION: GTME Prospect Research (Flagship accounts)
-- ============================================================================
CREATE TABLE IF NOT EXISTS dim_gtme_prospects (
    prospect_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity (links to dim_companies if exists)
    prospect_key VARCHAR(100) NOT NULL UNIQUE,  -- e.g., 'norrell-construction'
    company_id UUID REFERENCES dim_companies(company_id) ON DELETE SET NULL,

    -- Company Intel
    company_name VARCHAR(255) NOT NULL,
    intel JSONB,              -- {size, revenue, services, certifications, locations}

    -- Research
    discovery_questions JSONB, -- [{question, why_it_matters}]
    pain_indicators JSONB,     -- [{indicator, evidence}]

    -- Outreach
    target_contacts JSONB,     -- [{name, role, channel, priority}]
    custom_sequence_key VARCHAR(100) REFERENCES dim_gtme_sequences(sequence_key),

    -- Status
    status VARCHAR(50) DEFAULT 'researched' CHECK (status IN ('researched', 'contacted', 'engaged', 'meeting', 'won', 'lost')),

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    synced_from_file VARCHAR(255)
);

-- ============================================================================
-- INDEXES for performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_gtme_sequences_campaign ON dim_gtme_sequences(campaign_type);
CREATE INDEX IF NOT EXISTS idx_gtme_sequences_active ON dim_gtme_sequences(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_gtme_campaigns_active ON dim_gtme_campaigns(is_active) WHERE is_active = TRUE;
CREATE INDEX IF NOT EXISTS idx_gtme_scripts_campaign ON dim_gtme_scripts(campaign_key);
CREATE INDEX IF NOT EXISTS idx_gtme_prospects_status ON dim_gtme_prospects(status);
CREATE INDEX IF NOT EXISTS idx_gtme_prospects_company ON dim_gtme_prospects(company_id) WHERE company_id IS NOT NULL;

-- ============================================================================
-- RLS Policies (service_role full access)
-- ============================================================================
ALTER TABLE dim_gtme_sequences ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_gtme_campaigns ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_gtme_scripts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_gtme_resources ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_gtme_prospects ENABLE ROW LEVEL SECURITY;

-- Service role gets full access (for sync scripts and agents)
CREATE POLICY "service_role_full_access_sequences" ON dim_gtme_sequences FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_full_access_campaigns" ON dim_gtme_campaigns FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_full_access_scripts" ON dim_gtme_scripts FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_full_access_resources" ON dim_gtme_resources FOR ALL TO service_role USING (true);
CREATE POLICY "service_role_full_access_prospects" ON dim_gtme_prospects FOR ALL TO service_role USING (true);

-- Authenticated users can read
CREATE POLICY "authenticated_read_sequences" ON dim_gtme_sequences FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_read_campaigns" ON dim_gtme_campaigns FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_read_scripts" ON dim_gtme_scripts FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_read_resources" ON dim_gtme_resources FOR SELECT TO authenticated USING (true);
CREATE POLICY "authenticated_read_prospects" ON dim_gtme_prospects FOR SELECT TO authenticated USING (true);

-- ============================================================================
-- Updated_at trigger
-- ============================================================================
CREATE OR REPLACE FUNCTION update_gtme_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_gtme_sequences_updated_at
    BEFORE UPDATE ON dim_gtme_sequences
    FOR EACH ROW EXECUTE FUNCTION update_gtme_updated_at();

CREATE TRIGGER trigger_gtme_campaigns_updated_at
    BEFORE UPDATE ON dim_gtme_campaigns
    FOR EACH ROW EXECUTE FUNCTION update_gtme_updated_at();

CREATE TRIGGER trigger_gtme_scripts_updated_at
    BEFORE UPDATE ON dim_gtme_scripts
    FOR EACH ROW EXECUTE FUNCTION update_gtme_updated_at();

CREATE TRIGGER trigger_gtme_resources_updated_at
    BEFORE UPDATE ON dim_gtme_resources
    FOR EACH ROW EXECUTE FUNCTION update_gtme_updated_at();

CREATE TRIGGER trigger_gtme_prospects_updated_at
    BEFORE UPDATE ON dim_gtme_prospects
    FOR EACH ROW EXECUTE FUNCTION update_gtme_updated_at();

-- ============================================================================
-- COMMENTS for documentation
-- ============================================================================
COMMENT ON TABLE dim_gtme_sequences IS 'GTME email/SMS/LinkedIn sequences synced from coperniq-forge markdown files';
COMMENT ON TABLE dim_gtme_campaigns IS 'GTME campaign strategies with targeting, messaging, and objection handling';
COMMENT ON TABLE dim_gtme_scripts IS 'Phone scripts for cold and warm calling (Challenger + NSTTD style)';
COMMENT ON TABLE dim_gtme_resources IS 'Value-add content pieces for sequence touches (PDFs, articles, etc.)';
COMMENT ON TABLE dim_gtme_prospects IS 'Flagship prospect research with custom sequences and intel';
