"""
BeautifulSoup Team Page Scraper - FREE Alternative to Browserbase

Scrapes team/about/leadership pages using httpx + BeautifulSoup.
Works for static websites (most company sites).
Falls back gracefully for JS-heavy sites.

Usage:
    from app.services.beautifulsoup_team_scraper import BeautifulSoupTeamScraper

    scraper = BeautifulSoupTeamScraper()
    contacts = await scraper.scrape_team_page("https://acme.com")

Cost: $0 (completely free)
Speed: ~1-2 seconds per site
Limitations: Won't work on JS-rendered pages (React SPAs, etc.)
"""

import asyncio
import re
from typing import List, Dict, Optional, Set
from urllib.parse import urljoin, urlparse
import httpx
from bs4 import BeautifulSoup
import structlog

from app.services.url_validator import validate_website_url

logger = structlog.get_logger(__name__)

# Common team page URL patterns
TEAM_PAGE_PATTERNS = [
    "/about",
    "/about-us",
    "/about-us/",
    "/team",
    "/our-team",
    "/leadership",
    "/management",
    "/people",
    "/who-we-are",
    "/company",
    "/company/team",
    "/company/about",
    "/staff",
    "/executives",
    "/about/team",
    "/about/leadership",
]

# Title patterns that indicate ATL (Above The Line) executives
ATL_TITLE_PATTERNS = [
    r"\b(CEO|Chief Executive|President)\b",
    r"\b(CFO|Chief Financial|Finance Director)\b",
    r"\b(COO|Chief Operating|Operations Director)\b",
    r"\b(CTO|Chief Technology|Tech Director|VP Engineering)\b",
    r"\b(CMO|Chief Marketing|Marketing Director|VP Marketing)\b",
    r"\b(CRO|Chief Revenue|Revenue Director|VP Sales)\b",
    r"\b(CSO|Chief Sales|Sales Director)\b",
    r"\b(CPO|Chief Product|Product Director|VP Product)\b",
    r"\b(CHRO|Chief Human|HR Director|VP HR|People Director)\b",
    r"\b(Managing Director|General Manager|Partner)\b",
    r"\b(Founder|Co-Founder|Owner)\b",
    r"\b(Vice President|VP|SVP|EVP)\b",
    r"\b(Director)\b",  # Broad but useful
]

# Patterns to identify name + title blocks
NAME_PATTERNS = [
    # "John Smith" style
    r"^[A-Z][a-z]+\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?$",
]

# GARBAGE FILTER: Names that are NOT real people
GARBAGE_NAMES = {
    # Service/product categories
    "installation types", "battery storage", "industrial solar", "commercial solar",
    "residential solar", "solar panels", "solar energy", "solar power",
    "heating", "cooling", "plumbing", "electrical", "hvac", "roofing",
    "air conditioning", "water heater", "energy", "services",
    "ev charging", "ev chargers", "solar installation", "solar installer",
    "heat pump", "ductless", "mini split", "geothermal",
    # Placeholder names
    "john doe", "jane doe", "test user", "sample name", "your name",
    "first last", "name here", "full name",
    # Navigation/UI text
    "learn more", "read more", "click here", "view all", "see more",
    "schedule now", "call now", "get quote", "request quote", "contact us",
    "about us", "our team", "meet the team", "leadership", "management",
    "follow us", "follow us:",
    # Social media
    "facebook", "twitter", "linkedin", "instagram", "youtube", "tiktok",
}

# Patterns that indicate concatenated names (e.g., "JohnCEO", "MaryDirector")
# More specific to avoid false positives like "McCall"
CONCATENATED_PATTERNS = [
    r'\w+(CEO|CFO|CTO|COO|CMO|VP|Vice|Director|Manager|Owner|Founder|President|Customer|Advocate|Designer|Specialist|Crew|Lead|Installer|Technician|Roofing)$',
]


