"""FastAPI application entry point."""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse

from app.api import health
from app.api import leads
from app.api import documents
from app.api import contacts
from app.api import knowledge
from app.api import customers
from app.api import refine
from app.api import research
from app.api import transfer
from app.api import voice
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.exceptions import (
    SalesAgentException,
    ValidationError,
    ResourceNotFoundError,
    ExternalAPIError,
    DatabaseError,
    ServiceUnavailableError,
    AuthenticationError,
    AuthorizationError,
)

# Configure logging
logger = setup_logging(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered sales automation platform using Cerebras ultra-fast inference",
    docs_url=f"{settings.API_V1_PREFIX}/docs",
    redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Explicit methods only
    allow_headers=["Content-Type", "Authorization"],  # Required headers only
)


# Exception Handlers - Ordered from specific to general
@app.exception_handler(SalesAgentException)
async def sales_agent_exception_handler(request: Request, exc: SalesAgentException):
    """
    Handle all custom Sales Agent exceptions with structured error responses.

    Returns error_code, message, and timestamp for debugging.
    Technical details are logged but not exposed to users.
    """
    # Error already logged in exception __init__
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle Pydantic request validation errors (422)."""
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "VALIDATION_ERROR",
            "message": "Request validation failed",
            "details": exc.errors(),
            "body": exc.body
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle generic FastAPI HTTP exceptions."""
    logger.error(f"HTTP {exc.status_code} on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions to prevent stack trace leaks."""
    logger.error(
        f"Unhandled exception on {request.url.path}: {exc}",
        exc_info=True  # Include stack trace in logs
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred"
        }
    )


# Include routers with API version prefix
app.include_router(health.router, prefix=settings.API_V1_PREFIX, tags=["health"])
app.include_router(leads.router, prefix=settings.API_V1_PREFIX)
app.include_router(documents.router, prefix=settings.API_V1_PREFIX)
app.include_router(contacts.router, prefix=settings.API_V1_PREFIX)
app.include_router(knowledge.router, prefix=settings.API_V1_PREFIX)  # Task 24: Knowledge base endpoints
app.include_router(customers.router, prefix=settings.API_V1_PREFIX)  # Task 25: Customer platform endpoints
app.include_router(refine.router, prefix=settings.API_V1_PREFIX)  # Task 1: Iterative refinement engine
app.include_router(research.router, prefix=settings.API_V1_PREFIX)  # Task 3: Multi-agent research pipeline
app.include_router(transfer.router, prefix=settings.API_V1_PREFIX)  # Task 4: Agent transfer system
app.include_router(voice.router, prefix=settings.API_V1_PREFIX)  # Task 6: Cartesia voice integration


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Sales Agent API",
        "version": settings.VERSION,
        "docs": "/api/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
