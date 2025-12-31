"""
Dealer Intelligence API endpoints.

Provides REST endpoints for dealer market analytics:
- Market overview (totals, tier distribution)
- Growth signals (dealers gaining OEM certs)
- Geographic clusters (hot markets by state)
- Trifecta dealers (HVAC+Solar+Battery combos)
"""
import logging
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_async_db
from app.services.dealer_analytics_service import DealerAnalyticsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/dealers", tags=["dealer-intelligence"])


# Response Models
class TierDistribution(BaseModel):
    """ICP tier distribution."""
    PLATINUM: int = 0
    GOLD: int = 0
    SILVER: int = 0
    BRONZE: int = 0


class CapabilityDistribution(BaseModel):
    """Dealer capability counts."""
    solar: int = 0
    battery: int = 0
    hvac: int = 0
    generator: int = 0
    trifecta: int = 0


class MarketOverviewResponse(BaseModel):
    """Market overview response."""
    total_dealers: int
    tier_distribution: TierDistribution
    capability_distribution: CapabilityDistribution
    avg_icp_score: float
    avg_oem_count: float


class DealerCapabilities(BaseModel):
    """Dealer capability flags."""
    solar: bool = False
    battery: bool = False
    hvac: bool = False
    generator: bool = False


class GrowthSignalResponse(BaseModel):
    """Dealer growth signal response."""
    id: str
    name: str
    state: Optional[str]
    city: Optional[str]
    icp_tier: Optional[str]
    icp_score: float
    total_oem_count: int
    oems_certified: List[str]
    capabilities: DealerCapabilities
    updated_at: Optional[str]


class GeoClusterTierDistribution(BaseModel):
    """Tier distribution for a geographic cluster."""
    PLATINUM: int = 0
    GOLD: int = 0
    SILVER: int = 0
    BRONZE: int = 0


class GeoClusterCapabilities(BaseModel):
    """Capability counts for a geographic cluster."""
    solar: int = 0
    battery: int = 0
    hvac: int = 0
    generator: int = 0


class GeoClusterResponse(BaseModel):
    """Geographic cluster (state) response."""
    state: str
    dealer_count: int
    avg_icp_score: float
    tier_distribution: GeoClusterTierDistribution
    capabilities: GeoClusterCapabilities
    trifecta_dealers: int
    avg_oem_count: float
    last_updated: Optional[str]


class TrifectaDealerCapabilities(BaseModel):
    """Additional capabilities for trifecta dealers."""
    generator: bool = False
    ev_charger: bool = False
    smart_panel: bool = False


class TrifectaDealerResponse(BaseModel):
    """Trifecta dealer response."""
    id: str
    name: str
    state: Optional[str]
    city: Optional[str]
    icp_tier: Optional[str]
    icp_score: float
    total_oem_count: int
    oems_certified: List[str]
    additional_capabilities: TrifectaDealerCapabilities
    website: Optional[str]
    phone: Optional[str]
    updated_at: Optional[str]


