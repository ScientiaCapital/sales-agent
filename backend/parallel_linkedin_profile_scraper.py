"""
Parallel LinkedIn Profile Scraper

Searches for personal LinkedIn profile URLs using Google site search.
Implements conservative rate limiting and confidence-based matching.

Usage:
    scraper = ParallelLinkedInProfileScraper(session_pool)
    result = await scraper.search_profile("John Smith", "Acme Corp", "CEO")

Rate Limits (Conservative):
    - 50 profile searches/day (most sensitive)
    - 10 profile searches/hour
    - 45-90s between searches
"""

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional
from urllib.parse import quote_plus

from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.services.browserbase_session_pool import BrowserbaseSessionPool

# Configure logging
logger = logging.getLogger(__name__)


@dataclass
class ProfileCandidate:
    """Single LinkedIn profile candidate from search results."""

    url: str
    snippet: str
    position: int  # 1-indexed position in search results
    name_match_score: float  # 0-1
    company_match_score: float  # 0-1
    title_match_score: float  # 0-1


@dataclass
class ProfileSearchResult:
    """Result of LinkedIn profile search for a contact."""

    contact_id: str
    contact_name: str
    company_name: str
    linkedin_url: Optional[str]
    confidence: float  # 0-1
    search_query: str
    candidates: List[ProfileCandidate] = field(default_factory=list)
    error: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.utcnow)


class RateLimiter:
    """Conservative rate limiter for LinkedIn profile searches."""

    def __init__(
        self,
        max_per_hour: int = 10,
        max_per_day: int = 50,
        min_delay: float = 45.0,
        max_delay: float = 90.0
    ):
        self.max_per_hour = max_per_hour
        self.max_per_day = max_per_day
        self.min_delay = min_delay
        self.max_delay = max_delay

        self.hourly_requests: List[datetime] = []
        self.daily_requests: List[datetime] = []

    async def acquire(self) -> None:
        """Wait until next request is allowed under rate limits."""
        now = datetime.utcnow()

        # Clean old timestamps
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        self.hourly_requests = [ts for ts in self.hourly_requests if ts > hour_ago]
        self.daily_requests = [ts for ts in self.daily_requests if ts > day_ago]

        # Check hourly limit
        if len(self.hourly_requests) >= self.max_per_hour:
            oldest = min(self.hourly_requests)
            wait_until = oldest + timedelta(hours=1)
            wait_seconds = (wait_until - now).total_seconds()
            if wait_seconds > 0:
                logger.info(f"[RateLimit] Hourly limit reached. Waiting {wait_seconds:.1f}s...")
                await asyncio.sleep(wait_seconds)

        # Check daily limit
        if len(self.daily_requests) >= self.max_per_day:
            oldest = min(self.daily_requests)
            wait_until = oldest + timedelta(days=1)
            wait_seconds = (wait_until - now).total_seconds()
            if wait_seconds > 0:
                logger.info(f"[RateLimit] Daily limit reached. Waiting {wait_seconds:.1f}s...")
                await asyncio.sleep(wait_seconds)

        # Random delay between requests
        delay = random.uniform(self.min_delay, self.max_delay)
        await asyncio.sleep(delay)

        # Record request
        now = datetime.utcnow()
        self.hourly_requests.append(now)
        self.daily_requests.append(now)


