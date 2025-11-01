"""
QualificationAgent V2 - Enhanced with Unified Claude SDK

This version demonstrates how to integrate the Unified Claude SDK for
intelligent routing between Anthropic Claude and DeepSeek models.

Key Improvements:
- 11x cheaper input tokens with DeepSeek for simple qualifications
- Automatic routing based on lead complexity
- Prompt caching for 90% cost reduction on repeated system prompts
- Maintains backward compatibility with existing LangChain agents

Performance & Cost:
    Simple Lead (DeepSeek):
        - Latency: <2000ms
        - Cost: $0.0001 per lead (11x cheaper than Claude)

    Complex Lead (Claude):
        - Latency: <3000ms
        - Cost: $0.0011 per lead (high quality reasoning)

    With Prompt Caching (Claude):
        - First request: $0.0011
        - Subsequent: $0.0001 (90% savings)

Usage:
    ```python
    # Create agent
    agent = QualificationAgentV2()

    # Auto-routing based on complexity
    result = await agent.qualify_lead({
        "company_name": "Acme Corp",
        "industry": "SaaS",
        "company_size": "50-200"
    })

    # Force specific provider
    result = await agent.qualify_lead({...}, force_provider="anthropic")
    ```
"""

import time
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

from app.core.logging import setup_logging
from app.services.unified_claude_sdk import (
    get_unified_claude_client,
    Provider,
    Complexity
)

logger = setup_logging(__name__)


# ========== Models ==========

class LeadInput(BaseModel):
    """Input model for lead qualification."""
    company_name: str
    industry: Optional[str] = None
    company_size: Optional[str] = None
    website: Optional[str] = None
    contact_title: Optional[str] = None
    contact_email: Optional[str] = None
    revenue: Optional[str] = None
    location: Optional[str] = None


class LeadQualificationOutput(BaseModel):
    """Output model for lead qualification."""
    qualification_score: float = Field(ge=0, le=100)
    tier: Literal["hot", "warm", "cold", "unqualified"]
    reasoning: str
    fit_assessment: str
    contact_quality: str
    next_steps: str
    estimated_deal_size: str
    provider_used: str
    cost_usd: float
    latency_ms: int


# ========== Qualification Agent V2 ==========

