"""
Buyer Intent API endpoints.

Provides REST endpoints for buyer intent scoring:
- Hot leads (high intent score)
- Signal tracking and recording
- Intent score calculation
"""
import logging
from typing import List, Optional, Dict, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_async_db
from app.models.buyer_intent import IntentSignalType, IntentSignalSource
from app.services.intent_scoring_service import IntentScoringService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intent", tags=["buyer-intent"])


# Request/Response Models
class RecordSignalRequest(BaseModel):
    """Request to record an intent signal."""
    lead_id: str = Field(..., description="Lead UUID")
    signal_type: str = Field(
        ...,
        description="Signal type (email_opened, reply_positive, call_scheduled, etc.)"
    )
    source: str = Field(
        ...,
        description="Signal source (email, website, linkedin, call)"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict,
        description="Additional context (email_id, page_url, etc.)"
    )
    weight_override: Optional[float] = Field(
        None,
        ge=-10,
        le=10,
        description="Override default signal weight"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "lead_id": "550e8400-e29b-41d4-a716-446655440000",
                "signal_type": "reply_positive",
                "source": "email",
                "metadata": {"email_id": "msg_123", "campaign": "Q4_outreach"}
            }
        }


class SignalResponse(BaseModel):
    """Intent signal response."""
    id: str
    lead_id: str
    signal_type: str
    signal_weight: float
    source: str
    metadata: Dict[str, Any]
    created_at: Optional[str]


