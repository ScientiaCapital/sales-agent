"""add_unified_api_call_tracking

Revision ID: 010_unified_tracking
Revises: 009_add_security_rbac_gdpr_audit_tables
Create Date: 2025-10-08

This migration creates the unified api_call_logs table for tracking
API calls across all LLM providers (Cerebras, OpenRouter, Ollama, Anthropic).

Tables created:
- api_call_logs: Unified tracking for all providers with cost/performance metrics

Migration also copies existing CerebrasAPICall data to preserve historical records.
The cerebras_api_calls table is kept for backward compatibility but marked as deprecated.
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '010_unified_tracking'
down_revision: Union[str, None] = '009_security_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create unified api_call_logs table and migrate existing Cerebras data.
    """
    # Create ENUM types
    provider_enum = sa.Enum(
        'cerebras', 'openrouter', 'ollama', 'anthropic', 'deepseek',
        name='providertype'
    )
    operation_enum = sa.Enum(
        'qualification', 'research', 'enrichment', 'outreach',
        'conversation', 'synthesis', 'analysis', 'other',
        name='operationtype'
    )

    provider_enum.create(op.get_bind(), checkfirst=True)
    operation_enum.create(op.get_bind(), checkfirst=True)

    # Create api_call_logs table
    op.create_table(
        'api_call_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('provider', provider_enum, nullable=False),
        sa.Column('model', sa.String(length=100), nullable=False),
        sa.Column('endpoint', sa.String(length=200), nullable=False),
        sa.Column('prompt_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completion_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('input_cost_usd', sa.Float(), nullable=True),
        sa.Column('output_cost_usd', sa.Float(), nullable=True),
        sa.Column('latency_ms', sa.Integer(), nullable=False),
        sa.Column('cache_hit', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('user_id', sa.String(length=100), nullable=True),
        sa.Column('operation_type', operation_enum, nullable=False),
        sa.Column('success', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    # Create indexes for primary key and common queries
    op.create_index(op.f('ix_api_call_logs_id'), 'api_call_logs', ['id'], unique=False)
    op.create_index(op.f('ix_api_call_logs_provider'), 'api_call_logs', ['provider'], unique=False)
    op.create_index(op.f('ix_api_call_logs_model'), 'api_call_logs', ['model'], unique=False)
    op.create_index(op.f('ix_api_call_logs_cache_hit'), 'api_call_logs', ['cache_hit'], unique=False)
    op.create_index(op.f('ix_api_call_logs_user_id'), 'api_call_logs', ['user_id'], unique=False)
    op.create_index(op.f('ix_api_call_logs_operation_type'), 'api_call_logs', ['operation_type'], unique=False)
    op.create_index(op.f('ix_api_call_logs_success'), 'api_call_logs', ['success'], unique=False)
    op.create_index(op.f('ix_api_call_logs_created_at'), 'api_call_logs', ['created_at'], unique=False)

    # Create composite indexes for time-series queries
    op.create_index('idx_provider_created', 'api_call_logs', ['provider', 'created_at'], unique=False)
    op.create_index('idx_operation_created', 'api_call_logs', ['operation_type', 'created_at'], unique=False)
    op.create_index('idx_model_created', 'api_call_logs', ['model', 'created_at'], unique=False)
    op.create_index('idx_user_created', 'api_call_logs', ['user_id', 'created_at'], unique=False)
    op.create_index('idx_success_created', 'api_call_logs', ['success', 'created_at'], unique=False)

    # Add CHECK constraints for data integrity
    op.create_check_constraint(
        'ck_api_call_logs_tokens_nonnegative',
        'api_call_logs',
        'prompt_tokens >= 0 AND completion_tokens >= 0 AND total_tokens >= 0'
    )

    op.create_check_constraint(
        'ck_api_call_logs_cost_nonnegative',
        'api_call_logs',
        'cost_usd >= 0'
    )

    op.create_check_constraint(
        'ck_api_call_logs_latency_positive',
        'api_call_logs',
        'latency_ms > 0'
    )

    # Migrate existing Cerebras API call data
    # Map old operation_type strings to new enum values
    op.execute("""
        INSERT INTO api_call_logs (
            provider,
            model,
            endpoint,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            cost_usd,
            input_cost_usd,
            output_cost_usd,
            latency_ms,
            cache_hit,
            user_id,
            operation_type,
            success,
            error_message,
            created_at
        )
        SELECT
            'cerebras'::providertype,
            model,
            endpoint,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            cost_usd,
            input_cost_usd,
            output_cost_usd,
            latency_ms,
            cache_hit,
            NULL,  -- user_id (not tracked in old model)
            CASE
                WHEN operation_type = 'lead_qualification' THEN 'qualification'::operationtype
                WHEN operation_type = 'research' THEN 'research'::operationtype
                WHEN operation_type = 'enrichment' THEN 'enrichment'::operationtype
                WHEN operation_type = 'outreach' THEN 'outreach'::operationtype
                WHEN operation_type = 'conversation' THEN 'conversation'::operationtype
                WHEN operation_type = 'synthesis' THEN 'synthesis'::operationtype
                WHEN operation_type = 'analysis' THEN 'analysis'::operationtype
                ELSE 'other'::operationtype
            END,
            success,
            error_message,
            created_at
        FROM cerebras_api_calls
    """)

    # Add comment to cerebras_api_calls table marking it as deprecated
    op.execute("""
        COMMENT ON TABLE cerebras_api_calls IS
        'DEPRECATED: Use api_call_logs for all new tracking. Kept for backward compatibility.'
    """)


def downgrade() -> None:
    """
    Drop unified api_call_logs table and restore cerebras_api_calls as primary tracker.

    WARNING: This will delete all non-Cerebras provider tracking data!
    """
    # Remove deprecation comment from cerebras_api_calls
    op.execute("""
        COMMENT ON TABLE cerebras_api_calls IS NULL
    """)

    # Drop CHECK constraints
    op.drop_constraint('ck_api_call_logs_latency_positive', 'api_call_logs', type_='check')
    op.drop_constraint('ck_api_call_logs_cost_nonnegative', 'api_call_logs', type_='check')
    op.drop_constraint('ck_api_call_logs_tokens_nonnegative', 'api_call_logs', type_='check')

    # Drop composite indexes
    op.drop_index('idx_success_created', table_name='api_call_logs')
    op.drop_index('idx_user_created', table_name='api_call_logs')
    op.drop_index('idx_model_created', table_name='api_call_logs')
    op.drop_index('idx_operation_created', table_name='api_call_logs')
    op.drop_index('idx_provider_created', table_name='api_call_logs')

    # Drop simple indexes
    op.drop_index(op.f('ix_api_call_logs_created_at'), table_name='api_call_logs')
    op.drop_index(op.f('ix_api_call_logs_success'), table_name='api_call_logs')
    op.drop_index(op.f('ix_api_call_logs_operation_type'), table_name='api_call_logs')
    op.drop_index(op.f('ix_api_call_logs_user_id'), table_name='api_call_logs')
    op.drop_index(op.f('ix_api_call_logs_cache_hit'), table_name='api_call_logs')
    op.drop_index(op.f('ix_api_call_logs_model'), table_name='api_call_logs')
    op.drop_index(op.f('ix_api_call_logs_provider'), table_name='api_call_logs')
    op.drop_index(op.f('ix_api_call_logs_id'), table_name='api_call_logs')

    # Drop table
    op.drop_table('api_call_logs')

    # Drop ENUM types
    sa.Enum(name='operationtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='providertype').drop(op.get_bind(), checkfirst=True)
