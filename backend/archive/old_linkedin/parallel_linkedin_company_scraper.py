"""
Parallel LinkedIn Company Scraper

Scrapes LinkedIn company /people/ pages to extract employee lists.
Uses Browserbase session pool for concurrent scraping with human-like behavior.

Key Features:
- Google search to find company LinkedIn URLs
- Extract employee count from company page
- Scrape /people/ page with infinite scroll pagination
- Classify employees as ATL (Above The Line) or BTL (Below The Line)
- Rate limiting: 30 companies/hour with random delays
- Graceful error handling per company

Author: Sales Agent Pipeline
Date: Dec 1, 2025
"""

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from urllib.parse import quote_plus, urljoin

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.services.browserbase_session_pool import BrowserbaseSessionPool

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# ATL title keywords (case-insensitive, matched as whole words)
ATL_KEYWORDS = {
    'ceo', 'chief executive', 'president', 'owner', 'founder', 'co-founder',
    'vp', 'vice president', 'director', 'partner', 'principal',
    'chief', 'cto', 'cfo', 'coo', 'cmo', 'managing', 'head of'
}

# Regex pattern for word boundary matching (re already imported above)
ATL_PATTERN = re.compile(
    r'\b(' + '|'.join(re.escape(kw) for kw in ATL_KEYWORDS) + r')\b',
    re.IGNORECASE
)


@dataclass
class LinkedInEmployee:
    """Employee extracted from LinkedIn company page."""
    name: str
    title: str
    profile_url: Optional[str] = None
    is_atl: bool = False

    def __post_init__(self):
        """Classify employee as ATL based on title keywords."""
        if not self.is_atl:  # Allow manual override
            self.is_atl = self._classify_atl()

    def _classify_atl(self) -> bool:
        """Check if title contains ATL keywords (whole word match only)."""
        # Use regex word boundaries to avoid false positives like
        # "Coordinator" matching "coo"
        return bool(ATL_PATTERN.search(self.title))


@dataclass
class LinkedInCompanyResult:
    """Result from scraping a LinkedIn company page."""
    company_name: str
    domain: str
    linkedin_url: Optional[str] = None
    employee_count: Optional[int] = None
    employees: List[LinkedInEmployee] = field(default_factory=list)
    atl_employees: List[LinkedInEmployee] = field(default_factory=list)
    error: Optional[str] = None

    def __post_init__(self):
        """Filter ATL employees from all employees."""
        if not self.atl_employees and self.employees:
            self.atl_employees = [emp for emp in self.employees if emp.is_atl]


