"""
Iterative Refinement API Endpoint

POST /api/refine - Execute 4-step refinement process
GET /api/refine/status - Get refinement engine status
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
import logging
import json

from app.services.iterative_refinement import (
    IterativeRefinementEngine,
    RefinementResult,
    RefinementStep
)
from app.services.cerebras_routing import CerebrasAccessMethod

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/refine", tags=["refinement"])


class RefineRequest(BaseModel):
    """Request for iterative refinement."""
    prompt: str = Field(..., description="User's original request", min_length=10)
    context: Optional[str] = Field(None, description="Additional context or background")
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="Model temperature")
    stream: bool = Field(False, description="Enable streaming responses")
    preferred_method: Optional[str] = Field(
        "direct",
        description="Preferred Cerebras access method (direct|openrouter|langchain|cartesia)"
    )
    target_improvement: Optional[float] = Field(
        0.40,
        ge=0.0,
        le=1.0,
        description="Target quality improvement (default: 0.40 = 40%)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Explain how Kubernetes works to a beginner",
                "context": "Audience is new to DevOps and containerization",
                "temperature": 0.7,
                "stream": False,
                "preferred_method": "direct",
                "target_improvement": 0.40
            }
        }


class RefineResponse(BaseModel):
    """Response from refinement process."""
    initial_response: str
    refined_response: str
    quality_improvement: float
    total_latency_ms: int
    total_cost_usd: float
    iterations: int
    metadata: Dict[str, Any]


@router.post("/", response_model=RefineResponse, status_code=status.HTTP_200_OK)
async def refine_prompt(request: RefineRequest):
    """
    Execute iterative refinement process on a prompt.

    **Process:**
    1. INITIAL: Generate baseline response
    2. REFLECT: Analyze gaps and weaknesses
    3. ELABORATE: Expand with detail
    4. CRITIQUE: Identify remaining issues
    5. REFINE: Produce final polished output

    **Target:** 40% quality improvement over baseline

    **Returns:**
    - Initial and refined responses
    - Quality improvement metric
    - Latency and cost tracking
    - Iteration details
    """
    try:
        # Parse preferred method
        try:
            method = CerebrasAccessMethod(request.preferred_method)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid preferred_method: {request.preferred_method}. "
                       f"Must be one of: direct, openrouter, langchain, cartesia"
            )

        # Initialize refinement engine
        engine = IterativeRefinementEngine(
            preferred_method=method,
            target_quality_improvement=request.target_improvement
        )

        logger.info(
            f"Starting refinement: method={method.value}, "
            f"prompt={request.prompt[:50]}..."
        )

        # Execute refinement
        result: RefinementResult = await engine.refine(
            prompt=request.prompt,
            context=request.context,
            temperature=request.temperature,
            stream=request.stream
        )

        # Build response
        response = RefineResponse(
            initial_response=result.initial_response,
            refined_response=result.refined_response,
            quality_improvement=result.quality_improvement,
            total_latency_ms=result.total_latency_ms,
            total_cost_usd=result.total_cost_usd,
            iterations=len(result.iterations),
            metadata=result.metadata
        )

        logger.info(
            f"Refinement complete: {result.quality_improvement:.1%} improvement, "
            f"{result.total_latency_ms}ms, ${result.total_cost_usd:.6f}"
        )

        return response

    except Exception as e:
        logger.error(f"Refinement failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Refinement process failed: {str(e)}"
        )


@router.post("/stream")
async def refine_prompt_stream(request: RefineRequest):
    """
    Execute iterative refinement with streaming progress updates.

    **Returns:** Server-Sent Events stream with:
    - process_start
    - step_start (for each step)
    - step_complete (for each step)
    - final (with complete result)
    """
    try:
        # Parse preferred method
        try:
            method = CerebrasAccessMethod(request.preferred_method)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid preferred_method: {request.preferred_method}"
            )

        # Initialize refinement engine
        engine = IterativeRefinementEngine(
            preferred_method=method,
            target_quality_improvement=request.target_improvement
        )

        async def event_generator():
            """Generate SSE events for refinement progress."""
            try:
                async for event in engine.stream_refine(
                    prompt=request.prompt,
                    context=request.context,
                    temperature=request.temperature
                ):
                    # Format as SSE
                    yield f"data: {json.dumps(event)}\n\n"

            except Exception as e:
                logger.error(f"Streaming refinement failed: {str(e)}", exc_info=True)
                error_event = {
                    "type": "error",
                    "message": str(e)
                }
                yield f"data: {json.dumps(error_event)}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )

    except Exception as e:
        logger.error(f"Stream setup failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Streaming setup failed: {str(e)}"
        )


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_refinement_status():
    """
    Get current refinement engine status.

    **Returns:**
    - Preferred access method
    - Target improvement percentage
    - Resource usage statistics
    - Router status
    """
    try:
        # Create temporary engine to get status
        engine = IterativeRefinementEngine()
        return engine.get_status()

    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve status: {str(e)}"
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check for refinement service.

    **Returns:**
    - Service health status
    - Available access methods
    - Circuit breaker states
    """
    try:
        from app.services.cerebras_routing import CerebrasRouter

        router_instance = CerebrasRouter()
        router_status = router_instance.get_status()

        # Check if at least one method is available
        clients_initialized = router_status.get("clients_initialized", {})
        available_methods = [
            method for method, available in clients_initialized.items()
            if available
        ]

        health_status = {
            "status": "healthy" if available_methods else "degraded",
            "service": "iterative_refinement",
            "available_methods": available_methods,
            "total_methods": len(clients_initialized),
            "circuit_breakers": {
                method: status["circuit_breaker"]["state"]
                for method, status in router_status.get("access_methods", {}).items()
            }
        }

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "service": "iterative_refinement",
            "error": str(e)
        }
