"""
GrowthAgent - Cyclic StateGraph for Multi-Touch Outreach Campaigns

Uses LangGraph's custom StateGraph with cyclic edges for iterative campaign
refinement. The agent analyzes performance, adjusts strategy, executes touches,
measures results, and loops until goal is met or max cycles reached.

Architecture:
    Cyclic StateGraph: analyze → strategize → execute → measure → [loop back]
    - analyze: Review past performance and learnings
    - strategize: Design next outreach touch based on analysis
    - execute: Record outreach in CRM (simulated for MVP)
    - measure: Evaluate success metrics and decide if goal met
    - Conditional edge: Loop back to analyze OR end

Cycle Termination:
    - Goal met: Campaign achieved success metric (meeting booked, reply received)
    - Max cycles: Safety limit to prevent infinite loops (default: 5)

LLM Providers:
    - cerebras (default): Ultra-fast (633ms), cheapest, great for high-volume
    - anthropic: Claude Haiku for complex strategy reasoning
    - openrouter: DeepSeek/Qwen/Yi/GLM for cost optimization

Performance:
    - Target: <30 seconds for 5-cycle campaign
    - Typical: 4 LLM calls per cycle × 5 cycles = 20 calls
    - Cost: $0.0015 (Cerebras) to $0.0045 (Claude) per campaign

Usage:
    ```python
    from app.services.langgraph.agents import GrowthAgent

    # Default (Cerebras - fast and cheap)
    agent = GrowthAgent()
    result = await agent.run_campaign(
        lead_id=123,
        goal="book_meeting",
        max_cycles=5
    )

    # Claude (best strategy reasoning)
    agent = GrowthAgent(provider="anthropic")
    result = await agent.run_campaign(lead_id=456, goal="get_reply")

    # DeepSeek (cost-optimized via OpenRouter)
    agent = GrowthAgent(
        provider="openrouter",
        model="deepseek/deepseek-chat"
    )
    result = await agent.run_campaign(lead_id=789, goal="book_demo")
    ```
"""

import os
import time
from typing import Dict, Any, List, Literal, Optional, Union
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.messages import HumanMessage, AIMessage
from langchain_anthropic import ChatAnthropic
from langchain_cerebras import ChatCerebras
from langgraph.graph import StateGraph, END

from app.services.langgraph.state_schemas import GrowthAgentState
from app.core.logging import setup_logging
from app.core.exceptions import ValidationError
from app.core.cost_optimized_llm import CostOptimizedLLMProvider, LLMConfig
from app.services.cost_tracking import get_cost_optimizer
# Lazy import to avoid circular dependency
# from app.services.langgraph.tools import get_transfer_tools

logger = setup_logging(__name__)


# ========== Output Schema ==========

@dataclass
class GrowthCampaignResult:
    """
    Structured output from GrowthAgent campaign execution.

    Contains campaign strategy, executed touches, and success metrics.
    """
    # Campaign execution summary
    lead_id: int
    goal: str
    goal_met: bool = False

    # Strategy and execution
    final_strategy: str = ""
    executed_touches: List[Dict[str, Any]] = field(default_factory=list)

    # Performance metrics
    cycle_count: int = 0
    response_rate: float = 0.0
    engagement_score: float = 0.0

    # Learnings accumulated
    learnings: List[str] = field(default_factory=list)

    # Performance tracking
    latency_ms: int = 0
    total_cost_usd: float = 0.0

    # Error tracking
    errors: List[str] = field(default_factory=list)


# ========== GrowthAgent ==========

