"""Add agent_conversations table for session archive

Revision ID: 88c41a4ae582
Revises: ebf714f5f7b9
Create Date: 2025-11-01 12:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '88c41a4ae582'
down_revision: Union[str, None] = 'ebf714f5f7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create agent_conversations table
    op.create_table(
        'agent_conversations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('user_id', sa.String(length=255), nullable=False),
        sa.Column('agent_type', sa.String(length=50), nullable=False),
        sa.Column('messages', sa.JSON(), nullable=False),
        sa.Column('tool_results', sa.JSON(), nullable=True),
        sa.Column('message_count', sa.Integer(), nullable=True),
        sa.Column('tool_call_count', sa.Integer(), nullable=True),
        sa.Column('total_cost_usd', sa.DECIMAL(precision=10, scale=6), nullable=True),
        sa.Column('avg_response_time_ms', sa.Integer(), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('archived_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('extra_metadata', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes
    op.create_index('idx_user_agent', 'agent_conversations', ['user_id', 'agent_type'], unique=False)
    op.create_index('idx_started_at', 'agent_conversations', ['started_at'], unique=False)
    op.create_index('idx_archived_at', 'agent_conversations', ['archived_at'], unique=False)
    op.create_index(op.f('ix_agent_conversations_session_id'), 'agent_conversations', ['session_id'], unique=True)
    op.create_index(op.f('ix_agent_conversations_user_id'), 'agent_conversations', ['user_id'], unique=False)
    op.create_index(op.f('ix_agent_conversations_agent_type'), 'agent_conversations', ['agent_type'], unique=False)


def downgrade() -> None:
    # Drop indexes
    op.drop_index(op.f('ix_agent_conversations_agent_type'), table_name='agent_conversations')
    op.drop_index(op.f('ix_agent_conversations_user_id'), table_name='agent_conversations')
    op.drop_index(op.f('ix_agent_conversations_session_id'), table_name='agent_conversations')
    op.drop_index('idx_archived_at', table_name='agent_conversations')
    op.drop_index('idx_started_at', table_name='agent_conversations')
    op.drop_index('idx_user_agent', table_name='agent_conversations')

    # Drop table
    op.drop_table('agent_conversations')
