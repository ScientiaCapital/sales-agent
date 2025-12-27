"""Add call_insights table for AI-powered call analysis

Revision ID: 019_call_insights
Revises: 018_schema_improvements
Create Date: 2025-12-27

This migration adds the call_insights table to store AI-analyzed
call recordings data. Integrates with PostCallAnalyzer (AssemblyAI)
to extract sentiment, objections, buying signals, and action items.

Features:
- Links to voice_session_logs for call metadata
- Links to dim_companies for lead context
- JSONB columns for flexible insight storage
- Scoring metrics for call quality assessment
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '019_call_insights'
down_revision: Union[str, None] = '018_schema_improvements'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'call_insights',
        # Primary key
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False,
                  server_default=sa.text('gen_random_uuid()')),

        # Foreign keys
        sa.Column('voice_session_id', sa.String(length=255), nullable=True),
        sa.Column('lead_id', postgresql.UUID(as_uuid=True), nullable=True),

        # Analysis results
        sa.Column('transcript', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_label', sa.String(length=20), nullable=True),

        # Extracted insights (JSONB for flexibility)
        sa.Column('objections', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('buying_signals', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('action_items', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('competitors_mentioned', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('key_topics', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'[]'::jsonb")),
        sa.Column('entities', postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),

        # Scoring metrics
        sa.Column('call_score', sa.Integer(), nullable=True),
        sa.Column('talk_ratio', sa.Float(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('outcome', sa.String(length=50), nullable=True),

        # Metadata
        sa.Column('analyzer_version', sa.String(length=20), nullable=True),
        sa.Column('analyzed_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),

        # Constraints
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['voice_session_id'], ['voice_session_logs.id'],
                                ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['lead_id'], ['dim_companies.id'],
                                ondelete='SET NULL'),
    )

    # Indexes for common queries
    op.create_index('idx_call_insights_voice_session', 'call_insights',
                    ['voice_session_id'], unique=False)
    op.create_index('idx_call_insights_lead', 'call_insights',
                    ['lead_id'], unique=False)
    op.create_index('idx_call_insights_sentiment', 'call_insights',
                    ['sentiment_label'], unique=False)
    op.create_index('idx_call_insights_outcome', 'call_insights',
                    ['outcome'], unique=False)
    op.create_index('idx_call_insights_analyzed_at', 'call_insights',
                    ['analyzed_at'], unique=False)
    op.create_index('idx_call_insights_call_score', 'call_insights',
                    ['call_score'], unique=False)

    # CHECK constraints for data validation
    op.execute("""
        ALTER TABLE call_insights
        ADD CONSTRAINT ck_call_insights_sentiment_score_range
        CHECK (sentiment_score IS NULL OR (sentiment_score >= -1 AND sentiment_score <= 1));

        ALTER TABLE call_insights
        ADD CONSTRAINT ck_call_insights_call_score_range
        CHECK (call_score IS NULL OR (call_score >= 0 AND call_score <= 100));

        ALTER TABLE call_insights
        ADD CONSTRAINT ck_call_insights_talk_ratio_range
        CHECK (talk_ratio IS NULL OR (talk_ratio >= 0 AND talk_ratio <= 1));

        ALTER TABLE call_insights
        ADD CONSTRAINT ck_call_insights_valid_sentiment
        CHECK (sentiment_label IS NULL OR sentiment_label IN ('positive', 'negative', 'neutral'));

        ALTER TABLE call_insights
        ADD CONSTRAINT ck_call_insights_valid_outcome
        CHECK (outcome IS NULL OR outcome IN (
            'meeting_booked', 'callback_scheduled', 'qualified',
            'not_qualified', 'needs_nurturing', 'follow_up_required'
        ));
    """)

    # Add updated_at trigger
    op.execute("""
        CREATE TRIGGER call_insights_timestamp
            BEFORE UPDATE ON call_insights
            FOR EACH ROW
            EXECUTE FUNCTION update_timestamp();
    """)

    # Add table comment
    op.execute("""
        COMMENT ON TABLE call_insights IS
        'AI-analyzed call recordings with sentiment, objections, buying signals, and action items. Fed by PostCallAnalyzer (AssemblyAI).';
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS call_insights_timestamp ON call_insights;")
    op.drop_index('idx_call_insights_call_score', table_name='call_insights')
    op.drop_index('idx_call_insights_analyzed_at', table_name='call_insights')
    op.drop_index('idx_call_insights_outcome', table_name='call_insights')
    op.drop_index('idx_call_insights_sentiment', table_name='call_insights')
    op.drop_index('idx_call_insights_lead', table_name='call_insights')
    op.drop_index('idx_call_insights_voice_session', table_name='call_insights')
    op.drop_table('call_insights')
