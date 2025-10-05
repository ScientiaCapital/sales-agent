"""add_comprehensive_database_indexes

Revision ID: 007
Revises: 006
Create Date: 2025-10-04

This migration adds comprehensive database indexes for optimal query performance
across all models, focusing on:
1. Foreign key columns (PostgreSQL does NOT auto-index FKs)
2. Frequently queried columns (status, timestamps, scores)
3. Composite indexes for common multi-column queries

Performance Impact:
- Improves query performance for filtered/sorted queries
- Minimal write overhead (<5%) for B-tree indexes
- Significant read performance gains (10-100x for large tables)

Index Strategy:
- Single-column indexes: For simple WHERE/ORDER BY queries
- Composite indexes: For multi-column queries (column order matters!)
- Foreign keys: MUST be explicitly indexed for join performance
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_comprehensive_indexes'
down_revision: Union[str, None] = '006_create_reports_table'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add comprehensive indexes for query performance optimization.

    Priority Levels:
    - HIGH: Foreign keys, frequently filtered columns
    - MEDIUM: Timestamp columns, score/priority fields
    - LOW: Composite indexes for advanced query patterns
    """

    # ============================================================================
    # HIGH PRIORITY: Foreign Key Indexes
    # PostgreSQL does NOT automatically index foreign keys!
    # ============================================================================

    # social_media_activity foreign key indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_social_media_activity_lead_id
        ON social_media_activity (lead_id)
    """)

    # contact_social_profiles foreign key indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contact_social_profiles_lead_id
        ON contact_social_profiles (lead_id)
    """)

    # organization_charts foreign key indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_organization_charts_lead_id
        ON organization_charts (lead_id)
    """)

    # ============================================================================
    # MEDIUM PRIORITY: Timestamp and Status Columns
    # For time-range queries and status filtering
    # ============================================================================

    # leads table - timestamp indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_qualified_at
        ON leads (qualified_at DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_updated_at
        ON leads (updated_at DESC)
    """)

    # agent_executions - timestamp indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_agent_executions_started_at
        ON agent_executions (started_at DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_agent_executions_completed_at
        ON agent_executions (completed_at DESC)
    """)

    # social_media_activity - timestamp indexes
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_social_media_activity_posted_at
        ON social_media_activity (posted_at DESC)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_social_media_activity_scraped_at
        ON social_media_activity (scraped_at DESC)
    """)

    # social_media_activity - sentiment index for filtering
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_social_media_activity_sentiment
        ON social_media_activity (sentiment)
    """)

    # contact_social_profiles - decision maker score index
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contact_social_profiles_decision_maker_score
        ON contact_social_profiles (decision_maker_score DESC)
    """)

    # contact_social_profiles - contact priority index
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contact_social_profiles_contact_priority
        ON contact_social_profiles (contact_priority)
    """)

    # voice_session_logs - completed_at index
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_voice_session_logs_completed_at
        ON voice_session_logs (completed_at DESC)
    """)

    # ============================================================================
    # LOW PRIORITY: Composite Indexes for Advanced Query Patterns
    # Column order is critical: most selective column first
    # ============================================================================

    # leads - sorted qualified leads (score DESC, created_at DESC)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_leads_score_created
        ON leads (qualification_score DESC, created_at DESC)
        WHERE qualification_score IS NOT NULL
    """)

    # agent_executions - active executions by time (status, created_at)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_agent_executions_status_created
        ON agent_executions (status, created_at DESC)
    """)

    # agent_executions - lead execution status (lead_id, status)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_agent_executions_lead_status
        ON agent_executions (lead_id, status)
    """)

    # social_media_activity - platform timeline (platform, posted_at)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_social_media_activity_platform_posted
        ON social_media_activity (platform, posted_at DESC)
    """)

    # contact_social_profiles - top contacts per company (company_name, score)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_contact_profiles_company_score
        ON contact_social_profiles (company_name, decision_maker_score DESC)
    """)

    # voice_session_logs - active sessions by status and time
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_voice_sessions_status_created
        ON voice_session_logs (status, created_at DESC)
    """)


def downgrade() -> None:
    """
    Remove all indexes added in this migration.
    """

    # Composite indexes
    op.execute('DROP INDEX IF EXISTS ix_voice_sessions_status_created')
    op.execute('DROP INDEX IF EXISTS ix_contact_profiles_company_score')
    op.execute('DROP INDEX IF EXISTS ix_social_media_activity_platform_posted')
    op.execute('DROP INDEX IF EXISTS ix_agent_executions_lead_status')
    op.execute('DROP INDEX IF EXISTS ix_agent_executions_status_created')
    op.execute('DROP INDEX IF EXISTS ix_leads_score_created')

    # Single-column indexes
    op.execute('DROP INDEX IF EXISTS ix_voice_session_logs_completed_at')
    op.execute('DROP INDEX IF EXISTS ix_contact_social_profiles_contact_priority')
    op.execute('DROP INDEX IF EXISTS ix_contact_social_profiles_decision_maker_score')
    op.execute('DROP INDEX IF EXISTS ix_social_media_activity_sentiment')
    op.execute('DROP INDEX IF EXISTS ix_social_media_activity_scraped_at')
    op.execute('DROP INDEX IF EXISTS ix_social_media_activity_posted_at')
    op.execute('DROP INDEX IF EXISTS ix_agent_executions_completed_at')
    op.execute('DROP INDEX IF EXISTS ix_agent_executions_started_at')
    op.execute('DROP INDEX IF EXISTS ix_leads_updated_at')
    op.execute('DROP INDEX IF EXISTS ix_leads_qualified_at')

    # Foreign key indexes
    op.execute('DROP INDEX IF EXISTS ix_organization_charts_lead_id')
    op.execute('DROP INDEX IF EXISTS ix_contact_social_profiles_lead_id')
    op.execute('DROP INDEX IF EXISTS ix_social_media_activity_lead_id')
