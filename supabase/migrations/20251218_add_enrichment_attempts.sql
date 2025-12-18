-- Track every enrichment API call for detailed cost/success reporting
CREATE TABLE IF NOT EXISTS fact_enrichment_attempts (
    attempt_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES dim_companies(company_id),
    company_name TEXT,
    domain TEXT NOT NULL,

    -- Enrichment source
    source TEXT NOT NULL CHECK (source IN ('hunter_io', 'apollo_free', 'apollo_paid', 'linkedin', 'browserbase', 'ai_enrichment')),

    -- Results
    success BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    contacts_found INTEGER DEFAULT 0,
    atl_found INTEGER DEFAULT 0,
    btl_found INTEGER DEFAULT 0,
    emails_found INTEGER DEFAULT 0,
    phones_found INTEGER DEFAULT 0,

    -- Cost & Performance
    cost_usd DECIMAL(10,6) DEFAULT 0,
    latency_ms INTEGER,
    api_credits_used INTEGER DEFAULT 0,

    -- Metadata
    batch_id UUID,
    session_id TEXT,
    raw_response JSONB,

    -- Timestamps
    attempted_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for reporting
CREATE INDEX idx_enrichment_attempts_source ON fact_enrichment_attempts(source);
CREATE INDEX idx_enrichment_attempts_date ON fact_enrichment_attempts(attempted_at);
CREATE INDEX idx_enrichment_attempts_company ON fact_enrichment_attempts(company_id);
CREATE INDEX idx_enrichment_attempts_batch ON fact_enrichment_attempts(batch_id);
CREATE INDEX idx_enrichment_attempts_success ON fact_enrichment_attempts(source, success);

-- RLS
ALTER TABLE fact_enrichment_attempts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "service_role_all" ON fact_enrichment_attempts FOR ALL TO service_role USING (true);

-- Comment
COMMENT ON TABLE fact_enrichment_attempts IS 'Tracks every enrichment API call for detailed cost/success reporting and progressive enrichment tracking';
