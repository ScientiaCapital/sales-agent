"""Hunter.io and Browserbase discovery stages."""
import time
from typing import Any

from app.core.logging import setup_logging
from app.services.hunter_service import HunterService, extract_domain
from app.services.browserbase_team_scraper import get_browserbase_team_scraper
from app.services.contact_discovery_audit import DiscoveryMethod
from .discovery_context import DiscoveryContext
from .classification import is_atl_title

logger = setup_logging(__name__)


async def search_hunter(
    ctx: DiscoveryContext,
    hunter_service: HunterService,
    audit: Any
) -> None:
    """Stage 1: Hunter.io domain search for contacts."""
    if not ctx.company_website:
        return

    domain = extract_domain(ctx.company_website)
    start = time.time()

    try:
        contacts = await hunter_service.domain_search(
            domain=domain, limit=10, atl_only=False
        )
        latency = int((time.time() - start) * 1000)

        if contacts:
            atl_count, btl_count = 0, 0
            for contact in contacts:
                email = contact.get('email', '').lower()
                if email and email not in ctx.seen_emails:
                    contact['source'] = 'hunter'
                    ctx.all_contacts.append(contact)
                    ctx.seen_emails.add(email)
                    if contact.get('is_atl'):
                        atl_count += 1
                    else:
                        btl_count += 1

            audit.log_attempt(
                DiscoveryMethod.HUNTER_DOMAIN_SEARCH,
                success=True, contacts=len(contacts),
                atl=atl_count, btl=btl_count,
                latency_ms=latency, cost_usd=0.01,
                contacts_data=contacts
            )
            logger.info(f"Hunter.io found {len(contacts)} contacts for {ctx.company_name}")
        else:
            audit.log_attempt(
                DiscoveryMethod.HUNTER_DOMAIN_SEARCH,
                success=True, contacts=0, latency_ms=latency,
                reason="No contacts found"
            )
    except Exception as e:
        latency = int((time.time() - start) * 1000)
        audit.log_attempt(
            DiscoveryMethod.HUNTER_DOMAIN_SEARCH,
            success=False, latency_ms=latency, reason=str(e)
        )
        logger.warning(f"Hunter.io domain search failed: {e}")


async def scrape_browserbase_team(
    ctx: DiscoveryContext,
    audit: Any
) -> None:
    """Stage 1.5: Browserbase team page scraping for JS-heavy sites."""
    if not ctx.company_website:
        return

    # Only run if Hunter found <3 ATL contacts
    current_atl = [c for c in ctx.all_contacts if c.get('is_atl')]
    if len(current_atl) >= 3:
        return

    start = time.time()
    try:
        scraper = await get_browserbase_team_scraper()
        team_contacts = await scraper.scrape_team_page(ctx.company_website)
        latency = int((time.time() - start) * 1000)

        if not team_contacts:
            audit.log_attempt(
                DiscoveryMethod.BROWSERBASE_TEAM,
                success=True, contacts=0, latency_ms=latency,
                reason="No team page found or no contacts extracted"
            )
            return

        new_atl, new_btl = 0, 0
        for contact in team_contacts:
            email = contact.get('email', '').lower()
            if email and email not in ctx.seen_emails:
                is_atl = is_atl_title(contact.get('title', ''))
                normalized = {
                    'email': email,
                    'first_name': contact.get('name', '').split()[0] if contact.get('name') else '',
                    'last_name': ' '.join(contact.get('name', '').split()[1:]) if contact.get('name') else '',
                    'position': contact.get('title', ''),
                    'is_atl': is_atl,
                    'source': 'browserbase_team'
                }
                ctx.all_contacts.append(normalized)
                ctx.seen_emails.add(email)
                if is_atl:
                    new_atl += 1
                else:
                    new_btl += 1
            elif contact.get('name') and not email:
                # Contact without email - still valuable for BTL marketing
                normalized = {
                    'email': '',
                    'first_name': contact.get('name', '').split()[0] if contact.get('name') else '',
                    'last_name': ' '.join(contact.get('name', '').split()[1:]) if contact.get('name') else '',
                    'position': contact.get('title', ''),
                    'is_atl': is_atl_title(contact.get('title', '')),
                    'source': 'browserbase_team',
                    'needs_email': True
                }
                ctx.all_contacts.append(normalized)
                if normalized['is_atl']:
                    new_atl += 1
                else:
                    new_btl += 1

        audit.log_attempt(
            DiscoveryMethod.BROWSERBASE_TEAM,
            success=True, contacts=len(team_contacts),
            atl=new_atl, btl=new_btl,
            latency_ms=latency, cost_usd=0.01,
            reason=f"Team page scraped: {new_atl} new ATL, {new_btl} new BTL"
        )
        logger.info(f"Browserbase found {len(team_contacts)} team members")

    except Exception as e:
        latency = int((time.time() - start) * 1000)
        audit.log_attempt(
            DiscoveryMethod.BROWSERBASE_TEAM,
            success=False, latency_ms=latency, reason=str(e)
        )
        logger.warning(f"Browserbase team scraping failed: {e}")


__all__ = ["search_hunter", "scrape_browserbase_team"]
