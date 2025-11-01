"""
EnrichmentAgent - ReAct Agent for Multi-Source Contact Enrichment

Uses LangGraph's create_react_agent() with ChatAnthropic for intelligent
multi-tool enrichment from Apollo.io, LinkedIn, and Close CRM.

Architecture:
    ReAct Loop: Reason → Act (call tool) → Observe → Repeat
    - Model decides which tools to call based on available data
    - Tools execute and return structured results
    - Model synthesizes all data into enriched_data
    - Loop continues until sufficient data or max_iterations reached

Tools Available:
    - enrich_contact_tool: Apollo.io enrichment via email
    - get_linkedin_profile_tool: LinkedIn scraping via Browserbase
    - get_lead_tool: Fetch existing CRM data from Close CRM

Performance:
    - Target: <15 seconds per enrichment (network-bound)
    - Model: claude-3-5-haiku-20241022 (fast, cheap, excellent tool use)
    - Typical iterations: 2-4 tool calls (Apollo → LinkedIn → synthesize)
    - Max iterations: 25 (prevents infinite loops)

Usage:
    ```python
    from app.services.langgraph.agents import EnrichmentAgent

    agent = EnrichmentAgent()
    result = await agent.enrich(
        email="john@acme.com",
        linkedin_url="https://linkedin.com/in/johndoe"
    )

    print(f"Enriched data: {result.enriched_data}")
    print(f"Confidence: {result.confidence_score}")
    print(f"Sources: {result.data_sources}")
    ```
"""

import os
import time
from typing import Optional, Dict, Any, List, Tuple, Union
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_anthropic import ChatAnthropic
from langgraph.prebuilt import create_react_agent

from app.services.langgraph.tools import (
    # enrich_contact_tool,  # Apollo.io - commented out (no API key)
    get_linkedin_profile_tool,
    get_lead_tool
)
from app.services.cache.enrichment_cache import get_enrichment_cache
from app.core.logging import setup_logging
from app.core.exceptions import ValidationError
from app.core.cost_optimized_llm import CostOptimizedLLMProvider, LLMConfig
from app.services.cost_tracking import get_cost_optimizer
from app.services.langgraph.tools import get_transfer_tools
from app.services.review_scraper import get_review_scraper

# New services for company-based enrichment
from app.services.hunter_email_service import get_hunter_service, HunterResult
from app.services.linkedin_company_service import get_linkedin_company_service, LinkedInCompanyResult
from app.services.linkedin_people_service import get_linkedin_people_service, LinkedInPeopleResult
from app.services.website_validator import get_website_validator
import asyncio

logger = setup_logging(__name__)


# ========== Output Schema ==========

@dataclass
class EnrichmentResult:
    """
    Structured output from EnrichmentAgent.

    Contains enriched data from multiple sources with quality metrics.
    """
    # Enriched contact data (merged from all sources)
    enriched_data: Dict[str, Any] = field(default_factory=dict)

    # Which sources contributed data
    data_sources: List[str] = field(default_factory=list)

    # Confidence score (0-1) based on data completeness and quality
    confidence_score: float = 0.0

    # Tool execution tracking
    tools_called: List[str] = field(default_factory=list)
    tool_results: Dict[str, Any] = field(default_factory=dict)

    # Performance metrics
    latency_ms: int = 0
    iterations_used: int = 0
    total_cost_usd: float = 0.0

    # Error tracking
    errors: List[str] = field(default_factory=list)


# ========== EnrichmentAgent ==========

