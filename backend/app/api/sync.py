"""
CRM Sync Monitoring API

Endpoints for monitoring and controlling CRM synchronization operations.

Features:
- Real-time sync status for all platforms
- Sync history and metrics
- Manual sync triggering
- Conflict resolution
"""

from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.database import get_db
from app.models.crm import CRMSyncLog, CRMCredential
from app.services.crm_sync_service import CRMSyncService
from app.core.logging import setup_logging
from app.celery_app import celery_app

logger = setup_logging(__name__)

router = APIRouter()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SyncTriggerRequest(BaseModel):
    """Request to manually trigger a sync operation"""

    platform: str = Field(..., description="CRM platform (close, apollo, linkedin)")
    direction: str = Field(default="import", description="Sync direction (import, export, bidirectional)")
    filters: Optional[Dict[str, Any]] = Field(None, description="Platform-specific filters")

    class Config:
        json_schema_extra = {
            "example": {
                "platform": "close",
                "direction": "import",
                "filters": {
                    "query": "company:Acme",
                    "created_date_gte": "2025-01-01"
                }
            }
        }


class SyncStatusResponse(BaseModel):
    """Current sync status for a platform"""

    platform: str
    status: str  # never_synced, completed, failed, running
    last_sync_at: Optional[str]
    contacts_processed: Optional[int]
    contacts_created: Optional[int]
    contacts_updated: Optional[int]
    contacts_failed: Optional[int]
    duration_seconds: Optional[float]
    errors: Optional[List[Dict[str, Any]]]


class SyncHistoryResponse(BaseModel):
    """Sync operation history"""

    sync_logs: List[Dict[str, Any]]
    total_count: int
    page: int
    page_size: int


# ============================================================================
# SYNC STATUS ENDPOINTS
# ============================================================================

@router.get("/status", response_model=List[SyncStatusResponse])
async def get_all_sync_status(db: Session = Depends(get_db)):
    """
    Get current sync status for all CRM platforms.

    Returns:
        List of sync statuses for Close, Apollo, and LinkedIn
    """
    try:
        sync_service = CRMSyncService(db=db)
        platforms = ["close", "apollo", "linkedin"]

        statuses = []
        for platform in platforms:
            status = await sync_service.get_sync_status(platform)
            statuses.append(SyncStatusResponse(**status))

        return statuses

    except Exception as e:
        logger.error(f"Error getting sync status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


@router.get("/status/{platform}", response_model=SyncStatusResponse)
async def get_platform_sync_status(
    platform: str,
    db: Session = Depends(get_db)
):
    """
    Get current sync status for a specific CRM platform.

    Args:
        platform: CRM platform (close, apollo, linkedin)

    Returns:
        Sync status for the platform
    """
    try:
        if platform.lower() not in ["close", "apollo", "linkedin"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform: {platform}. Must be close, apollo, or linkedin"
            )

        sync_service = CRMSyncService(db=db)
        status = await sync_service.get_sync_status(platform)

        return SyncStatusResponse(**status)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting {platform} sync status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")


# ============================================================================
# SYNC HISTORY ENDPOINTS
# ============================================================================

@router.get("/history", response_model=SyncHistoryResponse)
async def get_sync_history(
    platform: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db)
):
    """
    Get sync operation history with filtering and pagination.

    Args:
        platform: Filter by platform (close, apollo, linkedin)
        status: Filter by status (completed, failed)
        page: Page number (1-indexed)
        page_size: Results per page

    Returns:
        Paginated sync history
    """
    try:
        query = db.query(CRMSyncLog)

        # Apply filters
        if platform:
            query = query.filter(CRMSyncLog.platform == platform.lower())
        if status:
            query = query.filter(CRMSyncLog.status == status.lower())

        # Get total count
        total_count = query.count()

        # Apply pagination
        offset = (page - 1) * page_size
        sync_logs = query.order_by(CRMSyncLog.started_at.desc()).offset(offset).limit(page_size).all()

        # Convert to dict
        logs_data = []
        for log in sync_logs:
            logs_data.append({
                "id": log.id,
                "platform": log.platform,
                "operation": log.operation,
                "contacts_processed": log.contacts_processed,
                "contacts_created": log.contacts_created,
                "contacts_updated": log.contacts_updated,
                "contacts_failed": log.contacts_failed,
                "errors": log.errors,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "duration_seconds": log.duration_seconds,
                "status": log.status
            })

        return SyncHistoryResponse(
            sync_logs=logs_data,
            total_count=total_count,
            page=page,
            page_size=page_size
        )

    except Exception as e:
        logger.error(f"Error getting sync history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sync history: {str(e)}")


# ============================================================================
# MANUAL SYNC TRIGGER
# ============================================================================

