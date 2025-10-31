"""
Agent Transfer Tools - Enable Multi-Agent Workflow Handoffs

Implements Cerebras cookbook pattern for agent-to-agent transfers.
Allows agents to hand off conversations and tasks to specialized agents.

Pattern from Cerebras sales agent:
- Agents use function tools to transfer control
- Transfer tools return new agent instances
- Context is passed seamlessly between agents
- Each agent has distinct capabilities and prompts

Usage:
    ```python
    from app.services.langgraph.tools.agent_transfer_tools import create_transfer_tools

    # Create transfer tools for qualification agent
    tools = create_transfer_tools(
        current_agent="qualification",
        available_transfers=["enrichment", "growth", "marketing"]
    )

    # Agent can now call transfer tools:
    # - transfer_to_enrichment(reason, context)
    # - transfer_to_growth(reason, context)
    # - transfer_to_marketing(reason, context)
    ```

Transfer Flow:
    1. Agent A determines it needs Agent B's expertise
    2. Agent A calls transfer_to_agent_b(reason="...", context={...})
    3. Transfer tool validates the transfer
    4. Transfer tool routes to Agent B via orchestrator
    5. Agent B receives context and continues workflow
    6. Result flows back through orchestrator
"""

from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum

from langchain_core.tools import tool, BaseTool
from pydantic import BaseModel, Field

from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ========== Transfer Models ==========

class AgentType(str, Enum):
    """Available agent types for transfers."""
    QUALIFICATION = "qualification"
    ENRICHMENT = "enrichment"
    GROWTH = "growth"
    MARKETING = "marketing"
    BDR = "bdr"
    CONVERSATION = "conversation"
    REASONER = "reasoner"
    SOCIAL_RESEARCH = "social_research"


class TransferReason(str, Enum):
    """Reasons for agent transfer."""
    SPECIALIZED_EXPERTISE = "specialized_expertise"
    WORKFLOW_CONTINUATION = "workflow_continuation"
    USER_REQUEST = "user_request"
    TASK_DELEGATION = "task_delegation"
    ERROR_RECOVERY = "error_recovery"


@dataclass
class TransferRequest:
    """Agent transfer request."""
    from_agent: str
    to_agent: AgentType
    reason: TransferReason
    context: Dict[str, Any]
    urgency: str = "normal"  # low, normal, high
    require_approval: bool = False  # Human-in-loop flag


class TransferContext(BaseModel):
    """Context passed between agents during transfer."""
    lead_id: Optional[int] = Field(None, description="Lead ID being processed")
    company_name: Optional[str] = Field(None, description="Company name")
    prior_results: Dict[str, Any] = Field(default_factory=dict, description="Results from prior agents")
    workflow_stage: str = Field("", description="Current workflow stage")
    additional_context: Dict[str, Any] = Field(default_factory=dict, description="Additional context")


# ========== Transfer Tool Factory ==========

def create_transfer_tools(
    current_agent: str,
    available_transfers: List[str],
    orchestrator_callback: Optional[Callable] = None
) -> List[BaseTool]:
    """
    Create agent transfer tools for the current agent.

    Args:
        current_agent: Name of current agent
        available_transfers: List of agent names this agent can transfer to
        orchestrator_callback: Optional callback to orchestrator for actual transfer

    Returns:
        List of transfer tools (one per available transfer)

    Example:
        >>> tools = create_transfer_tools(
        ...     current_agent="qualification",
        ...     available_transfers=["enrichment", "growth"]
        ... )
        >>> # Creates: transfer_to_enrichment, transfer_to_growth
    """
    transfer_tools = []

    for target_agent in available_transfers:
        transfer_tool = create_transfer_tool(
            current_agent=current_agent,
            target_agent=target_agent,
            orchestrator_callback=orchestrator_callback
        )
        transfer_tools.append(transfer_tool)

    logger.info(
        f"Created {len(transfer_tools)} transfer tools for {current_agent}: "
        f"{', '.join(available_transfers)}"
    )

    return transfer_tools


def create_transfer_tool(
    current_agent: str,
    target_agent: str,
    orchestrator_callback: Optional[Callable] = None
) -> BaseTool:
    """
    Create a single transfer tool for specific agent.

    Args:
        current_agent: Name of current agent
        target_agent: Name of target agent
        orchestrator_callback: Optional callback for orchestration

    Returns:
        Transfer tool for target agent
    """

    @tool
    def transfer_tool(
        reason: str = Field(..., description="Reason for transfer"),
        context: Dict[str, Any] = Field(default_factory=dict, description="Context to pass"),
        lead_id: Optional[int] = Field(None, description="Lead ID if applicable"),
        company_name: Optional[str] = Field(None, description="Company name if applicable"),
        workflow_stage: str = Field("", description="Current workflow stage"),
        urgency: str = Field("normal", description="Transfer urgency (low/normal/high)"),
        require_approval: bool = Field(False, description="Require human approval before transfer")
    ) -> Dict[str, Any]:
        """
        Transfer workflow to specialized agent.

        This tool hands off the current workflow to another agent
        that has specific expertise needed to continue processing.

        Returns:
            Transfer confirmation with next agent details
        """
        logger.info(
            f"🔄 Transfer requested: {current_agent} → {target_agent} "
            f"(reason: {reason})"
        )

        # Build transfer request
        transfer_request = TransferRequest(
            from_agent=current_agent,
            to_agent=AgentType(target_agent),
            reason=TransferReason.SPECIALIZED_EXPERTISE,
            context={
                "lead_id": lead_id,
                "company_name": company_name,
                "workflow_stage": workflow_stage,
                "reason": reason,
                **context
            },
            urgency=urgency,
            require_approval=require_approval
        )

        # If orchestrator callback provided, use it
        if orchestrator_callback:
            result = orchestrator_callback(transfer_request)
            return result

        # Otherwise, return transfer confirmation
        # (Actual transfer will be handled by orchestrator)
        return {
            "transfer_initiated": True,
            "from_agent": current_agent,
            "to_agent": target_agent,
            "reason": reason,
            "context": transfer_request.context,
            "next_action": f"Workflow transferred to {target_agent} agent",
            "message": f"Successfully transferred to {target_agent} for {reason}"
        }

    # Set dynamic tool name and description
    transfer_tool.name = f"transfer_to_{target_agent}"
    transfer_tool.description = (
        f"Transfer workflow to {target_agent} agent for specialized processing. "
        f"Use when {target_agent} expertise is needed. "
        f"Current agent: {current_agent}"
    )

    return transfer_tool


