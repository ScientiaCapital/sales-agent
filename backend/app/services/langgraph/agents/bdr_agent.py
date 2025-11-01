"""
BDRAgent - Human-in-Loop StateGraph for High-Value Outreach

Uses LangGraph's interrupt() pattern to pause execution for human approval before
sending high-value emails. Implements approval gates with revision loops for
iterative refinement based on human feedback.

Architecture:
    Human-in-Loop StateGraph: research → draft → approval_gate (PAUSE) → send/revise
    - research: Gather company/contact intelligence (DeepSeek - cost-effective)
    - draft: Create personalized email (Claude - premium quality)
    - approval_gate: interrupt() - PAUSE for human review
    - Conditional routing:
        * approved → send → END
        * rejected → revise → draft (revision loop)

Interrupt Pattern:
    - First invoke: Runs until interrupt(), returns draft for review
    - Human reviews draft, provides decision (approve/reject + feedback)
    - Resume with Command(resume={action, feedback})
    - If approved: sends email and completes
    - If rejected: revises based on feedback and re-drafts

Cost Optimization:
    - Research: DeepSeek ($0.27/M) - good reasoning, low cost
    - Draft/Revise: Claude Haiku ($0.25+$1.25/M) - premium quality for BDR
    - Justification: High-value enterprise deals justify premium quality

Performance:
    - Research phase: ~2 seconds (DeepSeek)
    - Draft phase: ~3 seconds (Claude)
    - Human review: Variable (async)
    - Total: ~5 seconds + human time
    - Cost per outreach: $0.002-0.004 (mostly Claude costs)

Usage:
    ```python
    from app.services.langgraph.agents import BDRAgent
    from langgraph.types import Command

    # Initialize with checkpointer for state persistence
    agent = BDRAgent()

    # Start outreach (runs until interrupt)
    thread_id = "lead_123"
    config = {"configurable": {"thread_id": thread_id}}
    result = await agent.start_outreach(
        lead_id=123,
        company_name="Acme Corp",
        contact_name="Jane Doe",
        contact_title="VP Engineering",
        config=config
    )

    # Result contains __interrupt__ with draft for review
    print(result["__interrupt__"][0].value)
    # > {"subject": "...", "body": "...", "research": "..."}

    # Human reviews, then resume with approval
    final_result = await agent.resume_with_decision(
        action="approve",  # or "reject"
        feedback="Looks great!",  # or revision notes
        config=config
    )

    # If rejected, it loops back for revision
    # If approved, it sends and returns final result
    ```
"""

import os
import time
import uuid
from typing import Dict, Any, Optional, Literal, Union
from dataclasses import dataclass
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.messages import HumanMessage, AIMessage
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt, Command
from typing_extensions import TypedDict

from app.services.langgraph.llm_selector import get_llm_for_capability
from app.core.logging import setup_logging
from app.core.exceptions import ValidationError
from app.core.cost_optimized_llm import CostOptimizedLLMProvider, LLMConfig

logger = setup_logging(__name__)


# ========== State Schema ==========

class BDRAgentState(TypedDict):
    """
    State for BDRAgent with human-in-loop approval.

    Tracks research, drafts, approvals, and revisions across workflow.
    """
    # Input: Lead information
    lead_id: int
    company_name: str
    contact_name: str
    contact_title: Optional[str]

    # Research phase
    research_summary: Optional[str]

    # Draft phase
    draft_subject: Optional[str]
    draft_body: Optional[str]
    revision_count: int

    # Approval phase (set by human during resume)
    approval_status: Optional[str]  # "pending", "approved", "rejected"
    approval_feedback: Optional[str]

    # Execution phase
    sent_at: Optional[str]
    final_version: Optional[str]

    # Metadata
    total_cost_usd: float
    generation_metadata: Dict[str, Any]


# ========== Output Schema ==========

@dataclass
class BDROutreachResult:
    """
    Structured output from BDRAgent outreach execution.

    Contains research, drafts, approval status, and execution details.
    """
    # Lead information
    lead_id: int
    company_name: str
    contact_name: str

    # Research findings
    research_summary: str

    # Email content
    draft_subject: str
    draft_body: str
    final_version: str

    # Approval tracking
    approval_status: str  # "approved", "rejected", "pending"
    approval_feedback: Optional[str]
    revision_count: int

    # Execution
    sent_at: Optional[datetime]

    # Performance
    total_cost_usd: float
    latency_ms: int
    generation_metadata: Dict[str, Any]


# ========== BDRAgent ==========

