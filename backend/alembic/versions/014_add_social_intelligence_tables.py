"""Add social intelligence tables (email_engagement with CHECK constraint)

Revision ID: 014_social_intelligence
Revises: 2ebd5747346c
Create Date: 2025-11-16 12:00:00.000000

Adds tables for social intelligence pipeline:
- email_drafts: Email drafts created by AI
- email_engagement: Email engagement tracking with CHECK constraint on event_type
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '014_social_intelligence'
down_revision = '2ebd5747346c'  # References latest migration (CSV imports)
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create social intelligence tables with proper constraints"""
    
    # Create email_drafts table
    op.create_table(
        'email_drafts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('close_lead_id', sa.String(length=255), nullable=False),
        sa.Column('close_contact_id', sa.String(length=255), nullable=False),
        sa.Column('close_activity_id', sa.String(length=255), nullable=True),
        sa.Column('subject', sa.String(length=500), nullable=True),
        sa.Column('body_html', sa.Text(), nullable=True),
        sa.Column('research_context', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('opens_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_opened_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for email_drafts
    op.create_index('idx_email_drafts_lead', 'email_drafts', ['close_lead_id'])
    op.create_index('idx_email_drafts_contact', 'email_drafts', ['close_contact_id'])
    op.create_index('idx_email_drafts_opens', 'email_drafts', ['opens_count'], postgresql_ops={'opens_count': 'DESC'})
    op.create_index('idx_email_drafts_created', 'email_drafts', ['created_at'], postgresql_ops={'created_at': 'DESC'})
    op.create_index('idx_email_drafts_sent', 'email_drafts', ['sent_at'], postgresql_ops={'sent_at': 'DESC'})
    
    # Create email_engagement table WITH CHECK constraint on event_type
    op.create_table(
        'email_engagement',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email_draft_id', sa.Integer(), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('event_timestamp', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['email_draft_id'], ['email_drafts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        # CRITICAL: Add CHECK constraint to match SQL schema
        sa.CheckConstraint(
            "event_type IN ('open', 'click', 'reply', 'high_intent_detected')",
            name='check_email_engagement_event_type'
        )
    )
    
    # Create indexes for email_engagement
    op.create_index('idx_email_engagement_draft', 'email_engagement', ['email_draft_id'])
    op.create_index('idx_email_engagement_timestamp', 'email_engagement', ['event_timestamp'], postgresql_ops={'event_timestamp': 'DESC'})
    op.create_index('idx_email_engagement_type', 'email_engagement', ['event_type'])


def downgrade() -> None:
    """Remove social intelligence tables"""
    
    # Drop indexes
    op.drop_index('idx_email_engagement_type', table_name='email_engagement')
    op.drop_index('idx_email_engagement_timestamp', table_name='email_engagement')
    op.drop_index('idx_email_engagement_draft', table_name='email_engagement')
    
    op.drop_index('idx_email_drafts_sent', table_name='email_drafts')
    op.drop_index('idx_email_drafts_created', table_name='email_drafts')
    op.drop_index('idx_email_drafts_opens', table_name='email_drafts')
    op.drop_index('idx_email_drafts_contact', table_name='email_drafts')
    op.drop_index('idx_email_drafts_lead', table_name='email_drafts')
    
    # Drop tables (CASCADE will handle foreign key)
    op.drop_table('email_engagement')
    op.drop_table('email_drafts')

