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
from app.core.config import settings
from app.core.logging import setup_logging

# Configure logging
logger = setup_logging(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI-powered sales automation platform using Cerebras ultra-fast inference",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],  # Explicit methods only
    allow_headers=["Content-Type", "Authorization"],  # Required headers only
)


# Exception Handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors (422)."""
    logger.warning(f"Validation error on {request.url.path}: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with proper logging."""
    logger.error(f"HTTP {exc.status_code} on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
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
        content={"detail": "Internal server error"}
    )


# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(leads.router)
app.include_router(documents.router)
app.include_router(contacts.router)
app.include_router(knowledge.router)  # Task 24: Knowledge base endpoints
app.include_router(customers.router)  # Task 25: Customer platform endpoints
app.include_router(refine.router)  # Task 1: Iterative refinement engine


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
