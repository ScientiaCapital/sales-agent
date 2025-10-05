"""Context7 MCP Server with RunPod vLLM Load Balancer Backend.

This FastAPI-based MCP server provides Context7 research capabilities
using RunPod's vLLM inference for cost-effective AI operations.

Architecture:
- FastAPI for HTTP endpoints
- AsyncOpenAI client for RunPod vLLM backend
- Health checks for auto-scaling
- Structured error handling and logging
"""

from typing import Optional
from datetime import datetime
import os
import logging

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from openai import AsyncOpenAI
import httpx

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Context7 MCP Load Balancer",
    version="1.0.0",
    description="Context7 research server with RunPod vLLM backend",
    docs_url="/docs",
    redoc_url="/redoc",
)

# RunPod vLLM client configuration
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
RUNPOD_VLLM_ENDPOINT_ID = os.getenv("RUNPOD_VLLM_ENDPOINT_ID")

if not RUNPOD_API_KEY or not RUNPOD_VLLM_ENDPOINT_ID:
    logger.warning(
        "RUNPOD_API_KEY or RUNPOD_VLLM_ENDPOINT_ID not set. "
        "Research endpoint will fail without valid credentials."
    )

# Initialize AsyncOpenAI client for RunPod vLLM
# Uses custom base_url to route to RunPod load balancing endpoint
vllm_client = AsyncOpenAI(
    api_key=RUNPOD_API_KEY or "dummy-key",
    base_url=f"https://api.runpod.ai/v2/{RUNPOD_VLLM_ENDPOINT_ID or 'dummy'}/openai/v1",
    timeout=httpx.Timeout(60.0, connect=10.0),  # 60s total, 10s connect
) if RUNPOD_API_KEY and RUNPOD_VLLM_ENDPOINT_ID else None


# Request/Response Models
class ResearchRequest(BaseModel):
    """Research query request model."""
    query: str = Field(..., min_length=1, max_length=5000, description="Research query to process")
    max_tokens: Optional[int] = Field(2000, ge=100, le=4000, description="Maximum tokens in response")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Sampling temperature")


class ResearchResponse(BaseModel):
    """Research query response model."""
    result: str = Field(..., description="Research result from vLLM")
    model: str = Field(..., description="Model used for inference")
    tokens_used: Optional[int] = Field(None, description="Total tokens consumed")
    latency_ms: int = Field(..., description="Request latency in milliseconds")
    timestamp: str = Field(..., description="Response timestamp")


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service health status")
    service: str = Field(..., description="Service name")
    timestamp: str = Field(..., description="Health check timestamp")
    vllm_configured: bool = Field(..., description="Whether vLLM backend is configured")


# Health Check Endpoint
@app.get("/ping", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Health check endpoint for RunPod auto-scaling.
    
    RunPod monitors this endpoint to determine worker health.
    Returns 200 OK if service is healthy.
    
    Returns:
        HealthResponse with service status and metadata
    """
    return HealthResponse(
        status="healthy",
        service="context7-mcp",
        timestamp=datetime.utcnow().isoformat(),
        vllm_configured=vllm_client is not None
    )


# Research Endpoint
@app.post("/v1/research", response_model=ResearchResponse)
async def research(request: ResearchRequest) -> ResearchResponse:
    """Context7 research endpoint with RunPod vLLM backend.
    
    Processes research queries using RunPod's vLLM load balancer.
    Automatically scales based on request volume.
    
    Args:
        request: ResearchRequest with query and parameters
    
    Returns:
        ResearchResponse with research results and metadata
    
    Raises:
        HTTPException: 500 if vLLM backend is not configured
        HTTPException: 503 if vLLM backend is unavailable
        HTTPException: 504 if request times out
    """
    start_time = datetime.utcnow()
    
    # Validate vLLM client is configured
    if not vllm_client:
        logger.error("vLLM client not configured - missing RUNPOD_API_KEY or RUNPOD_VLLM_ENDPOINT_ID")
        raise HTTPException(
            status_code=500,
            detail="RunPod vLLM backend not configured. Set RUNPOD_API_KEY and RUNPOD_VLLM_ENDPOINT_ID."
        )
    
    try:
        # Call RunPod vLLM via OpenAI-compatible API
        logger.info(f"Processing research query: {request.query[:100]}...")
        
        response = await vllm_client.chat.completions.create(
            model="meta-llama/Llama-3.1-8B",
            messages=[
                {
                    "role": "system",
                    "content": "You are a research assistant. Provide comprehensive, accurate answers based on the query."
                },
                {
                    "role": "user",
                    "content": f"Research query: {request.query}"
                }
            ],
            max_tokens=request.max_tokens,
            temperature=request.temperature,
        )
        
        # Calculate latency
        end_time = datetime.utcnow()
        latency_ms = int((end_time - start_time).total_seconds() * 1000)
        
        # Extract result
        result_text = response.choices[0].message.content
        tokens_used = response.usage.total_tokens if response.usage else None
        
        logger.info(f"Research completed in {latency_ms}ms, tokens: {tokens_used}")
        
        return ResearchResponse(
            result=result_text,
            model=response.model,
            tokens_used=tokens_used,
            latency_ms=latency_ms,
            timestamp=end_time.isoformat()
        )
        
    except httpx.TimeoutException as e:
        logger.error(f"RunPod vLLM timeout: {e}")
        raise HTTPException(
            status_code=504,
            detail="Request to vLLM backend timed out. Try again with a shorter query."
        )
    
    except Exception as e:
        logger.error(f"RunPod vLLM error: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"vLLM backend unavailable: {str(e)}"
        )


# Root Endpoint
@app.get("/")
async def root():
    """Root endpoint with service information."""
    return {
        "service": "Context7 MCP Load Balancer",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/ping",
            "research": "/v1/research",
            "docs": "/docs"
        }
    }


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle uncaught exceptions."""
    logger.error(f"Uncaught exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Check logs for details."}
    )


if __name__ == "__main__":
    import uvicorn
    
    # Run the server
    uvicorn.run(
        "context7_load_balancer:app",
        host="0.0.0.0",
        port=8002,
        reload=True,
        log_level="info"
    )
