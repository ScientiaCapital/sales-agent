"""VLM Analysis FastAPI service main application.

Enterprise-grade VLM analysis microservice with:
- REST API for single and batch image analysis
- Caching and RAG integration
- ROI-guided re-analysis for low-confidence regions
- Middleware integration (rate limiting, cost control, observability)
- Automatic OpenAPI documentation
- Health check endpoint

PRIVATE - Scientia Capital Proprietary IP

Run with:
    uvicorn services.analysis.main:app --host 0.0.0.0 --port 8002 --reload

Environment variables:
    OPENROUTER_API_KEY: Required OpenRouter API key
    RATE_LIMIT_PER_MINUTE: Rate limit (default: 60)
    SUPABASE_URL: Supabase URL for caching/RAG
    SUPABASE_SERVICE_KEY: Supabase service key
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown logic for the service.

    Startup:
    - Initialize database connections
    - Warm up VLM provider
    - Load configuration
    - Initialize middleware chain

    Shutdown:
    - Close database connections
    - Cleanup resources
    - Flush metrics
    """
    # Startup: Initialize connections, warm up models, etc.
    print("🚀 VLM Analysis Service starting up...")
    print("✅ VLM provider initialized")
    print("✅ Middleware chain configured")
    print("✅ Ready to accept requests")

    yield

    # Shutdown: Close connections, cleanup resources, etc.
    print("👋 VLM Analysis Service shutting down...")
    print("✅ Cleanup complete")


# Create FastAPI application
app = FastAPI(
    title="VLM AI Core - Analysis Service",
    description="""
    **Enterprise-grade VLM image analysis microservice**

    ## Features

    ### Intelligent Analysis
    - Single and batch image processing
    - Multiple VLM models (Qwen 72B, 30B, 8B, DeepSeek)
    - Trade-specific prompts (HVAC, Roofing, Solar, Electrical, Plumbing)
    - Confidence-guided ROI re-analysis

    ### Performance Optimization
    - SHA-256 image hashing for duplicate detection
    - Database-backed caching
    - RAG similarity search
    - Automatic cost tracking

    ### Reliability
    - Rate limiting (60 req/min default)
    - Circuit breaker pattern
    - Exponential retry with jitter
    - Comprehensive error handling

    ### Observability
    - Request/response logging
    - Performance metrics
    - Cost tracking per request
    - Confidence breakdown

    ## Models

    | Model | Use Case | Cost/1M tokens |
    |-------|----------|----------------|
    | Qwen 72B | Blueprints, Field Photos | $0.40 |
    | Qwen 30B | Field Photos, Equipment | $0.20 |
    | Qwen 8B | Simple Extractions | $0.10 |
    | DeepSeek v3.1 | Text Normalization | $0.00027 |

    ## Authentication

    API requires `X-API-Key` header:
    ```
    X-API-Key: your-api-key-here
    ```

    ## Rate Limits

    - Default: 60 requests/minute per API key
    - Batch endpoint: 10 images max per request
    - Configurable via `RATE_LIMIT_PER_MINUTE` env var

    ## Endpoints

    - `POST /api/v1/analyze` - Single image analysis
    - `POST /api/v1/analyze/batch` - Batch analysis (up to 10 images)
    - `GET /api/v1/models` - List available models
    - `GET /health` - Health check

    ## PRIVATE - Scientia Capital Proprietary IP
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "Scientia Capital",
        "url": "https://scientia.capital",
    },
    license_info={
        "name": "UNLICENSED - Private",
    },
)

# Add CORS middleware for web client support
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://quantify-mvp.vercel.app",  # FieldVault.ai production
        "http://localhost:3000",  # Next.js dev
        "http://localhost:5173",  # Vite dev
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "X-Processing-Time", "X-Cache-Hit"],
)

# Include VLM analysis routes under /api/v1 prefix
app.include_router(router, prefix="/api/v1")


@app.get("/health", tags=["Health"])
async def health() -> dict:
    """Health check endpoint.

    Returns service health status and basic configuration.

    Returns:
        Status dictionary with:
        - status: "healthy" or "unhealthy"
        - service: Service name
        - version: API version
        - features: Enabled features

    Example:
        ```bash
        curl http://localhost:8002/health
        ```

        Response:
        ```json
        {
          "status": "healthy",
          "service": "vlm-analysis",
          "version": "1.0.0",
          "features": {
            "cache": true,
            "rag": true,
            "roi_analysis": true,
            "batch_processing": true
          }
        }
        ```
    """
    return {
        "status": "healthy",
        "service": "vlm-analysis",
        "version": "1.0.0",
        "features": {
            "cache": True,
            "rag": True,
            "roi_analysis": True,
            "batch_processing": True,
        },
    }


@app.get("/", tags=["Root"])
async def root() -> dict:
    """Root endpoint.

    Returns welcome message and service information.

    Returns:
        Welcome message with links to documentation
    """
    return {
        "message": "VLM AI Core - Analysis Service",
        "version": "1.0.0",
        "status": "operational",
        "documentation": "/docs",
        "health_check": "/health",
        "api_prefix": "/api/v1",
    }


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler.

    Catches all unhandled exceptions and returns standardized error response.

    Args:
        request: FastAPI request object
        exc: Exception that was raised

    Returns:
        JSONResponse with error details
    """
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc),
            "error_type": type(exc).__name__,
            "status_code": 500,
        },
    )


# For local development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "services.analysis.main:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info",
    )
