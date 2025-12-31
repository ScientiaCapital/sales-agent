"""Create buyer intent signals table and scoring infrastructure.

Revision ID: 024_buyer_intent
Revises: 023_dealer_metrics
Create Date: 2025-12-28

Creates infrastructure for buyer intent scoring:
- buyer_intent_signals: Individual intent signals from email, web, calls
- Adds intent_score column to dim_companies for fast queries
- Indexes for efficient intent signal aggregation
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '025_buyer_intent'
down_revision: Union[str, None] = '024_dealer_metrics'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create buyer intent signals table and add intent_score to dim_companies."""

    # ===========================================================================
    # TABLE: buyer_intent_signals
    # ===========================================================================
    op.create_table(
        'buyer_intent_signals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True),
                  sa.ForeignKey('dim_companies.id', ondelete='CASCADE'),
                  nullable=False, index=True),

        # Signal classification
        sa.Column('signal_type', sa.String(50), nullable=False),
        sa.Column('signal_weight', sa.Float, nullable=False),
        sa.Column('source', sa.String(50), nullable=False),

        # Additional context
        sa.Column('metadata', postgresql.JSONB, server_default='{}', nullable=False),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )

    # ===========================================================================
    # INDEXES for buyer_intent_signals
    # ===========================================================================

    # Composite index for lead intent aggregation
    op.create_index(
        'idx_intent_lead_created',
        'buyer_intent_signals',
        ['lead_id', 'created_at']
    )

    # Index for filtering by signal type
    op.create_index(
        'idx_intent_signal_type',
        'buyer_intent_signals',
        ['signal_type']
    )

    # Index for time-based queries (recent signals)
    op.create_index(
        'idx_intent_created_desc',
        'buyer_intent_signals',
        [sa.text('created_at DESC')]
    )

    # Index for source filtering
    op.create_index(
        'idx_intent_source',
        'buyer_intent_signals',
        ['source']
    )

    # ===========================================================================
    # ADD COLUMNS to dim_companies for intent scoring
    # ===========================================================================

    # Add intent_score column (0-100 scale)
    op.execute("""
        ALTER TABLE dim_companies
        ADD COLUMN IF NOT EXISTS intent_score FLOAT DEFAULT 0
    """)

    # Add intent_updated_at for cache invalidation
    op.execute("""
        ALTER TABLE dim_companies
        ADD COLUMN IF NOT EXISTS intent_updated_at TIMESTAMPTZ
    """)

    # Index for hot leads query (high intent score)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dim_companies_intent_score
        ON dim_companies(intent_score DESC)
        WHERE intent_score > 0
    """)

    # ===========================================================================
    # ENABLE RLS on buyer_intent_signals
    # ===========================================================================
    op.execute('ALTER TABLE buyer_intent_signals ENABLE ROW LEVEL SECURITY')

    # Service role policy
    op.execute("""
        CREATE POLICY "buyer_intent_signals_service_all"
        ON buyer_intent_signals
        FOR ALL
        USING (auth.jwt()->>'role' = 'service_role')
        WITH CHECK (auth.jwt()->>'role' = 'service_role')
    """)

    # ===========================================================================
    # FUNCTION: Calculate intent score with time decay
    # ===========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION calculate_lead_intent_score(p_lead_id UUID)
        RETURNS FLOAT AS $$
        DECLARE
            v_score FLOAT := 0;
            v_half_life_days FLOAT := 7.0;
        BEGIN
            -- Calculate weighted sum with exponential time decay
            -- Score = SUM(weight * 2^(-days_old / half_life))
            SELECT COALESCE(
                SUM(
                    signal_weight * POWER(2, -1.0 * EXTRACT(EPOCH FROM (NOW() - created_at)) / (v_half_life_days * 86400))
                ),
                0
            )
            INTO v_score
            FROM buyer_intent_signals
            WHERE lead_id = p_lead_id
              AND created_at >= NOW() - INTERVAL '30 days';

            -- Cap at 100
            RETURN LEAST(v_score, 100);
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ===========================================================================
    # TRIGGER: Auto-update intent_score on new signals
    # ===========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION update_lead_intent_score()
        RETURNS TRIGGER AS $$
        BEGIN
            UPDATE dim_companies
            SET intent_score = calculate_lead_intent_score(NEW.lead_id),
                intent_updated_at = NOW()
            WHERE id = NEW.lead_id;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)

    op.execute("""
        CREATE TRIGGER trg_update_intent_score
        AFTER INSERT ON buyer_intent_signals
        FOR EACH ROW
        EXECUTE FUNCTION update_lead_intent_score()
    """)

    print("\n" + "=" * 80)
    print("BUYER INTENT MIGRATION 024 COMPLETED")
    print("=" * 80)
    print("Created table:")
    print("  - buyer_intent_signals (signal tracking)")
    print("\nAdded columns to dim_companies:")
    print("  - intent_score (0-100)")
    print("  - intent_updated_at (cache timestamp)")
    print("\nCreated functions:")
    print("  - calculate_lead_intent_score(lead_id)")
    print("  - update_lead_intent_score() trigger function")
    print("\nCreated trigger:")
    print("  - trg_update_intent_score (auto-updates score on new signals)")
    print("=" * 80 + "\n")


def downgrade() -> None:
    """Remove buyer intent infrastructure."""

    # Drop trigger
    op.execute("DROP TRIGGER IF EXISTS trg_update_intent_score ON buyer_intent_signals")

    # Drop functions
    op.execute("DROP FUNCTION IF EXISTS update_lead_intent_score()")
    op.execute("DROP FUNCTION IF EXISTS calculate_lead_intent_score(UUID)")

    # Drop RLS policy
    op.execute('DROP POLICY IF EXISTS "buyer_intent_signals_service_all" ON buyer_intent_signals')

    # Drop indexes on dim_companies
    op.execute("DROP INDEX IF EXISTS idx_dim_companies_intent_score")

    # Remove columns from dim_companies
    op.execute("ALTER TABLE dim_companies DROP COLUMN IF EXISTS intent_updated_at")
    op.execute("ALTER TABLE dim_companies DROP COLUMN IF EXISTS intent_score")

    # Drop table (includes indexes)
    op.drop_table('buyer_intent_signals')

    print("Rolled back buyer intent migration 024")
