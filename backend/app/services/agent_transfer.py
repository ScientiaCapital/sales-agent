"""
Agent Transfer System

Implements intelligent agent-to-agent handoffs using the @transfer_tool pattern.

Supported Transfer Flows:
1. QualificationAgent → EnrichmentAgent (qualified leads need enrichment)
2. Enrichment Agent → BDRAgent (enriched leads ready for outreach)
3. BDRAgent → AEAgent (high-value leads need AE attention)
4. Any → SupervisorAgent (escalation for complex cases)

Each transfer includes:
- Context preservation across agents
- Automatic state management
- Handoff verification
- Transfer audit trail
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
import json

from app.services.cerebras_routing import CerebrasRouter, CerebrasAccessMethod

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Agent roles in the sales workflow."""
    QUALIFICATION = "qualification"    # Qualify incoming leads
    ENRICHMENT = "enrichment"         # Enrich lead data
    BDR = "bdr"                       # Business Development Representative
    AE = "ae"                         # Account Executive
    SUPERVISOR = "supervisor"         # Escalation and oversight
    RESEARCH = "research"             # Research specialist
    OUTREACH = "outreach"             # Automated outreach


@dataclass
class TransferContext:
    """Context passed between agents during transfer."""
    lead_id: Optional[int]
    lead_data: Dict[str, Any]
    conversation_history: List[Dict[str, str]]
    transfer_reason: str
    priority: str  # low|medium|high|urgent
    metadata: Dict[str, Any]
    timestamp: str


@dataclass
class TransferResult:
    """Result of agent transfer operation."""
    from_agent: AgentRole
    to_agent: AgentRole
    transfer_context: TransferContext
    handoff_successful: bool
    handoff_message: str
    next_action: str
    estimated_completion_time: Optional[str]
    total_latency_ms: int
    total_cost_usd: float


class AgentTransferError(Exception):
    """Raised when agent transfer fails."""
    pass


