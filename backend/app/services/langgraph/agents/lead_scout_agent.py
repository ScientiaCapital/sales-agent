"""
LeadScoutAgent - Autonomous Lead Discovery and Prioritization

Finds and prioritizes leads from Supabase, generating "WHY call" recommendations.
Designed to run autonomously via Celery Beat every 30 minutes.

Architecture:
    1. Query Supabase → Get unenriched companies with domains
    2. For each company:
       a. Scrape website for signals (brands, services, ATL contacts)
       b. Score with QualificationAgent
       c. Generate "WHY call" reasoning
    3. Save recommendations back to Supabase

Flow:
    ┌─────────────┐
    │ fetch_leads │ ─── Query Supabase for unenriched companies
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │  research   │ ─── Scrape website + enrich contacts (parallel)
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │   score     │ ─── QualificationAgent ICP scoring
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │  explain    │ ─── Generate "WHY call" + opener
    └──────┬──────┘
           │
    ┌──────▼──────┐
    │    save     │ ─── Update Supabase with recommendations
    └─────────────┘

Usage:
    # Manual run
    python -c "
    import asyncio
    from app.services.langgraph.agents.lead_scout_agent import LeadScoutAgent

    async def run():
        scout = LeadScoutAgent()
        results = await scout.scout(limit=5)
        for r in results:
            print(f'{r[\"company_name\"]}: {r[\"priority\"]} - {r[\"why_call\"][:100]}...')

    asyncio.run(run())
    "

    # Via API
    POST /api/v1/langgraph/scout/run {"limit": 5}
"""

import os
import time
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from langchain_core.prompts import ChatPromptTemplate
from app.services.langchain_cerebras_compat import ChatCerebras
from langchain_anthropic import ChatAnthropic

from app.core.logging import setup_logging
from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.services.langgraph.tools.supabase_tools import (
    query_unenriched_leads,
    update_lead_recommendation,
    get_lead_details,
)

logger = setup_logging(__name__)


# ========== Output Schema ==========

class ScoutResult(BaseModel):
    """Result for a single scouted lead."""
    company_id: str
    company_name: str
    domain: Optional[str]
    icp_score: float
    priority: str  # HOT, WARM, COLD
    why_call: str
    recommended_opener: Optional[str]
    key_signals: List[str]
    best_contact: Optional[str]
    scouted_at: str


class ScoutBatchResult(BaseModel):
    """Result for a batch of scouted leads."""
    total_scouted: int
    hot_leads: int
    warm_leads: int
    cold_leads: int
    errors: List[str]
    results: List[ScoutResult]
    duration_ms: int


# ========== LeadScoutAgent ==========

class LeadScoutAgent:
    """
    Autonomous lead discovery agent.

    Queries Supabase for unenriched leads, researches them,
    generates "WHY call" recommendations, and saves back.
    """

    # Prompt for generating WHY call reasoning
    WHY_CALL_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert BDR (Business Development Representative) helping identify ideal HVAC/MEP service company prospects.

Given the company research data below, generate:
1. A compelling 2-3 sentence "WHY call this company" explanation for Tim's calling list
2. A natural conversation opener (15-20 words) that references something specific about the company
3. Key signals that make this a good prospect (bullet points)

Focus on:
- Company longevity and stability (years in business)
- Service offerings that indicate growth (maintenance plans, commercial services)
- OEM brands they service (Carrier, Trane, etc.)
- Geographic footprint (service areas)
- Team size and ATL contacts
- Certifications (NATE, ACCA, etc.)
- Reviews and reputation

Be specific and actionable. Tim needs to know exactly WHY this company is worth calling TODAY."""),
        ("human", """Company Research Data:
---
Name: {company_name}
Domain: {domain}
Industry: {industry}
Location: {city}, {state}
Phone: {phone}

ICP Score: {icp_score}/100
ICP Tier: {icp_tier}

OEM Brands: {oem_brands}
Service Areas: {service_areas}
Certifications: {certifications}
Events Attended: {events_attended}

