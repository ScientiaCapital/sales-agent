"""
Lead Prediction Agent - "Why Call Now" Reasoning Generator
==========================================================
LangGraph agent that generates personalized "why call now" reasoning
for top leads. Uses OpenRouter for access to various LLMs (Qwen, DeepSeek, Mixtral).

Only runs for top-N leads to control costs - algorithmic ranking handles the rest.

Flow:
    ┌─────────────┐
    │ get_context │ ─── Fetch lead data + recent signals
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │  generate   │ ─── LLM generates "why call now" reasoning
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │    save     │ ─── Update prediction_why_now in Supabase
    └─────────────┘

Author: Claude + Tim
Date: Dec 3, 2025
"""

import os
import time
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from dotenv import load_dotenv
load_dotenv()

logger = logging.getLogger(__name__)


# ============================================================================
# Output Schemas
# ============================================================================

class WhyNowResult(BaseModel):
    """Result from why-now generation for a single lead."""
    company_id: str
    company_name: str
    why_now: str
    confidence: float
    processing_time_ms: int


class MorningBriefingResult(BaseModel):
    """Result from morning briefing generation."""
    generated_at: str
    top_leads: List[Dict[str, Any]]
    summary: str
    processing_time_ms: int


# ============================================================================
# Supabase Client
# ============================================================================
_supabase_client = None


def get_supabase_client():
    """Get or create Supabase client."""
    global _supabase_client

    if _supabase_client is None:
        try:
            from supabase import create_client
        except ImportError:
            raise RuntimeError("supabase package not installed")

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")

        if not url or not key:
            raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        _supabase_client = create_client(url, key)

    return _supabase_client


# ============================================================================
# OpenRouter LLM Integration
# ============================================================================

def get_openrouter_llm(model: str = "qwen/qwen-2.5-72b-instruct"):
    """
    Get OpenRouter LLM client.

    Supported models:
    - qwen/qwen-2.5-72b-instruct (default, cost-effective)
    - deepseek/deepseek-chat (good for reasoning)
    - mistralai/mixtral-8x7b-instruct (fast)
    - meta-llama/llama-3.1-70b-instruct (balanced)

    Args:
        model: OpenRouter model ID

    Returns:
        LangChain ChatOpenAI configured for OpenRouter
    """
    from langchain_openai import ChatOpenAI

    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY must be set in .env")

    return ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        openai_api_base="https://openrouter.ai/api/v1",
        temperature=0.7,
        max_tokens=500,
        default_headers={
            "HTTP-Referer": "https://sales-agent.local",
            "X-Title": "Sales Agent Prediction Market",
        }
    )


# ============================================================================
# Lead Prediction Agent
# ============================================================================

