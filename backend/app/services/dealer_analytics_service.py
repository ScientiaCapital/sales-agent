"""
DealerAnalyticsService - Market intelligence for dealer network.

Provides analytics across 23K+ dealers with materialized views for performance:
- Market overview (totals, tier distribution, OEM breakdown)
- Growth signals (dealers gaining certifications)
- Geographic clusters (hot markets by state)
- Trifecta dealers (HVAC+Solar+Battery combos)

Uses materialized views created in migration 023_dealer_metrics.
"""
import logging
from typing import Dict, Any, List, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, text
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger(__name__)


class DealerAnalyticsService:
    """
    Service for dealer market intelligence.

    Uses materialized views for sub-100ms dashboard queries:
    - mv_dealer_market_trends
    - mv_dealer_oem_distribution
    - mv_dealer_growth_signals

    Usage:
        service = DealerAnalyticsService(db)
        overview = await service.get_market_overview()
    """

    def __init__(self, db: AsyncSession):
        """Initialize with async database session."""
        self.db = db

    async def get_market_overview(self) -> Dict[str, Any]:
        """
        Get high-level market overview.

        Returns:
            - total_dealers: Total dealer count
            - tier_distribution: Count by ICP tier
            - capability_distribution: Count by capability
            - oem_distribution: Count by OEM category
            - avg_icp_score: Average ICP score
        """
        # Get totals from materialized view
        result = await self.db.execute(text("""
            SELECT
                SUM(dealer_count) as total_dealers,
                SUM(platinum_count) as platinum_count,
                SUM(gold_count) as gold_count,
                SUM(silver_count) as silver_count,
                SUM(bronze_count) as bronze_count,
                SUM(solar_dealers) as solar_dealers,
                SUM(battery_dealers) as battery_dealers,
                SUM(hvac_dealers) as hvac_dealers,
                SUM(generator_dealers) as generator_dealers,
                SUM(trifecta_dealers) as trifecta_dealers,
                AVG(avg_icp_score) as avg_icp_score,
                AVG(avg_oem_count) as avg_oem_count
            FROM mv_dealer_market_trends
        """))
        row = result.fetchone()

        if not row:
            return {
                "total_dealers": 0,
                "tier_distribution": {},
                "capability_distribution": {},
                "avg_icp_score": 0,
                "avg_oem_count": 0,
            }

        return {
            "total_dealers": int(row.total_dealers or 0),
            "tier_distribution": {
                "PLATINUM": int(row.platinum_count or 0),
                "GOLD": int(row.gold_count or 0),
                "SILVER": int(row.silver_count or 0),
                "BRONZE": int(row.bronze_count or 0),
            },
            "capability_distribution": {
                "solar": int(row.solar_dealers or 0),
                "battery": int(row.battery_dealers or 0),
                "hvac": int(row.hvac_dealers or 0),
                "generator": int(row.generator_dealers or 0),
                "trifecta": int(row.trifecta_dealers or 0),
            },
            "avg_icp_score": round(float(row.avg_icp_score or 0), 1),
            "avg_oem_count": round(float(row.avg_oem_count or 0), 1),
        }

    async def get_growth_signals(
        self,
        limit: int = 50,
        min_oem_count: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Get dealers with recent OEM additions (growth signals).

        Returns dealers updated in last 30 days with multiple OEMs,
        indicating expanding capabilities.

        Args:
            limit: Maximum results to return
            min_oem_count: Minimum OEM count filter

        Returns:
            List of dealer growth signal records
        """
        result = await self.db.execute(text("""
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
                updated_at
            FROM mv_dealer_growth_signals
            WHERE total_oem_count >= :min_oem
            ORDER BY total_oem_count DESC, icp_score DESC
            LIMIT :limit
        """), {"min_oem": min_oem_count, "limit": limit})

        rows = result.fetchall()

        return [
            {
                "id": str(row.id),
                "name": row.name,
                "state": row.state,
                "city": row.city,
                "icp_tier": row.icp_tier,
                "icp_score": float(row.icp_score) if row.icp_score else 0,
                "total_oem_count": int(row.total_oem_count or 0),
                "oems_certified": row.oems_certified or [],
                "capabilities": {
                    "solar": bool(row.has_solar),
                    "battery": bool(row.has_battery),
                    "hvac": bool(row.has_hvac),
                    "generator": bool(row.has_generator),
                },
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]

    async def get_geo_clusters(
        self,
        min_dealers: int = 10,
        sort_by: str = "dealer_count"
    ) -> List[Dict[str, Any]]:
        """
        Get hot markets by state from materialized view.

        Args:
            min_dealers: Minimum dealer count to include state
            sort_by: Field to sort by (dealer_count, avg_icp_score, trifecta_dealers)

        Returns:
            List of state market data
        """
        # Whitelist of valid sort fields - prevents SQL injection
        VALID_SORT_FIELDS = {
            "dealer_count": "dealer_count DESC",
            "avg_icp_score": "avg_icp_score DESC",
            "trifecta_dealers": "trifecta_dealers DESC",
            "platinum_count": "platinum_count DESC",
        }
        order_clause = VALID_SORT_FIELDS.get(sort_by, "dealer_count DESC")

        result = await self.db.execute(text(f"""
            SELECT
                state,
                dealer_count,
                avg_icp_score,
                platinum_count,
                gold_count,
                silver_count,
                bronze_count,
                solar_dealers,
                battery_dealers,
                hvac_dealers,
                generator_dealers,
                trifecta_dealers,
                avg_oem_count,
                last_updated
            FROM mv_dealer_market_trends
            WHERE dealer_count >= :min_dealers
              AND state IS NOT NULL
            ORDER BY {order_clause}
        """), {"min_dealers": min_dealers})

        rows = result.fetchall()

        return [
            {
                "state": row.state,
                "dealer_count": int(row.dealer_count or 0),
                "avg_icp_score": round(float(row.avg_icp_score or 0), 1),
                "tier_distribution": {
                    "PLATINUM": int(row.platinum_count or 0),
                    "GOLD": int(row.gold_count or 0),
                    "SILVER": int(row.silver_count or 0),
                    "BRONZE": int(row.bronze_count or 0),
                },
                "capabilities": {
                    "solar": int(row.solar_dealers or 0),
                    "battery": int(row.battery_dealers or 0),
                    "hvac": int(row.hvac_dealers or 0),
                    "generator": int(row.generator_dealers or 0),
                },
                "trifecta_dealers": int(row.trifecta_dealers or 0),
                "avg_oem_count": round(float(row.avg_oem_count or 0), 1),
                "last_updated": row.last_updated.isoformat() if row.last_updated else None,
            }
            for row in rows
        ]

    async def get_trifecta_dealers(
        self,
        state: Optional[str] = None,
        min_icp_score: float = 0,
        limit: int = 100,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get dealers with HVAC + Solar + Battery capabilities.

        These multi-capability dealers are prime targets for
        comprehensive energy solutions.

        Args:
            state: Filter by state (optional)
            min_icp_score: Minimum ICP score filter
            limit: Maximum results per page
            offset: Pagination offset

        Returns:
            Paginated list of trifecta dealers
        """
        params = {
            "min_score": min_icp_score,
            "limit": limit,
            "offset": offset,
        }

        state_filter = ""
        if state:
            state_filter = "AND state = :state"
            params["state"] = state.upper()

        # Count query
        count_result = await self.db.execute(text(f"""
            SELECT COUNT(*) as total
            FROM dim_companies
            WHERE source_type = 'dealer_scraper'
              AND has_hvac = true
              AND has_solar = true
              AND has_battery = true
              AND COALESCE(icp_score, 0) >= :min_score
              {state_filter}
        """), params)
        total = count_result.scalar() or 0

        # Data query
        result = await self.db.execute(text(f"""
            SELECT
                id,
                name,
                state,
                city,
                icp_tier,
                icp_score,
                total_oem_count,
                oems_certified,
                has_generator,
                has_ev_charger,
                has_smart_panel,
                website,
                phone,
                updated_at
            FROM dim_companies
            WHERE source_type = 'dealer_scraper'
              AND has_hvac = true
              AND has_solar = true
              AND has_battery = true
              AND COALESCE(icp_score, 0) >= :min_score
              {state_filter}
            ORDER BY icp_score DESC, total_oem_count DESC
            LIMIT :limit OFFSET :offset
        """), params)

        rows = result.fetchall()

        dealers = [
            {
                "id": str(row.id),
                "name": row.name,
                "state": row.state,
                "city": row.city,
                "icp_tier": row.icp_tier,
                "icp_score": float(row.icp_score) if row.icp_score else 0,
                "total_oem_count": int(row.total_oem_count or 0),
                "oems_certified": row.oems_certified or [],
                "additional_capabilities": {
                    "generator": bool(row.has_generator),
                    "ev_charger": bool(row.has_ev_charger),
                    "smart_panel": bool(row.has_smart_panel),
                },
                "website": row.website,
                "phone": row.phone,
                "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            }
            for row in rows
        ]

        return {
            "dealers": dealers,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }

    async def get_oem_distribution(self) -> Dict[str, Any]:
        """
        Get OEM distribution metrics from materialized view.

        Returns counts of OEM certifications by category across all dealers.
        """
        result = await self.db.execute(text("""
            SELECT
                SUM(total_hvac_oems) as hvac_oems,
                SUM(total_solar_oems) as solar_oems,
                SUM(total_battery_oems) as battery_oems,
                SUM(total_generator_oems) as generator_oems,
                SUM(total_smart_panel_oems) as smart_panel_oems,
                SUM(total_iot_oems) as iot_oems,
                SUM(multi_oem_dealers) as multi_oem_dealers,
                SUM(diversified_dealers) as diversified_dealers
            FROM mv_dealer_oem_distribution
        """))
        row = result.fetchone()

        if not row:
            return {"total_oems_by_category": {}, "dealer_diversification": {}}

        return {
            "total_oems_by_category": {
                "hvac": int(row.hvac_oems or 0),
                "solar": int(row.solar_oems or 0),
                "battery": int(row.battery_oems or 0),
                "generator": int(row.generator_oems or 0),
                "smart_panel": int(row.smart_panel_oems or 0),
                "iot": int(row.iot_oems or 0),
            },
            "dealer_diversification": {
                "multi_oem_3plus": int(row.multi_oem_dealers or 0),
                "diversified_5plus": int(row.diversified_dealers or 0),
            },
        }

    async def refresh_views(self) -> Dict[str, str]:
        """
        Refresh all dealer analytics materialized views.

        Should be called periodically (e.g., hourly) to update cached data.
        Uses CONCURRENTLY refresh for minimal blocking.

        Returns:
            Status of refresh operation
        """
        try:
            await self.db.execute(text("SELECT refresh_dealer_analytics_views()"))
            await self.db.commit()
            logger.info("Refreshed dealer analytics materialized views")
            return {"status": "success", "message": "Views refreshed successfully"}
        except Exception as e:
            logger.error(f"Failed to refresh dealer analytics views: {e}")
            return {"status": "error", "message": str(e)}