Google Rating: {google_rating} ({google_review_count} reviews)

Existing AI Story: {ai_company_story}
Existing Hooks: {ai_personal_hooks}
---

Generate your analysis:""")
    ])

    def __init__(
        self,
        provider: str = "cerebras",
        model: Optional[str] = None,
        temperature: float = 0.3
    ):
        """
        Initialize LeadScoutAgent.

        Args:
            provider: LLM provider (cerebras, claude)
            model: Model ID (auto-selected if None)
            temperature: Generation temperature (0.3 for focused but creative)
        """
        self.provider = provider
        self.model = model or self._default_model(provider)
        self.temperature = temperature

        # Initialize LLM
        if provider == "cerebras":
            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                raise ValueError("CEREBRAS_API_KEY not set")
            self.llm = ChatCerebras(
                api_key=api_key,
                model=self.model,
                temperature=temperature,
                max_tokens=800
            )
        elif provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self.llm = ChatAnthropic(
                api_key=api_key,
                model=self.model,
                temperature=temperature,
                max_tokens=800
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Build chain
        self.chain = self.WHY_CALL_PROMPT | self.llm

        # Initialize qualification agent (for scoring)
        self.qualification_agent = QualificationAgent(
            provider=provider,
            model=self.model
        )

        logger.info(f"LeadScoutAgent initialized: provider={provider}, model={self.model}")

    def _default_model(self, provider: str) -> str:
        """Get default model for provider."""
        defaults = {
            "cerebras": "llama-3.3-70b",
            "claude": "claude-3-haiku-20240307"
        }
        return defaults.get(provider, "llama-3.3-70b")

    async def scout(
        self,
        limit: int = 10,
        require_domain: bool = True,
        icp_tier: Optional[str] = None
    ) -> ScoutBatchResult:
        """
        Scout a batch of leads.

        Args:
            limit: Maximum leads to scout (1-50)
            require_domain: Only scout leads with domains
            icp_tier: Filter by ICP tier (PLATINUM, GOLD, etc.)

        Returns:
            ScoutBatchResult with scouted leads and stats
        """
        start_time = time.time()
        results = []
        errors = []
        hot_count = 0
        warm_count = 0
        cold_count = 0

        logger.info(f"Starting scout run: limit={limit}, require_domain={require_domain}")

        try:
            # 1. Fetch leads from Supabase
            leads = query_unenriched_leads.invoke({
                'limit': limit,
                'require_domain': require_domain,
                'unenriched_only': True,
                'icp_tier': icp_tier
            })

            logger.info(f"Fetched {len(leads)} leads to scout")

            if not leads:
                return ScoutBatchResult(
                    total_scouted=0,
                    hot_leads=0,
                    warm_leads=0,
                    cold_leads=0,
                    errors=["No unenriched leads found"],
                    results=[],
                    duration_ms=int((time.time() - start_time) * 1000)
                )

            # 2. Scout each lead
            for lead in leads:
                try:
                    result = await self._scout_single_lead(lead)
                    results.append(result)

                    # Count by priority
                    if result.priority == "HOT":
                        hot_count += 1
                    elif result.priority == "WARM":
                        warm_count += 1
                    else:
                        cold_count += 1

                except Exception as e:
                    error_msg = f"Failed to scout {lead.get('company_name')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        except Exception as e:
            error_msg = f"Scout batch failed: {str(e)}"
            logger.error(error_msg)
            errors.append(error_msg)

        duration_ms = int((time.time() - start_time) * 1000)

        logger.info(
            f"Scout complete: {len(results)} scouted, "
            f"{hot_count} HOT, {warm_count} WARM, {cold_count} COLD, "
            f"{len(errors)} errors, {duration_ms}ms"
        )

        return ScoutBatchResult(
            total_scouted=len(results),
            hot_leads=hot_count,
            warm_leads=warm_count,
            cold_leads=cold_count,
            errors=errors,
            results=results,
            duration_ms=duration_ms
        )

    async def _scout_single_lead(self, lead: Dict[str, Any]) -> ScoutResult:
        """
        Scout a single lead.

        Args:
            lead: Lead data from Supabase

        Returns:
            ScoutResult with recommendation
        """
        company_id = lead.get('company_id')
        company_name = lead.get('company_name', 'Unknown')
        domain = lead.get('domain')

        logger.info(f"Scouting: {company_name} ({domain})")

        # 1. Score with QualificationAgent (includes website scraping)
        qual_result, latency_ms, metadata = await self.qualification_agent.qualify(
            company_name=company_name,
            company_website=f"https://{domain}" if domain else None,
            industry=lead.get('industry', 'HVAC')
        )

        icp_score = qual_result.qualification_score
        tier = qual_result.tier

        # 2. Determine priority from score
        if icp_score >= 75:
            priority = "HOT"
        elif icp_score >= 55:
            priority = "WARM"
        else:
            priority = "COLD"

        # 3. Generate WHY call reasoning
        why_call_response = await self.chain.ainvoke({
            'company_name': company_name,
            'domain': domain or 'N/A',
            'industry': lead.get('industry', 'HVAC'),
            'city': lead.get('city', 'N/A'),
            'state': lead.get('state', 'N/A'),
            'phone': lead.get('phone', 'N/A'),
            'icp_score': icp_score,
            'icp_tier': tier,
            'oem_brands': lead.get('oem_brands', 'N/A'),
            'service_areas': lead.get('service_areas', 'N/A'),
            'certifications': lead.get('certifications', 'N/A'),
            'events_attended': lead.get('events_attended', 'N/A'),
            'google_rating': lead.get('google_rating', 'N/A'),
            'google_review_count': lead.get('google_review_count', 0),
            'ai_company_story': lead.get('ai_company_story', 'N/A'),
            'ai_personal_hooks': lead.get('ai_personal_hooks', 'N/A')
        })

        # Parse response
        why_call_text = why_call_response.content if hasattr(why_call_response, 'content') else str(why_call_response)

        # Extract opener (look for quoted text or first line)
        opener = None
        lines = why_call_text.strip().split('\n')
        for line in lines:
            if 'opener' in line.lower() or line.startswith('"'):
                opener = line.strip('"').strip()
                break

        # Extract key signals
        key_signals = []
        for line in lines:
            if line.strip().startswith('-') or line.strip().startswith('•'):
                key_signals.append(line.strip().lstrip('-•').strip())

        # 4. Save to Supabase
        try:
            update_lead_recommendation.invoke({
                'company_id': company_id,
                'recommendation': why_call_text[:1000],  # Truncate to fit
                'recommended_opener': opener[:500] if opener else None,
                'priority': priority,
                'icp_score': icp_score
            })
            logger.info(f"Saved recommendation for {company_name}")
        except Exception as e:
            logger.error(f"Failed to save recommendation for {company_name}: {e}")

        return ScoutResult(
            company_id=company_id,
            company_name=company_name,
            domain=domain,
            icp_score=icp_score,
            priority=priority,
            why_call=why_call_text[:500],  # Truncate for result
            recommended_opener=opener,
            key_signals=key_signals[:5],  # Top 5 signals
            best_contact=qual_result.contact_quality if hasattr(qual_result, 'contact_quality') else None,
            scouted_at=datetime.now().isoformat()
        )

    async def scout_single(self, company_id: str) -> ScoutResult:
        """
        Scout a single company by ID.

        Args:
            company_id: UUID of company in Supabase

        Returns:
            ScoutResult with recommendation
        """
        lead = get_lead_details.invoke({
            'company_id': company_id,
            'include_contacts': False
        })
        return await self._scout_single_lead(lead)


# ========== Exports ==========

__all__ = [
    "LeadScoutAgent",
    "ScoutResult",
    "ScoutBatchResult"
]
