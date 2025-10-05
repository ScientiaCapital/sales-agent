"""
Agent Transfer System API

POST /api/transfer/{from_agent}/{to_agent} - Execute agent transfer
GET /api/transfer/rules - Get transfer rules and paths
GET /api/transfer/history - Get transfer history
GET /api/transfer/status - Get system status
"""

from fastapi import APIRouter, HTTPException, status, Query
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import logging

from app.services.agent_transfer import (
    AgentTransferSystem,
    AgentRole,
    TransferContext,
    TransferResult,
    AgentTransferError
)
from app.services.cerebras_routing import CerebrasAccessMethod

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/transfer", tags=["transfer"])


class TransferRequest(BaseModel):
    """Request for agent transfer."""
    lead_id: Optional[int] = Field(None, description="Lead ID being transferred")
    lead_data: Dict[str, Any] = Field(..., description="Lead data and context")
    conversation_history: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Conversation history with user"
    )
    transfer_reason: str = Field(..., description="Reason for transfer", min_length=10)
    priority: str = Field("medium", description="Transfer priority (low|medium|high|urgent)")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    temperature: float = Field(0.7, ge=0.0, le=1.0, description="Model temperature")
    preferred_method: Optional[str] = Field(
        "direct",
        description="Preferred Cerebras access method"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "lead_id": 123,
                "lead_data": {
                    "company_name": "Acme Corp",
                    "industry": "SaaS",
                    "qualification_score": 85,
                    "contact_email": "ceo@acme.com"
                },
                "conversation_history": [
                    {"role": "agent", "content": "Analyzed lead qualification criteria"},
                    {"role": "system", "content": "Lead scored 85/100 - qualified"}
                ],
                "transfer_reason": "Lead is qualified and ready for enrichment with additional company data",
                "priority": "high",
                "temperature": 0.7,
                "preferred_method": "direct"
            }
        }


class TransferResponse(BaseModel):
    """Response from agent transfer."""
    from_agent: str
    to_agent: str
    handoff_successful: bool
    handoff_message: str
    next_action: str
    estimated_completion_time: str
    total_latency_ms: int
    lead_id: Optional[int]
    transfer_reason: str


class TransferPathResponse(BaseModel):
    """Transfer path information."""
    from_agent: str
    to_agent: str
    path: List[str]
    path_length: int
    is_direct: bool


@router.post("/{from_agent}/{to_agent}", response_model=TransferResponse, status_code=status.HTTP_200_OK)
async def execute_transfer(
    from_agent: str,
    to_agent: str,
    request: TransferRequest
):
    """
    Execute agent-to-agent transfer with context preservation.

    **Supported Transfer Flows:**
    - qualification → enrichment (qualified leads need data enrichment)
    - enrichment → bdr (enriched leads ready for outreach)
    - bdr → ae (high-value leads need AE attention)
    - any → supervisor (escalation for complex cases)

    **Transfer Process:**
    1. Validate transfer is allowed
    2. Source agent generates handoff message
    3. Target agent receives and confirms
    4. Next action is determined
    5. Audit trail is logged

    **Returns:**
    - Handoff confirmation
    - Next action from target agent
    - Estimated completion time
    """
    try:
        # Parse agent roles
        try:
            source_agent = AgentRole(from_agent)
            target_agent = AgentRole(to_agent)
        except ValueError as e:
            valid_agents = [a.value for a in AgentRole]
            raise HTTPException(
                status_code=400,
                detail=f"Invalid agent role. Valid agents: {valid_agents}"
            )

        # Parse preferred method
        try:
            method = CerebrasAccessMethod(request.preferred_method)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid preferred_method: {request.preferred_method}"
            )

        # Build transfer context
        from datetime import datetime
        context = TransferContext(
            lead_id=request.lead_id,
            lead_data=request.lead_data,
            conversation_history=request.conversation_history,
            transfer_reason=request.transfer_reason,
            priority=request.priority,
            metadata=request.metadata,
            timestamp=datetime.now().isoformat()
        )

        # Initialize transfer system
        transfer_system = AgentTransferSystem(preferred_method=method)

        logger.info(
            f"Executing transfer: {from_agent} → {to_agent}, "
            f"lead_id={request.lead_id}"
        )

        # Execute transfer
        result: TransferResult = await transfer_system.transfer(
            from_agent=source_agent,
            to_agent=target_agent,
            context=context,
            temperature=request.temperature
        )

        # Build response
        response = TransferResponse(
            from_agent=result.from_agent.value,
            to_agent=result.to_agent.value,
            handoff_successful=result.handoff_successful,
            handoff_message=result.handoff_message,
            next_action=result.next_action,
            estimated_completion_time=result.estimated_completion_time or "Unknown",
            total_latency_ms=result.total_latency_ms,
            lead_id=request.lead_id,
            transfer_reason=request.transfer_reason
        )

        logger.info(
            f"Transfer complete: {from_agent} → {to_agent}, "
            f"{result.total_latency_ms}ms"
        )

        return response

    except AgentTransferError as e:
        logger.error(f"Transfer validation failed: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    except Exception as e:
        logger.error(f"Transfer failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Transfer execution failed: {str(e)}"
        )


@router.get("/rules", status_code=status.HTTP_200_OK)
async def get_transfer_rules():
    """
    Get agent transfer rules and valid paths.

    **Returns:**
    - Transfer rules for each agent
    - Valid transfer targets
    - Role descriptions
    """
    transfer_system = AgentTransferSystem()

    return {
        "transfer_rules": {
            agent.value: [t.value for t in transfer_system.get_valid_targets(agent)]
            for agent in AgentRole
        },
        "agent_descriptions": {
            "qualification": "Qualifies incoming leads based on ICP criteria",
            "enrichment": "Enriches lead data with company and contact information",
            "bdr": "Business Development Representative for outreach",
            "ae": "Account Executive for high-value opportunities",
            "supervisor": "Handles escalations and complex cases",
            "research": "Conducts deep research on accounts",
            "outreach": "Automated outreach campaigns"
        },
        "common_paths": [
            ["qualification", "enrichment", "bdr"],
            ["enrichment", "bdr", "ae"],
            ["bdr", "supervisor"],
            ["research", "enrichment", "bdr"]
        ]
    }


@router.get("/path/{from_agent}/{to_agent}", response_model=TransferPathResponse, status_code=status.HTTP_200_OK)
async def get_transfer_path(from_agent: str, to_agent: str):
    """
    Get transfer path between two agents.

    **Returns:**
    - Shortest path from source to target agent
    - Path length
    - Whether it's a direct transfer
    """
    try:
        # Parse agent roles
        source = AgentRole(from_agent)
        target = AgentRole(to_agent)

        transfer_system = AgentTransferSystem()
        path = transfer_system.get_transfer_path(source, target)

        if not path:
            raise HTTPException(
                status_code=404,
                detail=f"No valid transfer path from {from_agent} to {to_agent}"
            )

        return TransferPathResponse(
            from_agent=from_agent,
            to_agent=to_agent,
            path=[a.value for a in path],
            path_length=len(path),
            is_direct=len(path) == 2
        )

    except ValueError:
        valid_agents = [a.value for a in AgentRole]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent role. Valid agents: {valid_agents}"
        )


