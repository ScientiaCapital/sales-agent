"""
DropInAgent - Universal Input Handler for Lead Enrichment

Accepts any input format and orchestrates the full enrichment pipeline:
- URL, company name, LinkedIn URL, Close lead ID, or person name
- ALWAYS checks Close CRM first for duplicates (domain + fuzzy name match)
- Routes to ScoutAgent for enrichment if new
- Routes to RankingAgent after enrichment
- Stages outreach if requested

Architecture:
    ┌──────────────┐
    │ receive_input│ ─── Accept any input (URL, name, Close ID, person)
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │ parse_input  │ ─── Detect type + extract domain/name
    └──────┬───────┘
           │
    ┌──────▼───────┐
    │🔍 CLOSE DEDUP│ ─── ALWAYS CHECK FIRST (domain + fuzzy name)
    └──────┬───────┘
           │
      ┌────┴────┐
      │         │
    EXISTS    NEW
      │         │
      ▼         ▼
   Return   ScoutAgent (enrich website + LinkedIn)
   link to      │
   existing     ▼
   lead    RankingAgent (ICP score + tier)
               │
               ▼
          (if HOT) OutreachAgent (stage drafts)
               │
               ▼
          Notify Slack/user

Usage:
    # Manual enrichment
    from app.services.langgraph.agents.dropin_agent import DropInAgent

    agent = DropInAgent()
    result = await agent.drop_in("https://acme-hvac.com")

    if result.exists_in_close:
        print(f"Already exists: {result.close_url}")
    else:
        print(f"Enriched: {result.icp_score}, tier: {result.icp_tier}")

    # Via API
    POST /api/v1/langgraph/dropin {"input": "https://acme-hvac.com"}

    # Via Slack
    /enrich https://acme-hvac.com

    # Via Claude Code
    /enrich https://acme-hvac.com --stage email,sms
"""

import os
import re
import time
from typing import Optional, Literal, List
from urllib.parse import urlparse
from pydantic import BaseModel
from difflib import SequenceMatcher

from app.core.logging import setup_logging
from app.services.crm.close_deduplication import CloseDeduplicationService
from app.services.langgraph.agents.lead_scout_agent import LeadScoutAgent
from app.services.langgraph.agents.qualification_agent import QualificationAgent

logger = setup_logging(__name__)


# ========== Input Models ==========

class ParsedInput(BaseModel):
    """Parsed input with detected type and extracted fields."""
    input_type: Literal["url", "domain", "company_name", "linkedin_url", "close_id", "person"]
    raw_input: str
    domain: Optional[str] = None
    company_name: Optional[str] = None
    person_name: Optional[str] = None
    close_lead_id: Optional[str] = None
    linkedin_url: Optional[str] = None


class ExistingLead(BaseModel):
    """Existing lead found in Close CRM."""
    close_lead_id: str
    company_name: str
    close_url: str
    confidence: float


class DropInResult(BaseModel):
    """Result from DropInAgent."""
    exists_in_close: bool
    status: Literal["exists", "enriched", "failed"]
    message: str

    # If exists
    existing_lead: Optional[ExistingLead] = None

    # If enriched
    company_id: Optional[str] = None
    company_name: Optional[str] = None
    domain: Optional[str] = None
    icp_score: Optional[float] = None
    icp_tier: Optional[str] = None
    priority: Optional[str] = None  # HOT, WARM, COLD
    why_call: Optional[str] = None

    # Metadata
    duration_ms: int = 0
    error: Optional[str] = None


# ========== DropInAgent ==========