class QualificationAgentV2:
    """
    Enhanced qualification agent using Unified Claude SDK.

    Features:
    - Intelligent routing between Claude and DeepSeek
    - Prompt caching for cost optimization
    - Complexity-based provider selection
    - Backward compatible with existing agents
    """

    # System prompt for qualification (this will be cached!)
    SYSTEM_PROMPT = """You are an expert B2B lead qualification agent for a sales automation platform.

Your task is to analyze leads and assign a qualification score from 0-100 based on:

1. **Company Fit** (40 points):
   - Industry alignment with our platform (SaaS, Tech, Professional Services)
   - Company size (50-500 employees ideal)
   - Revenue indicators
   - Market presence

2. **Contact Quality** (30 points):
   - Decision-maker level (C-suite, VP = high)
   - Department relevance (Sales, RevOps, Marketing)
   - Email validity

3. **Sales Potential** (30 points):
   - Budget indicators
   - Pain points alignment
   - Deal size potential
   - Urgency signals

Scoring Tiers:
- **Hot (80-100)**: Ideal fit, decision-maker, high budget, urgent need
- **Warm (60-79)**: Good fit, relevant contact, moderate budget
- **Cold (40-59)**: Partial fit, some potential, nurture needed
- **Unqualified (0-39)**: Poor fit, wrong contact, low potential

Respond in JSON format with:
{
  "qualification_score": <0-100>,
  "tier": "<hot|warm|cold|unqualified>",
  "reasoning": "<2-3 sentences explaining the score>",
  "fit_assessment": "<company fit evaluation>",
  "contact_quality": "<contact level assessment>",
  "next_steps": "<recommended action>",
  "estimated_deal_size": "<$X-$Y range>"
}"""

    def __init__(self):
        """Initialize qualification agent."""
        self.claude_client = None
        logger.info("QualificationAgentV2 initialized")

    async def initialize(self):
        """Initialize async resources."""
        self.claude_client = await get_unified_claude_client()
        logger.info("✅ QualificationAgentV2 connected to Unified Claude SDK")

    async def qualify_lead(
        self,
        lead_data: Dict[str, Any],
        force_provider: Optional[str] = None,
        enable_caching: bool = True
    ) -> LeadQualificationOutput:
        """
        Qualify a lead using intelligent routing.

        Args:
            lead_data: Lead information
            force_provider: Force specific provider ("anthropic" or "deepseek")
            enable_caching: Enable prompt caching (Claude only)

        Returns:
            LeadQualificationOutput with qualification results
        """
        if not self.claude_client:
            await self.initialize()

        start_time = time.time()

        try:
            # Parse input
            lead = LeadInput(**lead_data)

            # Detect complexity
            complexity = self._detect_complexity(lead)

            # Build prompt
            prompt = self._build_qualification_prompt(lead)

            # Determine provider
            provider = None
            if force_provider:
                provider = Provider.ANTHROPIC if force_provider == "anthropic" else Provider.DEEPSEEK

            logger.info(
                f"🔍 Qualifying lead: {lead.company_name} "
                f"(complexity={complexity.value}, provider={force_provider or 'auto'})"
            )

            # Generate response
            response = await self.claude_client.generate(
                prompt=prompt,
                system_prompt=self.SYSTEM_PROMPT,
                max_tokens=800,
                temperature=0.3,  # Lower temperature for consistent scoring
                complexity=complexity,
                provider=provider,
                enable_caching=enable_caching
            )

            # Parse JSON response
            import json
            result_json = self._extract_json(response.content)
            result_data = json.loads(result_json)

            # Calculate total latency
            total_latency_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"✅ Lead qualified: {lead.company_name} → {result_data['tier'].upper()} "
                f"(score={result_data['qualification_score']}, "
                f"provider={response.provider.value}, "
                f"cost=${response.cost_usd:.6f}, "
                f"latency={total_latency_ms}ms)"
            )

            # Return structured output
            return LeadQualificationOutput(
                qualification_score=result_data["qualification_score"],
                tier=result_data["tier"],
                reasoning=result_data["reasoning"],
                fit_assessment=result_data["fit_assessment"],
                contact_quality=result_data["contact_quality"],
                next_steps=result_data["next_steps"],
                estimated_deal_size=result_data["estimated_deal_size"],
                provider_used=response.provider.value,
                cost_usd=response.cost_usd,
                latency_ms=total_latency_ms
            )

        except Exception as e:
            logger.error(f"❌ Lead qualification failed: {e}")
            raise

    def _detect_complexity(self, lead: LeadInput) -> Complexity:
        """
        Detect lead complexity for routing.

        Args:
            lead: Lead data

        Returns:
            Complexity level
        """
        # Simple heuristic based on available data
        data_points = sum([
            bool(lead.industry),
            bool(lead.company_size),
            bool(lead.website),
            bool(lead.contact_title),
            bool(lead.contact_email),
            bool(lead.revenue),
            bool(lead.location)
        ])

        if data_points >= 5:
            # Rich data → Complex analysis → Use Claude
            return Complexity.COMPLEX
        elif data_points >= 3:
            # Moderate data → Medium analysis → Auto-route
            return Complexity.MEDIUM
        else:
            # Limited data → Simple scoring → Use DeepSeek
            return Complexity.SIMPLE

    def _build_qualification_prompt(self, lead: LeadInput) -> str:
        """
        Build qualification prompt from lead data.

        Args:
            lead: Lead data

        Returns:
            Formatted prompt
        """
        prompt_parts = [f"**Company Name**: {lead.company_name}"]

        if lead.industry:
            prompt_parts.append(f"**Industry**: {lead.industry}")
        if lead.company_size:
            prompt_parts.append(f"**Company Size**: {lead.company_size}")
        if lead.website:
            prompt_parts.append(f"**Website**: {lead.website}")
        if lead.contact_title:
            prompt_parts.append(f"**Contact Title**: {lead.contact_title}")
        if lead.contact_email:
            prompt_parts.append(f"**Contact Email**: {lead.contact_email}")
        if lead.revenue:
            prompt_parts.append(f"**Revenue**: {lead.revenue}")
        if lead.location:
            prompt_parts.append(f"**Location**: {lead.location}")

        prompt = "Analyze and qualify this lead:\n\n" + "\n".join(prompt_parts)
        prompt += "\n\nProvide qualification analysis in JSON format."

        return prompt

    def _extract_json(self, text: str) -> str:
        """
        Extract JSON from markdown code blocks or raw text.

        Args:
            text: Response text

        Returns:
            JSON string
        """
        import re

        # Try to find JSON in code blocks
        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            return json_match.group(1)

        # Try to find raw JSON
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            return json_match.group(0)

        raise ValueError("No JSON found in response")

    async def get_stats(self) -> Dict[str, Any]:
        """
        Get agent statistics.

        Returns:
            Statistics from Unified Claude SDK
        """
        if not self.claude_client:
            await self.initialize()

        return self.claude_client.get_stats()


# ========== Example Usage ==========

async def example_usage():
    """Example usage of QualificationAgentV2."""

    # Initialize agent
    agent = QualificationAgentV2()
    await agent.initialize()

    # Example 1: Simple lead (will use DeepSeek - cheap!)
    simple_lead = {
        "company_name": "Small Startup Inc",
        "industry": "SaaS"
    }
    result = await agent.qualify_lead(simple_lead)
    print(f"Simple Lead: {result.tier} (${result.cost_usd:.6f}, {result.latency_ms}ms)")

    # Example 2: Complex lead (will use Claude - quality!)
    complex_lead = {
        "company_name": "Enterprise Corp",
        "industry": "Enterprise SaaS",
        "company_size": "500-1000",
        "website": "https://enterprise.com",
        "contact_title": "VP of Sales",
        "contact_email": "vp@enterprise.com",
        "revenue": "$50M-$100M",
        "location": "San Francisco, CA"
    }
    result = await agent.qualify_lead(complex_lead)
    print(f"Complex Lead: {result.tier} (${result.cost_usd:.6f}, {result.latency_ms}ms)")

    # Example 3: Force DeepSeek for cost optimization
    result = await agent.qualify_lead(complex_lead, force_provider="deepseek")
    print(f"Forced DeepSeek: {result.tier} (${result.cost_usd:.6f}, {result.latency_ms}ms)")

    # Get statistics
    stats = await agent.get_stats()
    print(f"\nAgent Stats: {stats}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(example_usage())
