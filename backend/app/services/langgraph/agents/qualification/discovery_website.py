"""Website discovery and email scraping stages."""
import time
from typing import Optional, Any

from app.core.logging import setup_logging
from app.services.website_discovery import get_website_discovery_service
from app.services.email_extractor import EmailExtractor
from app.services.contact_discovery_audit import DiscoveryMethod
from .discovery_context import DiscoveryContext
from .classification import classify_phones

logger = setup_logging(__name__)


async def discover_website(
    ctx: DiscoveryContext,
    audit: Any
) -> Optional[str]:
    """Stage 0: Discover website if missing via Google search."""
    if ctx.company_website:
        return ctx.company_website

    logger.info(f"No website provided for {ctx.company_name}, attempting discovery...")
    start = time.time()

    try:
        discovery_service = await get_website_discovery_service()
        website = await discovery_service.discover_website(
            company_name=ctx.company_name,
            industry=ctx.industry or "",
            state=""
        )
        latency = int((time.time() - start) * 1000)

        if website:
            audit.log_attempt(
                DiscoveryMethod.WEBSITE_DISCOVERY,
                success=True, contacts=0, latency_ms=latency,
                reason=f"Found: {website}"
            )
            logger.info(f"✅ Discovered website for {ctx.company_name}: {website}")
            return website
        else:
            audit.log_attempt(
                DiscoveryMethod.WEBSITE_DISCOVERY,
                success=True, contacts=0, latency_ms=latency,
                reason="No website found via search"
            )
            return None

    except Exception as e:
        latency = int((time.time() - start) * 1000)
        audit.log_attempt(
            DiscoveryMethod.WEBSITE_DISCOVERY,
            success=False, latency_ms=latency, reason=str(e)
        )
        logger.warning(f"Website discovery failed for {ctx.company_name}: {e}")
        return None


async def scrape_website_emails(
    ctx: DiscoveryContext,
    email_extractor: EmailExtractor,
    audit: Any
) -> None:
    """Stage 2: Website email scraping fallback (FREE)."""
    if ctx.primary_email or not ctx.company_website:
        return

    start = time.time()
    try:
        extracted = await email_extractor.extract_emails(ctx.company_website)
        latency = int((time.time() - start) * 1000)

        if extracted:
            ctx.primary_email = extracted[0]
            ctx.extraction_method = "scraping"
            audit.log_attempt(
                DiscoveryMethod.WEBSITE_EMAIL_SCRAPE,
                success=True, contacts=len(extracted),
                atl=0, btl=len(extracted),
                latency_ms=latency, cost_usd=0.0,
                reason=f"Emails: {', '.join(extracted[:3])}"
            )
            logger.info(f"Website scraping found {len(extracted)} emails")
            ctx.notes += f"\nEmails found (scraping): {', '.join(extracted[:3])}"
        else:
            audit.log_attempt(
                DiscoveryMethod.WEBSITE_EMAIL_SCRAPE,
                success=True, contacts=0, latency_ms=latency,
                reason="No emails found on website"
            )
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        audit.log_attempt(
            DiscoveryMethod.WEBSITE_EMAIL_SCRAPE,
            success=False, latency_ms=latency, reason=str(e)
        )
        logger.error(f"Website scraping failed: {e}")


def finalize_contacts(ctx: DiscoveryContext) -> None:
    """Finalize contact lists and select primary email."""
    if not ctx.all_contacts:
        return

    # Classify phones
    ctx.all_contacts = classify_phones(ctx.all_contacts, ctx.company_phone)
    ctx.extraction_method = "hunter_apollo_search"
    ctx.discovery_cost = len(ctx.all_contacts) * 0.01

    # Separate ATL and BTL
    ctx.atl_contacts = [c for c in ctx.all_contacts if c.get('is_atl')]
    ctx.btl_contacts = [c for c in ctx.all_contacts if not c.get('is_atl')]

    # Select primary email
    if ctx.atl_contacts:
        ctx.primary_email = ctx.atl_contacts[0].get("email")
    elif ctx.all_contacts:
        ctx.primary_email = ctx.all_contacts[0].get("email")

    # Build contact notes
    if ctx.atl_contacts:
        atl_summary = ", ".join([
            f"{c['first_name']} {c['last_name']} ({c['position']}) [{c.get('source', 'unknown')}]"
            for c in ctx.atl_contacts[:5]
        ])
        ctx.notes += f"\n\nATL CONTACTS ({len(ctx.atl_contacts)} found):\n{atl_summary}"
        if len(ctx.atl_contacts) > 5:
            ctx.notes += f"\n+ {len(ctx.atl_contacts) - 5} more ATL contacts"

    if ctx.btl_contacts:
        btl_summary = ", ".join([
            f"{c['first_name']} {c['last_name']} ({c['position']}) [{c.get('source', 'unknown')}]"
            for c in ctx.btl_contacts[:3]
        ])
        ctx.notes += f"\n\nBTL CONTACTS (for marketing):\n{btl_summary}"
        if len(ctx.btl_contacts) > 3:
            ctx.notes += f"\n+ {len(ctx.btl_contacts) - 3} more BTL contacts"

    logger.info(
        f"Total: {len(ctx.all_contacts)} contacts "
        f"({len(ctx.atl_contacts)} ATL, {len(ctx.btl_contacts)} BTL)"
    )


__all__ = ["discover_website", "scrape_website_emails", "finalize_contacts"]