class GrowthAgent:
    """
    Cyclic StateGraph agent for iterative multi-touch outreach campaigns.

    Patterns:
        - Custom StateGraph with 4 nodes + conditional cycle
        - Multi-provider LLM support (Cerebras, Claude, OpenRouter)
        - Cycle tracking and termination (goal_met or max_cycles)
        - State preservation across cycles via spread operator

    Performance:
        - 20-30 seconds for 5-cycle campaign
        - 4 LLM calls per cycle (analyze, strategize, execute, measure)
        - $0.0015-$0.0045 per campaign depending on provider
    """

    def __init__(
        self,
        model: str = "llama3.1-8b",
        provider: Literal["cerebras", "anthropic", "deepseek"] = "cerebras",
        temperature: float = 0.4,
        max_tokens: int = 500,
        track_costs: bool = True,
        db: Optional[Union[Session, AsyncSession]] = None
    ):
        """
        Initialize GrowthAgent with configurable LLM provider.

        Supported Providers:
            - cerebras (default): Ultra-fast, cheapest, great for scale ($0.000006/call)
            - anthropic: Claude Haiku for best strategy reasoning ($0.001743/call)
            - deepseek: Cost-optimized reasoning via Anthropic-compatible API ($0.00027/call)

        Args:
            model: Model ID (provider-specific)
            provider: LLM provider selection
            temperature: Sampling temperature (0.4 for creative strategies)
            max_tokens: Max completion tokens per call
            track_costs: Enable cost tracking to ai-cost-optimizer (default: True)
            db: Database session for cost tracking (optional, supports Session or AsyncSession)
        """
        self.model = model
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Cost tracking
        self.track_costs = track_costs
        self.cost_optimizer = None  # Lazy init on first use
        self.db = db

        # Initialize cost-optimized provider if db provided
        if db:
            try:
                self.cost_provider = CostOptimizedLLMProvider(db)
                logger.info("GrowthAgent initialized with cost tracking enabled")
            except Exception as e:
                logger.error(f"Failed to initialize cost tracking: {e}")
                self.cost_provider = None
        else:
            self.cost_provider = None

        # Initialize LLM based on provider
        if provider == "cerebras":
            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                raise ValueError("CEREBRAS_API_KEY environment variable not set")

            self.llm = ChatCerebras(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key
            )

        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            self.llm = ChatAnthropic(
                model=self.model if "claude" in self.model else "claude-3-5-haiku-20241022",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key
            )

        elif provider == "deepseek":
            # DeepSeek supports Anthropic-compatible API (no OpenAI dependency!)
            # https://api-docs.deepseek.com/guides/anthropic_api
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")
            
            self.llm = ChatAnthropic(
                model=self.model if "deepseek" in self.model else "deepseek-chat",
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
                base_url="https://api.deepseek.com"  # Anthropic-compatible endpoint
            )

        else:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Use 'cerebras', 'anthropic', or 'deepseek'"
            )

        # Build cyclic StateGraph
        self.graph = self._build_graph()

        logger.info(
            f"GrowthAgent initialized: provider={provider}, model={model}, "
            f"temperature={temperature}"
        )

    # ========== Node Functions ==========

    async def _analyze_node(self, state: GrowthAgentState) -> GrowthAgentState:
        """
        Node 1: Analyze current campaign situation and past performance.

        Updates:
            - Increments cycle_count
            - Adds analysis message to state
        """
        cycle_count = state.get("cycle_count", 0) + 1
        executed_touches = state.get("executed_touches", [])
        learnings = state.get("learnings", [])
        goal = state.get("metadata", {}).get("goal", "engagement")

        # Build analysis prompt
        prompt = f"""You are a growth hacking strategist analyzing a multi-touch outreach campaign.

**Goal**: {goal}
**Current Cycle**: {cycle_count}
**Touches Executed**: {len(executed_touches)}
**Past Learnings**: {', '.join(learnings) if learnings else 'None yet'}

**Previous Touches**:
{self._format_touches(executed_touches)}

**Task**: Analyze what's working and what needs adjustment. Consider:
1. Which touches got responses?
2. What patterns indicate success?
3. What should we try differently?

Provide a 2-3 sentence analysis."""

        # Call LLM
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        analysis = response.content

        logger.info(f"Cycle {cycle_count} - Analysis: {analysis[:100]}...")

        # Update state
        return {
            **state,
            "cycle_count": cycle_count,
            "messages": state.get("messages", []) + [response],
            "metadata": {
                **state.get("metadata", {}),
                "last_analysis": analysis
            }
        }

    async def _strategize_node(self, state: GrowthAgentState) -> GrowthAgentState:
        """
        Node 2: Design next outreach touch based on analysis.

        Updates:
            - Sets current_strategy
            - Updates outreach_plan
        """
        analysis = state.get("metadata", {}).get("last_analysis", "No analysis available")
        cycle_count = state.get("cycle_count", 1)
        goal = state.get("metadata", {}).get("goal", "engagement")
        learnings = state.get("learnings", [])

        # Build strategy prompt
        prompt = f"""Based on the analysis, design the next outreach touch for cycle {cycle_count}.

**Analysis**: {analysis}
**Goal**: {goal}
**Learnings**: {', '.join(learnings) if learnings else 'First touch - no learnings yet'}

**Task**: Design a specific outreach strategy. Include:
1. Touch type (email, LinkedIn, phone, etc.)
2. Key message/angle
3. Timing relative to previous touches
4. Expected outcome

Provide strategy in 2-3 sentences."""

        # Call LLM
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        strategy = response.content

        logger.info(f"Cycle {cycle_count} - Strategy: {strategy[:100]}...")

        # Update state
        return {
            **state,
            "current_strategy": strategy,
            "outreach_plan": {
                "cycle": cycle_count,
                "strategy": strategy,
                "created_at": time.time()
            },
            "messages": state.get("messages", []) + [response]
        }

    async def _execute_node(self, state: GrowthAgentState) -> GrowthAgentState:
        """
        Node 3: Execute the outreach touch (simulated for MVP).

        In production, this would:
        - Send actual email via SendGrid/Postmark
        - Post LinkedIn message via API
        - Update CRM with touch record

        For MVP, we simulate execution and record in state.

        Updates:
            - Adds to executed_touches list
        """
        current_strategy = state.get("current_strategy", "No strategy set")
        cycle_count = state.get("cycle_count", 1)
        lead_id = state.get("lead_id")

        # Simulate touch execution
        touch_record = {
            "cycle": cycle_count,
            "strategy": current_strategy,
            "executed_at": time.time(),
            "status": "sent",  # In production: "sent", "delivered", "bounced"
            "touch_type": "email"  # Simplified for MVP
        }

        logger.info(f"Cycle {cycle_count} - Executed touch: {touch_record['touch_type']}")

        # Call LLM to confirm execution
        prompt = f"""Touch executed for cycle {cycle_count}.

**Strategy**: {current_strategy}
**Status**: {touch_record['status']}

Confirm execution with a brief note about what was sent."""

        response = await self.llm.ainvoke([HumanMessage(content=prompt)])

        # Update state
        executed_touches = state.get("executed_touches", [])
        executed_touches.append(touch_record)

        return {
            **state,
            "executed_touches": executed_touches,
            "messages": state.get("messages", []) + [response]
        }

    async def _measure_node(self, state: GrowthAgentState) -> GrowthAgentState:
        """
        Node 4: Measure campaign success and decide if goal is met.

        In production, this would:
        - Check email open/click rates
        - Query CRM for responses
        - Calculate engagement metrics

        For MVP, we simulate metrics based on cycle count and touches.

        Updates:
            - Sets response_rate, engagement_score
            - Sets goal_met flag
            - Adds learnings for next cycle
        """
        cycle_count = state.get("cycle_count", 1)
        executed_touches = state.get("executed_touches", [])
        goal = state.get("metadata", {}).get("goal", "engagement")
        max_cycles = state.get("max_cycles", 5)

        # Simulate metrics (MVP - replace with real API calls in production)
        # Response rate increases with cycles (simulating warming up)
        response_rate = min(0.15 * cycle_count, 0.45)  # Cap at 45%
        engagement_score = min(0.20 * cycle_count, 0.60)  # Cap at 60%

        # Goal achievement logic
        goal_met = False
        if goal == "book_meeting" and engagement_score > 0.5:
            goal_met = True
        elif goal == "get_reply" and response_rate > 0.3:
            goal_met = True
        elif goal == "engagement" and engagement_score > 0.4:
            goal_met = True

        # Build measurement prompt
        prompt = f"""Measure campaign performance after cycle {cycle_count}.

**Metrics**:
- Response Rate: {response_rate:.1%}
- Engagement Score: {engagement_score:.1%}
- Touches Executed: {len(executed_touches)}
- Goal: {goal}
- Goal Met: {goal_met}

**Task**: Provide key learning from this cycle in 1 sentence."""

        # Call LLM for learning extraction
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        learning = response.content

        logger.info(
            f"Cycle {cycle_count} - Metrics: response={response_rate:.1%}, "
            f"engagement={engagement_score:.1%}, goal_met={goal_met}"
        )

        # Update state
        learnings = state.get("learnings", [])
        learnings.append(learning)

        return {
            **state,
            "response_rate": response_rate,
            "engagement_score": engagement_score,
            "goal_met": goal_met,
            "learnings": learnings,
            "next_action": "continue" if not goal_met and cycle_count < max_cycles else "complete",
            "messages": state.get("messages", []) + [response]
        }

    # ========== Conditional Routing ==========

    def _should_continue(self, state: GrowthAgentState) -> Literal["analyze", "end"]:
        """
        Conditional edge: Decide whether to continue cycling or end.

        Returns:
            "analyze": Loop back for another cycle
            "end": Terminate campaign
        """
        goal_met = state.get("goal_met", False)
        cycle_count = state.get("cycle_count", 0)
        max_cycles = state.get("max_cycles", 5)

        # Termination conditions
        if goal_met:
            logger.info(f"Campaign goal met after {cycle_count} cycles - ending")
            return "end"

        if cycle_count >= max_cycles:
            logger.info(f"Max cycles ({max_cycles}) reached - ending")
            return "end"

        # Continue cycling
        logger.info(f"Continuing to cycle {cycle_count + 1}")
        return "analyze"

    # ========== Graph Construction ==========

    def _build_graph(self) -> StateGraph:
        """
        Build cyclic StateGraph with 4 nodes and conditional loop.

        Graph structure:
            START → analyze → strategize → execute → measure → [conditional]
                      ↑                                           ↓
                      └───────── (if not done) ──────────────────┘
                                      ↓
                                  (if done) → END
        """
        builder = StateGraph(GrowthAgentState)

        # Add nodes
        builder.add_node("analyze", self._analyze_node)
        builder.add_node("strategize", self._strategize_node)
        builder.add_node("execute", self._execute_node)
        builder.add_node("measure", self._measure_node)

        # Linear edges within cycle
        builder.add_edge("analyze", "strategize")
        builder.add_edge("strategize", "execute")
        builder.add_edge("execute", "measure")

        # Conditional edge creates the cycle
        builder.add_conditional_edges(
            "measure",
            self._should_continue,
            {
                "analyze": "analyze",  # Loop back
                "end": END  # Terminate
            }
        )

        # Set entry point
        builder.set_entry_point("analyze")

        # Compile graph
        return builder.compile()

    # ========== Helper Methods ==========

    def _format_touches(self, touches: List[Dict[str, Any]]) -> str:
        """Format executed touches for prompt display."""
        if not touches:
            return "None yet"

        formatted = []
        for i, touch in enumerate(touches, 1):
            formatted.append(
                f"{i}. {touch.get('touch_type', 'unknown')} - "
                f"{touch.get('strategy', 'no strategy')[:50]}..."
            )
        return "\n".join(formatted)

    def _estimate_cost(self, cycle_count: int) -> float:
        """
        Estimate campaign cost based on cycles and provider.

        Args:
            cycle_count: Number of cycles executed

        Returns:
            Estimated cost in USD
        """
        # 4 LLM calls per cycle (analyze, strategize, execute, measure)
        # ~500 tokens input + ~200 tokens output per call
        tokens_per_cycle = (500 + 200) * 4  # 2800 tokens

        total_tokens = tokens_per_cycle * cycle_count

        # Provider-specific pricing
        if self.provider == "cerebras":
            cost = (total_tokens / 1_000_000) * 0.10  # $0.10/M tokens
        elif self.provider == "anthropic":
            # Haiku: $0.25 input + $1.25 output
            cost = ((total_tokens * 0.7) / 1_000_000) * 0.25 + \
                   ((total_tokens * 0.3) / 1_000_000) * 1.25
        elif self.provider == "deepseek":
            # DeepSeek: $0.27 input + $1.10 output per 1M tokens
            cost = ((total_tokens * 0.7) / 1_000_000) * 0.27 + \
                   ((total_tokens * 0.3) / 1_000_000) * 1.10
        else:
            cost = (total_tokens / 1_000_000) * 0.30

        return round(cost, 4)

    # ========== Public API ==========

    async def run_campaign(
        self,
        lead_id: int,
        goal: str = "engagement",
        max_cycles: int = 5
    ) -> GrowthCampaignResult:
        """
        Run multi-touch growth campaign with iterative refinement.

        Args:
            lead_id: Lead ID to run campaign for
            goal: Campaign goal ("book_meeting", "get_reply", "engagement")
            max_cycles: Maximum cycle iterations (default: 5)

        Returns:
            GrowthCampaignResult with campaign execution summary

        Raises:
            ValidationError: If invalid parameters provided

        Example:
            >>> agent = GrowthAgent()
            >>> result = await agent.run_campaign(
            ...     lead_id=123,
            ...     goal="book_meeting",
            ...     max_cycles=5
            ... )
            >>> print(f"Goal met: {result.goal_met} in {result.cycle_count} cycles")
        """
        # Validate input
        if lead_id <= 0:
            raise ValidationError("lead_id must be positive integer")

        if goal not in ["book_meeting", "get_reply", "engagement"]:
            raise ValidationError(
                f"Invalid goal: {goal}. "
                f"Use 'book_meeting', 'get_reply', or 'engagement'"
            )

        # Initialize state
        initial_state: GrowthAgentState = {
            "messages": [],
            "agent_type": "growth",
            "lead_id": lead_id,
            "cycle_count": 0,
            "max_cycles": max_cycles,
            "goal_met": False,
            "current_strategy": "",
            "outreach_plan": {},
            "executed_touches": [],
            "response_rate": 0.0,
            "engagement_score": 0.0,
            "next_action": "",
            "learnings": [],
            "metadata": {
                "goal": goal,
                "provider": self.provider,
                "model": self.model
            }
        }

        start_time = time.time()

        try:
            # Run cyclic graph
            final_state = await self.graph.ainvoke(initial_state)

            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            # Extract results
            result = GrowthCampaignResult(
                lead_id=lead_id,
                goal=goal,
                goal_met=final_state.get("goal_met", False),
                final_strategy=final_state.get("current_strategy", ""),
                executed_touches=final_state.get("executed_touches", []),
                cycle_count=final_state.get("cycle_count", 0),
                response_rate=final_state.get("response_rate", 0.0),
                engagement_score=final_state.get("engagement_score", 0.0),
                learnings=final_state.get("learnings", []),
                latency_ms=latency_ms,
                total_cost_usd=self._estimate_cost(final_state.get("cycle_count", 0))
            )

            logger.info(
                f"Campaign complete: lead_id={lead_id}, goal_met={result.goal_met}, "
                f"cycles={result.cycle_count}, latency={latency_ms}ms"
            )
            
            # Log cost to ai-cost-optimizer
            if self.track_costs:
                await self._log_campaign_cost(
                    lead_id=lead_id,
                    goal=goal,
                    cycle_count=result.cycle_count,
                    goal_met=result.goal_met,
                    latency_ms=latency_ms,
                    total_cost_usd=result.total_cost_usd
                )

            return result

        except Exception as e:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            logger.error(f"Campaign failed: {str(e)}", exc_info=True)

            return GrowthCampaignResult(
                lead_id=lead_id,
                goal=goal,
                goal_met=False,
                latency_ms=latency_ms,
                errors=[str(e)]
            )

    async def _log_campaign_cost(
        self,
        lead_id: int,
        goal: str,
        cycle_count: int,
        goal_met: bool,
        latency_ms: int,
        total_cost_usd: float
    ):
        """
        Log growth campaign cost to ai-cost-optimizer.

        Args:
            lead_id: Lead ID campaign was run for
            goal: Campaign goal
            cycle_count: Number of cycles executed
            goal_met: Whether goal was achieved
            latency_ms: Total execution time
            total_cost_usd: Total cost of campaign
        """
        if self.cost_optimizer is None:
            self.cost_optimizer = await get_cost_optimizer()

        if self.cost_optimizer is None:
            return  # Failed to initialize

        # Build prompt summary
        prompt = f"Growth campaign: lead_id={lead_id}, goal={goal}, max_cycles={cycle_count}"

        # Build response summary
        response = (
            f"Executed {cycle_count} cycles | "
            f"Goal: {goal} ({'✓ Met' if goal_met else '✗ Not met'}) | "
            f"Provider: {self.provider}"
        )

        # Estimate token counts (4 LLM calls per cycle)
        # ~500 input + ~200 output per call
        estimated_input_tokens = 500 * 4 * cycle_count
        estimated_output_tokens = 200 * 4 * cycle_count

        await self.cost_optimizer.log_llm_call(
            provider=self.provider,
            model=self.model,
            prompt=prompt,
            response=response,
            tokens_in=estimated_input_tokens,
            tokens_out=estimated_output_tokens,
            cost_usd=total_cost_usd,
            agent_name="growth",
            metadata={
                "lead_id": lead_id,
                "goal": goal,
                "goal_met": goal_met,
                "cycle_count": cycle_count,
                "latency_ms": latency_ms
            }
        )

        logger.debug(
            f"💰 Logged growth campaign cost: ${total_cost_usd:.6f} "
            f"({cycle_count} cycles, {latency_ms}ms)"
        )

    def get_transfer_tools(self):
        """
        Get agent transfer tools for growth workflows.

        Returns:
            List of transfer tools that growth agent can use
        """
        from app.services.langgraph.tools import get_transfer_tools
        return get_transfer_tools("growth")


# ========== Exports ==========

__all__ = [
    "GrowthAgent",
    "GrowthCampaignResult",
]
