-- =============================================================================
-- Migration: 20251222_add_trigger_events_rls.sql
-- Purpose: Enable Row Level Security on trigger_events table
-- Policy: Service role only (backend server access)
-- Date: 2025-12-22
-- =============================================================================

-- Enable RLS
ALTER TABLE trigger_events ENABLE ROW LEVEL SECURITY;

-- Service role full access policy
DROP POLICY IF EXISTS "service_role_all_trigger_events" ON trigger_events;
CREATE POLICY "service_role_all_trigger_events"
    ON trigger_events
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- Comments
COMMENT ON TABLE trigger_events IS 'Buying signals (funding, hiring, news) - RLS enabled for service_role';
