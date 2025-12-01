"""Enable RLS Security on 16 Public Tables

Revision ID: 015_enable_rls_security
Revises: 014_add_social_intelligence_tables
Create Date: 2025-12-01 14:00:00.000000

SECURITY FIX: Critical security issue - 16 tables exposed without RLS
Project: oyyakkuvvtckocncuwwf (scientiacapital)

This migration fixes ~40-50 of the 113 total Supabase issues by:
1. Enabling Row Level Security (RLS) on 16 public tables
2. Creating service role policies for backend access
3. Securing sensitive company, contact, and activity data

Tables secured:
- Migration 001: lead_audit_log
- Migration 004: scraper_batches, scraper_imports
- Migration 005: dim_companies, dim_contacts, dim_users, dim_sources
- Migration 006: fact_activities, fact_opportunities, fact_pipeline_stages, fact_enrichments, re_enrich_queue
- Migration 003: close_activities, close_opportunities
- Migration 007: mv_bdr_work_queue, mv_icp_gold_leads (materialized views)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '015_enable_rls_security'
down_revision: Union[str, None] = '014_add_social_intelligence_tables'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Enable Row Level Security on all tables exposed to PostgREST API.
    Create service role policies for backend access.
    """

    # ===========================================================================
    # SECTION 1: ENABLE ROW LEVEL SECURITY ON ALL TABLES
    # ===========================================================================
    # All tables exposed to PostgREST API must have RLS enabled

    tables_to_secure = [
        # Migration 001: Audit Trail
        'lead_audit_log',

        # Migration 004: Scraper Import Tables
        'scraper_batches',
        'scraper_imports',

        # Migration 005: Star Schema Dimension Tables (CRITICAL)
        'dim_companies',      # MASTER LEAD LIST - Highest priority
        'dim_contacts',       # All contact data (ATL decision makers)
        'dim_users',          # Team member data
        'dim_sources',        # Data source tracking (low risk but complete coverage)

        # Migration 006: Star Schema Fact Tables (CRITICAL)
        'fact_activities',    # All Close CRM activities (calls, emails, SMS)
        'fact_opportunities', # Deal pipeline and revenue data
        'fact_pipeline_stages', # Pipeline stage history
        'fact_enrichments',   # Enrichment costs and ROI data
        're_enrich_queue',    # Re-enrichment queue

        # Migration 003: Close CRM Sync Tables
        'close_activities',   # Close CRM activity sync
        'close_opportunities', # Close CRM opportunity sync
    ]

    # Enable RLS on all tables
    for table in tables_to_secure:
        op.execute(f'ALTER TABLE {table} ENABLE ROW LEVEL SECURITY')

    # Enable RLS on materialized views (if supported by PostgreSQL version)
    # Note: PostgreSQL 9.5+ supports RLS on views
    try:
        op.execute('ALTER MATERIALIZED VIEW mv_icp_gold_leads ENABLE ROW LEVEL SECURITY')
        op.execute('ALTER MATERIALIZED VIEW mv_bdr_work_queue ENABLE ROW LEVEL SECURITY')
    except Exception as e:
        # Materialized views may not support RLS in all PostgreSQL versions
        print(f"Warning: Could not enable RLS on materialized views: {e}")

    # ===========================================================================
    # SECTION 2: CREATE SERVICE ROLE POLICIES
    # ===========================================================================
    # Allow backend service role full access to all tables

    policies = {
        # Migration 001
        'lead_audit_log': 'lead_audit_log_service_all',

        # Migration 004
        'scraper_batches': 'scraper_batches_service_all',
        'scraper_imports': 'scraper_imports_service_all',

        # Migration 005 (Star Schema Dimensions)
        'dim_companies': 'dim_companies_service_all',
        'dim_contacts': 'dim_contacts_service_all',
        'dim_users': 'dim_users_service_all',
        'dim_sources': 'dim_sources_service_all',

        # Migration 006 (Star Schema Facts)
        'fact_activities': 'fact_activities_service_all',
        'fact_opportunities': 'fact_opportunities_service_all',
        'fact_pipeline_stages': 'fact_pipeline_stages_service_all',
        'fact_enrichments': 'fact_enrichments_service_all',
        're_enrich_queue': 're_enrich_queue_service_all',

        # Migration 003 (Close CRM)
        'close_activities': 'close_activities_service_all',
        'close_opportunities': 'close_opportunities_service_all',
    }

    # Create service role policy for each table
    for table, policy_name in policies.items():
        # Drop existing policy if exists (idempotent)
        op.execute(f'DROP POLICY IF EXISTS "{policy_name}" ON {table}')

        # Create new service role policy
        op.execute(f'''
            CREATE POLICY "{policy_name}" ON {table}
                FOR ALL
                USING (auth.jwt()->>'role' = 'service_role')
                WITH CHECK (auth.jwt()->>'role' = 'service_role')
        ''')

    # ===========================================================================
    # SECTION 3: FIX DUPLICATE close_activities POLICIES
    # ===========================================================================
    # Migration 002 and 003 both define policies for close_activities
    # Drop old generic policies and use our properly-named policy

    # Drop old duplicate policies (if they exist)
    op.execute('DROP POLICY IF EXISTS "Service role full access" ON close_activities')
    op.execute('DROP POLICY IF EXISTS "Service role access" ON close_activities')

    # ===========================================================================
    # SECTION 4: CREATE POLICIES FOR MATERIALIZED VIEWS
    # ===========================================================================
    # Allow service role to access materialized views

    try:
        # mv_icp_gold_leads
        op.execute('DROP POLICY IF EXISTS "mv_icp_gold_leads_service_all" ON mv_icp_gold_leads')
        op.execute('''
            CREATE POLICY "mv_icp_gold_leads_service_all" ON mv_icp_gold_leads
                FOR SELECT
                USING (auth.jwt()->>'role' = 'service_role')
        ''')

        # mv_bdr_work_queue
        op.execute('DROP POLICY IF EXISTS "mv_bdr_work_queue_service_all" ON mv_bdr_work_queue')
        op.execute('''
            CREATE POLICY "mv_bdr_work_queue_service_all" ON mv_bdr_work_queue
                FOR SELECT
                USING (auth.jwt()->>'role' = 'service_role')
        ''')
    except Exception as e:
        print(f"Warning: Could not create policies on materialized views: {e}")

    # ===========================================================================
    # VERIFICATION QUERY (RUN AFTER MIGRATION)
    # ===========================================================================
    # Check that all tables now have RLS enabled
    print("\n" + "="*80)
    print("RLS SECURITY MIGRATION COMPLETED")
    print("="*80)
    print(f"✓ Enabled RLS on {len(tables_to_secure)} tables")
    print(f"✓ Created {len(policies)} service role policies")
    print("✓ Fixed duplicate close_activities policies")
    print("✓ Secured materialized views (if supported)")
    print("\nTo verify, run this query in psql:")
    print("""
    SELECT tablename, rowsecurity as rls_enabled
    FROM pg_tables
    WHERE schemaname = 'public'
        AND tablename IN (
            'lead_audit_log', 'scraper_batches', 'scraper_imports',
            'dim_companies', 'dim_contacts', 'dim_users', 'dim_sources',
            'fact_activities', 'fact_opportunities', 'fact_pipeline_stages',
            'fact_enrichments', 're_enrich_queue',
            'close_activities', 'close_opportunities'
        )
    ORDER BY tablename;
    """)
    print("="*80 + "\n")


