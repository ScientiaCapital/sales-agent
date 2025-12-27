"""Qualification workflow: Core qualify() logic extracted from agent."""
import time
from typing import Optional, List, Dict, Any, Tuple

from app.core.logging import setup_logging
from app.core.cost_optimized_llm import LLMConfig
from app.services.website_validator import get_website_validator
from app.services.review_scraper import get_review_scraper
from app.services.contact_discovery_audit import DiscoveryMethod, get_discovery_audit

from .schemas import LeadQualificationResult, PROVIDER_PRICING
from .prompting import format_optional_fields, build_full_prompt, parse_json_response
from .discovery_context import DiscoveryContext
from .discovery_website import discover_website, scrape_website_emails, finalize_contacts
from .discovery_hunter import search_hunter, scrape_browserbase_team

logger = setup_logging(__name__)


async def run_contact_discovery(
    ctx: DiscoveryContext,
    audit: Any,
    hunter_service: Any,
    email_extractor: Any
) -> Tuple[Optional[str], List[Dict[str, Any]]]:
    """Run all contact discovery stages."""
    # Stage 0: Website discovery
    if not ctx.company_website:
        ctx.company_website = await discover_website(ctx, audit)
        if ctx.company_website:
            audit.company_website = ctx.company_website

    if not ctx.company_website:
        return None, []

    # Website validation
    validator = await get_website_validator()
    website_result = await validator.validate(ctx.company_website)

    if not website_result.is_valid:
        logger.warning(f"Website validation failed for {ctx.company_name}")
        return "DISQUALIFY", []

    # Stage 1: Hunter.io search
    await search_hunter(ctx, hunter_service, audit)

    # Log Apollo as disabled
    audit.log_disabled_method(
        DiscoveryMethod.APOLLO_DOMAIN_SEARCH,
        "DISABLED: Set APOLLO_ENABLED=true when credits purchased"
    )

    finalize_contacts(ctx)

    # Stage 1.5: Browserbase team scraping
    await scrape_browserbase_team(ctx, audit)

    # Update primary email
    contact_email = None
    if ctx.atl_contacts:
        contact_email = ctx.atl_contacts[0].get('email')
    elif ctx.btl_contacts:
        contact_email = ctx.btl_contacts[0].get('email')

    # Stage 2: Website email scraping fallback
    if not contact_email:
        await scrape_website_emails(ctx, email_extractor, audit)
        contact_email = ctx.primary_email

    return contact_email, ctx.all_contacts


async def scrape_reviews(
    ctx: DiscoveryContext,
    audit: Any
) -> None:
    """Scrape reviews for reputation scoring."""
    start = time.time()
    try:
        scraper = await get_review_scraper()
        review_result = await scraper.get_reviews(ctx.company_name, ctx.company_website)
        latency = int((time.time() - start) * 1000)

        ctx.notes += "\n\nREPUTATION DATA:\n"
        ctx.notes += f"- Overall Reputation Score: {review_result.overall_reputation_score}/100\n"
        ctx.notes += f"- Average Rating: {review_result.average_rating}/5.0\n"
        ctx.notes += f"- Total Reviews: {review_result.total_reviews}\n"

        audit.log_attempt(
            DiscoveryMethod.REVIEW_SCRAPING,
            success=True, contacts=0, latency_ms=latency, cost_usd=0.0,
            reason=f"Score: {review_result.overall_reputation_score}/100"
        )
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        audit.log_attempt(
            DiscoveryMethod.REVIEW_SCRAPING,
            success=False, latency_ms=latency, reason=str(e)
        )


def disqualify_no_website(website_result) -> Tuple[LeadQualificationResult, int, Dict]:
    """Return disqualification result for inaccessible website."""
    return (
        LeadQualificationResult(
            qualification_score=0.0,
            qualification_reasoning=f"Website not accessible ({website_result.error_message})",
            tier="unqualified",
            fit_assessment="No digital presence",
            contact_quality="Cannot assess",
            sales_potential="Zero - company appears non-operational"
        ),
        0,
        {
            "provider": "website_validator",
            "disqualified_reason": "website_not_accessible",
            "website_error": website_result.error_message
        }
    )


async def call_llm(
    chain: Any,
    cost_provider: Any,
    company_name: str,
    optional_fields: str,
    lead_id: Optional[int],
    provider: str,
    model: str,
    max_tokens: int,
    temperature: float
) -> Tuple[LeadQualificationResult, int, str]:
    """Call LLM for qualification (cost-optimized or direct)."""
    start_time = time.time()

    if cost_provider:
        full_prompt = build_full_prompt(company_name, optional_fields)
        config = LLMConfig(
            agent_type="qualification",
            lead_id=lead_id,
            mode="passthrough",
            provider=provider,
            model=model
        )
        cost_result = await cost_provider.complete(
            prompt=full_prompt, config=config,
            max_tokens=max_tokens, temperature=temperature
        )
        response_text = cost_result["response"]
        latency_ms = cost_result.get("latency_ms", 0)
    else:
        response = await chain.ainvoke({
            "company_name": company_name,
            "optional_fields": optional_fields
        })
        response_text = response.content if hasattr(response, 'content') else str(response)
        latency_ms = int((time.time() - start_time) * 1000)

    result = parse_json_response(response_text)
    return result, latency_ms, response_text


def build_metadata(
    provider: str,
    model: str,
    temperature: float,
    latency_ms: int,
    contact_email: Optional[str],
    ctx: DiscoveryContext,
    discovered_contacts: List,
    company_website: Optional[str],
    audit: Any
) -> Dict[str, Any]:
    """Build qualification metadata."""
    estimated_tokens = 500
    cost_per_m = PROVIDER_PRICING.get(provider, {}).get(
        model, PROVIDER_PRICING.get(provider, {}).get("*", 0)
    )

    return {
        "provider": provider,
        "model": model,
        "temperature": temperature,
        "latency_ms": latency_ms,
        "agent_type": "qualification",
        "estimated_cost_usd": round((estimated_tokens / 1_000_000) * cost_per_m, 6),
        "extracted_email": contact_email,
        "extraction_method": ctx.extraction_method,
        "hunter_cost_usd": ctx.discovery_cost,
        "discovered_contacts": discovered_contacts,
        "discovered_website": company_website,
        "discovery_audit": audit.get_summary()
    }


__all__ = [
    "run_contact_discovery", "scrape_reviews",
    "disqualify_no_website", "call_llm", "build_metadata"
]
