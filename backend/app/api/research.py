"""
Multi-Agent Research Pipeline API

POST /api/research - Execute 5-agent research pipeline
GET /api/research/status - Get pipeline status
"""

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging
import json

from app.services.research_pipeline import (
    ResearchPipeline,
    ResearchResult,
    AgentExecution
)
from app.services.cerebras_routing import CerebrasAccessMethod

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/research", tags=["research"])


class ResearchRequest(BaseModel):
    """Request for multi-agent research."""
    topic: str = Field(..., description="Research topic or question", min_length=10)
    depth: str = Field("medium", description="Research depth (shallow|medium|deep)")
    format_style: str = Field("markdown", description="Output format (markdown|json|plain)")
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="Model temperature")
    stream: bool = Field(False, description="Enable streaming responses")
    preferred_method: Optional[str] = Field(
        "direct",
        description="Preferred Cerebras access method (direct|openrouter|langchain)"
    )
    max_queries: int = Field(5, ge=1, le=10, description="Max search queries to generate")
    timeout_seconds: float = Field(10.0, ge=1.0, le=60.0, description="Pipeline timeout")

    class Config:
        json_schema_extra = {
            "example": {
                "topic": "What are the latest advances in AI agent frameworks?",
                "depth": "medium",
                "format_style": "markdown",
                "temperature": 0.7,
                "stream": False,
                "preferred_method": "direct",
                "max_queries": 5,
                "timeout_seconds": 10.0
            }
        }


class ResearchResponse(BaseModel):
    """Response from research pipeline."""
    research_topic: str
    final_output: str
    total_latency_ms: int
    total_cost_usd: float
    queries_generated: List[str]
    search_results_count: int
    agents_executed: int
    metadata: Dict[str, Any]


@router.post("/", response_model=ResearchResponse, status_code=status.HTTP_200_OK)
async def execute_research(request: ResearchRequest):
    """
    Execute multi-agent research pipeline.

    **Pipeline (5 agents):**
    1. **QueryGenerator**: Creates 3-5 optimized search queries
    2. **WebSearcher**: Executes searches (simulated with LLM knowledge)
    3. **Summarizer**: Extracts key points from results
    4. **Synthesizer**: Combines insights into coherent narrative
    5. **Formatter**: Produces final polished output

    **Target:** <10s total execution time

    **Returns:**
    - Final research output
    - Execution metrics
    - Query and result details
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

        # Initialize research pipeline
        pipeline = ResearchPipeline(
            preferred_method=method,
            max_queries=request.max_queries,
            timeout_seconds=request.timeout_seconds
        )

        logger.info(
            f"Starting research: topic={request.topic[:50]}..., "
            f"timeout={request.timeout_seconds}s"
        )

        # Execute research
        result: ResearchResult = await pipeline.research(
            topic=request.topic,
            depth=request.depth,
            format_style=request.format_style,
            temperature=request.temperature
        )

        # Build response
        response = ResearchResponse(
            research_topic=result.research_topic,
            final_output=result.final_output,
            total_latency_ms=result.total_latency_ms,
            total_cost_usd=result.total_cost_usd,
            queries_generated=result.queries_generated,
            search_results_count=result.search_results_count,
            agents_executed=len(result.agent_executions),
            metadata=result.metadata
        )

        logger.info(
            f"Research complete: {result.total_latency_ms}ms, "
            f"${result.total_cost_usd:.6f}, "
            f"{len(result.agent_executions)} agents"
        )

        return response

    except Exception as e:
        logger.error(f"Research failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Research pipeline failed: {str(e)}"
        )


@router.post("/stream")
async def execute_research_stream(request: ResearchRequest):
    """
    Execute research pipeline with streaming progress updates.

    **Returns:** Server-Sent Events stream with:
    - pipeline_start
    - agent_start (for each agent)
    - agent_complete (for each agent)
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

        # Initialize research pipeline
        pipeline = ResearchPipeline(
            preferred_method=method,
            max_queries=request.max_queries,
            timeout_seconds=request.timeout_seconds
        )

        async def event_generator():
            """Generate SSE events for research progress."""
            try:
                async for event in pipeline.stream_research(
                    topic=request.topic,
                    depth=request.depth,
                    format_style=request.format_style,
                    temperature=request.temperature
                ):
                    # Format as SSE
                    yield f"data: {json.dumps(event)}\n\n"

            except Exception as e:
                logger.error(f"Streaming research failed: {str(e)}", exc_info=True)
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
                "X-Accel-Buffering": "no"
            }
        )

    except Exception as e:
        logger.error(f"Stream setup failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Streaming setup failed: {str(e)}"
        )


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_research_status():
    """
    Get research pipeline status.

    **Returns:**
    - Pipeline configuration
    - Resource usage statistics
    - Router status
    """
    try:
        # Create temporary pipeline to get status
        pipeline = ResearchPipeline()
        return pipeline.get_status()

    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve status: {str(e)}"
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check for research service.

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
            "service": "research_pipeline",
            "available_methods": available_methods,
            "total_methods": len(clients_initialized),
            "circuit_breakers": {
                method: status["circuit_breaker"]["state"]
                for method, status in router_status.get("access_methods", {}).items()
            },
            "target_execution_time": "<10s"
        }

        return health_status

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}", exc_info=True)
        return {
            "status": "unhealthy",
            "service": "research_pipeline",
            "error": str(e)
        }