class EnrichmentAgent:
    """
    ReAct agent for intelligent multi-source contact enrichment.

    Patterns:
        - create_react_agent() with Claude Haiku for fast tool calling
        - Structured error handling (tools never throw, return error status)
        - Confidence scoring based on data completeness and source quality
        - Graceful degradation (partial enrichment if some tools fail)

    Performance:
        - 5-10 seconds typical (Apollo + LinkedIn)
        - 2-4 tool calls average
        - Max 25 iterations (recursion_limit)
        - <$0.01 per enrichment (Haiku pricing)
    """

    def __init__(
        self,
        model: str = "claude-3-5-haiku-20241022",
        temperature: float = 0.3,
        max_iterations: int = 25,
        provider: str = "anthropic",
        use_cache: bool = True,
        track_costs: bool = True,
        db: Optional[Union[Session, AsyncSession]] = None
    ):
        """
        Initialize EnrichmentAgent with configurable LLM provider and caching.

        Supported Providers:
            - anthropic: Claude models (best tool calling, higher cost)
            - openrouter: DeepSeek/Qwen/Yi/GLM (90% cheaper, good tool calling)

        Args:
            model: Model ID (e.g., "claude-3-5-haiku-20241022" or "deepseek/deepseek-chat")
            temperature: Sampling temperature (0.3 for balanced reasoning)
            max_iterations: Max ReAct loop iterations (prevents infinite loops)
            provider: LLM provider ("anthropic" or "openrouter")
            use_cache: Enable LinkedIn profile caching (default: True, saves $0.10/profile)
            track_costs: Enable cost tracking to ai_cost_tracking table
            db: Database session for cost tracking (optional, supports Session or AsyncSession)
        """
        self.model = model
        self.temperature = temperature
        self.max_iterations = max_iterations
        self.provider = provider
        self.use_cache = use_cache
        self.cache = None  # Initialize on first use

        # Cost tracking
        self.track_costs = track_costs
        self.cost_optimizer = None  # Lazy init on first use
        self.db = db

        # Initialize cost-optimized provider if db provided
        if db:
            try:
                self.cost_provider = CostOptimizedLLMProvider(db)
                logger.info("EnrichmentAgent initialized with cost tracking enabled")
            except Exception as e:
                logger.error(f"Failed to initialize cost tracking: {e}")
                self.cost_provider = None
        else:
            self.cost_provider = None

        # Initialize LLM based on provider
        if provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            self.llm = ChatAnthropic(
                model=self.model,
                temperature=self.temperature,
                api_key=api_key
            )

        elif provider == "openrouter":
            # Use OpenRouter for DeepSeek/Qwen/Yi/GLM (90% cheaper!)
            from langchain_openai import ChatOpenAI

            api_key = os.getenv("OPENROUTER_API_KEY")
            if not api_key:
                raise ValueError("OPENROUTER_API_KEY environment variable not set")

            self.llm = ChatOpenAI(
                model=self.model,  # e.g., "deepseek/deepseek-chat"
                temperature=self.temperature,
                openai_api_key=api_key,
                openai_api_base="https://openrouter.ai/api/v1"
            )

        else:
            raise ValueError(
                f"Unsupported provider: {provider}. "
                f"Use 'anthropic' or 'openrouter'"
            )

        # Build ReAct agent with tools
        self.tools = [
            # enrich_contact_tool,  # Apollo.io - commented out (no API key)
            get_linkedin_profile_tool,
            get_lead_tool
        ]

        # System prompt guides tool use strategy
        self.system_message = self._build_system_prompt()

        # Create ReAct agent
        self.agent = create_react_agent(
            self.llm,
            self.tools,
            prompt=self.system_message
        )

        logger.info(
            f"EnrichmentAgent initialized: provider={provider}, model={model}, "
            f"temperature={temperature}, max_iterations={max_iterations}"
        )

    def _build_system_prompt(self) -> str:
        """Build system prompt for guiding tool use strategy."""
        return """You are an expert contact enrichment agent. Your goal is to gather comprehensive professional data about a contact using available tools.

**Available Tools:**
1. **enrich_contact_tool** - Apollo.io enrichment via email (returns: name, title, company, phone, LinkedIn URL)
2. **get_linkedin_profile_tool** - LinkedIn profile scraping (returns: work history, education, skills, current position)
3. **get_lead_tool** - Fetch existing CRM data from Close CRM (returns: stored contact info)

**Enrichment Strategy:**
1. **Start with available identifiers** (email OR linkedin_url)
2. **If email provided**: Call enrich_contact_tool first (Apollo often returns linkedin_url)
3. **If linkedin_url found**: Call get_linkedin_profile_tool for detailed career history
4. **If lead_id provided**: Call get_lead_tool to check existing CRM data
5. **Synthesize data**: Merge results from all sources, handling conflicts intelligently
6. **Stop when sufficient**: Stop calling tools once you have comprehensive data

**Conflict Resolution:**
- Prefer Apollo for contact info (email, phone, current company)
- Prefer LinkedIn for career history (experience, education, skills)
- Use CRM data as fallback if other sources unavailable

**Error Handling:**
- If a tool fails, try other available tools
- Return partial enrichment if at least one tool succeeds
- Document which tools failed in your response

**Output Format:**
Provide a final summary with:
- All enriched data collected
- Which tools were used successfully
- Data quality assessment (confidence level)
- Any errors encountered

Be strategic about tool use - don't call the same tool twice unless explicitly needed."""

    def _extract_tool_results(self, messages: List) -> Tuple[Dict[str, Any], List[str], List[str]]:
        """
        Extract tool results from agent message history.

        Args:
            messages: List of messages from agent execution

        Returns:
            Tuple of (tool_results, data_sources, errors):
                - tool_results: Dict mapping tool names to their outputs
                - data_sources: List of successful tool sources
                - errors: List of error messages from failed tools
        """
        tool_results = {}
        data_sources = []
        errors = []

        for message in messages:
            if isinstance(message, ToolMessage):
                # Extract tool name from message
                tool_name = message.name if hasattr(message, 'name') else "unknown_tool"

                # Parse tool response (content + artifact pattern)
                content = message.content if hasattr(message, 'content') else ""
                artifact = message.artifact if hasattr(message, 'artifact') else {}

                # Check if tool succeeded or failed
                if artifact and artifact.get("found") is not False and artifact.get("success") is not False:
                    # Tool succeeded
                    tool_results[tool_name] = artifact

                    # Track data source
                    source = artifact.get("source", tool_name.replace("_tool", ""))
                    if source not in data_sources:
                        data_sources.append(source)
                else:
                    # Tool failed or returned no data
                    error_msg = content if content else artifact.get("error", f"{tool_name} failed")
                    errors.append(error_msg)

        return tool_results, data_sources, errors

    def _merge_enriched_data(self, tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """
        Merge data from multiple tool results into unified enriched_data.

        Conflict resolution:
        - Apollo preferred for: email, phone, current company/title
        - LinkedIn preferred for: experience, education, skills
        - Merge without conflicts when possible

        Args:
            tool_results: Dict mapping tool names to their output artifacts

        Returns:
            Merged enriched_data dict
        """
        enriched = {}

        # Extract Apollo data (if available)
        apollo_data = tool_results.get("enrich_contact_tool", {})
        if apollo_data:
            contact = apollo_data.get("contact", {})
            enriched.update({
                "email": contact.get("email"),
                "phone": contact.get("phone"),
                "first_name": contact.get("first_name"),
                "last_name": contact.get("last_name"),
                "company": contact.get("company"),
                "title": contact.get("title"),
                "linkedin_url": contact.get("linkedin_url"),
                "apollo_person": apollo_data.get("apollo_person", {}),
                "apollo_enriched_at": apollo_data.get("enrichment_date")
            })

        # Extract LinkedIn data (if available)
        linkedin_data = tool_results.get("get_linkedin_profile_tool", {})
        if linkedin_data:
            # Merge LinkedIn-specific fields (career history)
            enriched.update({
                "linkedin_name": linkedin_data.get("name"),
                "linkedin_headline": linkedin_data.get("headline"),
                "linkedin_location": linkedin_data.get("location"),
                "linkedin_connections": linkedin_data.get("connections"),
                "experience": linkedin_data.get("experience", []),
                "education": linkedin_data.get("education", []),
                "skills": linkedin_data.get("skills", []),
                "current_company_linkedin": linkedin_data.get("current_company"),
                "current_title_linkedin": linkedin_data.get("current_title"),
                "linkedin_scraped_at": linkedin_data.get("scraped_at")
            })

            # Use LinkedIn data as fallback if Apollo missing
            if not enriched.get("company"):
                enriched["company"] = linkedin_data.get("current_company")
            if not enriched.get("title"):
                enriched["title"] = linkedin_data.get("current_title")
            if not enriched.get("linkedin_url"):
                enriched["linkedin_url"] = linkedin_data.get("profile_url")

        # Extract CRM data (if available)
        crm_data = tool_results.get("get_lead_tool", {})
        if crm_data and crm_data.get("lead"):
            lead = crm_data["lead"]
            # Use CRM as fallback only
            if not enriched.get("email"):
                enriched["email"] = lead.get("email")
            if not enriched.get("company"):
                enriched["company"] = lead.get("company")
            enriched["crm_lead_id"] = lead.get("id")
            enriched["crm_status"] = lead.get("status")

        # Remove None values
        enriched = {k: v for k, v in enriched.items() if v is not None}

        return enriched

    def _calculate_confidence_score(
        self,
        enriched_data: Dict[str, Any],
        data_sources: List[str],
        tools_called: List[str]
    ) -> float:
        """
        Calculate confidence score (0-1) based on data quality.

        Formula:
        - Completeness (40%): How many important fields populated
        - Source quality (30%): Apollo > LinkedIn > CRM
        - Freshness (30%): Ratio of successful tools

        Args:
            enriched_data: Merged enriched data
            data_sources: List of successful sources
            tools_called: List of all tools attempted

        Returns:
            Confidence score between 0 and 1
        """
        # Important fields for scoring
        important_fields = [
            "email", "phone", "first_name", "last_name",
            "company", "title", "linkedin_url",
            "experience", "education", "skills"
        ]

        # Completeness: % of important fields populated
        filled_fields = sum(1 for field in important_fields if enriched_data.get(field))
        completeness = filled_fields / len(important_fields)

        # Source quality: weighted by source reliability
        source_weights = {"apollo.io": 0.5, "linkedin_scraping": 0.3, "crm": 0.2}
        source_quality = sum(source_weights.get(source, 0.1) for source in data_sources)
        source_quality = min(source_quality, 1.0)  # Cap at 1.0

        # Freshness: % of tools that succeeded
        freshness = len(data_sources) / max(len(tools_called), 1)

        # Weighted average
        confidence = (completeness * 0.4) + (source_quality * 0.3) + (freshness * 0.3)

        return round(confidence, 2)

    async def enrich(
        self,
        email: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        lead_id: Optional[int] = None
    ) -> EnrichmentResult:
        """
        Enrich a contact using ReAct agent with multiple tools and intelligent caching.

        Requires at least ONE identifier: email, linkedin_url, or lead_id.

        Caching Strategy:
            - LinkedIn profiles cached for 7 days (saves $0.10 + 3s per cache hit)
            - Check cache before scraping LinkedIn
            - Always cache successful LinkedIn scrapes

        Args:
            email: Email address for Apollo enrichment
            linkedin_url: LinkedIn profile URL for scraping
            lead_id: Close CRM lead ID for existing data

        Returns:
            EnrichmentResult with enriched_data, confidence_score, and metadata

        Raises:
            ValidationError: If no identifiers provided
            Exception: If all enrichment tools fail

        Example:
            >>> agent = EnrichmentAgent()
            >>> result = await agent.enrich(email="john@acme.com")
            >>> print(result.enriched_data["company"])
            "Acme Corp"
        """
        # Validate input
        if not any([email, linkedin_url, lead_id]):
            raise ValidationError(
                "At least one identifier required: email, linkedin_url, or lead_id"
            )

        # Initialize cache on first use
        if self.use_cache and self.cache is None:
            self.cache = await get_enrichment_cache()

        # Check cache if LinkedIn URL provided
        if self.use_cache and linkedin_url:
            cached_profile = await self.cache.get_profile(linkedin_url)
            if cached_profile:
                # Cache hit! Log savings
                if self.track_costs and self.cost_optimizer is None:
                    self.cost_optimizer = await get_cost_optimizer()
                if self.cost_optimizer:
                    await self.cost_optimizer.log_cache_hit(
                        cache_type="linkedin",
                        cache_key=linkedin_url,
                        savings_usd=0.10,  # LinkedIn scrape cost
                        latency_saved_ms=3000,  # Avg scrape time
                        agent_name="enrichment"
                    )
                    logger.info(f"💾 LinkedIn cache hit saved $0.10 + 3s")
                
                # Return cached result immediately
                return EnrichmentResult(
                    enriched_data=cached_profile,
                    data_sources=["linkedin_cache"],
                    confidence_score=1.0,
                    tools_called=[],
                    tool_results={"linkedin_cache": cached_profile},
                    latency_ms=5,  # Cache hit is fast!
                    iterations_used=0,
                    total_cost_usd=0.0,  # Free!
                    errors=[]
                )

        # Build enrichment request message
        request_parts = []
        if email:
            request_parts.append(f"Email: {email}")
        if linkedin_url:
            request_parts.append(f"LinkedIn: {linkedin_url}")
        if lead_id:
            request_parts.append(f"CRM Lead ID: {lead_id}")

        request_message = (
            f"Enrich this contact using all available tools:\n" +
            "\n".join(request_parts) +
            "\n\nUse tools strategically to gather comprehensive professional data."
        )

        start_time = time.time()

        try:
            # Invoke ReAct agent with recursion limit
            result = await self.agent.ainvoke(
                {"messages": [HumanMessage(content=request_message)]},
                config={"recursion_limit": self.max_iterations}
            )

            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            # Extract messages from result
            messages = result.get("messages", [])

            # Count iterations (number of AI messages)
            iterations = sum(1 for m in messages if isinstance(m, AIMessage))

            # Extract tool results and errors
            tool_results, data_sources, errors = self._extract_tool_results(messages)

            # Track which tools were called
            tools_called = list(tool_results.keys())

            # Merge tool results into enriched_data
            enriched_data = self._merge_enriched_data(tool_results)

            # Add review scraping for reputation data
            company_name = enriched_data.get("company")
            company_website = enriched_data.get("website") or enriched_data.get("company_website")
            
            if company_name:
                try:
                    review_scraper = await get_review_scraper()
                    review_result = await review_scraper.get_reviews(company_name, company_website)
                    
                    # Add review data to enriched_data
                    enriched_data["reputation_score"] = review_result.overall_reputation_score
                    enriched_data["average_rating"] = review_result.average_rating
                    enriched_data["total_reviews"] = review_result.total_reviews
                    enriched_data["has_negative_signals"] = review_result.has_negative_signals
                    enriched_data["review_data_quality"] = review_result.data_quality
                    enriched_data["platform_reviews"] = [
                        {
                            "platform": r.platform,
                            "rating": r.rating,
                            "review_count": r.review_count,
                            "status": r.status
                        }
                        for r in review_result.platform_results
                    ]
                    
                    # Add review sources to data_sources
                    successful_platforms = [
                        r.platform for r in review_result.platform_results 
                        if r.status == "success"
                    ]
                    if successful_platforms:
                        data_sources.extend([f"{p}_reviews" for p in successful_platforms])
                    
                    logger.info(
                        f"Review enrichment complete: score={review_result.overall_reputation_score}, "
                        f"platforms={len(successful_platforms)}"
                    )
                except Exception as e:
                    logger.warning(f"Review scraping failed: {e}")
                    # Don't fail entire enrichment if reviews fail - just log and continue
                    errors.append(f"Review scraping failed: {str(e)}")

            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                enriched_data, data_sources, tools_called
            )

            # Check if we got any data
            if not enriched_data:
                raise Exception(
                    f"All enrichment tools failed. Errors: {'; '.join(errors)}"
                )

            # Build result
            enrichment_result = EnrichmentResult(
                enriched_data=enriched_data,
                data_sources=data_sources,
                confidence_score=confidence_score,
                tools_called=tools_called,
                tool_results=tool_results,
                latency_ms=latency_ms,
                iterations_used=iterations,
                total_cost_usd=self._estimate_cost(iterations),
                errors=errors
            )

            # Cache LinkedIn profile if successfully scraped
            if self.use_cache and linkedin_url and "get_linkedin_profile_tool" in tool_results:
                linkedin_data = tool_results["get_linkedin_profile_tool"]
                if linkedin_data and linkedin_data.get("found") is not False:
                    await self.cache.set_profile(linkedin_url, linkedin_data)
                    logger.info(f"💾 Cached LinkedIn profile for future use")

            logger.info(
                f"Enrichment complete: sources={data_sources}, "
                f"confidence={confidence_score}, latency={latency_ms}ms, "
                f"iterations={iterations}"
            )
            
            # Log cost to ai-cost-optimizer
            if self.track_costs:
                await self._log_enrichment_cost(
                    enriched_data=enriched_data,
                    tools_called=tools_called,
                    iterations=iterations,
                    latency_ms=latency_ms,
                    total_cost_usd=enrichment_result.total_cost_usd
                )

            return enrichment_result

        except Exception as e:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            logger.error(f"Enrichment failed: {str(e)}", exc_info=True)

            # Return partial result if we have any data
            # (This handles GraphRecursionError and other recoverable errors)
            return EnrichmentResult(
                enriched_data={},
                data_sources=[],
                confidence_score=0.0,
                tools_called=[],
                tool_results={},
                latency_ms=latency_ms,
                iterations_used=0,
                total_cost_usd=0.0,
                errors=[str(e)]
            )

    def _estimate_cost(self, iterations: int) -> float:
        """
        Estimate cost based on iterations and provider.

        Pricing (2025):
        - Claude Haiku: $0.25 input + $1.25 output per 1M tokens
        - DeepSeek v3: $0.27 input + $1.10 output per 1M tokens (via OpenRouter)
        - Qwen: $0.18 input + $0.90 output per 1M tokens (via OpenRouter)

        Typical enrichment: ~2000 input + ~500 output tokens per iteration

        Args:
            iterations: Number of ReAct loop iterations

        Returns:
            Estimated cost in USD
        """
        # Estimate tokens per iteration
        input_tokens_per_iter = 2000  # System prompt + tool results
        output_tokens_per_iter = 500  # Tool calls + reasoning

        total_input = input_tokens_per_iter * iterations
        total_output = output_tokens_per_iter * iterations

        # Provider-specific pricing
        if self.provider == "anthropic":
            input_cost = (total_input / 1_000_000) * 0.25
            output_cost = (total_output / 1_000_000) * 1.25
        elif self.provider == "openrouter":
            # Conservative estimate (DeepSeek pricing)
            input_cost = (total_input / 1_000_000) * 0.27
            output_cost = (total_output / 1_000_000) * 1.10
        else:
            # Default to Claude pricing
            input_cost = (total_input / 1_000_000) * 0.25
            output_cost = (total_output / 1_000_000) * 1.25

        return round(input_cost + output_cost, 4)

    async def enrich_from_company(
        self,
        company_name: str,
        website: str
    ) -> EnrichmentResult:
        """
        Enrich contacts at a company using parallel multi-source discovery.

        NO EMAIL REQUIRED - Discovers ATL contacts from:
        - Hunter.io (email discovery by domain)
        - LinkedIn Company Search → LinkedIn People Search
        - Website Scraping (existing about/team pages)

        Performance: <3000ms total (parallel execution)

        Args:
            company_name: Company name (e.g., "ACS Commercial Services")
            website: Company website URL (e.g., "https://acsfixit.com")

        Returns:
            EnrichmentResult with:
                - enriched_data["atl_contacts"]: List of discovered contacts
                - enriched_data["linkedin_company"]: Company LinkedIn profile
                - data_sources: ["hunter", "linkedin", "website"]
                - confidence_score: Based on contact quality

        Example:
            >>> agent = EnrichmentAgent()
            >>> result = await agent.enrich_from_company(
            ...     company_name="ACS Commercial Services",
            ...     website="https://acsfixit.com"
            ... )
            >>> print(f"Found {len(result.enriched_data['atl_contacts'])} contacts")
        """
        start_time = time.time()

        logger.info(f"Starting company enrichment for: {company_name}")

        try:
            # ===== PHASE 1: Parallel Data Gathering =====
            logger.info("Phase 1: Launching parallel data sources")

            hunter_task = self._get_hunter_emails(website)
            linkedin_company_task = self._get_linkedin_company(company_name, website)
            website_atl_task = self._get_website_atl(website)

            # Execute in parallel
            results = await asyncio.gather(
                hunter_task,
                linkedin_company_task,
                website_atl_task,
                return_exceptions=True
            )

            hunter_result, linkedin_company_result, website_atl_contacts = results

            # ===== PHASE 2: LinkedIn People Search =====
            linkedin_people = []
            if (linkedin_company_result
                and linkedin_company_result.status == "success"
                and linkedin_company_result.company):

                logger.info(f"Phase 2: Searching LinkedIn for ATL contacts at {company_name}")
                linkedin_people_result = await self._get_linkedin_people(
                    linkedin_company_result.company.linkedin_url,
                    company_name
                )
                if linkedin_people_result.status == "success":
                    linkedin_people = linkedin_people_result.people

            # ===== PHASE 3: Merge & Deduplicate =====
            logger.info("Phase 3: Merging and deduplicating contacts")

            hunter_contacts = (hunter_result.contacts
                             if hunter_result and hunter_result.status == "success"
                             else [])
            website_contacts = website_atl_contacts if website_atl_contacts else []

            merged_contacts = self._merge_atl_contacts(
                hunter_emails=hunter_contacts,
                linkedin_people=linkedin_people,
                website_atl=website_contacts
            )

            # Track successful sources
            data_sources = []
            if hunter_contacts:
                data_sources.append("hunter")
            if linkedin_people:
                data_sources.append("linkedin")
            if website_contacts:
                data_sources.append("website")

            # Build enriched_data
            enriched_data = {
                "company_name": company_name,
                "website": website,
                "atl_contacts": merged_contacts,
                "total_contacts_found": len(merged_contacts),
                "data_sources": data_sources
            }

            # Add LinkedIn company data if found
            if linkedin_company_result and linkedin_company_result.company:
                enriched_data["linkedin_company"] = {
                    "name": linkedin_company_result.company.name,
                    "linkedin_url": linkedin_company_result.company.linkedin_url,
                    "company_id": linkedin_company_result.company.company_id
                }

            # Calculate confidence based on contact count and source diversity
            confidence_score = self._calculate_company_confidence(
                merged_contacts,
                data_sources
            )

            latency_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Company enrichment complete: {len(merged_contacts)} contacts found, "
                f"{len(data_sources)} sources, {latency_ms}ms"
            )

            return EnrichmentResult(
                enriched_data=enriched_data,
                data_sources=data_sources,
                confidence_score=confidence_score,
                tools_called=[],  # Direct service calls, not tool-based
                tool_results={},
                latency_ms=latency_ms,
                iterations_used=0,
                total_cost_usd=0.0,  # Hunter.io API cost negligible
                errors=[]
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Company enrichment failed: {e}")

            return EnrichmentResult(
                enriched_data={},
                data_sources=[],
                confidence_score=0.0,
                tools_called=[],
                tool_results={},
                latency_ms=latency_ms,
                iterations_used=0,
                total_cost_usd=0.0,
                errors=[str(e)]
            )

    async def _get_hunter_emails(self, website: str) -> HunterResult:
        """Get emails from Hunter.io by domain"""
        try:
            hunter = await get_hunter_service()
            return await hunter.find_emails(website, atl_only=True)
        except Exception as e:
            logger.error(f"Hunter.io error: {e}")
            return HunterResult(
                domain=website,
                contacts=[],
                total_emails=0,
                status="error",
                error_message=str(e)
            )

    async def _get_linkedin_company(
        self,
        company_name: str,
        website: str
    ) -> LinkedInCompanyResult:
        """Find LinkedIn company profile"""
        try:
            linkedin_company = await get_linkedin_company_service()
            return await linkedin_company.find_company(company_name, website)
        except Exception as e:
            logger.error(f"LinkedIn company search error: {e}")
            return LinkedInCompanyResult(
                company=None,
                status="error",
                error_message=str(e)
            )

    async def _get_linkedin_people(
        self,
        company_linkedin_url: str,
        company_name: str
    ) -> LinkedInPeopleResult:
        """Search for ATL contacts at LinkedIn company"""
        try:
            linkedin_people = await get_linkedin_people_service()
            return await linkedin_people.find_atl_contacts(
                company_linkedin_url,
                company_name,
                limit=10
            )
        except Exception as e:
            logger.error(f"LinkedIn people search error: {e}")
            return LinkedInPeopleResult(
                people=[],
                company_name=company_name,
                total_found=0,
                status="error",
                error_message=str(e)
            )

    async def _get_website_atl(self, website: str) -> List[Dict[str, Any]]:
        """Scrape ATL contacts from website (existing service)"""
        try:
            validator = await get_website_validator()
            # Website validator returns validation result with atl_contacts
            result = await validator.validate_website(website)
            return result.get("atl_contacts", []) if result else []
        except Exception as e:
            logger.error(f"Website ATL scraping error: {e}")
            return []

    def _merge_atl_contacts(
        self,
        hunter_emails: List,
        linkedin_people: List,
        website_atl: List
    ) -> List[Dict[str, Any]]:
        """
        Merge and deduplicate ATL contacts from multiple sources.

        Priority: LinkedIn (95) > Hunter.io (50-100) > Website (50)

        Returns:
            List of deduplicated contacts sorted by confidence
        """
        contacts_map = {}  # key -> contact data

        # Add LinkedIn people first (highest priority)
        for person in linkedin_people:
            key = person.email if person.email else person.linkedin_url
            contacts_map[key] = {
                "name": person.name,
                "email": person.email,
                "linkedin_url": str(person.linkedin_url),
                "title": person.title,
                "company": person.company,
                "source": "linkedin",
                "confidence": 95
            }

        # Add Hunter.io emails (don't overwrite LinkedIn)
        for contact in hunter_emails:
            key = contact.email
            if key not in contacts_map:
                full_name = f"{contact.first_name or ''} {contact.last_name or ''}".strip()
                contacts_map[key] = {
                    "name": full_name or None,
                    "email": contact.email,
                    "linkedin_url": None,
                    "title": contact.position,
                    "company": None,
                    "source": "hunter",
                    "confidence": contact.confidence
                }

        # Add website ATL contacts (lowest priority)
        for atl in website_atl:
            key = atl.get("email") or atl.get("name")
            if key and key not in contacts_map:
                contacts_map[key] = {
                    "name": atl.get("name"),
                    "email": atl.get("email"),
                    "linkedin_url": atl.get("linkedin_url"),
                    "title": atl.get("title"),
                    "company": None,
                    "source": "website_scraping",
                    "confidence": 50
                }

        # Convert to list and sort by confidence
        contacts = list(contacts_map.values())
        contacts.sort(key=lambda x: x["confidence"], reverse=True)

        return contacts

    def _calculate_company_confidence(
        self,
        contacts: List[Dict],
        data_sources: List[str]
    ) -> float:
        """
        Calculate confidence score for company enrichment.

        Formula:
        - Contact count (40%): More contacts = higher confidence
        - Source diversity (30%): More sources = higher confidence
        - Contact quality (30%): LinkedIn > Hunter > Website
        """
        # Contact count score (0-1)
        contact_score = min(len(contacts) / 5.0, 1.0)  # Max at 5 contacts

        # Source diversity score (0-1)
        source_score = len(data_sources) / 3.0  # Max 3 sources

        # Contact quality score (0-1)
        if contacts:
            avg_confidence = sum(c["confidence"] for c in contacts) / len(contacts)
            quality_score = avg_confidence / 100.0
        else:
            quality_score = 0.0

        # Weighted average
        confidence = (
            contact_score * 0.4 +
            source_score * 0.3 +
            quality_score * 0.3
        )

        return round(confidence, 2)

    async def enrich_batch(
        self,
        contacts: List[Dict[str, Any]],
        max_concurrency: int = 5
    ) -> List[EnrichmentResult]:
        """
        Enrich multiple contacts in parallel using asyncio.

        Args:
            contacts: List of dicts with email/linkedin_url/lead_id
            max_concurrency: Max concurrent enrichments (default: 5)

        Returns:
            List of EnrichmentResults (same order as input)

        Example:
            >>> contacts = [
            ...     {"email": "john@acme.com"},
            ...     {"linkedin_url": "https://linkedin.com/in/jane"}
            ... ]
            >>> results = await agent.enrich_batch(contacts)
        """
        import asyncio

        semaphore = asyncio.Semaphore(max_concurrency)

        async def enrich_with_semaphore(contact: Dict[str, Any]):
            async with semaphore:
                return await self.enrich(**contact)

        tasks = [enrich_with_semaphore(contact) for contact in contacts]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        enrichment_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch enrichment failed for contact {i}: {result}")
                enrichment_results.append(EnrichmentResult(
                    errors=[str(result)]
                ))
            else:
                enrichment_results.append(result)

        return enrichment_results

    async def _log_enrichment_cost(
        self,
        enriched_data: Dict[str, Any],
        tools_called: List[str],
        iterations: int,
        latency_ms: int,
        total_cost_usd: float
    ):
        """
        Log enrichment cost to ai-cost-optimizer.

        Args:
            enriched_data: Enriched contact data
            tools_called: List of tools that were called
            iterations: Number of ReAct loop iterations
            latency_ms: Total execution time
            total_cost_usd: Total cost of enrichment
        """
        if self.cost_optimizer is None:
            self.cost_optimizer = await get_cost_optimizer()

        if self.cost_optimizer is None:
            return  # Failed to initialize

        # Build prompt summary
        identifiers = []
        if enriched_data.get("email"):
            identifiers.append(f"email={enriched_data['email']}")
        if enriched_data.get("linkedin_url"):
            identifiers.append(f"linkedin={enriched_data['linkedin_url'][:50]}")
        prompt = f"Enrich contact: {', '.join(identifiers)}"

        # Build response summary
        response_parts = [
            f"Sources: {', '.join(tools_called)}",
            f"Company: {enriched_data.get('company', 'N/A')}",
            f"Title: {enriched_data.get('title', 'N/A')}"
        ]
        response = " | ".join(response_parts)

        # Estimate token counts (rough estimate)
        estimated_input_tokens = 2000 * iterations
        estimated_output_tokens = 500 * iterations

        await self.cost_optimizer.log_llm_call(
            provider=self.provider,
            model=self.model,
            prompt=prompt,
            response=response,
            tokens_in=estimated_input_tokens,
            tokens_out=estimated_output_tokens,
            cost_usd=total_cost_usd,
            agent_name="enrichment",
            metadata={
                "tools_called": tools_called,
                "iterations": iterations,
                "latency_ms": latency_ms,
                "confidence_score": self._calculate_confidence_score(
                    enriched_data, tools_called, tools_called
                )
            }
        )

        logger.debug(
            f"💰 Logged enrichment cost: ${total_cost_usd:.6f} "
            f"({iterations} iterations, {latency_ms}ms)"
        )

    def get_transfer_tools(self):
        """
        Get agent transfer tools for enrichment workflows.

        Returns:
            List of transfer tools that enrichment agent can use
        """
        return get_transfer_tools("enrichment")


# ========== Exports ==========

__all__ = [
    "EnrichmentAgent",
    "EnrichmentResult",
]