@router.get("/history", status_code=status.HTTP_200_OK)
async def get_transfer_history(
    lead_id: Optional[int] = Query(None, description="Filter by lead ID"),
    from_agent: Optional[str] = Query(None, description="Filter by source agent"),
    to_agent: Optional[str] = Query(None, description="Filter by target agent"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum results")
):
    """
    Get transfer history with optional filters.

    **Returns:**
    - List of transfers
    - Transfer details
    - Handoff messages
    """
    try:
        # Parse agent filters
        source_filter = AgentRole(from_agent) if from_agent else None
        target_filter = AgentRole(to_agent) if to_agent else None

        transfer_system = AgentTransferSystem()
        history = transfer_system.get_transfer_history(
            lead_id=lead_id,
            from_agent=source_filter,
            to_agent=target_filter,
            limit=limit
        )

        return {
            "total_results": len(history),
            "transfers": [
                {
                    "from_agent": t.from_agent.value,
                    "to_agent": t.to_agent.value,
                    "lead_id": t.transfer_context.lead_id,
                    "transfer_reason": t.transfer_context.transfer_reason,
                    "priority": t.transfer_context.priority,
                    "handoff_successful": t.handoff_successful,
                    "handoff_message": t.handoff_message,
                    "next_action": t.next_action,
                    "timestamp": t.transfer_context.timestamp,
                    "latency_ms": t.total_latency_ms
                }
                for t in history
            ]
        }

    except ValueError as e:
        valid_agents = [a.value for a in AgentRole]
        raise HTTPException(
            status_code=400,
            detail=f"Invalid agent role. Valid agents: {valid_agents}"
        )


@router.get("/status", status_code=status.HTTP_200_OK)
async def get_transfer_status():
    """
    Get transfer system status.

    **Returns:**
    - Total transfers executed
    - Recent transfer history
    - Transfer rules
    - Router status
    """
    try:
        transfer_system = AgentTransferSystem()
        return transfer_system.get_status()

    except Exception as e:
        logger.error(f"Failed to get status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to retrieve status: {str(e)}"
        )


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check for transfer service.

    **Returns:**
    - Service health status
    - Available agents
    - Transfer capacity
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
            "service": "agent_transfer",
            "available_agents": [a.value for a in AgentRole],
            "total_agents": len(AgentRole),
            "available_methods": available_methods,
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
            "service": "agent_transfer",
            "error": str(e)
        }
