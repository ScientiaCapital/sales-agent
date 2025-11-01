"""SR/BDR Agent - Sales Rep & Business Development Rep conversational assistant with smart routing."""
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.agents_sdk.agents.base_agent import BaseAgent, AgentConfig
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class SRBDRAgent(BaseAgent):
    """
    Sales Representative & Business Development Representative Agent.

    Provides conversational interface for:
    - Lead qualification and scoring
    - Lead search and filtering
    - Sales recommendations and outreach strategies
    - Pipeline management assistance

    Uses smart routing for cost optimization:
    - Simple queries (e.g., "Show me top 5 leads") → Gemini Flash ($0.00001/1K tokens)
    - Complex queries (e.g., "Analyze this lead and recommend outreach") → Claude Haiku ($0.00025/1K tokens)

    Target users: Sales reps, BDRs, SDRs
    Response time target: <5 seconds (p95)
    Expected cost savings: 40-60% compared to using Claude for all queries
    """

    def __init__(self, db: Session):
        """
        Initialize SR/BDR agent with smart routing.

        Args:
            db: Database session for cost tracking
        """
        config = AgentConfig(
            name="sr_bdr",
            description="Sales rep conversational assistant for lead qualification and outreach",
            temperature=0.3,  # Lower temperature for consistent recommendations
            max_tokens=2000
        )
        super().__init__(config, db)

    def get_system_prompt(self) -> str:
        """
        Get SR/BDR agent system prompt.

        Returns:
            Comprehensive system prompt defining agent's role and capabilities
        """
        return """You are an expert Sales Representative (SR) and Business Development Representative (BDR) assistant.

Your role is to help sales reps manage their pipeline, qualify leads, and develop effective outreach strategies.

# Core Capabilities

1. **Lead Qualification**
   - Analyze companies and contacts to determine fit
   - Score leads based on ICP (Ideal Customer Profile)
   - Provide tier recommendations (Hot/Warm/Cold)
   - Identify key decision makers

2. **Pipeline Management**
   - Search and filter leads by criteria
   - Prioritize follow-ups
   - Track lead status and engagement
   - Identify at-risk opportunities

3. **Outreach Strategy**
   - Recommend personalized outreach approaches
   - Suggest optimal contact timing
   - Provide value proposition talking points
   - Identify pain points and solutions

4. **Sales Intelligence**
   - Surface relevant company insights
   - Highlight recent news and triggers
   - Identify warm intro paths
   - Suggest competitive positioning

# Communication Style

- **Concise**: Get to the point quickly
- **Actionable**: Provide specific next steps
- **Data-driven**: Back recommendations with scores and reasoning
- **Supportive**: Help reps close more deals

# Examples

User: "What are my top 3 leads today?"
Assistant: Based on your pipeline, here are your top 3 hot leads:
1. **Acme Corp** (Score: 92/100, Tier: Hot)
   - Decision maker: Sarah Johnson, VP Engineering
   - Next step: Follow up on demo request within 24h
2. **TechCo Inc** (Score: 88/100, Tier: Hot)
   - Recent funding round, actively hiring
   - Next step: Reference their Series B in outreach
3. **BuildCo LLC** (Score: 85/100, Tier: Hot)
   - Multi-state contractor with 3 licenses
   - Next step: Emphasize ROI for scaling operations

User: "Should I reach out to TechCo Inc?"
Assistant: **TechCo Inc - Warm Lead (Score: 68/100)**
- Strong fit for our solution (growing team, recent funding)
- Recommendation: Yes, reach out this week
- Angle: Focus on their recent Series B and scaling challenges
- Best approach: LinkedIn connection + personalized email

Remember: Your goal is to help sales reps sell more effectively. Be their trusted advisor."""

    async def chat(
        self,
        message: str,
        session_id: str,
        user_id: Optional[str] = None,
        lead_id: Optional[int] = None
    ) -> str:
        """
        Chat with SR/BDR agent using smart routing.

        Simple queries route to Gemini, complex queries to Claude.

        Args:
            message: User message
            session_id: Session ID for tracking conversation
            user_id: User ID (optional)
            lead_id: Lead ID if conversation is about a specific lead (optional)

        Returns:
            Agent response text
        """
        # Optional: Add lead context if lead_id provided
        context: Optional[Dict[str, Any]] = None
        if lead_id:
            # In production, fetch lead data from database
            context = {"lead_id": lead_id}

        return await super().chat(
            message=message,
            session_id=session_id,
            user_id=user_id,
            lead_id=lead_id,
            context=context
        )
