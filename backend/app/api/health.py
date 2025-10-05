"""Health check endpoints."""

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.services.cache_manager import CacheManager
from app.core.cache import get_cache

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    environment: str


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    from app.core.config import settings

    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )


@router.get("/health/detailed")
async def detailed_health_check(cache: CacheManager = Depends(get_cache)):
    """Detailed health check with service status including Redis cache."""
    from app.core.config import settings
    from app.models.database import check_database_health

    # Check database health
    db_health = await check_database_health()
    db_status = "operational" if db_health.get("status") == "healthy" else "degraded"

    # Check Redis cache health
    redis_health = await cache.health_check()
    redis_status = "operational" if redis_health.get("status") == "healthy" else "degraded"
    
    # Get cache statistics
    cache_stats = await cache.get_cache_stats()

    # Overall system health based on critical services (Redis is non-critical)
    overall_status = "healthy" if db_status == "operational" else "degraded"

    return {
        "status": overall_status,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {
            "api": "operational",
            "database": db_status,
            "redis": redis_status,
            "cerebras": "not_configured",   # Will be updated in task 2
        },
        "database_details": db_health,
        "redis_details": {
            **redis_health,
            "cache_stats": cache_stats
        },
    }


@router.get("/test-error")
async def test_error():
    """
    Test endpoint to trigger a Sentry error report.

    This endpoint intentionally raises an exception to verify Sentry integration.
    Use this to test that errors are being captured and sent to Sentry dashboard.
    """
    raise RuntimeError("Test error for Sentry monitoring - this is intentional")
