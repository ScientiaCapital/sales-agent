-- Migration: Create dim_ai_drafts table for AI-generated outreach content
-- Created: 2025-12-02
-- Purpose: Store AI-generated emails, SMS, and voice scripts for BDR approval workflow

-- ============================================================================
-- TABLE: dim_ai_drafts
-- ============================================================================

COMMENT ON SCHEMA public IS 'Sales Agent - AI Command Center';

CREATE TABLE IF NOT EXISTS public.dim_ai_drafts (
    -- Primary Key
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    -- Foreign Keys
    company_id UUID NOT NULL REFERENCES public.dim_companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES public.dim_contacts(id) ON DELETE SET NULL,

    -- Draft Content
    draft_type TEXT NOT NULL CHECK (draft_type IN ('email', 'sms', 'voice')),
    subject TEXT,  -- For email only
    body TEXT NOT NULL,

    -- AI Enrichment
    personal_hooks JSONB DEFAULT '[]'::jsonb,  -- Array of personalization insights
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    model_used TEXT DEFAULT 'llama-3.3-70b',
    processing_time_ms INT DEFAULT 0 CHECK (processing_time_ms >= 0),

    -- Workflow Status
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'sent', 'discarded')),
    sent_at TIMESTAMPTZ,
    close_activity_id TEXT,  -- Reference to Close CRM activity after sending

    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'system'
);

-- ============================================================================
-- COMMENTS
-- ============================================================================

COMMENT ON TABLE public.dim_ai_drafts IS 'AI-generated outreach drafts (email, SMS, voice) for BDR approval workflow';

COMMENT ON COLUMN public.dim_ai_drafts.id IS 'Unique draft identifier';
COMMENT ON COLUMN public.dim_ai_drafts.company_id IS 'Company this draft targets (required)';
COMMENT ON COLUMN public.dim_ai_drafts.contact_id IS 'Specific contact if known (optional)';
COMMENT ON COLUMN public.dim_ai_drafts.draft_type IS 'Type of outreach: email, sms, or voice';
COMMENT ON COLUMN public.dim_ai_drafts.subject IS 'Email subject line (email drafts only)';
COMMENT ON COLUMN public.dim_ai_drafts.body IS 'Main content of the draft';
COMMENT ON COLUMN public.dim_ai_drafts.personal_hooks IS 'Array of personalization insights (e.g., ["Carrier dealer", "Family-owned 20+ years"])';
COMMENT ON COLUMN public.dim_ai_drafts.confidence IS 'AI confidence score (0.0-1.0) for draft quality';
COMMENT ON COLUMN public.dim_ai_drafts.model_used IS 'AI model used to generate draft (e.g., llama-3.3-70b, deepseek-chat)';
COMMENT ON COLUMN public.dim_ai_drafts.processing_time_ms IS 'Time taken to generate draft in milliseconds';
COMMENT ON COLUMN public.dim_ai_drafts.status IS 'Draft lifecycle: pending → approved/discarded → sent';
COMMENT ON COLUMN public.dim_ai_drafts.sent_at IS 'Timestamp when draft was sent to prospect';
COMMENT ON COLUMN public.dim_ai_drafts.close_activity_id IS 'Close CRM activity ID after sending (for tracking)';
COMMENT ON COLUMN public.dim_ai_drafts.created_at IS 'Draft generation timestamp';
COMMENT ON COLUMN public.dim_ai_drafts.updated_at IS 'Last modification timestamp';
COMMENT ON COLUMN public.dim_ai_drafts.created_by IS 'User or system that created the draft';

-- ============================================================================
-- INDEXES
-- ============================================================================

-- Partial index for pending drafts queue (most common query)
CREATE INDEX idx_drafts_pending
ON public.dim_ai_drafts (status, created_at DESC)
WHERE status = 'pending';

-- Company lookup (for "show all drafts for this company")
CREATE INDEX idx_drafts_company
ON public.dim_ai_drafts (company_id);

-- Contact lookup (for "show all drafts for this contact")
CREATE INDEX idx_drafts_contact
ON public.dim_ai_drafts (contact_id)
WHERE contact_id IS NOT NULL;

-- Draft type filtering
CREATE INDEX idx_drafts_type
ON public.dim_ai_drafts (draft_type, created_at DESC);

-- Sent drafts lookup (for analytics)
CREATE INDEX idx_drafts_sent
ON public.dim_ai_drafts (sent_at DESC)
WHERE sent_at IS NOT NULL;

-- ============================================================================
-- TRIGGERS
-- ============================================================================

-- Updated_at trigger
CREATE OR REPLACE FUNCTION public.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at
BEFORE UPDATE ON public.dim_ai_drafts
FOR EACH ROW
EXECUTE FUNCTION public.update_updated_at_column();

-- ============================================================================
-- ROW LEVEL SECURITY (RLS)
-- ============================================================================

ALTER TABLE public.dim_ai_drafts ENABLE ROW LEVEL SECURITY;

-- Allow service role full access (for backend API)
CREATE POLICY "Allow all for service role"
ON public.dim_ai_drafts
FOR ALL
TO service_role
USING (true)
WITH CHECK (true);

-- Allow authenticated users to read their own drafts
CREATE POLICY "Allow authenticated users to read all drafts"
ON public.dim_ai_drafts
FOR SELECT
TO authenticated
USING (true);

-- ============================================================================
-- GRANTS
-- ============================================================================

GRANT ALL ON public.dim_ai_drafts TO service_role;
GRANT SELECT ON public.dim_ai_drafts TO authenticated;

-- ============================================================================
-- VALIDATION
-- ============================================================================

-- Validate table creation
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name = 'dim_ai_drafts'
    ) THEN
        RAISE EXCEPTION 'dim_ai_drafts table was not created successfully';
    END IF;

    RAISE NOTICE 'Migration 20251202_create_ai_drafts.sql completed successfully';
END $$;