class ParallelLinkedInProfileScraper:
    """
    Searches for personal LinkedIn profiles using Google site search.

    Implements conservative rate limiting to avoid detection and provides
    confidence scoring for profile matches.
    """

    def __init__(
        self,
        session_pool: BrowserbaseSessionPool,
        max_per_hour: int = 10,
        max_per_day: int = 50,
        min_delay: float = 45.0,
        max_delay: float = 90.0
    ):
        """
        Initialize scraper with session pool and rate limits.

        Args:
            session_pool: Browserbase session pool for browser automation
            max_per_hour: Maximum profile searches per hour
            max_per_day: Maximum profile searches per day
            min_delay: Minimum seconds between searches
            max_delay: Maximum seconds between searches
        """
        self.session_pool = session_pool
        self.rate_limiter = RateLimiter(
            max_per_hour=max_per_hour,
            max_per_day=max_per_day,
            min_delay=min_delay,
            max_delay=max_delay
        )

    def _build_search_query(self, contact_name: str, company_name: str) -> str:
        """
        Build Google search query for LinkedIn profile.

        Args:
            contact_name: Full name of contact
            company_name: Company name

        Returns:
            URL-encoded search query
        """
        # site:linkedin.com/in "John Smith" "Acme Corp"
        query = f'site:linkedin.com/in "{contact_name}" "{company_name}"'
        return query

    def _normalize_name(self, name: str) -> str:
        """Normalize name for comparison (lowercase, no punctuation)."""
        return re.sub(r'[^a-z\s]', '', name.lower()).strip()

    def _calculate_name_match(self, candidate_url: str, contact_name: str) -> float:
        """
        Calculate name match score between URL and contact name.

        LinkedIn URLs are typically: linkedin.com/in/john-smith-12345678

        Args:
            candidate_url: LinkedIn profile URL
            contact_name: Full name of contact

        Returns:
            Match score 0-1 (1 = perfect match)
        """
        # Extract name portion from URL
        # Example: linkedin.com/in/john-smith-12345678 -> john-smith
        match = re.search(r'/in/([a-z-]+)', candidate_url.lower())
        if not match:
            return 0.0

        url_name = match.group(1)
        # Remove trailing numbers (LinkedIn ID)
        url_name = re.sub(r'-\d+$', '', url_name)

        # Normalize contact name
        normalized_contact = self._normalize_name(contact_name)
        contact_parts = normalized_contact.split()

        # Convert URL hyphens to spaces for comparison
        url_name_normalized = url_name.replace('-', ' ')

        # Exact match
        if url_name_normalized == normalized_contact:
            return 1.0

        # Check if all contact name parts are in URL
        url_parts = url_name_normalized.split()
        matched_parts = sum(1 for part in contact_parts if part in url_parts)

        if matched_parts == len(contact_parts):
            return 0.9
        elif matched_parts >= len(contact_parts) - 1:  # Allow 1 missing part
            return 0.7
        elif matched_parts > 0:
            return 0.4 * (matched_parts / len(contact_parts))

        return 0.0

    def _calculate_company_match(self, snippet: str, company_name: str) -> float:
        """
        Calculate company match score between snippet and company name.

        Args:
            snippet: Search result snippet text
            company_name: Company name to match

        Returns:
            Match score 0-1 (1 = perfect match)
        """
        if not snippet or not company_name:
            return 0.0

        snippet_lower = snippet.lower()
        company_lower = company_name.lower()

        # Exact match
        if company_lower in snippet_lower:
            return 1.0

        # Check for partial company name match
        company_words = company_lower.split()
        matched_words = sum(1 for word in company_words if word in snippet_lower)

        if matched_words > 0:
            return 0.5 * (matched_words / len(company_words))

        return 0.0

    def _calculate_title_match(self, snippet: str, title: Optional[str]) -> float:
        """
        Calculate title match score between snippet and contact title.

        Args:
            snippet: Search result snippet text
            title: Contact title (e.g., "CEO", "VP Sales")

        Returns:
            Match score 0-1 (1 = perfect match)
        """
        if not snippet or not title:
            return 0.0

        snippet_lower = snippet.lower()
        title_lower = title.lower()

        # Common title keywords
        title_keywords = ['ceo', 'president', 'owner', 'founder', 'vp', 'director', 'manager']

        # Exact title match
        if title_lower in snippet_lower:
            return 1.0

        # Check for title keywords
        for keyword in title_keywords:
            if keyword in title_lower and keyword in snippet_lower:
                return 0.6

        return 0.0

    def _calculate_confidence(
        self,
        candidate: ProfileCandidate,
        is_top_result: bool
    ) -> float:
        """
        Calculate overall confidence score for profile match.

        Scoring:
            - Name match: 0-0.4 (weighted by match quality)
            - Company match: 0-0.3
            - Title match: 0-0.2
            - Top result bonus: +0.1

        Args:
            candidate: Profile candidate with match scores
            is_top_result: Whether this is the #1 search result

        Returns:
            Confidence score 0-1
        """
        confidence = 0.0

        # Name match (up to 0.4)
        confidence += candidate.name_match_score * 0.4

        # Company match (up to 0.3)
        confidence += candidate.company_match_score * 0.3

        # Title match (up to 0.2)
        confidence += candidate.title_match_score * 0.2

        # Top result bonus (0.1)
        if is_top_result:
            confidence += 0.1

        return min(confidence, 1.0)

    async def _extract_linkedin_profiles(self, page: Page) -> List[dict]:
        """
        Extract LinkedIn profile URLs from Google search results.

        Args:
            page: Playwright page with Google search results

        Returns:
            List of dicts with 'url', 'snippet', 'position'
        """
        profiles = []

        # Wait for search results
        try:
            await page.wait_for_selector('div#search', timeout=10000)
        except PlaywrightTimeoutError:
            logger.warning("[LinkedIn] No search results found")
            return profiles

        # Extract search result links
        # Google search results are in <a> tags with specific class
        search_results = await page.query_selector_all('div#search a[href*="linkedin.com/in/"]')

        for idx, result in enumerate(search_results[:5], start=1):  # Top 5 results
            try:
                url = await result.get_attribute('href')
                if not url or '/in/' not in url:
                    continue

                # Clean URL (remove Google tracking params)
                if url.startswith('/url?q='):
                    url = url.split('/url?q=')[1].split('&')[0]

                # Extract snippet text (parent container)
                parent = await result.evaluate_handle('el => el.closest("div[data-sokoban-container]") || el.parentElement')
                snippet = await parent.inner_text() if parent else ""

                profiles.append({
                    'url': url,
                    'snippet': snippet,
                    'position': idx
                })

            except Exception as e:
                logger.debug(f"[LinkedIn] Error extracting result {idx}: {e}")
                continue

        return profiles

    async def search_profile(
        self,
        contact_name: str,
        company_name: str,
        contact_id: str = "",
        title: Optional[str] = None
    ) -> ProfileSearchResult:
        """
        Search for LinkedIn profile using Google site search.

        Args:
            contact_name: Full name of contact
            company_name: Company name
            contact_id: Unique contact identifier (for logging)
            title: Optional contact title (improves confidence scoring)

        Returns:
            ProfileSearchResult with best match and confidence score
        """
        await self.rate_limiter.acquire()

        search_query = self._build_search_query(contact_name, company_name)
        logger.info(f"[{contact_name}] Searching LinkedIn profile")

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

            # Navigate to Google search
            google_url = f"https://www.google.com/search?q={quote_plus(search_query)}"
            await page.goto(google_url, wait_until='domcontentloaded', timeout=30000)

            # Random wait (human-like behavior)
            await asyncio.sleep(random.uniform(1.5, 3.0))

            # Extract LinkedIn profiles from results
            raw_profiles = await self._extract_linkedin_profiles(page)

            if not raw_profiles:
                logger.info(f"[{contact_name}] No LinkedIn profiles found")
                return ProfileSearchResult(
                    contact_id=contact_id,
                    contact_name=contact_name,
                    company_name=company_name,
                    linkedin_url=None,
                    confidence=0.0,
                    search_query=search_query,
                    candidates=[],
                    error="No profiles found"
                )

            # Score each candidate
            candidates = []
            for raw in raw_profiles:
                name_score = self._calculate_name_match(raw['url'], contact_name)
                company_score = self._calculate_company_match(raw['snippet'], company_name)
                title_score = self._calculate_title_match(raw['snippet'], title)

                candidate = ProfileCandidate(
                    url=raw['url'],
                    snippet=raw['snippet'],
                    position=raw['position'],
                    name_match_score=name_score,
                    company_match_score=company_score,
                    title_match_score=title_score
                )
                candidates.append(candidate)

            # Calculate confidence for each candidate
            candidate_confidences = [
                (c, self._calculate_confidence(c, c.position == 1))
                for c in candidates
            ]

            # Sort by confidence (descending)
            candidate_confidences.sort(key=lambda x: x[1], reverse=True)

            # Best match
            best_candidate, best_confidence = candidate_confidences[0]

            logger.info(
                f"[{contact_name}] Found {len(candidates)} candidates. "
                f"Best confidence: {best_confidence:.2f}"
            )

            return ProfileSearchResult(
                contact_id=contact_id,
                contact_name=contact_name,
                company_name=company_name,
                linkedin_url=best_candidate.url if best_confidence >= 0.3 else None,
                confidence=best_confidence,
                search_query=search_query,
                candidates=[c for c, _ in candidate_confidences]
            )

        except Exception as e:
            logger.error(f"[{contact_name}] Error searching LinkedIn profile: {e}")
            return ProfileSearchResult(
                contact_id=contact_id,
                contact_name=contact_name,
                company_name=company_name,
                linkedin_url=None,
                confidence=0.0,
                search_query=search_query,
                candidates=[],
                error=str(e)
            )

        finally:
            # Close browser connection
            if browser:
                try:
                    await browser.close()
                except Exception:
                    pass
            # Return session to pool
            if session:
                await self.session_pool.checkin(session)

    async def search_profiles_batch(
        self,
        contacts: List[dict]
    ) -> List[ProfileSearchResult]:
        """
        Search LinkedIn profiles for batch of contacts (sequential with rate limiting).

        Args:
            contacts: List of dicts with 'name', 'company', 'id', 'title' (optional)

        Returns:
            List of ProfileSearchResult objects
        """
        results = []

        for idx, contact in enumerate(contacts, start=1):
            logger.info(f"[Batch] Processing {idx}/{len(contacts)}: {contact['name']}")

            result = await self.search_profile(
                contact_name=contact['name'],
                company_name=contact['company'],
                contact_id=contact.get('id', ''),
                title=contact.get('title')
            )
            results.append(result)

        # Summary
        successful = sum(1 for r in results if r.linkedin_url)
        avg_confidence = sum(r.confidence for r in results) / len(results) if results else 0

        logger.info(
            f"[Batch] Complete: {successful}/{len(contacts)} profiles found. "
            f"Avg confidence: {avg_confidence:.2f}"
        )

        return results


