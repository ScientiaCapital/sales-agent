"""
LangGraph Agent API Endpoints

Provides REST API endpoints for invoking LangGraph agents with streaming support.

Endpoints:
- POST /api/langgraph/invoke - Invoke agent and return complete response
- POST /api/langgraph/stream - Stream agent execution via Server-Sent Events (SSE)
- GET /api/langgraph/state/{thread_id} - Retrieve conversation state from checkpoint

Integration:
- Uses Redis checkpointing for conversation continuity
- Supports streaming via SSE for real-time responses
- Ready to integrate with agents built in Phases 3-4

Architecture:
- Phase 2 (Current): Endpoints with placeholder logic demonstrating patterns
- Phase 3: Plug in QualificationAgent and EnrichmentAgent (LCEL chains)
- Phase 4: Add GrowthAgent, MarketingAgent, BDRAgent, ConversationAgent (StateGraphs)
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, AsyncGenerator
import json
import logging
from datetime import datetime

from app.models.database import get_db
from app.services.langgraph import (
    get_redis_checkpointer,
    create_streaming_config,
    get_checkpoint_config,
    get_thread_id_for_lead,
)
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/langgraph", tags=["langgraph"])


# ========== Request/Response Schemas ==========

class InvokeAgentRequest(BaseModel):
    """Request schema for invoking a LangGraph agent."""

    agent_type: str = Field(
        ...,
        description="Agent type: qualification, enrichment, growth, marketing, bdr, conversation"
    )
    input: Dict[str, Any] = Field(
        ...,
        description="Input data matching the agent's state schema"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Thread ID for conversation continuity (auto-generated if not provided)"
    )
    lead_id: Optional[int] = Field(
        default=None,
        description="Lead ID to associate with this agent execution"
    )
    stream_mode: str = Field(
        default="values",
        description="Streaming mode: messages, updates, values, custom"
    )


class AgentResponse(BaseModel):
    """Response schema for agent invocation."""

    status: str = Field(description="Status: success, error, pending")
    agent_type: str = Field(description="Type of agent that was invoked")
    thread_id: str = Field(description="Thread ID for conversation continuity")
    output: Dict[str, Any] = Field(description="Agent output state")
    metadata: Dict[str, Any] = Field(description="Execution metadata (latency, cost, etc.)")
    timestamp: str = Field(description="ISO 8601 timestamp of completion")


class StateResponse(BaseModel):
    """Response schema for checkpoint state retrieval."""

    thread_id: str = Field(description="Thread ID")
    checkpoint_exists: bool = Field(description="Whether a checkpoint was found")
    state: Optional[Dict[str, Any]] = Field(description="Checkpoint state data")
    metadata: Optional[Dict[str, Any]] = Field(description="Checkpoint metadata")


# ========== Helper Functions ==========

async def get_or_create_thread_id(
    request: InvokeAgentRequest
) -> str:
    """
    Get thread ID from request or generate one.

    Args:
        request: Agent invocation request

    Returns:
        Thread ID string
    """
    if request.thread_id:
        return request.thread_id

    if request.lead_id:
        # Generate thread ID for lead-based conversation
        return get_thread_id_for_lead(request.lead_id)

    # Generate generic thread ID
    from uuid import uuid4
    return f"thread_{uuid4().hex[:16]}"


# ========== Endpoints ==========

@router.post("/invoke", response_model=AgentResponse, status_code=200)
async def invoke_agent(
    request: InvokeAgentRequest,
    db: Session = Depends(get_db)
):
    """
    Invoke a LangGraph agent and return the complete response.

    This endpoint executes a LangGraph agent with the provided input and returns
    the final state after completion. For real-time token streaming, use the
    /stream endpoint instead.

    Supported Agents:
    - qualification: Lead qualification with AI scoring
    - enrichment: Contact enrichment with tool calling (Apollo, LinkedIn)
    - growth: Multi-touch outreach campaigns (Phase 4)
    - marketing: Multi-channel content generation (Phase 4)
    - bdr: Human-in-loop outreach workflow (Phase 4)
    - conversation: Voice-enabled conversational agent (Phase 4)

    Args:
        request: Agent invocation request with type, input, and optional thread_id
        db: Database session

    Returns:
        AgentResponse with status, output state, and metadata

    Raises:
        HTTPException 400: Invalid agent type or input
        HTTPException 500: Agent execution error

    Example:
        ```bash
        curl -X POST http://localhost:8001/api/langgraph/invoke \\
          -H "Content-Type: application/json" \\
          -d '{
            "agent_type": "qualification",
            "input": {
              "company_name": "Acme Corp",
              "industry": "SaaS",
              "company_size": "50-200"
            },
            "lead_id": 123
          }'
        ```
    """
    try:
        # Validate agent type
        valid_agents = ["qualification", "enrichment", "growth", "marketing", "bdr", "conversation"]
        if request.agent_type not in valid_agents:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent_type. Must be one of: {', '.join(valid_agents)}"
            )

        # Get or create thread ID
        thread_id = await get_or_create_thread_id(request)

        # Initialize Redis checkpointer
        checkpointer = await get_redis_checkpointer()

        # Create streaming configuration
        config = create_streaming_config(
            thread_id=thread_id,
            stream_mode=request.stream_mode,
            recursion_limit=25
        )

        # TODO (Phase 3): Replace with actual agent invocation
        # Example for QualificationAgent:
        # from app.services.langgraph.agents import QualificationAgent
        # agent = QualificationAgent()
        # graph = await agent.compile(enable_checkpointing=True)
        # result = await graph.ainvoke(request.input, config)

        # Placeholder response demonstrating expected structure
        logger.info(f"Invoked {request.agent_type} agent with thread_id={thread_id}")

        placeholder_output = {
            "agent_type": request.agent_type,
            "messages": [],
            "metadata": {
                "note": "Phase 2 placeholder - actual agents will be implemented in Phase 3-4",
                "received_input": request.input,
                "thread_id": thread_id
            }
        }

        # Build response
        response = AgentResponse(
            status="success",
            agent_type=request.agent_type,
            thread_id=thread_id,
            output=placeholder_output,
            metadata={
                "latency_ms": 0,
                "cost_usd": 0.0,
                "phase": "placeholder",
                "note": "Actual agent execution will be added in Phase 3"
            },
            timestamp=datetime.utcnow().isoformat()
        )

        return response

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error invoking agent: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Agent invocation failed: {str(e)}"
        )


@router.post("/stream")
async def stream_agent(
    request: InvokeAgentRequest,
    db: Session = Depends(get_db)
):
    """
    Stream a LangGraph agent execution via Server-Sent Events (SSE).

    This endpoint provides real-time streaming of agent execution, including
    token-by-token LLM output and state updates. Use this for interactive
    experiences where users need immediate feedback.

    Streaming Modes:
    - messages: Token-by-token LLM output (for chat interfaces)
    - updates: Node-level state updates (for progress tracking)
    - values: Full state snapshots after each node (for debugging)
    - custom: Custom streaming data via writer()

    Args:
        request: Agent invocation request with type, input, and optional thread_id
        db: Database session

    Returns:
        StreamingResponse with text/event-stream media type

    Raises:
        HTTPException 400: Invalid agent type or input
        HTTPException 500: Agent execution error

    Example:
        ```bash
        curl -X POST http://localhost:8001/api/langgraph/stream \\
          -H "Content-Type: application/json" \\
          -d '{
            "agent_type": "enrichment",
            "input": {"email": "john@acme.com"},
            "stream_mode": "messages"
          }'
        ```

    SSE Event Format:
        ```
        data: {"type": "message", "content": "Enriching contact...", "metadata": {...}}

        data: {"type": "update", "node": "enrich_apollo", "state": {...}}

        data: {"type": "end", "output": {...}}
        ```
    """
    try:
        # Validate agent type
        valid_agents = ["qualification", "enrichment", "growth", "marketing", "bdr", "conversation"]
        if request.agent_type not in valid_agents:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent_type. Must be one of: {', '.join(valid_agents)}"
            )

        # Get or create thread ID
        thread_id = await get_or_create_thread_id(request)

        # Initialize Redis checkpointer
        checkpointer = await get_redis_checkpointer()

        # Create streaming configuration
        config = create_streaming_config(
            thread_id=thread_id,
            stream_mode=request.stream_mode,
            recursion_limit=25
        )

        async def event_generator() -> AsyncGenerator[str, None]:
            """
            Generate SSE events from agent execution.

            Yields:
                SSE-formatted strings with agent execution events
            """
            try:
                # Send initial event
                yield f"data: {json.dumps({'type': 'start', 'agent_type': request.agent_type, 'thread_id': thread_id})}\n\n"

                # TODO (Phase 3): Replace with actual agent streaming
                # Example for EnrichmentAgent:
                # from app.services.langgraph.agents import EnrichmentAgent
                # agent = EnrichmentAgent()
                # graph = await agent.compile(enable_checkpointing=True)
                #
                # async for event in graph.astream(request.input, config, stream_mode=request.stream_mode):
                #     yield f"data: {json.dumps({'type': 'message', 'content': event})}\n\n"

                # Placeholder streaming events
                logger.info(f"Streaming {request.agent_type} agent with thread_id={thread_id}")

                # Simulate progress events
                events = [
                    {"type": "message", "content": f"Initializing {request.agent_type} agent..."},
                    {"type": "update", "node": "start", "state": request.input},
                    {"type": "message", "content": "Processing input data..."},
                    {"type": "message", "content": "Phase 2 placeholder - actual streaming will be added in Phase 3"},
                ]

                for event in events:
                    yield f"data: {json.dumps(event)}\n\n"

                # Send completion event
                final_output = {
                    "type": "end",
                    "status": "success",
                    "output": {
                        "agent_type": request.agent_type,
                        "thread_id": thread_id,
                        "note": "Placeholder response - actual agent output will be added in Phase 3"
                    }
                }
                yield f"data: {json.dumps(final_output)}\n\n"

            except Exception as e:
                logger.error(f"Error in event generator: {e}", exc_info=True)
                error_event = {
                    "type": "error",
                    "error": str(e),
                    "timestamp": datetime.utcnow().isoformat()
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

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error setting up streaming: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initialize streaming: {str(e)}"
        )


@router.get("/state/{thread_id}", response_model=StateResponse, status_code=200)
async def get_agent_state(
    thread_id: str,
    checkpoint_id: Optional[str] = None
):
    """
    Retrieve conversation state from Redis checkpoint.

    This endpoint allows clients to retrieve the full conversation state for
    a given thread, including message history and agent-specific data. Useful
    for resuming conversations or displaying conversation history.

    Args:
        thread_id: Thread identifier for the conversation
        checkpoint_id: Optional specific checkpoint ID (defaults to latest)

    Returns:
        StateResponse with checkpoint state and metadata

    Raises:
        HTTPException 404: Thread ID not found in checkpoints
        HTTPException 500: Checkpoint retrieval error

    Example:
        ```bash
        # Get latest checkpoint for thread
        curl http://localhost:8001/api/langgraph/state/lead_123

        # Get specific checkpoint
        curl http://localhost:8001/api/langgraph/state/lead_123?checkpoint_id=abc123
        ```
    """
    try:
        # Initialize Redis checkpointer
        checkpointer = await get_redis_checkpointer()

        # Create checkpoint config
        config = get_checkpoint_config(thread_id, checkpoint_id)

        # Retrieve checkpoint
        checkpoint = await checkpointer.aget(config)

        if not checkpoint:
            raise HTTPException(
                status_code=404,
                detail=f"No checkpoint found for thread_id: {thread_id}"
            )

        # Extract state and metadata
        state = checkpoint.get("channel_values", {})
        metadata = checkpoint.get("metadata", {})

        logger.info(f"Retrieved checkpoint for thread_id={thread_id}")

        return StateResponse(
            thread_id=thread_id,
            checkpoint_exists=True,
            state=state,
            metadata=metadata
        )

    except HTTPException:
        raise

    except Exception as e:
        logger.error(f"Error retrieving checkpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve checkpoint state: {str(e)}"
        )


# ========== Exports ==========

__all__ = [
    "router",
    "InvokeAgentRequest",
    "AgentResponse",
    "StateResponse",
]
