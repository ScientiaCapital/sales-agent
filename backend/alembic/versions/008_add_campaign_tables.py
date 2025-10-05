"""add_campaign_tables

Revision ID: 008_campaign_tables
Revises: 007_comprehensive_indexes
Create Date: 2025-10-04

This migration creates the campaign management tables for personalized outreach:
- campaigns: Campaign configuration and performance tracking
- campaign_messages: Individual messages with variants
- message_variant_analytics: A/B testing analytics
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '008_campaign_tables'
down_revision: Union[str, None] = '007_comprehensive_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create campaign management tables for personalized outreach system.
    """
    # Create campaigns table
    op.create_table(
        'campaigns',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='draft'),
        sa.Column('channel', sa.String(length=50), nullable=False),
        sa.Column('target_audience', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('min_qualification_score', sa.Float(), nullable=True),
        sa.Column('total_messages', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('messages_sent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('messages_delivered', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('messages_opened', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('messages_clicked', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('messages_replied', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('variant_performance', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('winning_variant', sa.Integer(), nullable=True),
        sa.Column('total_cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create campaign indexes
    op.create_index(op.f('ix_campaigns_id'), 'campaigns', ['id'], unique=False)
    op.create_index(op.f('ix_campaigns_name'), 'campaigns', ['name'], unique=False)
    op.create_index(op.f('ix_campaigns_status'), 'campaigns', ['status'], unique=False)
    op.create_index(op.f('ix_campaigns_channel'), 'campaigns', ['channel'], unique=False)

    # Create campaign_messages table
    op.create_table(
        'campaign_messages',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('campaign_id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('variants', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('selected_variant', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('clicked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('replied_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('channel_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('generation_latency_ms', sa.Integer(), nullable=True),
        sa.Column('generation_model', sa.String(length=100), nullable=True),
        sa.Column('generation_cost_usd', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['campaign_id'], ['campaigns.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE')
    )

    # Create campaign_messages indexes
    op.create_index(op.f('ix_campaign_messages_id'), 'campaign_messages', ['id'], unique=False)
    op.create_index(op.f('ix_campaign_messages_campaign_id'), 'campaign_messages', ['campaign_id'], unique=False)
    op.create_index(op.f('ix_campaign_messages_lead_id'), 'campaign_messages', ['lead_id'], unique=False)
    op.create_index(op.f('ix_campaign_messages_status'), 'campaign_messages', ['status'], unique=False)

    # Create message_variant_analytics table
    op.create_table(
        'message_variant_analytics',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('message_id', sa.Integer(), nullable=False),
        sa.Column('variant_number', sa.Integer(), nullable=False),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('tone', sa.String(length=100), nullable=True),
        sa.Column('sent_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('delivered_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('opened_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('clicked_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('replied_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('bounced_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('open_rate', sa.Float(), nullable=True),
        sa.Column('click_rate', sa.Float(), nullable=True),
        sa.Column('reply_rate', sa.Float(), nullable=True),
        sa.Column('conversion_rate', sa.Float(), nullable=True),
        sa.Column('is_statistically_significant', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('confidence_level', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['message_id'], ['campaign_messages.id'], ondelete='CASCADE')
    )

    # Create message_variant_analytics indexes
    op.create_index(op.f('ix_message_variant_analytics_id'), 'message_variant_analytics', ['id'], unique=False)
    op.create_index(op.f('ix_message_variant_analytics_message_id'), 'message_variant_analytics', ['message_id'], unique=False)

    # Add CHECK constraints for data integrity
    op.create_check_constraint(
        'ck_campaigns_status_valid',
        'campaigns',
        "status IN ('draft', 'active', 'paused', 'completed', 'cancelled')"
    )

    op.create_check_constraint(
        'ck_campaigns_channel_valid',
        'campaigns',
        "channel IN ('email', 'linkedin', 'sms', 'custom')"
    )

    op.create_check_constraint(
        'ck_campaigns_qualification_score_range',
        'campaigns',
        'min_qualification_score IS NULL OR (min_qualification_score >= 0 AND min_qualification_score <= 100)'
    )

    op.create_check_constraint(
        'ck_campaign_messages_status_valid',
        'campaign_messages',
        "status IN ('pending', 'sent', 'delivered', 'opened', 'clicked', 'replied', 'bounced', 'failed')"
    )

    op.create_check_constraint(
        'ck_campaign_messages_selected_variant_valid',
        'campaign_messages',
        'selected_variant >= 0 AND selected_variant <= 2'
    )

    op.create_check_constraint(
        'ck_message_variant_analytics_variant_number_valid',
        'message_variant_analytics',
        'variant_number >= 0 AND variant_number <= 2'
    )

    op.create_check_constraint(
        'ck_message_variant_analytics_rates_valid',
        'message_variant_analytics',
        """
        (open_rate IS NULL OR (open_rate >= 0 AND open_rate <= 1)) AND
        (click_rate IS NULL OR (click_rate >= 0 AND click_rate <= 1)) AND
        (reply_rate IS NULL OR (reply_rate >= 0 AND reply_rate <= 1)) AND
        (conversion_rate IS NULL OR (conversion_rate >= 0 AND conversion_rate <= 1))
        """
    )


def downgrade() -> None:
    """
    Drop campaign management tables and all associated indexes and constraints.
    """
    # Drop CHECK constraints
    op.drop_constraint('ck_message_variant_analytics_rates_valid', 'message_variant_analytics', type_='check')
    op.drop_constraint('ck_message_variant_analytics_variant_number_valid', 'message_variant_analytics', type_='check')
    op.drop_constraint('ck_campaign_messages_selected_variant_valid', 'campaign_messages', type_='check')
    op.drop_constraint('ck_campaign_messages_status_valid', 'campaign_messages', type_='check')
    op.drop_constraint('ck_campaigns_qualification_score_range', 'campaigns', type_='check')
    op.drop_constraint('ck_campaigns_channel_valid', 'campaigns', type_='check')
    op.drop_constraint('ck_campaigns_status_valid', 'campaigns', type_='check')

    # Drop message_variant_analytics indexes
    op.drop_index(op.f('ix_message_variant_analytics_message_id'), table_name='message_variant_analytics')
    op.drop_index(op.f('ix_message_variant_analytics_id'), table_name='message_variant_analytics')

    # Drop campaign_messages indexes
    op.drop_index(op.f('ix_campaign_messages_status'), table_name='campaign_messages')
    op.drop_index(op.f('ix_campaign_messages_lead_id'), table_name='campaign_messages')
    op.drop_index(op.f('ix_campaign_messages_campaign_id'), table_name='campaign_messages')
    op.drop_index(op.f('ix_campaign_messages_id'), table_name='campaign_messages')

    # Drop campaigns indexes
    op.drop_index(op.f('ix_campaigns_channel'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_status'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_name'), table_name='campaigns')
    op.drop_index(op.f('ix_campaigns_id'), table_name='campaigns')

    # Drop tables in reverse order
    op.drop_table('message_variant_analytics')
    op.drop_table('campaign_messages')
    op.drop_table('campaigns')
