"""
Website Crawler for Sales Agent

Full-site crawling with Browserbase + Playwright.
Adapted from bug-hive crawler patterns with screenshot capture.

Features:
- Recursive link following (max 20 pages, depth 3)
- Screenshot every page
- Rate limiting (5-10s between pages)
- Same-domain filtering
- SPA wait support (networkidle + extra delay)
"""

import asyncio
import os
import time
import uuid
from pathlib import Path
from typing import Optional
from urllib.parse import urljoin, urlparse
from dataclasses import dataclass

import httpx
import structlog

# Load .env from project root (same as browserbase_team_scraper)
from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parents[3] / '.env'
if _env_path.exists():
    load_dotenv(_env_path, override=True)

logger = structlog.get_logger(__name__)

# Rate limiting
DELAY_BETWEEN_PAGES = float(os.getenv("CRAWLER_PAGE_DELAY", "5.0"))
MAX_CONCURRENT_PAGES = 1  # Sequential for safety

# Screenshot storage
SCREENSHOT_DIR = Path("/tmp/screenshots")


@dataclass
class PageResult:
    """Result from crawling a single page."""
    url: str
    screenshot_path: Optional[str]
    text: str
    html: str
    depth: int
    links: list
    page_title: str
    crawl_time_ms: int
    status: str = "success"  # success, failed, 404, timeout
    page_type: str = "unknown"  # team, about, contact, homepage, other


def detect_page_type(url: str, text: str = "") -> str:
    """Detect what type of page this is based on URL and content."""
    url_lower = url.lower()
    text_lower = text.lower()[:2000] if text else ""

    if any(p in url_lower for p in ["/team", "/our-team", "/leadership", "/staff", "/people", "/management"]):
        return "team"
    if any(p in url_lower for p in ["/about", "/about-us", "/company"]):
        return "about"
    if any(p in url_lower for p in ["/contact", "/contact-us", "/locations"]):
        return "contact"
    if url_lower.rstrip("/").endswith((".com", ".net", ".org")) or url_lower.count("/") <= 3:
        return "homepage"

    # Check content for team indicators
    if any(term in text_lower for term in ["our team", "meet the team", "leadership", "management team"]):
        return "team"

    return "other"


