-- LinkedIn OAuth Schema for Supabase
-- Run this in Supabase SQL Editor (https://supabase.com/dashboard → SQL Editor)

-- OAuth credentials (encrypted at rest via Supabase)
CREATE TABLE IF NOT EXISTS linkedin_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL UNIQUE,
    access_token TEXT NOT NULL,
    id_token TEXT,
    expires_at TIMESTAMPTZ NOT NULL,
    scope TEXT,
    linkedin_sub TEXT,
    linkedin_email TEXT,
    linkedin_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- OAuth flow state (CSRF protection + session tracking)
CREATE TABLE IF NOT EXISTS oauth_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    state TEXT NOT NULL UNIQUE,
    redirect_after TEXT,
    user_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT NOW() + INTERVAL '30 minutes'
);

-- Index for cleanup of expired state entries
CREATE INDEX IF NOT EXISTS idx_oauth_state_expires ON oauth_state(expires_at);

-- Enable Row Level Security
ALTER TABLE linkedin_credentials ENABLE ROW LEVEL SECURITY;
ALTER TABLE oauth_state ENABLE ROW LEVEL SECURITY;

-- RLS Policies for service role access
-- Note: Service role bypasses RLS by default in Supabase, but explicit policies are good practice

-- linkedin_credentials policies
CREATE POLICY "Service role can manage linkedin_credentials"
    ON linkedin_credentials
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- oauth_state policies
CREATE POLICY "Service role can manage oauth_state"
    ON oauth_state
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Cleanup function for expired oauth_state entries (optional - run via cron)
CREATE OR REPLACE FUNCTION cleanup_expired_oauth_state()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM oauth_state WHERE expires_at < NOW();
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
