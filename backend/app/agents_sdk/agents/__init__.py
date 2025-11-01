"""
Agent SDK Agents with Cost-Optimized Smart Routing.

This module contains 3 conversational agents that use intelligent LLM routing
to minimize costs while maintaining quality:

- SRBDRAgent: Sales rep assistant (smart routing for lead queries)
- PipelineManagerAgent: License import orchestrator (smart routing for pipeline operations)
- CustomerSuccessAgent: Onboarding and support assistant (smart routing for customer queries)

All agents use CostOptimizedLLMProvider with mode="smart_router" to automatically
select the best provider based on query complexity:
- Simple queries → Gemini Flash ($0.00001/1K tokens)
- Complex queries → Claude Haiku ($0.00025/1K tokens)

Expected cost savings: 40-70% compared to using Claude for all queries.
"""

from app.agents_sdk.agents.base_agent import BaseAgent, AgentConfig
from app.agents_sdk.agents.sr_bdr import SRBDRAgent
from app.agents_sdk.agents.pipeline_manager import PipelineManagerAgent
from app.agents_sdk.agents.cs_agent import CustomerSuccessAgent

__all__ = [
    "BaseAgent",
    "AgentConfig",
    "SRBDRAgent",
    "PipelineManagerAgent",
    "CustomerSuccessAgent",
]
