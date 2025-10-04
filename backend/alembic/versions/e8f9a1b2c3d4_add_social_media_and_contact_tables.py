"""add_social_media_and_contact_tables

Revision ID: e8f9a1b2c3d4
Revises: af36f48fb48c
Create Date: 2025-10-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'e8f9a1b2c3d4'
down_revision: Union[str, None] = 'af36f48fb48c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create social_media_activity table
    op.create_table('social_media_activity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False),
        sa.Column('platform_post_id', sa.String(length=255), nullable=True),
        sa.Column('post_url', sa.String(length=1000), nullable=True),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('text_content', sa.Text(), nullable=True),
        sa.Column('author_username', sa.String(length=255), nullable=True),
        sa.Column('author_name', sa.String(length=255), nullable=True),
        sa.Column('likes_count', sa.Integer(), nullable=True),
        sa.Column('retweets_count', sa.Integer(), nullable=True),
        sa.Column('comments_count', sa.Integer(), nullable=True),
        sa.Column('shares_count', sa.Integer(), nullable=True),
        sa.Column('upvotes_count', sa.Integer(), nullable=True),
        sa.Column('engagement_score', sa.Float(), nullable=True),
        sa.Column('sentiment', sa.String(length=20), nullable=True),
        sa.Column('sentiment_score', sa.Float(), nullable=True),
        sa.Column('sentiment_reasoning', sa.Text(), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('additional_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_social_media_activity_company_name'), 'social_media_activity', ['company_name'], unique=False)
    op.create_index(op.f('ix_social_media_activity_id'), 'social_media_activity', ['id'], unique=False)
    op.create_index(op.f('ix_social_media_activity_platform'), 'social_media_activity', ['platform'], unique=False)
    op.create_index(op.f('ix_social_media_activity_platform_post_id'), 'social_media_activity', ['platform_post_id'], unique=True)

    # Create contact_social_profiles table
    op.create_table('contact_social_profiles',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_name', sa.String(length=255), nullable=False),
        sa.Column('contact_email', sa.String(length=255), nullable=True),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('job_title', sa.String(length=255), nullable=True),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('linkedin_headline', sa.String(length=500), nullable=True),
        sa.Column('linkedin_location', sa.String(length=255), nullable=True),
        sa.Column('linkedin_connections', sa.String(length=50), nullable=True),
        sa.Column('current_company', sa.String(length=255), nullable=True),
        sa.Column('current_title', sa.String(length=255), nullable=True),
        sa.Column('tenure', sa.String(length=100), nullable=True),
        sa.Column('decision_maker_score', sa.Integer(), nullable=True),
        sa.Column('contact_priority', sa.String(length=20), nullable=True),
        sa.Column('is_c_level', sa.Boolean(), nullable=True),
        sa.Column('is_vp_level', sa.Boolean(), nullable=True),
        sa.Column('twitter_url', sa.String(length=500), nullable=True),
        sa.Column('twitter_username', sa.String(length=100), nullable=True),
        sa.Column('facebook_url', sa.String(length=500), nullable=True),
        sa.Column('instagram_url', sa.String(length=500), nullable=True),
        sa.Column('experience_years', sa.Integer(), nullable=True),
        sa.Column('skills', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('education', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('work_history', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('last_activity_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('engagement_frequency', sa.String(length=50), nullable=True),
        sa.Column('topics_discussed', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('scraped_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('scraping_method', sa.String(length=100), nullable=True),
        sa.Column('data_quality_score', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_contact_social_profiles_company_name'), 'contact_social_profiles', ['company_name'], unique=False)
    op.create_index(op.f('ix_contact_social_profiles_contact_email'), 'contact_social_profiles', ['contact_email'], unique=False)
    op.create_index(op.f('ix_contact_social_profiles_contact_name'), 'contact_social_profiles', ['contact_name'], unique=False)
    op.create_index(op.f('ix_contact_social_profiles_id'), 'contact_social_profiles', ['id'], unique=False)
    op.create_index(op.f('ix_contact_social_profiles_linkedin_url'), 'contact_social_profiles', ['linkedin_url'], unique=True)

    # Create organization_charts table
    op.create_table('organization_charts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('company_linkedin_url', sa.String(length=500), nullable=True),
        sa.Column('lead_id', sa.Integer(), nullable=True),
        sa.Column('hierarchy_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('total_employees_analyzed', sa.Integer(), nullable=True),
        sa.Column('key_decision_makers_count', sa.Integer(), nullable=True),
        sa.Column('c_level_contacts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('vp_level_contacts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('director_level_contacts', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('reporting_relationships', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('team_structures', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('chart_depth', sa.Integer(), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_organization_charts_company_linkedin_url'), 'organization_charts', ['company_linkedin_url'], unique=True)
    op.create_index(op.f('ix_organization_charts_company_name'), 'organization_charts', ['company_name'], unique=False)
    op.create_index(op.f('ix_organization_charts_id'), 'organization_charts', ['id'], unique=False)


def downgrade() -> None:
    # Drop organization_charts table
    op.drop_index(op.f('ix_organization_charts_id'), table_name='organization_charts')
    op.drop_index(op.f('ix_organization_charts_company_name'), table_name='organization_charts')
    op.drop_index(op.f('ix_organization_charts_company_linkedin_url'), table_name='organization_charts')
    op.drop_table('organization_charts')

    # Drop contact_social_profiles table
    op.drop_index(op.f('ix_contact_social_profiles_linkedin_url'), table_name='contact_social_profiles')
    op.drop_index(op.f('ix_contact_social_profiles_id'), table_name='contact_social_profiles')
    op.drop_index(op.f('ix_contact_social_profiles_contact_name'), table_name='contact_social_profiles')
    op.drop_index(op.f('ix_contact_social_profiles_contact_email'), table_name='contact_social_profiles')
    op.drop_index(op.f('ix_contact_social_profiles_company_name'), table_name='contact_social_profiles')
    op.drop_table('contact_social_profiles')

    # Drop social_media_activity table
    op.drop_index(op.f('ix_social_media_activity_platform_post_id'), table_name='social_media_activity')
    op.drop_index(op.f('ix_social_media_activity_platform'), table_name='social_media_activity')
    op.drop_index(op.f('ix_social_media_activity_id'), table_name='social_media_activity')
    op.drop_index(op.f('ix_social_media_activity_company_name'), table_name='social_media_activity')
    op.drop_table('social_media_activity')