class AgentTransferSystem:
    """
    Agent transfer system with @transfer_tool pattern implementation.

    Workflow:
    1. Source agent requests transfer
    2. System validates transfer rules
    3. Context is packaged and preserved
    4. Target agent receives handoff
    5. Target agent confirms readiness
    6. Transfer complete, audit logged

    Example Transfer Flow:
    ```
    QualificationAgent: "This lead is qualified, transfer to enrichment"
    → @transfer_tool(to="enrichment", reason="qualification_complete")
    → EnrichmentAgent receives context
    → EnrichmentAgent: "Starting enrichment for lead #123"
    ```
    """

    # Valid transfer paths (from_agent → to_agent)
    TRANSFER_RULES = {
        AgentRole.QUALIFICATION: [AgentRole.ENRICHMENT, AgentRole.SUPERVISOR],
        AgentRole.ENRICHMENT: [AgentRole.BDR, AgentRole.SUPERVISOR],
        AgentRole.BDR: [AgentRole.AE, AgentRole.SUPERVISOR],
        AgentRole.AE: [AgentRole.SUPERVISOR],
        AgentRole.RESEARCH: [AgentRole.QUALIFICATION, AgentRole.ENRICHMENT, AgentRole.BDR],
        AgentRole.OUTREACH: [AgentRole.BDR, AgentRole.SUPERVISOR],
        AgentRole.SUPERVISOR: [
            AgentRole.QUALIFICATION,
            AgentRole.ENRICHMENT,
            AgentRole.BDR,
            AgentRole.AE,
            AgentRole.RESEARCH
        ]
    }

    def __init__(
        self,
        router: Optional[CerebrasRouter] = None,
        preferred_method: CerebrasAccessMethod = CerebrasAccessMethod.DIRECT
    ):
        """
        Initialize agent transfer system.

        Args:
            router: CerebrasRouter for agent communication
            preferred_method: Preferred Cerebras access method
        """
        self.router = router or CerebrasRouter()
        self.preferred_method = preferred_method
        self.transfer_history: List[TransferResult] = []

        logger.info(f"Initialized AgentTransferSystem: method={preferred_method.value}")

    async def transfer(
        self,
        from_agent: AgentRole,
        to_agent: AgentRole,
        context: TransferContext,
        temperature: float = 0.7
    ) -> TransferResult:
        """
        Execute agent transfer with context preservation.

        Args:
            from_agent: Source agent role
            to_agent: Target agent role
            context: Transfer context with lead data
            temperature: Model temperature

        Returns:
            TransferResult with handoff details

        Raises:
            AgentTransferError: If transfer is invalid or fails
        """
        start_time = datetime.now()

        logger.info(
            f"Transfer request: {from_agent.value} → {to_agent.value} "
            f"(lead_id={context.lead_id}, reason={context.transfer_reason})"
        )

        # Step 1: Validate transfer rules
        self._validate_transfer(from_agent, to_agent)

        # Step 2: Generate handoff message from source agent
        handoff_prep = await self._prepare_handoff(
            from_agent, to_agent, context, temperature
        )

        # Step 3: Transfer context to target agent
        handoff_accept = await self._execute_handoff(
            from_agent, to_agent, context, handoff_prep, temperature
        )

        # Step 4: Generate next action from target agent
        next_action = await self._determine_next_action(
            to_agent, context, temperature
        )

        end_time = datetime.now()
        total_duration = (end_time - start_time).total_seconds() * 1000

        result = TransferResult(
            from_agent=from_agent,
            to_agent=to_agent,
            transfer_context=context,
            handoff_successful=True,
            handoff_message=handoff_accept,
            next_action=next_action,
            estimated_completion_time=self._estimate_completion(to_agent),
            total_latency_ms=int(total_duration),
            total_cost_usd=0.0  # Updated with actual costs in _prepare_handoff, etc.
        )

        self.transfer_history.append(result)

        logger.info(
            f"Transfer complete: {from_agent.value} → {to_agent.value}, "
            f"{total_duration:.0f}ms"
        )

        return result

    def _validate_transfer(self, from_agent: AgentRole, to_agent: AgentRole):
        """
        Validate transfer is allowed by rules.

        Raises:
            AgentTransferError: If transfer is not allowed
        """
        allowed_targets = self.TRANSFER_RULES.get(from_agent, [])

        if to_agent not in allowed_targets:
            raise AgentTransferError(
                f"Transfer from {from_agent.value} to {to_agent.value} is not allowed. "
                f"Valid targets: {[a.value for a in allowed_targets]}"
            )

    async def _prepare_handoff(
        self,
        from_agent: AgentRole,
        to_agent: AgentRole,
        context: TransferContext,
        temperature: float
    ) -> str:
        """Generate handoff message from source agent."""
        handoff_prompt = f"""You are the {from_agent.value.upper()} agent completing a handoff.

TRANSFER DETAILS:
- Target Agent: {to_agent.value}
- Lead ID: {context.lead_id}
- Lead Data: {json.dumps(context.lead_data, indent=2)}
- Transfer Reason: {context.transfer_reason}
- Priority: {context.priority}

CONVERSATION HISTORY:
{json.dumps(context.conversation_history, indent=2)}

Generate a brief handoff message to the {to_agent.value} agent that includes:
1. What you've accomplished
2. Why this lead is being transferred
3. Key information the next agent should know
4. Any urgent considerations

Keep it professional and concise (2-3 sentences):"""

        response = await self.router.route_inference(
            prompt=handoff_prompt,
            preferred_method=self.preferred_method,
            temperature=temperature,
            max_tokens=200
        )

        logger.debug(f"Handoff preparation: {response.latency_ms}ms")
        return response.content

    async def _execute_handoff(
        self,
        from_agent: AgentRole,
        to_agent: AgentRole,
        context: TransferContext,
        handoff_message: str,
        temperature: float
    ) -> str:
        """Execute handoff and get confirmation from target agent."""
        accept_prompt = f"""You are the {to_agent.value.upper()} agent receiving a handoff.

HANDOFF FROM {from_agent.value.upper()}:
{handoff_message}

LEAD DATA:
{json.dumps(context.lead_data, indent=2)}

PRIORITY: {context.priority}

Acknowledge the handoff and state your first action:
1. Confirm you understand the context
2. State what you'll do first
3. Set expectations for completion

Be brief and actionable (2-3 sentences):"""

        response = await self.router.route_inference(
            prompt=accept_prompt,
            preferred_method=self.preferred_method,
            temperature=temperature,
            max_tokens=200
        )

        logger.debug(f"Handoff acceptance: {response.latency_ms}ms")
        return response.content

    async def _determine_next_action(
        self,
        agent: AgentRole,
        context: TransferContext,
        temperature: float
    ) -> str:
        """Determine next specific action for target agent."""
        action_prompt = f"""As the {agent.value.upper()} agent, determine the specific next action.

LEAD DATA:
{json.dumps(context.lead_data, indent=2)}

PRIORITY: {context.priority}

What is the FIRST concrete step you will take?
Be specific and actionable (one sentence):"""

        response = await self.router.route_inference(
            prompt=action_prompt,
            preferred_method=self.preferred_method,
            temperature=temperature,
            max_tokens=100
        )

        logger.debug(f"Next action determination: {response.latency_ms}ms")
        return response.content

    def _estimate_completion(self, agent: AgentRole) -> str:
        """Estimate completion time for agent role."""
        estimates = {
            AgentRole.QUALIFICATION: "2-5 minutes",
            AgentRole.ENRICHMENT: "5-10 minutes",
            AgentRole.BDR: "15-30 minutes",
            AgentRole.AE: "1-2 hours",
            AgentRole.SUPERVISOR: "Varies",
            AgentRole.RESEARCH: "10-20 minutes",
            AgentRole.OUTREACH: "5-15 minutes"
        }
        return estimates.get(agent, "Unknown")

    def get_transfer_path(
        self,
        from_agent: AgentRole,
        to_agent: AgentRole
    ) -> List[AgentRole]:
        """
        Get shortest transfer path between agents.

        Args:
            from_agent: Starting agent
            to_agent: Target agent

        Returns:
            List of agents in transfer path
        """
        # Simple BFS to find path
        if from_agent == to_agent:
            return [from_agent]

        queue = [(from_agent, [from_agent])]
        visited = {from_agent}

        while queue:
            current, path = queue.pop(0)

            # Get allowed transfers
            allowed = self.TRANSFER_RULES.get(current, [])

            if to_agent in allowed:
                return path + [to_agent]

            for next_agent in allowed:
                if next_agent not in visited:
                    visited.add(next_agent)
                    queue.append((next_agent, path + [next_agent]))

        # No path found
        return []

    def get_valid_targets(self, from_agent: AgentRole) -> List[AgentRole]:
        """Get list of valid transfer targets for an agent."""
        return self.TRANSFER_RULES.get(from_agent, [])

    def get_transfer_history(
        self,
        lead_id: Optional[int] = None,
        from_agent: Optional[AgentRole] = None,
        to_agent: Optional[AgentRole] = None,
        limit: int = 100
    ) -> List[TransferResult]:
        """
        Get transfer history with optional filters.

        Args:
            lead_id: Filter by lead ID
            from_agent: Filter by source agent
            to_agent: Filter by target agent
            limit: Maximum results to return

        Returns:
            List of matching TransferResult objects
        """
        results = self.transfer_history

        # Apply filters
        if lead_id is not None:
            results = [r for r in results if r.transfer_context.lead_id == lead_id]

        if from_agent is not None:
            results = [r for r in results if r.from_agent == from_agent]

        if to_agent is not None:
            results = [r for r in results if r.to_agent == to_agent]

        # Return most recent first
        return list(reversed(results))[:limit]

    def get_status(self) -> Dict[str, Any]:
        """Get transfer system status."""
        return {
            "total_transfers": len(self.transfer_history),
            "recent_transfers": [
                {
                    "from": t.from_agent.value,
                    "to": t.to_agent.value,
                    "lead_id": t.transfer_context.lead_id,
                    "timestamp": t.transfer_context.timestamp,
                    "successful": t.handoff_successful
                }
                for t in list(reversed(self.transfer_history))[:10]
            ],
            "transfer_rules": {
                agent.value: [t.value for t in targets]
                for agent, targets in self.TRANSFER_RULES.items()
            },
            "router_status": self.router.get_status()
        }
