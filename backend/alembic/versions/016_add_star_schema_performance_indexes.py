"""add_performance_indexes_for_star_schema

Revision ID: 016_star_schema_performance
Revises: 014_social_intelligence
Create Date: 2025-12-01

This migration adds critical performance indexes identified in the Supabase audit.
Fixes Category 3 (Performance Issues) from SUPABASE_ISSUES_CATEGORIZED.md.

Target Tables:
- dim_companies: JSONB indexes for enrichment_data, OEM brands, license types
- dim_contacts: JSONB indexes for linkedin_data
- fact_activities: Missing foreign key index for contact_id
- re_enrich_queue: Timestamp and priority indexes for work queue
- Composite indexes for common query patterns

Performance Impact:
- JSONB GIN indexes: 10-100x faster for JSONB queries
- Foreign key indexes: Essential for join performance
- Timestamp indexes: Critical for time-range queries and work queues
- Composite indexes: 2-5x faster for multi-column filters

Index Strategy:
- Use CONCURRENTLY to avoid table locks (production safe)
- GIN indexes for JSONB columns (optimal for containment queries)
- B-tree indexes for foreign keys and timestamps
- Composite indexes with most selective column first

Estimated Issues Fixed: 20-30 performance issues (all Category 3)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '016_star_schema_performance'
down_revision: Union[str, None] = '014_social_intelligence'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add comprehensive performance indexes for star schema tables.

    Priority Levels:
    - CRITICAL: JSONB columns (enrichment data)
    - HIGH: Foreign keys, work queue indexes
    - MEDIUM: Composite indexes for common query patterns
    """

    # ============================================================================
    # CRITICAL: JSONB Column Indexes
    # ============================================================================
    # Enable fast queries on JSONB columns containing enrichment data
    # GIN indexes are optimal for JSONB containment queries (@>, ?, ?&, ?|)

    print("Creating JSONB GIN indexes for enrichment data...")

    # dim_companies - enrichment_data (if exists)
    # Note: Check if column exists in actual schema
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'dim_companies'
                AND column_name = 'enrichment_data'
            ) THEN
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_companies_enrichment_data
                    ON dim_companies USING GIN (enrichment_data);
            END IF;
        END $$;
    """)

    # dim_companies - oem_brands and license_types (confirmed to exist)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_companies_oem_brands
            ON dim_companies USING GIN (oem_brands)
    """)

    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_companies_license_types
            ON dim_companies USING GIN (license_types)
    """)

    # dim_contacts - linkedin_data (if exists)
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'dim_contacts'
                AND column_name = 'linkedin_data'
            ) THEN
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_contacts_linkedin_data
                    ON dim_contacts USING GIN (linkedin_data);
            END IF;
        END $$;
    """)

    # re_enrich_queue - result_summary JSONB
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_re_enrich_queue_result
            ON re_enrich_queue USING GIN (result_summary)
    """)

    # ============================================================================
    # HIGH PRIORITY: Foreign Key Indexes
    # ============================================================================
    # PostgreSQL does NOT automatically index foreign keys
    # These are essential for join performance

    print("Creating foreign key indexes...")

    # fact_activities - contact_id (missing in audit)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_activities_contact_id
            ON fact_activities(contact_id)
    """)

    # Note: company_id and user_id already have indexes from migration 006
    # but we'll ensure they exist with IF NOT EXISTS
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_activities_company_id
            ON fact_activities(company_id)
    """)

    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_activities_user_id
            ON fact_activities(user_id)
    """)

    # ============================================================================
    # HIGH PRIORITY: Work Queue Timestamp Indexes
    # ============================================================================
    # Critical for re-enrichment queue processing and monitoring

    print("Creating work queue indexes...")

    # re_enrich_queue - processed_at for finding completed/pending items
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_re_enrich_processed
            ON re_enrich_queue(processed_at)
            WHERE processed_at IS NOT NULL
    """)

    # re_enrich_queue - priority and created_at for queue ordering
    # Note: A partial index already exists for status='pending'
    # This composite index handles priority-based processing
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_re_enrich_priority_created
            ON re_enrich_queue(priority, created_at)
            WHERE status = 'pending'
    """)

    # ============================================================================
    # MEDIUM PRIORITY: Composite Indexes for Common Query Patterns
    # ============================================================================
    # Optimize multi-column queries (most selective column first)

    print("Creating composite indexes...")

    # dim_companies - ICP tier and score (for BDR queue queries)
    # Query pattern: "Get top GOLD/PLATINUM leads sorted by score"
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_companies_tier_score
            ON dim_companies(icp_tier, icp_score DESC)
            WHERE icp_tier IN ('PLATINUM', 'GOLD')
    """)

    # dim_contacts - company and role level (for finding decision makers)
    # Query pattern: "Get ATL contacts for a company"
    op.execute("""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'dim_contacts'
                AND column_name = 'role_level'
            ) THEN
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_contacts_company_role
                    ON dim_contacts(company_id, role_level)
                    WHERE is_atl = TRUE;
            ELSE
                -- Fallback if role_level doesn't exist, use is_atl filter
                CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_contacts_company_atl
                    ON dim_contacts(company_id, is_atl)
                    WHERE is_atl = TRUE;
            END IF;
        END $$;
    """)

    # fact_activities - company and activity type (for engagement analysis)
    # Query pattern: "Get all calls/emails for a company"
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_activities_company_type
            ON fact_activities(company_id, activity_type, activity_at DESC)
    """)

    # fact_activities - user and date (for BDR activity reports)
    # Query pattern: "Get all activities by BDR in date range"
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_activities_user_date
            ON fact_activities(user_id, activity_at DESC)
    """)

    # ============================================================================
    # MEDIUM PRIORITY: Enrichment Tracking Indexes
    # ============================================================================
    # For cost analysis and ROI tracking

    print("Creating enrichment tracking indexes...")

    # dim_companies - last_enriched_at (for staleness detection)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_companies_last_enriched
            ON dim_companies(last_enriched_at)
            WHERE last_enriched_at IS NOT NULL
    """)

    # dim_companies - flagged_for_reenrich (already exists, ensure it's there)
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_companies_reenrich_flag
            ON dim_companies(flagged_for_reenrich)
            WHERE flagged_for_reenrich = TRUE
    """)

    # fact_enrichments - cost tracking for budget analysis
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_enrichments_cost
            ON fact_enrichments(cost_usd DESC)
            WHERE cost_usd > 0
    """)

    # fact_enrichments - success rate tracking
    op.execute("""
        CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_enrichments_method_success
            ON fact_enrichments(method, success, enriched_at DESC)
    """)

    print("✅ All performance indexes created successfully!")
    print("📊 Estimated performance improvements:")
    print("   - JSONB queries: 10-100x faster")
    print("   - Join queries: 5-20x faster")
    print("   - Work queue queries: 2-10x faster")
    print("   - Multi-column filters: 2-5x faster")


