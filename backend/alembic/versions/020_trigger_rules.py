"""Add trigger rules and executions tables.

Revision ID: 020_trigger_rules
Revises: 019_call_insights
Create Date: 2025-12-27
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision: str = '020_trigger_rules'
down_revision: Union[str, None] = '019_call_insights'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create trigger_rules and trigger_executions tables."""

    # Create trigger_rules table
    op.create_table(
        'trigger_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('is_active', sa.Boolean, default=True, nullable=False),
        sa.Column('priority', sa.Integer, default=50, nullable=False),

        # Trigger definition
        sa.Column('trigger_type', sa.String(50), nullable=False),
        sa.Column('conditions', JSONB, nullable=False, server_default='[]'),

        # Actions to execute
        sa.Column('actions', JSONB, nullable=False, server_default='[]'),

        # Execution stats
        sa.Column('times_triggered', sa.Integer, default=0, nullable=False),
        sa.Column('last_triggered_at', sa.DateTime(timezone=True), nullable=True),

        # Metadata
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),

        # Constraints
        sa.CheckConstraint("priority >= 0 AND priority <= 100",
                          name='ck_trigger_rules_priority_range'),
        sa.CheckConstraint(
            "trigger_type IN ('call_insight', 'email_reply', 'signal', 'lead_update', 'deal_update')",
            name='ck_trigger_rules_valid_trigger_type'
        ),
    )

    # Create indexes
    op.create_index('ix_trigger_rules_is_active', 'trigger_rules', ['is_active'])
    op.create_index('ix_trigger_rules_trigger_type', 'trigger_rules', ['trigger_type'])
    op.create_index('ix_trigger_rules_priority', 'trigger_rules', ['priority', 'is_active'])

    # Create trigger_executions table
    op.create_table(
        'trigger_executions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text('gen_random_uuid()')),
        sa.Column('rule_id', UUID(as_uuid=True),
                  sa.ForeignKey('trigger_rules.id', ondelete='CASCADE'),
                  nullable=False),

        # Execution context
        sa.Column('trigger_data', JSONB, nullable=True),
        sa.Column('matched_conditions', JSONB, nullable=True),
        sa.Column('entity_type', sa.String(50), nullable=True),  # lead, deal, call, etc.
        sa.Column('entity_id', sa.String(255), nullable=True),   # ID of the entity

        # Actions executed
        sa.Column('actions_executed', JSONB, nullable=True),
        sa.Column('action_results', JSONB, nullable=True),

        # Status
        sa.Column('success', sa.Boolean, nullable=False),
        sa.Column('error_message', sa.Text, nullable=True),

        # Timing
        sa.Column('executed_at', sa.DateTime(timezone=True),
                  server_default=sa.text('NOW()'), nullable=False),
        sa.Column('duration_ms', sa.Integer, nullable=True),
    )

    # Create indexes for trigger_executions
    op.create_index('ix_trigger_executions_rule_id', 'trigger_executions', ['rule_id'])
    op.create_index('ix_trigger_executions_executed_at', 'trigger_executions', ['executed_at'])
    op.create_index('ix_trigger_executions_entity', 'trigger_executions',
                   ['entity_type', 'entity_id'])
    op.create_index('ix_trigger_executions_success', 'trigger_executions', ['success'])

    # Add comment
    op.execute("""
        COMMENT ON TABLE trigger_rules IS
        'Automation rules: signal → condition → action pipeline for automated workflows'
    """)
    op.execute("""
        COMMENT ON TABLE trigger_executions IS
        'Audit log of trigger rule executions with results and timing'
    """)


def downgrade() -> None:
    """Drop trigger tables."""
    op.drop_table('trigger_executions')
    op.drop_table('trigger_rules')
