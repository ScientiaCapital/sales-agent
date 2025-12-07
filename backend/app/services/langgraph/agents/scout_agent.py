"""
ScoutAgent - Lead Discovery + Sales Intelligence (Consolidated)

Merges LeadScoutAgent + SalesIntelAgent into a unified pipeline:
1. Fetch unenriched companies from Supabase
2. Scrape website for signals (brands, services, contacts, personal hooks)
3. Extract sales intelligence (personal details, company story, pain points)
4. Generate "WHY call now" reasoning for BDR
5. Save enrichment data back to Supabase
6. Emit `company_enriched` event for RankingAgent

Schedule: Every 30 min
Event Trigger: `company_imported`
Emits: `company_enriched`

Architecture (per plan Part 1, Section 8.6):
- Session persistence via progress.txt and state.json
- Context-efficient: fetches minimal data, enriches incrementally
- Event-driven: emits company_enriched for downstream agents

Usage:
    ```python
    from app.services.langgraph.agents.scout_agent import ScoutAgent

    agent = ScoutAgent()
    result = await agent.run_cycle(limit=5)
    # Returns: {"processed": 5, "enriched": 4, "errors": 1, "event": "company_enriched"}
    ```
"""

import os
import time
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from pathlib import Path
from pydantic import BaseModel, Field

from langchain_core.prompts import ChatPromptTemplate
from langchain_cerebras import ChatCerebras
from langchain_anthropic import ChatAnthropic

from app.core.logging import setup_logging
from app.services.langgraph.tools.supabase_tools import (
    query_unenriched_leads,
    get_supabase,
)

logger = setup_logging(__name__)


# ========== Output Schemas ==========

class PersonalHook(BaseModel):
    """Personal detail for rapport building."""
    category: str = Field(description="Category: family, pets, hobbies, background, community")
    detail: str = Field(description="The specific detail")
    conversation_opener: str = Field(description="How to use in conversation")


class ScoutEnrichmentResult(BaseModel):
    """Result for a single enriched company."""
    company_id: str
    company_name: str
    domain: Optional[str]

    # Company intel
    company_story: Optional[str] = None
    years_in_business: Optional[int] = None
    company_values: List[str] = Field(default_factory=list)

    # Personal hooks (for rapport)
    personal_hooks: List[PersonalHook] = Field(default_factory=list)

    # Pain points and signals
    pain_points: List[str] = Field(default_factory=list)
    buying_signals: List[str] = Field(default_factory=list)

    # BDR outreach intel
    why_call: str
    recommended_opener: Optional[str] = None

    # Metadata
    enriched_at: str
    processing_time_ms: int


class ScoutCycleResult(BaseModel):
    """Result for a full scout cycle."""
    total_fetched: int
    total_enriched: int
    total_errors: int
    errors: List[str]
    results: List[ScoutEnrichmentResult]
    duration_ms: int
    event: str = "company_enriched"  # For event system


# ========== Agent Implementation ==========

