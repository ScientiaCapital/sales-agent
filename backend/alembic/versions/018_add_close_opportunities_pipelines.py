"""Add Close CRM opportunities and pipelines tables

Revision ID: 018_close_opportunities_pipelines
Revises: 017_cold_reach_tables
Create Date: 2025-12-26

This migration adds database models for Close CRM pipeline and opportunity tracking.
Part of Phase 1: Pipeline Models for the Close CRM Enhancements project.

New Tables:
- crm_opportunities: Tracks deals through sales stages with Close lead references
- crm_pipelines: Stores pipeline configurations and stage definitions

Indexes:
- Optimized for opportunity queries by stage, expected close date, and sync status
- Pipeline queries by active status and name
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '018_close_opportunities_pipelines'
down_revision: Union[str, None] = '017_cold_reach_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create crm_opportunities and crm_pipelines tables with indexes"""

    # Create crm_opportunities table
    op.create_table(
        'crm_opportunities',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False, server_default='close'),
        sa.Column('close_lead_id', sa.String(length=255), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=3), nullable=False, server_default='USD'),
        sa.Column('stage', sa.String(length=50), nullable=False),
        sa.Column('probability', sa.Float(), nullable=True),
        sa.Column('expected_close_date', sa.DateTime(), nullable=True),
        sa.Column('actual_close_date', sa.DateTime(), nullable=True),
        sa.Column('owner_id', sa.String(length=255), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(), nullable=True),
        sa.Column('sync_status', sa.String(length=50), nullable=False, server_default='active'),
        sa.Column('raw_data', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['contact_id'], ['crm_contacts.id'], ondelete='SET NULL'),
        sa.UniqueConstraint('external_id', name='uq_crm_opportunities_external_id')
    )

    # Create indexes for crm_opportunities
    op.create_index(op.f('ix_crm_opportunities_id'), 'crm_opportunities', ['id'], unique=False)
    op.create_index(op.f('ix_crm_opportunities_external_id'), 'crm_opportunities', ['external_id'], unique=True)
    op.create_index(op.f('ix_crm_opportunities_close_lead_id'), 'crm_opportunities', ['close_lead_id'], unique=False)
    op.create_index(op.f('ix_crm_opportunities_contact_id'), 'crm_opportunities', ['contact_id'], unique=False)
    op.create_index('idx_opp_external_id', 'crm_opportunities', ['external_id'], unique=True)
    op.create_index('idx_opp_close_lead_id', 'crm_opportunities', ['close_lead_id'], unique=False)
    op.create_index('idx_opp_stage_expected_close', 'crm_opportunities', ['stage', 'expected_close_date'], unique=False)
    op.create_index('idx_opp_sync_status', 'crm_opportunities', ['sync_status'], unique=False)

    # Create crm_pipelines table
    op.create_table(
        'crm_pipelines',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('platform', sa.String(length=50), nullable=False, server_default='close'),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('stages_json', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('external_id', name='uq_crm_pipelines_external_id')
    )

    # Create indexes for crm_pipelines
    op.create_index(op.f('ix_crm_pipelines_id'), 'crm_pipelines', ['id'], unique=False)
    op.create_index(op.f('ix_crm_pipelines_external_id'), 'crm_pipelines', ['external_id'], unique=True)
    op.create_index(op.f('ix_crm_pipelines_is_active'), 'crm_pipelines', ['is_active'], unique=False)
    op.create_index('idx_pipeline_external_id', 'crm_pipelines', ['external_id'], unique=True)
    op.create_index('idx_pipeline_active', 'crm_pipelines', ['is_active'], unique=False)
    op.create_index('idx_pipeline_name', 'crm_pipelines', ['name'], unique=False)


def downgrade() -> None:
    """Drop crm_opportunities and crm_pipelines tables"""

    # Drop indexes for crm_pipelines
    op.drop_index('idx_pipeline_name', table_name='crm_pipelines')
    op.drop_index('idx_pipeline_active', table_name='crm_pipelines')
    op.drop_index('idx_pipeline_external_id', table_name='crm_pipelines')
    op.drop_index(op.f('ix_crm_pipelines_is_active'), table_name='crm_pipelines')
    op.drop_index(op.f('ix_crm_pipelines_external_id'), table_name='crm_pipelines')
    op.drop_index(op.f('ix_crm_pipelines_id'), table_name='crm_pipelines')

    # Drop crm_pipelines table
    op.drop_table('crm_pipelines')

    # Drop indexes for crm_opportunities
    op.drop_index('idx_opp_sync_status', table_name='crm_opportunities')
    op.drop_index('idx_opp_stage_expected_close', table_name='crm_opportunities')
    op.drop_index('idx_opp_close_lead_id', table_name='crm_opportunities')
    op.drop_index('idx_opp_external_id', table_name='crm_opportunities')
    op.drop_index(op.f('ix_crm_opportunities_contact_id'), table_name='crm_opportunities')
    op.drop_index(op.f('ix_crm_opportunities_close_lead_id'), table_name='crm_opportunities')
    op.drop_index(op.f('ix_crm_opportunities_external_id'), table_name='crm_opportunities')
    op.drop_index(op.f('ix_crm_opportunities_id'), table_name='crm_opportunities')

    # Drop crm_opportunities table
    op.drop_table('crm_opportunities')
