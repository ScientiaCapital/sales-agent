-- Migration: Add signal columns to dim_ai_drafts
-- Created: 2025-12-08
-- Purpose: Track the signal/trigger that prompted each draft

-- Add signal columns to track "why now" for each draft
ALTER TABLE public.dim_ai_drafts
ADD COLUMN IF NOT EXISTS signal_type TEXT,
ADD COLUMN IF NOT EXISTS signal_source TEXT,
ADD COLUMN IF NOT EXISTS signal_reason TEXT,
ADD COLUMN IF NOT EXISTS close_lead_status TEXT,
ADD COLUMN IF NOT EXISTS correspondence_summary TEXT;

-- Add comments
COMMENT ON COLUMN public.dim_ai_drafts.signal_type IS 'Type of signal that triggered the draft: SQL_BOOKING, NURTURE_REENGAGE, SAL_FOLLOWUP, OPPORTUNITY_PROGRESS, COLD_NEW, REPLY';
COMMENT ON COLUMN public.dim_ai_drafts.signal_source IS 'Source of the signal: close_status, smart_view, supabase_new, activity_reply';
COMMENT ON COLUMN public.dim_ai_drafts.signal_reason IS 'Human-readable reason for the outreach';
COMMENT ON COLUMN public.dim_ai_drafts.close_lead_status IS 'Close CRM lead status at time of draft: SQL, SAL, MQL, Opportunity, Nurture_Hot, Nurture_Cold, etc.';
COMMENT ON COLUMN public.dim_ai_drafts.correspondence_summary IS 'Summary of prior correspondence with this lead';

-- Create index for filtering by signal type
CREATE INDEX IF NOT EXISTS idx_drafts_signal_type
ON public.dim_ai_drafts (signal_type)
WHERE signal_type IS NOT NULL;

-- Add last_close_activity_at column to dim_companies to track correspondence
ALTER TABLE public.dim_companies
ADD COLUMN IF NOT EXISTS last_close_activity_at TIMESTAMP,
ADD COLUMN IF NOT EXISTS close_activity_count INTEGER DEFAULT 0,
ADD COLUMN IF NOT EXISTS close_lead_status TEXT;

COMMENT ON COLUMN public.dim_companies.last_close_activity_at IS 'Timestamp of most recent Close CRM activity';
COMMENT ON COLUMN public.dim_companies.close_activity_count IS 'Total number of Close CRM activities for this lead';
COMMENT ON COLUMN public.dim_companies.close_lead_status IS 'Current Close CRM lead status: SQL, SAL, MQL, Opportunity, etc.';

-- Validation
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'dim_ai_drafts'
        AND column_name = 'signal_type'
    ) THEN
        RAISE EXCEPTION 'signal_type column was not created successfully';
    END IF;

    RAISE NOTICE 'Migration 20251208_add_signal_columns.sql completed successfully';
END $$;
