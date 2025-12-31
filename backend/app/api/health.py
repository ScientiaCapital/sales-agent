"""Health check endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.services.cache_manager import CacheManager
from app.core.cache import get_cache
from app.auth.dependencies import get_current_user

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


@router.get("/health/circuit-breakers")
async def circuit_breaker_status(current_user: dict = Depends(get_current_user)):
    """
    Get status of all circuit breakers for external API services.

    Returns status, failure counts, and recovery timing for each service.
    Protected endpoint - requires authentication.
    """
    from app.services.circuit_breaker_registry import get_all_circuit_breaker_status

    statuses = get_all_circuit_breaker_status()

    # Calculate summary
    total = len(statuses)
    open_count = sum(1 for s in statuses.values() if s.get("state") == "open")
    half_open_count = sum(1 for s in statuses.values() if s.get("state") == "half_open")

    return {
        "summary": {
            "total_breakers": total,
            "open": open_count,
            "half_open": half_open_count,
            "closed": total - open_count - half_open_count,
            "status": "degraded" if open_count > 0 else "healthy"
        },
        "breakers": statuses
    }


@router.post("/health/circuit-breakers/{service_name}/reset")
async def reset_circuit_breaker_endpoint(
    service_name: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Manually reset a circuit breaker to closed state.

    Use with caution - only reset if you've confirmed the external service is healthy.
    """
    from app.services.circuit_breaker_registry import reset_circuit_breaker

    if reset_circuit_breaker(service_name):
        return {"status": "reset", "service": service_name, "new_state": "closed"}
    else:
        raise HTTPException(status_code=404, detail=f"Circuit breaker '{service_name}' not found")
