-- Migration: Add close_email_id column to dim_ai_drafts
-- Created: 2025-12-08
-- Purpose: Track the Close CRM email draft ID when staging drafts

-- Add close_email_id column (stores the Close CRM email activity ID for staged drafts)
ALTER TABLE public.dim_ai_drafts
ADD COLUMN IF NOT EXISTS close_email_id TEXT;

-- Add comment
COMMENT ON COLUMN public.dim_ai_drafts.close_email_id IS 'Close CRM email activity ID for staged drafts (status=draft in Close)';

-- Create index for lookup by Close email ID
CREATE INDEX IF NOT EXISTS idx_drafts_close_email_id
ON public.dim_ai_drafts (close_email_id)
WHERE close_email_id IS NOT NULL;

-- Validation
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public'
        AND table_name = 'dim_ai_drafts'
        AND column_name = 'close_email_id'
    ) THEN
        RAISE EXCEPTION 'close_email_id column was not created successfully';
    END IF;

    RAISE NOTICE 'Migration 20251208_add_close_email_id.sql completed successfully';
END $$;
