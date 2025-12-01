"""Add schema improvements for Category 4 issues

Revision ID: 015_schema_improvements
Revises: 014_social_intelligence
Create Date: 2025-12-01

This migration addresses Category 4 issues from the Supabase audit:
- Adds missing NOT NULL constraints with defaults
- Adds CHECK constraints for data validation
- Adds missing timestamp update triggers
- Standardizes data types for consistency
- Improves data integrity across tables
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '015_schema_improvements'
down_revision = '014_social_intelligence'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Apply schema improvements for data integrity and consistency"""

    # ============================================================================
    # PART 1: Add CHECK constraints for non-negative values
    # ============================================================================

    # Lead current state - ensure counts are non-negative
    op.execute("""
        ALTER TABLE lead_current_state
        ADD CONSTRAINT IF NOT EXISTS ck_lead_state_total_calls_nonnegative
        CHECK (total_calls >= 0);

        ALTER TABLE lead_current_state
        ADD CONSTRAINT IF NOT EXISTS ck_lead_state_total_emails_nonnegative
        CHECK (total_emails >= 0);

        ALTER TABLE lead_current_state
        ADD CONSTRAINT IF NOT EXISTS ck_lead_state_contact_count_nonnegative
        CHECK (contact_count >= 0);

        ALTER TABLE lead_current_state
        ADD CONSTRAINT IF NOT EXISTS ck_lead_state_oem_count_nonnegative
        CHECK (oem_count >= 0);
    """)

    # ============================================================================
    # PART 2: Add NOT NULL constraints where appropriate
    # ============================================================================

    # Lead current state - qualification_score should have default and be NOT NULL
    op.execute("""
        -- Set default for existing NULL values
        UPDATE lead_current_state
        SET qualification_score = 0
        WHERE qualification_score IS NULL;

        -- Add default for future inserts
        ALTER TABLE lead_current_state
        ALTER COLUMN qualification_score SET DEFAULT 0;

        -- Make it NOT NULL
        ALTER TABLE lead_current_state
        ALTER COLUMN qualification_score SET NOT NULL;
    """)

    # Dim companies - icp_score should be NOT NULL for scored companies
    op.execute("""
        -- Set default for existing NULL values
        UPDATE dim_companies
        SET icp_score = 0
        WHERE icp_score IS NULL;

        -- Add default for future inserts
        ALTER TABLE dim_companies
        ALTER COLUMN icp_score SET DEFAULT 0;

        -- Make it NOT NULL
        ALTER TABLE dim_companies
        ALTER COLUMN icp_score SET NOT NULL;
    """)

    # ============================================================================
    # PART 3: Add CHECK constraints for valid stage values
    # ============================================================================

    # Lead current state - validate stage values
    op.execute("""
        ALTER TABLE lead_current_state
        ADD CONSTRAINT IF NOT EXISTS ck_lead_state_valid_stage
        CHECK (current_stage IN (
            'imported', 'qualified', 'enriched', 'in_close', 'contacted',
            'meeting_booked', 'opportunity', 'won', 'lost'
        ));
    """)

    # Scraper batches - validate status values
    op.execute("""
        ALTER TABLE scraper_batches
        ADD CONSTRAINT IF NOT EXISTS ck_scraper_batches_valid_status
        CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'cancelled'));
    """)

    # ============================================================================
    # PART 4: Add phone number format validation
    # ============================================================================

    # Dim companies - validate phone format
    op.execute("""
        ALTER TABLE dim_companies
        ADD CONSTRAINT IF NOT EXISTS ck_dim_companies_valid_phone_format
        CHECK (phone IS NULL OR phone ~ '^\\+?[0-9\\s\\-\\(\\)\\.]+$');
    """)

    # Dim contacts - validate phone format
    op.execute("""
        ALTER TABLE dim_contacts
        ADD CONSTRAINT IF NOT EXISTS ck_dim_contacts_valid_phone_format
        CHECK (phone IS NULL OR phone ~ '^\\+?[0-9\\s\\-\\(\\)\\.]+$');
    """)

    # ============================================================================
    # PART 5: Add missing timestamp update triggers
    # ============================================================================

    # Create reusable update_timestamp function if not exists
    op.execute("""
        CREATE OR REPLACE FUNCTION update_timestamp()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Add timestamp update trigger for dim_companies
    op.execute("""
        DROP TRIGGER IF EXISTS dim_companies_timestamp ON dim_companies;
        CREATE TRIGGER dim_companies_timestamp
            BEFORE UPDATE ON dim_companies
            FOR EACH ROW
            EXECUTE FUNCTION update_timestamp();
    """)

    # Add timestamp update trigger for dim_contacts
    op.execute("""
        DROP TRIGGER IF EXISTS dim_contacts_timestamp ON dim_contacts;
        CREATE TRIGGER dim_contacts_timestamp
            BEFORE UPDATE ON dim_contacts
            FOR EACH ROW
            EXECUTE FUNCTION update_timestamp();
    """)

    # Add timestamp update trigger for dim_users
    op.execute("""
        DROP TRIGGER IF EXISTS dim_users_timestamp ON dim_users;
        CREATE TRIGGER dim_users_timestamp
            BEFORE UPDATE ON dim_users
            FOR EACH ROW
            EXECUTE FUNCTION update_timestamp();
    """)

    # ============================================================================
    # PART 6: Add CHECK constraints for ICP tier validation
    # ============================================================================

    op.execute("""
        ALTER TABLE dim_companies
        ADD CONSTRAINT IF NOT EXISTS ck_dim_companies_valid_icp_tier
        CHECK (icp_tier IS NULL OR icp_tier IN ('PLATINUM', 'GOLD', 'SILVER', 'BRONZE'));
    """)

    # ============================================================================
    # PART 7: Add CHECK constraints for score ranges
    # ============================================================================

    # ICP scores should be between 0 and 100
    op.execute("""
        ALTER TABLE dim_companies
        ADD CONSTRAINT IF NOT EXISTS ck_dim_companies_icp_score_range
        CHECK (icp_score >= 0 AND icp_score <= 100);
    """)

    # Qualification scores should be between 0 and 100
    op.execute("""
        ALTER TABLE lead_current_state
        ADD CONSTRAINT IF NOT EXISTS ck_lead_state_qualification_score_range
        CHECK (qualification_score >= 0 AND qualification_score <= 100);
    """)

    # ============================================================================
    # PART 8: Add CHECK constraints for confidence scores
    # ============================================================================

    # Dim contacts - confidence should be between 0 and 1
    op.execute("""
        ALTER TABLE dim_contacts
        ADD CONSTRAINT IF NOT EXISTS ck_dim_contacts_confidence_range
        CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1));
    """)

    # ============================================================================
    # PART 9: Add comments to tables for documentation
    # ============================================================================

    op.execute("""
        COMMENT ON TABLE dim_companies IS
        'Master dimension table for company/lead data. Contains ICP scoring, contact info, and pipeline state. Updated: 2025-12-01 with schema improvements.';

        COMMENT ON TABLE dim_contacts IS
        'Dimension table for contact/decision-maker data. Links to companies. ATL = Above The Line (decision makers). Updated: 2025-12-01 with schema improvements.';

        COMMENT ON TABLE lead_current_state IS
        'Current state tracking for leads in the pipeline. Denormalized for dashboard performance. Updated: 2025-12-01 with schema improvements.';
    """)


def downgrade() -> None:
    """Remove schema improvements"""

    # Remove CHECK constraints
    op.execute("""
        ALTER TABLE lead_current_state DROP CONSTRAINT IF EXISTS ck_lead_state_total_calls_nonnegative;
        ALTER TABLE lead_current_state DROP CONSTRAINT IF EXISTS ck_lead_state_total_emails_nonnegative;
        ALTER TABLE lead_current_state DROP CONSTRAINT IF EXISTS ck_lead_state_contact_count_nonnegative;
        ALTER TABLE lead_current_state DROP CONSTRAINT IF EXISTS ck_lead_state_oem_count_nonnegative;
        ALTER TABLE lead_current_state DROP CONSTRAINT IF EXISTS ck_lead_state_valid_stage;
        ALTER TABLE lead_current_state DROP CONSTRAINT IF EXISTS ck_lead_state_qualification_score_range;

        ALTER TABLE scraper_batches DROP CONSTRAINT IF EXISTS ck_scraper_batches_valid_status;

        ALTER TABLE dim_companies DROP CONSTRAINT IF EXISTS ck_dim_companies_valid_phone_format;
        ALTER TABLE dim_companies DROP CONSTRAINT IF EXISTS ck_dim_companies_valid_icp_tier;
        ALTER TABLE dim_companies DROP CONSTRAINT IF EXISTS ck_dim_companies_icp_score_range;

        ALTER TABLE dim_contacts DROP CONSTRAINT IF EXISTS ck_dim_contacts_valid_phone_format;
        ALTER TABLE dim_contacts DROP CONSTRAINT IF EXISTS ck_dim_contacts_confidence_range;
    """)

    # Remove triggers
    op.execute("""
        DROP TRIGGER IF EXISTS dim_companies_timestamp ON dim_companies;
        DROP TRIGGER IF EXISTS dim_contacts_timestamp ON dim_contacts;
        DROP TRIGGER IF EXISTS dim_users_timestamp ON dim_users;
    """)

    # Note: We don't remove NOT NULL constraints or defaults in downgrade
    # as that could cause data loss. Manual intervention required if rollback needed.
    op.execute("""
        -- WARNING: NOT NULL constraints and defaults NOT removed in downgrade
        -- to prevent potential data loss. Manual intervention required if needed.
        COMMENT ON TABLE dim_companies IS
        'Master dimension table for company/lead data. Contains ICP scoring, contact info, and pipeline state.';

        COMMENT ON TABLE dim_contacts IS
        'Dimension table for contact/decision-maker data. Links to companies. ATL = Above The Line (decision makers).';

        COMMENT ON TABLE lead_current_state IS
        'Current state tracking for leads in the pipeline. Denormalized for dashboard performance.';
    """)
