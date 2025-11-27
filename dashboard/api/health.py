"""
Health Check Endpoint for Sales-Agent Dashboard

GET /api/health - Returns system health status
"""

from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Literal

app = FastAPI()


class HealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    database: bool
    redis: bool
    cerebras_api: bool
    close_api: bool
    apollo_api: bool
    timestamp: str
    version: str


@app.get("/api/health")
async def health_check() -> JSONResponse:
    """
    Health check endpoint - returns system status.

    For MVP: Returns mock healthy status.
    Production: Will check actual service connections.
    """
    response = HealthResponse(
        status="healthy",
        database=True,
        redis=True,
        cerebras_api=True,
        close_api=True,
        apollo_api=True,
        timestamp=datetime.utcnow().isoformat(),
        version="1.0.0-mvp"
    )

    return JSONResponse(
        content=response.model_dump(),
        headers={
            "Cache-Control": "public, max-age=30",
            "Access-Control-Allow-Origin": "*",
        }
    )
