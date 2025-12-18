-- =============================================================================
-- FACT TABLE: GTME Touches (Outreach Telemetry)
-- =============================================================================
-- Tracks every outreach touch using GTME content (sequences, scripts, resources)
-- Links back to dim_gtme_* tables for attribution and ROI analysis
--
-- This closes the loop: We know which messaging converts and by how much.
-- =============================================================================

CREATE TABLE IF NOT EXISTS fact_gtme_touches (
    touch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- =========================================================================
    -- DIMENSION KEYS (Star Schema)
    -- =========================================================================
    company_id UUID REFERENCES dim_companies(company_id) ON DELETE SET NULL,
    contact_id UUID REFERENCES dim_contacts(contact_id) ON DELETE SET NULL,
    user_id UUID REFERENCES dim_users(user_id) ON DELETE SET NULL,  -- BDR who executed

    -- GTME Content Used (from coperniq-forge)
    sequence_key VARCHAR(100) REFERENCES dim_gtme_sequences(sequence_key) ON DELETE SET NULL,
    campaign_key VARCHAR(100) REFERENCES dim_gtme_campaigns(campaign_key) ON DELETE SET NULL,
    script_key VARCHAR(100) REFERENCES dim_gtme_scripts(script_key) ON DELETE SET NULL,
    resource_key VARCHAR(100) REFERENCES dim_gtme_resources(resource_key) ON DELETE SET NULL,
    prospect_key VARCHAR(100) REFERENCES dim_gtme_prospects(prospect_key) ON DELETE SET NULL,

    -- =========================================================================
    -- TOUCH DETAILS
    -- =========================================================================
    channel VARCHAR(50) NOT NULL CHECK (channel IN ('email', 'call', 'sms', 'linkedin', 'voicemail')),
    touch_type VARCHAR(50) NOT NULL CHECK (touch_type IN (
        'sequence_email',      -- Automated sequence email
        'cold_call',           -- Using phone script
        'warm_call',           -- Using phone script with warm opener
        'voicemail',           -- Left voicemail
        'linkedin_connect',    -- LinkedIn connection request
        'linkedin_message',    -- LinkedIn DM
        'sms',                 -- SMS touch
        'manual_email',        -- One-off email using GTME template
        'resource_share'       -- Sent value-add resource
    )),

    -- Sequence Position (if part of sequence)
    sequence_step_number INTEGER,  -- Which step in the sequence (1, 2, 3...)

    -- Script Variant Used (A/B testing)
    script_variant VARCHAR(10),  -- 'A', 'B', or NULL
    subject_variant VARCHAR(10), -- 'A', 'B', or NULL (for email subject A/B tests)

    -- =========================================================================
    -- OUTCOMES (Updated async as events occur)
    -- =========================================================================
    outcome VARCHAR(50) CHECK (outcome IN (
        -- Call outcomes
        'connected',           -- Got through to decision maker
        'gatekeeper',          -- Stopped at gatekeeper
        'voicemail',           -- Left voicemail
        'no_answer',           -- No pickup
        'bad_number',          -- Wrong/disconnected

        -- Email outcomes
        'sent',                -- Email sent
        'opened',              -- Email opened
        'clicked',             -- Link clicked
        'replied',             -- Got a reply
        'bounced',             -- Email bounced
        'unsubscribed',        -- Opted out

        -- Meeting outcomes
        'meeting_booked',      -- Success! Meeting scheduled
        'demo_scheduled',      -- Demo specifically scheduled
        'callback_scheduled',  -- Callback time set

        -- Negative outcomes
        'not_interested',      -- Hard no
        'competitor',          -- Using competitor
        'timing_bad',          -- Not now, maybe later
        'wrong_person',        -- Need different contact

        -- Neutral
        'pending'              -- Awaiting response
    )),

    -- =========================================================================
    -- ENGAGEMENT METRICS
    -- =========================================================================
    call_duration_seconds INTEGER,     -- For calls
    open_count INTEGER DEFAULT 0,      -- Times email was opened
    click_count INTEGER DEFAULT 0,     -- Times links were clicked

    -- =========================================================================
    -- ATTRIBUTION
    -- =========================================================================
    is_first_touch BOOLEAN DEFAULT FALSE,  -- First outreach to this contact
    touch_sequence_position INTEGER,        -- Nth touch to this contact overall

    -- Meeting Attribution (if outcome = meeting_booked)
    meeting_booked_at TIMESTAMPTZ,
    attributed_revenue_usd DECIMAL(12, 2),  -- If won, attributed value

    -- =========================================================================
    -- CRM LINKAGE
    -- =========================================================================
    close_activity_id VARCHAR(100),  -- Links to Close CRM activity
    close_lead_id VARCHAR(100),      -- Close Lead ID

    -- =========================================================================
    -- METADATA
    -- =========================================================================
    notes TEXT,                        -- BDR notes on the touch
    pain_indicators_mentioned JSONB,   -- Which pains came up in convo
    discovery_answers JSONB,           -- Answers to discovery questions

    -- =========================================================================
    -- TIMESTAMPS
    -- =========================================================================
    touched_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- When touch occurred
    outcome_updated_at TIMESTAMPTZ,                  -- When outcome was last updated
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- =============================================================================
-- INDEXES (Optimized for common queries)
-- =============================================================================

-- Primary lookups
CREATE INDEX IF NOT EXISTS idx_gtme_touches_company ON fact_gtme_touches(company_id);
CREATE INDEX IF NOT EXISTS idx_gtme_touches_contact ON fact_gtme_touches(contact_id);
CREATE INDEX IF NOT EXISTS idx_gtme_touches_user ON fact_gtme_touches(user_id);

-- GTME content analysis
CREATE INDEX IF NOT EXISTS idx_gtme_touches_sequence ON fact_gtme_touches(sequence_key);
CREATE INDEX IF NOT EXISTS idx_gtme_touches_campaign ON fact_gtme_touches(campaign_key);
CREATE INDEX IF NOT EXISTS idx_gtme_touches_script ON fact_gtme_touches(script_key);

-- Performance analysis
CREATE INDEX IF NOT EXISTS idx_gtme_touches_channel ON fact_gtme_touches(channel);
CREATE INDEX IF NOT EXISTS idx_gtme_touches_outcome ON fact_gtme_touches(outcome);
CREATE INDEX IF NOT EXISTS idx_gtme_touches_date ON fact_gtme_touches(touched_at DESC);

-- A/B test analysis
CREATE INDEX IF NOT EXISTS idx_gtme_touches_variant ON fact_gtme_touches(sequence_key, subject_variant)
    WHERE subject_variant IS NOT NULL;

-- Meeting attribution
CREATE INDEX IF NOT EXISTS idx_gtme_touches_meetings ON fact_gtme_touches(outcome)
    WHERE outcome IN ('meeting_booked', 'demo_scheduled');

-- First touch analysis
CREATE INDEX IF NOT EXISTS idx_gtme_touches_first ON fact_gtme_touches(is_first_touch)
    WHERE is_first_touch = TRUE;

-- =============================================================================
-- RLS POLICIES
-- =============================================================================
ALTER TABLE fact_gtme_touches ENABLE ROW LEVEL SECURITY;

CREATE POLICY "service_role_full_access_touches"
    ON fact_gtme_touches FOR ALL TO service_role USING (true);

CREATE POLICY "authenticated_read_touches"
    ON fact_gtme_touches FOR SELECT TO authenticated USING (true);

-- =============================================================================
-- UPDATED_AT TRIGGER
-- =============================================================================
CREATE TRIGGER trigger_gtme_touches_updated_at
    BEFORE UPDATE ON fact_gtme_touches
    FOR EACH ROW EXECUTE FUNCTION update_gtme_updated_at();

-- =============================================================================
-- COMMENTS
-- =============================================================================
COMMENT ON TABLE fact_gtme_touches IS 'Tracks every outreach touch using GTME content for attribution and ROI analysis';
COMMENT ON COLUMN fact_gtme_touches.sequence_key IS 'Links to dim_gtme_sequences - which email sequence was used';
COMMENT ON COLUMN fact_gtme_touches.script_key IS 'Links to dim_gtme_scripts - which phone script was used';
COMMENT ON COLUMN fact_gtme_touches.script_variant IS 'A/B test variant (A or B) for cold opener';
COMMENT ON COLUMN fact_gtme_touches.subject_variant IS 'A/B test variant (A or B) for email subject line';
COMMENT ON COLUMN fact_gtme_touches.is_first_touch IS 'True if this was the first outreach to this contact';
COMMENT ON COLUMN fact_gtme_touches.attributed_revenue_usd IS 'Revenue attributed to this touch if opportunity was won';

-- =============================================================================
-- HELPER VIEW: GTME Sequence Performance
-- =============================================================================
CREATE OR REPLACE VIEW v_gtme_sequence_performance AS
SELECT
    t.sequence_key,
    s.name AS sequence_name,
    s.campaign_type,
    COUNT(*) AS total_touches,
    COUNT(DISTINCT t.company_id) AS unique_companies,
    COUNT(*) FILTER (WHERE t.outcome = 'opened') AS opens,
    COUNT(*) FILTER (WHERE t.outcome = 'clicked') AS clicks,
    COUNT(*) FILTER (WHERE t.outcome = 'replied') AS replies,
    COUNT(*) FILTER (WHERE t.outcome IN ('meeting_booked', 'demo_scheduled')) AS meetings,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.outcome = 'opened') / NULLIF(COUNT(*), 0), 2) AS open_rate,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.outcome = 'replied') / NULLIF(COUNT(*), 0), 2) AS reply_rate,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.outcome IN ('meeting_booked', 'demo_scheduled')) / NULLIF(COUNT(*), 0), 2) AS meeting_rate,
    SUM(t.attributed_revenue_usd) AS total_attributed_revenue
