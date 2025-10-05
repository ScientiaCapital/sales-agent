"""add_performance_indexes_and_constraints

Revision ID: 005
Revises: 004
Create Date: 2025-10-04

This migration adds database indexes for query performance optimization
and CHECK constraints for data integrity enforcement.

Indexes added:
- leads.industry (for segmentation queries)
- leads.created_at (for time-based filtering, already exists but ensuring consistency)

CHECK constraints added:
- leads.qualification_score must be between 0 and 100
- Valid email format validation (basic check)

Note: Some indexes may already exist from model definitions (index=True).
This migration ensures they are explicitly managed in the schema.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_performance_indexes'
down_revision: Union[str, None] = 'af36f48fb48c'  # Current database state
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add performance indexes and data integrity constraints to leads and api_calls tables.
    """

    # Add indexes to leads table for common query patterns
    # Note: Some columns like id, company_name, contact_email, qualification_score
    # already have indexes from model definitions (index=True in Column)

    # Index for industry-based segmentation queries
    op.create_index(
        op.f('ix_leads_industry'),
        'leads',
        ['industry'],
        unique=False
    )

    # Ensure created_at has an index for time-range queries
    # This might already exist, but we'll create it if it doesn't
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_created_at
        ON leads (created_at DESC)
    """)

    # Add CHECK constraints to leads table for data integrity

    # Qualification score must be between 0 and 100
    op.create_check_constraint(
        'ck_leads_qualification_score_range',
        'leads',
        'qualification_score IS NULL OR (qualification_score >= 0 AND qualification_score <= 100)'
    )

    # Email format validation (basic check for @ symbol)
    op.create_check_constraint(
        'ck_leads_contact_email_format',
        'leads',
        "contact_email IS NULL OR contact_email ~ '^[^@]+@[^@]+\\.[^@]+$'"
    )

    # Company website should start with http:// or https:// if provided
    op.create_check_constraint(
        'ck_leads_company_website_format',
        'leads',
        "company_website IS NULL OR company_website ~ '^https?://'"
    )

    # Latency must be non-negative if provided
    op.create_check_constraint(
        'ck_leads_qualification_latency_positive',
        'leads',
        'qualification_latency_ms IS NULL OR qualification_latency_ms >= 0'
    )

    # Add CHECK constraints to cerebras_api_calls table

    # Token counts must be positive
    op.create_check_constraint(
        'ck_cerebras_api_calls_tokens_positive',
        'cerebras_api_calls',
        'prompt_tokens > 0 AND completion_tokens > 0 AND total_tokens > 0'
    )

    # Total tokens should equal sum of prompt and completion tokens
    op.create_check_constraint(
        'ck_cerebras_api_calls_total_tokens',
        'cerebras_api_calls',
        'total_tokens = prompt_tokens + completion_tokens'
    )

    # Latency must be positive
    op.create_check_constraint(
        'ck_cerebras_api_calls_latency_positive',
        'cerebras_api_calls',
        'latency_ms > 0'
    )

    # Cost must be non-negative
    op.create_check_constraint(
        'ck_cerebras_api_calls_cost_positive',
        'cerebras_api_calls',
        'cost_usd >= 0'
    )


def downgrade() -> None:
    """
    Remove performance indexes and constraints added in upgrade.
    """

    # Drop CHECK constraints from cerebras_api_calls
    op.drop_constraint('ck_cerebras_api_calls_cost_positive', 'cerebras_api_calls', type_='check')
    op.drop_constraint('ck_cerebras_api_calls_latency_positive', 'cerebras_api_calls', type_='check')
    op.drop_constraint('ck_cerebras_api_calls_total_tokens', 'cerebras_api_calls', type_='check')
    op.drop_constraint('ck_cerebras_api_calls_tokens_positive', 'cerebras_api_calls', type_='check')

    # Drop CHECK constraints from leads
    op.drop_constraint('ck_leads_qualification_latency_positive', 'leads', type_='check')
    op.drop_constraint('ck_leads_company_website_format', 'leads', type_='check')
    op.drop_constraint('ck_leads_contact_email_format', 'leads', type_='check')
    op.drop_constraint('ck_leads_qualification_score_range', 'leads', type_='check')

    # Drop indexes from leads
    op.execute('DROP INDEX IF EXISTS ix_leads_created_at')
    op.drop_index(op.f('ix_leads_industry'), table_name='leads')