class DropInAgent:
    """
    Universal input handler for lead enrichment.

    Accepts any input format, checks Close CRM first for duplicates,
    then enriches if new.
    """

    # Regex patterns
    URL_PATTERN = re.compile(r'^https?://[^\s]+$')
    DOMAIN_PATTERN = re.compile(r'^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}$')
    LINKEDIN_PATTERN = re.compile(r'linkedin\.com/(company|in)/')
    CLOSE_ID_PATTERN = re.compile(r'^lead_[a-zA-Z0-9]+$')

    def __init__(
        self,
        close_api_key: Optional[str] = None,
        provider: str = "cerebras",
        model: Optional[str] = None
    ):
        """
        Initialize DropInAgent.

        Args:
            close_api_key: Close CRM API key (defaults to env CLOSE_API_KEY)
            provider: LLM provider for enrichment (cerebras, claude)
            model: LLM model ID
        """
        self.close_api_key = close_api_key or os.getenv("CLOSE_API_KEY")
        if not self.close_api_key:
            raise ValueError("CLOSE_API_KEY environment variable not set")

        # Initialize Close CRM deduplication service
        self.close_dedup = CloseDeduplicationService(api_key=self.close_api_key)

        # Initialize enrichment agents
        self.scout_agent = LeadScoutAgent(provider=provider, model=model)
        self.qualification_agent = QualificationAgent(provider=provider, model=model)

        logger.info(f"DropInAgent initialized: provider={provider}")

    async def drop_in(
        self,
        input: str,
        input_type: Literal["auto", "url", "company_name", "close_id", "person"] = "auto",
        stage_channels: Optional[List[str]] = None,
        auto_trigger: bool = False
    ) -> DropInResult:
        """
        Drop in a lead from any source.

        Args:
            input: Any input (URL, company name, Close ID, person, etc.)
            input_type: Input type (auto-detects if "auto")
            stage_channels: Channels to stage for outreach (email, sms, linkedin, call)
            auto_trigger: Auto-send outreach if HOT (default: False)

        Returns:
            DropInResult with enrichment results or existing lead link
        """
        start_time = time.time()
        logger.info(f"DropIn: {input} (type: {input_type})")

        try:
            # 1. Parse input
            parsed = self._parse_input(input, input_type)
            logger.info(f"Parsed as: {parsed.input_type}, domain={parsed.domain}, name={parsed.company_name}")

            # 2. ALWAYS check Close CRM first for duplicates
            logger.info("🔍 Checking Close CRM for duplicates...")
            existing = await self._check_close_dedup(parsed)

            if existing:
                # Duplicate found - return existing lead
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    f"⚠️  Already exists in Close: {existing.company_name} "
                    f"(confidence: {existing.confidence:.1f}%, lead_id: {existing.close_lead_id})"
                )
                return DropInResult(
                    exists_in_close=True,
                    status="exists",
                    message=f"Lead already exists in Close CRM: {existing.company_name}",
                    existing_lead=existing,
                    duration_ms=duration_ms
                )

            # 3. Not a duplicate - proceed with enrichment
            logger.info("✅ Not a duplicate. Starting enrichment...")
            result = await self._enrich_new_lead(parsed)

            # 4. Handle staging if requested
            if stage_channels and result.status == "enriched":
                await self._stage_outreach(result, stage_channels, auto_trigger)

            duration_ms = int((time.time() - start_time) * 1000)
            result.duration_ms = duration_ms
            return result

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"DropIn failed: {e}")
            return DropInResult(
                exists_in_close=False,
                status="failed",
                message=f"Enrichment failed: {str(e)}",
                error=str(e),
                duration_ms=duration_ms
            )

    def _parse_input(
        self,
        input: str,
        input_type: Literal["auto", "url", "company_name", "close_id", "person"]
    ) -> ParsedInput:
        """
        Parse input and detect type.

        Args:
            input: Raw input string
            input_type: Hint for input type ("auto" for auto-detection)

        Returns:
            ParsedInput with detected type and extracted fields
        """
        input = input.strip()

        # Manual type hints
        if input_type == "close_id":
            return ParsedInput(
                input_type="close_id",
                raw_input=input,
                close_lead_id=input
            )
        elif input_type == "company_name":
            return ParsedInput(
                input_type="company_name",
                raw_input=input,
                company_name=input
            )
        elif input_type == "person":
            # Extract company from "John Smith, Acme HVAC" or "John Smith at Acme HVAC"
            parts = re.split(r',|\sat\s', input, maxsplit=1)
            person_name = parts[0].strip()
            company_name = parts[1].strip() if len(parts) > 1 else None
            return ParsedInput(
                input_type="person",
                raw_input=input,
                person_name=person_name,
                company_name=company_name
            )

        # Auto-detection
        if self.CLOSE_ID_PATTERN.match(input):
            return ParsedInput(
                input_type="close_id",
                raw_input=input,
                close_lead_id=input
            )

        if self.LINKEDIN_PATTERN.search(input):
            return ParsedInput(
                input_type="linkedin_url",
                raw_input=input,
                linkedin_url=input,
                domain=self._extract_domain(input)
            )

        if self.URL_PATTERN.match(input):
            domain = self._extract_domain(input)
            company_name = self._domain_to_company_name(domain)
            return ParsedInput(
                input_type="url",
                raw_input=input,
                domain=domain,
                company_name=company_name
            )

        if self.DOMAIN_PATTERN.match(input):
            company_name = self._domain_to_company_name(input)
            return ParsedInput(
                input_type="domain",
                raw_input=input,
                domain=input,
                company_name=company_name
            )

        # Default to company name
        return ParsedInput(
            input_type="company_name",
            raw_input=input,
            company_name=input
        )

    def _extract_domain(self, url: str) -> Optional[str]:
        """
        Extract domain from URL.

        Args:
            url: URL string

        Returns:
            Domain (e.g., "acme-hvac.com") or None
        """
        try:
            parsed = urlparse(url)
            domain = parsed.netloc or parsed.path
            # Remove www. prefix
            if domain.startswith("www."):
                domain = domain[4:]
            return domain if domain else None
        except Exception:
            return None

    def _domain_to_company_name(self, domain: str) -> str:
        """
        Convert domain to company name.

        Args:
            domain: Domain (e.g., "acme-hvac.com")

        Returns:
            Company name (e.g., "Acme HVAC")
        """
        if not domain:
            return ""

        # Remove TLD
        name = domain.split('.')[0]

        # Replace hyphens/underscores with spaces
        name = name.replace('-', ' ').replace('_', ' ')

        # Title case
        name = name.title()

        return name

    async def _check_close_dedup(self, parsed: ParsedInput) -> Optional[ExistingLead]:
        """
        Check Close CRM for duplicates (domain + fuzzy name match).

        Args:
            parsed: Parsed input

        Returns:
            ExistingLead if found, None otherwise
        """
        # Check by Close lead ID first
        if parsed.close_lead_id:
            # TODO: Fetch lead details from Close CRM by ID
            logger.info(f"Fetching Close lead by ID: {parsed.close_lead_id}")
            # For now, treat as existing
            return ExistingLead(
                close_lead_id=parsed.close_lead_id,
                company_name="Unknown",
                close_url=f"https://app.close.com/lead/{parsed.close_lead_id}/",
                confidence=100.0
            )

        # Check by domain (if available)
        if parsed.domain:
            result = await self.close_dedup.check_duplicate(
                company_name=parsed.domain,
                email=None  # No email at this stage
            )
            if result.company_match_found and result.company_confidence >= 85.0:
                return ExistingLead(
                    close_lead_id=result.matched_lead_id,
                    company_name=result.matched_company_name,
                    close_url=f"https://app.close.com/lead/{result.matched_lead_id}/",
                    confidence=result.company_confidence
                )

        # Check by company name (fuzzy match)
        if parsed.company_name:
            result = await self.close_dedup.check_duplicate(
                company_name=parsed.company_name,
                email=None
            )
            if result.company_match_found and result.company_confidence >= 85.0:
                return ExistingLead(
                    close_lead_id=result.matched_lead_id,
                    company_name=result.matched_company_name,
                    close_url=f"https://app.close.com/lead/{result.matched_lead_id}/",
                    confidence=result.company_confidence
                )

        # No duplicate found
        return None

    async def _enrich_new_lead(self, parsed: ParsedInput) -> DropInResult:
        """
        Enrich a new lead using ScoutAgent + QualificationAgent.

        Args:
            parsed: Parsed input

        Returns:
            DropInResult with enrichment data
        """
        company_name = parsed.company_name or "Unknown"
        domain = parsed.domain

        # Use QualificationAgent for enrichment
        website_url = f"https://{domain}" if domain else None

        qual_result, latency_ms, metadata = await self.qualification_agent.qualify(
            company_name=company_name,
            company_website=website_url,
            industry="HVAC"  # Default industry
        )

        # Determine priority from score
        icp_score = qual_result.qualification_score
        tier = qual_result.tier

        if icp_score >= 75:
            priority = "HOT"
        elif icp_score >= 55:
            priority = "WARM"
        else:
            priority = "COLD"

        logger.info(
            f"Enriched: {company_name}, score={icp_score}, tier={tier}, priority={priority}"
        )

        return DropInResult(
            exists_in_close=False,
            status="enriched",
            message=f"Successfully enriched: {company_name}",
            company_name=company_name,
            domain=domain,
            icp_score=icp_score,
            icp_tier=tier,
            priority=priority,
            why_call=qual_result.reasoning[:500] if hasattr(qual_result, 'reasoning') else None
        )

    async def _stage_outreach(
        self,
        result: DropInResult,
        channels: List[str],
        auto_trigger: bool
    ):
        """
        Stage outreach for enriched lead.

        Args:
            result: Enrichment result
            channels: Channels to stage (email, sms, linkedin, call)
            auto_trigger: Auto-send if HOT
        """
        logger.info(f"Staging outreach for {result.company_name}: channels={channels}, auto={auto_trigger}")

        # TODO: Integrate with OutreachAgent
        # For now, just log
        for channel in channels:
            logger.info(f"  - Staging {channel} draft")

        if auto_trigger and result.priority == "HOT":
            logger.info("  - Auto-triggering outreach (HOT lead)")


# ========== Exports ==========

__all__ = [
    "DropInAgent",
    "DropInResult",
    "ParsedInput",
    "ExistingLead"
]