class LeadPredictionAgent:
    """
    Generates 'why call now' reasoning for top leads.

    Uses OpenRouter for LLM access to cost-effective models.
    Only processes top-N leads (cost control).
    """

    def __init__(self, model: str = "qwen/qwen-2.5-72b-instruct"):
        """
        Initialize agent with specified model.

        Args:
            model: OpenRouter model ID
        """
        self.model_name = model
        self.llm = get_openrouter_llm(model)
        logger.info(f"LeadPredictionAgent initialized with model: {model}")

    async def generate_why_now(self, company: Dict[str, Any]) -> WhyNowResult:
        """
        Generate 1-2 sentence "why call now" reasoning for a lead.

        Uses company data, AI insights, and recent signals to craft
        a specific, timely reason to call.

        Args:
            company: Dict with company data from dim_companies

        Returns:
            WhyNowResult with reasoning
        """
        start_time = time.time()
        company_id = company.get('company_id', 'unknown')
        company_name = company.get('company_name', 'Unknown Company')

        # Build context from available data
        context_parts = []

        # Company story
        if company.get('ai_company_story'):
            context_parts.append(f"Company Story: {company['ai_company_story'][:500]}")

        # Personal hooks
        if company.get('ai_personal_hooks'):
            hooks = company['ai_personal_hooks']
            if isinstance(hooks, str):
                context_parts.append(f"Personal Hooks: {hooks[:300]}")
            elif isinstance(hooks, list):
                hook_text = ", ".join([h.get('detail', '') for h in hooks[:3]])
                context_parts.append(f"Personal Hooks: {hook_text}")

        # Pain points
        if company.get('ai_pain_points'):
            context_parts.append(f"Pain Points: {company['ai_pain_points'][:300]}")

        # OEM brands
        if company.get('oem_brands'):
            brands = company['oem_brands']
            if isinstance(brands, list):
                brands = ", ".join(brands)
            context_parts.append(f"OEM Brands: {brands}")

        # Location
        city = company.get('city', '')
        state = company.get('state', '')
        if city or state:
            context_parts.append(f"Location: {city}, {state}")

        # ICP score
        if company.get('icp_score'):
            context_parts.append(f"ICP Score: {company['icp_score']} ({company.get('icp_tier', 'N/A')})")

        # Prediction rank
        if company.get('prediction_rank'):
            context_parts.append(f"Prediction Rank: #{company['prediction_rank']}")

        context = "\n".join(context_parts) if context_parts else "No additional context available."

        # Create prompt
        prompt = f"""You are a sales strategist helping a BDR prepare for their morning calls.

Company: {company_name}
Context:
{context}

Based on this information, write 1-2 sentences explaining WHY the BDR should call this lead NOW (today).
Focus on:
- Specific, timely reasons (not generic platitudes)
- Mentioning something personal or company-specific
- Creating urgency without being pushy

Format: Start with "Call because..." and be specific.

Your "why call now" reasoning:"""

        try:
            # Call LLM
            response = await self.llm.ainvoke(prompt)
            why_now = response.content.strip()

            # Clean up response
            if why_now.startswith('"') and why_now.endswith('"'):
                why_now = why_now[1:-1]

            processing_time = int((time.time() - start_time) * 1000)

            return WhyNowResult(
                company_id=company_id,
                company_name=company_name,
                why_now=why_now,
                confidence=0.8,
                processing_time_ms=processing_time
            )

        except Exception as e:
            logger.error(f"Error generating why-now for {company_name}: {e}")
            processing_time = int((time.time() - start_time) * 1000)

            return WhyNowResult(
                company_id=company_id,
                company_name=company_name,
                why_now="Call because they're a strong ICP match and worth prioritizing today.",
                confidence=0.3,
                processing_time_ms=processing_time
            )

    async def generate_morning_briefing(
        self,
        top_n: int = 10
    ) -> MorningBriefingResult:
        """
        Generate morning briefing markdown for top leads.

        Queries top-N leads by prediction rank, generates why-now
        reasoning for each, and creates a formatted briefing.

        Args:
            top_n: Number of leads to include (default 10)

        Returns:
            MorningBriefingResult with formatted briefing
        """
        start_time = time.time()
        supabase = get_supabase_client()

        # Query top leads by prediction_rank
        result = supabase.table('dim_companies').select(
            'company_id, company_name, domain, phone, city, state, '
            'icp_score, icp_tier, prediction_score, prediction_rank, '
            'ai_company_story, ai_personal_hooks, ai_pain_points, oem_brands'
        ).not_.is_(
            'prediction_rank', 'null'
        ).order('prediction_rank', desc=False).limit(top_n).execute()

        leads = result.data or []

        if not leads:
            return MorningBriefingResult(
                generated_at=datetime.now().isoformat(),
                top_leads=[],
                summary="No leads available for morning briefing.",
                processing_time_ms=int((time.time() - start_time) * 1000)
            )

        # Generate why-now for each lead
        briefing_leads = []
        for lead in leads:
            why_now_result = await self.generate_why_now(lead)

            # Save to database
            try:
                supabase.table('dim_companies').update({
                    'prediction_why_now': why_now_result.why_now
                }).eq('company_id', lead['company_id']).execute()
            except Exception as e:
                logger.error(f"Error saving why-now for {lead['company_id']}: {e}")

            briefing_leads.append({
                'rank': lead.get('prediction_rank'),
                'company_name': lead.get('company_name'),
                'phone': lead.get('phone'),
                'location': f"{lead.get('city', '')}, {lead.get('state', '')}".strip(', '),
                'icp_tier': lead.get('icp_tier'),
                'prediction_score': lead.get('prediction_score'),
                'why_now': why_now_result.why_now
            })

        # Generate summary
        summary = self._format_briefing_markdown(briefing_leads)

        processing_time = int((time.time() - start_time) * 1000)

        return MorningBriefingResult(
            generated_at=datetime.now().isoformat(),
            top_leads=briefing_leads,
            summary=summary,
            processing_time_ms=processing_time
        )

    def _format_briefing_markdown(self, leads: List[Dict[str, Any]]) -> str:
        """Format leads into a markdown briefing."""
        lines = [
            f"# 🌅 Morning Briefing - {datetime.now().strftime('%B %d, %Y')}",
            "",
            f"## Top {len(leads)} Leads to Call Today",
            ""
        ]

        for lead in leads:
            lines.extend([
                f"### #{lead['rank']} - {lead['company_name']}",
                f"📞 {lead.get('phone', 'No phone')} | 📍 {lead.get('location', 'Unknown')}",
                f"🎯 {lead.get('icp_tier', 'N/A')} | Score: {lead.get('prediction_score', 0)}",
                "",
                f"**Why Call Now:** {lead.get('why_now', 'No reasoning available')}",
                "",
                "---",
                ""
            ])

        lines.append(f"*Generated at {datetime.now().strftime('%I:%M %p %Z')}*")

        return "\n".join(lines)


# ============================================================================
# Convenience Functions
# ============================================================================

async def generate_why_now_for_lead(company_id: str, model: str = "qwen/qwen-2.5-72b-instruct") -> Dict[str, Any]:
    """
    Generate why-now reasoning for a single lead.

    Convenience function for one-off generation.

    Args:
        company_id: UUID of the company
        model: OpenRouter model to use

    Returns:
        Dict with why_now and metadata
    """
    supabase = get_supabase_client()

    # Get company data
    result = supabase.table('dim_companies').select(
        'company_id, company_name, domain, phone, city, state, '
        'icp_score, icp_tier, prediction_score, prediction_rank, '
        'ai_company_story, ai_personal_hooks, ai_pain_points, oem_brands'
    ).eq('company_id', company_id).execute()

    if not result.data:
        return {"error": f"Company not found: {company_id}"}

    company = result.data[0]

    agent = LeadPredictionAgent(model=model)
    result = await agent.generate_why_now(company)

    # Save to database
    try:
        supabase.table('dim_companies').update({
            'prediction_why_now': result.why_now
        }).eq('company_id', company_id).execute()
    except Exception as e:
        logger.error(f"Error saving why-now: {e}")

    return {
        "company_id": result.company_id,
        "company_name": result.company_name,
        "why_now": result.why_now,
        "confidence": result.confidence,
        "processing_time_ms": result.processing_time_ms
    }