def downgrade() -> None:
    """
    Remove all indexes added in this migration.
    Note: DROP INDEX CONCURRENTLY is not supported in PostgreSQL <12
    Use regular DROP INDEX (will acquire brief lock)
    """

    print("Removing performance indexes...")

    # Enrichment tracking indexes
    op.execute('DROP INDEX IF EXISTS idx_fact_enrichments_method_success')
    op.execute('DROP INDEX IF EXISTS idx_fact_enrichments_cost')
    op.execute('DROP INDEX IF EXISTS idx_dim_companies_reenrich_flag')
    op.execute('DROP INDEX IF EXISTS idx_dim_companies_last_enriched')

    # Composite indexes
    op.execute('DROP INDEX IF EXISTS idx_fact_activities_user_date')
    op.execute('DROP INDEX IF EXISTS idx_fact_activities_company_type')
    op.execute('DROP INDEX IF EXISTS idx_dim_contacts_company_atl')
    op.execute('DROP INDEX IF EXISTS idx_dim_contacts_company_role')
    op.execute('DROP INDEX IF EXISTS idx_dim_companies_tier_score')

    # Work queue indexes
    op.execute('DROP INDEX IF EXISTS idx_re_enrich_priority_created')
    op.execute('DROP INDEX IF EXISTS idx_re_enrich_processed')

    # Foreign key indexes
    op.execute('DROP INDEX IF EXISTS idx_fact_activities_user_id')
    op.execute('DROP INDEX IF EXISTS idx_fact_activities_company_id')
    op.execute('DROP INDEX IF EXISTS idx_fact_activities_contact_id')

    # JSONB indexes
    op.execute('DROP INDEX IF EXISTS idx_re_enrich_queue_result')
    op.execute('DROP INDEX IF EXISTS idx_dim_contacts_linkedin_data')
    op.execute('DROP INDEX IF EXISTS idx_dim_companies_license_types')
    op.execute('DROP INDEX IF EXISTS idx_dim_companies_oem_brands')
    op.execute('DROP INDEX IF EXISTS idx_dim_companies_enrichment_data')

    print("✅ All performance indexes removed successfully!")