FROM fact_gtme_touches t
LEFT JOIN dim_gtme_sequences s ON t.sequence_key = s.sequence_key
WHERE t.sequence_key IS NOT NULL
GROUP BY t.sequence_key, s.name, s.campaign_type;

COMMENT ON VIEW v_gtme_sequence_performance IS 'Aggregated performance metrics for each GTME sequence';

-- =============================================================================
-- HELPER VIEW: GTME Script Performance (A/B Analysis)
-- =============================================================================
CREATE OR REPLACE VIEW v_gtme_script_ab_analysis AS
SELECT
    t.script_key,
    sc.name AS script_name,
    t.script_variant,
    COUNT(*) AS total_calls,
    COUNT(*) FILTER (WHERE t.outcome = 'connected') AS connects,
    COUNT(*) FILTER (WHERE t.outcome IN ('meeting_booked', 'demo_scheduled', 'callback_scheduled')) AS conversions,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.outcome = 'connected') / NULLIF(COUNT(*), 0), 2) AS connect_rate,
    ROUND(100.0 * COUNT(*) FILTER (WHERE t.outcome IN ('meeting_booked', 'demo_scheduled', 'callback_scheduled')) / NULLIF(COUNT(*), 0), 2) AS conversion_rate,
    AVG(t.call_duration_seconds) FILTER (WHERE t.outcome = 'connected') AS avg_connected_duration
