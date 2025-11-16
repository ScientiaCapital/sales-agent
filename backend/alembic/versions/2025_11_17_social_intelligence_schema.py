"""Add social intelligence schema

Revision ID: 2025_11_17_social
Revises:
Create Date: 2025-11-17 10:00:00.000000

Tables:
- social_posts: LinkedIn/Twitter posts with AI analysis
- contact_monitoring: Contact monitoring status
- email_drafts: Email drafts created by AI
- email_engagement: Email open/click tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2025_11_17_social'
down_revision = None  # Update this to latest migration if others exist
branch_labels = None
depends_on = None


def upgrade():
    # Create social_posts table
    op.create_table(
        'social_posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.String(255), nullable=False),
        sa.Column('platform', sa.String(50), nullable=False),  # 'linkedin' or 'twitter'
        sa.Column('post_text', sa.Text(), nullable=True),
        sa.Column('post_url', sa.String(500), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('ai_analysis', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('quality_score', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_social_posts_contact', 'social_posts', ['contact_id'])
    op.create_index('idx_social_posts_scraped', 'social_posts', ['scraped_at'], postgresql_using='btree')
    op.create_index('idx_social_posts_platform', 'social_posts', ['platform'])

    # Create contact_monitoring table
    op.create_table(
        'contact_monitoring',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('close_contact_id', sa.String(255), nullable=False),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        sa.Column('twitter_handle', sa.String(100), nullable=True),
        sa.Column('last_linkedin_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_twitter_check', sa.DateTime(timezone=True), nullable=True),
        sa.Column('monitoring_enabled', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('total_posts_found', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('close_contact_id')
    )
    op.create_index('idx_contact_monitoring_enabled', 'contact_monitoring', ['monitoring_enabled'])

    # Create email_drafts table
    op.create_table(
        'email_drafts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('close_lead_id', sa.String(255), nullable=False),
        sa.Column('close_contact_id', sa.String(255), nullable=False),
        sa.Column('close_activity_id', sa.String(255), nullable=True),  # ID from Close CRM API
        sa.Column('subject', sa.String(500), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('research_context', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('opens_count', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_email_drafts_lead', 'email_drafts', ['close_lead_id'])
    op.create_index('idx_email_drafts_contact', 'email_drafts', ['close_contact_id'])
    op.create_index('idx_email_drafts_opens', 'email_drafts', ['opens_count'], postgresql_using='btree')
    op.create_index('idx_email_drafts_created', 'email_drafts', ['created_at'], postgresql_using='btree')

    # Create email_engagement table
    op.create_table(
        'email_engagement',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_draft_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),  # 'open', 'click', 'reply'
        sa.Column('event_timestamp', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['email_draft_id'], ['email_drafts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_email_engagement_draft', 'email_engagement', ['email_draft_id'])
    op.create_index('idx_email_engagement_timestamp', 'email_engagement', ['event_timestamp'], postgresql_using='btree')
    op.create_index('idx_email_engagement_type', 'email_engagement', ['event_type'])


def downgrade():
    op.drop_table('email_engagement')
    op.drop_table('email_drafts')
    op.drop_table('contact_monitoring')
    op.drop_table('social_posts')
