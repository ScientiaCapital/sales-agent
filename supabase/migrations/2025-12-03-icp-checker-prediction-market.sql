-- ICP Checker + Lead Prediction Market Migration
-- Run in Supabase SQL Editor

-- ICP Checker columns
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS icp_last_checked TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS icp_score_previous FLOAT;

-- Prediction Market columns
ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS prediction_score FLOAT DEFAULT 0,
ADD COLUMN IF NOT EXISTS prediction_rank INTEGER,
ADD COLUMN IF NOT EXISTS prediction_why_now TEXT,
ADD COLUMN IF NOT EXISTS prediction_updated_at TIMESTAMPTZ;

-- Create signals table for momentum tracking
CREATE TABLE IF NOT EXISTS fact_lead_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES dim_companies(company_id) ON DELETE CASCADE,
    signal_type VARCHAR(50) NOT NULL,
    signal_value JSONB DEFAULT '{}',
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ DEFAULT (NOW() + INTERVAL '7 days')
);

-- Indexes for fast lookups
CREATE INDEX IF NOT EXISTS idx_lead_signals_company_id ON fact_lead_signals(company_id);
CREATE INDEX IF NOT EXISTS idx_lead_signals_created_at ON fact_lead_signals(created_at DESC);

-- RLS
ALTER TABLE fact_lead_signals ENABLE ROW LEVEL SECURITY;

-- Policy for service role access
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_policies WHERE policyname = 'Service role full access' AND tablename = 'fact_lead_signals'
    ) THEN
        CREATE POLICY "Service role full access" ON fact_lead_signals
            FOR ALL USING (auth.role() = 'service_role');
    END IF;
END $$;
