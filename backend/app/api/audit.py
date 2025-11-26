"""
Lead Audit Trail API endpoints for GTM agents.

Provides query access to the lead audit log, enabling GTM agents
to understand context about leads:
- What happened to this lead?
- Why was this lead skipped/merged?
- What happened in this pipeline run?

Usage by GTM agents:
    GET /api/v1/audit/lead/{company_name}  # Full lead history
    GET /api/v1/audit/session/{session_id}  # Pipeline run summary
    GET /api/v1/audit/dedup/{company_name}  # Deduplication decisions only
    GET /api/v1/audit/recent?hours=24  # Recent activity
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from app.models.database import get_async_db
from app.services.lead_audit_service import LeadAuditService
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/audit", tags=["audit"])


# =========================================================================
# Response Models
# =========================================================================

class AuditEventResponse(BaseModel):
    """Single audit event response."""
    id: str
    lead_id: Optional[str] = None
    company_name: str
    session_id: str
    event_type: str
    stage: str
    decision_data: dict
    source_file: Optional[str] = None
    source_row: Optional[int] = None
    created_at: datetime
    created_by: str
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None

    class Config:
        from_attributes = True


class SessionSummaryResponse(BaseModel):
    """Pipeline session summary response."""
    session_id: str
    total_events: int
    companies_processed: int
    by_event_type: dict
    by_stage: dict
    total_cost_usd: float
    total_latency_ms: int
    first_event: Optional[str] = None
    last_event: Optional[str] = None


class LeadHistoryResponse(BaseModel):
    """Lead history response with all events."""
    company_name: str
    event_count: int
    events: List[AuditEventResponse]


class RecentlyProcessedResponse(BaseModel):
    """Response for recently processed check."""
    company_name: str
    was_recently_processed: bool
    hours_checked: int


# =========================================================================
# Dependency
# =========================================================================

async def get_audit_service(db: AsyncSession = Depends(get_async_db)) -> LeadAuditService:
    """Dependency to get audit service with async session."""
    return LeadAuditService(db)


# =========================================================================
# Endpoints
# =========================================================================

@router.get("/lead/{company_name}", response_model=LeadHistoryResponse)
async def get_lead_history(
    company_name: str,
    limit: int = Query(100, ge=1, le=1000),
    audit_service: LeadAuditService = Depends(get_audit_service)
):
    """
    Get full audit history for a lead by company name.

    Used by GTM agents to understand what happened to a company:
    - Import source and row number
    - Qualification score and tier
    - Enrichment sources tried
    - Deduplication decisions
    - Export status

    Args:
        company_name: Company name to search (exact match)
        limit: Maximum events to return (default 100)

    Returns:
        LeadHistoryResponse with all audit events for this company
    """
    logger.info(f"Fetching audit history for company: {company_name}")

    try:
        events = await audit_service.get_lead_history(
            company_name=company_name,
            limit=limit
        )

        return LeadHistoryResponse(
            company_name=company_name,
            event_count=len(events),
            events=[
                AuditEventResponse(
                    id=str(event.id),
                    lead_id=str(event.lead_id) if event.lead_id else None,
                    company_name=event.company_name,
                    session_id=event.session_id,
                    event_type=event.event_type,
                    stage=event.stage,
                    decision_data=event.decision_data or {},
                    source_file=event.source_file,
                    source_row=event.source_row,
                    created_at=event.created_at,
                    created_by=event.created_by,
                    latency_ms=event.latency_ms,
                    cost_usd=float(event.cost_usd) if event.cost_usd else None
                )
                for event in events
            ]
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error fetching lead history: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch lead history")


@router.get("/session/{session_id}", response_model=SessionSummaryResponse)
async def get_session_summary(
    session_id: str,
    audit_service: LeadAuditService = Depends(get_audit_service)
):
    """
    Get summary statistics for a pipeline session.

    Used by GTM agents to understand pipeline run performance:
    - Total events and companies processed
    - Breakdown by event type and stage
    - Total costs and latency
    - Time range of the run

    Args:
        session_id: Pipeline execution session ID

    Returns:
        SessionSummaryResponse with aggregate statistics
    """
    logger.info(f"Fetching session summary: {session_id}")

    try:
        summary = await audit_service.get_session_summary(session_id=session_id)
        return SessionSummaryResponse(**summary)
    except Exception as e:
        logger.error(f"Error fetching session summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch session summary")


@router.get("/dedup/{company_name}", response_model=LeadHistoryResponse)
async def get_dedup_decisions(
    company_name: str,
    audit_service: LeadAuditService = Depends(get_audit_service)
):
    """
    Get all deduplication decisions for a company.

    Used by GTM agents to understand why a company was:
    - Created as new lead
    - Added as contact to existing lead
    - Skipped as duplicate
    - Updated with new data

    Args:
        company_name: Company name to search

    Returns:
        LeadHistoryResponse with only dedup events
    """
    logger.info(f"Fetching dedup decisions for company: {company_name}")

    try:
        events = await audit_service.get_dedup_decisions(company_name=company_name)

        return LeadHistoryResponse(
            company_name=company_name,
            event_count=len(events),
            events=[
                AuditEventResponse(
                    id=str(event.id),
                    lead_id=str(event.lead_id) if event.lead_id else None,
                    company_name=event.company_name,
                    session_id=event.session_id,
                    event_type=event.event_type,
                    stage=event.stage,
                    decision_data=event.decision_data or {},
                    source_file=event.source_file,
                    source_row=event.source_row,
                    created_at=event.created_at,
                    created_by=event.created_by,
                    latency_ms=event.latency_ms,
                    cost_usd=float(event.cost_usd) if event.cost_usd else None
                )
                for event in events
            ]
        )
    except Exception as e:
        logger.error(f"Error fetching dedup decisions: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch dedup decisions")


@router.get("/recent", response_model=List[AuditEventResponse])
async def get_recent_activity(
    hours: int = Query(24, ge=1, le=168),
    event_types: Optional[str] = Query(None, description="Comma-separated event types to filter"),
    limit: int = Query(100, ge=1, le=1000),
    audit_service: LeadAuditService = Depends(get_audit_service)
):
    """
    Get recent audit activity.

    Used for monitoring dashboards and GTM agent awareness:
    - What's been processed recently?
    - Any failures or issues?
    - Activity volume by type

    Args:
        hours: Time window in hours (default 24, max 168)
        event_types: Comma-separated filter (e.g., "lead_qualified,lead_enriched")
        limit: Maximum events to return (default 100)

    Returns:
        List of recent audit events
    """
    logger.info(f"Fetching recent activity: hours={hours}, limit={limit}")

    try:
        # Parse event_types if provided
        event_type_list = None
        if event_types:
            event_type_list = [et.strip() for et in event_types.split(",")]

        events = await audit_service.get_recent_activity(
            hours=hours,
            event_types=event_type_list,
            limit=limit
        )

        return [
            AuditEventResponse(
                id=str(event.id),
                lead_id=str(event.lead_id) if event.lead_id else None,
                company_name=event.company_name,
                session_id=event.session_id,
                event_type=event.event_type,
                stage=event.stage,
                decision_data=event.decision_data or {},
                source_file=event.source_file,
                source_row=event.source_row,
                created_at=event.created_at,
                created_by=event.created_by,
                latency_ms=event.latency_ms,
                cost_usd=float(event.cost_usd) if event.cost_usd else None
            )
            for event in events
        ]
    except Exception as e:
        logger.error(f"Error fetching recent activity: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch recent activity")


@router.get("/check/{company_name}", response_model=RecentlyProcessedResponse)
async def check_recently_processed(
    company_name: str,
    hours: int = Query(24, ge=1, le=168),
    audit_service: LeadAuditService = Depends(get_audit_service)
):
    """
    Check if a company was processed recently.

    Used to prevent duplicate processing within a time window:
    - GTM agents check before re-processing
    - Batch imports skip recently processed leads

    Args:
        company_name: Company name to check
        hours: Time window in hours (default 24)

    Returns:
        RecentlyProcessedResponse with boolean result
    """
    logger.info(f"Checking if recently processed: {company_name} (last {hours}h)")

    try:
        was_processed = await audit_service.check_recently_processed(
            company_name=company_name,
            hours=hours
        )

        return RecentlyProcessedResponse(
            company_name=company_name,
            was_recently_processed=was_processed,
            hours_checked=hours
        )
    except Exception as e:
        logger.error(f"Error checking recently processed: {e}")
        raise HTTPException(status_code=500, detail="Failed to check processing status")
