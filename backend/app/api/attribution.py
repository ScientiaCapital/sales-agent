"""
Attribution Dashboard API endpoints.

Provides REST endpoints for:
- Deal attribution tracking
- Multi-touch attribution analysis
- Channel and rep performance metrics
- ROI calculations
"""
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_async_db
from app.services.analytics.attribution_service import AttributionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/attribution", tags=["attribution"])


# Request/Response Models
class TouchpointSchema(BaseModel):
    """Touchpoint definition."""
    type: str = Field(..., description="Touchpoint type (email_sent, call_completed, etc.)")
    channel: str = Field(..., description="Channel (email, call, meeting, etc.)")
    timestamp: str = Field(..., description="ISO timestamp of the touchpoint")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class CreateAttributionRequest(BaseModel):
    """Request to create deal attribution."""
    deal_id: str = Field(..., description="Unique deal identifier from CRM")
    deal_value: Optional[float] = Field(None, ge=0)
    lead_id: Optional[str] = None
    deal_name: Optional[str] = None
    touchpoints: List[TouchpointSchema] = Field(default_factory=list)
    closed_at: Optional[str] = Field(None, description="ISO timestamp")
    rep_id: Optional[str] = None
    rep_name: Optional[str] = None
    primary_campaign: Optional[str] = None
    primary_source: Optional[str] = None


class AddTouchpointRequest(BaseModel):
    """Request to add a touchpoint to existing attribution."""
    touchpoint_type: str
    channel: str
    timestamp: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AttributionResponse(BaseModel):
    """Deal attribution response."""
    id: str
    deal_id: str
    lead_id: Optional[str]
    deal_name: Optional[str]
    deal_value: Optional[float]
    closed_at: Optional[str]
    touchpoints: List[Dict[str, Any]]
    total_touches: int
    days_in_pipeline: Optional[int]
    first_touch_channel: Optional[str]
    last_touch_channel: Optional[str]
    first_touch_value: Optional[float]
    last_touch_value: Optional[float]
    linear_touch_value: Optional[float]
    time_decay_value: Optional[float]
    rep_id: Optional[str]
    rep_name: Optional[str]
    primary_campaign: Optional[str]
    primary_source: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class AttributionListResponse(BaseModel):
    """List of attributions."""
    attributions: List[AttributionResponse]
    total: int


class ChannelPerformanceResponse(BaseModel):
    """Channel performance metrics."""
    channel: str
    deal_count: int
    total_value: float
    attributed_value: float
    avg_days_to_close: Optional[float]


class RepPerformanceResponse(BaseModel):
    """Rep performance metrics."""
    rep_id: str
    rep_name: Optional[str]
    deal_count: int
    total_value: float
    avg_deal_value: float
    avg_days_to_close: Optional[float]
    avg_touches: Optional[float]


class ActivityROIResponse(BaseModel):
    """Activity ROI metrics."""
    activity_type: str
    touch_count: int
    deals_influenced: int
    total_attributed_value: float
    avg_value_per_touch: float


class TouchpointTypeResponse(BaseModel):
    """Touchpoint type definition."""
    id: str
    name: str
    channel: str
    description: Optional[str]
    default_weight: float


