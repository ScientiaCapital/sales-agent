"""Add workflow_rules table for automation

Revision ID: 019_workflow_rules
Revises: 018_close_opportunities_pipelines
Create Date: 2025-12-26

This migration adds the workflow_rules table for declarative workflow automation.
Part of Phase 4: Workflow Automation for the Close CRM Enhancements project.

New Table:
- workflow_rules: Stores automation rules with triggers and actions

Trigger Types:
- stage_change: Fires when opportunity stage changes
- lead_created: Fires when a new lead is created
- opportunity_won: Fires when an opportunity is marked as won
- opportunity_lost: Fires when an opportunity is marked as lost
- days_in_stage: Fires when a deal stays in a stage for N days
- icp_tier_change: Fires when ICP tier is updated

Action Types:
- create_task: Create a follow-up task in Close
- send_alert: Send an in-app alert
- send_slack: Send a Slack notification
- trigger_agent: Trigger an AI agent workflow
- update_field: Update a field on the lead/opportunity

Indexes:
- trigger_type: For filtering rules by trigger
- is_active: For filtering active rules only
- priority: For ordering rule execution
- Composite: is_active + trigger_type for common query pattern
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '019_workflow_rules'
down_revision: Union[str, None] = '018_close_opportunities_pipelines'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create workflow_rules table with indexes"""

    # Create workflow_rules table
    op.create_table(
        'workflow_rules',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),

        # Trigger configuration
        sa.Column('trigger_type', sa.String(length=50), nullable=False),
        sa.Column('trigger_conditions', sa.JSON(), nullable=False),

        # Action configuration
        sa.Column('action_type', sa.String(length=50), nullable=False),
        sa.Column('action_config', sa.JSON(), nullable=False),

        # Rule control
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),

        # Timestamps
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('NOW()')),

        # Audit
        sa.Column('created_by', sa.String(length=255), nullable=True),

        # Execution tracking
        sa.Column('execution_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_executed_at', sa.DateTime(), nullable=True),

        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for workflow_rules
    op.create_index(op.f('ix_workflow_rules_id'), 'workflow_rules', ['id'], unique=False)
    op.create_index('idx_workflow_rules_trigger_type', 'workflow_rules', ['trigger_type'], unique=False)
    op.create_index('idx_workflow_rules_is_active', 'workflow_rules', ['is_active'], unique=False)
    op.create_index('idx_workflow_rules_priority', 'workflow_rules', ['priority'], unique=False)
    op.create_index('idx_workflow_rules_active_trigger', 'workflow_rules', ['is_active', 'trigger_type'], unique=False)


def downgrade() -> None:
    """Drop workflow_rules table"""

    # Drop indexes
    op.drop_index('idx_workflow_rules_active_trigger', table_name='workflow_rules')
    op.drop_index('idx_workflow_rules_priority', table_name='workflow_rules')
    op.drop_index('idx_workflow_rules_is_active', table_name='workflow_rules')
    op.drop_index('idx_workflow_rules_trigger_type', table_name='workflow_rules')
    op.drop_index(op.f('ix_workflow_rules_id'), table_name='workflow_rules')

    # Drop table
    op.drop_table('workflow_rules')
