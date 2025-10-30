"""
Add indexes to leads table for performance

Revision ID: 20251030_lead_indexes
Revises: 
Create Date: 2025-10-30
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20251030_lead_indexes'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create indexes if they don't already exist
    op.create_index('idx_leads_created_at', 'leads', ['created_at'], unique=False)
    op.create_index('idx_leads_updated_at', 'leads', ['updated_at'], unique=False)
    op.create_index('idx_leads_qualified_at', 'leads', ['qualified_at'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index('idx_leads_qualified_at', table_name='leads')
    op.drop_index('idx_leads_updated_at', table_name='leads')
    op.drop_index('idx_leads_created_at', table_name='leads')
