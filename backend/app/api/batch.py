"""
Batch Processing API Router

REST API and WebSocket endpoints for batch lead processing:
- POST /batch/start - Start a new batch job
- GET /batch/{id} - Get batch status
- POST /batch/{id}/pause - Pause running batch
- POST /batch/{id}/resume - Resume paused batch
- POST /batch/{id}/cancel - Cancel batch
- GET /batch/{id}/leads - List leads with status
- WS /batch/ws/{id} - Real-time progress updates

Rate Limiting:
- All endpoints respect Apollo/Hunter quotas via BatchRateLimiter
- Rate limit status available at GET /batch/rate-limits
"""

import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Depends, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.batch_job import BatchJob, BatchJobLead
from app.core.logging import setup_logging
from app.services.batch_rate_limiter import create_rate_limiter

logger = setup_logging(__name__)

router = APIRouter(prefix="/batch", tags=["batch"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class BatchStartRequest(BaseModel):
    """Request to start a new batch job."""
    name: str = Field(..., description="Batch job name", max_length=255)
    company_ids: List[str] = Field(..., description="List of company UUIDs to process")
    priority: str = Field("medium", description="Priority: high, medium, low")
    options: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Pipeline options (skip_enrichment, skip_marketing, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "name": "December Enrichment Batch",
                "company_ids": ["uuid1", "uuid2", "uuid3"],
                "priority": "high",
                "options": {"skip_marketing": True}
            }
        }


class BatchStatusResponse(BaseModel):
    """Response with batch job status."""
    id: str
    name: str
    status: str
    priority: str
    total_leads: int
    processed_leads: int
    successful_leads: int
    failed_leads: int
    skipped_leads: int
    percent_complete: float
    created_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]


class BatchLeadResponse(BaseModel):
    """Response for a single lead in a batch."""
    id: str
    company_id: str
    status: str
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    error_message: Optional[str]
    retry_count: int
    latency_ms: Optional[int]
    cost_usd: Optional[float]


class RateLimitStatusResponse(BaseModel):
    """Response with rate limit status."""
    apollo: Dict[str, Any]
    hunter: Dict[str, Any]
    browserbase: Dict[str, Any]
    redis_connected: bool


# ============================================================================
# API ENDPOINTS
# ============================================================================

@router.post("/start", response_model=Dict[str, Any])
async def start_batch(
    request: BatchStartRequest,
    db: Session = Depends(get_db)
):
    """
    Start a new batch processing job.

    Creates a batch job record and dispatches leads to Celery workers.
    Leads are processed in parallel (up to 10 concurrent) with rate limiting.

    Args:
        request: Batch start request with company IDs and options

    Returns:
        Dictionary with batch_id and initial status
    """
    logger.info(f"Starting batch '{request.name}' with {len(request.company_ids)} leads")

    # Validate priority
    if request.priority not in ("high", "medium", "low"):
        raise HTTPException(status_code=400, detail="Priority must be high, medium, or low")

    # Check rate limits before starting
    rate_limiter = create_rate_limiter()
    apollo_remaining = await rate_limiter.get_apollo_remaining()

    if apollo_remaining["day"] < len(request.company_ids):
        raise HTTPException(
            status_code=429,
            detail=f"Insufficient Apollo quota. Need {len(request.company_ids)}, have {apollo_remaining['day']} daily remaining."
        )

    try:
        # Create batch job record
        batch_job = BatchJob(
            name=request.name,
            status="pending",
            total_leads=len(request.company_ids),
            priority=request.priority,
            options_json=request.options or {},
        )
        db.add(batch_job)
        db.commit()
        db.refresh(batch_job)

        batch_id = str(batch_job.id)

        # Create lead records
        for company_id in request.company_ids:
            lead = BatchJobLead(
                batch_job_id=batch_job.id,
                company_id=company_id,
                status="pending",
            )
            db.add(lead)
        db.commit()

        # Dispatch to Celery
        from app.tasks.batch_tasks import start_batch_task
        start_batch_task.delay(
            batch_id=batch_id,
            company_ids=request.company_ids,
            options=request.options,
            priority=request.priority,
        )

        logger.info(f"Batch {batch_id} created and dispatched")

        return {
            "batch_id": batch_id,
            "status": "pending",
            "total_leads": len(request.company_ids),
            "priority": request.priority,
            "message": "Batch job created and processing started",
        }

    except Exception as e:
        logger.error(f"Failed to start batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{batch_id}", response_model=BatchStatusResponse)
