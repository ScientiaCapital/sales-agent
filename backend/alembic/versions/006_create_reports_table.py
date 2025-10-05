"""create_reports_table

Revision ID: 006_reports_table
Revises: 005_performance_indexes
Create Date: 2025-10-04

This migration creates the reports table for storing AI-generated
company research reports from the multi-agent pipeline.

Tables created:
- reports: Stores report content (markdown/HTML) and structured data
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '006_reports_table'
down_revision: Union[str, None] = '005_performance_indexes'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create reports table with JSON columns for structured agent data.
    """
    op.create_table(
        'reports',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('lead_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='generating'),
        sa.Column('content_markdown', sa.Text(), nullable=True),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('research_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('insights_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=True),
        sa.Column('generation_time_ms', sa.Integer(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['lead_id'], ['leads.id'], ondelete='CASCADE'),
    )
    
    # Create indexes for common query patterns
    op.create_index(op.f('ix_reports_id'), 'reports', ['id'], unique=False)
    op.create_index(op.f('ix_reports_lead_id'), 'reports', ['lead_id'], unique=False)
    op.create_index(op.f('ix_reports_status'), 'reports', ['status'], unique=False)
    op.create_index(op.f('ix_reports_created_at'), 'reports', ['created_at'], unique=False)
    
    # Add CHECK constraints for data integrity
    op.create_check_constraint(
        'ck_reports_status_valid',
        'reports',
        "status IN ('generating', 'completed', 'failed')"
    )
    
    op.create_check_constraint(
        'ck_reports_confidence_score_range',
        'reports',
        'confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)'
    )
    
    op.create_check_constraint(
        'ck_reports_generation_time_positive',
        'reports',
        'generation_time_ms IS NULL OR generation_time_ms >= 0'
    )


def downgrade() -> None:
    """
    Drop reports table and all associated indexes and constraints.
    """
    # Drop CHECK constraints
    op.drop_constraint('ck_reports_generation_time_positive', 'reports', type_='check')
    op.drop_constraint('ck_reports_confidence_score_range', 'reports', type_='check')
    op.drop_constraint('ck_reports_status_valid', 'reports', type_='check')
    
    # Drop indexes
    op.drop_index(op.f('ix_reports_created_at'), table_name='reports')
    op.drop_index(op.f('ix_reports_status'), table_name='reports')
    op.drop_index(op.f('ix_reports_lead_id'), table_name='reports')
    op.drop_index(op.f('ix_reports_id'), table_name='reports')
    
    # Drop table
    op.drop_table('reports')
