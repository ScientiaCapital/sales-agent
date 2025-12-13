"""
Website Content Scraper - Captures Landing Pages for Agent Analysis

Scrapes and stores website content for:
1. Landing page text/HTML for agent context
2. Key page metadata (title, description, keywords)
3. Services/products mentioned
4. Company signals (hiring, funding, tech stack)
5. Screenshot paths (when Playwright available)

This data powers:
- VLM/OCR analysis of screenshots
- Agent tools that read company context
- Personalization for outreach

Cost: $0 (BeautifulSoup) or Browserbase for JS-heavy sites
"""

import asyncio
import re
import os
import hashlib
from typing import Dict, List, Optional, Any
from urllib.parse import urljoin, urlparse
from datetime import datetime
from pathlib import Path
import httpx
from bs4 import BeautifulSoup
import structlog

from app.services.url_validator import validate_website_url

logger = structlog.get_logger(__name__)

# Pages to scrape for context
IMPORTANT_PAGES = [
    "/",           # Homepage - main value prop
    "/about",      # About - company story
    "/services",   # Services - what they offer
    "/products",   # Products
    "/solutions",  # Solutions
    "/pricing",    # Pricing - business model
    "/careers",    # Careers - hiring signals
    "/contact",    # Contact - location info
    "/team",       # Team - leadership
    "/customers",  # Customers - social proof
    "/case-studies",
]

# Signals to detect on pages
HIRING_SIGNALS = [
    r"we.?re\s+hiring",
    r"join\s+(our|the)\s+team",
    r"open\s+positions?",
    r"career\s+opportunities",
    r"now\s+hiring",
    r"help\s+wanted",
]

FUNDING_SIGNALS = [
    r"series\s+[a-d]",
    r"raised\s+\$?\d+",
    r"funding\s+round",
    r"backed\s+by",
    r"investors?\s+include",
    r"venture\s+capital",
]

GROWTH_SIGNALS = [
    r"fastest[\s-]growing",
    r"inc\.?\s*5000",
    r"award[\s-]winning",
    r"industry\s+leader",
    r"trusted\s+by\s+\d+",
    r"serving\s+\d+\s+(customers?|clients?|companies)",
]

TECH_STACK_PATTERNS = {
    "salesforce": r"salesforce|sfdc",
    "hubspot": r"hubspot",
    "marketo": r"marketo",
    "pardot": r"pardot",
    "dynamics": r"dynamics\s*365|microsoft\s*crm",
    "zoho": r"zoho\s*crm",
    "pipedrive": r"pipedrive",
    "aws": r"amazon\s*web\s*services|aws",
    "gcp": r"google\s*cloud|gcp",
    "azure": r"microsoft\s*azure|azure",
    "react": r"react\.?js|reactjs",
    "vue": r"vue\.?js|vuejs",
    "angular": r"angular",
    "python": r"python",
    "node": r"node\.?js|nodejs",
}