async def get_batch_status(
    batch_id: str,
    db: Session = Depends(get_db)
):
    """
    Get the status of a batch job.

    Args:
        batch_id: UUID of the batch job

    Returns:
        BatchStatusResponse with current status and progress
    """
    batch_job = db.query(BatchJob).filter(BatchJob.id == batch_id).first()

    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch job {batch_id} not found")

    return BatchStatusResponse(
        id=str(batch_job.id),
        name=batch_job.name,
        status=batch_job.status,
        priority=batch_job.priority or "medium",
        total_leads=batch_job.total_leads,
        processed_leads=batch_job.processed_leads or 0,
        successful_leads=batch_job.successful_leads or 0,
        failed_leads=batch_job.failed_leads or 0,
        skipped_leads=batch_job.skipped_leads or 0,
        percent_complete=batch_job.percent_complete,
        created_at=batch_job.created_at,
        started_at=batch_job.started_at,
        completed_at=batch_job.completed_at,
        error_message=batch_job.error_message,
    )


@router.get("/{batch_id}/leads", response_model=List[BatchLeadResponse])
async def get_batch_leads(
    batch_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(100, le=1000),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    """
    Get leads in a batch job with their status.

    Args:
        batch_id: UUID of the batch job
        status: Optional status filter (pending, processing, completed, failed, skipped)
        limit: Max results (default 100, max 1000)
        offset: Pagination offset

    Returns:
        List of BatchLeadResponse objects
    """
    query = db.query(BatchJobLead).filter(BatchJobLead.batch_job_id == batch_id)

    if status:
        query = query.filter(BatchJobLead.status == status)

    leads = query.order_by(BatchJobLead.started_at.desc()).offset(offset).limit(limit).all()

    return [
        BatchLeadResponse(
            id=str(lead.id),
            company_id=str(lead.company_id),
            status=lead.status,
            started_at=lead.started_at,
            completed_at=lead.completed_at,
            error_message=lead.error_message,
            retry_count=lead.retry_count or 0,
            latency_ms=lead.latency_ms,
            cost_usd=float(lead.cost_usd) if lead.cost_usd else None,
        )
        for lead in leads
    ]


@router.post("/{batch_id}/pause")
async def pause_batch(
    batch_id: str,
    db: Session = Depends(get_db)
):
    """
    Pause a running batch job.

    Stops processing new leads but allows in-progress leads to complete.

    Args:
        batch_id: UUID of the batch job

    Returns:
        Status confirmation
    """
    batch_job = db.query(BatchJob).filter(BatchJob.id == batch_id).first()

    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch job {batch_id} not found")

    if batch_job.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause batch in '{batch_job.status}' status"
        )

    from app.tasks.batch_tasks import pause_batch_task
    result = pause_batch_task.delay(batch_id)

    return {"batch_id": batch_id, "status": "pausing", "task_id": result.id}


@router.post("/{batch_id}/resume")
async def resume_batch(
    batch_id: str,
    db: Session = Depends(get_db)
):
    """
    Resume a paused batch job.

    Args:
        batch_id: UUID of the batch job

    Returns:
        Status confirmation
    """
    batch_job = db.query(BatchJob).filter(BatchJob.id == batch_id).first()

    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch job {batch_id} not found")

    if batch_job.status != "paused":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume batch in '{batch_job.status}' status"
        )

    from app.tasks.batch_tasks import resume_batch_task
    result = resume_batch_task.delay(batch_id)

    return {"batch_id": batch_id, "status": "resuming", "task_id": result.id}


