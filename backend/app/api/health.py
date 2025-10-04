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

    return {
        "status": "healthy",
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "services": {
            "api": "operational",
            "database": "not_configured",  # Will be updated in task 1.3
            "redis": "not_configured",      # Will be updated in task 1.3
            "cerebras": "not_configured",   # Will be updated in task 2
        },
    }