@router.post("/trigger")
async def trigger_sync(
    request: SyncTriggerRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    Manually trigger a sync operation for a CRM platform.

    This queues a background Celery task for the sync operation.

    Args:
        request: Sync trigger request with platform, direction, and filters

    Returns:
        Task ID for tracking the sync operation
    """
    try:
        # Validate platform
        if request.platform.lower() not in ["close", "apollo", "linkedin"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid platform: {request.platform}. Must be close, apollo, or linkedin"
            )

        # Validate direction
        if request.direction not in ["import", "export", "bidirectional"]:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid direction: {request.direction}. Must be import, export, or bidirectional"
            )

        # Check if credentials exist for platform
        credential = db.query(CRMCredential).filter(
            CRMCredential.platform == request.platform.lower(),
            CRMCredential.is_active == True
        ).first()

        if not credential:
            raise HTTPException(
                status_code=404,
                detail=f"No active credentials found for {request.platform}. Please configure credentials first."
            )

        # Queue Celery task
        task = celery_app.send_task(
            "sync_crm_contacts",
            args=(request.platform, request.direction, request.filters),
            queue="crm_sync"
        )

        logger.info(f"Queued sync task: {task.id} for {request.platform}")

        return {
            "status": "queued",
            "task_id": task.id,
            "platform": request.platform,
            "direction": request.direction,
            "message": f"Sync operation queued for {request.platform}. Use task_id to check status."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering sync: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to trigger sync: {str(e)}")


# ============================================================================
# SYNC METRICS
# ============================================================================

@router.get("/metrics")
async def get_sync_metrics(
    platform: Optional[str] = None,
    days: int = 7,
    db: Session = Depends(get_db)
):
    """
    Get aggregate sync metrics for analytics.

    Args:
        platform: Filter by platform (optional)
        days: Number of days to include in metrics (default: 7)

    Returns:
        Aggregate metrics including success rates, contact counts, error rates
    """
    try:
        from datetime import timedelta
        from sqlalchemy import func

        cutoff_date = datetime.utcnow() - timedelta(days=days)

        query = db.query(
            CRMSyncLog.platform,
            func.count(CRMSyncLog.id).label("total_syncs"),
            func.sum(CRMSyncLog.contacts_processed).label("total_processed"),
            func.sum(CRMSyncLog.contacts_created).label("total_created"),
            func.sum(CRMSyncLog.contacts_updated).label("total_updated"),
            func.sum(CRMSyncLog.contacts_failed).label("total_failed"),
            func.avg(CRMSyncLog.duration_seconds).label("avg_duration")
        ).filter(
            CRMSyncLog.started_at >= cutoff_date
        )

        if platform:
            query = query.filter(CRMSyncLog.platform == platform.lower())

        query = query.group_by(CRMSyncLog.platform)

        results = query.all()

        metrics = []
        for result in results:
            success_rate = 0.0
            if result.total_processed and result.total_processed > 0:
                success_rate = ((result.total_processed - (result.total_failed or 0)) / result.total_processed) * 100

            metrics.append({
                "platform": result.platform,
                "period_days": days,
                "total_syncs": result.total_syncs,
                "contacts_processed": result.total_processed or 0,
                "contacts_created": result.total_created or 0,
                "contacts_updated": result.total_updated or 0,
                "contacts_failed": result.total_failed or 0,
                "success_rate_percent": round(success_rate, 2),
                "avg_duration_seconds": round(result.avg_duration, 2) if result.avg_duration else 0
            })

        return {
            "period_days": days,
            "metrics": metrics
        }

    except Exception as e:
        logger.error(f"Error getting sync metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sync metrics: {str(e)}")


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def sync_health_check(db: Session = Depends(get_db)):
    """
    Check health of CRM sync system.

    Returns:
        Health status including configured platforms and recent sync status
    """
    try:
        # Check configured platforms
        configured_platforms = db.query(CRMCredential.platform).filter(
            CRMCredential.is_active == True
        ).distinct().all()

        platforms_configured = [p[0] for p in configured_platforms]

        # Check recent syncs
        from datetime import timedelta
        recent_cutoff = datetime.utcnow() - timedelta(hours=24)
        recent_syncs = db.query(CRMSyncLog).filter(
            CRMSyncLog.started_at >= recent_cutoff
        ).count()

        # Check for recent failures
        recent_failures = db.query(CRMSyncLog).filter(
            CRMSyncLog.started_at >= recent_cutoff,
            CRMSyncLog.status == "failed"
        ).count()

        health_status = "healthy"
        if recent_failures > 0:
            health_status = "degraded"
        if len(platforms_configured) == 0:
            health_status = "no_credentials"

        return {
            "status": health_status,
            "configured_platforms": platforms_configured,
            "syncs_last_24h": recent_syncs,
            "failures_last_24h": recent_failures,
            "timestamp": datetime.utcnow().isoformat()
        }

    except Exception as e:
        logger.error(f"Error checking sync health: {e}", exc_info=True)
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