class WebsiteCrawler:
    """
    Full-site crawler using Browserbase + Playwright.

    Crawls entire website (up to max_pages) and takes screenshots
    of every page for VLM analysis.
    """

    def __init__(
        self,
        browserbase_api_key: Optional[str] = None,
        browserbase_project_id: Optional[str] = None,
    ):
        """
        Initialize crawler with Browserbase credentials.

        Args:
            browserbase_api_key: API key (or from BROWSERBASE_API_KEY env)
            browserbase_project_id: Project ID (or from BROWSERBASE_PROJECT_ID env)
        """
        self.api_key = browserbase_api_key or os.getenv("BROWSERBASE_API_KEY")
        self.project_id = browserbase_project_id or os.getenv("BROWSERBASE_PROJECT_ID")
        self.base_url = "https://api.browserbase.com/v1"

        if not self.api_key or not self.project_id:
            logger.warning("Browserbase credentials not configured")

        # Ensure screenshot directory exists
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    async def crawl_website(
        self,
        website_url: str,
        max_pages: int = 20,
        max_depth: int = 3,
        company_id: Optional[str] = None,
    ) -> list[PageResult]:
        """
        Crawl entire website and return page results with screenshots.

        Args:
            website_url: Base URL to start crawling
            max_pages: Maximum pages to crawl (default 20)
            max_depth: Maximum link depth (default 3)
            company_id: Optional company ID for organizing screenshots

        Returns:
            List of PageResult objects with screenshots
        """
        if not self.api_key or not self.project_id:
            logger.error("Browserbase not configured - cannot crawl")
            return []

        # Normalize URL
        if not website_url.startswith("http"):
            website_url = f"https://{website_url}"

        # Parse base domain for same-domain filtering
        parsed = urlparse(website_url)
        base_domain = f"{parsed.scheme}://{parsed.netloc}"

        # Create screenshot subdirectory for this company
        company_screenshot_dir = SCREENSHOT_DIR / (company_id or "unknown")
        company_screenshot_dir.mkdir(parents=True, exist_ok=True)

        # Crawl state
        crawled_urls: set[str] = set()

        # Start with homepage + priority pages for contact extraction
        priority_pages = [
            "",  # Homepage
            "/about", "/about-us", "/about-us/",
            "/team", "/our-team", "/leadership", "/leadership/",
            "/contact", "/contact-us",
            "/staff", "/people", "/management",
            "/our-leadership", "/executive-team", "/executives",
        ]

        pending_urls: list[tuple[str, int]] = []
        for page in priority_pages:
            url = f"{base_domain}{page}" if page else website_url
            pending_urls.append((url, 0))

        results: list[PageResult] = []

        logger.info(
            "Starting website crawl",
            website_url=website_url,
            max_pages=max_pages,
            max_depth=max_depth,
        )

        # Create Browserbase session
        session_id = await self._create_session()
        if not session_id:
            logger.error("Failed to create Browserbase session")
            return []

        try:
            # Get playwright connection URL
            connect_url = await self._get_connect_url(session_id)
            if not connect_url:
                logger.error("Failed to get Browserbase connect URL")
                return []

            # Connect with Playwright
            from playwright.async_api import async_playwright

            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(connect_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()

                # BFS crawl
                while pending_urls and len(results) < max_pages:
                    current_url, depth = pending_urls.pop(0)

                    # Skip if already crawled or too deep
                    if current_url in crawled_urls or depth > max_depth:
                        continue

                    # Skip non-same-domain links
                    if not current_url.startswith(base_domain):
                        continue

                    crawled_urls.add(current_url)

                    # Rate limit
                    if len(results) > 0:
                        await asyncio.sleep(DELAY_BETWEEN_PAGES)

                    # Crawl page
                    try:
                        result = await self._crawl_page(
                            page=page,
                            url=current_url,
                            depth=depth,
                            screenshot_dir=company_screenshot_dir,
                            base_domain=base_domain,
                        )

                        if result:
                            results.append(result)

                            # Add discovered links to queue
                            for link in result.links:
                                if link not in crawled_urls:
                                    pending_urls.append((link, depth + 1))

                            logger.info(
                                f"Crawled page {len(results)}/{max_pages}",
                                url=current_url,
                                links_found=len(result.links),
                                depth=depth,
                            )

                    except Exception as e:
                        logger.warning(
                            "Failed to crawl page",
                            url=current_url,
                            error=str(e),
                        )
                        continue

                await browser.close()

        finally:
            # Clean up session
            await self._close_session(session_id)

        logger.info(
            "Website crawl complete",
            website_url=website_url,
            pages_crawled=len(results),
            total_links=sum(len(r.links) for r in results),
        )

        return results

    async def _crawl_page(
        self,
        page,
        url: str,
        depth: int,
        screenshot_dir: Path,
        base_domain: str,
    ) -> Optional[PageResult]:
        """
        Crawl a single page and return result.

        Args:
            page: Playwright page object
            url: URL to crawl
            depth: Current depth
            screenshot_dir: Directory for screenshots
            base_domain: Base domain for filtering links

        Returns:
            PageResult or None if failed
        """
        start_time = time.time()

        try:
            # Navigate with networkidle for SPA support
            await page.goto(url, wait_until="networkidle", timeout=30000)

            # Extra wait for SPA content to render
            await asyncio.sleep(3.0)

            # Try to wait for common content elements
            try:
                await page.wait_for_selector("main, article, .content, #content", timeout=5000)
            except Exception:
                pass  # Continue anyway

            # Extract text content
            text_content = await page.evaluate("() => document.body?.innerText || ''")

            # Extract HTML
            html_content = await page.content()

            # Get page title
            page_title = await page.title()

            # Extract links
            links_data = await page.evaluate("""() => {
                const anchors = Array.from(document.querySelectorAll('a[href]'))
                    .map(a => a.href)
                    .filter(href => href && !href.startsWith('javascript:') && !href.startsWith('mailto:') && !href.startsWith('tel:'));
                return [...new Set(anchors)];
            }""")

            # Filter to same domain
            filtered_links = []
            for href in links_data:
                if href.startswith(base_domain):
                    # Skip common non-content pages
                    if self._should_skip_url(href):
                        continue
                    if href not in filtered_links:
                        filtered_links.append(href)

            # Take screenshot
            screenshot_path = None
            try:
                screenshot_filename = f"{uuid.uuid4().hex[:8]}.png"
                screenshot_full_path = screenshot_dir / screenshot_filename
                await page.screenshot(path=str(screenshot_full_path), full_page=True)
                screenshot_path = str(screenshot_full_path)
            except Exception as e:
                logger.warning("Screenshot failed", url=url, error=str(e))

            crawl_time_ms = int((time.time() - start_time) * 1000)

            return PageResult(
                url=url,
                screenshot_path=screenshot_path,
                text=text_content[:50000] if text_content else "",  # Limit size
                html=html_content[:100000] if html_content else "",  # Limit size
                depth=depth,
                links=filtered_links,
                page_title=page_title,
                crawl_time_ms=crawl_time_ms,
            )

        except Exception as e:
            logger.error("Page crawl failed", url=url, error=str(e))
            return None

    def _should_skip_url(self, url: str) -> bool:
        """
        Check if URL should be skipped (non-content pages).

        Args:
            url: URL to check

        Returns:
            True if URL should be skipped
        """
        skip_patterns = [
            # File types
            ".pdf", ".doc", ".docx", ".xls", ".xlsx", ".zip", ".rar",
            ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
            ".mp3", ".mp4", ".avi", ".mov",
            # Common non-content paths
            "/wp-content/", "/wp-admin/", "/wp-includes/",
            "/cdn-cgi/", "/assets/", "/static/",
            "/login", "/logout", "/signup", "/register",
            "/cart", "/checkout", "/account",
            "/search", "/feed", "/rss",
            "#",  # Anchors
        ]

        url_lower = url.lower()
        return any(pattern in url_lower for pattern in skip_patterns)

    async def _create_session(self) -> Optional[str]:
        """Create a Browserbase session."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/sessions",
                    headers={
                        "X-BB-API-Key": self.api_key,
                        "Content-Type": "application/json",
                    },
                    json={"projectId": self.project_id},
                    timeout=30.0,
                )
                response.raise_for_status()
                data = response.json()
                return data.get("id")
            except Exception as e:
                logger.error("Failed to create Browserbase session", error=str(e))
                return None

    async def _get_connect_url(self, session_id: str) -> Optional[str]:
        """Get Playwright connect URL for session."""
        return f"wss://connect.browserbase.com?apiKey={self.api_key}&sessionId={session_id}"

    async def _close_session(self, session_id: str) -> None:
        """Close a Browserbase session."""
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{self.base_url}/sessions/{session_id}/stop",
                    headers={"X-BB-API-Key": self.api_key},
                    timeout=10.0,
                )
            except Exception as e:
                logger.warning("Failed to close Browserbase session", error=str(e))


# Convenience function for quick testing
async def test_crawler(
    website_url: str,
    max_pages: int = 5,
    company_id: str = "test",
) -> list[PageResult]:
    """
    Quick test function for website crawler.

    Args:
        website_url: URL to crawl
        max_pages: Max pages to crawl
        company_id: Company ID for screenshots

    Returns:
        List of page results
    """
    crawler = WebsiteCrawler()
    results = await crawler.crawl_website(
        website_url=website_url,
        max_pages=max_pages,
        company_id=company_id,
    )

    print(f"\n=== Crawl Results ===")
    print(f"Pages crawled: {len(results)}")
    for r in results:
        print(f"  - {r.url} (depth={r.depth}, screenshot={r.screenshot_path is not None})")

    return results
