-- =============================================================================
-- FACT_CLOSE_ACTIVITIES: Close CRM Activity Tracking (Dec 6, 2025)
-- =============================================================================
-- Comprehensive activity tracking from Close CRM for BDR Cockpit metrics.
-- Supports all activity types: Email, SMS, Call, Meeting, Note
-- Fields mapped from Close CRM API documentation.
-- =============================================================================

-- Drop if exists for clean recreation
DROP TABLE IF EXISTS fact_close_activities CASCADE;

CREATE TABLE fact_close_activities (
    -- Primary Key
    activity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Close CRM IDs (for sync/dedup)
    close_activity_id TEXT UNIQUE NOT NULL,  -- Close's activity ID (e.g., 'acti_xxx')
    close_lead_id TEXT,                       -- Close's lead ID (e.g., 'lead_xxx')
    close_contact_id TEXT,                    -- Close's contact ID (e.g., 'cont_xxx')
    close_user_id TEXT,                       -- Close's user ID (e.g., 'user_xxx')

    -- Star Schema Foreign Keys (nullable - may not always have match)
    company_id UUID REFERENCES dim_companies(company_id) ON DELETE SET NULL,
    contact_id UUID REFERENCES dim_contacts(contact_id) ON DELETE SET NULL,
    user_id UUID REFERENCES dim_users(user_id) ON DELETE SET NULL,

    -- Activity Classification
    activity_type TEXT NOT NULL CHECK (activity_type IN (
        'email', 'sms', 'call', 'meeting', 'note', 'task', 'lead_status_change'
    )),
    direction TEXT CHECK (direction IN ('inbound', 'outbound', 'internal')),

    -- Email-Specific Fields (from Close API)
    email_status TEXT,  -- 'draft', 'outbox', 'sent', 'inbox', 'scheduled'
    email_subject TEXT,
    email_body_text TEXT,
    email_body_html TEXT,
    email_sender TEXT,              -- Sender email address
    email_recipients JSONB,         -- Array of recipient emails
    email_cc JSONB,                 -- CC recipients
    email_bcc JSONB,                -- BCC recipients
    email_opens INTEGER DEFAULT 0,  -- Number of opens tracked
    email_clicks INTEGER DEFAULT 0, -- Number of link clicks

    -- SMS-Specific Fields (from Close API)
    sms_text TEXT,
    sms_status TEXT,  -- 'scheduled', 'sent', 'delivered', 'failed'
    sms_phone_from TEXT,
    sms_phone_to TEXT,
    sms_attachments JSONB,

    -- Call-Specific Fields (from Close API)
    call_duration_seconds INTEGER,
    call_disposition TEXT,  -- 'connected', 'voicemail', 'no_answer', 'busy', 'wrong_number'
    call_phone_from TEXT,
    call_phone_to TEXT,
    call_recording_url TEXT,
    call_voicemail_url TEXT,
    call_notes TEXT,

    -- Meeting-Specific Fields
    meeting_title TEXT,
    meeting_location TEXT,
    meeting_start_at TIMESTAMPTZ,
    meeting_end_at TIMESTAMPTZ,
    meeting_attendees JSONB,

    -- Sequence Context (from Close Sequences)
    sequence_id TEXT,           -- Close sequence ID if part of sequence
    sequence_name TEXT,         -- Sequence name for easy querying
    sequence_step INTEGER,      -- Which step in the sequence
    is_sequence_activity BOOLEAN DEFAULT FALSE,

    -- Timestamps from Close CRM
    date_created TIMESTAMPTZ NOT NULL,  -- When Close created the record
    date_sent TIMESTAMPTZ,              -- When actually sent (email/SMS)
    date_scheduled TIMESTAMPTZ,         -- Future scheduled time
    date_updated TIMESTAMPTZ,           -- Last update in Close

    -- Sync Metadata
    synced_at TIMESTAMPTZ DEFAULT NOW(),
    sync_source TEXT DEFAULT 'close_api',  -- 'close_api', 'webhook', 'manual'

    -- Quality Metrics (for BDR dashboards)
    is_reply BOOLEAN DEFAULT FALSE,        -- Is this a reply to our outreach?
    reply_to_activity_id UUID,             -- Which activity did this reply to?
    sentiment TEXT,                        -- 'positive', 'negative', 'neutral' (AI classified)

    -- Raw Close Data (for debugging/audit)
    raw_close_data JSONB
);

-- =============================================================================
-- INDEXES for BDR Cockpit Performance
-- =============================================================================

