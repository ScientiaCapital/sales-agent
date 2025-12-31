"""
Call Insights API endpoints.

Provides REST endpoints for:
- Retrieving call analysis insights
- Triggering manual analysis
- Querying insights by lead/sentiment/outcome
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_async_db
from app.services.intelligence import CallInsightsService
from app.tasks.call_analysis_tasks import analyze_call_recording

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/calls", tags=["call-intelligence"])


# Response Models
class InsightResponse(BaseModel):
    """Call insight response."""
    id: str
    voice_session_id: Optional[str]
    lead_id: Optional[str]
    transcript: Optional[str]
    summary: Optional[str]
    sentiment_score: Optional[float]
    sentiment_label: Optional[str]
    objections: List[str]
    buying_signals: List[str]
    action_items: List[str]
    competitors_mentioned: List[str]
    key_topics: List[str]
    call_score: Optional[int]
    talk_ratio: Optional[float]
    duration_seconds: Optional[int]
    outcome: Optional[str]
    analyzed_at: Optional[str]

    class Config:
        from_attributes = True


class AnalyzeRequest(BaseModel):
    """Request to analyze a call."""
    audio_url: str = Field(..., description="URL to the call recording")
    lead_id: Optional[str] = Field(None, description="Optional lead ID")


class AnalyzeResponse(BaseModel):
    """Response from analysis request."""
    task_id: str
    voice_session_id: str
    status: str = "queued"


class InsightListResponse(BaseModel):
    """List of insights response."""
    insights: List[InsightResponse]
    total: int


# Endpoints
@router.get("/{session_id}/insights", response_model=InsightResponse)
async def get_call_insights(
    session_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get insights for a specific call.

    Returns analyzed call data including sentiment, objections, buying signals.
    """
    service = CallInsightsService(db)
    insight = await service.get_insight_by_session(session_id)

    if not insight:
        raise HTTPException(
            status_code=404,
            detail=f"No insights found for session {session_id}"
        )

    return InsightResponse(**insight.to_dict())


@router.post("/{session_id}/analyze", response_model=AnalyzeResponse)
async def analyze_call(
    session_id: str,
    request: AnalyzeRequest,
):
    """
    Trigger analysis of a call recording.

    Queues a Celery task to analyze the recording asynchronously.
    """
    task = analyze_call_recording.delay(
        voice_session_id=session_id,
        audio_url=request.audio_url,
        lead_id=request.lead_id,
    )

    logger.info(f"Queued analysis for {session_id}, task {task.id}")

    return AnalyzeResponse(
        task_id=task.id,
        voice_session_id=session_id,
        status="queued",
    )


@router.get("/insights", response_model=InsightListResponse)
async def list_insights(
    sentiment: Optional[str] = Query(None, description="Filter by sentiment"),
    outcome: Optional[str] = Query(None, description="Filter by outcome"),
    min_score: Optional[int] = Query(None, ge=0, le=100, description="Minimum call score"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_async_db),
):
    """
    List call insights with optional filters.

    Supports filtering by sentiment, outcome, and minimum call score.
    """
    service = CallInsightsService(db)

    if sentiment:
        insights = await service.get_insights_by_sentiment(sentiment, limit)
    elif outcome:
        insights = await service.get_insights_by_outcome(outcome, limit)
    else:
        insights = await service.get_recent_insights(limit, min_score)

    return InsightListResponse(
        insights=[InsightResponse(**i.to_dict()) for i in insights],
        total=len(insights),
    )


@router.get("/leads/{lead_id}/call-history", response_model=InsightListResponse)
async def get_lead_call_history(
    lead_id: str,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_async_db),
):
    """
    Get all call insights for a specific lead.

    Returns chronological list of analyzed calls.
    """
    try:
        lead_uuid = UUID(lead_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid lead ID format")

    service = CallInsightsService(db)
    insights = await service.get_insights_for_lead(lead_uuid, limit, offset)

    return InsightListResponse(
        insights=[InsightResponse(**i.to_dict()) for i in insights],
        total=len(insights),
    )


@router.get("/insights/{insight_id}", response_model=InsightResponse)
async def get_insight_by_id(
    insight_id: str,
    db: AsyncSession = Depends(get_async_db),
):
    """Get a specific insight by ID."""
    try:
        insight_uuid = UUID(insight_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid insight ID format")

    service = CallInsightsService(db)
    insight = await service.get_insight_by_id(insight_uuid)

    if not insight:
        raise HTTPException(
            status_code=404,
            detail=f"Insight {insight_id} not found"
        )

    return InsightResponse(**insight.to_dict())
