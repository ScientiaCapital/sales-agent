"""Create materialized views for dealer market analytics.

Revision ID: 023_dealer_metrics
Revises: 022_enable_rls_additional_tables
Create Date: 2025-12-28

Creates materialized views for fast dealer market trend queries:
- mv_dealer_market_trends: State-level dealer aggregations
- mv_dealer_oem_distribution: OEM certification distribution

These views provide sub-100ms dashboard queries for 23K+ dealers.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '024_dealer_metrics'
down_revision: Union[str, None] = '023_account_layer'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create materialized views for dealer analytics."""

    # ===========================================================================
    # MATERIALIZED VIEW 1: Market Trends by State
    # ===========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dealer_market_trends AS
        SELECT
            state,
            COUNT(*) as dealer_count,
            AVG(icp_score) as avg_icp_score,
            COUNT(*) FILTER (WHERE icp_tier = 'PLATINUM') as platinum_count,
            COUNT(*) FILTER (WHERE icp_tier = 'GOLD') as gold_count,
            COUNT(*) FILTER (WHERE icp_tier = 'SILVER') as silver_count,
            COUNT(*) FILTER (WHERE icp_tier = 'BRONZE') as bronze_count,
            COUNT(*) FILTER (WHERE has_solar = true) as solar_dealers,
            COUNT(*) FILTER (WHERE has_battery = true) as battery_dealers,
            COUNT(*) FILTER (WHERE has_hvac = true) as hvac_dealers,
            COUNT(*) FILTER (WHERE has_generator = true) as generator_dealers,
            COUNT(*) FILTER (WHERE has_hvac = true AND has_solar = true AND has_battery = true) as trifecta_dealers,
            AVG(total_oem_count) as avg_oem_count,
            MAX(updated_at) as last_updated
        FROM dim_companies
        WHERE source_type = 'dealer_scraper'
        GROUP BY state
    """)

    # Create unique index for concurrent refresh
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dealer_trends_state
        ON mv_dealer_market_trends(state)
    """)

    # ===========================================================================
    # MATERIALIZED VIEW 2: OEM Distribution
    # ===========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dealer_oem_distribution AS
        SELECT
            COALESCE(state, 'Unknown') as state,
            SUM(hvac_oem_count) as total_hvac_oems,
            SUM(solar_oem_count) as total_solar_oems,
            SUM(battery_oem_count) as total_battery_oems,
            SUM(generator_oem_count) as total_generator_oems,
            SUM(smart_panel_oem_count) as total_smart_panel_oems,
            SUM(iot_oem_count) as total_iot_oems,
            COUNT(*) FILTER (WHERE total_oem_count >= 3) as multi_oem_dealers,
            COUNT(*) FILTER (WHERE total_oem_count >= 5) as diversified_dealers
        FROM dim_companies
        WHERE source_type = 'dealer_scraper'
        GROUP BY state
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dealer_oem_state
        ON mv_dealer_oem_distribution(state)
    """)

    # ===========================================================================
    # MATERIALIZED VIEW 3: Growth Signals (Recent OEM Additions)
    # ===========================================================================
    op.execute("""
        CREATE MATERIALIZED VIEW IF NOT EXISTS mv_dealer_growth_signals AS
        SELECT
            id,
            name,
            state,
            city,
            icp_tier,
            icp_score,
            total_oem_count,
            oems_certified,
            has_solar,
            has_battery,
            has_hvac,
            has_generator,
            updated_at,
            created_at
        FROM dim_companies
        WHERE source_type = 'dealer_scraper'
          AND total_oem_count >= 2
          AND updated_at >= NOW() - INTERVAL '30 days'
        ORDER BY total_oem_count DESC, icp_score DESC
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_dealer_growth_id
        ON mv_dealer_growth_signals(id)
    """)

    # ===========================================================================
    # FUNCTION: Refresh Materialized Views
    # ===========================================================================
    op.execute("""
        CREATE OR REPLACE FUNCTION refresh_dealer_analytics_views()
        RETURNS void AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dealer_market_trends;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dealer_oem_distribution;
            REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dealer_growth_signals;
        END;
        $$ LANGUAGE plpgsql;
    """)

    # ===========================================================================
    # Additional Indexes on dim_companies for dealer queries
    # ===========================================================================
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dim_companies_source_type
        ON dim_companies(source_type)
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dim_companies_dealer_state
        ON dim_companies(state)
        WHERE source_type = 'dealer_scraper'
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dim_companies_icp_tier
        ON dim_companies(icp_tier)
        WHERE source_type = 'dealer_scraper'
    """)

    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_dim_companies_trifecta
        ON dim_companies(has_hvac, has_solar, has_battery)
        WHERE source_type = 'dealer_scraper'
    """)

    print("\n" + "=" * 80)
    print("DEALER ANALYTICS MIGRATION 023 COMPLETED")
    print("=" * 80)
    print("Created materialized views:")
    print("  - mv_dealer_market_trends (state-level aggregations)")
    print("  - mv_dealer_oem_distribution (OEM distribution by state)")
    print("  - mv_dealer_growth_signals (recent OEM additions)")
    print("\nCreated function:")
    print("  - refresh_dealer_analytics_views() for concurrent refresh")
    print("\nCreated indexes for dealer queries")
    print("=" * 80 + "\n")


def downgrade() -> None:
    """Drop materialized views and related objects."""

    # Drop function
    op.execute("DROP FUNCTION IF EXISTS refresh_dealer_analytics_views()")

    # Drop materialized views
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_dealer_growth_signals")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_dealer_oem_distribution")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_dealer_market_trends")

    # Drop indexes
    op.execute("DROP INDEX IF EXISTS idx_dim_companies_trifecta")
    op.execute("DROP INDEX IF EXISTS idx_dim_companies_icp_tier")
    op.execute("DROP INDEX IF EXISTS idx_dim_companies_dealer_state")
    op.execute("DROP INDEX IF EXISTS idx_dim_companies_source_type")

    print("Rolled back dealer analytics migration 023")
