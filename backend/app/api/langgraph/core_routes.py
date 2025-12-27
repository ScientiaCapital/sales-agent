"""Core LangGraph API routes - Agent invocation, streaming, and state endpoints."""

import json
import time
import uuid
from datetime import datetime
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.langgraph.schemas import InvokeAgentRequest, AgentResponse, StateResponse
from app.api.langgraph.helpers import get_or_create_thread_id, VALID_AGENTS
from app.models.database import get_db
from app.models.langgraph_models import LangGraphExecution
from app.services.langgraph import (
    get_redis_checkpointer,
    create_streaming_config,
    get_checkpoint_config,
)
from app.core.logging import setup_logging
from app.auth.dependencies import get_current_user

logger = setup_logging(__name__)
router = APIRouter(tags=["langgraph-core"])


async def _invoke_agent(request: InvokeAgentRequest, db: Session):
    """Execute the appropriate agent based on request type."""
    from app.services.langgraph.agents.qualification_agent import QualificationAgent
    from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
    from app.services.langgraph.agents.growth_agent import GrowthAgent
    from app.services.langgraph.agents.marketing_agent import MarketingAgent
    from app.services.langgraph.agents.bdr_agent import BDRAgent
    from app.services.langgraph.agents.conversation_agent import ConversationAgent

    thread_id = await get_or_create_thread_id(request)

    if request.agent_type == "qualification":
        agent = QualificationAgent(
            provider=request.provider or "cerebras",
            model=request.model,
            db=db
        )
        result, latency_ms, metadata = await agent.qualify(**request.input)
        return thread_id, {
            "score": result.qualification_score,
            "reasoning": result.qualification_reasoning,
            "tier": result.tier,
            "fit_assessment": result.fit_assessment,
            "contact_quality": result.contact_quality,
            "sales_potential": result.sales_potential,
            "recommendations": result.recommendations or [],
            "provider": metadata.get("provider"),
            "model": metadata.get("model")
        }, result

    elif request.agent_type == "enrichment":
        agent = EnrichmentAgent()
        result = await agent.enrich(**request.input)
        return thread_id, {
            "enriched_data": result.enriched_data,
            "data_sources": result.data_sources,
            "confidence_score": result.confidence_score,
            "tools_called": result.tools_called,
            "latency_ms": result.latency_ms,
            "iterations_used": result.iterations_used,
            "total_cost_usd": result.total_cost_usd,
            "errors": result.errors
        }, result

    elif request.agent_type == "growth":
        agent = GrowthAgent()
        result = await agent.run_campaign(
            lead_id=request.input.get("lead_id"),
            goal=request.input.get("goal", "engagement"),
            max_cycles=request.input.get("max_cycles", 5)
        )
        return thread_id, {
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
        }, result

    elif request.agent_type == "marketing":
        agent = MarketingAgent()
        result = await agent.generate_campaign(
            campaign_brief=request.input.get("campaign_brief"),
            target_audience=request.input.get("target_audience"),
            campaign_goals=request.input.get("campaign_goals", ["awareness"])
        )
        return thread_id, {
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
        }, result

    elif request.agent_type == "bdr":
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
        return thread_id, {
            "status": "draft_ready",
            "draft_subject": interrupt_data.get("draft_subject"),
            "draft_body": interrupt_data.get("draft_body"),
            "research_summary": interrupt_data.get("research_summary"),
            "company_name": interrupt_data.get("company_name"),
            "contact_name": interrupt_data.get("contact_name"),
            "revision_count": interrupt_data.get("revision_count", 0),
            "requires_approval": True
        }, result

    elif request.agent_type == "conversation":
        agent = ConversationAgent()
        config = create_streaming_config(thread_id=thread_id)
        result = await agent.send_message(
            text=request.input.get("text") or request.input.get("user_input"),
            context=request.input.get("context"),
            config=config if thread_id else None
        )
        return thread_id, {
            "user_input": result.user_input,
            "assistant_response": result.assistant_response,
            "audio_output": result.audio_output,
            "turn_number": result.turn_number,
            "audio_metadata": result.audio_metadata,
            "latency_breakdown": result.latency_breakdown,
            "total_cost_usd": result.total_cost_usd,
            "estimated_audio_duration_ms": result.estimated_audio_duration_ms
        }, result

    raise HTTPException(status_code=400, detail=f"Unsupported agent type: {request.agent_type}")


