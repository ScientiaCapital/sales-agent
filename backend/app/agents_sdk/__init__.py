"""
Agent SDK Integration Layer with Cost-Optimized Smart Routing

This package contains conversational agents that use intelligent LLM routing
to minimize costs while maintaining quality.

Architecture:
    - Smart Routing: CostOptimizedLLMProvider (mode="smart_router")
    - Simple queries → Gemini Flash ($0.00001/1K tokens)
    - Complex queries → Claude Haiku ($0.00025/1K tokens)
    - Cost Tracking: All calls logged to ai_cost_tracking table

Implemented Agents:
    - SR/BDR Agent: Sales rep conversational assistant
    - Pipeline Manager: Interactive license import orchestration
    - Customer Success Agent: Onboarding and support assistant

Usage:
    ```python
    from app.agents_sdk.agents import SRBDRAgent
    from app.models.database import SessionLocal

    db = SessionLocal()
    agent = SRBDRAgent(db=db)

    response = await agent.chat(
        message="What are my top 3 leads?",
        session_id="session_123",
        user_id="rep_456"
    )
    print(response)  # Automatically uses smart routing
    ```

Expected cost savings: 40-70% compared to using Claude for all queries.
"""

__version__ = "0.2.0"

from app.agents_sdk.agents import (
    SRBDRAgent,
    PipelineManagerAgent,
    CustomerSuccessAgent,
    BaseAgent,
    AgentConfig
)

__all__ = [
    "SRBDRAgent",
    "PipelineManagerAgent",
    "CustomerSuccessAgent",
    "BaseAgent",
    "AgentConfig",
]
