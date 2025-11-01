"""
QualificationAgent - Multi-Provider Lead Qualification

Supports multiple LLM providers with free-form JSON generation and parsing:
- Cerebras (llama3.1-8b, llama3.1-70b) - Ultra-fast, cost-effective
- Claude (haiku, sonnet) - High quality reasoning
- DeepSeek (v3) - Cost-effective analysis
- Ollama (local) - Private inference

Architecture:
    Input → ChatPromptTemplate → LLM → Free-form JSON → Parse → Result

Performance Targets:
    - Cerebras llama3.1-8b: <500ms, $0.00001/request
    - Cerebras llama3.1-70b: <800ms, $0.00006/request
    - Claude Haiku: <2000ms, $0.0005/request
    - DeepSeek v3: <3000ms, $0.00003/request
    - Ollama: <1000ms, $0/request

Usage:
    ```python
    from app.services.langgraph.agents import QualificationAgent

    # Cerebras (default)
    agent = QualificationAgent(provider="cerebras", model="llama3.1-8b")

    # Claude
    agent = QualificationAgent(provider="claude", model="claude-3-haiku-20240307")

    # DeepSeek
    agent = QualificationAgent(provider="deepseek", model="deepseek-chat")

    # Ollama
    agent = QualificationAgent(provider="ollama", model="llama3.1:8b")

    result = await agent.qualify(
        company_name="Acme Corp",
        industry="SaaS",
        company_size="50-200"
    )

    print(f"Score: {result.qualification_score}")
    print(f"Reasoning: {result.qualification_reasoning}")
    print(f"Tier: {result.tier}")
    ```
"""

import os
import time
import json
import re
from typing import Optional, List, Dict, Any, Literal, Union
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from langchain_core.prompts import ChatPromptTemplate
from langchain_cerebras import ChatCerebras
from langchain_anthropic import ChatAnthropic
from langchain_community.chat_models import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import BaseChatModel

from app.core.logging import setup_logging
from app.core.exceptions import CerebrasAPIError
from app.core.cost_optimized_llm import CostOptimizedLLMProvider, LLMConfig
from app.services.cache.qualification_cache import get_qualification_cache
from app.services.cost_tracking import get_cost_optimizer
# Lazy import to avoid circular dependency
# from app.services.langgraph.tools import get_transfer_tools
from app.services.website_validator import get_website_validator
from app.services.review_scraper import get_review_scraper

logger = setup_logging(__name__)


# ========== Pydantic Output Schema ==========

class LeadQualificationResult(BaseModel):
    """
    Structured output schema for lead qualification.

    Enforced by with_structured_output() - guarantees this structure
    without manual JSON parsing or error handling.
    """
    qualification_score: float = Field(
        description="Qualification score from 0-100 based on company fit, contact quality, and sales potential"
    )

    qualification_reasoning: str = Field(
        description="2-3 sentence explanation covering fit, quality, and potential"
    )

    tier: str = Field(
        description="Qualification tier: 'hot' (80-100), 'warm' (60-79), 'cold' (40-59), or 'unqualified' (0-39)"
    )

    fit_assessment: str = Field(
        description="Company fit evaluation: size, industry alignment, market presence"
    )

    contact_quality: str = Field(
        description="Contact level and relevance: decision-maker assessment"
    )

    sales_potential: str = Field(
        description="Buying signals and readiness indicators"
    )

    recommendations: Optional[List[str]] = Field(
        default=None,
        description="2-4 actionable next steps for this lead (provide at least 2)"
    )


# ========== QualificationAgent ==========

