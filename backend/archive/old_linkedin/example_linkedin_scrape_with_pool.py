"""
Example: LinkedIn Company Scraping with Browserbase Session Pool

This demonstrates how to use the session pool for efficient LinkedIn scraping.

Key Benefits:
    - Session reuse: ~7-15 second session creation only happens once per 15 companies
    - Stealth mode: Advanced fingerprint randomization and US proxies
    - Concurrent scraping: Process multiple companies in parallel
    - Auto-rotation: Sessions refresh automatically after max_uses

Usage:
    python example_linkedin_scrape_with_pool.py
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import List, Dict, Any

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.browserbase_session_pool import (
    get_session_pool,
    close_session_pool,
    BrowserbaseSession,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


async def scrape_linkedin_company(
    session: BrowserbaseSession, company_name: str
) -> Dict[str, Any]:
    """
    Scrape a single LinkedIn company page.

    Args:
        session: Browserbase session from pool
        company_name: Company name to search

    Returns:
        Dict with scraped data (employee_count, industry, etc.)
    """
    try:
        from playwright.async_api import async_playwright

        logger.info(f"Scraping LinkedIn for: {company_name}")

        async with async_playwright() as p:
            # Connect to Browserbase session via CDP
            browser = await p.chromium.connect_over_cdp(session.connect_url)

            # Get existing context/page
            contexts = browser.contexts
            if not contexts:
                logger.error("No browser contexts available")
                return {"error": "No browser context"}

            context = contexts[0]
            pages = context.pages

            if not pages:
                page = await context.new_page()
            else:
                page = pages[0]

            # Search LinkedIn via Google (avoids direct LinkedIn rate limits)
            search_url = f"https://www.google.com/search?q=site:linkedin.com/company {company_name}"
            logger.info(f"Navigating to: {search_url}")

            await page.goto(search_url, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(2000)  # Wait for results to render

            # Extract first LinkedIn company link
            linkedin_link = await page.query_selector(
                'a[href*="linkedin.com/company/"]'
            )

            if not linkedin_link:
                logger.warning(f"No LinkedIn company page found for: {company_name}")
                return {"company_name": company_name, "linkedin_found": False}

            linkedin_url = await linkedin_link.get_attribute("href")
            logger.info(f"Found LinkedIn URL: {linkedin_url}")

            # Navigate to LinkedIn company page
            await page.goto(linkedin_url, wait_until="networkidle", timeout=15000)
            await page.wait_for_timeout(3000)  # Wait for page to fully load

            # Extract company data
            result = {"company_name": company_name, "linkedin_url": linkedin_url}

            # Extract employee count
            try:
                employee_element = await page.query_selector(
                    'a[href*="/search/results/people/"]'
                )
                if employee_element:
                    employee_text = await employee_element.inner_text()
                    result["employee_count"] = employee_text.strip()
            except Exception:
                pass

            # Extract industry
            try:
                industry_element = await page.query_selector(
                    'div.org-top-card-summary-info-list__info-item:has-text("Industry")'
                )
                if industry_element:
                    industry_text = await industry_element.inner_text()
                    result["industry"] = industry_text.replace("Industry", "").strip()
            except Exception:
                pass

            # Extract company size
            try:
                size_element = await page.query_selector(
                    'div.org-top-card-summary-info-list__info-item:has-text("employees")'
                )
                if size_element:
                    size_text = await size_element.inner_text()
                    result["company_size"] = size_text.strip()
            except Exception:
                pass

            logger.info(f"✓ Scraped {company_name}: {result}")

            # Close browser connection (session remains in pool)
            await browser.close()

            return result

    except Exception as e:
        logger.error(f"Failed to scrape {company_name}: {e}", exc_info=True)
        return {"company_name": company_name, "error": str(e)}


async def scrape_companies_batch(companies: List[str], max_concurrent: int = 3):
    """
    Scrape multiple companies using session pool.

    Args:
        companies: List of company names to scrape
        max_concurrent: Max concurrent scrapes (default: 3)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Scraping {len(companies)} companies (max_concurrent={max_concurrent})")
    logger.info(f"{'='*60}\n")

    pool = await get_session_pool()
    results = []

    # Warm up pool with initial sessions
    await pool.warm_up(count=min(3, max_concurrent))

    # Show initial pool stats
    stats = await pool.get_pool_stats()
    logger.info(f"Initial pool stats: {stats}\n")

    async def scrape_one(company: str):
        """Scrape one company with session management."""
        session = await pool.checkout()
        try:
            result = await scrape_linkedin_company(session, company)
            return result
        finally:
            await pool.checkin(session)

    # Process companies in batches
    for i in range(0, len(companies), max_concurrent):
        batch = companies[i : i + max_concurrent]
        logger.info(f"Processing batch {i//max_concurrent + 1}: {batch}")

        batch_results = await asyncio.gather(
            *[scrape_one(company) for company in batch], return_exceptions=True
        )

        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Batch scrape error: {result}")
            else:
                results.append(result)

        # Show pool stats after batch
        stats = await pool.get_pool_stats()
        logger.info(f"Pool stats after batch: {stats}\n")

    return results


async def main():
    """Run example LinkedIn scraping with session pool."""
    logger.info("\n" + "=" * 60)
    logger.info("LINKEDIN COMPANY SCRAPING EXAMPLE")
    logger.info("=" * 60)

    # Example companies to scrape
    companies = [
        "Anthropic",
        "OpenAI",
        "Google DeepMind",
        "Mistral AI",
        "Cohere",
        "Hugging Face",
    ]

    try:
        # Scrape companies
        results = await scrape_companies_batch(companies, max_concurrent=3)

        # Print results
        logger.info("\n" + "=" * 60)
        logger.info("SCRAPING RESULTS")
        logger.info("=" * 60)

        for result in results:
            logger.info(f"\n{result.get('company_name', 'Unknown')}:")
            for key, value in result.items():
                if key != "company_name":
                    logger.info(f"  {key}: {value}")

        # Final pool stats
        pool = await get_session_pool()
        stats = await pool.get_pool_stats()
        logger.info(f"\nFinal pool stats: {stats}")

        logger.info("\n" + "=" * 60)
        logger.info(f"✅ Scraped {len(results)} companies successfully")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Example failed: {e}", exc_info=True)
        return 1

    finally:
        # Cleanup pool on exit
        await close_session_pool()
        logger.info("Session pool closed")

    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
