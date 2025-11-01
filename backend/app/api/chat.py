"""
Chat API endpoints for Claude Agent SDK agents.

Provides conversational interfaces for:
- SR/BDR Agent: Sales rep assistant
- Pipeline Manager: Import orchestration
- Customer Success: Onboarding & support
"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional

from app.agents_sdk.agents import SRBDRAgent, PipelineManagerAgent, CustomerSuccessAgent
from app.agents_sdk.schemas.chat import ChatRequest, ChatResponse
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/sr-bdr", response_model=ChatResponse)
async def sr_bdr_chat(request: ChatRequest):
    """
    Chat with SR/BDR Agent - Sales rep conversational assistant.

    Args:
        request: Chat request with user_id, message, and optional session_id

    Returns:
        ChatResponse with agent's reply and session info

    Features:
        - Lead qualification and scoring
        - Pipeline management
        - Sales recommendations
        - Streaming support (if request.stream=True)
    """
    try:
        agent = SRBDRAgent()

        # Get or create session
        session_id = await agent.get_or_create_session(
            user_id=request.user_id,
            session_id=request.session_id
        )

        logger.info(f"SR/BDR chat: user={request.user_id}, session={session_id}, message_len={len(request.message)}")

        # Stream response if requested
        if request.stream:
            return StreamingResponse(
                agent.chat(session_id=session_id, message=request.message),
                media_type="text/event-stream"
            )

        # Non-streaming response
        # TODO: Implement non-streaming response accumulation
        # For now, return placeholder
        return ChatResponse(
            session_id=session_id,
            message="SR/BDR agent response (streaming only for MVP)",
            agent_type="sr_bdr"
        )

    except Exception as e:
        logger.error(f"SR/BDR chat failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )


@router.post("/pipeline-manager", response_model=ChatResponse)
async def pipeline_manager_chat(request: ChatRequest):
    """
    Chat with Pipeline Manager Agent - Interactive import orchestration.

    Args:
        request: Chat request with user_id, message, and optional session_id

    Returns:
        ChatResponse with agent's reply and session info

    Features:
        - Pipeline status monitoring
        - Import validation
        - Error diagnosis
        - Progress tracking
    """
    try:
        agent = PipelineManagerAgent()

        # Get or create session
        session_id = await agent.get_or_create_session(
            user_id=request.user_id,
            session_id=request.session_id
        )

        logger.info(f"Pipeline Manager chat: user={request.user_id}, session={session_id}")

        # Stream response if requested
        if request.stream:
            return StreamingResponse(
                agent.chat(session_id=session_id, message=request.message),
                media_type="text/event-stream"
            )

        # Non-streaming response
        return ChatResponse(
            session_id=session_id,
            message="Pipeline Manager agent response (streaming only for MVP)",
            agent_type="pipeline_manager"
        )

    except Exception as e:
        logger.error(f"Pipeline Manager chat failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )


@router.post("/customer-success", response_model=ChatResponse)
async def customer_success_chat(request: ChatRequest):
    """
    Chat with Customer Success Agent - Onboarding & support assistant.

    Args:
        request: Chat request with user_id, message, and optional session_id

    Returns:
        ChatResponse with agent's reply and session info

    Features:
        - Onboarding guidance
        - Feature explanations
        - Troubleshooting support
        - Best practices recommendations
    """
    try:
        agent = CustomerSuccessAgent()

        # Get or create session
        session_id = await agent.get_or_create_session(
            user_id=request.user_id,
            session_id=request.session_id
        )

        logger.info(f"Customer Success chat: user={request.user_id}, session={session_id}")

        # Stream response if requested
        if request.stream:
            return StreamingResponse(
                agent.chat(session_id=session_id, message=request.message),
                media_type="text/event-stream"
            )

        # Non-streaming response
        return ChatResponse(
            session_id=session_id,
            message="Customer Success agent response (streaming only for MVP)",
            agent_type="customer_success"
        )

    except Exception as e:
        logger.error(f"Customer Success chat failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Chat failed: {str(e)}"
        )


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Retrieve session history.

    Args:
        session_id: Session identifier

    Returns:
        Session data with message history
    """
    try:
        # TODO: Implement session retrieval from Redis
        # For now, return placeholder
        logger.info(f"Session retrieval: {session_id}")
        return {
            "session_id": session_id,
            "status": "not_implemented",
            "message": "Session retrieval will be implemented in future tasks"
        }

    except Exception as e:
        logger.error(f"Session retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Session retrieval failed: {str(e)}"
        )


@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete/archive session.

    Args:
        session_id: Session identifier

    Returns:
        Confirmation of deletion
    """
    try:
        # TODO: Implement session deletion/archival
        # For now, return placeholder
        logger.info(f"Session deletion: {session_id}")
        return {
            "session_id": session_id,
            "status": "not_implemented",
            "message": "Session deletion will be implemented in future tasks"
        }

    except Exception as e:
        logger.error(f"Session deletion failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Session deletion failed: {str(e)}"
        )