class QualificationAgent:
    """
    Multi-provider lead qualification agent with free-form JSON generation.

    Patterns:
        - LCEL chain composition with | operator
        - Free-form JSON generation + manual parsing
        - Async-first design with ainvoke()
        - Built-in LangSmith tracing
        - Provider abstraction (Cerebras/Claude/DeepSeek/Ollama)

    Performance Optimizations:
        - Temperature 0.2 (faster generation, fewer tokens)
        - Streaming disabled for batch mode (lower latency)
        - Provider-specific TCP warming
    """

    # Provider pricing (per million tokens, combined input+output for simplicity)
    PROVIDER_PRICING = {
        "cerebras": {
            "llama3.1-8b": 0.10,
            "llama3.1-70b": 0.60,
        },
        "claude": {
            "claude-3-haiku-20240307": 1.25,  # $0.25 in + $1.00 out
            "claude-3-5-sonnet-20241022": 4.50,  # $3.00 in + $15.00 out
        },
        "deepseek": {
            "deepseek-chat": 0.27,  # $0.14 in + $0.28 out (cache-enabled)
        },
        "ollama": {
            "*": 0.0  # Local inference, no cost
        }
    }

    def __init__(
        self,
        provider: Literal["cerebras", "claude", "deepseek", "ollama"] = "cerebras",
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 500,
        use_cache: bool = True,
        track_costs: bool = True,
        db: Optional[Union[Session, AsyncSession]] = None
    ):
        """
        Initialize QualificationAgent with specified provider and optional cost tracking.

        Args:
            provider: LLM provider (cerebras/claude/deepseek/ollama)
            model: Model ID (auto-selects if None)
            temperature: Sampling temperature (0.2 for consistent scoring)
            max_tokens: Max completion tokens (500 for free-form JSON)
            use_cache: Enable qualification caching (default: True, saves $0.000006/call + 633ms)
            track_costs: Enable cost tracking to ai_cost_tracking table
            db: Database session for cost tracking (optional, supports Session or AsyncSession)
        """
        self.provider = provider
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.use_cache = use_cache
        self.cache = None  # Initialize on first use
        self.cost_optimizer = None  # Lazy init for legacy cost tracking
        self.track_costs = track_costs
        self.db = db

        # Initialize cost-optimized provider if db provided
        if db:
            try:
                self.cost_provider = CostOptimizedLLMProvider(db)
                logger.info("QualificationAgent initialized with cost tracking enabled")
            except Exception as e:
                logger.error(f"Failed to initialize cost tracking: {e}")
                self.cost_provider = None
        else:
            self.cost_provider = None
            if track_costs:
                logger.warning("Cost tracking requested but no database session provided")

        # Auto-select model if not provided
        if model is None:
            model_map = {
                "cerebras": "llama3.1-8b",
                "claude": "claude-3-haiku-20240307",
                "deepseek": "deepseek-chat",
                "ollama": "llama3.1:8b"
            }
            model = model_map[provider]

        self.model = model

        # Initialize LLM based on provider
        self.llm = self._initialize_llm()

        # Build LCEL chain with free-form output
        self.chain = self._build_chain()

        logger.info(
            f"QualificationAgent initialized: provider={provider}, model={model}, "
            f"temperature={temperature}, max_tokens={max_tokens}"
        )

    def _initialize_llm(self) -> BaseChatModel:
        """Initialize LLM based on provider."""
        if self.provider == "cerebras":
            api_key = os.getenv("CEREBRAS_API_KEY")
            if not api_key:
                raise ValueError("CEREBRAS_API_KEY environment variable not set")

            return ChatCerebras(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key
            )

        elif self.provider == "claude":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            return ChatAnthropic(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key
            )

        elif self.provider == "deepseek":
            # DeepSeek supports Anthropic-compatible API (no OpenAI needed!)
            # https://api-docs.deepseek.com/guides/anthropic_api
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError("ANTHROPIC_API_KEY environment variable not set")

            return ChatAnthropic(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
                base_url="https://api.deepseek.com"  # Anthropic-compatible endpoint
            )

        elif self.provider == "ollama":
            # Ollama runs locally, no API key needed
            return ChatOllama(
                model=self.model,
                temperature=self.temperature,
                num_predict=self.max_tokens
            )

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    def _build_chain(self):
        """
        Build LCEL chain: prompt | llm (free-form JSON generation)

        Returns:
            Compiled LCEL chain ready for invocation
        """
        # System prompt for qualification criteria with JSON output
        system_prompt = """You are an AI sales assistant specializing in B2B lead qualification.

Analyze the provided lead information and assign a qualification score from 0-100 based on:

1. **Company Fit** (40 points)
   - Company size matches ICP (Ideal Customer Profile)
   - Industry alignment with product offerings
   - Market presence and growth indicators

2. **Contact Quality** (30 points)
   - Decision-maker level (C-suite, VP, Director)
   - Relevant title for the purchase decision
   - Accessibility and responsiveness signals

3. **Sales Potential** (30 points)
   - Buying signals (recent funding, expansion, hiring)
   - Urgency indicators (pain points, deadlines)
   - Budget/readiness signals

Scoring Tiers:
- Hot (80-100): High fit, decision-maker, strong buying signals → immediate outreach
- Warm (60-79): Good fit, relevant contact, some signals → nurture campaign
- Cold (40-59): Moderate fit, lower contact quality → long-term nurture
- Unqualified (0-39): Poor fit or missing critical info → deprioritize

**IMPORTANT**: Respond ONLY with valid JSON in this exact format:
{{
  "qualification_score": <number 0-100>,
  "qualification_reasoning": "<2-3 sentence explanation>",
  "tier": "<hot|warm|cold|unqualified>",
  "fit_assessment": "<company fit evaluation>",
  "contact_quality": "<contact level assessment>",
  "sales_potential": "<buying signals and readiness>",
  "recommendations": ["<action 1>", "<action 2>", "<action 3>"]
}}

Do not include any text before or after the JSON object."""

        # User prompt template
        user_prompt_template = """Qualify this lead:

Company: {company_name}
{optional_fields}

Respond with JSON only."""

        # Create ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt_template)
        ])

        # Build LCEL chain with free-form output
        # Pattern: prompt | llm (returns raw text to be parsed)
        chain = prompt | self.llm

        return chain

    def _parse_json_response(self, response_text: str) -> LeadQualificationResult:
        """
        Parse free-form JSON response from LLM.

        Args:
            response_text: Raw text response from LLM

        Returns:
            Parsed LeadQualificationResult

        Raises:
            ValueError: If JSON parsing fails
        """
        try:
            # Try to extract JSON from response (handles cases where LLM adds text)
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if not json_match:
                raise ValueError(f"No JSON object found in response: {response_text[:200]}")

            json_str = json_match.group(0)
            data = json.loads(json_str)

            # Validate and create Pydantic model
            result = LeadQualificationResult(**data)
            return result

        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed: {e}\nResponse: {response_text[:500]}")
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to parse qualification response: {e}")
            raise ValueError(f"Failed to parse qualification response: {str(e)}")

    def _format_optional_fields(
        self,
        company_website: Optional[str] = None,
        company_size: Optional[str] = None,
        industry: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_title: Optional[str] = None,
        notes: Optional[str] = None
    ) -> str:
        """Format optional fields for prompt."""
        fields = []

        if company_website:
            fields.append(f"Website: {company_website}")
        if company_size:
            fields.append(f"Size: {company_size}")
        if industry:
            fields.append(f"Industry: {industry}")
        if contact_name:
            fields.append(f"Contact: {contact_name}")
        if contact_title:
            fields.append(f"Title: {contact_title}")
        if notes:
            fields.append(f"Notes: {notes}")

        return "\n".join(fields) if fields else "No additional information provided."

    async def qualify(
        self,
        company_name: str,
        lead_id: Optional[int] = None,
        company_website: Optional[str] = None,
        company_size: Optional[str] = None,
        industry: Optional[str] = None,
        contact_name: Optional[str] = None,
        contact_title: Optional[str] = None,
        notes: Optional[str] = None
    ) -> tuple[LeadQualificationResult, int, Dict[str, Any]]:
        """
        Qualify a lead using LCEL chain with Cerebras inference.

        Args:
            company_name: Company name (required)
            lead_id: Lead ID for cost tracking (optional)
            company_website: Company website URL
            company_size: Company size (e.g., "50-200 employees")
            industry: Industry sector
            contact_name: Contact person's name
            contact_title: Contact person's job title
            notes: Additional context or notes

        Returns:
            Tuple of (result, latency_ms, metadata):
                - result: LeadQualificationResult with all fields populated
                - latency_ms: End-to-end latency in milliseconds
                - metadata: Dict with model, tokens, cost, etc.

        Raises:
            CerebrasAPIError: If Cerebras API call fails
            ValueError: If company_name is empty

        Example:
            >>> agent = QualificationAgent()
            >>> result, latency, meta = await agent.qualify(
            ...     company_name="Acme Corp",
            ...     lead_id=123,
            ...     industry="SaaS",
            ...     company_size="100-500"
            ... )
            >>> print(f"Score: {result.qualification_score}, Latency: {latency}ms")
        """
        if not company_name:
            raise ValueError("company_name is required")

        # ===== WEBSITE VALIDATION (ICP Qualifier) =====
        # If no website or website is down, lead is not ICP
        if company_website:
            validator = await get_website_validator()
            website_result = await validator.validate(company_website)

            if not website_result.is_valid:
                # Website check failed - DISQUALIFY immediately
                logger.warning(
                    f"Website validation failed for {company_name}: {website_result.error_message}"
                )
                return (
                    LeadQualificationResult(
                        qualification_score=0.0,
                        qualification_reasoning=f"Company website is not accessible ({website_result.error_message}). This indicates the company may not be operational or lacks digital presence, making them not fit for our ICP.",
                        tier="unqualified",
                        fit_assessment="No digital presence - website not accessible",
                        contact_quality="Cannot assess - no website",
                        sales_potential="Zero - company appears non-operational"
                    ),
                    int((time.time() - time.time()) * 1000),  # Minimal latency
                    {
                        "provider": "website_validator",
                        "model": "http_check",
                        "disqualified_reason": "website_not_accessible",
                        "website_status_code": website_result.status_code,
                        "website_error": website_result.error_message
                    }
                )

            # Website is valid - log additional context for scoring
            logger.info(
                f"Website validated for {company_name}: "
                f"team_page={website_result.has_team_page}, "
                f"atl_contacts={len(website_result.atl_contacts)}"
            )

            # ===== REVIEW SCRAPING (Reputation Data) =====
            # Scrape reviews from multiple platforms for reputation scoring
            try:
                review_scraper = await get_review_scraper()
                review_result = await review_scraper.get_reviews(company_name, company_website)

                # Add review data to context for scoring
                notes = notes or ""
                notes += f"\n\nREPUTATION DATA:\n"
                notes += f"- Overall Reputation Score: {review_result.overall_reputation_score}/100\n"
                notes += f"- Average Rating: {review_result.average_rating}/5.0\n"
                notes += f"- Total Reviews: {review_result.total_reviews}\n"
                notes += f"- Review Data Quality: {review_result.data_quality}\n"
                notes += f"- Negative Signals: {'Yes' if review_result.has_negative_signals else 'No'}\n"

                # Platform breakdown
                successful_platforms = [r for r in review_result.platform_results if r.status == "success"]
                if successful_platforms:
                    notes += f"- Platforms Found: {', '.join([p.platform for p in successful_platforms])}\n"

                logger.info(
                    f"Reviews scraped for {company_name}: "
                    f"reputation_score={review_result.overall_reputation_score}, "
                    f"platforms={len(successful_platforms)}"
                )
            except Exception as e:
                logger.warning(f"Review scraping failed for {company_name}: {e}")
                # Don't fail qualification if review scraping fails
                pass

        # Initialize cache on first use
        if self.use_cache and self.cache is None:
            self.cache = await get_qualification_cache()

        # Check cache before LLM call
        if self.use_cache:
            cached_qualification = await self.cache.get_qualification(company_name, industry)
            if cached_qualification:
                # Cache hit! Return immediately
                result = LeadQualificationResult(**cached_qualification["result"])
                
                # Log cache hit savings
                if self.track_costs and self.cost_optimizer is None:
                    try:
                        self.cost_optimizer = await get_cost_optimizer()
                    except Exception:
                        pass
                
                if self.cost_optimizer:
                    # Calculate savings
                    cost_per_m_tokens = self.PROVIDER_PRICING.get(self.provider, {}).get(
                        self.model,
                        self.PROVIDER_PRICING.get(self.provider, {}).get("*", 0)
                    )
                    estimated_tokens = 100  # Rough estimate for qualification
                    savings_usd = (estimated_tokens / 1_000_000) * cost_per_m_tokens
                    
                    await self.cost_optimizer.log_cache_hit(
                        cache_type="qualification",
                        cache_key=f"{company_name}:{industry or 'none'}",
                        savings_usd=savings_usd,
                        latency_saved_ms=cached_qualification["latency_ms"],
                        agent_name="qualification"
                    )
                
                return result, cached_qualification["latency_ms"], cached_qualification["metadata"]

        # Format optional fields
        optional_fields = self._format_optional_fields(
            company_website=company_website,
            company_size=company_size,
            industry=industry,
            contact_name=contact_name,
            contact_title=contact_title,
            notes=notes
        )

        # Measure latency
        start_time = time.time()

        try:
            # Use cost-optimized provider if available (new path with tracking)
            if self.cost_provider:
                # Build full prompt text for CostOptimizedLLMProvider
                full_prompt = f"""You are an AI sales assistant specializing in B2B lead qualification.

Analyze the provided lead information and assign a qualification score from 0-100 based on:

1. **Company Fit** (40 points)
   - Company size matches ICP (Ideal Customer Profile)
   - Industry alignment with product offerings
   - Market presence and growth indicators

2. **Contact Quality** (30 points)
   - Decision-maker level (C-suite, VP, Director)
   - Relevant title for the purchase decision
   - Accessibility and responsiveness signals

3. **Sales Potential** (30 points)
   - Buying signals (recent funding, expansion, hiring)
   - Urgency indicators (pain points, deadlines)
   - Budget/readiness signals

Scoring Tiers:
- Hot (80-100): High fit, decision-maker, strong buying signals → immediate outreach
- Warm (60-79): Good fit, relevant contact, some signals → nurture campaign
- Cold (40-59): Moderate fit, lower contact quality → long-term nurture
- Unqualified (0-39): Poor fit or missing critical info → deprioritize

**IMPORTANT**: Respond ONLY with valid JSON in this exact format:
{{
  "qualification_score": <number 0-100>,
  "qualification_reasoning": "<2-3 sentence explanation>",
  "tier": "<hot|warm|cold|unqualified>",
  "fit_assessment": "<company fit evaluation>",
  "contact_quality": "<contact level assessment>",
  "sales_potential": "<buying signals and readiness>",
  "recommendations": ["<action 1>", "<action 2>", "<action 3>"]
}}

Do not include any text before or after the JSON object.

Qualify this lead:

Company: {company_name}
{optional_fields}

Respond with JSON only."""

                # Create config for cost tracking
                config = LLMConfig(
                    agent_type="qualification",
                    lead_id=lead_id,  # Pass lead_id for per-lead tracking
                    mode="passthrough",  # Keep existing Cerebras behavior
                    provider=self.provider,
                    model=self.model
                )

                # Call cost-optimized provider
                cost_result = await self.cost_provider.complete(
                    prompt=full_prompt,
                    config=config,
                    max_tokens=self.max_tokens,
                    temperature=self.temperature
                )

                response_text = cost_result["response"]
                latency_ms = cost_result.get("latency_ms", 0)

            else:
                # Fallback to direct LCEL chain (existing path, no new tracking)
                # Invoke LCEL chain (async) - returns AIMessage
                response = await self.chain.ainvoke({
                    "company_name": company_name,
                    "optional_fields": optional_fields
                })

                # Extract text content from AIMessage
                response_text = response.content if hasattr(response, 'content') else str(response)

                end_time = time.time()
                latency_ms = int((end_time - start_time) * 1000)

            # Parse free-form JSON response (same for both paths)
            result: LeadQualificationResult = self._parse_json_response(response_text)

            # Calculate cost based on provider and model
            estimated_tokens = len(company_name) * 4 + len(optional_fields) * 2 + 300  # Rough estimate
            cost_per_m_tokens = self.PROVIDER_PRICING.get(self.provider, {}).get(
                self.model,
                self.PROVIDER_PRICING.get(self.provider, {}).get("*", 0)
            )
            estimated_cost_usd = (estimated_tokens / 1_000_000) * cost_per_m_tokens

            # Build metadata
            metadata = {
                "provider": self.provider,
                "model": self.model,
                "temperature": self.temperature,
                "latency_ms": latency_ms,
                "agent_type": "qualification",
                "lcel_chain": True,
                "free_form_json": True,
                "estimated_tokens": estimated_tokens,
                "estimated_cost_usd": round(estimated_cost_usd, 6)
            }

            logger.info(
                f"Lead qualified successfully: company={company_name}, "
                f"score={result.qualification_score}, tier={result.tier}, "
                f"latency={latency_ms}ms, provider={self.provider}, model={self.model}"
            )

            # Cache qualification result
            if self.use_cache:
                cache_data = {
                    "result": result.model_dump(),
                    "latency_ms": latency_ms,
                    "metadata": metadata
                }
                await self.cache.set_qualification(company_name, industry, cache_data)
                logger.info(f"💾 Cached qualification for future use")

            # Cost tracking is now handled by CostOptimizedLLMProvider
            # No legacy tracking needed

            return result, latency_ms, metadata

        except Exception as e:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            logger.error(
                f"Lead qualification failed: company={company_name}, "
                f"latency={latency_ms}ms, provider={self.provider}, error={str(e)}",
                exc_info=True
            )

            raise CerebrasAPIError(
                message=f"Lead qualification failed with {self.provider}",
                details={
                    "company_name": company_name,
                    "provider": self.provider,
                    "model": self.model,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

    def get_transfer_tools(self):
        """
        Get agent transfer tools for qualification workflows.

        Returns:
            List of transfer tools allowing handoff to enrichment/growth agents
        """
        # Lazy import to avoid circular dependency
        from app.services.langgraph.tools import get_transfer_tools
        return get_transfer_tools("qualification")

    async def qualify_batch(
        self,
        leads: List[Dict[str, Any]],
        max_concurrency: int = 5
    ) -> List[tuple[LeadQualificationResult, int, Dict[str, Any]]]:
        """
        Qualify multiple leads in parallel using LCEL batch processing.

        Args:
            leads: List of lead dicts with company_name and optional fields
            max_concurrency: Maximum concurrent API calls (default: 5)

        Returns:
            List of (result, latency_ms, metadata) tuples

        Example:
            >>> leads = [
            ...     {"company_name": "Acme Corp", "industry": "SaaS"},
            ...     {"company_name": "TechCo", "industry": "FinTech"}
            ... ]
            >>> results = await agent.qualify_batch(leads)
        """
        import asyncio

        # Create tasks with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrency)

        async def qualify_with_semaphore(lead: Dict[str, Any]):
            async with semaphore:
                return await self.qualify(**lead)

        tasks = [qualify_with_semaphore(lead) for lead in leads]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch qualification failed for lead {i}: {result}")
            else:
                successful_results.append(result)

        return successful_results


# ========== Exports ==========

__all__ = [
    "QualificationAgent",
    "LeadQualificationResult",
]