@router.post("/invoke", response_model=AgentResponse, status_code=200)
async def invoke_agent(
    request: InvokeAgentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Invoke a LangGraph agent and return the complete response."""
    try:
        if request.agent_type not in VALID_AGENTS:
            raise HTTPException(status_code=400, detail=f"Invalid agent_type. Must be one of: {', '.join(VALID_AGENTS)}")

        await get_redis_checkpointer()
        thread_id = await get_or_create_thread_id(request)
        start_time = time.time()

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
            thread_id, output_data, result = await _invoke_agent(request, db)
            duration_ms = int((time.time() - start_time) * 1000)

            execution.status = "success"
            execution.completed_at = datetime.utcnow()
            execution.duration_ms = duration_ms
            execution.output_data = output_data
            execution.cost_usd = getattr(result, 'cost_usd', 0.0)
            execution.tokens_used = getattr(result, 'tokens_used', 0)
            db.commit()

            logger.info(f"{request.agent_type} agent completed in {duration_ms}ms")
            return AgentResponse(
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

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            execution.status = "failed"
            execution.completed_at = datetime.utcnow()
            execution.duration_ms = duration_ms
            execution.error_message = str(e)
            db.commit()
            logger.error(f"{request.agent_type} agent failed: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Agent execution failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error invoking agent: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent invocation failed: {str(e)}")


@router.post("/stream")
async def stream_agent(
    request: InvokeAgentRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """Stream a LangGraph agent execution via Server-Sent Events (SSE)."""
    try:
        if request.agent_type not in VALID_AGENTS:
            raise HTTPException(status_code=400, detail=f"Invalid agent_type. Must be one of: {', '.join(VALID_AGENTS)}")

        thread_id = await get_or_create_thread_id(request)
        await get_redis_checkpointer()

        async def event_generator() -> AsyncGenerator[str, None]:
            try:
                yield f"data: {json.dumps({'type': 'start', 'agent_type': request.agent_type, 'thread_id': thread_id})}\n\n"
                start_time = time.time()

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

                try:
                    yield f"data: {json.dumps({'type': 'message', 'content': f'Starting {request.agent_type} agent...'})}\n\n"
                    _, output_data, result = await _invoke_agent(request, db)
                    duration_ms = int((time.time() - start_time) * 1000)

                    execution.status = "success"
                    execution.completed_at = datetime.utcnow()
                    execution.duration_ms = duration_ms
                    execution.output_data = output_data
                    execution.cost_usd = getattr(result, 'cost_usd', 0.0)
                    db.commit()

                    yield f"data: {json.dumps({'type': 'complete', 'output': output_data, 'metadata': {'duration_ms': duration_ms, 'cost_usd': execution.cost_usd}})}\n\n"

                except Exception as e:
                    duration_ms = int((time.time() - start_time) * 1000)
                    execution.status = "failed"
                    execution.completed_at = datetime.utcnow()
                    execution.duration_ms = duration_ms
                    execution.error_message = str(e)
                    db.commit()
                    yield f"data: {json.dumps({'type': 'error', 'error': str(e), 'metadata': {'duration_ms': duration_ms}})}\n\n"
                    raise

            except Exception as e:
                logger.error(f"Error in event generator: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting up streaming: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initialize streaming: {str(e)}")


@router.get("/state/{thread_id}", response_model=StateResponse, status_code=200)
async def get_agent_state(
    thread_id: str,
    checkpoint_id: str = None,
    current_user: dict = Depends(get_current_user),
):
    """Retrieve conversation state from Redis checkpoint."""
    try:
        checkpointer = await get_redis_checkpointer()
        config = get_checkpoint_config(thread_id, checkpoint_id)
        checkpoint = await checkpointer.aget(config)

        if not checkpoint:
            raise HTTPException(status_code=404, detail=f"No checkpoint found for thread_id: {thread_id}")

        state = checkpoint.get("channel_values", {})
        metadata = checkpoint.get("metadata", {})
        logger.info(f"Retrieved checkpoint for thread_id={thread_id}")

        return StateResponse(thread_id=thread_id, checkpoint_exists=True, state=state, metadata=metadata)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving checkpoint: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to retrieve checkpoint state: {str(e)}")
