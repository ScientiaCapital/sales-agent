"""Add account-based layer for multi-stakeholder engagement.

Revision ID: 023_account_layer
Revises: 022_enable_rls_additional_tables
Create Date: 2025-12-28

This migration introduces the Account abstraction layer:
- dim_accounts: Parent table grouping companies by domain
- Rollup metrics for stakeholder engagement tracking
- Pipeline stage tracking at the account level
- Foreign key relationships to existing dim_companies and dim_sequences

The Account model enables:
1. Multi-stakeholder sales engagement (ATL vs BTL contacts)
2. Account-level pipeline and deal tracking
3. Stakeholder score calculation (% ATL contacts engaged)
4. Domain-based company grouping for enterprise sales
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = '023_account_layer'
down_revision: Union[str, None] = '022_enable_rls_additional_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create dim_accounts table and add foreign keys to related tables."""

    # =========================================================================
    # SECTION 1: CREATE DIM_ACCOUNTS TABLE
    # =========================================================================
    op.create_table(
        'dim_accounts',
        # Primary key
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Account identification
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('domain', sa.String(255), unique=True, nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('employee_count', sa.Integer, nullable=True),

        # Rollup metrics (denormalized for query performance)
        sa.Column('total_contacts', sa.Integer, default=0, nullable=False,
                  server_default='0'),
        sa.Column('engaged_contacts', sa.Integer, default=0, nullable=False,
                  server_default='0'),
        sa.Column('total_activities', sa.Integer, default=0, nullable=False,
                  server_default='0'),
        sa.Column('stakeholder_score', sa.Float, nullable=True),

        # Pipeline tracking
        sa.Column('account_stage', sa.String(50), default='prospect',
                  nullable=False, server_default='prospect'),
        sa.Column('deal_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('probability', sa.Float, nullable=True),

        # Timestamps
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )

    # =========================================================================
    # SECTION 2: ADD ACCOUNT_ID FOREIGN KEY TO DIM_COMPANIES
    # =========================================================================
    op.add_column(
        'dim_companies',
        sa.Column('account_id', UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_companies_account',
        'dim_companies',
        'dim_accounts',
        ['account_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # =========================================================================
    # SECTION 3: ADD ACCOUNT_ID FOREIGN KEY TO DIM_SEQUENCES
    # =========================================================================
    op.add_column(
        'dim_sequences',
        sa.Column('account_id', UUID(as_uuid=True), nullable=True)
    )
    op.create_foreign_key(
        'fk_sequences_account',
        'dim_sequences',
        'dim_accounts',
        ['account_id'],
        ['id'],
        ondelete='SET NULL'
    )

    # =========================================================================
    # SECTION 4: CREATE INDEXES FOR PERFORMANCE
    # =========================================================================
    op.create_index('idx_accounts_domain', 'dim_accounts', ['domain'])
    op.create_index('idx_accounts_stage', 'dim_accounts', ['account_stage'])
    op.create_index('idx_accounts_name', 'dim_accounts', ['name'])
    op.create_index('idx_accounts_created', 'dim_accounts', ['created_at'])
    op.create_index('idx_companies_account', 'dim_companies', ['account_id'])
    op.create_index('idx_sequences_account', 'dim_sequences', ['account_id'])

    # Composite index for stage + probability queries (pipeline views)
    op.create_index(
        'idx_accounts_stage_probability',
        'dim_accounts',
        ['account_stage', 'probability']
    )

    # =========================================================================
    # SECTION 5: ADD CHECK CONSTRAINTS
    # =========================================================================
    op.execute("""
        ALTER TABLE dim_accounts
        ADD CONSTRAINT ck_accounts_valid_stage
        CHECK (account_stage IN (
            'prospect', 'engaged', 'qualified', 'opportunity', 'customer', 'churned'
        ));
    """)

    op.execute("""
        ALTER TABLE dim_accounts
        ADD CONSTRAINT ck_accounts_probability_range
        CHECK (probability IS NULL OR (probability >= 0 AND probability <= 1));
    """)

    op.execute("""
        ALTER TABLE dim_accounts
        ADD CONSTRAINT ck_accounts_stakeholder_score_range
        CHECK (stakeholder_score IS NULL OR (stakeholder_score >= 0 AND stakeholder_score <= 1));
    """)

    op.execute("""
        ALTER TABLE dim_accounts
        ADD CONSTRAINT ck_accounts_nonnegative_contacts
        CHECK (total_contacts >= 0 AND engaged_contacts >= 0);
    """)

    op.execute("""
        ALTER TABLE dim_accounts
        ADD CONSTRAINT ck_accounts_nonnegative_activities
        CHECK (total_activities >= 0);
    """)

    # =========================================================================
    # SECTION 6: ADD UPDATE TIMESTAMP TRIGGER
    # =========================================================================
    op.execute("""
        DROP TRIGGER IF EXISTS dim_accounts_timestamp ON dim_accounts;
        CREATE TRIGGER dim_accounts_timestamp
            BEFORE UPDATE ON dim_accounts
            FOR EACH ROW
            EXECUTE FUNCTION update_timestamp();
    """)

    # =========================================================================
    # SECTION 7: ENABLE RLS FOR SECURITY
    # =========================================================================
    op.execute('ALTER TABLE dim_accounts ENABLE ROW LEVEL SECURITY')

    # Create service role policy
    op.execute("""
        CREATE POLICY "dim_accounts_service_all" ON dim_accounts
            FOR ALL
            USING (auth.jwt()->>'role' = 'service_role')
            WITH CHECK (auth.jwt()->>'role' = 'service_role')
    """)

    # =========================================================================
    # SECTION 8: ADD TABLE COMMENTS
    # =========================================================================
    op.execute("""
        COMMENT ON TABLE dim_accounts IS
        'Account-level aggregation for multi-stakeholder engagement. Groups companies by domain for enterprise sales tracking. Contains rollup metrics and pipeline state.';

        COMMENT ON COLUMN dim_accounts.stakeholder_score IS
        'Percentage of ATL (Above The Line) contacts that are engaged. Calculated as engaged_atl_contacts / total_atl_contacts.';

        COMMENT ON COLUMN dim_accounts.account_stage IS
        'Pipeline stage: prospect -> engaged -> qualified -> opportunity -> customer. Used for funnel metrics.';
    """)

    print("\n" + "=" * 80)
    print("ACCOUNT LAYER MIGRATION 023 COMPLETED")
    print("=" * 80)
    print("Created: dim_accounts table with rollup metrics")
    print("Added: account_id FK to dim_companies and dim_sequences")
    print("Indexes: domain, stage, name, created_at, composite stage+probability")
    print("Constraints: stage validation, probability range, non-negative counts")
    print("Security: RLS enabled with service_role policy")
    print("=" * 80 + "\n")


def downgrade() -> None:
    """Remove account layer tables and references."""

    print("\n[WARNING] Downgrading account layer - this will remove account data!")

    # Remove RLS policy
    op.execute('DROP POLICY IF EXISTS "dim_accounts_service_all" ON dim_accounts')

    # Remove trigger
    op.execute('DROP TRIGGER IF EXISTS dim_accounts_timestamp ON dim_accounts')

    # Remove indexes
    op.drop_index('idx_accounts_stage_probability', table_name='dim_accounts')
    op.drop_index('idx_sequences_account', table_name='dim_sequences')
    op.drop_index('idx_companies_account', table_name='dim_companies')
    op.drop_index('idx_accounts_created', table_name='dim_accounts')
    op.drop_index('idx_accounts_name', table_name='dim_accounts')
    op.drop_index('idx_accounts_stage', table_name='dim_accounts')
    op.drop_index('idx_accounts_domain', table_name='dim_accounts')

    # Remove foreign keys and columns
    op.drop_constraint('fk_sequences_account', 'dim_sequences', type_='foreignkey')
    op.drop_column('dim_sequences', 'account_id')
    op.drop_constraint('fk_companies_account', 'dim_companies', type_='foreignkey')
    op.drop_column('dim_companies', 'account_id')

    # Drop the accounts table (this will also drop constraints)
    op.drop_table('dim_accounts')

    print("[DONE] Account layer removed")
