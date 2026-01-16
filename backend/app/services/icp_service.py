"""
ICPService - Top 500 ICP outreach pipeline service.

Provides functionality for:
- Querying top 500 ICP leads with ATL contacts
- Exporting to CSV for Close CRM import
- Refreshing materialized view
"""
import csv
import io
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)


class ICPService:
    """
    Service for managing Top 500 ICP outreach pipeline.

    Uses mv_top500_icp materialized view for fast queries.
    """

    def __init__(self, db: AsyncSession):
        """Initialize with async database session."""
        self.db = db

    async def get_top500(
        self,
        tier: Optional[str] = None,
        state: Optional[str] = None,
        has_phone: Optional[bool] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Get top 500 ICP leads with ATL contacts.

        Args:
            tier: Filter by ICP tier (PLATINUM, GOLD, SILVER, BRONZE)
            state: Filter by state
            has_phone: Filter by phone availability
            limit: Max results (default 500)
            offset: Pagination offset

        Returns:
            Paginated list of ICP leads with contact info
        """
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        # Build WHERE clauses
        filters = []
        if tier:
            filters.append("icp_tier = :tier")
            params["tier"] = tier.upper()
        if state:
            filters.append("state = :state")
            params["state"] = state.upper()
        if has_phone is not None:
            filters.append("has_phone = :has_phone")
            params["has_phone"] = has_phone

        where_clause = ""
        if filters:
            where_clause = "WHERE " + " AND ".join(filters)

        # Count query
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM mv_top500_icp
            {where_clause}
        """
        count_result = await self.db.execute(text(count_sql), params)
        total = count_result.scalar() or 0

        # Data query
        data_sql = f"""
            SELECT
                company_id,
                company_name,
                domain,
                website,
                company_phone,
                city,
                state,
                icp_score,
                icp_tier,
                total_score,
                atl_count,
                has_phone,
                has_hvac_trade,
                is_mep_contractor,
                has_commercial,
                has_industrial,
                has_residential,
                is_multi_trade,
                trade_count,
                oem_count,
                intent_score,
                contact_id,
                atl_name,
                atl_title,
                atl_email,
                atl_phone,
                atl_linkedin,
                atl_verified,
                atl_confidence,
                atl_source,
                rank
            FROM mv_top500_icp
            {where_clause}
            ORDER BY rank ASC
            LIMIT :limit OFFSET :offset
        """
        result = await self.db.execute(text(data_sql), params)
        rows = result.fetchall()

        leads = [
            {
                "company_id": str(row.company_id),
                "company_name": row.company_name,
                "domain": row.domain,
                "website": row.website,
                "company_phone": row.company_phone,
                "city": row.city,
                "state": row.state,
                "icp_score": row.icp_score,
                "icp_tier": row.icp_tier,
                "total_score": row.total_score,
                "atl_count": row.atl_count,
                "has_phone": row.has_phone,
                "has_hvac_trade": row.has_hvac_trade,
                "is_mep_contractor": row.is_mep_contractor,
                "has_commercial": row.has_commercial,
                "has_industrial": row.has_industrial,
                "has_residential": row.has_residential,
                "is_multi_trade": row.is_multi_trade,
                "trade_count": row.trade_count,
                "oem_count": row.oem_count,
                "intent_score": float(row.intent_score) if row.intent_score else 0,
                "contact_id": str(row.contact_id) if row.contact_id else None,
                "atl_name": row.atl_name,
                "atl_title": row.atl_title,
                "atl_email": row.atl_email,
                "atl_phone": row.atl_phone,
                "atl_linkedin": row.atl_linkedin,
                "atl_verified": row.atl_verified,
                "atl_confidence": row.atl_confidence,
                "atl_source": row.atl_source,
                "rank": row.rank,
            }
            for row in rows
        ]

        return {
            "leads": leads,
            "total": int(total),
            "limit": limit,
            "offset": offset,
            "has_more": (offset + limit) < total,
        }

    async def get_tier_breakdown(self) -> Dict[str, int]:
        """
        Get count of leads by ICP tier.

        Returns:
            Dict mapping tier names to counts
        """
        result = await self.db.execute(text("""
            SELECT icp_tier, COUNT(*) as count
            FROM mv_top500_icp
            GROUP BY icp_tier
            ORDER BY
                CASE icp_tier
                    WHEN 'PLATINUM' THEN 1
                    WHEN 'GOLD' THEN 2
                    WHEN 'SILVER' THEN 3
                    WHEN 'BRONZE' THEN 4
                    ELSE 5
                END
        """))
        rows = result.fetchall()

        return {row.icp_tier: row.count for row in rows if row.icp_tier}

    async def get_state_breakdown(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get count of leads by state.

        Args:
            limit: Max states to return

        Returns:
            List of state counts sorted by count descending
        """
        result = await self.db.execute(text("""
            SELECT state, COUNT(*) as count
            FROM mv_top500_icp
            WHERE state IS NOT NULL
            GROUP BY state
            ORDER BY count DESC
            LIMIT :limit
        """), {"limit": limit})
        rows = result.fetchall()

        return [{"state": row.state, "count": row.count} for row in rows]

    async def export_csv(
        self,
        tier: Optional[str] = None,
        state: Optional[str] = None,
        has_phone: Optional[bool] = None,
    ) -> str:
        """
        Export top 500 ICP leads to CSV format.

        Args:
            tier: Filter by ICP tier
            state: Filter by state
            has_phone: Filter by phone availability

        Returns:
            CSV string ready for download
        """
        # Get all matching leads (no pagination for export)
        data = await self.get_top500(
            tier=tier,
            state=state,
            has_phone=has_phone,
            limit=500,
            offset=0,
        )

        # Create CSV in memory
        output = io.StringIO()
        writer = csv.writer(output)

        # Header row (Close CRM compatible)
        headers = [
            "Rank",
            "Company",
            "Domain",
            "Website",
            "Company Phone",
            "City",
            "State",
            "ICP Score",
            "ICP Tier",
            "Total Score",
            "ATL Count",
            "Has Phone",
            "ATL Name",
            "ATL Title",
            "ATL Email",
            "ATL Phone",
            "ATL LinkedIn",
            "ATL Verified",
            "HVAC Trade",
            "MEP Contractor",
            "Commercial",
            "Industrial",
            "Residential",
            "Multi-Trade",
            "Trade Count",
            "OEM Count",
            "Intent Score",
        ]
        writer.writerow(headers)

        # Data rows
        for lead in data["leads"]:
            writer.writerow([
                lead["rank"],
                lead["company_name"],
                lead["domain"],
                lead["website"],
                lead["company_phone"],
                lead["city"],
                lead["state"],
                lead["icp_score"],
                lead["icp_tier"],
                lead["total_score"],
                lead["atl_count"],
                "Yes" if lead["has_phone"] else "No",
                lead["atl_name"],
                lead["atl_title"],
                lead["atl_email"],
                lead["atl_phone"],
                lead["atl_linkedin"],
                "Yes" if lead["atl_verified"] else "No",
                "Yes" if lead["has_hvac_trade"] else "No",
                "Yes" if lead["is_mep_contractor"] else "No",
                "Yes" if lead["has_commercial"] else "No",
                "Yes" if lead["has_industrial"] else "No",
                "Yes" if lead["has_residential"] else "No",
                "Yes" if lead["is_multi_trade"] else "No",
                lead["trade_count"],
                lead["oem_count"],
                lead["intent_score"],
            ])

        return output.getvalue()

    async def refresh_materialized_view(self) -> Dict[str, Any]:
        """
        Refresh the mv_top500_icp materialized view.

        Uses CONCURRENTLY to avoid blocking reads.

        Returns:
            Refresh status with timing info
        """
        start_time = datetime.utcnow()

        try:
            await self.db.execute(
                text("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_top500_icp")
            )
            await self.db.commit()

            end_time = datetime.utcnow()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)

            logger.info(f"Refreshed mv_top500_icp in {duration_ms}ms")

            return {
                "status": "success",
                "refreshed_at": end_time.isoformat(),
                "duration_ms": duration_ms,
            }
        except Exception as e:
            logger.error(f"Failed to refresh mv_top500_icp: {e}")
            return {
                "status": "error",
                "error": str(e),
            }

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics for the top 500 list.

        Returns:
            Stats including total count, tier breakdown, phone coverage
        """
        result = await self.db.execute(text("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN has_phone THEN 1 ELSE 0 END) as with_phone,
                SUM(CASE WHEN atl_verified THEN 1 ELSE 0 END) as verified,
                AVG(icp_score) as avg_icp_score,
                AVG(total_score) as avg_total_score,
                SUM(CASE WHEN has_hvac_trade THEN 1 ELSE 0 END) as hvac_count,
                SUM(CASE WHEN is_mep_contractor THEN 1 ELSE 0 END) as mep_count
            FROM mv_top500_icp
        """))
        row = result.fetchone()

        tier_breakdown = await self.get_tier_breakdown()
        state_breakdown = await self.get_state_breakdown(limit=10)

        return {
            "total": row.total or 0,
            "with_phone": row.with_phone or 0,
            "verified": row.verified or 0,
            "phone_coverage_pct": round(
                (row.with_phone / row.total * 100) if row.total else 0, 1
            ),
            "avg_icp_score": round(row.avg_icp_score or 0, 1),
            "avg_total_score": round(row.avg_total_score or 0, 1),
            "hvac_count": row.hvac_count or 0,
            "mep_count": row.mep_count or 0,
            "tier_breakdown": tier_breakdown,
            "top_states": state_breakdown,
        }