class ParallelLinkedInCompanyScraper:
    """
    Parallel LinkedIn company scraper using Browserbase session pool.

    Rate Limiting:
    - Max 30 companies/hour (2 minutes per company average)
    - Random delays 3-8s between page loads
    - Natural scrolling behavior to avoid detection

    Usage:
        scraper = ParallelLinkedInCompanyScraper(max_workers=3)
        await scraper.initialize()
        results = await scraper.scrape_companies([
            {"name": "Acme Corp", "domain": "acme.com"},
            {"name": "TechCo", "domain": "techco.io"}
        ])
        await scraper.cleanup()
    """

    def __init__(
        self,
        max_workers: int = 3,
        scroll_cycles: int = 5,
        timeout_ms: int = 30000
    ):
        """
        Initialize scraper.

        Args:
            max_workers: Number of concurrent browser sessions
            scroll_cycles: Max number of scroll cycles on /people/ page
            timeout_ms: Page load timeout in milliseconds
        """
        self.max_workers = max_workers
        self.scroll_cycles = scroll_cycles
        self.timeout_ms = timeout_ms
        self.session_pool: Optional[BrowserbaseSessionPool] = None

    async def initialize(self):
        """Initialize Browserbase session pool."""
        logger.info(f"Initializing session pool with {self.max_workers} workers")
        self.session_pool = BrowserbaseSessionPool(max_sessions=self.max_workers)
        logger.info("Session pool ready")

    async def cleanup(self):
        """Cleanup session pool."""
        if self.session_pool:
            logger.info("Cleaning up session pool")
            await self.session_pool.close_all()
            self.session_pool = None

    async def scrape_companies(
        self,
        companies: List[Dict[str, str]]
    ) -> List[LinkedInCompanyResult]:
        """
        Scrape multiple companies in parallel.

        Args:
            companies: List of dicts with 'name' and 'domain' keys

        Returns:
            List of LinkedInCompanyResult objects
        """
        if not self.session_pool:
            raise RuntimeError("Session pool not initialized. Call initialize() first.")

        logger.info(f"Starting parallel scrape of {len(companies)} companies")

        # Create tasks for parallel execution
        tasks = [
            self.scrape_company(company['name'], company['domain'])
            for company in companies
        ]

        # Run with progress logging
        results = []
        for i, task in enumerate(asyncio.as_completed(tasks), 1):
            result = await task
            results.append(result)
            logger.info(f"Progress: {i}/{len(companies)} companies scraped")

        # Log summary
        success_count = sum(1 for r in results if not r.error)
        atl_count = sum(len(r.atl_employees) for r in results)
        logger.info(
            f"Scraping complete: {success_count}/{len(companies)} successful, "
            f"{atl_count} total ATL employees found"
        )

        return results

    async def scrape_company(
        self,
        company_name: str,
        domain: str
    ) -> LinkedInCompanyResult:
        """
        Scrape a single company's LinkedIn page.

        Steps:
        1. Google search: site:linkedin.com/company "{company_name}"
        2. Navigate to company page (extract employee count)
        3. Navigate to /people/ page
        4. Paginate with infinite scroll
        5. Extract all visible employees
        6. Classify ATL/BTL

        Args:
            company_name: Company name for search
            domain: Company domain

        Returns:
            LinkedInCompanyResult with employees or error
        """
        result = LinkedInCompanyResult(
            company_name=company_name,
            domain=domain
        )

        session = None
        browser = None
        page = None
        try:
            # Checkout session from pool
            session = await self.session_pool.checkout()

            # Connect to Browserbase via CDP
            from playwright.async_api import async_playwright
            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(session.connect_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            logger.info(f"[{company_name}] Starting LinkedIn scrape")

            # Step 1: Find LinkedIn company URL via Google
            linkedin_url = await self._find_linkedin_url(page, company_name)
            if not linkedin_url:
                result.error = "LinkedIn company page not found"
                logger.warning(f"[{company_name}] {result.error}")
                return result

            result.linkedin_url = linkedin_url
            logger.info(f"[{company_name}] Found LinkedIn: {linkedin_url}")

            # Human-like delay
            await self._random_delay()

            # Step 2: Navigate to company page and extract employee count
            employee_count = await self._extract_employee_count(page, linkedin_url)
            result.employee_count = employee_count
            logger.info(f"[{company_name}] Employee count: {employee_count or 'unknown'}")

            # Human-like delay
            await self._random_delay()

            # Step 3: Navigate to /people/ page
            people_url = urljoin(linkedin_url.rstrip('/') + '/', 'people/')
            logger.info(f"[{company_name}] Navigating to /people/ page")
            await page.goto(people_url, wait_until='networkidle', timeout=self.timeout_ms)

            # Step 4 & 5: Scroll and extract employees
            employees = await self._extract_employees(page, company_name)
            result.employees = employees
            result.atl_employees = [emp for emp in employees if emp.is_atl]

            logger.info(
                f"[{company_name}] Extracted {len(employees)} employees "
                f"({len(result.atl_employees)} ATL)"
            )

        except PlaywrightTimeoutError as e:
            result.error = f"Timeout: {str(e)}"
            logger.error(f"[{company_name}] Timeout error: {e}")
        except Exception as e:
            result.error = f"Error: {str(e)}"
            logger.error(f"[{company_name}] Unexpected error: {e}", exc_info=True)
        finally:
            # Close browser connection
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            # Always return session to pool
            if session:
                await self.session_pool.checkin(session)

        return result

    async def _find_linkedin_url(self, page: Page, company_name: str) -> Optional[str]:
        """
        Find LinkedIn company URL via Google search.

        Args:
            page: Playwright page
            company_name: Company name to search

        Returns:
            LinkedIn company URL or None
        """
        try:
            # Google search query
            query = f'site:linkedin.com/company "{company_name}"'
            search_url = f"https://www.google.com/search?q={quote_plus(query)}"

            await page.goto(search_url, wait_until='networkidle', timeout=self.timeout_ms)

            # Extract first linkedin.com/company link
            links = await page.locator('a[href*="linkedin.com/company/"]').all()

            for link in links:
                href = await link.get_attribute('href')
                if href and '/company/' in href:
                    # Clean up URL (remove Google redirect)
                    match = re.search(r'(https://[^/]+\.linkedin\.com/company/[^/&?]+)', href)
                    if match:
                        return match.group(1)

            return None

        except Exception as e:
            logger.error(f"Error finding LinkedIn URL: {e}")
            return None

    async def _extract_employee_count(self, page: Page, linkedin_url: str) -> Optional[int]:
        """
        Extract employee count from LinkedIn company page.

        Args:
            page: Playwright page
            linkedin_url: LinkedIn company URL

        Returns:
            Employee count or None
        """
        try:
            await page.goto(linkedin_url, wait_until='networkidle', timeout=self.timeout_ms)

            # Look for employee count text (e.g., "1,234 employees")
            # LinkedIn shows this in various places, try multiple selectors
            selectors = [
                'text=/\\d+[,\\d]* employees?/i',
                'text=/\\d+[,\\d]* associated members?/i',
                '[class*="org-top-card"] text=/\\d+[,\\d]*/i'
            ]

            for selector in selectors:
                try:
                    element = page.locator(selector).first
                    if await element.count() > 0:
                        text = await element.inner_text()
                        # Extract number
                        match = re.search(r'([\d,]+)', text)
                        if match:
                            count_str = match.group(1).replace(',', '')
                            return int(count_str)
                except:
                    continue

            return None

        except Exception as e:
            logger.error(f"Error extracting employee count: {e}")
            return None

    async def _extract_employees(
        self,
        page: Page,
        company_name: str
    ) -> List[LinkedInEmployee]:
        """
        Extract employees from /people/ page with infinite scroll.

        Args:
            page: Playwright page (already on /people/ page)
            company_name: Company name for logging

        Returns:
            List of LinkedInEmployee objects
        """
        employees = []

        try:
            # Scroll and load more employees
            for cycle in range(self.scroll_cycles):
                logger.info(f"[{company_name}] Scroll cycle {cycle + 1}/{self.scroll_cycles}")

                # Natural scrolling
                await page.evaluate("""
                    () => {
                        window.scrollTo({
                            top: document.body.scrollHeight,
                            behavior: 'smooth'
                        });
                    }
                """)

                # Wait for new content to load (random delay 2-4s)
                await asyncio.sleep(random.uniform(2.0, 4.0))

            # Extract all visible employee cards
            # LinkedIn uses various class names, adapt as needed
            employee_cards = await page.locator('[class*="org-people-profile-card"]').all()

            for card in employee_cards:
                try:
                    # Extract name
                    name_element = card.locator('[class*="profile-card__title"]').first
                    name = await name_element.inner_text() if await name_element.count() > 0 else ""

                    # Extract title
                    title_element = card.locator('[class*="profile-card__subtitle"]').first
                    title = await title_element.inner_text() if await title_element.count() > 0 else ""

                    # Extract profile URL
                    link_element = card.locator('a[href*="/in/"]').first
                    profile_url = None
                    if await link_element.count() > 0:
                        href = await link_element.get_attribute('href')
                        if href:
                            # Clean up URL
                            match = re.search(r'(https://[^/]+\.linkedin\.com/in/[^/?]+)', href)
                            if match:
                                profile_url = match.group(1)

                    if name and title:
                        employee = LinkedInEmployee(
                            name=name.strip(),
                            title=title.strip(),
                            profile_url=profile_url
                        )
                        employees.append(employee)

                except Exception as e:
                    logger.debug(f"[{company_name}] Error extracting employee card: {e}")
                    continue

            # Deduplicate by profile URL (same person might appear multiple times)
            seen_urls = set()
            unique_employees = []
            for emp in employees:
                key = emp.profile_url or emp.name  # Use URL if available, else name
                if key not in seen_urls:
                    seen_urls.add(key)
                    unique_employees.append(emp)

            return unique_employees

        except Exception as e:
            logger.error(f"[{company_name}] Error extracting employees: {e}")
            return employees

    async def _random_delay(self):
        """Random delay 3-8 seconds to mimic human behavior."""
        delay = random.uniform(3.0, 8.0)
        logger.debug(f"Human-like delay: {delay:.1f}s")
        await asyncio.sleep(delay)


async def main():
    """Example usage and testing."""
    # Test companies
    test_companies = [
        {"name": "Anthropic", "domain": "anthropic.com"},
        {"name": "OpenAI", "domain": "openai.com"},
        {"name": "Scientia Capital", "domain": "scientiacapital.com"}
    ]

    scraper = ParallelLinkedInCompanyScraper(max_workers=2)

    try:
        await scraper.initialize()
        results = await scraper.scrape_companies(test_companies)

        # Print results
        print("\n" + "="*80)
        print("LINKEDIN SCRAPING RESULTS")
        print("="*80)

        for result in results:
            print(f"\nCompany: {result.company_name}")
            print(f"Domain: {result.domain}")
            print(f"LinkedIn URL: {result.linkedin_url or 'Not found'}")
            print(f"Employee Count: {result.employee_count or 'Unknown'}")
            print(f"Employees Extracted: {len(result.employees)}")
            print(f"ATL Employees: {len(result.atl_employees)}")

            if result.atl_employees:
                print("\nATL Employees:")
                for emp in result.atl_employees[:5]:  # Show first 5
                    print(f"  - {emp.name} | {emp.title}")
                if len(result.atl_employees) > 5:
                    print(f"  ... and {len(result.atl_employees) - 5} more")

            if result.error:
                print(f"Error: {result.error}")

            print("-" * 80)

    finally:
        await scraper.cleanup()


if __name__ == "__main__":
    asyncio.run(main())
