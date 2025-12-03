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
import time
import uuid
from datetime import datetime

from app.models.database import get_db
from app.models.langgraph_models import LangGraphExecution
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
    # Multi-provider support
    provider: Optional[str] = Field(
        default="cerebras",
        description="LLM provider: cerebras, claude, deepseek, ollama (qualification agent only)"
    )
    model: Optional[str] = Field(
        default=None,
        description="Model ID (auto-selects if None). Examples: llama3.1-8b, claude-3-haiku-20240307, deepseek-chat, llama3.1:8b"
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
              "company_size": "50-200",
              "company_website": "https://acme.com",
              "contact_email": "john@acme.com"
            },
            "lead_id": 123
          }'
        ```

        Note: If contact_email is not provided and company_website is available,
        the qualification agent will automatically attempt to extract emails from the website.
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
        await get_redis_checkpointer()

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
                # Multi-provider support with configurable provider and model + cost tracking
                agent = QualificationAgent(
                    provider=request.provider or "cerebras",
                    model=request.model,  # None = auto-select
                    db=db  # Enable cost tracking
                )
                result, latency_ms, metadata = await agent.qualify(**request.input)
                output_data = {
                    "score": result.qualification_score,
                    "reasoning": result.qualification_reasoning,
                    "tier": result.tier,
                    "fit_assessment": result.fit_assessment,
                    "contact_quality": result.contact_quality,
                    "sales_potential": result.sales_potential,
                    "recommendations": result.recommendations or [],
                    # Include provider/model info in output
                    "provider": metadata.get("provider"),
                    "model": metadata.get("model")
                }
                
            elif request.agent_type == "enrichment":
                agent = EnrichmentAgent()
                result = await agent.enrich(**request.input)
                output_data = {
                    "enriched_data": result.enriched_data,
                    "data_sources": result.data_sources,  # Fixed: was 'sources'
                    "confidence_score": result.confidence_score,
                    "tools_called": result.tools_called,
                    "latency_ms": result.latency_ms,
                    "iterations_used": result.iterations_used,
                    "total_cost_usd": result.total_cost_usd,
                    "errors": result.errors
                }
                
            elif request.agent_type == "growth":
                agent = GrowthAgent()
                # GrowthAgent expects: lead_id, goal, max_cycles
                result = await agent.run_campaign(
                    lead_id=request.input.get("lead_id"),
                    goal=request.input.get("goal", "engagement"),
                    max_cycles=request.input.get("max_cycles", 5)
                )
                output_data = {
                    "lead_id": result.lead_id,
                    "goal": result.goal,
                    "goal_met": result.goal_met,
                    "cycle_count": result.cycle_count,
                    "response_rate": result.response_rate,
                    "engagement_score": result.engagement_score,
                    "learnings": result.learnings,
                    "executed_touches": result.executed_touches,
                    "final_strategy": result.final_strategy,
                    "latency_ms": result.latency_ms,
                    "total_cost_usd": result.total_cost_usd
                }
                
            elif request.agent_type == "marketing":
                agent = MarketingAgent()
                # MarketingAgent expects: campaign_brief, target_audience, campaign_goals
                result = await agent.generate_campaign(
                    campaign_brief=request.input.get("campaign_brief"),
                    target_audience=request.input.get("target_audience"),
                    campaign_goals=request.input.get("campaign_goals", ["awareness"])
                )
                output_data = {
                    "email_content": result.email_content,
                    "linkedin_content": result.linkedin_content,
                    "social_content": result.social_content,
                    "blog_content": result.blog_content,
                    "campaign_brief": result.campaign_brief,
                    "target_audience": result.target_audience,
                    "campaign_goals": result.campaign_goals,
                    "total_cost_usd": result.total_cost_usd,
                    "content_quality_score": result.content_quality_score,
                    "recommended_schedule": result.recommended_schedule,
                    "estimated_reach": result.estimated_reach,
                    "latency_ms": result.latency_ms
                }
                
            elif request.agent_type == "bdr":
                agent = BDRAgent()
                # BDRAgent expects: lead_id, company_name, contact_name, contact_title, config
                config = create_streaming_config(thread_id=thread_id)
                result = await agent.start_outreach(
                    lead_id=request.input.get("lead_id"),
                    company_name=request.input.get("company_name"),
                    contact_name=request.input.get("contact_name"),
                    contact_title=request.input.get("contact_title"),
                    config=config
                )
                # BDRAgent returns interrupt data - extract draft for response
                interrupt_data = result.get("__interrupt__", [{}])[0].get("value", {}) if "__interrupt__" in result else {}
                output_data = {
                    "status": "draft_ready",
                    "draft_subject": interrupt_data.get("draft_subject"),
                    "draft_body": interrupt_data.get("draft_body"),
                    "research_summary": interrupt_data.get("research_summary"),
                    "company_name": interrupt_data.get("company_name"),
                    "contact_name": interrupt_data.get("contact_name"),
                    "revision_count": interrupt_data.get("revision_count", 0),
                    "requires_approval": True
                }
                
            elif request.agent_type == "conversation":
                agent = ConversationAgent()
                # ConversationAgent expects: text, voice_config, context, config
                config = create_streaming_config(thread_id=thread_id)
                result = await agent.send_message(
                    text=request.input.get("text") or request.input.get("user_input"),
                    context=request.input.get("context"),
                    config=config if thread_id else None
                )
                output_data = {
                    "user_input": result.user_input,
                    "assistant_response": result.assistant_response,
                    "audio_output": result.audio_output,  # Base64 encoded if needed
                    "turn_number": result.turn_number,
                    "audio_metadata": result.audio_metadata,
                    "latency_breakdown": result.latency_breakdown,
                    "total_cost_usd": result.total_cost_usd,
                    "estimated_audio_duration_ms": result.estimated_audio_duration_ms
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
        await get_redis_checkpointer()

        # Create streaming configuration
        create_streaming_config(
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
                        agent = QualificationAgent(db=db)  # Enable cost tracking
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
                            "data_sources": result.data_sources,
                            "confidence_score": result.confidence_score,
                            "tools_called": result.tools_called,
                            "latency_ms": result.latency_ms,
                            "iterations_used": result.iterations_used,
                            "total_cost_usd": result.total_cost_usd,
                            "errors": result.errors
                        }
                        
                    elif request.agent_type == "growth":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Analyzing growth opportunities...'})}\n\n"
                        agent = GrowthAgent()
                        result = await agent.run_campaign(
                            lead_id=request.input.get("lead_id"),
                            goal=request.input.get("goal", "engagement"),
                            max_cycles=request.input.get("max_cycles", 5)
                        )
                        output_data = {
                            "lead_id": result.lead_id,
                            "goal": result.goal,
                            "goal_met": result.goal_met,
                            "cycle_count": result.cycle_count,
                            "response_rate": result.response_rate,
                            "engagement_score": result.engagement_score,
                            "learnings": result.learnings,
                            "executed_touches": result.executed_touches,
                            "final_strategy": result.final_strategy,
                            "latency_ms": result.latency_ms,
                            "total_cost_usd": result.total_cost_usd
                        }
                        
                    elif request.agent_type == "marketing":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Generating marketing campaigns...'})}\n\n"
                        agent = MarketingAgent()
                        result = await agent.generate_campaign(
                            campaign_brief=request.input.get("campaign_brief"),
                            target_audience=request.input.get("target_audience"),
                            campaign_goals=request.input.get("campaign_goals", ["awareness"])
                        )
                        output_data = {
                            "email_content": result.email_content,
                            "linkedin_content": result.linkedin_content,
                            "social_content": result.social_content,
                            "blog_content": result.blog_content,
                            "campaign_brief": result.campaign_brief,
                            "target_audience": result.target_audience,
                            "campaign_goals": result.campaign_goals,
                            "total_cost_usd": result.total_cost_usd,
                            "content_quality_score": result.content_quality_score,
                            "recommended_schedule": result.recommended_schedule,
                            "estimated_reach": result.estimated_reach,
                            "latency_ms": result.latency_ms
                        }
                        
                    elif request.agent_type == "bdr":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Processing BDR workflow...'})}\n\n"
                        agent = BDRAgent()
                        config = create_streaming_config(thread_id=thread_id)
                        result = await agent.start_outreach(
                            lead_id=request.input.get("lead_id"),
                            company_name=request.input.get("company_name"),
                            contact_name=request.input.get("contact_name"),
                            contact_title=request.input.get("contact_title"),
                            config=config
                        )
                        interrupt_data = result.get("__interrupt__", [{}])[0].get("value", {}) if "__interrupt__" in result else {}
                        output_data = {
                            "status": "draft_ready",
                            "draft_subject": interrupt_data.get("draft_subject"),
                            "draft_body": interrupt_data.get("draft_body"),
                            "research_summary": interrupt_data.get("research_summary"),
                            "company_name": interrupt_data.get("company_name"),
                            "contact_name": interrupt_data.get("contact_name"),
                            "revision_count": interrupt_data.get("revision_count", 0),
                            "requires_approval": True
                        }
                        
                    elif request.agent_type == "conversation":
                        yield f"data: {json.dumps({'type': 'message', 'content': 'Processing conversation...'})}\n\n"
                        agent = ConversationAgent()
                        config = create_streaming_config(thread_id=thread_id)
                        result = await agent.send_message(
                            text=request.input.get("text") or request.input.get("user_input"),
                            context=request.input.get("context"),
                            config=config if thread_id else None
                        )
                        output_data = {
                            "user_input": result.user_input,
                            "assistant_response": result.assistant_response,
                            "audio_output": result.audio_output,
                            "turn_number": result.turn_number,
                            "audio_metadata": result.audio_metadata,
                            "latency_breakdown": result.latency_breakdown,
                            "total_cost_usd": result.total_cost_usd,
                            "estimated_audio_duration_ms": result.estimated_audio_duration_ms
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


# ========== Lead Scout Endpoints ==========

class ScoutRunRequest(BaseModel):
    """Request schema for triggering a scout run."""
    limit: int = Field(
        default=10,
        description="Number of leads to scout (1-50)"
    )
    require_domain: bool = Field(
        default=True,
        description="Only scout leads with website domains"
    )
    icp_tier: Optional[str] = Field(
        default=None,
        description="Filter by ICP tier: PLATINUM, GOLD, SILVER, BRONZE"
    )
    async_mode: bool = Field(
        default=False,
        description="Run via Celery task (returns task_id) or inline (returns results)"
    )


class ScoutResultItem(BaseModel):
    """Single scout result item."""
    company_id: str
    company_name: str
    domain: Optional[str]
    icp_score: float
    priority: str
    why_call: str
    scouted_at: str


class ScoutRunResponse(BaseModel):
    """Response for scout run."""
    status: str
    task_id: Optional[str] = None
    total_scouted: Optional[int] = None
    hot_leads: Optional[int] = None
    warm_leads: Optional[int] = None
    cold_leads: Optional[int] = None
    duration_ms: Optional[int] = None
    results: Optional[list] = None
    errors: Optional[list] = None


@router.post("/scout/run", response_model=ScoutRunResponse, status_code=200)
async def run_lead_scout(request: ScoutRunRequest):
    """
    Trigger a Lead Scout run to discover and prioritize leads.

    The Lead Scout agent:
    1. Queries Supabase for unenriched companies with domains
    2. Scrapes websites for signals (brands, certifications, contacts)
    3. Scores each lead with QualificationAgent
    4. Generates "WHY call" recommendations for Tim's calling list
    5. Saves results back to Supabase

    Args:
        request: Scout configuration (limit, require_domain, icp_tier, async_mode)

    Returns:
        ScoutRunResponse with results or task_id (if async)

    Example:
        ```bash
        # Inline (wait for results)
        curl -X POST http://localhost:8001/api/v1/langgraph/scout/run \\
          -H "Content-Type: application/json" \\
          -d '{"limit": 5, "require_domain": true}'

        # Async (returns immediately)
        curl -X POST http://localhost:8001/api/v1/langgraph/scout/run \\
          -H "Content-Type: application/json" \\
          -d '{"limit": 10, "async_mode": true}'
        ```
    """
    try:
        if request.async_mode:
            # Run via Celery task
            from app.tasks.agent_tasks import run_lead_scout_task

            task = run_lead_scout_task.delay(
                limit=request.limit,
                require_domain=request.require_domain,
                icp_tier=request.icp_tier
            )

            logger.info(f"Lead Scout task queued: {task.id}")

            return ScoutRunResponse(
                status="queued",
                task_id=task.id
            )
        else:
            # Run inline (synchronous)
            from app.services.langgraph.agents.lead_scout_agent import LeadScoutAgent

            scout = LeadScoutAgent(provider='cerebras')
            result = await scout.scout(
                limit=request.limit,
                require_domain=request.require_domain,
                icp_tier=request.icp_tier
            )

            logger.info(
                f"Lead Scout completed: {result.total_scouted} scouted, "
                f"{result.hot_leads} HOT in {result.duration_ms}ms"
            )

            return ScoutRunResponse(
                status="success",
                total_scouted=result.total_scouted,
                hot_leads=result.hot_leads,
                warm_leads=result.warm_leads,
                cold_leads=result.cold_leads,
                duration_ms=result.duration_ms,
                results=[
                    {
                        "company_id": r.company_id,
                        "company_name": r.company_name,
                        "domain": r.domain,
                        "icp_score": r.icp_score,
                        "priority": r.priority,
                        "why_call": r.why_call[:200],
                        "scouted_at": r.scouted_at
                    }
                    for r in result.results
                ],
                errors=result.errors
            )

    except Exception as e:
        logger.error(f"Error running Lead Scout: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Lead Scout failed: {str(e)}"
        )


@router.get("/scout/results", status_code=200)
async def get_scout_results(
    limit: int = 20,
    priority: Optional[str] = None
):
    """
    Get recent scout results (leads with AI recommendations).

    Returns leads from Supabase that have been scouted and have recommendations.

    Args:
        limit: Maximum number of results (1-100)
        priority: Filter by priority (HOT, WARM, COLD)

    Returns:
        List of scouted leads with recommendations

    Example:
        ```bash
        # Get all recent scouts
        curl http://localhost:8001/api/v1/langgraph/scout/results?limit=10

        # Get only HOT leads
        curl http://localhost:8001/api/v1/langgraph/scout/results?priority=HOT
        ```
    """
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase

        supabase = get_supabase()
        limit = max(1, min(limit, 100))

        # Query leads with AI company story (indicates scouted)
        query = supabase.table('dim_companies').select(
            'company_id, company_name, domain, '
            'icp_tier, icp_score, current_stage, '
            'ai_company_story, ai_personal_hooks, ai_pain_points, '
            'phone, state, city, ai_enriched_at'
        ).not_.is_('ai_company_story', 'null')

        if priority:
            query = query.eq('current_stage', priority.upper())

        query = query.order('ai_enriched_at', desc=True).limit(limit)

        result = query.execute()

        return {
            "status": "success",
            "count": len(result.data),
            "results": result.data
        }

    except Exception as e:
        logger.error(f"Error getting scout results: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scout results: {str(e)}"
        )


@router.get("/scout/status", status_code=200)
async def get_scout_status():
    """
    Get Lead Scout status and statistics.

    Returns counts of scouted leads by priority tier.

    Example:
        ```bash
        curl http://localhost:8001/api/v1/langgraph/scout/status
        ```
    """
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase

        supabase = get_supabase()

        # Get counts by priority
        total = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).not_.is_('ai_company_story', 'null').execute()

        hot = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).eq('current_stage', 'HOT').not_.is_('ai_company_story', 'null').execute()

        warm = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).eq('current_stage', 'WARM').not_.is_('ai_company_story', 'null').execute()

        cold = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).eq('current_stage', 'COLD').not_.is_('ai_company_story', 'null').execute()

        # Get unenriched count (remaining to scout)
        unenriched = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).not_.is_('domain', 'null').is_('ai_company_story', 'null').execute()

        return {
            "status": "success",
            "scouted": {
                "total": total.count or 0,
                "hot": hot.count or 0,
                "warm": warm.count or 0,
                "cold": cold.count or 0
            },
            "remaining": unenriched.count or 0,
            "next_scheduled": "Every 30 minutes (Celery Beat)"
        }

    except Exception as e:
        logger.error(f"Error getting scout status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get scout status: {str(e)}"
        )


# ========== Morning Report Endpoints ==========

class ReportRunRequest(BaseModel):
    """Request schema for generating a morning report."""
    hours_back: int = Field(
        default=24,
        description="Hours to look back for scouted leads (default: 24)"
    )
    top_n: int = Field(
        default=10,
        description="Number of top leads to include with outreach drafts (1-25)"
    )
    save_to_file: bool = Field(
        default=True,
        description="Save report to data/reports/ as markdown"
    )
    async_mode: bool = Field(
        default=False,
        description="Run via Celery task (returns task_id) or inline (returns results)"
    )


class ReportRunResponse(BaseModel):
    """Response for morning report generation."""
    status: str
    task_id: Optional[str] = None
    generated_at: Optional[str] = None
    report_date: Optional[str] = None
    total_scouted: Optional[int] = None
    hot_leads: Optional[int] = None
    warm_leads: Optional[int] = None
    cold_leads: Optional[int] = None
    top_leads_count: Optional[int] = None
    signals_summary: Optional[dict] = None
    summary: Optional[str] = None
    file_path: Optional[str] = None


@router.post("/report/generate", response_model=ReportRunResponse, status_code=200)
async def generate_morning_report(request: ReportRunRequest):
    """
    Generate a morning report with overnight scout results and outreach drafts.

    The Morning Report agent:
    1. Queries leads scouted in the last N hours
    2. Summarizes HOT/WARM/COLD counts and signal patterns
    3. For top leads, generates personalized outreach drafts:
       - Email draft (150-200 words)
       - SMS draft (under 160 characters)
       - Call opener (2-3 sentences)
    4. Optionally saves to markdown file

    Scheduled to run daily at 9 AM EST (14:00 UTC) via Celery Beat.

    Args:
        request: Report configuration (hours_back, top_n, save_to_file, async_mode)

    Returns:
        ReportRunResponse with summary or task_id (if async)

    Example:
        ```bash
        # Generate report inline
        curl -X POST http://localhost:8001/api/v1/langgraph/report/generate \\
          -H "Content-Type: application/json" \\
          -d '{"hours_back": 24, "top_n": 10}'

        # Generate via Celery
        curl -X POST http://localhost:8001/api/v1/langgraph/report/generate \\
          -H "Content-Type: application/json" \\
          -d '{"async_mode": true}'
        ```
    """
    try:
        if request.async_mode:
            # Run via Celery task
            from app.tasks.agent_tasks import generate_morning_report_task

            task = generate_morning_report_task.delay(
                hours_back=request.hours_back,
                top_n=request.top_n,
                save_to_file=request.save_to_file
            )

            logger.info(f"Morning Report task queued: {task.id}")

            return ReportRunResponse(
                status="queued",
                task_id=task.id
            )
        else:
            # Run inline (synchronous)
            from app.services.langgraph.agents.morning_report_agent import MorningReportAgent

            agent = MorningReportAgent(provider='cerebras')
            report = await agent.generate_report(
                hours_back=request.hours_back,
                top_n=request.top_n
            )

            file_path = None
            if request.save_to_file:
                file_path = await agent.save_report_to_file(report)

            logger.info(
                f"Morning Report generated: {report.total_scouted} leads, "
                f"{report.hot_leads} HOT, {len(report.top_leads)} with outreach drafts"
            )

            return ReportRunResponse(
                status="success",
                generated_at=report.generated_at,
                report_date=report.report_date,
                total_scouted=report.total_scouted,
                hot_leads=report.hot_leads,
                warm_leads=report.warm_leads,
                cold_leads=report.cold_leads,
                top_leads_count=len(report.top_leads),
                signals_summary=report.signals_summary,
                summary=report.summary,
                file_path=file_path
            )

    except Exception as e:
        logger.error(f"Error generating Morning Report: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Morning Report failed: {str(e)}"
        )


@router.get("/report/latest", status_code=200)
async def get_latest_report():
    """
    Get the most recent morning report file.

    Returns the content of the latest morning_report_*.md file from data/reports/.

    Example:
        ```bash
        curl http://localhost:8001/api/v1/langgraph/report/latest
        ```
    """
    try:
        from pathlib import Path

        reports_dir = Path("data/reports")
        if not reports_dir.exists():
            return {
                "status": "no_reports",
                "message": "No reports directory found. Run /report/generate first."
            }

        # Find most recent report
        reports = sorted(reports_dir.glob("morning_report_*.md"), reverse=True)

        if not reports:
            return {
                "status": "no_reports",
                "message": "No morning reports found. Run /report/generate first."
            }

        latest = reports[0]
        content = latest.read_text()

        return {
            "status": "success",
            "file_name": latest.name,
            "file_path": str(latest),
            "content": content
        }

    except Exception as e:
        logger.error(f"Error getting latest report: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get latest report: {str(e)}"
        )


# ========== Sales Intel Endpoints ==========

class SalesIntelRunRequest(BaseModel):
    """Request schema for running SalesIntel analysis."""
    limit: int = Field(
        default=10,
        description="Number of leads to analyze (1-50)"
    )
    async_mode: bool = Field(
        default=False,
        description="Run via Celery task (returns task_id) or inline (returns results)"
    )


class SalesIntelRunResponse(BaseModel):
    """Response for SalesIntel run."""
    status: str
    task_id: Optional[str] = None
    leads_processed: Optional[int] = None
    hooks_extracted: Optional[int] = None
    duration_ms: Optional[int] = None
    results: Optional[list] = None
    errors: Optional[list] = None


@router.post("/intel/run", response_model=SalesIntelRunResponse, status_code=200)
async def run_sales_intel(request: SalesIntelRunRequest):
    """
    Run SalesIntelAgent to extract personal hooks from scouted leads.

    The Sales Intel agent:
    1. Queries leads that have been scouted (have ai_company_story) but lack personal hooks
    2. Analyzes scraped website content for personal details (hobbies, family, pets, background)
    3. Generates personalized openers based on extracted hooks
    4. Saves hooks and drafts back to Supabase (ai_personal_hooks, ai_pain_points)

    Scheduled to run every hour at :30 via Celery Beat.

    Args:
        request: Config (limit, async_mode)

    Returns:
        SalesIntelRunResponse with results or task_id (if async)

    Example:
        ```bash
        # Run inline
        curl -X POST http://localhost:8001/api/v1/langgraph/intel/run \\
          -H "Content-Type: application/json" \\
          -d '{"limit": 5}'

        # Run via Celery
        curl -X POST http://localhost:8001/api/v1/langgraph/intel/run \\
          -H "Content-Type: application/json" \\
          -d '{"limit": 10, "async_mode": true}'
        ```
    """
    try:
        if request.async_mode:
            # Run via Celery task
            from app.tasks.agent_tasks import run_sales_intel_batch_task

            task = run_sales_intel_batch_task.delay(limit=request.limit)

            logger.info(f"SalesIntel task queued: {task.id}")

            return SalesIntelRunResponse(
                status="queued",
                task_id=task.id
            )
        else:
            # Run inline (synchronous)
            from app.services.langgraph.agents.sales_intel_agent import SalesIntelAgent
            from app.services.langgraph.tools.supabase_tools import (
                query_leads_for_sales_intel,
                save_sales_intel
            )
            import time as time_module

            start_time = time_module.time()

            # Get leads needing intel analysis
            leads = query_leads_for_sales_intel(limit=request.limit)

            if not leads:
                return SalesIntelRunResponse(
                    status="success",
                    leads_processed=0,
                    hooks_extracted=0,
                    duration_ms=0,
                    results=[],
                    errors=[]
                )

            agent = SalesIntelAgent(provider='cerebras')
            results = []
            errors = []
            total_hooks = 0

            for lead in leads:
                try:
                    # Run SalesIntelAgent on each lead
                    intel_result = await agent.analyze(
                        company_name=lead.get('company_name', ''),
                        contact_name=lead.get('contact_name'),
                        contact_title=lead.get('contact_title'),
                        scraped_content=lead.get('ai_company_story', ''),
                        services=lead.get('service_areas'),
                        brands=lead.get('oem_brands'),
                        location=f"{lead.get('city', '')}, {lead.get('state', '')}"
                    )

                    # Save to Supabase
                    save_sales_intel(
                        company_id=lead['company_id'],
                        personal_hooks=intel_result.personal_hooks,
                        company_story=intel_result.company_story,
                        pain_points=intel_result.pain_points,
                        email_draft=intel_result.email_body,
                        sms_draft=intel_result.sms_draft,
                        voice_opener=intel_result.voice_opener
                    )

                    hook_count = len(intel_result.personal_hooks) if intel_result.personal_hooks else 0
                    total_hooks += hook_count

                    results.append({
                        "company_id": lead['company_id'],
                        "company_name": lead.get('company_name'),
                        "hooks_found": hook_count,
                        "has_email_draft": bool(intel_result.email_body),
                        "has_sms_draft": bool(intel_result.sms_draft)
                    })

                except Exception as e:
                    errors.append({
                        "company_id": lead.get('company_id'),
                        "error": str(e)
                    })
                    logger.error(f"SalesIntel failed for {lead.get('company_id')}: {e}")

            duration_ms = int((time_module.time() - start_time) * 1000)

            logger.info(
                f"SalesIntel completed: {len(results)} leads, "
                f"{total_hooks} hooks in {duration_ms}ms"
            )

            return SalesIntelRunResponse(
                status="success",
                leads_processed=len(results),
                hooks_extracted=total_hooks,
                duration_ms=duration_ms,
                results=results,
                errors=errors if errors else None
            )

    except Exception as e:
        logger.error(f"Error running SalesIntel: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"SalesIntel failed: {str(e)}"
        )


@router.get("/intel/results", status_code=200)
async def get_sales_intel_results(
    limit: int = 20,
    has_hooks: bool = True
):
    """
    Get leads with extracted personal hooks.

    Args:
        limit: Maximum results (1-100)
        has_hooks: Only return leads with personal hooks extracted

    Returns:
        List of leads with personal hooks and drafts

    Example:
        ```bash
        curl http://localhost:8001/api/v1/langgraph/intel/results?limit=10
        ```
    """
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase

        supabase = get_supabase()
        limit = max(1, min(limit, 100))

        query = supabase.table('dim_companies').select(
            'company_id, company_name, domain, '
            'icp_tier, icp_score, current_stage, '
            'ai_personal_hooks, ai_pain_points, ai_company_story, '
            'phone, state, city, ai_enriched_at'
        )

        if has_hooks:
            query = query.not_.is_('ai_personal_hooks', 'null')

        query = query.order('ai_enriched_at', desc=True).limit(limit)

        result = query.execute()

        return {
            "status": "success",
            "count": len(result.data),
            "results": result.data
        }

    except Exception as e:
        logger.error(f"Error getting intel results: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get intel results: {str(e)}"
        )


# ========== Growth Campaign Endpoints ==========

class GrowthCampaignRequest(BaseModel):
    """Request schema for running growth campaigns."""
    goal: str = Field(
        default="book_meeting",
        description="Campaign goal: book_meeting, get_reply, engagement"
    )
    max_leads: int = Field(
        default=5,
        description="Maximum leads to run campaigns for (1-20)"
    )
    max_cycles: int = Field(
        default=5,
        description="Maximum optimization cycles per lead (1-10)"
    )
    async_mode: bool = Field(
        default=False,
        description="Run via Celery task (returns task_id) or inline (returns results)"
    )


class GrowthCampaignResponse(BaseModel):
    """Response for growth campaign run."""
    status: str
    task_id: Optional[str] = None
    campaigns_run: Optional[int] = None
    goals_met: Optional[int] = None
    total_cycles: Optional[int] = None
    duration_ms: Optional[int] = None
    results: Optional[list] = None
    errors: Optional[list] = None


@router.post("/growth/run", response_model=GrowthCampaignResponse, status_code=200)
async def run_growth_campaigns(request: GrowthCampaignRequest):
    """
    Run GrowthAgent multi-touch campaigns for HOT leads.

    The Growth Agent:
    1. Queries HOT leads with ICP score >= 75
    2. For each lead, runs a 5-cycle optimization loop:
       - Analyze current state
       - Strategize next touch
       - Execute outreach
       - Measure results
       - Learn and adapt
    3. Goals: book_meeting, get_reply, or engagement
    4. Operates autonomously (no human approval needed)

    Scheduled to run daily at 10 AM EST (15:00 UTC) via Celery Beat.

    Args:
        request: Campaign config (goal, max_leads, max_cycles, async_mode)

    Returns:
        GrowthCampaignResponse with results or task_id (if async)

    Example:
        ```bash
        # Run inline
        curl -X POST http://localhost:8001/api/v1/langgraph/growth/run \\
          -H "Content-Type: application/json" \\
          -d '{"goal": "book_meeting", "max_leads": 3}'

        # Run via Celery
        curl -X POST http://localhost:8001/api/v1/langgraph/growth/run \\
          -H "Content-Type: application/json" \\
          -d '{"goal": "engagement", "max_leads": 5, "async_mode": true}'
        ```
    """
    try:
        if request.async_mode:
            # Run via Celery task
            from app.tasks.agent_tasks import run_growth_campaigns_task

            task = run_growth_campaigns_task.delay(
                goal=request.goal,
                max_leads=request.max_leads
            )

            logger.info(f"Growth campaign task queued: {task.id}")

            return GrowthCampaignResponse(
                status="queued",
                task_id=task.id
            )
        else:
            # Run inline (synchronous)
            from app.services.langgraph.agents.growth_agent import GrowthAgent
            from app.services.langgraph.tools.supabase_tools import query_hot_leads
            import time as time_module

            start_time = time_module.time()

            # Get HOT leads
            leads = query_hot_leads(limit=request.max_leads)

            if not leads:
                return GrowthCampaignResponse(
                    status="success",
                    campaigns_run=0,
                    goals_met=0,
                    total_cycles=0,
                    duration_ms=0,
                    results=[],
                    errors=[]
                )

            agent = GrowthAgent(provider='cerebras')
            results = []
            errors = []
            goals_met = 0
            total_cycles = 0

            for lead in leads:
                try:
                    # Run campaign for each lead
                    campaign_result = await agent.run_campaign(
                        lead_id=lead['company_id'],
                        goal=request.goal,
                        max_cycles=request.max_cycles
                    )

                    if campaign_result.goal_met:
                        goals_met += 1

                    total_cycles += campaign_result.cycle_count

                    results.append({
                        "company_id": lead['company_id'],
                        "company_name": lead.get('company_name'),
                        "goal": campaign_result.goal,
                        "goal_met": campaign_result.goal_met,
                        "cycles": campaign_result.cycle_count,
                        "response_rate": campaign_result.response_rate,
                        "engagement_score": campaign_result.engagement_score,
                        "learnings": campaign_result.learnings[:3] if campaign_result.learnings else []
                    })

                except Exception as e:
                    errors.append({
                        "company_id": lead.get('company_id'),
                        "error": str(e)
                    })
                    logger.error(f"Growth campaign failed for {lead.get('company_id')}: {e}")

            duration_ms = int((time_module.time() - start_time) * 1000)

            logger.info(
                f"Growth campaigns completed: {len(results)} campaigns, "
                f"{goals_met} goals met in {duration_ms}ms"
            )

            return GrowthCampaignResponse(
                status="success",
                campaigns_run=len(results),
                goals_met=goals_met,
                total_cycles=total_cycles,
                duration_ms=duration_ms,
                results=results,
                errors=errors if errors else None
            )

    except Exception as e:
        logger.error(f"Error running Growth campaigns: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Growth campaigns failed: {str(e)}"
        )


@router.get("/growth/status", status_code=200)
async def get_growth_status():
    """
    Get Growth campaign status and statistics.

    Returns counts of HOT leads available and campaign history.

    Example:
        ```bash
        curl http://localhost:8001/api/v1/langgraph/growth/status
        ```
    """
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase

        supabase = get_supabase()

        # Get HOT lead counts
        hot_total = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).eq('current_stage', 'HOT').execute()

        hot_high_icp = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).eq('current_stage', 'HOT').gte('icp_score', 75).execute()

        # Get leads with AI drafts (indicates campaign run)
        with_drafts = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).eq('current_stage', 'HOT').not_.is_('ai_personal_hooks', 'null').execute()

        return {
            "status": "success",
            "hot_leads": {
                "total": hot_total.count or 0,
                "high_icp": hot_high_icp.count or 0,
                "with_campaigns": with_drafts.count or 0
            },
            "next_scheduled": "Daily at 10 AM EST (15:00 UTC)"
        }

    except Exception as e:
        logger.error(f"Error getting growth status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get growth status: {str(e)}"
        )


# ========== BDR Outreach Endpoints ==========

class BDRRunRequest(BaseModel):
    """Request schema for running BDR outreach."""
    company_id: Optional[str] = Field(
        default=None,
        description="UUID of a specific company to target"
    )
    limit: int = Field(
        default=3,
        description="Number of leads to process in batch (1-10)"
    )
    async_mode: bool = Field(
        default=True,
        description="Run via Celery task (recommended for Slack notifications)"
    )


class BDRRunResponse(BaseModel):
    """Response for BDR outreach."""
    status: str
    task_id: Optional[str] = None
    draft_id: Optional[str] = None
    company_name: Optional[str] = None
    leads_queued: Optional[int] = None
    message: Optional[str] = None


class BDRApprovalRequest(BaseModel):
    """Request schema for approving/rejecting a BDR draft."""
    draft_id: str = Field(
        ...,
        description="UUID of the draft in dim_ai_drafts"
    )
    action: str = Field(
        ...,
        description="Action: approve, reject, revise"
    )
    feedback: Optional[str] = Field(
        default=None,
        description="Feedback for revision (required if action=revise)"
    )
    approved_by: Optional[str] = Field(
        default="API",
        description="Name of the person taking the action"
    )


@router.post("/bdr/run", response_model=BDRRunResponse, status_code=200)
async def run_bdr_outreach(request: BDRRunRequest):
    """
    Run BDR outreach for a specific company or batch of HOT leads.

    The BDR Agent:
    1. Researches the prospect using existing AI intel
    2. Drafts a personalized email with subject line
    3. Saves draft to dim_ai_drafts with status="pending_approval"
    4. Sends Slack notification with Approve/Reject buttons
    5. PAUSES until human approves via Slack or API

    When approved, the email is marked as "sent" (integrate with SendGrid for actual sending).

    Scheduled to run every hour via Celery Beat (3 leads per batch).

    Args:
        request: BDR config (company_id for single, or limit for batch)

    Returns:
        BDRRunResponse with task_id or draft_id

    Example:
        ```bash
        # Single company
        curl -X POST http://localhost:8001/api/v1/langgraph/bdr/run \\
          -H "Content-Type: application/json" \\
          -d '{"company_id": "abc-123-uuid"}'

        # Batch (3 leads)
        curl -X POST http://localhost:8001/api/v1/langgraph/bdr/run \\
          -H "Content-Type: application/json" \\
          -d '{"limit": 3}'
        ```
    """
    try:
        if request.company_id:
            # Single company outreach
            from app.tasks.agent_tasks import run_bdr_outreach_task

            if request.async_mode:
                task = run_bdr_outreach_task.delay(request.company_id)
                logger.info(f"BDR outreach task queued: {task.id}")
                return BDRRunResponse(
                    status="queued",
                    task_id=task.id,
                    message=f"BDR outreach queued for company_id={request.company_id}"
                )
            else:
                # For sync mode, we'd run inline but BDR requires Slack so async is recommended
                return BDRRunResponse(
                    status="error",
                    message="BDR requires async_mode=true for Slack notification workflow"
                )
        else:
            # Batch outreach
            from app.tasks.agent_tasks import run_bdr_batch_task

            task = run_bdr_batch_task.delay(limit=request.limit)
            logger.info(f"BDR batch task queued: {task.id}")

            return BDRRunResponse(
                status="queued",
                task_id=task.id,
                leads_queued=request.limit,
                message=f"BDR batch queued for up to {request.limit} leads"
            )

    except Exception as e:
        logger.error(f"Error running BDR outreach: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"BDR outreach failed: {str(e)}"
        )


@router.post("/bdr/approve", status_code=200)
async def approve_bdr_draft(request: BDRApprovalRequest):
    """
    Approve, reject, or request revision for a BDR draft.

    This endpoint provides API access to the same actions available
    via Slack buttons. Use this for programmatic approvals or
    when Slack is not configured.

    Args:
        request: Approval request with draft_id and action

    Returns:
        Status of the draft after action

    Example:
        ```bash
        # Approve
        curl -X POST http://localhost:8001/api/v1/langgraph/bdr/approve \\
          -H "Content-Type: application/json" \\
          -d '{"draft_id": "abc-123", "action": "approve", "approved_by": "Tim"}'

        # Reject
        curl -X POST http://localhost:8001/api/v1/langgraph/bdr/approve \\
          -H "Content-Type: application/json" \\
          -d '{"draft_id": "abc-123", "action": "reject"}'

        # Request revision
        curl -X POST http://localhost:8001/api/v1/langgraph/bdr/approve \\
          -H "Content-Type: application/json" \\
          -d '{"draft_id": "abc-123", "action": "revise", "feedback": "Make it shorter"}'
        ```
    """
    try:
        from app.tasks.agent_tasks import resume_bdr_outreach_task

        if request.action not in ["approve", "reject", "revise"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid action. Must be: approve, reject, or revise"
            )

        if request.action == "revise" and not request.feedback:
            raise HTTPException(
                status_code=400,
                detail="Feedback is required for revision action"
            )

        # Trigger the resume task
        task = resume_bdr_outreach_task.delay(
            draft_id=request.draft_id,
            action=request.action,
            feedback=request.feedback,
            approved_by=request.approved_by
        )

        logger.info(f"BDR resume task queued: {task.id} for {request.action}")

        return {
            "status": "processing",
            "task_id": task.id,
            "draft_id": request.draft_id,
            "action": request.action,
            "message": f"Draft {request.action} processing"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving BDR draft: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Approval failed: {str(e)}"
        )


@router.get("/bdr/drafts", status_code=200)
async def get_bdr_drafts(
    status: Optional[str] = None,
    limit: int = 20
):
    """
    Get BDR drafts from dim_ai_drafts.

    Args:
        status: Filter by status (pending_approval, sent, rejected)
        limit: Maximum results (1-100)

    Returns:
        List of drafts with their status

    Example:
        ```bash
        # Get pending drafts
        curl http://localhost:8001/api/v1/langgraph/bdr/drafts?status=pending_approval

        # Get all recent drafts
        curl http://localhost:8001/api/v1/langgraph/bdr/drafts?limit=50
        ```
    """
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase

        supabase = get_supabase()
        limit = max(1, min(limit, 100))

        query = supabase.table('dim_ai_drafts').select(
            'draft_id, company_id, contact_email, draft_type, '
            'subject, body, status, approved_by, created_at, sent_at'
        )

        if status:
            query = query.eq('status', status)

        query = query.order('created_at', desc=True).limit(limit)

        result = query.execute()

        # Enrich with company names
        drafts = result.data or []
        if drafts:
            company_ids = list(set(d['company_id'] for d in drafts if d.get('company_id')))
            if company_ids:
                companies = supabase.table('dim_companies').select(
                    'company_id, company_name'
                ).in_('company_id', company_ids).execute()
                company_map = {c['company_id']: c['company_name'] for c in (companies.data or [])}

                for draft in drafts:
                    draft['company_name'] = company_map.get(draft.get('company_id'), 'Unknown')

        return {
            "status": "success",
            "count": len(drafts),
            "drafts": drafts
        }

    except Exception as e:
        logger.error(f"Error getting BDR drafts: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get drafts: {str(e)}"
        )


@router.get("/bdr/status", status_code=200)
async def get_bdr_status():
    """
    Get BDR status and statistics.

    Returns counts of drafts by status and leads available.

    Example:
        ```bash
        curl http://localhost:8001/api/v1/langgraph/bdr/status
        ```
    """
    try:
        from app.services.langgraph.tools.supabase_tools import get_supabase

        supabase = get_supabase()

        # Get draft counts by status
        pending = supabase.table('dim_ai_drafts').select(
            'draft_id', count='exact'
        ).eq('status', 'pending_approval').execute()

        sent = supabase.table('dim_ai_drafts').select(
            'draft_id', count='exact'
        ).eq('status', 'sent').execute()

        rejected = supabase.table('dim_ai_drafts').select(
            'draft_id', count='exact'
        ).eq('status', 'rejected').execute()

        # Get HOT leads available for BDR
        available = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).eq('current_stage', 'HOT').gte('icp_score', 70).not_.is_(
            'ai_company_story', 'null'
        ).execute()

        return {
            "status": "success",
            "drafts": {
                "pending_approval": pending.count or 0,
                "sent": sent.count or 0,
                "rejected": rejected.count or 0
            },
            "leads_available": available.count or 0,
            "next_scheduled": "Every hour at :00 (3 leads per batch)"
        }

    except Exception as e:
        logger.error(f"Error getting BDR status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get BDR status: {str(e)}"
        )


# ========== Exports ==========

__all__ = [
    "router",
    "InvokeAgentRequest",
    "AgentResponse",
    "StateResponse",
    "ScoutRunRequest",
    "ScoutRunResponse",
    "ReportRunRequest",
    "ReportRunResponse",
    "SalesIntelRunRequest",
    "SalesIntelRunResponse",
    "GrowthCampaignRequest",
    "GrowthCampaignResponse",
    "BDRRunRequest",
    "BDRRunResponse",
    "BDRApprovalRequest",
]
