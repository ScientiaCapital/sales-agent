"""FastAPI application entry point."""

# Load environment variables FIRST, before any imports that access them
from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / '.env', override=True)

import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Essential Dashboard Imports (3)
from app.api import health
try:
    from app.api import ai_outreach  # AI-powered outreach draft management
except (ImportError, ModuleNotFoundError) as e:
    if 'langchain' not in str(e):
        raise
    ai_outreach = None

try:
    from app.api.dashboard import router as dashboard_router  # Dashboard endpoints for frontend (refactored into modules)
    # Create a mock module object to maintain compatibility with existing code
    class DashboardModule:
        router = dashboard_router
    dashboard = DashboardModule()
except (ImportError, ModuleNotFoundError) as e:
    if 'langchain' not in str(e):
        raise
    dashboard = None

try:
    from app.api import sync_from_scraper  # Dealer scraper webhook endpoint
except (ImportError, ModuleNotFoundError) as e:
    if 'langchain' not in str(e):
        raise
    sync_from_scraper = None

# GTM Automation Infrastructure (15)
from app.api import supabase_auth  # Supabase authentication
try:
    from app.api import langgraph_agents
except (ImportError, ModuleNotFoundError) as e:
    if 'langchain' not in str(e):
        raise
    langgraph_agents = None
from app.api.webhooks import router as webhooks_close  # Close CRM webhooks (modular)
from app.api import webhooks  # Slack/external webhooks for BDR approval
from app.api import audit  # Lead audit trail for GTM agents
from app.api import sync
from app.api import close_outreach  # Close CRM SMS/Voice integration
from app.api import close_opportunities  # Close CRM opportunities/pipelines
from app.api import sequences  # Email sequence management
from app.api import alerts  # Alert management for BDR workflow
from app.api import batch  # Batch processing with parallel execution
from app.api import agents  # Agent control API for BDR Cockpit
from app.api import cockpit_websocket  # WebSocket for BDR Cockpit real-time updates
from app.api import rankings  # Lead prediction market rankings
from app.api import slack_commands  # Slack slash commands (/enrich)
from app.api import claude_chat  # Claude chat API for CEO/CTO interaction
from app.api import voice_routes  # Twilio voice calling integration
from app.api.routes import voice as voice_api_routes  # Voice API routes (Twilio webhooks, Slack callbacks)
from app.api import workflow_rules  # Workflow automation rules (Phase 4)
from app.core.config import settings
from app.core.logging import setup_logging
from app.core.metrics import MetricsMiddleware, metrics_endpoint
from app.core.cache import get_cache_manager
from sqlalchemy import text
from app.models.database import engine
from app.core.exceptions import (
    SalesAgentException,
)

# Configure logging
logger = setup_logging(__name__)

# Configure LangSmith tracing via lang-core (early initialization)
try:
    from lang_core.langsmith import configure_tracing
    configure_tracing(
        project=os.getenv("LANGSMITH_PROJECT", "sales-agent"),
        tags=["production", "sales-agent"],
        enabled=os.getenv("LANGSMITH_TRACING", "true").lower() == "true"
    )
    logger.info("LangSmith tracing configured via lang-core")
except ImportError:
    logger.warning("lang-core not installed, LangSmith tracing not configured")