class TrifectaDealerListResponse(BaseModel):
    """Paginated list of trifecta dealers."""
    dealers: List[TrifectaDealerResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class OemCategoryDistribution(BaseModel):
    """OEM distribution by category."""
    hvac: int = 0
    solar: int = 0
    battery: int = 0
    generator: int = 0
    smart_panel: int = 0
    iot: int = 0


class DealerDiversification(BaseModel):
    """Dealer diversification metrics."""
    multi_oem_3plus: int = 0
    diversified_5plus: int = 0


class OemDistributionResponse(BaseModel):
    """OEM distribution response."""
    total_oems_by_category: OemCategoryDistribution
    dealer_diversification: DealerDiversification


class RefreshViewsResponse(BaseModel):
    """Refresh views response."""
    status: str
    message: str


# Endpoints
@router.get("/market-overview", response_model=MarketOverviewResponse)
async def get_market_overview(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get high-level market overview.

    Returns total dealer count, tier distribution, capability breakdown,
    and average metrics across the entire dealer network.
    """
    service = DealerAnalyticsService(db)
    overview = await service.get_market_overview()

    return MarketOverviewResponse(
        total_dealers=overview["total_dealers"],
        tier_distribution=TierDistribution(**overview["tier_distribution"]),
        capability_distribution=CapabilityDistribution(
            **overview["capability_distribution"]
        ),
        avg_icp_score=overview["avg_icp_score"],
        avg_oem_count=overview["avg_oem_count"],
    )


@router.get("/growth-signals", response_model=List[GrowthSignalResponse])
async def get_growth_signals(
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    min_oem_count: int = Query(2, ge=1, description="Min OEM certifications"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get dealers with recent OEM additions (growth signals).

    Returns dealers updated in last 30 days with multiple OEMs,
    indicating expanding capabilities and growth.
    """
    service = DealerAnalyticsService(db)
    signals = await service.get_growth_signals(
        limit=limit,
        min_oem_count=min_oem_count,
    )

    return [
        GrowthSignalResponse(
            id=s["id"],
            name=s["name"],
            state=s["state"],
            city=s["city"],
            icp_tier=s["icp_tier"],
            icp_score=s["icp_score"],
            total_oem_count=s["total_oem_count"],
            oems_certified=s["oems_certified"],
            capabilities=DealerCapabilities(**s["capabilities"]),
            updated_at=s["updated_at"],
        )
        for s in signals
    ]


@router.get("/geo-clusters", response_model=List[GeoClusterResponse])
async def get_geo_clusters(
    min_dealers: int = Query(10, ge=1, description="Min dealers per state"),
    sort_by: str = Query(
        "dealer_count",
        regex="^(dealer_count|avg_icp_score|trifecta_dealers|platinum_count)$",
        description="Sort field",
    ),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get hot markets by state.

    Returns state-level aggregations including dealer counts,
    tier distribution, and capability breakdown.
    """
    service = DealerAnalyticsService(db)
    clusters = await service.get_geo_clusters(
        min_dealers=min_dealers,
        sort_by=sort_by,
    )

    return [
        GeoClusterResponse(
            state=c["state"],
            dealer_count=c["dealer_count"],
            avg_icp_score=c["avg_icp_score"],
            tier_distribution=GeoClusterTierDistribution(
                **c["tier_distribution"]
            ),
            capabilities=GeoClusterCapabilities(**c["capabilities"]),
            trifecta_dealers=c["trifecta_dealers"],
            avg_oem_count=c["avg_oem_count"],
            last_updated=c["last_updated"],
        )
        for c in clusters
    ]


@router.get("/trifecta", response_model=TrifectaDealerListResponse)
async def get_trifecta_dealers(
    state: Optional[str] = Query(None, description="Filter by state"),
    min_icp_score: float = Query(0, ge=0, le=100, description="Min ICP score"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get dealers with HVAC + Solar + Battery capabilities.

    These multi-capability dealers are prime targets for
    comprehensive energy solutions.
    """
    service = DealerAnalyticsService(db)
    result = await service.get_trifecta_dealers(
        state=state,
        min_icp_score=min_icp_score,
        limit=limit,
        offset=offset,
    )

    dealers = [
        TrifectaDealerResponse(
            id=d["id"],
            name=d["name"],
            state=d["state"],
            city=d["city"],
            icp_tier=d["icp_tier"],
            icp_score=d["icp_score"],
            total_oem_count=d["total_oem_count"],
            oems_certified=d["oems_certified"],
            additional_capabilities=TrifectaDealerCapabilities(
                **d["additional_capabilities"]
            ),
            website=d["website"],
            phone=d["phone"],
            updated_at=d["updated_at"],
        )
        for d in result["dealers"]
    ]

    return TrifectaDealerListResponse(
        dealers=dealers,
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        has_more=result["has_more"],
    )


@router.get("/oem-distribution", response_model=OemDistributionResponse)
async def get_oem_distribution(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get OEM distribution metrics.

    Returns counts of OEM certifications by category and
    dealer diversification metrics.
    """
    service = DealerAnalyticsService(db)
    distribution = await service.get_oem_distribution()

    return OemDistributionResponse(
        total_oems_by_category=OemCategoryDistribution(
            **distribution["total_oems_by_category"]
        ),
        dealer_diversification=DealerDiversification(
            **distribution["dealer_diversification"]
        ),
    )


@router.post("/refresh-views", response_model=RefreshViewsResponse)
async def refresh_analytics_views(
    db: AsyncSession = Depends(get_async_db),
):
    """
    Refresh dealer analytics materialized views.

    Should be called periodically (e.g., hourly) to update cached data.
    Uses CONCURRENTLY refresh for minimal blocking.
    """
    service = DealerAnalyticsService(db)
    result = await service.refresh_views()

    if result["status"] != "success":
        raise HTTPException(
            status_code=500,
            detail=result["message"],
        )

    return RefreshViewsResponse(**result)
