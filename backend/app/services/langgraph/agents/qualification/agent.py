"""QualificationAgent: Multi-provider lead qualification facade."""
import os
import asyncio
from typing import Optional, List, Dict, Any, Literal, Tuple, Union
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import setup_logging
from app.core.exceptions import CerebrasAPIError
from app.core.cost_optimized_llm import CostOptimizedLLMProvider
from app.services.cache.qualification_cache import get_qualification_cache
from app.services.email_extractor import EmailExtractor
from app.services.hunter_service import HunterService
from app.services.apollo import ApolloService
from app.services.contact_discovery_audit import get_discovery_audit

from .schemas import LeadQualificationResult
from .llm_factory import initialize_llm, get_default_model
from .classification import is_atl_title
from .prompting import build_qualification_chain, format_optional_fields
from .discovery_context import DiscoveryContext
from .qualify_workflow import (
    run_contact_discovery, scrape_reviews,
    disqualify_no_website, call_llm, build_metadata
)

logger = setup_logging(__name__)


class QualificationAgent:
    """Multi-provider lead qualification agent with free-form JSON generation."""

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
        self.provider, self.temperature, self.max_tokens = provider, temperature, max_tokens
        self.use_cache, self.cache, self.track_costs, self.db = use_cache, None, track_costs, db
        self.model = model or get_default_model(provider)
        self.cost_provider = None
        if db:
            try:
                self.cost_provider = CostOptimizedLLMProvider(db)
            except Exception as e:
                logger.error(f"Failed to initialize cost tracking: {e}")

        self.llm = initialize_llm(provider, self.model, temperature, max_tokens)
        self.chain = build_qualification_chain(self.llm)
        self.email_extractor = EmailExtractor()
        self.hunter_service = HunterService()
        self.apollo_service = None
        if os.getenv("APOLLO_ENABLED", "false").lower() == "true":
            try:
                self.apollo_service = ApolloService()
            except Exception as e:
                logger.warning(f"Apollo not available: {e}")
        logger.info(f"QualificationAgent initialized: {provider}/{self.model}")

    def _is_atl_title(self, title: str) -> bool:
        return is_atl_title(title)

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
        company_phone: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Tuple[LeadQualificationResult, int, Dict[str, Any]]:
        if not company_name:
            raise ValueError("company_name is required")

        discovered_contacts = []
        audit = get_discovery_audit(
            company_name=company_name,
            company_website=company_website,
            session_id=str(lead_id) if lead_id else None,
            create_new=True
        )

        ctx = DiscoveryContext(
            company_name=company_name,
            company_website=company_website,
            company_phone=company_phone,
            industry=industry,
            lead_id=lead_id,
            notes=notes or ""
        )

        # Run contact discovery if no email provided
        if not contact_email:
            result = await run_contact_discovery(
                ctx, audit, self.hunter_service, self.email_extractor
            )
            if result[0] == "DISQUALIFY":
                from app.services.website_validator import get_website_validator
                validator = await get_website_validator()
                website_result = await validator.validate(ctx.company_website)
                return disqualify_no_website(website_result)

            contact_email = result[0]
            discovered_contacts = result[1]
            company_website = ctx.company_website

            # Scrape reviews
            if company_website:
                await scrape_reviews(ctx, audit)
                ctx.notes += audit.get_qualification_notes()
                notes = ctx.notes
        else:
            ctx.extraction_method = "provided"

        # Cache check
        if self.use_cache and self.cache is None:
            self.cache = await get_qualification_cache()

        if self.use_cache:
            cached = await self.cache.get_qualification(company_name, industry)
            if cached:
                result = LeadQualificationResult(**cached["result"])
                meta = cached["metadata"].copy()
                if discovered_contacts:
                    meta["discovered_contacts"] = discovered_contacts
                meta["discovery_audit"] = audit.get_summary()
                return result, cached["latency_ms"], meta

        # LLM call
        optional_fields = format_optional_fields(
            company_website=company_website,
            company_size=company_size,
            industry=industry,
            contact_name=contact_name,
            contact_title=contact_title,
            notes=notes
        )

        try:
            result, latency_ms, _ = await call_llm(
                self.chain, self.cost_provider, company_name, optional_fields,
                lead_id, self.provider, self.model, self.max_tokens, self.temperature
            )
        except Exception as e:
            logger.error(f"Lead qualification failed: {e}", exc_info=True)
            raise CerebrasAPIError(
                message=f"Lead qualification failed with {self.provider}",
                details={"company_name": company_name, "error": str(e)}
            )

        metadata = build_metadata(
            self.provider, self.model, self.temperature, latency_ms,
            contact_email, ctx, discovered_contacts, company_website, audit
        )

        logger.info(f"Lead qualified: {company_name}, score={result.qualification_score}")

        # Cache result
        if self.use_cache:
            await self.cache.set_qualification(company_name, industry, {
                "result": result.model_dump(),
                "latency_ms": latency_ms,
                "metadata": metadata
            })

        return result, latency_ms, metadata

    def get_transfer_tools(self):
        """Get agent transfer tools for qualification workflows."""
        from app.services.langgraph.tools import get_transfer_tools
        return get_transfer_tools("qualification")

    async def qualify_batch(
        self,
        leads: List[Dict[str, Any]],
        max_concurrency: int = 5
    ) -> List[Tuple[LeadQualificationResult, int, Dict[str, Any]]]:
        """Qualify multiple leads in parallel."""
        semaphore = asyncio.Semaphore(max_concurrency)

        async def qualify_with_semaphore(lead: Dict[str, Any]):
            async with semaphore:
                return await self.qualify(**lead)

        tasks = [qualify_with_semaphore(lead) for lead in leads]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return [r for r in results if not isinstance(r, Exception)]


__all__ = ["QualificationAgent"]
