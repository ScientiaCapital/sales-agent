-- =====================================================
-- Sales Agent Pipeline Tracking Table
-- =====================================================
-- Tracks full lifecycle: Enriched → Lead → Opp → Won/Lost
-- Attribution: Every deal traces back to sales-agent enrichment
-- =====================================================

CREATE TABLE IF NOT EXISTS fact_opportunities (
    -- Primary Keys
    opportunity_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES dim_companies(company_id),
    close_opportunity_id VARCHAR(100) UNIQUE NOT NULL,

    -- Opportunity Details
    status VARCHAR(20) CHECK (status IN ('active', 'won', 'lost')),
    stage VARCHAR(50),  -- 'Demo', 'Proposal', 'Negotiation', etc.
    value DECIMAL(12,2) DEFAULT 0,
    confidence INTEGER CHECK (confidence BETWEEN 0 AND 100),

    -- Timeline
    expected_close_date TIMESTAMPTZ,
    actual_close_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    -- Outcome Tracking
    close_reason TEXT,  -- Why won/lost
    sales_agent_attribution BOOLEAN DEFAULT TRUE,  -- Tracks if from sales-agent enrichment

    -- Metadata
    custom_fields JSONB DEFAULT '{}'
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_opportunities_company_id ON fact_opportunities(company_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_status ON fact_opportunities(status);
CREATE INDEX IF NOT EXISTS idx_opportunities_close_opp_id ON fact_opportunities(close_opportunity_id);
CREATE INDEX IF NOT EXISTS idx_opportunities_sales_agent ON fact_opportunities(sales_agent_attribution) WHERE sales_agent_attribution = TRUE;

-- Comments
COMMENT ON TABLE fact_opportunities IS
  'Tracks sales pipeline from enrichment to close.
   Every opportunity with sales_agent_attribution=TRUE came from our enrichment.';

COMMENT ON COLUMN fact_opportunities.sales_agent_attribution IS
  'TRUE if this opportunity originated from sales-agent enrichment.
   Used for ROI tracking and attribution reporting.';

-- =====================================================
-- Update dim_companies to track Close sync status
-- =====================================================

ALTER TABLE dim_companies
ADD COLUMN IF NOT EXISTS synced_to_close_at TIMESTAMPTZ,
ADD COLUMN IF NOT EXISTS close_sync_status VARCHAR(20) DEFAULT 'pending' CHECK (close_sync_status IN ('pending', 'synced', 'failed'));

CREATE INDEX IF NOT EXISTS idx_companies_close_sync ON dim_companies(close_sync_status) WHERE close_sync_status != 'synced';

COMMENT ON COLUMN dim_companies.synced_to_close_at IS
  'When this enriched company was last synced to Close CRM';

COMMENT ON COLUMN dim_companies.close_sync_status IS
  'Sync status: pending (needs sync), synced (in Close), failed (sync error)';
