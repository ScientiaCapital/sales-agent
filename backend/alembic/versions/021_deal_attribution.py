"""Add deal attribution table for tracking touchpoints and ROI.

Revision ID: 021_deal_attribution
Revises: 020_trigger_rules
Create Date: 2025-12-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = '021_deal_attribution'
down_revision: Union[str, None] = '020_trigger_rules'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create fact_deal_attribution table for multi-touch attribution."""

    op.create_table(
        'fact_deal_attribution',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),

        # Deal identification
        sa.Column('deal_id', sa.String(100), nullable=False, unique=True),
        sa.Column('lead_id', UUID(as_uuid=True),
                  sa.ForeignKey('dim_companies.id', ondelete='SET NULL'),
                  nullable=True),
        sa.Column('deal_name', sa.String(255), nullable=True),

        # Deal value and timing
        sa.Column('deal_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),

        # Touchpoint tracking
        sa.Column('touchpoints', JSONB, nullable=False, server_default='[]'),
        sa.Column('total_touches', sa.Integer, default=0, nullable=False),
        sa.Column('days_in_pipeline', sa.Integer, nullable=True),

        # Multi-touch attribution models (pre-calculated for fast queries)
        sa.Column('first_touch_channel', sa.String(100), nullable=True),
        sa.Column('last_touch_channel', sa.String(100), nullable=True),
        sa.Column('first_touch_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('last_touch_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('linear_touch_value', sa.Numeric(12, 2), nullable=True),
        sa.Column('time_decay_value', sa.Numeric(12, 2), nullable=True),

        # Sales rep attribution
        sa.Column('rep_id', sa.String(100), nullable=True),
        sa.Column('rep_name', sa.String(255), nullable=True),

        # Campaign/source tracking
        sa.Column('primary_campaign', sa.String(255), nullable=True),
        sa.Column('primary_source', sa.String(100), nullable=True),

        # Metadata
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )

    # Create indexes for common query patterns
    op.create_index('ix_deal_attribution_closed_at', 'fact_deal_attribution', ['closed_at'])
    op.create_index('ix_deal_attribution_lead_id', 'fact_deal_attribution', ['lead_id'])
    op.create_index('ix_deal_attribution_deal_id', 'fact_deal_attribution', ['deal_id'])
    op.create_index('ix_deal_attribution_rep_id', 'fact_deal_attribution', ['rep_id'])
    op.create_index('ix_deal_attribution_first_touch', 'fact_deal_attribution', ['first_touch_channel'])
    op.create_index('ix_deal_attribution_last_touch', 'fact_deal_attribution', ['last_touch_channel'])

    # Create touchpoint_types table for standardization
    op.create_table(
        'touchpoint_types',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('channel', sa.String(50), nullable=False),  # email, call, meeting, etc.
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('default_weight', sa.Float, default=1.0, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
    )

    # Insert default touchpoint types
    op.execute("""
        INSERT INTO touchpoint_types (name, channel, description, default_weight) VALUES
        ('email_sent', 'email', 'Outbound email sent', 0.5),
        ('email_opened', 'email', 'Email opened by recipient', 0.3),
        ('email_clicked', 'email', 'Link clicked in email', 0.8),
        ('email_replied', 'email', 'Reply received to email', 1.0),
        ('call_completed', 'call', 'Phone call completed', 1.0),
        ('call_positive', 'call', 'Positive sentiment call', 1.5),
        ('meeting_scheduled', 'meeting', 'Meeting scheduled', 1.2),
        ('meeting_completed', 'meeting', 'Meeting completed', 1.5),
        ('demo_completed', 'demo', 'Product demo completed', 2.0),
        ('proposal_sent', 'proposal', 'Proposal/quote sent', 1.5),
        ('linkedin_connection', 'social', 'LinkedIn connection made', 0.4),
        ('website_visit', 'web', 'Website visit tracked', 0.2),
        ('content_download', 'content', 'Content/whitepaper downloaded', 0.6),
        ('webinar_attended', 'webinar', 'Webinar attended', 0.8)
    """)

    # Add comment
    op.execute("""
        COMMENT ON TABLE fact_deal_attribution IS
        'Multi-touch attribution for closed deals - tracks all touchpoints that influenced conversion'
    """)
    op.execute("""
        COMMENT ON TABLE touchpoint_types IS
        'Standardized touchpoint types with default weights for attribution models'
    """)


def downgrade() -> None:
    """Drop attribution tables."""
    op.drop_table('fact_deal_attribution')
    op.drop_table('touchpoint_types')
