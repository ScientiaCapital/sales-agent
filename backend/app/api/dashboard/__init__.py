"""
Dashboard API Module
====================
Refactored dashboard endpoints organized by function.

This module aggregates routers from:
- metrics.py - Core metrics and combined stats
- close_sync.py - Close CRM integration (outreach, lifecycle, trifecta)
- queues.py - Work queues (ICP queue, attention, activity, imports)
- agents.py - Agent health and status
- celery_health.py - Celery observability
- mission_control.py - Mission control stats

Author: Claude + Tim
Date: Dec 18, 2025
"""

from fastapi import APIRouter

# Import sub-routers
from .metrics import router as metrics_router
from .close_sync import router as close_sync_router
from .queues import router as queues_router
from .agents import router as agents_router
from .celery_health import router as celery_health_router
from .mission_control import router as mission_control_router

# Create main dashboard router
router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# Include all sub-routers
router.include_router(metrics_router)
router.include_router(close_sync_router)
router.include_router(queues_router)
router.include_router(agents_router)
router.include_router(celery_health_router)
router.include_router(mission_control_router)

__all__ = ["router"]