@router.post("/{batch_id}/cancel")
async def cancel_batch(
    batch_id: str,
    db: Session = Depends(get_db)
):
    """
    Cancel a batch job.

    Stops all processing and marks remaining leads as skipped.

    Args:
        batch_id: UUID of the batch job

    Returns:
        Status confirmation
    """
    batch_job = db.query(BatchJob).filter(BatchJob.id == batch_id).first()

    if not batch_job:
        raise HTTPException(status_code=404, detail=f"Batch job {batch_id} not found")

    if batch_job.status in ("completed", "completed_with_errors", "failed", "cancelled"):
        raise HTTPException(
            status_code=400,
            detail=f"Batch already in terminal state: {batch_job.status}"
        )

    from app.tasks.batch_tasks import cancel_batch_task
    result = cancel_batch_task.delay(batch_id)

    return {"batch_id": batch_id, "status": "cancelling", "task_id": result.id}


@router.get("/rate-limits/status", response_model=RateLimitStatusResponse)
async def get_rate_limit_status():
    """
    Get current rate limit status for all services.

    Returns:
        RateLimitStatusResponse with Apollo, Hunter, Browserbase quotas
    """
    rate_limiter = create_rate_limiter()
    status = await rate_limiter.get_status()

    return RateLimitStatusResponse(
        apollo=status["apollo"],
        hunter=status["hunter"],
        browserbase=status["browserbase"],
        redis_connected=status["redis_connected"],
    )


@router.get("/")
async def list_batches(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
    db: Session = Depends(get_db)
):
    """
    List all batch jobs.

    Args:
        status: Optional status filter
        limit: Max results (default 20, max 100)
        offset: Pagination offset

    Returns:
        List of batch jobs with summary info
    """
    query = db.query(BatchJob)

    if status:
        query = query.filter(BatchJob.status == status)

    batches = query.order_by(BatchJob.created_at.desc()).offset(offset).limit(limit).all()

    return [
        {
            "id": str(batch.id),
            "name": batch.name,
            "status": batch.status,
            "priority": batch.priority,
            "total_leads": batch.total_leads,
            "processed_leads": batch.processed_leads or 0,
            "percent_complete": batch.percent_complete,
            "created_at": batch.created_at.isoformat() if batch.created_at else None,
        }
        for batch in batches
    ]


# ============================================================================
# WEBSOCKET ENDPOINT
# ============================================================================

@router.websocket("/ws/{batch_id}")
async def batch_progress_websocket(
    websocket: WebSocket,
    batch_id: str
):
    """
    WebSocket endpoint for real-time batch progress updates.

    Subscribes to Redis pub/sub channel for the batch and forwards
    all progress updates to the connected client.

    Messages include:
    - batch_started: Batch processing started
    - lead_completed: Individual lead completed
    - batch_paused: Batch was paused
    - batch_completed: All leads processed
    - batch_cancelled: Batch was cancelled
    """
    await websocket.accept()
    logger.info(f"WebSocket connected for batch {batch_id}")

    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        redis = aioredis.from_url(redis_url)
        pubsub = redis.pubsub()

        channel = f"batch:{batch_id}:progress"
        await pubsub.subscribe(channel)

        logger.info(f"Subscribed to channel {channel}")

        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "batch_id": batch_id,
            "channel": channel,
        })

        # Listen for messages
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = json.loads(message["data"])
                    await websocket.send_json(data)

                    # Close connection if batch completed/cancelled
                    if data.get("type") in ("batch_completed", "batch_cancelled", "batch_failed"):
                        logger.info(f"Batch {batch_id} terminal state, closing WebSocket")
                        break

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in message: {message['data']}")

    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for batch {batch_id}")

    except Exception as e:
        logger.error(f"WebSocket error for batch {batch_id}: {e}")
        await websocket.close(code=1011, reason=str(e))

    finally:
        # Cleanup Redis resources with proper null checks
        try:
            if 'pubsub' in dir() and pubsub:
                await pubsub.unsubscribe(channel)
            if 'redis' in dir() and redis:
                await redis.close()
        except Exception as e:
            logger.warning(f"Error cleaning up WebSocket resources for batch {batch_id}: {e}")
