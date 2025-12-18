"""
Dashboard Celery Health Module
===============================
Celery worker and task observability endpoint.

Endpoints:
- GET /celery-stats - Real-time Celery worker and task statistics

Author: Claude + Tim
Date: Dec 18, 2025
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# ============================================================================
# Response Models
# ============================================================================

class CeleryWorkerStats(BaseModel):
    """Stats for a single Celery worker."""
    hostname: str
    status: str  # online, offline
    active_tasks: int
    processed_total: int
    pool_size: Optional[int] = None
    concurrency: Optional[int] = None


class CeleryTaskStats(BaseModel):
    """Stats for Celery tasks."""
    scheduled_count: int
    active_count: int
    reserved_count: int
    recent_tasks: List[Dict[str, Any]]


class CeleryStatsResponse(BaseModel):
    """Response for Celery observability endpoint."""
    status: str  # healthy, degraded, offline
    workers: List[CeleryWorkerStats]
    tasks: CeleryTaskStats
    redis_connected: bool
    beat_running: bool
    summary: Dict[str, Any]


# ============================================================================
# Endpoint
# ============================================================================

@router.get("/celery-stats", response_model=CeleryStatsResponse)
async def get_celery_stats():
    """
    Get real-time Celery worker and task statistics.

    Provides observability into:
    - Worker health and status
    - Active/scheduled/reserved task counts
    - Redis connectivity
    - Beat scheduler status
    """
    try:
        from app.celery_app import celery_app
        import redis

        workers = []
        active_count = 0
        scheduled_count = 0
        reserved_count = 0
        recent_tasks = []

        # Check Redis connectivity
        redis_connected = False
        try:
            redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
            r = redis.from_url(redis_url)
            r.ping()
            redis_connected = True
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}")

        # Get worker stats via Celery inspect
        try:
            inspector = celery_app.control.inspect(timeout=3.0)

            # Ping workers
            ping_result = inspector.ping() or {}
            stats_result = inspector.stats() or {}
            active_result = inspector.active() or {}
            scheduled_result = inspector.scheduled() or {}
            reserved_result = inspector.reserved() or {}

            for hostname, pong in ping_result.items():
                stats = stats_result.get(hostname, {})
                active_tasks = active_result.get(hostname, [])
                scheduled_tasks = scheduled_result.get(hostname, [])
                reserved_tasks = reserved_result.get(hostname, [])

                workers.append(CeleryWorkerStats(
                    hostname=hostname,
                    status="online" if pong else "offline",
                    active_tasks=len(active_tasks),
                    processed_total=stats.get("total", {}).get("celery.backend_cleanup", 0) if stats else 0,
                    pool_size=stats.get("pool", {}).get("max-concurrency") if stats else None,
                    concurrency=stats.get("pool", {}).get("processes") if stats else None
                ))

                active_count += len(active_tasks)
                scheduled_count += len(scheduled_tasks)
                reserved_count += len(reserved_tasks)

                # Collect recent active tasks
                for task in active_tasks[:5]:
                    recent_tasks.append({
                        "name": task.get("name", "unknown"),
                        "id": task.get("id", ""),
                        "args": str(task.get("args", []))[:100],
                        "started": task.get("time_start"),
                        "hostname": hostname
                    })

        except Exception as e:
            logger.warning(f"Celery inspect failed: {e}")

        # Check Beat status (look for celerybeat-schedule file)
        beat_running = False
        try:
            import os.path
            beat_schedule_path = "celerybeat-schedule"
            if os.path.exists(beat_schedule_path):
                # Check if modified in last 5 minutes
                mtime = os.path.getmtime(beat_schedule_path)
                if (datetime.now().timestamp() - mtime) < 300:
                    beat_running = True
        except Exception:
            pass

        # Determine overall status
        if not redis_connected:
            status = "offline"
        elif len(workers) == 0:
            status = "degraded"
        elif all(w.status == "online" for w in workers):
            status = "healthy"
        else:
            status = "degraded"

        return CeleryStatsResponse(
            status=status,
            workers=workers,
            tasks=CeleryTaskStats(
                scheduled_count=scheduled_count,
                active_count=active_count,
                reserved_count=reserved_count,
                recent_tasks=recent_tasks[:10]
            ),
            redis_connected=redis_connected,
            beat_running=beat_running,
            summary={
                "total_workers": len(workers),
                "online_workers": sum(1 for w in workers if w.status == "online"),
                "total_active_tasks": active_count,
                "total_scheduled": scheduled_count,
                "health_score": 100 if status == "healthy" else (50 if status == "degraded" else 0)
            }
        )

    except Exception as e:
        logger.error(f"Error fetching Celery stats: {e}")
        return CeleryStatsResponse(
            status="offline",
            workers=[],
            tasks=CeleryTaskStats(
                scheduled_count=0,
                active_count=0,
                reserved_count=0,
                recent_tasks=[]
            ),
            redis_connected=False,
            beat_running=False,
            summary={
                "error": str(e),
                "total_workers": 0,
                "online_workers": 0,
                "health_score": 0
            }
        )