class SignalListResponse(BaseModel):
    """Paginated list of signals."""
    signals: List[SignalResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class HotLeadResponse(BaseModel):
    """Hot lead with intent data."""
    id: str
    name: str
    state: Optional[str]
    city: Optional[str]
    icp_tier: Optional[str]
    icp_score: float
    intent_score: float
    intent_updated_at: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    recent_signals_7d: int
    last_signal_type: Optional[str]
    last_signal_at: Optional[str]


class HotLeadListResponse(BaseModel):
    """Paginated list of hot leads."""
    leads: List[HotLeadResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class IntentScoreResponse(BaseModel):
    """Intent score calculation response."""
    lead_id: str
    intent_score: float
    calculated_at: str


class SignalTypeStats(BaseModel):
    """Statistics for a signal type."""
    count: int
    total_weight: float
    last_at: Optional[str]


class SignalSummaryResponse(BaseModel):
    """Signal summary for a lead."""
    lead_id: str
    period_days: int
    total_signals: int
    total_weight: float
    signals_by_type: Dict[str, SignalTypeStats]


class BatchRecalculateRequest(BaseModel):
    """Request to batch recalculate intent scores."""
    lead_ids: Optional[List[str]] = Field(
        None,
        description="List of lead UUIDs to recalculate (None = all)"
    )
    min_signals: int = Field(
        1,
        ge=1,
        description="Minimum signal count to include"
    )


class BatchRecalculateResponse(BaseModel):
    """Batch recalculate response."""
    status: str
    leads_updated: int


class SignalTypesResponse(BaseModel):
    """Available signal types and weights."""
    signal_types: Dict[str, float]
    sources: List[str]


# Endpoints
@router.get("/hot-leads", response_model=HotLeadListResponse)
async def get_hot_leads(
    min_score: float = Query(50.0, ge=0, le=100, description="Min intent score"),
    state: Optional[str] = Query(None, description="Filter by state"),
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get leads with high intent scores.

    Returns leads sorted by intent score, with recent signal activity.
    High intent indicates strong buying signals from email engagement,
    replies, or call scheduling.
    """
    service = IntentScoringService(db)
    result = await service.get_hot_leads(
        min_score=min_score,
        state=state,
        limit=limit,
        offset=offset,
    )

    leads = [
        HotLeadResponse(**lead)
        for lead in result["leads"]
    ]

    return HotLeadListResponse(
        leads=leads,
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        has_more=result["has_more"],
    )


@router.get("/signals/{lead_id}", response_model=SignalListResponse)
async def get_lead_signals(
    lead_id: str,
    limit: int = Query(50, ge=1, le=200, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get all intent signals for a specific lead.

    Returns chronological list of engagement signals.
    """
    try:
        lead_uuid = UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lead ID format")

    service = IntentScoringService(db)
    result = await service.get_signals_for_lead(
        lead_id=lead_uuid,
        limit=limit,
        offset=offset,
    )

    signals = [
        SignalResponse(**s)
        for s in result["signals"]
    ]

    return SignalListResponse(
        signals=signals,
        total=result["total"],
        limit=result["limit"],
        offset=result["offset"],
        has_more=result["has_more"],
    )


@router.get("/signals/{lead_id}/summary", response_model=SignalSummaryResponse)
async def get_signal_summary(
    lead_id: str,
    days: int = Query(30, ge=1, le=90, description="Lookback period"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get signal summary statistics for a lead.

    Returns aggregated signal counts by type.
    """
    try:
        lead_uuid = UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lead ID format")

    service = IntentScoringService(db)
    summary = await service.get_signal_summary(
        lead_id=lead_uuid,
        days=days,
    )

    return SignalSummaryResponse(
        lead_id=summary["lead_id"],
        period_days=summary["period_days"],
        total_signals=summary["total_signals"],
        total_weight=summary["total_weight"],
        signals_by_type={
            k: SignalTypeStats(**v)
            for k, v in summary["signals_by_type"].items()
        },
    )


@router.post("/signals", response_model=SignalResponse, status_code=201)
async def record_signal(
    request: RecordSignalRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Record a new intent signal for a lead.

    The lead's intent_score is automatically updated via database trigger.

    Signal types and weights:
    - email_opened: 1.0
    - email_opened_3x: 3.0
    - link_clicked: 4.0
    - reply_positive: 5.0
    - reply_question: 3.5
    - reply_pricing: 4.5
    - response_under_1h: 2.0
    - call_scheduled: 5.0
    - demo_requested: 7.0
    - meeting_booked: 8.0
    """
    try:
        lead_uuid = UUID(request.lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lead ID format")

    service = IntentScoringService(db)

    try:
        signal = await service.record_intent_signal(
            lead_id=lead_uuid,
            signal_type=request.signal_type,
            source=request.source,
            metadata=request.metadata,
            weight_override=request.weight_override,
        )
    except Exception as e:
        logger.error(f"Failed to record signal: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    return SignalResponse(**signal.to_dict())


@router.post("/calculate/{lead_id}", response_model=IntentScoreResponse)
async def calculate_intent_score(
    lead_id: str,
    force_update: bool = Query(True, description="Update dim_companies"),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Recalculate intent score for a lead.

    Uses time-decayed weighted sum of signals.
    If force_update=True, updates the intent_score in dim_companies.
    """
    try:
        lead_uuid = UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lead ID format")

    service = IntentScoringService(db)
    score = await service.calculate_intent_score(
        lead_id=lead_uuid,
        force_update=force_update,
    )

    from datetime import datetime
    return IntentScoreResponse(
        lead_id=lead_id,
        intent_score=score,
        calculated_at=datetime.utcnow().isoformat(),
    )


@router.post("/batch-recalculate", response_model=BatchRecalculateResponse)
async def batch_recalculate_scores(
    request: BatchRecalculateRequest,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Recalculate intent scores for multiple leads.

    If lead_ids not provided, recalculates for all leads with signals.
    """
    service = IntentScoringService(db)

    lead_uuids = None
    if request.lead_ids:
        try:
            lead_uuids = [UUID(lid) for lid in request.lead_ids]
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid lead ID format")

    result = await service.batch_recalculate_scores(
        lead_ids=lead_uuids,
        min_signals=request.min_signals,
    )

    return BatchRecalculateResponse(**result)


@router.get("/signal-types", response_model=SignalTypesResponse)
async def get_signal_types():
    """
    Get available signal types and their default weights.

    Use these values when recording signals.
    """
    from app.models.buyer_intent import INTENT_SIGNAL_WEIGHTS

    return SignalTypesResponse(
        signal_types=INTENT_SIGNAL_WEIGHTS,
        sources=[s.value for s in IntentSignalSource],
    )
