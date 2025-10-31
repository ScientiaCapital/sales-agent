"""add report_templates table

Revision ID: add_report_templates
Revises: add_analytics_tables
Create Date: 2025-10-30 10:30:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'add_report_templates'
down_revision = '20251030_add_analytics'  # After analytics tables migration
branch_labels = None
depends_on = None


def upgrade():
    """Create report_templates table"""
    op.create_table(
        'report_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('template_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('report_type', sa.String(length=50), nullable=False),
        sa.Column('query_config', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('visualization_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('filter_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('is_system_template', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_by', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('usage_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('template_id')
    )

    # Create indexes for better query performance
    op.create_index(op.f('ix_report_templates_id'), 'report_templates', ['id'], unique=False)
    op.create_index(op.f('ix_report_templates_template_id'), 'report_templates', ['template_id'], unique=True)
    op.create_index(op.f('ix_report_templates_report_type'), 'report_templates', ['report_type'], unique=False)
    op.create_index(op.f('ix_report_templates_is_system_template'), 'report_templates', ['is_system_template'], unique=False)


def downgrade():
    """Drop report_templates table"""
    op.drop_index(op.f('ix_report_templates_is_system_template'), table_name='report_templates')
    op.drop_index(op.f('ix_report_templates_report_type'), table_name='report_templates')
    op.drop_index(op.f('ix_report_templates_template_id'), table_name='report_templates')
    op.drop_index(op.f('ix_report_templates_id'), table_name='report_templates')
    op.drop_table('report_templates')
