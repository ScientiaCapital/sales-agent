"""Add ai_cost_tracking table and views

Revision ID: aa04f1da746c
Revises: d282f36fa807
Create Date: 2025-11-01 13:42:00.653576

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa04f1da746c'
down_revision: Union[str, None] = 'd282f36fa807'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create leads table if it doesn't exist (minimal version for foreign key)
    op.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id SERIAL PRIMARY KEY,
        company_name VARCHAR(255),
        contact_email VARCHAR(255),
        qualification_score INTEGER,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT now()
    );
    """)

    # Create ai_cost_tracking table
    op.create_table('ai_cost_tracking',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('agent_type', sa.String(length=50), nullable=False),
        sa.Column('agent_mode', sa.String(length=20), nullable=True),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('session_id', sa.String(length=255), nullable=True),
        sa.Column('user_id', sa.String(length=255), nullable=True),
        sa.Column('prompt_text', sa.Text(), nullable=True),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False),
        sa.Column('prompt_complexity', sa.String(length=20), nullable=True),
        sa.Column('completion_text', sa.Text(), nullable=True),
        sa.Column('completion_tokens', sa.Integer(), nullable=False),
        sa.Column('provider', sa.String(length=50), nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('cost_usd', sa.DECIMAL(precision=10, scale=8), nullable=False),
        sa.Column('latency_ms', sa.Integer(), nullable=True),
        sa.Column('cache_hit', sa.Boolean(), nullable=True, default=False),
        sa.Column('quality_score', sa.Float(), nullable=True),
        sa.Column('feedback_count', sa.Integer(), nullable=True, default=0),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_agent_type', 'ai_cost_tracking', ['agent_type'])
    op.create_index('idx_lead_id', 'ai_cost_tracking', ['lead_id'])
    op.create_index('idx_session_id', 'ai_cost_tracking', ['session_id'])
    op.create_index('idx_timestamp', 'ai_cost_tracking', ['timestamp'])
    op.create_index('idx_cache_hit', 'ai_cost_tracking', ['cache_hit'])

    # Create analytics views
    op.execute("""
    CREATE VIEW agent_cost_summary AS
    SELECT
        agent_type,
        COUNT(*) as total_requests,
        SUM(cost_usd) as total_cost_usd,
        AVG(cost_usd) as avg_cost_per_request,
        AVG(latency_ms) as avg_latency_ms,
        SUM(CASE WHEN cache_hit THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0) as cache_hit_rate
    FROM ai_cost_tracking
    GROUP BY agent_type;
    """)

    op.execute("""
    CREATE VIEW lead_cost_summary AS
    SELECT
        lead_id,
        COUNT(*) as ai_calls,
        SUM(cost_usd) as total_cost_usd,
        array_agg(DISTINCT agent_type) as agents_used
    FROM ai_cost_tracking
    WHERE lead_id IS NOT NULL
    GROUP BY lead_id;
    """)


def downgrade() -> None:
    # Drop views
    op.execute("DROP VIEW IF EXISTS lead_cost_summary")
    op.execute("DROP VIEW IF EXISTS agent_cost_summary")

    # Drop indexes
    op.drop_index('idx_cache_hit', table_name='ai_cost_tracking')
    op.drop_index('idx_timestamp', table_name='ai_cost_tracking')
    op.drop_index('idx_session_id', table_name='ai_cost_tracking')
    op.drop_index('idx_lead_id', table_name='ai_cost_tracking')
    op.drop_index('idx_agent_type', table_name='ai_cost_tracking')

    # Drop table
    op.drop_table('ai_cost_tracking')