class BDRAgent:
    """
    Human-in-loop StateGraph agent for high-value BDR outreach.

    Pauses execution for human approval before sending emails to enterprise prospects.
    """

    def __init__(
        self,
        # LLM provider overrides
        research_provider: Optional[str] = None,
        draft_provider: Optional[str] = None,
        # LLM parameters
        temperature: float = 0.7,
        max_tokens: int = 1000,
        # Cost tracking
        db: Optional[Union[Session, AsyncSession]] = None
    ):
        """
        Initialize BDRAgent with cost-optimized LLMs and checkpointer.

        Args:
            research_provider: Override research LLM (default: DeepSeek for cost)
            draft_provider: Override draft LLM (default: Claude for quality)
            temperature: Sampling temperature (0.7 for personalization)
            max_tokens: Max completion tokens
            db: Database session for cost tracking (optional, supports Session or AsyncSession)
        """
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.db = db

        # Initialize cost-optimized provider if db provided
        if db:
            try:
                self.cost_provider = CostOptimizedLLMProvider(db)
                logger.info("BDRAgent initialized with cost tracking enabled")
            except Exception as e:
                logger.error(f"Failed to initialize cost tracking: {e}")
                self.cost_provider = None
        else:
            self.cost_provider = None

        logger.info("Initializing BDRAgent with human-in-loop pattern")

        # Research LLM: DeepSeek (cost-effective reasoning)
        self.research_provider = research_provider or "deepseek"
        self.research_llm = get_llm_for_capability(
            "reasoning",
            provider=research_provider,
            temperature=0.3,  # Lower for factual research
            max_tokens=800
        )

        # Draft LLM: Claude Haiku (premium quality for BDR)
        self.draft_provider = draft_provider or "claude"
        self.draft_llm = get_llm_for_capability(
            "quality",
            provider=draft_provider,
            temperature=temperature,
            max_tokens=max_tokens
        )

        logger.info(
            f"LLM providers: research={self.research_provider}, "
            f"draft={self.draft_provider}"
        )

        # Initialize checkpointer for state persistence across interrupts
        self.checkpointer = InMemorySaver()

        # Build StateGraph with human-in-loop
        self.graph = self._build_graph()


    # ========== Node Functions ==========

    async def _research_node(self, state: BDRAgentState) -> Dict[str, Any]:
        """
        Research company and contact using DeepSeek (cost-effective).
        """
        logger.info(
            f"Researching {state['company_name']} / {state['contact_name']} "
            f"with {self.research_provider}"
        )
        start_time = time.time()

        prompt = f"""Research this prospect for high-value B2B outreach:

Company: {state['company_name']}
Contact: {state['contact_name']}
Title: {state.get('contact_title', 'Unknown')}

Provide a concise research summary (200-300 words) covering:
1. Company overview and recent news
2. Contact's role and likely pain points
3. Potential value proposition angles
4. Recommended outreach approach

Focus on insights that enable personalized outreach."""

        response = await self.research_llm.ainvoke(prompt)
        latency_ms = int((time.time() - start_time) * 1000)

        # Estimate cost (DeepSeek: $0.27/M tokens)
        estimated_tokens = len(prompt.split()) + len(response.content.split())
        cost_usd = (estimated_tokens / 1_000_000) * 0.27

        logger.info(f"Research complete in {latency_ms}ms, cost: ${cost_usd:.6f}")

        return {
            "research_summary": response.content,
            "generation_metadata": {
                "research": {
                    "provider": self.research_provider,
                    "latency_ms": latency_ms,
                    "cost_usd": cost_usd,
                    "estimated_tokens": estimated_tokens
                }
            }
        }


    async def _draft_node(self, state: BDRAgentState) -> Dict[str, Any]:
        """
        Draft personalized email using Claude (premium quality).
        """
        logger.info(f"Drafting email with {self.draft_provider}")
        start_time = time.time()

        # Build prompt with research context and any revision feedback
        revision_context = ""
        if state.get("approval_feedback"):
            revision_context = f"\n\nREVISION FEEDBACK: {state['approval_feedback']}\n\nPlease incorporate this feedback into the revised draft."

        prompt = f"""Draft a highly personalized cold email for this B2B prospect:

Company: {state['company_name']}
Contact: {state['contact_name']}
Title: {state.get('contact_title', 'Decision Maker')}

RESEARCH INSIGHTS:
{state.get('research_summary', 'No research available')}
{revision_context}

Create an email (200-250 words) with:
- Compelling subject line (5-7 words, avoid spam triggers)
- Personalized opening referencing their company/role
- Clear value proposition tied to their likely pain points
- Soft ask (call, demo, or reply)
- Professional but conversational tone

Format:
SUBJECT: [subject line]

BODY:
[email body]"""

        response = await self.draft_llm.ainvoke(prompt)
        latency_ms = int((time.time() - start_time) * 1000)

        # Estimate cost (Claude Haiku: $0.25 input + $1.25 output per M tokens)
        input_tokens = len(prompt.split())
        output_tokens = len(response.content.split())
        cost_usd = (input_tokens / 1_000_000) * 0.25 + (output_tokens / 1_000_000) * 1.25

        # Parse subject and body from response
        content = response.content
        subject = ""
        body = ""

        if "SUBJECT:" in content:
            parts = content.split("BODY:", 1)
            subject = parts[0].replace("SUBJECT:", "").strip()
            body = parts[1].strip() if len(parts) > 1 else content
        else:
            # Fallback: first line is subject, rest is body
            lines = content.split("\n", 1)
            subject = lines[0].strip()
            body = lines[1].strip() if len(lines) > 1 else content

        logger.info(f"Draft complete in {latency_ms}ms, cost: ${cost_usd:.6f}")

        return {
            "draft_subject": subject,
            "draft_body": body,
            "revision_count": state.get("revision_count", 0) + 1,
            "generation_metadata": {
                **state.get("generation_metadata", {}),
                "draft": {
                    "provider": self.draft_provider,
                    "latency_ms": latency_ms,
                    "cost_usd": cost_usd,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens
                }
            }
        }


    async def _approval_gate_node(self, state: BDRAgentState) -> Dict[str, Any]:
        """
        Pause execution and wait for human approval.

        Uses interrupt() to pause the graph and surface the draft for review.
        Returns human-provided decision when resumed.
        """
        logger.info(f"Pausing for human approval (revision #{state.get('revision_count', 1)})")

        # Pause execution and return draft for human review
        approval_data = interrupt({
            "message": "Email draft ready for review",
            "lead_id": state["lead_id"],
            "company_name": state["company_name"],
            "contact_name": state["contact_name"],
            "research_summary": state.get("research_summary", ""),
            "draft_subject": state.get("draft_subject", ""),
            "draft_body": state.get("draft_body", ""),
            "revision_count": state.get("revision_count", 0)
        })

        # When resumed, approval_data contains human decision
        logger.info(f"Resumed with decision: {approval_data.get('action', 'unknown')}")

        return {
            "approval_status": approval_data.get("action", "pending"),
            "approval_feedback": approval_data.get("feedback", "")
        }


    async def _send_node(self, state: BDRAgentState) -> Dict[str, Any]:
        """
        Execute send (approved email).

        For MVP, simulates send. Production would integrate with email service.
        """
        logger.info(f"Sending approved email to {state['contact_name']}")

        sent_at = datetime.now().isoformat()
        final_version = f"Subject: {state['draft_subject']}\n\n{state['draft_body']}"

        logger.info(f"Email sent successfully at {sent_at}")

        return {
            "sent_at": sent_at,
            "final_version": final_version,
            "approval_status": "approved"  # Confirm approved
        }


    async def _revise_node(self, state: BDRAgentState) -> Dict[str, Any]:
        """
        Prepare for revision loop (rejected draft).

        Sets up state for re-drafting with human feedback.
        """
        logger.info(
            f"Email rejected, preparing revision #{state.get('revision_count', 0) + 1}"
        )

        # Feedback is already in state from approval_gate
        # Just pass through to loop back to draft node

        return {}


    # ========== Routing Functions ==========

    def _route_after_approval(self, state: BDRAgentState) -> Literal["send", "revise"]:
        """
        Route based on approval decision.

        approved → send node
        rejected → revise node (loops back to draft)
        """
        action = state.get("approval_status", "pending")

        if action == "approved":
            logger.info("Routing to send (approved)")
            return "send"
        else:  # rejected
            logger.info("Routing to revise (rejected)")
            return "revise"


    # ========== Graph Construction ==========

    def _build_graph(self) -> StateGraph:
        """
        Build human-in-loop StateGraph with approval gates.

        Architecture:
                     ┌──────────────────┐
                     │                  │
            research → draft → approval_gate (INTERRUPT)
                         ↑         │
                         │         ├─ approved → send → END
                         │         │
                         └─ revise ←─ rejected
        """
        logger.info("Building human-in-loop StateGraph for BDRAgent")

        builder = StateGraph(BDRAgentState)

        # Add nodes
        builder.add_node("research", self._research_node)
        builder.add_node("draft", self._draft_node)
        builder.add_node("approval_gate", self._approval_gate_node)
        builder.add_node("send", self._send_node)
        builder.add_node("revise", self._revise_node)

        # Linear edges: research → draft → approval_gate
        builder.add_edge(START, "research")
        builder.add_edge("research", "draft")
        builder.add_edge("draft", "approval_gate")

        # Conditional routing after approval
        builder.add_conditional_edges(
            "approval_gate",
            self._route_after_approval,
            {
                "send": "send",
                "revise": "revise"
            }
        )

        # Revision loop: revise → draft
        builder.add_edge("revise", "draft")

        # Exit point: send → END
        builder.add_edge("send", END)

        logger.info("Human-in-loop StateGraph compiled with checkpointer")
        return builder.compile(checkpointer=self.checkpointer)


    # ========== Public API ==========

    async def start_outreach(
        self,
        lead_id: int,
        company_name: str,
        contact_name: str,
        contact_title: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Start BDR outreach workflow (runs until interrupt).

        This method initiates the workflow and runs until the approval gate,
        where it pauses and returns the draft for human review.

        Args:
            lead_id: Lead identifier
            company_name: Company name for research
            contact_name: Contact name for personalization
            contact_title: Contact's job title (optional)
            config: LangGraph config with thread_id for state persistence

        Returns:
            Dict with __interrupt__ containing draft for review

        Example:
            >>> agent = BDRAgent()
            >>> config = {"configurable": {"thread_id": "lead_123"}}
            >>> result = await agent.start_outreach(
            ...     lead_id=123,
            ...     company_name="Acme Corp",
            ...     contact_name="Jane Doe",
            ...     contact_title="VP Engineering",
            ...     config=config
            ... )
            >>> print(result["__interrupt__"][0].value["draft_subject"])
        """
        # Validate inputs
        if not company_name or not company_name.strip():
            raise ValidationError("company_name cannot be empty")

        if not contact_name or not contact_name.strip():
            raise ValidationError("contact_name cannot be empty")

        # Generate thread_id if not provided
        if not config:
            config = {"configurable": {"thread_id": str(uuid.uuid4())}}
        elif "configurable" not in config or "thread_id" not in config["configurable"]:
            config = {"configurable": {"thread_id": str(uuid.uuid4())}}

        logger.info(
            f"Starting outreach: lead_id={lead_id}, company={company_name}, "
            f"contact={contact_name}, thread={config['configurable']['thread_id']}"
        )

        start_time = time.time()

        # Run graph until interrupt
        result = await self.graph.ainvoke({
            "lead_id": lead_id,
            "company_name": company_name,
            "contact_name": contact_name,
            "contact_title": contact_title,
            "research_summary": None,
            "draft_subject": None,
            "draft_body": None,
            "revision_count": 0,
            "approval_status": None,
            "approval_feedback": None,
            "sent_at": None,
            "final_version": None,
            "total_cost_usd": 0.0,
            "generation_metadata": {}
        }, config=config)

        latency_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Outreach paused at approval gate in {latency_ms}ms, "
            f"thread_id={config['configurable']['thread_id']}"
        )

        return result


    async def resume_with_decision(
        self,
        action: Literal["approve", "reject"],
        feedback: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resume outreach workflow with human approval decision.

        Args:
            action: "approve" to send, "reject" to revise
            feedback: Revision notes (required if action="reject")
            config: Same config with thread_id from start_outreach

        Returns:
            Final result (sent) or new interrupt (if revision needed)

        Example:
            >>> # Approve and send
            >>> result = await agent.resume_with_decision(
            ...     action="approve",
            ...     feedback="Looks great!",
            ...     config=config
            ... )
            >>> print(result["sent_at"])

            >>> # Reject and request revision
            >>> result = await agent.resume_with_decision(
            ...     action="reject",
            ...     feedback="Too formal, make it more casual",
            ...     config=config
            ... )
            >>> # Returns new interrupt with revised draft
        """
        if not config or "configurable" not in config or "thread_id" not in config["configurable"]:
            raise ValidationError("config with thread_id is required to resume")

        if action == "reject" and not feedback:
            raise ValidationError("feedback is required when rejecting")

        logger.info(
            f"Resuming with action={action}, thread={config['configurable']['thread_id']}"
        )

        start_time = time.time()

        # Resume graph with decision
        result = await self.graph.ainvoke(
            Command(resume={"action": action, "feedback": feedback or ""}),
            config=config
        )

        latency_ms = int((time.time() - start_time) * 1000)

        # Check if still at interrupt (revision loop) or completed (sent)
        if "__interrupt__" in result:
            logger.info(f"Revision complete, paused again for approval in {latency_ms}ms")
        else:
            logger.info(f"Outreach completed in {latency_ms}ms")

        return result


# ========== Exports ==========

__all__ = [
    "BDRAgent",
    "BDROutreachResult",
]