FROM fact_gtme_touches t
LEFT JOIN dim_gtme_scripts sc ON t.script_key = sc.script_key
WHERE t.script_key IS NOT NULL AND t.channel = 'call'
GROUP BY t.script_key, sc.name, t.script_variant;

COMMENT ON VIEW v_gtme_script_ab_analysis IS 'A/B test analysis for phone script cold openers';

-- =============================================================================
-- HELPER VIEW: Daily GTME Activity Dashboard
-- =============================================================================
CREATE OR REPLACE VIEW v_gtme_daily_activity AS
SELECT
    DATE(touched_at) AS activity_date,
    u.name AS bdr_name,
    t.channel,
    COUNT(*) AS total_touches,
    COUNT(*) FILTER (WHERE t.outcome = 'connected') AS connects,
    COUNT(*) FILTER (WHERE t.outcome = 'replied') AS replies,
    COUNT(*) FILTER (WHERE t.outcome IN ('meeting_booked', 'demo_scheduled')) AS meetings_booked,
    COUNT(DISTINCT t.company_id) AS unique_companies_touched
FROM fact_gtme_touches t
LEFT JOIN dim_users u ON t.user_id = u.user_id
GROUP BY DATE(touched_at), u.name, t.channel
ORDER BY activity_date DESC, meetings_booked DESC;

COMMENT ON VIEW v_gtme_daily_activity IS 'Daily BDR activity summary with GTME-attributed outcomes';
