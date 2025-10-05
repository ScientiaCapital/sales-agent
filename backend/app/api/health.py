"""Health check endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

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
async def detailed_health_check():
    """Detailed health check with service status."""
    from app.core.config import settings
    from app.models.database import check_database_health

    # Check database health
    db_health = await check_database_health()
    db_status = "operational" if db_health.get("status") == "healthy" else "degraded"

    # Overall system health based on critical services
    overall_status = "healthy" if db_status == "operational" else "degraded"

    return {
        "status": overall_status,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {
            "api": "operational",
            "database": db_status,
            "redis": "not_configured",      # Will be updated in task 1.3
            "cerebras": "not_configured",   # Will be updated in task 2
        },
        "database_details": db_health,
    }
