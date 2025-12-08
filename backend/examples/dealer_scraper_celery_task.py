"""
Example Celery Task for dealer-scraper-mvp

Copy this to: dealer-scraper-mvp/tasks.py

This task pushes scraped contractors and contacts to the sales-agent API.
"""

import httpx
from celery import shared_task
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Configuration
SALES_AGENT_API_URL = "http://localhost:8001/api/v1/scraper"  # Change for production
BATCH_SIZE = 100  # Number of records per batch
HTTP_TIMEOUT = 120.0  # 2 minutes for large batches


@shared_task(name="push_contractors_to_sales_agent", bind=True, max_retries=3)
def push_contractors_to_sales_agent(self, contractors: list, source_scraper: str):
    """
    Push batch of scraped contractors to sales-agent API.

    Args:
        contractors: List of contractor dicts with keys:
            - company_name (required)
            - normalized_name (required)
            - state (required)
            - source_scraper (required)
            - phone, email, domain (optional)
            - oem_brands, certifications, service_areas (optional arrays)
        source_scraper: Source identifier (e.g., 'carrier', 'generac', 'enphase')

    Returns:
        dict: Sync result with inserted/updated/skipped counts

    Raises:
        httpx.HTTPError: On HTTP errors (will retry)
        Exception: On validation errors (won't retry)
    """
    batch_id = f"{source_scraper}_contractors_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"Pushing {len(contractors)} contractors to sales-agent (batch_id: {batch_id})")

    payload = {
        "contractors": contractors,
        "batch_id": batch_id,
        "source_scraper": source_scraper
    }

    try:
        response = httpx.post(
            f"{SALES_AGENT_API_URL}/contractors",
            json=payload,
            timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()

        logger.info(
            f"✅ Contractor sync complete: "
            f"{result['inserted']} inserted, "
            f"{result['updated']} updated, "
            f"{result['skipped']} skipped"
        )

        if result.get('errors'):
            logger.warning(f"⚠️ {len(result['errors'])} errors occurred during sync")
            for error in result['errors']:
                logger.warning(f"  - {error['company_name']}: {error['error']}")

        return result

    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP error pushing contractors: {e}")
        # Retry on HTTP errors (5xx, timeouts)
        raise self.retry(exc=e, countdown=60)  # Retry after 60 seconds

    except Exception as e:
        logger.error(f"❌ Validation error pushing contractors: {e}")
        # Don't retry on validation errors (4xx)
        raise


@shared_task(name="push_contacts_to_sales_agent", bind=True, max_retries=3)
def push_contacts_to_sales_agent(self, contacts: list, source_scraper: str):
    """
    Push batch of scraped contacts to sales-agent API.

    Args:
        contacts: List of contact dicts with keys:
            - company_name (required) - Must match contractor.company_name
            - normalized_company_name (required) - Must match contractor.normalized_name
            - full_name (required)
            - source_scraper (required)
            - email, phone, title (optional)
            - is_decision_maker (optional, boolean)
        source_scraper: Source identifier

    Returns:
        dict: Sync result with inserted/updated/skipped counts

    Raises:
        httpx.HTTPError: On HTTP errors (will retry)
        Exception: On validation errors (won't retry)
    """
    batch_id = f"{source_scraper}_contacts_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    logger.info(f"Pushing {len(contacts)} contacts to sales-agent (batch_id: {batch_id})")

    payload = {
        "contacts": contacts,
        "batch_id": batch_id,
        "source_scraper": source_scraper
    }

    try:
        response = httpx.post(
            f"{SALES_AGENT_API_URL}/contacts",
            json=payload,
            timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()

        result = response.json()

        logger.info(
            f"✅ Contact sync complete: "
            f"{result['inserted']} inserted, "
            f"{result['updated']} updated, "
            f"{result['skipped']} skipped"
        )

        if result.get('errors'):
            logger.warning(f"⚠️ {len(result['errors'])} errors occurred during sync")
            for error in result['errors']:
                logger.warning(f"  - {error['contact_name']}: {error['error']}")

        return result

    except httpx.HTTPError as e:
        logger.error(f"❌ HTTP error pushing contacts: {e}")
        raise self.retry(exc=e, countdown=60)

    except Exception as e:
        logger.error(f"❌ Validation error pushing contacts: {e}")
        raise


@shared_task(name="push_scrape_results_to_sales_agent")
def push_scrape_results_to_sales_agent(
    contractors: list,
    contacts: list,
    source_scraper: str
):
    """
    Push both contractors and contacts in sequence.

    This is the main entry point for dealer-scraper-mvp scrapers.

    Args:
        contractors: List of contractor dicts
        contacts: List of contact dicts
        source_scraper: Source identifier (e.g., 'carrier', 'generac')

    Returns:
        dict: Combined results from both syncs

    Example:
        >>> from tasks import push_scrape_results_to_sales_agent
        >>> contractors = [
        ...     {
        ...         "company_name": "ABC HVAC",
        ...         "normalized_name": "abc hvac",
        ...         "phone": "5551234567",
        ...         "domain": "abchvac.com",
        ...         "state": "tx",
        ...         "oem_brands": ["Carrier", "Trane"],
        ...         "source_scraper": "carrier"
        ...     }
        ... ]
        >>> contacts = [
        ...     {
        ...         "company_name": "ABC HVAC",
        ...         "normalized_company_name": "abc hvac",
        ...         "full_name": "John Smith",
        ...         "email": "john@abchvac.com",
        ...         "title": "Owner",
        ...         "is_decision_maker": True,
        ...         "source_scraper": "carrier"
        ...     }
        ... ]
        >>> result = push_scrape_results_to_sales_agent(contractors, contacts, "carrier")
    """
    results = {}

    # Step 1: Push contractors first (required for contacts)
    if contractors:
        logger.info(f"Step 1/2: Pushing {len(contractors)} contractors...")
        contractor_result = push_contractors_to_sales_agent(contractors, source_scraper)
        results['contractors'] = contractor_result
    else:
        logger.info("No contractors to push")
        results['contractors'] = None

    # Step 2: Push contacts (requires companies to exist)
    if contacts:
        logger.info(f"Step 2/2: Pushing {len(contacts)} contacts...")
        contact_result = push_contacts_to_sales_agent(contacts, source_scraper)
        results['contacts'] = contact_result
    else:
        logger.info("No contacts to push")
        results['contacts'] = None

    # Summary
    total_contractors = results['contractors']['inserted'] + results['contractors']['updated'] if results['contractors'] else 0
    total_contacts = results['contacts']['inserted'] + results['contacts']['updated'] if results['contacts'] else 0

    logger.info(
        f"🎉 Sync complete: {total_contractors} contractors, {total_contacts} contacts synced to sales-agent"
    )

    return results


# ============================================================================
# USAGE EXAMPLE FROM SCRAPER
# ============================================================================

def example_scraper_usage():
    """
    Example: How to use this from a scraper in dealer-scraper-mvp.

    In your scraper (e.g., carrier_scraper.py):
    """

    from tasks import push_scrape_results_to_sales_agent

    # Scrape dealers
    contractors = []
    contacts = []

    for dealer in scrape_carrier_dealers():  # Your scraping logic
        # Add contractor
        contractors.append({
            "company_name": dealer["name"],
            "normalized_name": normalize_name(dealer["name"]),  # Your normalization function
            "phone": dealer.get("phone"),
            "domain": extract_domain(dealer.get("website")),
            "state": dealer["state"].lower(),
            "city": dealer.get("city"),
            "oem_brands": ["Carrier"],
            "certifications": dealer.get("certifications", []),
            "service_areas": dealer.get("service_areas", []),
            "source_scraper": "carrier"
        })

        # Add contacts if available
        if dealer.get("contacts"):
            for contact in dealer["contacts"]:
                contacts.append({
                    "company_name": dealer["name"],
                    "normalized_company_name": normalize_name(dealer["name"]),
                    "full_name": contact["name"],
                    "email": contact.get("email"),
                    "phone": contact.get("phone"),
                    "title": contact.get("title"),
                    "is_decision_maker": is_decision_maker_title(contact.get("title")),
                    "source_scraper": "carrier"
                })

    # Push to sales-agent (async via Celery)
    push_scrape_results_to_sales_agent.delay(contractors, contacts, "carrier")

    print(f"Queued {len(contractors)} contractors and {len(contacts)} contacts for sync")


# ============================================================================
# BATCH PROCESSING FOR LARGE SCRAPES
# ============================================================================

@shared_task(name="push_large_scrape_in_batches")
def push_large_scrape_in_batches(
    all_contractors: list,
    all_contacts: list,
    source_scraper: str,
    batch_size: int = 100
):
    """
    Process large scrape results in batches.

    Useful for scrapers that return 1000+ results.

    Args:
        all_contractors: Full list of contractors
        all_contacts: Full list of contacts
        source_scraper: Source identifier
        batch_size: Number of records per batch (default: 100)

    Returns:
        dict: Aggregated results from all batches
    """
    from celery import group

    # Split contractors into batches
    contractor_batches = [
        all_contractors[i:i + batch_size]
        for i in range(0, len(all_contractors), batch_size)
    ]

    # Split contacts into batches
    contact_batches = [
        all_contacts[i:i + batch_size]
        for i in range(0, len(all_contacts), batch_size)
    ]

    logger.info(
        f"Processing {len(all_contractors)} contractors in {len(contractor_batches)} batches, "
        f"{len(all_contacts)} contacts in {len(contact_batches)} batches"
    )

    # Push contractors in parallel
    contractor_job = group(
        push_contractors_to_sales_agent.s(batch, source_scraper)
        for batch in contractor_batches
    )
    contractor_results = contractor_job.apply_async()

    # Wait for contractors to finish before pushing contacts
    contractor_results.join()

    # Push contacts in parallel
    contact_job = group(
        push_contacts_to_sales_agent.s(batch, source_scraper)
        for batch in contact_batches
    )
    contact_results = contact_job.apply_async()

    # Wait for all to finish
    contact_results.join()

    logger.info("🎉 All batches processed successfully")

    return {
        "contractor_batches": len(contractor_batches),
        "contact_batches": len(contact_batches),
        "total_contractors": len(all_contractors),
        "total_contacts": len(all_contacts)
    }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def normalize_name(name: str) -> str:
    """
    Normalize company name for deduplication.

    Example:
        >>> normalize_name("ABC HVAC & Plumbing, LLC")
        'abc hvac plumbing'
    """
    import re

    # Remove common suffixes
    name = re.sub(r'\b(LLC|Inc|Corp|Ltd|Co)\b', '', name, flags=re.IGNORECASE)

    # Remove punctuation
    name = re.sub(r'[^\w\s]', '', name)

    # Remove extra whitespace and lowercase
    name = ' '.join(name.lower().split())

    return name


def is_decision_maker_title(title: str) -> bool:
    """
    Check if title indicates decision maker (ATL).

    Example:
        >>> is_decision_maker_title("Owner")
        True
        >>> is_decision_maker_title("Technician")
        False
    """
    if not title:
        return False

    atl_keywords = [
        "owner", "president", "ceo", "cfo", "cto",
        "vp", "vice president", "director", "manager",
        "partner", "founder", "chief"
    ]

    title_lower = title.lower()
    return any(keyword in title_lower for keyword in atl_keywords)


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.

    Example:
        >>> extract_domain("https://www.abchvac.com/about")
        'abchvac.com'
    """
    if not url:
        return None

    from urllib.parse import urlparse

    parsed = urlparse(url)
    domain = parsed.netloc or parsed.path

    # Remove www.
    domain = domain.replace('www.', '')

    return domain.lower() if domain else None
