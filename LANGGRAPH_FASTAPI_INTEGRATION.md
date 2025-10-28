# LangGraph ReAct Agent - FastAPI Integration Guide

FastAPI endpoints for production contact enrichment using LangGraph agents.

## Table of Contents

1. [Synchronous Endpoints](#synchronous-endpoints)
2. [Asynchronous Endpoints](#asynchronous-endpoints)
3. [Streaming Endpoints](#streaming-endpoints)
4. [Error Handling](#error-handling)
5. [Request/Response Models](#requestresponse-models)
6. [Integration Example](#integration-example)

---

## Synchronous Endpoints

### Single Contact Enrichment

```python
# backend/app/api/enrichment.py

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional, Dict, Any
import logging

from app.services.langgraph_react_patterns import (
    SyncEnrichmentExecutor,
    AgentConfig,
    EnrichmentResult,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/enrich", tags=["enrichment"])


class EnrichmentRequest(BaseModel):
    """Request model for contact enrichment"""
    email: EmailStr
    linkedin_url: Optional[HttpUrl] = None
    wait_for_completion: bool = True  # True = sync, False = background


class EnrichmentResponse(BaseModel):
    """Response model for enrichment result"""
    status: str  # "success" | "partial" | "error"
    enrichment_data: Dict[str, Any]
    final_response: str
    iterations: int
    tools_called: int
    enrichment_score: Optional[float] = None
    error: Optional[str] = None


@router.post(
    "/single",
    response_model=EnrichmentResponse,
    status_code=status.HTTP_200_OK,
)
async def enrich_single_contact(request: EnrichmentRequest) -> EnrichmentResponse:
    """
    Synchronously enrich a single contact.

    This endpoint blocks until enrichment is complete (typically 5-15 seconds).
    Recommended for real-time enrichment in user-facing flows.

    Args:
        request: EnrichmentRequest with email and optional LinkedIn URL

    Returns:
        EnrichmentResponse with enriched contact data and metrics

    Example:
        POST /api/enrich/single
        {
            "email": "john@acme.com",
            "linkedin_url": "https://linkedin.com/in/johndoe"
        }

        Response:
        {
            "status": "success",
            "enrichment_data": {
                "full_name": "John Doe",
                "title": "Senior Engineer",
                "company": "Acme Corp",
                ...
            },
            "iterations": 9,
            "tools_called": 3,
            "enrichment_score": 85.5
        }
    """
    try:
        # Create executor with default config
        executor = SyncEnrichmentExecutor()

        # Execute enrichment
        result: EnrichmentResult = executor.enrich(
            email=str(request.email),
            linkedin_url=str(request.linkedin_url) if request.linkedin_url else None,
        )

        # Extract enrichment score if available
        enrichment_score = None
        if result.enrichment_data.get("enrichment_summary"):
            enrichment_score = result.enrichment_data["enrichment_summary"].get(
                "enrichment_score"
            )

        return EnrichmentResponse(
            status=result.status,
            enrichment_data=result.enrichment_data,
            final_response=result.final_response,
            iterations=result.metrics.iterations,
            tools_called=result.metrics.tool_calls,
            enrichment_score=enrichment_score,
            error=result.error,
        )

    except ValueError as e:
        logger.error(f"Invalid input: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid input: {str(e)}",
        )
    except Exception as e:
        logger.exception(f"Enrichment failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Enrichment service error",
        )


@router.get(
    "/health",
    response_model=Dict[str, Any],
)
async def enrichment_health() -> Dict[str, Any]:
    """
    Health check for enrichment service.

    Returns:
        Service status and configuration info

    Example:
        GET /api/enrich/health

        Response:
        {
            "status": "healthy",
            "service": "langgraph_enrichment",
            "model": "claude-3-5-sonnet-20241022",
            "recursion_limit": 25
        }
    """
    return {
        "status": "healthy",
        "service": "langgraph_enrichment",
        "model": "claude-3-5-sonnet-20241022",
        "recursion_limit": 25,
        "timestamp": datetime.utcnow().isoformat(),
    }
```

---

## Asynchronous Endpoints

### Concurrent Batch Enrichment

```python
# In backend/app/api/enrichment.py (add to existing router)

from app.services.langgraph_react_patterns import AsyncEnrichmentExecutor


class BatchEnrichmentRequest(BaseModel):
    """Request model for batch enrichment"""
    contacts: List[Dict[str, Optional[str]]]  # List of {"email": str, "linkedin_url": str}
    max_concurrent: int = 5


class BatchEnrichmentResponse(BaseModel):
    """Response model for batch enrichment"""
    total_contacts: int
    successful: int
    partial: int
    failed: int
    results: List[EnrichmentResponse]
    total_time_seconds: float


@router.post(
    "/batch",
    response_model=BatchEnrichmentResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enrich_batch(request: BatchEnrichmentRequest) -> BatchEnrichmentResponse:
    """
    Asynchronously enrich multiple contacts concurrently.

    Processes up to max_concurrent contacts in parallel. Returns 202 Accepted
    to indicate async processing. Actual results may take 10-60 seconds depending
    on contact count.

    Args:
        request: BatchEnrichmentRequest with list of contacts

    Returns:
        BatchEnrichmentResponse with aggregated results

    Example:
        POST /api/enrich/batch
        {
            "contacts": [
                {"email": "john@acme.com", "linkedin_url": null},
                {"email": "jane@corp.com", "linkedin_url": "https://linkedin.com/in/jane"}
            ],
            "max_concurrent": 5
        }

        Response:
        {
            "total_contacts": 2,
            "successful": 1,
            "partial": 1,
            "failed": 0,
            "results": [...],
            "total_time_seconds": 12.45
        }
    """
    start_time = time.time()

    try:
        # Create async executor
        executor = AsyncEnrichmentExecutor()

        # Prepare contacts list
        contacts = [
            (contact["email"], contact.get("linkedin_url"))
            for contact in request.contacts
        ]

        # Run concurrent enrichment
        raw_results = await executor.enrich_batch(
            contacts,
            max_concurrent=request.max_concurrent,
        )

        # Process results
        enrichment_results = []
        successful = 0
        partial = 0
        failed = 0

        for result in raw_results:
            if isinstance(result, Exception):
                # Handle exception in batch
                failed += 1
                enrichment_results.append(
                    EnrichmentResponse(
                        status="error",
                        enrichment_data={},
                        final_response="",
                        iterations=0,
                        tools_called=0,
                        error=str(result),
                    )
                )
            else:
                enrichment_results.append(
                    EnrichmentResponse(
                        status=result.status,
                        enrichment_data=result.enrichment_data,
                        final_response=result.final_response,
                        iterations=result.metrics.iterations,
                        tools_called=result.metrics.tool_calls,
                        enrichment_score=(
                            result.enrichment_data.get("enrichment_summary", {}).get(
                                "enrichment_score"
                            )
                            if result.enrichment_data
                            else None
                        ),
                        error=result.error,
                    )
                )

                if result.status == "success":
                    successful += 1
                elif result.status == "partial":
                    partial += 1
                else:
                    failed += 1

        return BatchEnrichmentResponse(
            total_contacts=len(request.contacts),
            successful=successful,
            partial=partial,
            failed=failed,
            results=enrichment_results,
            total_time_seconds=time.time() - start_time,
        )

    except Exception as e:
        logger.exception(f"Batch enrichment failed: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Batch enrichment service error",
        )


@router.post(
    "/batch-async",
    status_code=status.HTTP_202_ACCEPTED,
)
async def enrich_batch_async(
    request: BatchEnrichmentRequest,
    background_tasks: BackgroundTasks,
) -> Dict[str, Any]:
    """
    Fire-and-forget batch enrichment.

    Accepts the batch, queues it for processing, and returns immediately with
    a job ID. Results are stored in database or cache for later retrieval.

    Args:
        request: BatchEnrichmentRequest with list of contacts
        background_tasks: FastAPI background tasks

    Returns:
        Job ID for tracking progress

    Example:
        POST /api/enrich/batch-async
        {
            "contacts": [...],
            "max_concurrent": 5
        }

        Response:
        {
            "job_id": "enrich_batch_12345",
            "status": "queued",
            "message": "Batch enrichment queued. Check /jobs/{job_id} for status"
        }
    """
    job_id = f"enrich_batch_{uuid.uuid4()}"

    # Queue background task
    async def process_batch():
        try:
            executor = AsyncEnrichmentExecutor()
            contacts = [
                (contact["email"], contact.get("linkedin_url"))
                for contact in request.contacts
            ]

            results = await executor.enrich_batch(
                contacts,
                max_concurrent=request.max_concurrent,
            )

            # Store results in cache/database
            await store_enrichment_results(job_id, results)
        except Exception as e:
            logger.exception(f"Background enrichment failed for {job_id}")
            await store_enrichment_error(job_id, str(e))

    background_tasks.add_task(process_batch)

    return {
        "job_id": job_id,
        "status": "queued",
        "message": f"Batch enrichment queued. Check /api/enrich/jobs/{job_id} for status",
    }


@router.get(
    "/jobs/{job_id}",
    response_model=Dict[str, Any],
)
async def get_batch_status(job_id: str) -> Dict[str, Any]:
    """
    Get status and results of a background enrichment job.

    Args:
        job_id: Job ID from /batch-async endpoint

    Returns:
        Job status and results if complete

    Example:
        GET /api/enrich/jobs/enrich_batch_12345

        Response (in progress):
        {
            "job_id": "enrich_batch_12345",
            "status": "processing",
            "progress": {"completed": 2, "total": 5}
        }

        Response (complete):
        {
            "job_id": "enrich_batch_12345",
            "status": "completed",
            "results": [...]
        }
    """
    job_status = await get_job_status(job_id)

    if not job_status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found",
        )

    return job_status
```

---

## Streaming Endpoints

### Real-Time Enrichment Progress

```python
# In backend/app/api/enrichment.py (add to existing router)

from fastapi.responses import StreamingResponse
from app.services.langgraph_react_patterns import StreamingEnrichmentExecutor


@router.post(
    "/stream",
    response_class=StreamingResponse,
)
async def enrich_stream(request: EnrichmentRequest):
    """
    Stream enrichment progress in real-time using Server-Sent Events (SSE).

    Connects to the enrichment agent and streams updates as they occur.
    Useful for real-time UI updates showing agent progress.

    Args:
        request: EnrichmentRequest with email and optional LinkedIn URL

    Returns:
        Server-Sent Events stream with progress updates

    Example:
        POST /api/enrich/stream
        {
            "email": "john@acme.com"
        }

        Response stream (SSE):
        data: {"event": "tool_call", "iteration": 1, "tools": [{"name": "search_apollo_contact", "args": {"email": "john@acme.com"}}]}
        data: {"event": "tool_result", "iteration": 1, "tool_name": "search_apollo_contact", "status": "success"}
        data: {"event": "tool_call", "iteration": 2, "tools": [{"name": "search_linkedin_profile", ...}]}
        ...
        data: {"event": "complete", "total_iterations": 9}
    """

    async def event_generator():
        executor = StreamingEnrichmentExecutor()

        try:
            async for update in executor.enrich_streaming_async(
                email=str(request.email),
                linkedin_url=str(request.linkedin_url)
                if request.linkedin_url
                else None,
            ):
                # Send as SSE
                yield f"data: {json.dumps(update)}\n\n"

        except Exception as e:
            logger.exception(f"Streaming enrichment failed: {str(e)}")
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


# HTML client example for streaming endpoint
STREAMING_CLIENT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Contact Enrichment Streaming</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .progress { border: 1px solid #ccc; padding: 10px; margin: 10px 0; }
        .event { padding: 5px; margin: 5px 0; font-size: 12px; }
        .tool-call { background-color: #e3f2fd; }
        .tool-result { background-color: #f1f8e9; }
        .error { background-color: #ffebee; color: red; }
    </style>
</head>
<body>
    <h1>Contact Enrichment Streaming</h1>

    <div>
        <input type="email" id="email" placeholder="Enter email" />
        <button onclick="startEnrichment()">Start Enrichment</button>
    </div>

    <div class="progress" id="progress" style="display: none;">
        <h3>Progress:</h3>
        <div id="events"></div>
    </div>

    <script>
        function startEnrichment() {
            const email = document.getElementById('email').value;
            const progressDiv = document.getElementById('progress');
            const eventsDiv = document.getElementById('events');

            progressDiv.style.display = 'block';
            eventsDiv.innerHTML = '';

            const eventSource = new EventSource(
                `/api/enrich/stream?email=${encodeURIComponent(email)}`,
                { method: 'POST' }
            );

            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                const eventEl = document.createElement('div');
                eventEl.className = `event ${data.event}`;
                eventEl.textContent = `[${data.event}] ${JSON.stringify(data)}`;
                eventsDiv.appendChild(eventEl);
            };

            eventSource.onerror = (error) => {
                const errorEl = document.createElement('div');
                errorEl.className = 'event error';
                errorEl.textContent = 'Stream error or complete';
                eventsDiv.appendChild(errorEl);
                eventSource.close();
            };
        }
    </script>
</body>
</html>
"""
```

---

## Error Handling

### Comprehensive Error Handling Pattern

```python
# In backend/app/api/enrichment.py (add error handlers)

from fastapi import Request
from fastapi.responses import JSONResponse


class EnrichmentException(Exception):
    """Base exception for enrichment service"""
    def __init__(self, message: str, status_code: int = 500):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


class EnrichmentTimeoutException(EnrichmentException):
    """Raised when enrichment times out"""
    def __init__(self):
        super().__init__("Enrichment timed out after 30 seconds", 504)


class InvalidContactException(EnrichmentException):
    """Raised when contact data is invalid"""
    def __init__(self, detail: str):
        super().__init__(f"Invalid contact data: {detail}", 400)


@router.exception_handler(EnrichmentException)
async def enrichment_exception_handler(request: Request, exc: EnrichmentException):
    """Handle custom enrichment exceptions"""
    logger.error(f"Enrichment error: {exc.message}")

    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.message,
            "status_code": exc.status_code,
            "request_path": str(request.url.path),
        },
    )


# Usage in endpoints
@router.post("/safe-single")
async def enrich_safe_contact(request: EnrichmentRequest) -> EnrichmentResponse:
    """Enrichment with comprehensive error handling"""

    # Validate input
    if not request.email:
        raise InvalidContactException("Email is required")

    if "@" not in request.email:
        raise InvalidContactException("Invalid email format")

    try:
        executor = SyncEnrichmentExecutor(
            config=AgentConfig(timeout_seconds=30)
        )
        result = executor.enrich(
            email=str(request.email),
            linkedin_url=str(request.linkedin_url) if request.linkedin_url else None,
        )

        if result.status == "error":
            raise EnrichmentException(result.error, 500)

        return EnrichmentResponse(
            status=result.status,
            enrichment_data=result.enrichment_data,
            final_response=result.final_response,
            iterations=result.metrics.iterations,
            tools_called=result.metrics.tool_calls,
            error=result.error,
        )

    except GraphRecursionError:
        raise EnrichmentException(
            "Enrichment exceeded maximum iterations", 504
        )
    except TimeoutError:
        raise EnrichmentTimeoutException()
    except Exception as e:
        logger.exception("Unexpected enrichment error")
        raise EnrichmentException(str(e), 500)
```

---

## Request/Response Models

### Pydantic Models

```python
# backend/app/schemas/enrichment.py

from pydantic import BaseModel, EmailStr, HttpUrl, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class EnrichmentContactInput(BaseModel):
    """Input contact data"""
    email: EmailStr
    linkedin_url: Optional[HttpUrl] = None

    class Config:
        json_schema_extra = {
            "example": {
                "email": "john@acme.com",
                "linkedin_url": "https://linkedin.com/in/johndoe"
            }
        }


class ApolloEnrichmentData(BaseModel):
    """Apollo.io enrichment result"""
    name: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    company_size: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    location: Optional[str] = None
    industry: Optional[str] = None


class LinkedInEnrichmentData(BaseModel):
    """LinkedIn enrichment result"""
    name: Optional[str] = None
    headline: Optional[str] = None
    about: Optional[str] = None
    experience: List[Dict[str, Any]] = []
    skills: List[str] = []
    education: Optional[Dict[str, Any]] = None
    endorsements: Dict[str, int] = {}


class EnrichmentSummary(BaseModel):
    """Final enrichment summary"""
    email: str
    full_name: Optional[str] = None
    title: Optional[str] = None
    company: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    skills: List[str] = []
    enrichment_score: float = Field(ge=0, le=100)
    data_sources: List[str]
    enriched_at: datetime


class EnrichmentMetricsResponse(BaseModel):
    """Execution metrics"""
    total_time_ms: float
    iterations: int
    tool_calls: int
    tools_succeeded: int
    tools_failed: int
    recursion_limit_exceeded: bool


class FullEnrichmentResponse(BaseModel):
    """Complete enrichment response"""
    status: str  # "success" | "partial" | "error"
    contact: EnrichmentContactInput
    apollo_data: Optional[ApolloEnrichmentData] = None
    linkedin_data: Optional[LinkedInEnrichmentData] = None
    enrichment_summary: Optional[EnrichmentSummary] = None
    metrics: EnrichmentMetricsResponse
    final_response: str
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "contact": {"email": "john@acme.com"},
                "apollo_data": {
                    "name": "John Doe",
                    "title": "Senior Engineer",
                    "company": "Acme Corp"
                },
                "enrichment_summary": {
                    "full_name": "John Doe",
                    "enrichment_score": 85.5
                },
                "metrics": {
                    "total_time_ms": 8450.5,
                    "iterations": 9,
                    "tool_calls": 3
                }
            }
        }
```

---

## Integration Example

### Complete FastAPI Integration

```python
# backend/app/api/enrichment_integration.py

from fastapi import FastAPI, APIRouter
from contextlib import asynccontextmanager
from app.api.enrichment import router as enrichment_router


# Lifespan management for resource initialization
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup resources"""
    logger.info("Starting enrichment service")

    # Verify agent configuration
    executor = SyncEnrichmentExecutor()
    logger.info("Enrichment agent initialized successfully")

    yield

    logger.info("Shutting down enrichment service")


def create_enrichment_app() -> FastAPI:
    """Create FastAPI app with enrichment endpoints"""

    app = FastAPI(
        title="Contact Enrichment API",
        description="LangGraph ReAct agent for contact enrichment",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Include enrichment routes
    app.include_router(enrichment_router)

    # Root endpoint
    @app.get("/", tags=["health"])
    async def root():
        return {
            "service": "contact-enrichment",
            "status": "operational",
            "endpoints": {
                "single": "/api/enrich/single",
                "batch": "/api/enrich/batch",
                "stream": "/api/enrich/stream",
                "docs": "/docs",
            },
        }

    return app


# Run with: uvicorn backend.app.api.enrichment_integration:app --reload
if __name__ == "__main__":
    import uvicorn
    app = create_enrichment_app()
    uvicorn.run(app, host="0.0.0.0", port=8001)
```

### Client Usage Examples

```python
# example_client.py

import asyncio
import httpx
import json


async def example_single_enrichment():
    """Example: Single contact enrichment"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/api/enrich/single",
            json={
                "email": "john@acme.com",
                "linkedin_url": "https://linkedin.com/in/johndoe"
            }
        )

        result = response.json()
        print(f"Status: {result['status']}")
        print(f"Enrichment Score: {result['enrichment_score']}")
        print(f"Time: {result['metrics']['total_time_ms']:.1f}ms")


async def example_batch_enrichment():
    """Example: Batch enrichment"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8001/api/enrich/batch",
            json={
                "contacts": [
                    {"email": "john@acme.com"},
                    {"email": "jane@corp.com"},
                    {"email": "bob@startup.io"},
                ],
                "max_concurrent": 3
            }
        )

        result = response.json()
        print(f"Total: {result['total_contacts']}")
        print(f"Successful: {result['successful']}")
        print(f"Time: {result['total_time_seconds']:.1f}s")


async def example_streaming_enrichment():
    """Example: Streaming enrichment"""
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST",
            "http://localhost:8001/api/enrich/stream",
            json={"email": "john@acme.com"}
        ) as response:
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    data = json.loads(line[6:])
                    if data["event"] == "tool_call":
                        print(f"Calling: {[t['name'] for t in data['tools']]}")
                    elif data["event"] == "tool_result":
                        print(f"Result: {data['tool_name']} = {data['status']}")
                    elif data["event"] == "complete":
                        print(f"Done in {data['total_iterations']} iterations")


# Run examples
if __name__ == "__main__":
    print("Single enrichment...")
    asyncio.run(example_single_enrichment())

    print("\nBatch enrichment...")
    asyncio.run(example_batch_enrichment())

    print("\nStreaming enrichment...")
    asyncio.run(example_streaming_enrichment())
```

---

## Testing

### Unit Tests for Endpoints

```python
# backend/tests/test_enrichment_api.py

import pytest
from fastapi.testclient import TestClient
from app.api.enrichment_integration import create_enrichment_app


@pytest.fixture
def client():
    """Create test client"""
    app = create_enrichment_app()
    return TestClient(app)


def test_health_check(client):
    """Test health endpoint"""
    response = client.get("/api/enrich/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_invalid_email(client):
    """Test invalid email handling"""
    response = client.post(
        "/api/enrich/single",
        json={"email": "invalid-email"}
    )
    assert response.status_code == 422  # Pydantic validation error


def test_enrichment_success(client, mocker):
    """Test successful enrichment"""
    # Mock the agent
    mocker.patch(
        "app.services.langgraph_react_patterns.SyncEnrichmentExecutor.enrich",
        return_value=EnrichmentResult(
            status="success",
            enrichment_data={
                "apollo_data": {"name": "John Doe"},
                "enrichment_summary": {"enrichment_score": 85.0}
            },
            final_response="Enrichment complete",
            metrics=AgentExecutionMetrics(...)
        )
    )

    response = client.post(
        "/api/enrich/single",
        json={"email": "test@example.com"}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "success"
    assert response.json()["enrichment_score"] == 85.0


@pytest.mark.asyncio
async def test_batch_enrichment(client, mocker):
    """Test batch enrichment"""
    mocker.patch(
        "app.services.langgraph_react_patterns.AsyncEnrichmentExecutor.enrich_batch",
        return_value=[...]
    )

    response = client.post(
        "/api/enrich/batch",
        json={
            "contacts": [
                {"email": "john@acme.com"},
                {"email": "jane@corp.com"}
            ]
        }
    )

    assert response.status_code == 202  # Accepted
    assert response.json()["total_contacts"] == 2
```

---

## Deployment Considerations

### Production Configuration

```python
# backend/app/core/config.py

from pydantic_settings import BaseSettings


class EnrichmentSettings(BaseSettings):
    """Enrichment service configuration"""

    # LLM Configuration
    model: str = "claude-3-5-sonnet-20241022"
    temperature: float = 0.7
    max_tokens: int = 2000

    # Agent Configuration
    recursion_limit: int = 25
    timeout_seconds: int = 30
    enable_checkpointing: bool = True

    # API Configuration
    batch_max_concurrent: int = 5
    batch_max_size: int = 100

    # Monitoring
    log_level: str = "INFO"
    enable_metrics: bool = True

    class Config:
        env_file = ".env"
        env_prefix = "ENRICHMENT_"


# Usage in FastAPI
settings = EnrichmentSettings()

agent_config = AgentConfig(
    model=settings.model,
    temperature=settings.temperature,
    recursion_limit=settings.recursion_limit,
)
```

### Docker Deployment

```dockerfile
# Dockerfile for enrichment service

FROM python:3.13-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY backend/ ./backend/

# Set environment
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/api/enrich/health || exit 1

# Run
CMD ["uvicorn", "backend.app.api.enrichment_integration:app", \
     "--host", "0.0.0.0", "--port", "8001"]
```

