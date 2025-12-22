-- Trigger Events Table
-- Stores detected buying signals (funding, hiring, news, tech changes) for ICP companies

CREATE TABLE IF NOT EXISTS trigger_events (
    event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES dim_companies(company_id) ON DELETE CASCADE,

    -- Event classification
    event_type VARCHAR(50) NOT NULL CHECK (event_type IN (
        'funding',
        'hiring',
        'news',
        'executive_change',
        'tech_stack_change',
        'partnership',
        'acquisition',
        'product_launch',
        'expansion',
        'award'
    )),

    -- Event details
    event_date DATE,
    signal_strength INTEGER NOT NULL CHECK (signal_strength BETWEEN 1 AND 10),
    title TEXT NOT NULL,
    description TEXT,
    details JSONB DEFAULT '{}',

    -- Source tracking
    source_url TEXT,
    source_type VARCHAR(50), -- 'web_scrape', 'api', 'manual'
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Action tracking
    actioned BOOLEAN DEFAULT FALSE,
    actioned_at TIMESTAMPTZ,
    actioned_by VARCHAR(255),
    action_notes TEXT,

    -- Deduplication
    content_hash VARCHAR(64), -- SHA256 hash for duplicate detection

    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_trigger_events_company ON trigger_events(company_id);
CREATE INDEX idx_trigger_events_type ON trigger_events(event_type);
CREATE INDEX idx_trigger_events_detected ON trigger_events(detected_at DESC);
CREATE INDEX idx_trigger_events_actioned ON trigger_events(actioned) WHERE actioned = FALSE;
CREATE INDEX idx_trigger_events_signal ON trigger_events(signal_strength DESC);
CREATE UNIQUE INDEX idx_trigger_events_dedup ON trigger_events(company_id, content_hash);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_trigger_events_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_events_updated_at
    BEFORE UPDATE ON trigger_events
    FOR EACH ROW
    EXECUTE FUNCTION update_trigger_events_updated_at();

-- View: Recent high-priority triggers for dashboard
CREATE OR REPLACE VIEW v_hot_trigger_events AS
SELECT
    te.event_id,
    te.event_type,
    te.title,
    te.signal_strength,
    te.detected_at,
    te.actioned,
    dc.name as company_name,
    dc.icp_tier,
    dc.icp_score,
    COUNT(ct.contact_id) FILTER (WHERE ct.phone IS NOT NULL) as contacts_with_phone
FROM trigger_events te
JOIN dim_companies dc ON te.company_id = dc.company_id
LEFT JOIN dim_contacts ct ON dc.company_id = ct.company_id AND ct.is_atl = TRUE
WHERE te.signal_strength >= 7
  AND te.actioned = FALSE
  AND te.detected_at >= NOW() - INTERVAL '7 days'
GROUP BY te.event_id, te.event_type, te.title, te.signal_strength, te.detected_at, te.actioned, dc.name, dc.icp_tier, dc.icp_score
ORDER BY te.signal_strength DESC, te.detected_at DESC;

-- Comments
COMMENT ON TABLE trigger_events IS 'Buying signals detected for ICP companies (funding, hiring, news, etc.)';
COMMENT ON COLUMN trigger_events.signal_strength IS 'Priority score 1-10 (10 = hottest, immediate action required)';
COMMENT ON COLUMN trigger_events.content_hash IS 'SHA256 hash of title + company_id for duplicate detection';
