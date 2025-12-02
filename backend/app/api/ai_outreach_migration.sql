-- AI Outreach Drafts Table Migration
-- Run this in Supabase SQL Editor to create the table

CREATE TABLE IF NOT EXISTS ai_outreach_drafts (
    -- Primary key
    draft_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Company reference
    company_id UUID NOT NULL REFERENCES dim_companies(company_id) ON DELETE CASCADE,
    company_name TEXT NOT NULL,

    -- Draft classification
    draft_type TEXT NOT NULL CHECK (draft_type IN ('email', 'sms', 'voice')),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'sent', 'discarded')),

    -- Content
    subject TEXT,  -- Email only (null for SMS/voice)
    body TEXT NOT NULL,

    -- Contact context
    contact_name TEXT,
    contact_title TEXT,
    personal_hooks JSONB DEFAULT '[]',  -- Array of {category, detail, opener}

    -- Metadata
    confidence REAL DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    generated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,

    -- Close CRM integration
    close_activity_id TEXT  -- Activity ID from Close CRM after sending
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_draft_status ON ai_outreach_drafts(status, draft_type);
CREATE INDEX IF NOT EXISTS idx_draft_company ON ai_outreach_drafts(company_id);
CREATE INDEX IF NOT EXISTS idx_draft_generated ON ai_outreach_drafts(generated_at DESC);
CREATE INDEX IF NOT EXISTS idx_draft_pending ON ai_outreach_drafts(status) WHERE status = 'pending';

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_ai_outreach_drafts_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER ai_outreach_drafts_updated_at
    BEFORE UPDATE ON ai_outreach_drafts
    FOR EACH ROW
    EXECUTE FUNCTION update_ai_outreach_drafts_updated_at();

-- Row Level Security (RLS) - Adjust based on your auth setup
ALTER TABLE ai_outreach_drafts ENABLE ROW LEVEL SECURITY;

-- Policy: Allow service role full access
CREATE POLICY "Service role has full access"
    ON ai_outreach_drafts
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Policy: Authenticated users can read their own drafts (if using Supabase Auth)
-- Uncomment if you want user-level access:
-- CREATE POLICY "Users can read drafts"
--     ON ai_outreach_drafts
--     FOR SELECT
--     TO authenticated
--     USING (true);

-- Comments for documentation
COMMENT ON TABLE ai_outreach_drafts IS 'AI-generated outreach drafts (email/SMS/voice) from SalesIntelAgent';
COMMENT ON COLUMN ai_outreach_drafts.draft_type IS 'Type of outreach: email, sms, or voice';
COMMENT ON COLUMN ai_outreach_drafts.status IS 'Workflow status: pending -> approved -> sent (or discarded)';
COMMENT ON COLUMN ai_outreach_drafts.personal_hooks IS 'JSONB array of personal details for rapport building';
COMMENT ON COLUMN ai_outreach_drafts.confidence IS 'AI confidence score (0-1) in draft quality';

-- Sample query to verify
-- SELECT
--     draft_id,
--     company_name,
--     draft_type,
--     status,
--     subject,
--     LEFT(body, 50) || '...' as body_preview,
--     confidence,
--     generated_at
-- FROM ai_outreach_drafts
-- WHERE status = 'pending'
-- ORDER BY generated_at DESC
-- LIMIT 10;