class ScoutAgent:
    """
    Consolidated ScoutAgent: Website scraping + sales intelligence extraction.

    Combines:
    - LeadScoutAgent: Discovers unenriched leads, scrapes websites
    - SalesIntelAgent: Extracts personal hooks, company story, pain points

    Implements session persistence per plan Part 8.6:
    - progress.txt: Freeform progress notes
    - state.json: Structured state for multi-window workflows
    """

    # Consolidated prompt: Website scraping + intel extraction
    ENRICHMENT_PROMPT = ChatPromptTemplate.from_messages([
        ("system", """You are an expert BDR intelligence analyst for HVAC/MEP service companies.

Your job is to analyze website content and extract actionable sales intelligence.

CRITICAL FOCUS AREAS:

1. **Personal Hooks** (for rapport building):
   - Family mentions (wife, kids, pets with NAMES)
   - Hobbies (golf, fishing, sports teams)
   - Background story (how they started the business)
   - Community involvement (church, charity, volunteer)
   - Personal interests in their bio

2. **Company Story**:
   - When/why founded
   - Years in business
   - Core values (family-owned, customer-first, etc.)
   - Awards or certifications mentioned

3. **Pain Points** (what they might struggle with):
   - Based on their services and market positioning
   - Common HVAC industry challenges
   - Signs of growth (hiring, expansion) or struggle

4. **Buying Signals**:
   - Recent expansion or growth
   - New service offerings
   - Technology adoption mentions
   - Hiring activity

5. **WHY Call Now**:
   - 2-3 sentence compelling reason to call THIS company
   - Reference specific details (brands, longevity, service areas)
   - Focus on opportunity or pain point
   - Include a natural conversation opener (15-20 words)

RULES:
- DO reference SPECIFIC personal details (their dogs' names, their golf game, etc.)
- DO NOT use generic phrases like "I noticed you're in HVAC"
- If no personal details found, say so and focus on company angles
- Be specific and actionable"""),

        ("human", """Analyze this company:

Company: {company_name}
Domain: {domain}
Location: {city}, {state}
Industry: {industry}

Website Content Extracted:
{scraped_content}

Existing Data:
- OEM Brands: {oem_brands}
- Service Areas: {service_areas}
- Certifications: {certifications}
- Google Rating: {google_rating} ({google_review_count} reviews)

Extract:
1. Personal hooks (family, pets, hobbies)
2. Company story and values
3. Pain points and buying signals
4. WHY call this company NOW
5. Conversation opener

Be specific and avoid generic statements.""")
    ])

    def __init__(
        self,
        provider: str = "cerebras",
        model: Optional[str] = None,
        temperature: float = 0.3,
        workspace_root: str = "backend/data/agents/scout_agent"
    ):
        """
        Initialize ScoutAgent.

        Args:
            provider: LLM provider (cerebras, claude)
            model: Model ID (auto-selected if None)
            temperature: Generation temperature
            workspace_root: Root directory for agent state persistence
        """
        self.provider = provider
        self.model = model or self._default_model(provider)
        self.temperature = temperature
        self.workspace = Path(workspace_root)

        # Ensure workspace exists
        self.workspace.mkdir(parents=True, exist_ok=True)

        # Initialize LLM
        if provider == "cerebras":
            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                raise ValueError("CEREBRAS_API_KEY not set")
            self.llm = ChatCerebras(
                api_key=api_key,
                model=self.model,
                temperature=temperature,
                max_tokens=2000
            )
        elif provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY not set")
            self.llm = ChatAnthropic(
                api_key=api_key,
                model=self.model,
                temperature=temperature,
                max_tokens=2000
            )
        else:
            raise ValueError(f"Unsupported provider: {provider}")

        # Build chain
        self.chain = self.ENRICHMENT_PROMPT | self.llm

        # Load previous state
        self.state = self._load_state()

        logger.info(
            f"ScoutAgent initialized: provider={provider}, model={self.model}, "
            f"workspace={workspace_root}"
        )

    def _default_model(self, provider: str) -> str:
        """Get default model for provider."""
        defaults = {
            "cerebras": "llama-3.3-70b",
            "claude": "claude-3-haiku-20240307"
        }
        return defaults.get(provider, "llama-3.3-70b")

    def _load_state(self) -> Dict[str, Any]:
        """Load agent state from previous session."""
        state_file = self.workspace / "state.json"
        if state_file.exists():
            try:
                with open(state_file, 'r') as f:
                    state = json.load(f)
                    logger.info(f"Loaded previous state: session {state.get('session_number', 0)}")
                    return state
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

        # Default state
        return {
            "session_number": 0,
            "total_enriched": 0,
            "last_run_at": None,
            "last_error": None
        }

    def _save_state(self, updates: Dict[str, Any]):
        """Save agent state for next session."""
        self.state.update(updates)
        self.state["session_number"] += 1

        state_file = self.workspace / "state.json"
        try:
            with open(state_file, 'w') as f:
                json.dump(self.state, f, indent=2, default=str)
            logger.debug(f"Saved state: session {self.state['session_number']}")
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def _append_progress(self, message: str):
        """Append to progress.txt for multi-window continuity."""
        progress_file = self.workspace / "progress.txt"
        try:
            with open(progress_file, 'a') as f:
                timestamp = datetime.now().isoformat()
                f.write(f"\n[{timestamp}] {message}\n")
        except Exception as e:
            logger.error(f"Failed to append progress: {e}")

    async def run_cycle(
        self,
        limit: int = 10,
        require_domain: bool = True,
        icp_tier: Optional[str] = None
    ) -> ScoutCycleResult:
        """
        Run a full scout cycle: fetch → enrich → save → emit event.

        Args:
            limit: Maximum companies to enrich per cycle
            require_domain: Only enrich companies with domains
            icp_tier: Filter by ICP tier (PLATINUM, GOLD, etc.)

        Returns:
            ScoutCycleResult with enrichment stats and event
        """
        start_time = time.time()
        results = []
        errors = []

        logger.info(f"Starting scout cycle: limit={limit}, require_domain={require_domain}")
        self._append_progress(f"Session {self.state['session_number']+1} started: limit={limit}")

        try:
            # 1. Fetch unenriched leads from Supabase
            leads = query_unenriched_leads.invoke({
                'limit': limit,
                'require_domain': require_domain,
                'unenriched_only': True,
                'icp_tier': icp_tier
            })

            logger.info(f"Fetched {len(leads)} unenriched leads")

            if not leads:
                duration_ms = int((time.time() - start_time) * 1000)
                self._save_state({
                    "last_run_at": datetime.now().isoformat(),
                    "last_result": "no_leads"
                })
                self._append_progress("No unenriched leads found")

                return ScoutCycleResult(
                    total_fetched=0,
                    total_enriched=0,
                    total_errors=0,
                    errors=["No unenriched leads found"],
                    results=[],
                    duration_ms=duration_ms
                )

            # 2. Enrich each lead
            for lead in leads:
                try:
                    result = await self._enrich_single_lead(lead)
                    results.append(result)
                except Exception as e:
                    error_msg = f"Failed to enrich {lead.get('company_name')}: {str(e)}"
                    logger.error(error_msg)
                    errors.append(error_msg)

        except Exception as e:
            error_msg = f"Scout cycle failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            errors.append(error_msg)

        duration_ms = int((time.time() - start_time) * 1000)

        # Save state
        self._save_state({
            "last_run_at": datetime.now().isoformat(),
            "total_enriched": self.state["total_enriched"] + len(results),
            "last_result": "success" if results else "no_results"
        })
        self._append_progress(
            f"Enriched {len(results)} companies, {len(errors)} errors, {duration_ms}ms"
        )

        logger.info(
            f"Scout cycle complete: {len(results)} enriched, "
            f"{len(errors)} errors, {duration_ms}ms"
        )

        return ScoutCycleResult(
            total_fetched=len(leads),
            total_enriched=len(results),
            total_errors=len(errors),
            errors=errors,
            results=results,
            duration_ms=duration_ms
        )

    async def _enrich_single_lead(self, lead: Dict[str, Any]) -> ScoutEnrichmentResult:
        """
        Enrich a single lead: scrape + extract intel + save.

        Args:
            lead: Lead data from Supabase

        Returns:
            ScoutEnrichmentResult with enrichment data
        """
        start_time = time.time()

        company_id = lead.get('company_id')
        company_name = lead.get('company_name', 'Unknown')
        domain = lead.get('domain')

        logger.info(f"Enriching: {company_name} ({domain})")

        # For MVP: Use existing data as "scraped content"
        # In production: Replace with actual website scraping
        scraped_content = lead.get('ai_company_story', '') or f"{company_name} is located in {lead.get('city', 'N/A')}, {lead.get('state', 'N/A')}"

        # Run AI extraction
        response = await self.chain.ainvoke({
            'company_name': company_name,
            'domain': domain or 'N/A',
            'city': lead.get('city', 'N/A'),
            'state': lead.get('state', 'N/A'),
            'industry': lead.get('industry', 'HVAC'),
            'scraped_content': scraped_content,
            'oem_brands': lead.get('oem_brands', 'N/A'),
            'service_areas': lead.get('service_areas', 'N/A'),
            'certifications': lead.get('certifications', 'N/A'),
            'google_rating': lead.get('google_rating', 'N/A'),
            'google_review_count': lead.get('google_review_count', 0)
        })

        # Parse response (structured output not yet enabled, so parse text)
        response_text = response.content if hasattr(response, 'content') else str(response)

        # Extract components (basic parsing - improve in production)
        why_call = response_text[:500] if len(response_text) > 500 else response_text
        opener = None

        # Try to extract opener from response
        lines = response_text.split('\n')
        for line in lines:
            if 'opener' in line.lower() or line.startswith('"'):
                opener = line.strip('"').strip()[:200]
                break

        processing_time_ms = int((time.time() - start_time) * 1000)

        # Save to Supabase
        supabase = get_supabase()
        try:
            supabase.table('dim_companies').update({
                'ai_company_story': response_text[:1000] if len(response_text) > 1000 else response_text,
                'ai_why_call': why_call,
                'ai_recommended_opener': opener,
                'last_enriched_at': datetime.now().isoformat()
            }).eq('company_id', company_id).execute()

            logger.info(f"Saved enrichment for {company_name}")
        except Exception as e:
            logger.error(f"Failed to save enrichment for {company_name}: {e}")
            raise

        return ScoutEnrichmentResult(
            company_id=company_id,
            company_name=company_name,
            domain=domain,
            company_story=response_text[:500] if len(response_text) > 500 else response_text,
            why_call=why_call,
            recommended_opener=opener,
            enriched_at=datetime.now().isoformat(),
            processing_time_ms=processing_time_ms
        )

    async def enrich_single(self, company_id: str) -> ScoutEnrichmentResult:
        """
        Enrich a single company by ID (on-demand).

        Args:
            company_id: UUID of company in Supabase

        Returns:
            ScoutEnrichmentResult
        """
        supabase = get_supabase()
        result = supabase.table('dim_companies').select('*').eq('company_id', company_id).execute()

        if not result.data:
            raise ValueError(f"Company not found: {company_id}")

        lead = result.data[0]
        return await self._enrich_single_lead(lead)


# ========== Exports ==========

__all__ = [
    "ScoutAgent",
    "ScoutEnrichmentResult",
    "ScoutCycleResult",
    "PersonalHook"
]