# Endpoints
@router.post("/deals", response_model=AttributionResponse, status_code=201)
async def create_attribution(
    request: CreateAttributionRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Create attribution record for a closed deal.

    Example:
    ```json
    {
        "deal_id": "deal_12345",
        "deal_value": 50000,
        "deal_name": "Acme Corp - Enterprise",
        "touchpoints": [
            {"type": "email_sent", "channel": "email", "timestamp": "2025-01-01T10:00:00Z"},
            {"type": "call_completed", "channel": "call", "timestamp": "2025-01-15T14:00:00Z"},
            {"type": "demo_completed", "channel": "demo", "timestamp": "2025-01-20T11:00:00Z"}
        ],
        "rep_id": "rep_001",
        "rep_name": "John Smith"
    }
    ```
    """
    service = AttributionService(db)

    lead_uuid = None
    if request.lead_id:
        try:
            lead_uuid = UUID(request.lead_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid lead_id format")

    closed_at = None
    if request.closed_at:
        try:
            closed_at = datetime.fromisoformat(request.closed_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid closed_at format")

    attribution = await service.create_attribution(
        deal_id=request.deal_id,
        deal_value=request.deal_value,
        lead_id=lead_uuid,
        deal_name=request.deal_name,
        touchpoints=[tp.model_dump() for tp in request.touchpoints],
        closed_at=closed_at,
        rep_id=request.rep_id,
        rep_name=request.rep_name,
        primary_campaign=request.primary_campaign,
        primary_source=request.primary_source,
    )

    return AttributionResponse(**attribution.to_dict())


@router.get("/deals", response_model=AttributionListResponse)
async def list_attributions(
    start_date: Optional[str] = Query(None, description="Filter by close date start (ISO)"),
    end_date: Optional[str] = Query(None, description="Filter by close date end (ISO)"),
    rep_id: Optional[str] = Query(None, description="Filter by rep ID"),
    channel: Optional[str] = Query(None, description="Filter by channel"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db),
):
    """List deal attributions with optional filters."""
    service = AttributionService(db)

    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    attributions = await service.list_attributions(
        limit=limit,
        offset=offset,
        start_date=start_dt,
        end_date=end_dt,
        rep_id=rep_id,
        channel=channel,
    )

    return AttributionListResponse(
        attributions=[AttributionResponse(**a.to_dict()) for a in attributions],
        total=len(attributions),
    )


@router.get("/deals/{deal_id}", response_model=AttributionResponse)
async def get_attribution(
    deal_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get attribution for a specific deal."""
    service = AttributionService(db)
    attribution = await service.get_attribution_by_deal(deal_id)

    if not attribution:
        raise HTTPException(status_code=404, detail=f"Attribution for deal {deal_id} not found")

    return AttributionResponse(**attribution.to_dict())


@router.post("/deals/{deal_id}/touchpoints", response_model=AttributionResponse)
async def add_touchpoint(
    deal_id: str,
    request: AddTouchpointRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """Add a touchpoint to an existing deal attribution."""
    service = AttributionService(db)

    timestamp = None
    if request.timestamp:
        try:
            timestamp = datetime.fromisoformat(request.timestamp.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")

    attribution = await service.add_touchpoint(
        deal_id=deal_id,
        touchpoint_type=request.touchpoint_type,
        channel=request.channel,
        timestamp=timestamp,
        metadata=request.metadata,
    )

    if not attribution:
        raise HTTPException(status_code=404, detail=f"Attribution for deal {deal_id} not found")

    return AttributionResponse(**attribution.to_dict())


@router.get("/channels", response_model=List[ChannelPerformanceResponse])
async def get_channel_performance(
    start_date: Optional[str] = Query(None, description="Filter by close date start"),
    end_date: Optional[str] = Query(None, description="Filter by close date end"),
    model: str = Query("last_touch", description="Attribution model (first_touch, last_touch, linear, time_decay)"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get revenue attribution by channel.

    Returns total deal value attributed to each channel based on the selected model.
    """
    service = AttributionService(db)

    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    results = await service.get_channel_performance(
        start_date=start_dt,
        end_date=end_dt,
        model=model,
    )

    return [ChannelPerformanceResponse(**r) for r in results]


@router.get("/reps", response_model=List[RepPerformanceResponse])
async def get_rep_performance(
    start_date: Optional[str] = Query(None, description="Filter by close date start"),
    end_date: Optional[str] = Query(None, description="Filter by close date end"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get deal performance by sales rep.

    Returns deals closed, total value, average deal size, and efficiency metrics.
    """
    service = AttributionService(db)

    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    results = await service.get_rep_performance(
        start_date=start_dt,
        end_date=end_dt,
    )

    return [RepPerformanceResponse(**r) for r in results]


@router.get("/roi", response_model=List[ActivityROIResponse])
async def get_activity_roi(
    start_date: Optional[str] = Query(None, description="Filter by close date start"),
    end_date: Optional[str] = Query(None, description="Filter by close date end"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get ROI metrics by activity type.

    Returns how much revenue each activity type influenced.
    """
    service = AttributionService(db)

    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid start_date format")
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    results = await service.get_roi_by_activity(
        start_date=start_dt,
        end_date=end_dt,
    )

    return [ActivityROIResponse(**r) for r in results]


@router.get("/touchpoint-types", response_model=List[TouchpointTypeResponse])
async def list_touchpoint_types(
    db: AsyncSession = Depends(get_async_db),
):
    """List all available touchpoint types with their default weights."""
    service = AttributionService(db)
    types = await service.get_touchpoint_types()

    return [TouchpointTypeResponse(**t.to_dict()) for t in types]


@router.get("/summary")
async def get_attribution_summary(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get high-level attribution summary for dashboard.

    Returns:
    - Total deals and revenue
    - Top performing channels
    - Top performing reps
    - Average metrics
    """
    service = AttributionService(db)

    start_dt = None
    end_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if end_date:
        try:
            end_dt = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            pass

    # Get all data
    attributions = await service.list_attributions(
        limit=1000,
        start_date=start_dt,
        end_date=end_dt,
    )

    if not attributions:
        return {
            "total_deals": 0,
            "total_revenue": 0,
            "avg_deal_value": 0,
            "avg_days_to_close": None,
            "avg_touches_per_deal": 0,
            "top_channels": [],
            "top_reps": [],
        }

    # Calculate summary
    total_deals = len(attributions)
    total_revenue = sum(float(a.deal_value or 0) for a in attributions)
    avg_deal_value = total_revenue / total_deals if total_deals > 0 else 0

    days_list = [a.days_in_pipeline for a in attributions if a.days_in_pipeline]
    avg_days = sum(days_list) / len(days_list) if days_list else None

    avg_touches = sum(a.total_touches for a in attributions) / total_deals if total_deals > 0 else 0

    # Get top channels and reps
    channels = await service.get_channel_performance(start_date=start_dt, end_date=end_dt)
    reps = await service.get_rep_performance(start_date=start_dt, end_date=end_dt)

    return {
        "total_deals": total_deals,
        "total_revenue": round(total_revenue, 2),
        "avg_deal_value": round(avg_deal_value, 2),
        "avg_days_to_close": round(avg_days, 1) if avg_days else None,
        "avg_touches_per_deal": round(avg_touches, 1),
        "top_channels": channels[:5],
        "top_reps": reps[:5],
    }