-- Primary lookup patterns
CREATE INDEX idx_fca_close_activity_id ON fact_close_activities(close_activity_id);
CREATE INDEX idx_fca_close_lead_id ON fact_close_activities(close_lead_id);
CREATE INDEX idx_fca_company_id ON fact_close_activities(company_id);
CREATE INDEX idx_fca_contact_id ON fact_close_activities(contact_id);
CREATE INDEX idx_fca_user_id ON fact_close_activities(user_id);

-- Activity type queries (for outreach metrics)
CREATE INDEX idx_fca_activity_type ON fact_close_activities(activity_type);
CREATE INDEX idx_fca_direction ON fact_close_activities(direction);

-- Time-based queries (critical for dashboard)
CREATE INDEX idx_fca_date_created ON fact_close_activities(date_created DESC);
CREATE INDEX idx_fca_date_sent ON fact_close_activities(date_sent DESC) WHERE date_sent IS NOT NULL;
CREATE INDEX idx_fca_synced_at ON fact_close_activities(synced_at DESC);

-- Outreach metrics composite indexes
CREATE INDEX idx_fca_type_date ON fact_close_activities(activity_type, date_created DESC);
CREATE INDEX idx_fca_type_direction_date ON fact_close_activities(activity_type, direction, date_created DESC);

-- Email-specific queries
CREATE INDEX idx_fca_email_status ON fact_close_activities(email_status) WHERE activity_type = 'email';
CREATE INDEX idx_fca_email_opens ON fact_close_activities(email_opens DESC) WHERE email_opens > 0;

-- SMS-specific queries
CREATE INDEX idx_fca_sms_status ON fact_close_activities(sms_status) WHERE activity_type = 'sms';

-- Call-specific queries
CREATE INDEX idx_fca_call_disposition ON fact_close_activities(call_disposition) WHERE activity_type = 'call';
CREATE INDEX idx_fca_call_duration ON fact_close_activities(call_duration_seconds DESC) WHERE call_duration_seconds > 0;

-- Sequence tracking
CREATE INDEX idx_fca_sequence ON fact_close_activities(sequence_id, sequence_step) WHERE is_sequence_activity = TRUE;

-- Reply tracking (for hot lead detection)
CREATE INDEX idx_fca_replies ON fact_close_activities(date_created DESC) WHERE is_reply = TRUE;

-- =============================================================================
-- ROW LEVEL SECURITY
-- =============================================================================

ALTER TABLE fact_close_activities ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Service role has full access to activities"
ON fact_close_activities
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

CREATE POLICY "Authenticated users can read activities"
ON fact_close_activities
FOR SELECT
TO authenticated
USING (true);

-- =============================================================================
-- HELPER VIEWS for BDR Cockpit
-- =============================================================================

-- Today's outreach metrics (used by /api/v1/metrics/outreach)
CREATE OR REPLACE VIEW v_outreach_today AS
SELECT
    activity_type,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE direction = 'outbound') as outbound_count,
    COUNT(*) FILTER (WHERE direction = 'inbound') as inbound_count,
    COUNT(*) FILTER (WHERE is_reply = TRUE) as reply_count
FROM fact_close_activities
WHERE date_created >= CURRENT_DATE
GROUP BY activity_type;

-- This week's outreach metrics
CREATE OR REPLACE VIEW v_outreach_week AS
SELECT
    activity_type,
    COUNT(*) as count,
    COUNT(*) FILTER (WHERE direction = 'outbound') as outbound_count,
    COUNT(*) FILTER (WHERE direction = 'inbound') as inbound_count,
    COUNT(*) FILTER (WHERE is_reply = TRUE) as reply_count
FROM fact_close_activities
WHERE date_created >= DATE_TRUNC('week', CURRENT_DATE)
GROUP BY activity_type;

-- =============================================================================
-- COMMENTS for Documentation
-- =============================================================================

COMMENT ON TABLE fact_close_activities IS 'Comprehensive Close CRM activity tracking for BDR Cockpit metrics and analytics';
COMMENT ON COLUMN fact_close_activities.close_activity_id IS 'Unique Close CRM activity ID (acti_xxx)';
COMMENT ON COLUMN fact_close_activities.activity_type IS 'Type: email, sms, call, meeting, note, task, lead_status_change';
COMMENT ON COLUMN fact_close_activities.direction IS 'Direction: inbound, outbound, internal';
COMMENT ON COLUMN fact_close_activities.email_status IS 'Email status from Close: draft, outbox, sent, inbox, scheduled';
COMMENT ON COLUMN fact_close_activities.is_reply IS 'Whether this is a reply to our outreach (hot lead indicator)';
COMMENT ON COLUMN fact_close_activities.sequence_id IS 'Close Sequence ID if activity is part of automated sequence';
COMMENT ON COLUMN fact_close_activities.raw_close_data IS 'Full Close API response for audit/debugging';