def downgrade() -> None:
    """
    Rollback: Disable RLS and remove all policies.
    WARNING: This will re-expose sensitive data to PostgREST API!
    """

    # ===========================================================================
    # SECTION 1: DROP ALL SERVICE ROLE POLICIES
    # ===========================================================================

    policies = {
        'lead_audit_log': 'lead_audit_log_service_all',
        'scraper_batches': 'scraper_batches_service_all',
        'scraper_imports': 'scraper_imports_service_all',
        'dim_companies': 'dim_companies_service_all',
        'dim_contacts': 'dim_contacts_service_all',
        'dim_users': 'dim_users_service_all',
        'dim_sources': 'dim_sources_service_all',
        'fact_activities': 'fact_activities_service_all',
        'fact_opportunities': 'fact_opportunities_service_all',
        'fact_pipeline_stages': 'fact_pipeline_stages_service_all',
        'fact_enrichments': 'fact_enrichments_service_all',
        're_enrich_queue': 're_enrich_queue_service_all',
        'close_activities': 'close_activities_service_all',
        'close_opportunities': 'close_opportunities_service_all',
    }

    # Drop all policies
    for table, policy_name in policies.items():
        op.execute(f'DROP POLICY IF EXISTS "{policy_name}" ON {table}')

    # Drop materialized view policies
    try:
        op.execute('DROP POLICY IF EXISTS "mv_icp_gold_leads_service_all" ON mv_icp_gold_leads')
        op.execute('DROP POLICY IF EXISTS "mv_bdr_work_queue_service_all" ON mv_bdr_work_queue')
    except Exception:
        pass

    # ===========================================================================
    # SECTION 2: DISABLE ROW LEVEL SECURITY
    # ===========================================================================
    # WARNING: This re-exposes all data to PostgREST API!

    tables_to_unsecure = [
        'lead_audit_log',
        'scraper_batches',
        'scraper_imports',
        'dim_companies',
        'dim_contacts',
        'dim_users',
        'dim_sources',
        'fact_activities',
        'fact_opportunities',
        'fact_pipeline_stages',
        'fact_enrichments',
        're_enrich_queue',
        'close_activities',
        'close_opportunities',
    ]

    # Disable RLS on all tables
    for table in tables_to_unsecure:
        op.execute(f'ALTER TABLE {table} DISABLE ROW LEVEL SECURITY')

    # Disable RLS on materialized views
    try:
        op.execute('ALTER MATERIALIZED VIEW mv_icp_gold_leads DISABLE ROW LEVEL SECURITY')
        op.execute('ALTER MATERIALIZED VIEW mv_bdr_work_queue DISABLE ROW LEVEL SECURITY')
    except Exception:
        pass

    print("\n" + "="*80)
    print("⚠️  WARNING: RLS SECURITY HAS BEEN DISABLED!")
    print("="*80)
    print("All sensitive data is now exposed to PostgREST API!")
    print("This rollback should only be used in development/testing.")
    print("="*80 + "\n")
