-- LinkedIn Action Queue Table
-- Stores queued LinkedIn actions (connections, messages, reactions, comments)
-- with rate limiting and execution tracking

CREATE TABLE IF NOT EXISTS linkedin_action_queue (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    lead_id UUID REFERENCES dim_companies(id) ON DELETE CASCADE,

    -- Action details
    action_type TEXT NOT NULL CHECK (action_type IN ('connect', 'message', 'react', 'comment')),
    payload JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Execution status
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'completed', 'failed', 'cancelled')),
    scheduled_for TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    executed_at TIMESTAMP WITH TIME ZONE,

    -- Result
    result JSONB,

    -- Audit
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_linkedin_queue_status ON linkedin_action_queue(status);
CREATE INDEX IF NOT EXISTS idx_linkedin_queue_scheduled ON linkedin_action_queue(scheduled_for) WHERE status = 'pending';
CREATE INDEX IF NOT EXISTS idx_linkedin_queue_lead_id ON linkedin_action_queue(lead_id);
CREATE INDEX IF NOT EXISTS idx_linkedin_queue_action_type ON linkedin_action_queue(action_type);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_linkedin_action_queue_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_linkedin_action_queue_updated_at
    BEFORE UPDATE ON linkedin_action_queue
    FOR EACH ROW
    EXECUTE FUNCTION update_linkedin_action_queue_updated_at();

-- Add RLS policies (if RLS is enabled)
ALTER TABLE linkedin_action_queue ENABLE ROW LEVEL SECURITY;

-- Allow service role full access
CREATE POLICY linkedin_action_queue_service_role ON linkedin_action_queue
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Comments for documentation
COMMENT ON TABLE linkedin_action_queue IS 'Queue for LinkedIn social selling actions with rate limiting';
COMMENT ON COLUMN linkedin_action_queue.action_type IS 'Type of LinkedIn action: connect, message, react, comment';
COMMENT ON COLUMN linkedin_action_queue.payload IS 'Action-specific data (profile_url, note, message, etc)';
COMMENT ON COLUMN linkedin_action_queue.status IS 'Execution status: pending, completed, failed, cancelled';
COMMENT ON COLUMN linkedin_action_queue.scheduled_for IS 'When this action should be executed';
COMMENT ON COLUMN linkedin_action_queue.executed_at IS 'When this action was actually executed';
COMMENT ON COLUMN linkedin_action_queue.result IS 'Result object from LinkedInAgent';
