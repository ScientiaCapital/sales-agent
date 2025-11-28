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
from langchain_openai import ChatOpenAI  # For DeepSeek (OpenAI-compatible API)
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
from app.services.email_extractor import EmailExtractor
from app.services.hunter_service import HunterService, extract_domain
from app.services.apollo import ApolloService
from app.services.website_discovery import get_website_discovery_service
from app.services.browserbase_team_scraper import get_browserbase_team_scraper
from app.services.apollo_enrichment_queue import get_apollo_queue, QueuePriority
from app.services.contact_discovery_audit import (
    ContactDiscoveryAudit,
    DiscoveryMethod,
    get_discovery_audit
)

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

        # Initialize email extractor
        self.email_extractor = EmailExtractor()

        # Initialize Hunter.io service
        self.hunter_service = HunterService()

        # Initialize Apollo service (optional - if API key configured)
        try:
            self.apollo_service = ApolloService()
            logger.info("Apollo service initialized")
        except Exception as e:
            self.apollo_service = None
            logger.warning(f"Apollo service not available: {e}")

        logger.info(
            f"QualificationAgent initialized: provider={provider}, model={model}, "
            f"temperature={temperature}, max_tokens={max_tokens}, email_extraction=enabled"
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
            # DeepSeek V3 uses OpenAI-compatible API
            # https://api-docs.deepseek.com - 671B MoE, $0.28/1M input, $0.42/1M output
            api_key = os.getenv("DEEPSEEK_API_KEY")
            if not api_key:
                raise ValueError("DEEPSEEK_API_KEY environment variable not set")

            return ChatOpenAI(
                model=self.model,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                api_key=api_key,
                base_url="https://api.deepseek.com"  # OpenAI-compatible endpoint
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

    def _is_atl_title(self, title: str) -> bool:
        """Check if job title indicates Above-The-Line (decision maker) position."""
        if not title:
            return False

        title_lower = title.lower()
        atl_keywords = [
            "ceo", "chief executive", "president", "owner", "founder", "co-founder",
            "cto", "chief technology", "cfo", "chief financial", "coo", "chief operating",
            "vp", "vice president", "svp", "senior vice president", "evp", "executive vice president",
            "director", "head of", "manager", "partner", "principal"
        ]

        return any(keyword in title_lower for keyword in atl_keywords)

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
        contact_email: Optional[str] = None,
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

        # Initialize email discovery tracking
        extraction_method = "none"
        hunter_cost = 0.0
        discovered_contacts = []  # Initialize at function level to avoid UnboundLocalError

        # Initialize Contact Discovery Audit for full visibility
        discovery_audit = get_discovery_audit(
            company_name=company_name,
            company_website=company_website,
            session_id=str(lead_id) if lead_id else None,
            create_new=True  # Fresh audit for each qualification
        )

        # ===== WEBSITE DISCOVERY (if missing) =====
        # Many contractor CSVs don't have websites - find them via Google BEFORE validation
        if not company_website:
            logger.info(f"No website provided for {company_name}, attempting discovery...")
            start_discovery = time.time()
            try:
                discovery_service = await get_website_discovery_service()
                discovered_website = await discovery_service.discover_website(
                    company_name=company_name,
                    industry=industry,
                    state=""  # NOTE: Address field not in current schema - would need usaddress library + parameter addition
                )
                discovery_latency = int((time.time() - start_discovery) * 1000)
                if discovered_website:
                    company_website = discovered_website
                    discovery_audit.company_website = company_website  # Update audit
                    discovery_audit.log_attempt(
                        DiscoveryMethod.WEBSITE_DISCOVERY,
                        success=True, contacts=0, latency_ms=discovery_latency,
                        reason=f"Found: {company_website}"
                    )
                    logger.info(f"✅ Discovered website for {company_name}: {company_website}")
                else:
                    discovery_audit.log_attempt(
                        DiscoveryMethod.WEBSITE_DISCOVERY,
                        success=True, contacts=0, latency_ms=discovery_latency,
                        reason="No website found via search"
                    )
                    logger.info(f"Could not discover website for {company_name}")
            except Exception as e:
                discovery_latency = int((time.time() - start_discovery) * 1000)
                discovery_audit.log_attempt(
                    DiscoveryMethod.WEBSITE_DISCOVERY,
                    success=False, latency_ms=discovery_latency,
                    reason=str(e)
                )
                logger.warning(f"Website discovery failed for {company_name}: {e}")

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

            # ===== EMAIL/CONTACT DISCOVERY =====
            # Three-tier contact discovery:
            # 1. Website Discovery (if missing) → 2. Hunter.io + Apollo Domain Search → 3. Phone Fallback
            # Discover ATL contacts if not provided
            if not contact_email:
                logger.info(f"Attempting contact discovery for {company_name}")

                # === STEP 0: Website Discovery (if missing) ===
                # Many contractor CSVs don't have websites - find them via Google
                if not company_website:
                    logger.info(f"No website provided for {company_name}, attempting discovery...")
                    try:
                        discovery_service = get_website_discovery_service()
                        discovered_website = await discovery_service.discover_website(
                            company_name=company_name,
                            industry=company_industry,
                            state=""  # NOTE: Address field not in current schema - would need usaddress library + parameter addition
                        )
                        if discovered_website:
                            company_website = discovered_website
                            logger.info(f"✅ Discovered website for {company_name}: {company_website}")
                        else:
                            logger.info(f"Could not discover website for {company_name}")
                    except Exception as e:
                        logger.warning(f"Website discovery failed for {company_name}: {e}")

                # Tier 1: Hunter.io + Apollo Domain Search (run both, merge results)
                # Returns ALL employees with job titles from both sources
                all_contacts = []
                seen_emails = set()

                if company_website:
                    domain = extract_domain(company_website)

                    # Hunter.io Domain Search
                    hunter_start = time.time()
                    try:
                        hunter_contacts = await self.hunter_service.domain_search(
                            domain=domain,
                            limit=10,
                            atl_only=False  # Get ALL contacts (ATL + BTL) for marketing
                        )
                        hunter_latency = int((time.time() - hunter_start) * 1000)

                        if hunter_contacts:
                            atl_count = 0
                            btl_count = 0
                            for contact in hunter_contacts:
                                email = contact.get('email', '').lower()
                                if email and email not in seen_emails:
                                    contact['source'] = 'hunter'
                                    all_contacts.append(contact)
                                    seen_emails.add(email)
                                    if contact.get('is_atl'):
                                        atl_count += 1
                                    else:
                                        btl_count += 1
                            discovery_audit.log_attempt(
                                DiscoveryMethod.HUNTER_DOMAIN_SEARCH,
                                success=True,
                                contacts=len(hunter_contacts),
                                atl=atl_count, btl=btl_count,
                                latency_ms=hunter_latency,
                                cost_usd=0.01,  # Hunter.io domain search cost
                                contacts_data=hunter_contacts
                            )
                            logger.info(f"Hunter.io found {len(hunter_contacts)} contacts for {company_name}")
                        else:
                            discovery_audit.log_attempt(
                                DiscoveryMethod.HUNTER_DOMAIN_SEARCH,
                                success=True, contacts=0, latency_ms=hunter_latency,
                                reason="No contacts found"
                            )
                    except Exception as e:
                        hunter_latency = int((time.time() - hunter_start) * 1000)
                        discovery_audit.log_attempt(
                            DiscoveryMethod.HUNTER_DOMAIN_SEARCH,
                            success=False, latency_ms=hunter_latency,
                            reason=str(e)
                        )
                        logger.warning(f"Hunter.io domain search failed for {company_website}: {e}")

                    # ============================================================
                    # APOLLO DISABLED - No credits available (Nov 26, 2025)
                    # Re-enable when Apollo credits are purchased
                    # ============================================================
                    # Apollo Domain Search + Enrichment (to get REAL emails, not placeholders)
                    # if self.apollo_service:
                    #     try:
                    #         # Use search_and_enrich to get verified emails (costs credits but gets real data)
                    #         apollo_contacts = await self.apollo_service.search_and_enrich_contacts(
                    #             domain=domain,
                    #             max_results=10,
                    #             reveal_emails=True,
                    #             reveal_phones=False  # Phones require webhook_url - get emails first
                    #         )
                    #
                    #         if apollo_contacts:
                    #             for contact in apollo_contacts:
                    #                 email = contact.get('email', '').lower() if contact.get('email') else ''
                    #
                    #                 # Skip placeholder emails
                    #                 if not email or 'not_unlocked' in email:
                    #                     continue
                    #
                    #                 # Check if Hunter already found this email
                    #                 if email in seen_emails:
                    #                     # CROSS-VERIFICATION: Mark existing contact as verified by both sources
                    #                     for existing in all_contacts:
                    #                         if existing.get('email', '').lower() == email:
                    #                             existing['verified_by'] = 'hunter+apollo'
                    #                             existing['apollo_verified'] = True
                    #                             logger.info(f"✅ Cross-verified: {email} found by both Hunter and Apollo")
                    #                     continue
                    #
                    #                 # New contact from Apollo (verified email)
                    #                 normalized = {
                    #                     'email': contact.get('email'),
                    #                     'first_name': contact.get('first_name', ''),
                    #                     'last_name': contact.get('last_name', ''),
                    #                     'position': contact.get('title', ''),
                    #                     'phone': contact.get('phone', ''),
                    #                     'linkedin_url': contact.get('linkedin_url', ''),
                    #                     'is_atl': self._is_atl_title(contact.get('title', '')),
                    #                     'source': contact.get('source', 'apollo'),  # Preserve enrichment source
                    #                     'verified_by': 'apollo',
                    #                     'email_verified': contact.get('email_verified', False),
                    #                     'confidence': contact.get('confidence', 'unknown')
                    #                 }
                    #                 all_contacts.append(normalized)
                    #                 seen_emails.add(email)
                    #                 logger.info(f"Apollo contact added: {email} (verified: {contact.get('email_verified', False)})")
                    #
                    #             verified_count = sum(1 for c in apollo_contacts if c.get('email_verified'))
                    #             logger.info(f"Apollo enriched {len(apollo_contacts)} contacts for {company_name} ({verified_count} verified emails)")
                    #     except Exception as e:
                    #         logger.warning(f"Apollo enrichment failed for {company_website}: {e}")
                    # ============================================================

                    # Log Apollo as disabled for audit visibility
                    discovery_audit.log_disabled_method(
                        DiscoveryMethod.APOLLO_DOMAIN_SEARCH,
                        "No Apollo credits (Nov 26, 2025) - re-enable when purchased"
                    )

                    # ===== QUEUE FOR APOLLO ENRICHMENT =====
                    # DISABLED - No Apollo credits (Nov 26, 2025)
                    # Re-enable when Apollo credits are purchased
                    # Calculate ATL contacts from Hunter.io results
                    atl_contacts = [c for c in all_contacts if c.get('is_atl')]
                    # contacts_needing_email = [c for c in all_contacts if c.get('needs_email') or not c.get('email')]
                    # if len(atl_contacts) < 3 or contacts_needing_email:
                    #     try:
                    #         apollo_queue = get_apollo_queue()
                    #         # Determine priority based on qualification
                    #         priority = QueuePriority.HIGH if len(atl_contacts) > 0 else QueuePriority.MEDIUM
                    #
                    #         await apollo_queue.add_to_queue(
                    #             company_name=company_name,
                    #             company_website=company_website,
                    #             company_phone=company_phone,
                    #             priority=priority,
                    #             source="qualification_incomplete",
                    #             existing_contacts=contacts_needing_email + [
                    #                 c for c in atl_contacts if c.get('needs_email')
                    #             ]
                    #         )
                    #         logger.info(
                    #             f"📋 Added to Apollo queue: {company_name} "
                    #             f"(priority={priority}, contacts_needing_email={len(contacts_needing_email)})"
                    #         )
                    #     except Exception as e:
                    #         logger.warning(f"Failed to add to Apollo queue: {e}")

                # === TIER 3: Phone-based Apollo Fallback ===
                # DISABLED - No Apollo credits (Nov 26, 2025)
                # if not all_contacts and company_phone and self.apollo_service:
                #     logger.info(f"No contacts from domain search, trying phone lookup: {company_phone}")
                #     try:
                #         phone_contacts = await self.apollo_service.enrich_by_phone(
                #             phone=company_phone,
                #             company_name=company_name
                #         )
                #
                #         if phone_contacts:
                #             for contact in phone_contacts:
                #                 email = contact.get('email', '').lower()
                #                 if email and email not in seen_emails:
                #                     # Normalize and add ATL classification
                #                     contact['is_atl'] = self._is_atl_title(contact.get('title', ''))
                #                     all_contacts.append(contact)
                #                     seen_emails.add(email)
                #             logger.info(f"✅ Apollo phone lookup found {len(phone_contacts)} contacts for {company_name}")
                #     except Exception as e:
                #         logger.warning(f"Apollo phone lookup failed for {company_phone}: {e}")

                # Process merged contacts
                if all_contacts:
                    discovered_contacts = all_contacts
                    extraction_method = "hunter_apollo_search"
                    hunter_cost = len(all_contacts) * 0.01  # Approximate cost

                    # Separate ATL and BTL contacts
                    atl_contacts = [c for c in all_contacts if c.get('is_atl')]
                    btl_contacts = [c for c in all_contacts if not c.get('is_atl')]

                    # Use ATL contact first (for outreach), fallback to first contact
                    if atl_contacts:
                        contact_email = atl_contacts[0]["email"]
                    else:
                        contact_email = all_contacts[0]["email"]

                    notes = notes or ""

                    if atl_contacts:
                        atl_summary = ", ".join([
                            f"{c['first_name']} {c['last_name']} ({c['position']}) [{c.get('source', 'unknown')}]"
                            for c in atl_contacts[:5]
                        ])
                        notes += f"\n\nATL CONTACTS ({len(atl_contacts)} found):\n{atl_summary}"
                        if len(atl_contacts) > 5:
                            notes += f"\n+ {len(atl_contacts) - 5} more ATL contacts"

                    if btl_contacts:
                        btl_summary = ", ".join([
                            f"{c['first_name']} {c['last_name']} ({c['position']}) [{c.get('source', 'unknown')}]"
                            for c in btl_contacts[:3]
                        ])
                        notes += f"\n\nBTL CONTACTS (for marketing):\n{btl_summary}"
                        if len(btl_contacts) > 3:
                            notes += f"\n+ {len(btl_contacts) - 3} more BTL contacts"

                    logger.info(
                        f"Total: {len(all_contacts)} contacts for {company_name} "
                        f"({len(atl_contacts)} ATL, {len(btl_contacts)} BTL), "
                        f"primary: {contact_email}"
                    )

                # ===== TIER 1.5: BROWSERBASE TEAM SCRAPING =====
                # If Hunter.io found <3 ATL contacts, use Browserbase to scrape team pages
                # This handles JavaScript-heavy sites that Hunter.io can't parse
                if company_website and len(atl_contacts) < 3:
                    browserbase_start = time.time()
                    try:
                        browserbase_scraper = await get_browserbase_team_scraper()
                        team_contacts = await browserbase_scraper.scrape_team_page(company_website)
                        browserbase_latency = int((time.time() - browserbase_start) * 1000)

                        if team_contacts:
                            new_atl = 0
                            new_btl = 0
                            for contact in team_contacts:
                                email = contact.get('email', '').lower()
                                # Only add if we don't already have this email
                                if email and email not in seen_emails:
                                    # Classify ATL/BTL
                                    is_atl = self._is_atl_title(contact.get('title', ''))
                                    normalized = {
                                        'email': email,
                                        'first_name': contact.get('name', '').split()[0] if contact.get('name') else '',
                                        'last_name': ' '.join(contact.get('name', '').split()[1:]) if contact.get('name') else '',
                                        'position': contact.get('title', ''),
                                        'is_atl': is_atl,
                                        'source': 'browserbase_team'
                                    }
                                    all_contacts.append(normalized)
                                    seen_emails.add(email)
                                    if is_atl:
                                        new_atl += 1
                                        atl_contacts.append(normalized)
                                    else:
                                        new_btl += 1
                                        btl_contacts.append(normalized)
                                elif contact.get('name') and not email:
                                    # Contact without email - still valuable for BTL marketing
                                    normalized = {
                                        'email': '',
                                        'first_name': contact.get('name', '').split()[0] if contact.get('name') else '',
                                        'last_name': ' '.join(contact.get('name', '').split()[1:]) if contact.get('name') else '',
                                        'position': contact.get('title', ''),
                                        'is_atl': self._is_atl_title(contact.get('title', '')),
                                        'source': 'browserbase_team',
                                        'needs_email': True
                                    }
                                    all_contacts.append(normalized)
                                    if normalized['is_atl']:
                                        new_atl += 1
                                    else:
                                        new_btl += 1

                            discovery_audit.log_attempt(
                                DiscoveryMethod.BROWSERBASE_TEAM,
                                success=True,
                                contacts=len(team_contacts),
                                atl=new_atl, btl=new_btl,
                                latency_ms=browserbase_latency,
                                cost_usd=0.01,  # Browserbase session cost estimate
                                reason=f"Team page scraped: {new_atl} new ATL, {new_btl} new BTL"
                            )

                            # Update primary contact if we found better ATL
                            if not contact_email and atl_contacts:
                                contact_email = atl_contacts[0].get('email', '')
                            elif not contact_email and btl_contacts:
                                contact_email = btl_contacts[0].get('email', '')

                            logger.info(f"Browserbase found {len(team_contacts)} team members ({new_atl} ATL, {new_btl} BTL)")
                        else:
                            discovery_audit.log_attempt(
                                DiscoveryMethod.BROWSERBASE_TEAM,
                                success=True, contacts=0, latency_ms=browserbase_latency,
                                reason="No team page found or no contacts extracted"
                            )
                    except Exception as e:
                        browserbase_latency = int((time.time() - browserbase_start) * 1000) if 'browserbase_start' in dir() else 0
                        discovery_audit.log_attempt(
                            DiscoveryMethod.BROWSERBASE_TEAM,
                            success=False, latency_ms=browserbase_latency,
                            reason=str(e)
                        )
                        logger.warning(f"Browserbase team scraping failed for {company_website}: {e}")

                # Tier 2: Website Scraping Fallback (FREE, but less reliable)
                # Only if Hunter.io + Browserbase didn't find ATL contacts
                if not contact_email and company_website:
                    scrape_start = time.time()
                    try:
                        extracted_emails = await self.email_extractor.extract_emails(company_website)
                        scrape_latency = int((time.time() - scrape_start) * 1000)

                        if extracted_emails:
                            contact_email = extracted_emails[0]  # Use top-priority email
                            extraction_method = "scraping"
                            discovery_audit.log_attempt(
                                DiscoveryMethod.WEBSITE_EMAIL_SCRAPE,
                                success=True,
                                contacts=len(extracted_emails),
                                atl=0, btl=len(extracted_emails),  # Scraped emails are typically BTL
                                latency_ms=scrape_latency,
                                cost_usd=0.0,  # FREE
                                reason=f"Emails: {', '.join(extracted_emails[:3])}"
                            )
                            logger.info(f"Website scraping found {len(extracted_emails)} emails, using: {contact_email}")

                            # Add to qualification notes
                            if notes:
                                notes += f"\nEmails found (scraping): {', '.join(extracted_emails[:3])}"
                            else:
                                notes = f"Emails found (scraping): {', '.join(extracted_emails[:3])}"
                        else:
                            discovery_audit.log_attempt(
                                DiscoveryMethod.WEBSITE_EMAIL_SCRAPE,
                                success=True, contacts=0, latency_ms=scrape_latency,
                                reason="No emails found on website"
                            )
                            logger.warning(f"No emails found via scraping for {company_website}")
                    except Exception as e:
                        scrape_latency = int((time.time() - scrape_start) * 1000)
                        discovery_audit.log_attempt(
                            DiscoveryMethod.WEBSITE_EMAIL_SCRAPE,
                            success=False, latency_ms=scrape_latency,
                            reason=str(e)
                        )
                        logger.error(f"Website scraping failed for {company_website}: {e}")
            else:
                # Email was provided upfront, no extraction needed
                extraction_method = "provided"

            # ===== REVIEW SCRAPING (Reputation Data) =====
            # Scrape reviews from multiple platforms for reputation scoring
            review_start = time.time()
            try:
                review_scraper = await get_review_scraper()
                review_result = await review_scraper.get_reviews(company_name, company_website)
                review_latency = int((time.time() - review_start) * 1000)

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

                # Log review scraping to audit
                discovery_audit.log_attempt(
                    DiscoveryMethod.REVIEW_SCRAPING,
                    success=True,
                    contacts=0,  # Review scraping doesn't find contacts
                    latency_ms=review_latency,
                    cost_usd=0.0,
                    reason=f"Score: {review_result.overall_reputation_score}/100, Platforms: {len(successful_platforms)}"
                )

                logger.info(
                    f"Reviews scraped for {company_name}: "
                    f"reputation_score={review_result.overall_reputation_score}, "
                    f"platforms={len(successful_platforms)}"
                )
            except Exception as e:
                review_latency = int((time.time() - review_start) * 1000)
                discovery_audit.log_attempt(
                    DiscoveryMethod.REVIEW_SCRAPING,
                    success=False, latency_ms=review_latency,
                    reason=str(e)
                )
                logger.warning(f"Review scraping failed for {company_name}: {e}")
                # Don't fail qualification if review scraping fails
                pass

            # ===== ADD DISCOVERY AUDIT TO NOTES =====
            # Append the discovery audit summary to qualification notes
            audit_notes = discovery_audit.get_qualification_notes()
            if notes:
                notes += audit_notes
            else:
                notes = audit_notes

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

                # ===== CRITICAL FIX: Merge discovered contacts into cached metadata =====
                # Contact discovery (Hunter.io, Apollo) runs BEFORE cache check
                # So we must update the cached metadata with newly discovered contacts
                cached_metadata = cached_qualification["metadata"].copy()
                if discovered_contacts:
                    cached_metadata["discovered_contacts"] = discovered_contacts
                    logger.info(f"🔄 Cache hit - merged {len(discovered_contacts)} newly discovered contacts into cached result")

                # Include discovery audit in cached metadata
                cached_metadata["discovery_audit"] = discovery_audit.get_summary()

                return result, cached_qualification["latency_ms"], cached_metadata

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
                "estimated_cost_usd": round(estimated_cost_usd, 6),
                "extracted_email": contact_email,  # Include extracted/provided email for downstream use
                "extraction_method": extraction_method,  # Track how email was discovered
                "hunter_cost_usd": hunter_cost,  # Track Hunter.io API costs
                "discovered_contacts": discovered_contacts,  # ALL ATL contacts from Hunter.io for enrichment/CRM
                "discovery_audit": discovery_audit.get_summary()  # Full contact discovery audit trail
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