class WebsiteContentScraper:
    """
    Comprehensive website scraper that captures content for agent analysis.

    Features:
    - Extracts clean text from HTML
    - Captures metadata (title, description, keywords)
    - Detects signals (hiring, funding, growth)
    - Identifies tech stack mentions
    - Stores for VLM/OCR processing
    """

    def __init__(self, timeout: float = 15.0, max_pages: int = 8):
        self.timeout = timeout
        self.max_pages = max_pages
        self.user_agent = (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )

    async def scrape_website(self, website: str) -> Dict[str, Any]:
        """
        Scrape a company website and extract all useful content.

        Returns:
            {
                "url": "https://example.com",
                "homepage_title": "...",
                "homepage_description": "...",
                "homepage_text": "...",  # Clean text, truncated
                "pages_scraped": [...],
                "services": [...],
                "products": [...],
                "signals": {
                    "is_hiring": True,
                    "has_funding": False,
                    "growth_indicators": [...],
                },
                "tech_stack": ["salesforce", "aws"],
                "social_links": {...},
                "scraped_at": "2024-01-01T00:00:00Z",
            }

        Raises:
            ValueError: If URL is blocked for security reasons (SSRF protection)
        """
        # SSRF Protection: Validate URL before making any requests
        website = validate_website_url(website)

        base_url = website.rstrip("/")
        result = {
            "url": base_url,
            "homepage_title": "",
            "homepage_description": "",
            "homepage_keywords": "",
            "homepage_text": "",
            "pages_scraped": [],
            "all_text": "",  # Combined text from all pages
            "services": [],
            "products": [],
            "value_proposition": "",
            "signals": {
                "is_hiring": False,
                "has_funding": False,
                "growth_indicators": [],
            },
            "tech_stack": [],
            "social_links": {},
            "contact_info": {},
            "scraped_at": datetime.now().isoformat(),
            "error": None,
        }

        all_text_parts = []

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout),
            follow_redirects=True,
            headers={"User-Agent": self.user_agent}
        ) as client:
            pages_scraped = 0

            for page_path in IMPORTANT_PAGES:
                if pages_scraped >= self.max_pages:
                    break

                url = f"{base_url}{page_path}" if page_path != "/" else base_url

                try:
                    page_data = await self._scrape_page(client, url)

                    if page_data:
                        result["pages_scraped"].append({
                            "path": page_path,
                            "url": url,
                            "title": page_data.get("title", ""),
                            "text_length": len(page_data.get("text", "")),
                        })

                        # Store homepage data specially
                        if page_path == "/":
                            result["homepage_title"] = page_data.get("title", "")
                            result["homepage_description"] = page_data.get("description", "")
                            result["homepage_keywords"] = page_data.get("keywords", "")
                            result["homepage_text"] = page_data.get("text", "")[:5000]
                            result["value_proposition"] = self._extract_value_prop(page_data.get("text", ""))
                            result["social_links"] = page_data.get("social_links", {})

                        # Accumulate text
                        all_text_parts.append(page_data.get("text", ""))

                        # Detect signals
                        text = page_data.get("text", "")
                        if self._detect_hiring(text):
                            result["signals"]["is_hiring"] = True
                        if self._detect_funding(text):
                            result["signals"]["has_funding"] = True

                        growth = self._detect_growth(text)
                        result["signals"]["growth_indicators"].extend(growth)

                        # Detect tech stack
                        tech = self._detect_tech_stack(text)
                        result["tech_stack"].extend(tech)

                        # Extract services/products from specific pages
                        if page_path in ["/services", "/solutions"]:
                            result["services"].extend(self._extract_list_items(page_data.get("soup")))
                        if page_path == "/products":
                            result["products"].extend(self._extract_list_items(page_data.get("soup")))

                        pages_scraped += 1

                except Exception as e:
                    logger.debug(f"Failed to scrape {url}: {e}")
                    continue

            # Combine all text (truncated for storage)
            result["all_text"] = " ".join(all_text_parts)[:20000]

            # Deduplicate
            result["tech_stack"] = list(set(result["tech_stack"]))
            result["signals"]["growth_indicators"] = list(set(result["signals"]["growth_indicators"]))[:5]
            result["services"] = list(set(result["services"]))[:10]
            result["products"] = list(set(result["products"]))[:10]

        logger.info(
            "Website content scraped",
            url=base_url,
            pages=len(result["pages_scraped"]),
            text_length=len(result["all_text"]),
            is_hiring=result["signals"]["is_hiring"],
            tech_stack=result["tech_stack"][:3],
        )

        return result

    async def _scrape_page(self, client: httpx.AsyncClient, url: str) -> Optional[Dict]:
        """Scrape a single page and extract content."""
        try:
            response = await client.get(url)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Remove script/style elements
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            # Extract metadata
            title = ""
            title_tag = soup.find("title")
            if title_tag:
                title = title_tag.get_text(strip=True)

            description = ""
            meta_desc = soup.find("meta", attrs={"name": "description"})
            if meta_desc:
                description = meta_desc.get("content", "")

            keywords = ""
            meta_keywords = soup.find("meta", attrs={"name": "keywords"})
            if meta_keywords:
                keywords = meta_keywords.get("content", "")

            # Extract clean text
            text = soup.get_text(separator=" ", strip=True)
            # Clean up whitespace
            text = re.sub(r'\s+', ' ', text)

            # Extract social links
            social_links = self._extract_social_links(soup)

            return {
                "title": title,
                "description": description,
                "keywords": keywords,
                "text": text,
                "soup": soup,
                "social_links": social_links,
            }

        except Exception as e:
            logger.debug(f"Error scraping {url}: {e}")
            return None

    def _extract_value_prop(self, text: str) -> str:
        """Extract the main value proposition (first ~200 chars of meaningful text)."""
        # Get first few sentences
        sentences = re.split(r'[.!?]', text)
        value_prop = ""
        for sentence in sentences[:3]:
            sentence = sentence.strip()
            if len(sentence) > 20:  # Skip very short fragments
                value_prop += sentence + ". "
                if len(value_prop) > 200:
                    break
        return value_prop[:300].strip()

    def _detect_hiring(self, text: str) -> bool:
        """Detect if company is hiring."""
        text_lower = text.lower()
        for pattern in HIRING_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_funding(self, text: str) -> bool:
        """Detect funding mentions."""
        text_lower = text.lower()
        for pattern in FUNDING_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_growth(self, text: str) -> List[str]:
        """Detect growth indicators."""
        indicators = []
        text_lower = text.lower()
        for pattern in GROWTH_SIGNALS:
            match = re.search(pattern, text_lower)
            if match:
                indicators.append(match.group(0))
        return indicators

    def _detect_tech_stack(self, text: str) -> List[str]:
        """Detect technology stack mentions."""
        tech = []
        text_lower = text.lower()
        for name, pattern in TECH_STACK_PATTERNS.items():
            if re.search(pattern, text_lower):
                tech.append(name)
        return tech

    def _extract_social_links(self, soup: BeautifulSoup) -> Dict[str, str]:
        """Extract social media links."""
        social = {}

        patterns = {
            "linkedin": r"linkedin\.com",
            "twitter": r"twitter\.com|x\.com",
            "facebook": r"facebook\.com",
            "instagram": r"instagram\.com",
            "youtube": r"youtube\.com",
            "github": r"github\.com",
        }

        for link in soup.find_all("a", href=True):
            href = link.get("href", "")
            for platform, pattern in patterns.items():
                if re.search(pattern, href, re.I) and platform not in social:
                    social[platform] = href

        return social

    def _extract_list_items(self, soup: Optional[BeautifulSoup]) -> List[str]:
        """Extract list items (services/products) from page."""
        if not soup:
            return []

        items = []

        # Look for h2/h3 headings that might be service names
        for heading in soup.find_all(["h2", "h3"]):
            text = heading.get_text(strip=True)
            if 3 < len(text) < 50:
                items.append(text)

        # Look for list items
        for li in soup.find_all("li"):
            text = li.get_text(strip=True)
            if 3 < len(text) < 50:
                items.append(text)

        return items[:20]


