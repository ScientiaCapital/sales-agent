-- Migration: Add batch job tracking tables
-- Description: Tables for tracking parallel batch processing jobs and individual lead status
-- Date: 2024-12-02

-- =============================================
-- BATCH JOBS TABLE
-- Tracks overall batch processing jobs
-- =============================================

CREATE TABLE IF NOT EXISTS batch_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Job identification
    name VARCHAR(255) NOT NULL,
    created_by VARCHAR(100),

    -- Status tracking
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN (
        'pending', 'running', 'paused', 'completed',
        'completed_with_errors', 'failed', 'cancelled'
    )),

    -- Progress counters
    total_leads INTEGER NOT NULL,
    processed_leads INTEGER DEFAULT 0,
    successful_leads INTEGER DEFAULT 0,
    failed_leads INTEGER DEFAULT 0,
    skipped_leads INTEGER DEFAULT 0,

    -- Configuration
    options_json JSONB DEFAULT '{}',
    priority VARCHAR(20) DEFAULT 'medium' CHECK (priority IN ('high', 'medium', 'low')),

    -- Timing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Results
    error_message TEXT,
    result_summary_json JSONB
);

-- Indexes for batch_jobs
CREATE INDEX IF NOT EXISTS idx_batch_jobs_status ON batch_jobs(status);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_created_at ON batch_jobs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_batch_jobs_priority ON batch_jobs(priority, status);

-- =============================================
-- BATCH JOB LEADS TABLE
-- Tracks individual lead status within a batch
-- =============================================

CREATE TABLE IF NOT EXISTS batch_job_leads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    batch_job_id UUID NOT NULL REFERENCES batch_jobs(id) ON DELETE CASCADE,
    company_id UUID NOT NULL,  -- References dim_companies.company_id

    -- Processing state
    status VARCHAR(50) DEFAULT 'pending' CHECK (status IN (
        'pending', 'processing', 'completed', 'failed', 'skipped'
    )),

    -- Timing
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,

    -- Error handling
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,

    -- Results
    result_json JSONB,
    latency_ms INTEGER,
    cost_usd DECIMAL(10, 6)
);

-- Indexes for batch_job_leads
CREATE INDEX IF NOT EXISTS idx_batch_job_leads_job_status ON batch_job_leads(batch_job_id, status);
CREATE INDEX IF NOT EXISTS idx_batch_job_leads_company ON batch_job_leads(company_id);
CREATE INDEX IF NOT EXISTS idx_batch_job_leads_status ON batch_job_leads(status);

-- =============================================
-- ROW LEVEL SECURITY
-- =============================================

-- Enable RLS
ALTER TABLE batch_jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE batch_job_leads ENABLE ROW LEVEL SECURITY;

-- Drop existing policies if they exist (idempotent)
DROP POLICY IF EXISTS "Service role has full access to batch_jobs" ON batch_jobs;
DROP POLICY IF EXISTS "Service role has full access to batch_job_leads" ON batch_job_leads;

-- Service role policies (for backend API)
CREATE POLICY "Service role has full access to batch_jobs"
    ON batch_jobs
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

CREATE POLICY "Service role has full access to batch_job_leads"
    ON batch_job_leads
    FOR ALL
    TO service_role
    USING (true)
    WITH CHECK (true);

-- =============================================
-- HELPER FUNCTIONS
-- =============================================

-- Function to update batch job progress atomically
CREATE OR REPLACE FUNCTION update_batch_progress(
    p_batch_id UUID,
    p_status VARCHAR(50),
    p_increment_processed BOOLEAN DEFAULT true
) RETURNS void AS $$
BEGIN
    UPDATE batch_jobs
    SET
        processed_leads = CASE WHEN p_increment_processed THEN processed_leads + 1 ELSE processed_leads END,
        successful_leads = CASE WHEN p_status = 'completed' THEN successful_leads + 1 ELSE successful_leads END,
        failed_leads = CASE WHEN p_status = 'failed' THEN failed_leads + 1 ELSE failed_leads END,
        skipped_leads = CASE WHEN p_status = 'skipped' THEN skipped_leads + 1 ELSE skipped_leads END
    WHERE id = p_batch_id;
END;
$$ LANGUAGE plpgsql;

-- Function to get batch progress summary
CREATE OR REPLACE FUNCTION get_batch_progress(p_batch_id UUID)
RETURNS TABLE(
    total INTEGER,
    processed INTEGER,
    successful INTEGER,
    failed INTEGER,
    skipped INTEGER,
    remaining INTEGER,
    percent_complete DECIMAL(5,2)
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        bj.total_leads AS total,
        bj.processed_leads AS processed,
        bj.successful_leads AS successful,
        bj.failed_leads AS failed,
        bj.skipped_leads AS skipped,
        (bj.total_leads - bj.processed_leads) AS remaining,
        CASE
            WHEN bj.total_leads > 0 THEN
                ROUND((bj.processed_leads::DECIMAL / bj.total_leads) * 100, 2)
            ELSE 0
        END AS percent_complete
    FROM batch_jobs bj
    WHERE bj.id = p_batch_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================
-- TRIGGERS
-- =============================================

-- Auto-update batch status when all leads processed
CREATE OR REPLACE FUNCTION check_batch_completion()
RETURNS TRIGGER AS $$
DECLARE
    v_total INTEGER;
    v_processed INTEGER;
    v_failed INTEGER;
BEGIN
    SELECT total_leads, processed_leads, failed_leads
    INTO v_total, v_processed, v_failed
    FROM batch_jobs
    WHERE id = NEW.batch_job_id;

    -- Check if all leads processed
    IF v_processed >= v_total THEN
        UPDATE batch_jobs
        SET
            status = CASE
                WHEN v_failed > 0 THEN 'completed_with_errors'
                ELSE 'completed'
            END,
            completed_at = NOW()
        WHERE id = NEW.batch_job_id AND status = 'running';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger (drop first for idempotency)
DROP TRIGGER IF EXISTS trigger_check_batch_completion ON batch_job_leads;
CREATE TRIGGER trigger_check_batch_completion
    AFTER UPDATE OF status ON batch_job_leads
    FOR EACH ROW
    WHEN (NEW.status IN ('completed', 'failed', 'skipped') AND OLD.status != NEW.status)
    EXECUTE FUNCTION check_batch_completion();

-- =============================================
-- COMMENTS
-- =============================================

COMMENT ON TABLE batch_jobs IS 'Tracks batch processing jobs for parallel lead enrichment';
COMMENT ON TABLE batch_job_leads IS 'Tracks individual lead status within a batch job';
COMMENT ON COLUMN batch_jobs.priority IS 'Queue priority: high (Platinum/Gold), medium (Silver), low (Bronze)';
COMMENT ON COLUMN batch_jobs.options_json IS 'Pipeline options passed to PipelineOrchestrator';
COMMENT ON COLUMN batch_job_leads.result_json IS 'Full result from PipelineTestResponse';