async def main():
    """Example usage of ParallelLinkedInProfileScraper."""
    from app.services.browserbase_session_pool import BrowserbaseSessionPool

    # Initialize session pool
    session_pool = BrowserbaseSessionPool(pool_size=3)
    await session_pool.initialize()

    try:
        # Initialize scraper with conservative limits
        scraper = ParallelLinkedInProfileScraper(
            session_pool=session_pool,
            max_per_hour=10,
            max_per_day=50,
            min_delay=45.0,
            max_delay=90.0
        )

        # Example contacts
        contacts = [
            {
                'id': '1',
                'name': 'Brian Chesky',
                'company': 'Airbnb',
                'title': 'CEO'
            },
            {
                'id': '2',
                'name': 'Satya Nadella',
                'company': 'Microsoft',
                'title': 'CEO'
            }
        ]

        # Search profiles
        results = await scraper.search_profiles_batch(contacts)

        # Log results
        for result in results:
            logger.info(f"{result.contact_name} @ {result.company_name}")
            logger.info(f"  LinkedIn: {result.linkedin_url}")
            logger.info(f"  Confidence: {result.confidence:.2f}")
            logger.info(f"  Candidates: {len(result.candidates)}")

    finally:
        await session_pool.close()


if __name__ == '__main__':
    asyncio.run(main())
