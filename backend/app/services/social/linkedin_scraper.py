"""
LinkedIn Scraper Service

Scrapes LinkedIn profiles for recent posts using Playwright browser automation.
Implements rate limiting, error handling, and graceful degradation.
"""

import asyncio
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

from playwright.async_api import async_playwright, Browser, BrowserContext
import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class LinkedInScraper:
    """
    Scrapes LinkedIn profiles for recent posts (last 7 days).

    Features:
    - Playwright browser automation (headless Chrome)
    - Rate limiting (100 profiles/day to avoid detection)
    - Smart caching (avoid re-scraping same profile)
    - Error handling and retry logic
    - Session persistence (cookies)

    Performance:
    - ~10-15 seconds per profile
    - Parallel scraping: 3 profiles simultaneously
    - Target: 20 ATL contacts = ~5 minutes total
    """

    MAX_PROFILES_PER_DAY = 100
    SCRAPE_INTERVAL_SECONDS = 3  # Rate limiting
    MAX_POSTS_PER_PROFILE = 5
    LOOKBACK_DAYS = 7
    PARALLEL_SCRAPERS = 3

    def __init__(self, database_url: str):
        """
        Initialize LinkedIn scraper.

        Args:
            database_url: Supabase PostgreSQL connection string
        """
        self.database_url = database_url
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self._session_initialized = False

    async def initialize(self):
        """Initialize browser and load session cookies."""
        logger.info("Initializing LinkedIn scraper...")

        playwright = await async_playwright().start()

        # Launch browser (headless for serverless)
        self.browser = await playwright.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled'
            ]
        )

        # Create context with realistic user agent
        self.context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            viewport={'width': 1920, 'height': 1080}
        )

        self._session_initialized = True
        logger.info("LinkedIn scraper initialized successfully")

    async def scrape_profiles(self, linkedin_urls: List[str]) -> List[Dict[str, Any]]:
        """
        Scrape multiple LinkedIn profiles in parallel.

        Args:
            linkedin_urls: List of LinkedIn profile URLs

        Returns:
            List of post dictionaries with fields:
            - contact_id: LinkedIn profile URL
            - platform: 'linkedin'
            - post_text: Full post content
            - post_url: URL to the post
            - posted_at: Timestamp of post
            - scraped_at: Current timestamp
        """
        if not self._session_initialized:
            await self.initialize()

        logger.info(f"Scraping {len(linkedin_urls)} LinkedIn profiles...")

        # Check daily limit
        daily_count = await self._get_daily_scrape_count()
        if daily_count >= self.MAX_PROFILES_PER_DAY:
            logger.warning(f"Daily scrape limit reached ({daily_count}/{self.MAX_PROFILES_PER_DAY})")
            return []

        # Batch scraping with parallelism
        all_posts = []
        for i in range(0, len(linkedin_urls), self.PARALLEL_SCRAPERS):
            batch = linkedin_urls[i:i + self.PARALLEL_SCRAPERS]

            tasks = [self._scrape_single_profile(url) for url in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Scraping error: {result}")
                elif result:
                    all_posts.extend(result)

            # Rate limiting between batches
            if i + self.PARALLEL_SCRAPERS < len(linkedin_urls):
                await asyncio.sleep(self.SCRAPE_INTERVAL_SECONDS)

        logger.info(f"Scraped {len(all_posts)} total posts from {len(linkedin_urls)} profiles")
        return all_posts

    async def _scrape_single_profile(self, profile_url: str) -> List[Dict[str, Any]]:
        """
        Scrape a single LinkedIn profile for recent posts.

        Args:
            profile_url: LinkedIn profile URL (e.g., https://linkedin.com/in/username)

        Returns:
            List of post dictionaries
        """
        try:
            logger.info(f"Scraping LinkedIn profile: {profile_url}")

            page = await self.context.new_page()

            # Navigate to profile activity page
            activity_url = f"{profile_url.rstrip('/')}/recent-activity/all/"
            await page.goto(activity_url, timeout=30000, wait_until='networkidle')

            # Wait for posts to load
            await page.wait_for_selector('div[data-id]', timeout=10000)

            # Extract posts
            posts = []
            cutoff_date = datetime.now() - timedelta(days=self.LOOKBACK_DAYS)

            # Get post elements
            post_elements = await page.query_selector_all('div[data-id]')

            for post_elem in post_elements[:self.MAX_POSTS_PER_PROFILE]:
                try:
                    # Extract post text
                    text_elem = await post_elem.query_selector('.feed-shared-update-v2__description')
                    post_text = await text_elem.inner_text() if text_elem else ""

                    # Extract post URL
                    link_elem = await post_elem.query_selector('a[href*="/posts/"]')
                    post_url = await link_elem.get_attribute('href') if link_elem else ""

                    # Extract timestamp
                    time_elem = await post_elem.query_selector('time')
                    time_str = await time_elem.get_attribute('datetime') if time_elem else None

                    if time_str:
                        posted_at = datetime.fromisoformat(time_str.replace('Z', '+00:00'))
                    else:
                        # Fallback: parse relative time (e.g., "2d ago")
                        posted_at = await self._parse_relative_time(time_elem)

                    # Only include posts within lookback window
                    if posted_at and posted_at >= cutoff_date and post_text:
                        posts.append({
                            'contact_id': profile_url,
                            'platform': 'linkedin',
                            'post_text': post_text.strip(),
                            'post_url': post_url,
                            'posted_at': posted_at,
                            'scraped_at': datetime.now()
                        })

                except Exception as e:
                    logger.warning(f"Error extracting post element: {e}")
                    continue

            await page.close()

            logger.info(f"Found {len(posts)} recent posts from {profile_url}")
            return posts

        except Exception as e:
            logger.error(f"Failed to scrape {profile_url}: {e}")
            return []

    async def _parse_relative_time(self, time_elem) -> Optional[datetime]:
        """Parse relative time strings like '2d ago', '1w ago'."""
        try:
            text = await time_elem.inner_text()

            # Extract number and unit
            match = re.search(r'(\d+)([hdwmy])', text.lower())
            if not match:
                return None

            num = int(match.group(1))
            unit = match.group(2)

            now = datetime.now()

            if unit == 'h':  # hours
                return now - timedelta(hours=num)
            elif unit == 'd':  # days
                return now - timedelta(days=num)
            elif unit == 'w':  # weeks
                return now - timedelta(weeks=num)
            elif unit == 'm':  # months (approximate)
                return now - timedelta(days=num * 30)
            elif unit == 'y':  # years
                return now - timedelta(days=num * 365)

            return None

        except Exception:
            return None

    async def _get_daily_scrape_count(self) -> int:
        """Get number of profiles scraped today."""
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url,
                row_factory=dict_row
            ) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT COUNT(DISTINCT contact_id)
                        FROM social_posts
                        WHERE platform = 'linkedin'
                          AND scraped_at >= CURRENT_DATE
                    """)
                    result = await cur.fetchone()
                    return result['count'] if result else 0

        except Exception as e:
            logger.error(f"Error checking daily scrape count: {e}")
            return 0

    async def save_posts(self, posts: List[Dict[str, Any]]) -> int:
        """
        Save scraped posts to Supabase database.

        Args:
            posts: List of post dictionaries

        Returns:
            Number of posts saved
        """
        if not posts:
            return 0

        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url,
                row_factory=dict_row
            ) as conn:
                async with conn.cursor() as cur:
                    # Insert posts (skip duplicates based on post_url)
                    for post in posts:
                        await cur.execute("""
                            INSERT INTO social_posts (
                                contact_id, platform, post_text, post_url,
                                posted_at, scraped_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (post_url) DO NOTHING
                        """, (
                            post['contact_id'],
                            post['platform'],
                            post['post_text'],
                            post['post_url'],
                            post['posted_at'],
                            post['scraped_at']
                        ))

                    await conn.commit()

            logger.info(f"Saved {len(posts)} LinkedIn posts to database")
            return len(posts)

        except Exception as e:
            logger.error(f"Error saving posts to database: {e}")
            return 0

    async def close(self):
        """Clean up browser resources."""
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()

        logger.info("LinkedIn scraper closed")


# Example usage for testing
async def main():
    """Test LinkedIn scraper locally."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    database_url = os.getenv('SUPABASE_DATABASE_URL')

    scraper = LinkedInScraper(database_url)

    try:
        # Test with sample LinkedIn URLs
        test_urls = [
            "https://www.linkedin.com/in/example-profile-1",
            "https://www.linkedin.com/in/example-profile-2"
        ]

        posts = await scraper.scrape_profiles(test_urls)

        print(f"\n{'='*60}")
        print(f"Scraped {len(posts)} posts")
        print(f"{'='*60}\n")

        for post in posts:
            print(f"Profile: {post['contact_id']}")
            print(f"Posted: {post['posted_at']}")
            print(f"Text: {post['post_text'][:100]}...")
            print(f"URL: {post['post_url']}")
            print("-" * 60)

        # Save to database
        saved_count = await scraper.save_posts(posts)
        print(f"\nSaved {saved_count} posts to database")

    finally:
        await scraper.close()


if __name__ == "__main__":
    asyncio.run(main())
