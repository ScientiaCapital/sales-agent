"""
Top 500 ICP Outreach API endpoints.

Provides REST endpoints for ICP outreach pipeline:
- Query top 500 ICP leads with ATL contacts
- Export to CSV for Close CRM import
- Refresh materialized view
- Statistics and breakdowns
"""
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_async_db
from app.services.icp_service import ICPService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/icp", tags=["icp-outreach"])


# Request/Response Models
class ICPLeadResponse(BaseModel):
    """Single ICP lead with ATL contact."""
    company_id: str
    company_name: str
    domain: Optional[str]
    website: Optional[str]
    company_phone: Optional[str]
    city: Optional[str]
    state: Optional[str]
    icp_score: Optional[int]
    icp_tier: Optional[str]
    total_score: int
    atl_count: int
    has_phone: bool
    has_hvac_trade: Optional[bool]
    is_mep_contractor: Optional[bool]
    has_commercial: Optional[bool]
    has_industrial: Optional[bool]
    has_residential: Optional[bool]
    is_multi_trade: Optional[bool]
    trade_count: Optional[int]
    oem_count: Optional[int]
    intent_score: float
    contact_id: Optional[str]
    atl_name: Optional[str]
    atl_title: Optional[str]
    atl_email: Optional[str]
    atl_phone: Optional[str]
    atl_linkedin: Optional[str]
    atl_verified: Optional[bool]
    atl_confidence: Optional[int]
    atl_source: Optional[str]
    rank: int


class ICPListResponse(BaseModel):
    """Paginated list of ICP leads."""
    leads: List[ICPLeadResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class TierBreakdownResponse(BaseModel):
    """ICP tier breakdown stats."""
    tier_breakdown: Dict[str, int]


class StateCount(BaseModel):
    """State with count."""
    state: str
    count: int


class ICPStatsResponse(BaseModel):
    """ICP list statistics."""
    total: int
    with_phone: int
    verified: int
    phone_coverage_pct: float
    avg_icp_score: float
    avg_total_score: float
    hvac_count: int
    mep_count: int
    tier_breakdown: Dict[str, int]
    top_states: List[StateCount]


class RefreshResponse(BaseModel):
    """Materialized view refresh response."""
    status: str
    refreshed_at: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None


# Endpoints
@router.get("/top500", response_model=ICPListResponse)
async def get_top500_icp(
    tier: Optional[str] = Query(
        None,
        description="Filter by ICP tier (PLATINUM, GOLD, SILVER, BRONZE)"
    ),
    state: Optional[str] = Query(None, description="Filter by state"),
    has_phone: Optional[bool] = Query(None, description="Filter by phone availability"),
    limit: int = Query(500, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get top 500 ICP leads with ATL contacts.

    Returns ranked list of companies with their best ATL contact info.
    Sorted by composite score (ICP + industry signals + phone bonus).

    Use tier/state/has_phone filters to narrow results.
    """
    service = ICPService(db)

    try:
        result = await service.get_top500(
            tier=tier,
            state=state,
            has_phone=has_phone,
            limit=limit,
            offset=offset,
        )

        leads = [ICPLeadResponse(**lead) for lead in result["leads"]]

        return ICPListResponse(
            leads=leads,
            total=result["total"],
            limit=result["limit"],
            offset=result["offset"],
            has_more=result["has_more"],
        )
    except Exception as e:
        logger.error(f"Failed to get top 500 ICP: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top500/export")
async def export_top500_csv(
    tier: Optional[str] = Query(None, description="Filter by ICP tier"),
    state: Optional[str] = Query(None, description="Filter by state"),
    has_phone: Optional[bool] = Query(None, description="Filter by phone availability"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Export top 500 ICP leads as CSV for Close CRM import.

    Returns downloadable CSV file with all lead and contact data.
    """
    service = ICPService(db)

    try:
        csv_content = await service.export_csv(
            tier=tier,
            state=state,
            has_phone=has_phone,
        )

        # Generate filename with date
        from datetime import datetime
        filename = f"top500_icp_outreach_{datetime.now().strftime('%Y%m%d')}.csv"

        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "Content-Type": "text/csv; charset=utf-8",
            },
        )
    except Exception as e:
        logger.error(f"Failed to export CSV: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/top500/refresh", response_model=RefreshResponse)
async def refresh_materialized_view(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Refresh the mv_top500_icp materialized view.

    Call this after bulk data updates to ensure the view is current.
    Uses CONCURRENTLY to avoid blocking reads during refresh.
    """
    service = ICPService(db)

    result = await service.refresh_materialized_view()

    return RefreshResponse(**result)


@router.get("/top500/stats", response_model=ICPStatsResponse)
async def get_top500_stats(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get summary statistics for the top 500 ICP list.

    Returns counts, tier breakdown, state distribution, and coverage metrics.
    """
    service = ICPService(db)

    try:
        stats = await service.get_stats()

        return ICPStatsResponse(
            total=stats["total"],
            with_phone=stats["with_phone"],
            verified=stats["verified"],
            phone_coverage_pct=stats["phone_coverage_pct"],
            avg_icp_score=stats["avg_icp_score"],
            avg_total_score=stats["avg_total_score"],
            hvac_count=stats["hvac_count"],
            mep_count=stats["mep_count"],
            tier_breakdown=stats["tier_breakdown"],
            top_states=[StateCount(**s) for s in stats["top_states"]],
        )
    except Exception as e:
        logger.error(f"Failed to get stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/top500/tiers", response_model=TierBreakdownResponse)
async def get_tier_breakdown(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get count of leads by ICP tier.

    Returns dict mapping tier names (PLATINUM, GOLD, etc.) to counts.
    """
    service = ICPService(db)

    try:
        breakdown = await service.get_tier_breakdown()
        return TierBreakdownResponse(tier_breakdown=breakdown)
    except Exception as e:
        logger.error(f"Failed to get tier breakdown: {e}")
        raise HTTPException(status_code=500, detail=str(e))