class WebsiteScreenshotter:
    """
    Takes screenshots of websites for VLM/OCR analysis.
    Requires Playwright to be installed.
    """

    def __init__(self, screenshot_dir: str = "/tmp/screenshots"):
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = None
        self._browser = None

    async def __aenter__(self):
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=True)
        except ImportError:
            logger.warning("Playwright not installed - screenshots disabled")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def take_screenshot(
        self,
        url: str,
        company_id: str,
        full_page: bool = False
    ) -> Optional[str]:
        """
        Take a screenshot of a website.

        Returns:
            Path to screenshot file, or None if failed

        Raises:
            ValueError: If URL is blocked for security reasons (SSRF protection)
        """
        if not self._browser:
            return None

        # SSRF Protection: Validate URL before making any requests
        url = validate_website_url(url)

        try:
            page = await self._browser.new_page(viewport={"width": 1280, "height": 800})
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Generate filename based on company ID and URL
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            filename = f"{company_id}_{url_hash}.png"
            filepath = self.screenshot_dir / filename

            await page.screenshot(path=str(filepath), full_page=full_page)
            await page.close()

            logger.info(f"Screenshot saved: {filepath}")
            return str(filepath)

        except Exception as e:
            logger.error(f"Screenshot failed for {url}: {e}")
            return None

    async def take_multiple_screenshots(
        self,
        base_url: str,
        company_id: str,
        pages: List[str] = ["/", "/about", "/services"]
    ) -> Dict[str, str]:
        """Take screenshots of multiple pages."""
        screenshots = {}

        for page_path in pages:
            url = f"{base_url.rstrip('/')}{page_path}" if page_path != "/" else base_url
            path = await self.take_screenshot(url, f"{company_id}_{page_path.replace('/', '_')}")
            if path:
                screenshots[page_path] = path

        return screenshots


# Convenience functions
async def scrape_website_content(website: str) -> Dict[str, Any]:
    """Scrape website content for agent analysis."""
    scraper = WebsiteContentScraper()
    return await scraper.scrape_website(website)


async def scrape_with_screenshots(
    website: str,
    company_id: str
) -> Dict[str, Any]:
    """Scrape website content AND take screenshots."""
    scraper = WebsiteContentScraper()
    content = await scraper.scrape_website(website)

    # Try to take screenshots if Playwright available
    async with WebsiteScreenshotter() as screenshotter:
        screenshots = await screenshotter.take_multiple_screenshots(
            website,
            company_id,
            pages=["/", "/about"]
        )
        content["screenshots"] = screenshots

    return content


# Test
async def test_scraper():
    """Test the website content scraper."""
    test_sites = [
        "https://linear.app",
        "https://stripe.com",
    ]

    scraper = WebsiteContentScraper()

    for site in test_sites:
        print(f"\n{'='*60}")
        print(f"Scraping: {site}")
        print('='*60)

        result = await scraper.scrape_website(site)

        print(f"Title: {result['homepage_title']}")
        print(f"Description: {result['homepage_description'][:100]}...")
        print(f"Value Prop: {result['value_proposition'][:150]}...")
        print(f"Pages Scraped: {len(result['pages_scraped'])}")
        print(f"Is Hiring: {result['signals']['is_hiring']}")
        print(f"Has Funding: {result['signals']['has_funding']}")
        print(f"Tech Stack: {result['tech_stack']}")
        print(f"Social Links: {list(result['social_links'].keys())}")
        print(f"Total Text Length: {len(result['all_text'])} chars")


if __name__ == "__main__":
    asyncio.run(test_scraper())