# Security Headers Middleware
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add security headers to all HTTP responses.

    Headers added:
    - X-Frame-Options: Prevent clickjacking attacks
    - X-Content-Type-Options: Prevent MIME type sniffing
    - X-XSS-Protection: Legacy XSS protection (still useful for older browsers)
    - Strict-Transport-Security: Enforce HTTPS (production only)
    - Content-Security-Policy: Control resource loading to prevent XSS
    """
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Prevent clickjacking
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # XSS Protection (legacy but still useful)
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Only add HSTS in production (when not localhost)
        if "localhost" not in str(request.url):
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        # Content Security Policy (hardened - no unsafe-inline/eval)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self'; "
            "img-src 'self' data: https:; "
            "font-src 'self' data:; "
            "connect-src 'self' https://*.supabase.co wss://*.supabase.co; "
            "frame-ancestors 'none'; "
            "base-uri 'self'"
        )

        return response

# Initialize Sentry error tracking (optional - only if SENTRY_DSN is set)
sentry_dsn = os.getenv("SENTRY_DSN")
if sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.redis import RedisIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

    sentry_sdk.init(
        dsn=sentry_dsn,
        environment=os.getenv("ENVIRONMENT", "development"),
        traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),  # 10% of transactions
        profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.1")),  # 10% profiling
        integrations=[
            FastApiIntegration(transaction_style="endpoint"),
            CeleryIntegration(),
            RedisIntegration(),
            SqlalchemyIntegration(),
        ],
        # Don't send data in test environment
        before_send=lambda event, hint: None if os.getenv("TESTING") == "true" else event,
    )
    logger.info(f"Sentry initialized for environment: {os.getenv('ENVIRONMENT', 'development')}")
else:
    logger.info("Sentry not configured (SENTRY_DSN not set)")

# Initialize Datadog APM tracing (optional - only if DATADOG_API_KEY is set)
datadog_enabled = os.getenv("DATADOG_ENABLED", "false").lower() == "true"
if datadog_enabled:
    from ddtrace import patch_all, config

    # Configure Datadog service name and environment
    config.service = os.getenv("DATADOG_SERVICE_NAME", "sales-agent-api")
    config.env = os.getenv("ENVIRONMENT", "development")
    config.version = os.getenv("VERSION", "1.0.0")

    # Patch all supported libraries for automatic instrumentation
    patch_all(
        fastapi=True,
        sqlalchemy=True,
        redis=True,
        httpx=True,
        aiohttp=True,
    )

    logger.info(f"Datadog APM initialized for service: {config.service}, env: {config.env}")
else:
    logger.info("Datadog APM not enabled (DATADOG_ENABLED=true not set)")

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

# Add Security Headers Middleware (after CORS)
app.add_middleware(SecurityHeadersMiddleware)

# Add Audit Logging Middleware
from app.middleware.audit import AuditLoggingMiddleware
app.add_middleware(AuditLoggingMiddleware)
app.add_middleware(MetricsMiddleware)

# Rate Limiting with SlowAPI
from slowapi.errors import RateLimitExceeded
from app.core.rate_limit import limiter, rate_limit_exceeded_handler
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)


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

# Essential Dashboard (4)
app.include_router(health.router, prefix=settings.API_V1_PREFIX, tags=["health"])
app.include_router(ai_outreach.router, prefix=settings.API_V1_PREFIX)  # AI outreach draft management
app.include_router(dashboard.router, prefix=settings.API_V1_PREFIX)  # Dashboard endpoints for frontend
app.include_router(sync_from_scraper.router, prefix=settings.API_V1_PREFIX)  # Dealer scraper webhook endpoint

# GTM Automation Infrastructure (15)
app.include_router(supabase_auth.router, prefix=settings.API_V1_PREFIX)  # Supabase authentication
app.include_router(langgraph_agents.router, prefix=settings.API_V1_PREFIX)  # LangGraph agent endpoints
app.include_router(webhooks.router, prefix=settings.API_V1_PREFIX)  # Slack/external webhooks for BDR approval
app.include_router(webhooks_close, prefix=settings.API_V1_PREFIX)  # Close CRM webhooks (email replies, etc.)
app.include_router(audit.router, prefix=settings.API_V1_PREFIX)  # Lead audit trail for GTM agents
app.include_router(sync.router, prefix=f"{settings.API_V1_PREFIX}/sync", tags=["sync"])  # CRM sync monitoring
app.include_router(close_outreach.router, prefix=settings.API_V1_PREFIX)  # Close CRM SMS/Voice outreach
app.include_router(close_opportunities.router, prefix=settings.API_V1_PREFIX)  # Close CRM opportunities/pipelines
app.include_router(sequences.router, prefix=settings.API_V1_PREFIX)  # Email sequence management
app.include_router(sequences.cockpit_router)  # Sequences cockpit endpoints (v1 prefix in router)
app.include_router(alerts.router, prefix=settings.API_V1_PREFIX)  # Alert management for BDR workflow
app.include_router(batch.router, prefix=settings.API_V1_PREFIX)  # Batch processing with parallel execution
app.include_router(agents.router, prefix=settings.API_V1_PREFIX)  # Agent control API for BDR Cockpit
app.include_router(cockpit_websocket.router, prefix=settings.API_V1_PREFIX)  # WebSocket for BDR Cockpit real-time updates
app.include_router(rankings.router, prefix=settings.API_V1_PREFIX)  # Lead prediction market rankings
app.include_router(slack_commands.router, prefix=settings.API_V1_PREFIX)  # Slack slash commands (/enrich)
app.include_router(claude_chat.router, prefix=settings.API_V1_PREFIX)  # Claude chat API for CEO/CTO interaction
app.include_router(voice_routes.router, prefix=settings.API_V1_PREFIX)  # Twilio voice calling integration
app.include_router(voice_api_routes.router, prefix=settings.API_V1_PREFIX)  # Voice API routes (Twilio webhooks, Slack callbacks)
app.include_router(workflow_rules.router, prefix=settings.API_V1_PREFIX)  # Workflow automation rules (Phase 4)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "Sales Agent API",
        "version": settings.VERSION,
        "docs": "/api/v1/docs",
    }

# Prometheus metrics endpoint
@app.get("/metrics")
async def metrics():
    return metrics_endpoint()

# JSON metrics summary endpoint
@app.get(f"{settings.API_V1_PREFIX}/metrics/summary")
async def metrics_summary():
    """Return JSON summary of cache and database health/metrics."""
    # Cache stats
    cache = get_cache_manager()
    cache_stats = await cache.get_cache_stats()

    # Database health
    db_health = {"status": "unknown"}
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_health = {"status": "healthy"}
    except Exception as e:
        db_health = {"status": "unhealthy", "error": str(e)}

    return {
        "app": {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "environment": os.getenv("ENVIRONMENT", "development"),
        },
        "database": db_health,
        "cache": cache_stats,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