class BeautifulSoupTeamScraper:
    """
    FREE team page scraper using BeautifulSoup.

    Strategy:
    1. Fetch main page
    2. Discover team/about/leadership page links
    3. Scrape team pages for names + titles
    4. Filter for ATL (executives only)
    """

    def __init__(self, timeout: float = 15.0, max_pages: int = 5):
        """
        Initialize the scraper.

        Args:
            timeout: HTTP request timeout in seconds
            max_pages: Max team-related pages to scrape per domain
        """
        self.timeout = timeout
        self.max_pages = max_pages
        self.user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    async def scrape_team_page(self, website: str) -> List[Dict[str, str]]:
        """
        Main entry point - scrape a company's team page.

        Args:
            website: Company website URL (e.g., "https://acme.com")

        Returns:
            List of ATL contacts found: [{"name": "...", "title": "..."}]

        Raises:
            ValueError: If URL is blocked for security reasons (SSRF protection)
        """
        # SSRF Protection: Validate URL before making any requests
        website = validate_website_url(website)

        base_url = website.rstrip("/")
        all_contacts: List[Dict[str, str]] = []
        visited_urls: Set[str] = set()

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"User-Agent": self.user_agent}
        ) as client:
            # Step 1: Try to find team pages
            team_urls = await self._discover_team_pages(client, base_url)

            if not team_urls:
                # Try common patterns directly
                team_urls = [f"{base_url}{pattern}" for pattern in TEAM_PAGE_PATTERNS[:5]]

            # Step 2: Scrape each team page
            pages_scraped = 0
            for url in team_urls:
                if pages_scraped >= self.max_pages:
                    break
                if url in visited_urls:
                    continue

                visited_urls.add(url)

                try:
                    contacts = await self._scrape_page(client, url)
                    all_contacts.extend(contacts)
                    pages_scraped += 1

                    if contacts:
                        logger.info(
                            "Found contacts on page",
                            url=url,
                            count=len(contacts)
                        )
                except Exception as e:
                    logger.debug(f"Failed to scrape {url}: {e}")
                    continue

        # Deduplicate by name and clean up
        seen_names: Set[str] = set()
        unique_contacts = []
        for contact in all_contacts:
            name = contact.get("name", "").strip()
            title = contact.get("title", "").strip()

            # Clean up name (remove title suffixes that got concatenated)
            name = self._clean_name(name)

            if not name:
                continue

            name_lower = name.lower()
            if name_lower in seen_names:
                continue

            # Final validation
            if not self._is_valid_contact(name, title):
                continue

            seen_names.add(name_lower)
            unique_contacts.append({"name": name, "title": title})

        logger.info(
            "Team scrape complete",
            website=website,
            total_contacts=len(unique_contacts)
        )

        return unique_contacts

    def _clean_name(self, name: str) -> str:
        """Clean up a name by removing common suffixes."""
        # Remove title suffixes that got concatenated (e.g., "John SmithCEO")
        patterns_to_remove = [
            r'(CEO|CFO|CTO|COO|CMO|CPO|CRO|CHRO)$',
            r'Co-?founder.*$',
            r'Founder.*$',
            r'President.*$',
            r'Director.*$',
            r'VP.*$',
            r'Vice\s+President.*$',
        ]

        for pattern in patterns_to_remove:
            name = re.sub(pattern, '', name, flags=re.I).strip()

        return name

    def _is_valid_contact(self, name: str, title: str) -> bool:
        """Final validation that a contact is legitimate."""
        # Name must still look valid after cleaning
        words = name.split()
        if len(words) < 2 or len(words) > 4:
            return False

        # Name must be reasonable length
        if len(name) < 4 or len(name) > 35:
            return False

        # Title must be present and reasonable
        if not title or len(title) < 3 or len(title) > 100:
            return False

        # Title should not be a long paragraph
        if '\n' in title or title.count(' ') > 15:
            return False

        # GARBAGE FILTER: Check for known non-person names
        name_lower = name.lower().strip()
        if name_lower in GARBAGE_NAMES:
            logger.debug(f"Filtered garbage name: {name}")
            return False

        # Check for concatenated names (e.g., "John SmithCEO")
        for pattern in CONCATENATED_PATTERNS:
            if re.search(pattern, name):
                logger.debug(f"Filtered concatenated name: {name}")
                return False

        # Filter names containing social media keywords
        social_keywords = ['linkedin', 'facebook', 'twitter', 'instagram', 'visit', 'follow']
        if any(kw in name_lower for kw in social_keywords):
            logger.debug(f"Filtered social media name: {name}")
            return False

        # Filter names that start/end with "Visit" (social media artifacts)
        if name.startswith("Visit ") or name.endswith(" Visit"):
            logger.debug(f"Filtered visit artifact: {name}")
            return False

        return True

    async def _discover_team_pages(
        self,
        client: httpx.AsyncClient,
        base_url: str
    ) -> List[str]:
        """Find links to team/about pages on the main page."""
        team_urls: List[str] = []

        try:
            response = await client.get(base_url)
            if response.status_code != 200:
                return team_urls

            soup = BeautifulSoup(response.text, "html.parser")

            # Find all links
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True).lower()

                # Check if link text or href matches team patterns
                is_team_link = any(
                    pattern in href.lower() or pattern.strip("/") in text
                    for pattern in TEAM_PAGE_PATTERNS
                )

                if is_team_link:
                    full_url = urljoin(base_url, href)
                    # Only include same-domain links
                    if urlparse(full_url).netloc == urlparse(base_url).netloc:
                        if full_url not in team_urls:
                            team_urls.append(full_url)

        except Exception as e:
            logger.debug(f"Error discovering team pages: {e}")

        return team_urls[:self.max_pages]

    async def _scrape_page(
        self,
        client: httpx.AsyncClient,
        url: str
    ) -> List[Dict[str, str]]:
        """Scrape a single page for team member info."""
        contacts: List[Dict[str, str]] = []

        try:
            response = await client.get(url)
            if response.status_code != 200:
                return contacts

            soup = BeautifulSoup(response.text, "html.parser")

            # Strategy 1: Look for structured team member blocks
            contacts.extend(self._extract_structured_members(soup))

            # Strategy 2: Look for name + title in close proximity
            contacts.extend(self._extract_proximity_members(soup))

            # Filter for ATL titles only
            atl_contacts = [
                c for c in contacts
                if self._is_atl_title(c.get("title", ""))
            ]

            return atl_contacts

        except Exception as e:
            logger.debug(f"Error scraping {url}: {e}")
            return contacts

    def _extract_structured_members(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract team members from structured HTML blocks."""
        contacts = []

        # Common patterns for team member cards
        member_selectors = [
            # Class-based
            "[class*='team-member']",
            "[class*='staff-member']",
            "[class*='person']",
            "[class*='leader']",
            "[class*='executive']",
            "[class*='bio']",
            # Structure-based
            ".team .card",
            ".staff .card",
            ".leadership .card",
        ]

        for selector in member_selectors:
            try:
                members = soup.select(selector)
                for member in members:
                    name, title = self._extract_name_title_from_block(member)
                    if name:
                        contacts.append({"name": name, "title": title or ""})
            except Exception:
                continue

        return contacts

    def _extract_proximity_members(self, soup: BeautifulSoup) -> List[Dict[str, str]]:
        """Extract team members based on name/title proximity."""
        contacts = []

        # Get all text blocks
        text_elements = soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "span", "div"])

        for i, elem in enumerate(text_elements):
            text = elem.get_text(strip=True)

            # Skip very long or very short text
            if len(text) < 3 or len(text) > 100:
                continue

            # Check if this looks like a name
            if self._looks_like_name(text):
                # Look for title in sibling or child elements
                title = self._find_nearby_title(elem, text_elements[i:i+5])
                if title and self._is_atl_title(title):
                    contacts.append({"name": text, "title": title})

        return contacts

    def _extract_name_title_from_block(self, block) -> tuple:
        """Extract name and title from a team member block."""
        name = None
        title = None

        # Try common class names for name
        name_elem = (
            block.select_one("[class*='name']") or
            block.select_one("h2, h3, h4") or
            block.select_one("strong, b")
        )

        if name_elem:
            name = name_elem.get_text(strip=True)

        # Try common class names for title
        title_elem = (
            block.select_one("[class*='title']") or
            block.select_one("[class*='position']") or
            block.select_one("[class*='role']") or
            block.select_one("p, span")
        )

        if title_elem and title_elem != name_elem:
            title = title_elem.get_text(strip=True)

        # Validate name looks like a name
        if name and not self._looks_like_name(name):
            name = None

        return name, title

    def _looks_like_name(self, text: str) -> bool:
        """Check if text looks like a person's name."""
        # Must have at least 2 words
        words = text.split()
        if len(words) < 2 or len(words) > 4:
            return False

        # Must start with capital letters
        if not all(word[0].isupper() for word in words if word):
            return False

        # Must not be too long (strict: 35 chars max for a real name)
        if len(text) > 35:
            return False

        # Each word should be reasonable length (2-15 chars)
        for word in words:
            if len(word) < 2 or len(word) > 15:
                return False

        # Must not contain certain patterns (likely not a name)
        bad_patterns = [
            r'\d',  # Numbers
            r'@',   # Email
            r'www\.',  # URL
            r'\.\s*com',
            r'LLC|Inc|Corp|Ltd',
            r'Contact|Email|Phone|Call|Ask|Learn|Read|View|See|Get|Try',
            r'CEO|CFO|CTO|COO|CMO|VP|Director|Manager|Engineer',  # Title in name field
            r'About|Team|Leadership|Company|Home|Blog|News|Press',  # Navigation
            r'Solutions?|Products?|Services?|Features?|Pricing',  # Marketing
            r'Growth|Marketing|Sales|Support|Help',  # Department names
        ]

        for pattern in bad_patterns:
            if re.search(pattern, text, re.I):
                return False

        return True

    def _find_nearby_title(self, name_elem, nearby_elements) -> Optional[str]:
        """Find a job title near a name element."""
        # Check sibling elements
        for sibling in name_elem.find_next_siblings()[:3]:
            text = sibling.get_text(strip=True)
            if self._is_atl_title(text):
                return text

        # Check parent's children
        parent = name_elem.parent
        if parent:
            for child in parent.children:
                if hasattr(child, 'get_text'):
                    text = child.get_text(strip=True)
                    if text != name_elem.get_text(strip=True) and self._is_atl_title(text):
                        return text

        return None

    def _is_atl_title(self, title: str) -> bool:
        """Check if a title indicates an ATL executive."""
        if not title:
            return False

        for pattern in ATL_TITLE_PATTERNS:
            if re.search(pattern, title, re.I):
                return True

        return False


# Convenience function for direct use
async def scrape_team_page_free(website: str) -> List[Dict[str, str]]:
    """
    Scrape a company's team page using BeautifulSoup (FREE).

    Args:
        website: Company website URL

    Returns:
        List of ATL contacts: [{"name": "...", "title": "..."}]
    """
    scraper = BeautifulSoupTeamScraper()
    return await scraper.scrape_team_page(website)


# Test function
async def test_scraper():
    """Test the scraper on a few sites."""
    test_sites = [
        "https://anthropic.com",
        "https://stripe.com",
    ]

    scraper = BeautifulSoupTeamScraper()

    for site in test_sites:
        print(f"\n{'='*50}")
        print(f"Testing: {site}")
        print('='*50)

        try:
            contacts = await scraper.scrape_team_page(site)
            if contacts:
                for contact in contacts:
                    print(f"  - {contact['name']}: {contact['title']}")
            else:
                print("  No ATL contacts found (may need JS rendering)")
        except Exception as e:
            print(f"  Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_scraper())