# ========== Specialized Transfer Tools ==========

@tool
def transfer_to_enrichment(
    reason: str = Field(..., description="Why enrichment is needed"),
    lead_id: Optional[int] = Field(None, description="Lead ID to enrich"),
    email: Optional[str] = Field(None, description="Email to enrich"),
    linkedin_url: Optional[str] = Field(None, description="LinkedIn URL to scrape")
) -> Dict[str, Any]:
    """
    Transfer to EnrichmentAgent for LinkedIn/Apollo data enrichment.

    Use when you need to:
    - Scrape LinkedIn profiles
    - Enrich contact data from multiple sources
    - Get detailed professional background
    - Find social media profiles
    """
    logger.info(f"🔄 Transfer to enrichment: {reason}")
    return {
        "transfer_initiated": True,
        "to_agent": "enrichment",
        "reason": reason,
        "context": {"lead_id": lead_id, "email": email, "linkedin_url": linkedin_url}
    }


@tool
def transfer_to_growth(
    reason: str = Field(..., description="Why growth analysis is needed"),
    company_name: str = Field(..., description="Company to analyze"),
    industry: Optional[str] = Field(None, description="Industry sector")
) -> Dict[str, Any]:
    """
    Transfer to GrowthAgent for market analysis and growth strategies.

    Use when you need to:
    - Analyze market opportunities
    - Research competitive landscape
    - Identify growth strategies
    - Evaluate market trends
    """
    logger.info(f"🔄 Transfer to growth: {reason}")
    return {
        "transfer_initiated": True,
        "to_agent": "growth",
        "reason": reason,
        "context": {"company_name": company_name, "industry": industry}
    }


@tool
def transfer_to_marketing(
    reason: str = Field(..., description="Why marketing is needed"),
    lead_id: Optional[int] = Field(None, description="Lead ID"),
    campaign_type: str = Field("", description="Type of campaign needed")
) -> Dict[str, Any]:
    """
    Transfer to MarketingAgent for campaign creation and outreach.

    Use when you need to:
    - Create personalized outreach campaigns
    - Generate email sequences
    - Design social media campaigns
    - Write marketing copy
    """
    logger.info(f"🔄 Transfer to marketing: {reason}")
    return {
        "transfer_initiated": True,
        "to_agent": "marketing",
        "reason": reason,
        "context": {"lead_id": lead_id, "campaign_type": campaign_type}
    }


@tool
def transfer_to_bdr(
    reason: str = Field(..., description="Why BDR workflow is needed"),
    lead_id: int = Field(..., description="Lead ID for BDR workflow"),
    meeting_type: str = Field("discovery", description="Type of meeting to book")
) -> Dict[str, Any]:
    """
    Transfer to BDRAgent for meeting booking and human-in-loop workflows.

    Use when you need to:
    - Book meetings with qualified leads
    - Coordinate calendars
    - Handle human approval workflows
    - Manage outreach sequences
    """
    logger.info(f"🔄 Transfer to BDR: {reason}")
    return {
        "transfer_initiated": True,
        "to_agent": "bdr",
        "reason": reason,
        "context": {"lead_id": lead_id, "meeting_type": meeting_type}
    }


@tool
def transfer_to_conversation(
    reason: str = Field(..., description="Why voice conversation is needed"),
    lead_id: int = Field(..., description="Lead ID for conversation"),
    conversation_type: str = Field("discovery", description="Type of conversation")
) -> Dict[str, Any]:
    """
    Transfer to ConversationAgent for voice/chat interactions.

    Use when you need to:
    - Conduct voice calls with leads
    - Have real-time chat conversations
    - Gather information through dialogue
    - Handle objections or questions
    """
    logger.info(f"🔄 Transfer to conversation: {reason}")
    return {
        "transfer_initiated": True,
        "to_agent": "conversation",
        "reason": reason,
        "context": {"lead_id": lead_id, "conversation_type": conversation_type}
    }


# ========== Transfer Registry ==========

# Default transfer tools available to all agents
DEFAULT_TRANSFER_TOOLS = [
    transfer_to_enrichment,
    transfer_to_growth,
    transfer_to_marketing,
    transfer_to_bdr,
    transfer_to_conversation,
]

# Agent-specific transfer permissions
TRANSFER_PERMISSIONS = {
    "qualification": ["enrichment", "growth"],
    "enrichment": ["growth", "marketing"],
    "growth": ["marketing"],
    "marketing": ["bdr"],
    "bdr": ["conversation"],
    "conversation": ["bdr", "enrichment"],
}


def get_allowed_transfers(agent_name: str) -> List[str]:
    """Get list of agents this agent can transfer to."""
    return TRANSFER_PERMISSIONS.get(agent_name, [])


def is_transfer_allowed(from_agent: str, to_agent: str) -> bool:
    """Check if transfer from one agent to another is allowed."""
    allowed = TRANSFER_PERMISSIONS.get(from_agent, [])
    return to_agent in allowed
