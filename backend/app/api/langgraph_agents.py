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
import time
import uuid
from datetime import datetime

from app.models.database import get_db
from app.models.langgraph_models import LangGraphExecution, LangGraphCheckpoint, LangGraphToolCall
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

        # Import and invoke actual agents
        from app.services.langgraph.agents.qualification_agent import QualificationAgent
        from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
        from app.services.langgraph.agents.growth_agent import GrowthAgent
        from app.services.langgraph.agents.marketing_agent import MarketingAgent
        from app.services.langgraph.agents.bdr_agent import BDRAgent
        from app.services.langgraph.agents.conversation_agent import ConversationAgent
        
        # Track execution start time
        start_time = time.time()
        
        # Create execution record
        execution = LangGraphExecution(
            execution_id=str(uuid.uuid4()),
            agent_type=request.agent_type,
            thread_id=thread_id,
            status="running",
            started_at=datetime.utcnow(),
            input_data=request.input,
            graph_type="chain" if request.agent_type in ["qualification", "enrichment"] else "graph"
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        
        try:
            # Invoke appropriate agent
            if request.agent_type == "qualification":
                agent = QualificationAgent()
                result = await agent.qualify(**request.input)
                output_data = {
                    "score": result.qualification_score,
                    "reasoning": result.qualification_reasoning,
                    "tier": result.tier,
                    "confidence": result.confidence_score,
                    "recommendations": result.recommendations
                }
                
            elif request.agent_type == "enrichment":
                agent = EnrichmentAgent()
                result = await agent.enrich(**request.input)
                output_data = {
                    "enriched_data": result.enriched_data,
                    "sources": result.sources,
                    "confidence": result.confidence_score,
                    "completeness": result.completeness_score
                }
                
            elif request.agent_type == "growth":
                agent = GrowthAgent()
                result = await agent.analyze(**request.input)
                output_data = {
                    "opportunities": result.opportunities,
                    "confidence": result.confidence_score,
                    "market_analysis": result.market_analysis,
                    "recommendations": result.recommendations
                }
                
            elif request.agent_type == "marketing":
                agent = MarketingAgent()
                result = await agent.generate(**request.input)
                output_data = {
                    "campaigns": result.campaigns,
                    "channels": result.channels,
                    "personalization": result.personalization_data,
                    "performance_prediction": result.performance_prediction
                }
                
            elif request.agent_type == "bdr":
                agent = BDRAgent()
                result = await agent.book(**request.input)
                output_data = {
                    "status": result.status,
                    "calendar_link": result.calendar_link,
                    "scheduled_time": result.scheduled_time,
                    "meeting_type": result.meeting_type,
                    "next_steps": result.next_steps
                }
                
            elif request.agent_type == "conversation":
                agent = ConversationAgent()
                result = await agent.converse(**request.input)
                output_data = {
                    "response": result.response,
                    "audio_data": result.audio_data,
                    "sentiment": result.sentiment,
                    "intent": result.intent,
                    "next_action": result.next_action
                }
            
            # Calculate execution metrics
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            
            # Update execution record
            execution.status = "success"
            execution.completed_at = datetime.utcnow()
            execution.duration_ms = duration_ms
            execution.output_data = output_data
            execution.cost_usd = getattr(result, 'cost_usd', 0.0)
            execution.tokens_used = getattr(result, 'tokens_used', 0)
            
            db.commit()
            
            # Prepare response
            response_data = AgentResponse(
                status="success",
                agent_type=request.agent_type,
                thread_id=thread_id,
                output=output_data,
                metadata={
                    "execution_id": execution.execution_id,
                    "duration_ms": duration_ms,
                    "cost_usd": execution.cost_usd,
                    "tokens_used": execution.tokens_used,
                    "graph_type": execution.graph_type
                },
                timestamp=execution.completed_at.isoformat()
            )
            
            logger.info(f"✅ {request.agent_type} agent completed successfully in {duration_ms}ms")
            return response_data
            
        except Exception as e:
            # Update execution record with error
            end_time = time.time()
            duration_ms = int((end_time - start_time) * 1000)
            
            execution.status = "failed"
            execution.completed_at = datetime.utcnow()
            execution.duration_ms = duration_ms
            execution.error_message = str(e)
            
            db.commit()
            
            logger.error(f"❌ {request.agent_type} agent failed: {str(e)}", exc_info=True)
            
            raise HTTPException(
                status_code=500,
                detail=f"Agent execution failed: {str(e)}"
            )

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

                # Import agents
                from app.services.langgraph.agents.qualification_agent import QualificationAgent
                from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
                from app.services.langgraph.agents.growth_agent import GrowthAgent
                from app.services.langgraph.agents.marketing_agent import MarketingAgent
                from app.services.langgraph.agents.bdr_agent import BDRAgent
                from app.services.langgraph.agents.conversation_agent import ConversationAgent
                
                # Track execution start time
                start_time = time.time()
                
                # Create execution record
                execution = LangGraphExecution(
                    execution_id=str(uuid.uuid4()),
                    agent_type=request.agent_type,
                    thread_id=thread_id,
                    status="running",
                    started_at=datetime.utcnow(),
                    input_data=request.input,
                    graph_type="chain" if request.agent_type in ["qualification", "enrichment"] else "graph"
                )
                db.add(execution)
                db.commit()
                db.refresh(execution)
                
                try:
                    # Send progress event
                    yield f"data: {json.dumps({'type': 'message', 'content': f'Starting {request.agent_type} agent...'})}\n\n"
                    
                    # Invoke appropriate agent
                    if request.agent_type == "qualification":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Qualifying lead with Cerebras AI...'})}\n\n"
                        agent = QualificationAgent()
                        result = await agent.qualify(**request.input)
                        output_data = {
                            "score": result.qualification_score,
                            "reasoning": result.qualification_reasoning,
                            "tier": result.tier,
                            "confidence": result.confidence_score,
                            "recommendations": result.recommendations
                        }
                        
                    elif request.agent_type == "enrichment":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Enriching contact data...'})}\n\n"
                        agent = EnrichmentAgent()
                        result = await agent.enrich(**request.input)
                        output_data = {
                            "enriched_data": result.enriched_data,
                            "sources": result.sources,
                            "confidence": result.confidence_score,
                            "completeness": result.completeness_score
                        }
                        
                    elif request.agent_type == "growth":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Analyzing growth opportunities...'})}\n\n"
                        agent = GrowthAgent()
                        result = await agent.analyze(**request.input)
                        output_data = {
                            "opportunities": result.opportunities,
                            "confidence": result.confidence_score,
                            "market_analysis": result.market_analysis,
                            "recommendations": result.recommendations
                        }
                        
                    elif request.agent_type == "marketing":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Generating marketing campaigns...'})}\n\n"
                        agent = MarketingAgent()
                        result = await agent.generate(**request.input)
                        output_data = {
                            "campaigns": result.campaigns,
                            "channels": result.channels,
                            "personalization": result.personalization_data,
                            "performance_prediction": result.performance_prediction
                        }
                        
                    elif request.agent_type == "bdr":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Processing BDR workflow...'})}\n\n"
                        agent = BDRAgent()
                        result = await agent.book(**request.input)
                        output_data = {
                            "status": result.status,
                            "calendar_link": result.calendar_link,
                            "scheduled_time": result.scheduled_time,
                            "meeting_type": result.meeting_type,
                            "next_steps": result.next_steps
                        }
                        
                    elif request.agent_type == "conversation":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Processing conversation...'})}\n\n"
                        agent = ConversationAgent()
                        result = await agent.converse(**request.input)
                        output_data = {
                            "response": result.response,
                            "audio_data": result.audio_data,
                            "sentiment": result.sentiment,
                            "intent": result.intent,
                            "next_action": result.next_action
                        }
                    
                    # Calculate execution metrics
                    end_time = time.time()
                    duration_ms = int((end_time - start_time) * 1000)
                    
                    # Update execution record
                    execution.status = "success"
                    execution.completed_at = datetime.utcnow()
                    execution.duration_ms = duration_ms
                    execution.output_data = output_data
                    execution.cost_usd = getattr(result, 'cost_usd', 0.0)
                    execution.tokens_used = getattr(result, 'tokens_used', 0)
                    
                    db.commit()
                    
                    # Send completion event
                    yield f"data: {json.dumps({'type': 'complete', 'output': output_data, 'metadata': {'duration_ms': duration_ms, 'cost_usd': execution.cost_usd}})}\n\n"
                    
                except Exception as e:
                    # Update execution record with error
                    end_time = time.time()
                    duration_ms = int((end_time - start_time) * 1000)
                    
                    execution.status = "failed"
                    execution.completed_at = datetime.utcnow()
                    execution.duration_ms = duration_ms
                    execution.error_message = str(e)
                    
                    db.commit()
                    
                    # Send error event
                    yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'metadata': {'duration_ms': duration_ms}})}\n\n"
                    raise
                    
            except Exception as e:
                logger.error(f"Error in event generator: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

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
