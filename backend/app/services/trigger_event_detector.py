"""
Trigger Event Detector Service

Detects buying signals for ICP companies:
- Funding rounds
- Hiring activity
- News/press releases
- Executive changes
- Tech stack changes

Uses free web scraping via Browserbase/Playwright (NO paid APIs).
"""

import asyncio
import logging
import re
from datetime import datetime, date, timedelta
from typing import List, Dict, Optional, Tuple
from uuid import UUID
import httpx
from pathlib import Path

from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parents[3] / '.env'
if _env_path.exists():
    load_dotenv(_env_path, override=True)

from app.models.trigger_event import TriggerEvent, TriggerEventType, TriggerEventSource
from supabase import create_client
import os

logger = logging.getLogger(__name__)

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY")
supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY) if SUPABASE_URL and SUPABASE_SERVICE_KEY else None


class TriggerEventDetector:
    """
    Detects buying signals for ICP companies using free web scraping.

    Detection methods:
    - detect_funding_signals(): TechCrunch, Crunchbase, VentureBeat
    - detect_hiring_signals(): Company careers pages
    - detect_news_signals(): Google News RSS
    - detect_executive_changes(): LinkedIn scraping
    """

    # Funding signal keywords
    FUNDING_KEYWORDS = [
        r"raised \$\d+[MK]?",  # "raised $15M"
        r"series [A-D]",
        r"seed round",
        r"funding round",
        r"investment",
        r"venture capital",
        r"vc funding"
    ]

    # Hiring signal keywords
    HIRING_KEYWORDS = [
        "we're hiring",
        "now hiring",
        "join our team",
        "open positions",
        "careers",
        "job openings",
        "we are hiring",
        "help wanted"
    ]

    def __init__(self):
        """Initialize trigger event detector."""
        self.supabase = supabase
        if not self.supabase:
            logger.warning("Supabase not configured - trigger events will not be saved")

    async def detect_all_signals(
        self,
        company_id: UUID,
        company_name: str,
        domain: Optional[str] = None
    ) -> List[TriggerEvent]:
        """
        Run all detection methods for a company.

        Args:
            company_id: Company UUID
            company_name: Company name for searches
            domain: Company domain for website scraping

        Returns:
            List of detected trigger events
        """
        logger.info(f"Detecting trigger events for: {company_name}")

        # Run all detectors in parallel
        results = await asyncio.gather(
            self.detect_funding_signals(company_id, company_name),
            self.detect_hiring_signals(company_id, company_name, domain),
            self.detect_news_signals(company_id, company_name),
            return_exceptions=True
        )

        # Flatten results and filter exceptions
        events = []
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"Detection error: {result}")
            elif isinstance(result, list):
                events.extend(result)

        logger.info(f"Detected {len(events)} trigger events for {company_name}")

        # Save to database
        if events and self.supabase:
            await self._save_events(events)

        return events

    async def detect_funding_signals(
        self,
        company_id: UUID,
        company_name: str
    ) -> List[TriggerEvent]:
        """
        Detect funding rounds via web scraping (TechCrunch, Crunchbase).

        Args:
            company_id: Company UUID
            company_name: Company name

        Returns:
            List of funding trigger events
        """
        events = []

        try:
            # Search TechCrunch for funding news
            techcrunch_events = await self._scrape_techcrunch_funding(company_id, company_name)
            events.extend(techcrunch_events)

            # Search Crunchbase public pages
            crunchbase_events = await self._scrape_crunchbase_funding(company_id, company_name)
            events.extend(crunchbase_events)

        except Exception as e:
            logger.error(f"Funding signal detection error for {company_name}: {e}")

        return events

    async def _scrape_techcrunch_funding(
        self,
        company_id: UUID,
        company_name: str
    ) -> List[TriggerEvent]:
        """
        Scrape TechCrunch for funding announcements.

        URL: https://search.techcrunch.com/search?p={company_name}+funding
        """
        events = []

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # TechCrunch search (publicly accessible)
                search_url = f"https://search.techcrunch.com/search"
                params = {"p": f"{company_name} funding"}

                response = await client.get(search_url, params=params)
                response.raise_for_status()

                # Simple regex-based extraction (no BeautifulSoup to keep it fast)
                text = response.text.lower()

                # Check for funding keywords
                for pattern in self.FUNDING_KEYWORDS:
                    matches = re.finditer(pattern, text, re.IGNORECASE)
                    for match in matches:
                        # Extract context around match
                        start = max(0, match.start() - 200)
                        end = min(len(text), match.end() + 200)
                        context = text[start:end]

                        # Create event
                        event = TriggerEvent(
                            company_id=company_id,
                            event_type=TriggerEventType.FUNDING,
                            title=f"{company_name} - {match.group()}",
                            description=context[:500],  # First 500 chars
                            source_url=search_url,
                            source_type=TriggerEventSource.WEB_SCRAPE,
                            details={"source": "techcrunch"}
                        )
                        event.signal_strength = event.calculate_signal_strength()
                        events.append(event)
                        break  # Only one event per company from TechCrunch

        except Exception as e:
            logger.error(f"TechCrunch scraping error: {e}")

        return events

    async def _scrape_crunchbase_funding(
        self,
        company_id: UUID,
        company_name: str
    ) -> List[TriggerEvent]:
        """
        Scrape Crunchbase public pages for funding info.

        URL: https://www.crunchbase.com/organization/{company_slug}
        """
        events = []

        try:
            # Convert company name to slug (e.g., "Acme Corp" -> "acme-corp")
            slug = company_name.lower().replace(" ", "-").replace(",", "").replace(".", "")

            async with httpx.AsyncClient(timeout=15.0) as client:
                url = f"https://www.crunchbase.com/organization/{slug}"

                response = await client.get(url)
                if response.status_code == 404:
                    logger.debug(f"Crunchbase profile not found for: {company_name}")
                    return events

                response.raise_for_status()

                text = response.text

                # Look for funding indicators
                funding_patterns = [
                    r"Total Funding Amount.*?\$([0-9.]+)([MBK])",
                    r"Last Funding Type.*?(Series [A-D]|Seed|IPO)",
                    r"Last Funding Date.*?(\d{4})"
                ]

                details = {}
                for pattern in funding_patterns:
                    match = re.search(pattern, text, re.IGNORECASE)
                    if match:
                        details["funding_info"] = match.group()

                if details:
                    event = TriggerEvent(
                        company_id=company_id,
                        event_type=TriggerEventType.FUNDING,
                        title=f"{company_name} - Funding Activity on Crunchbase",
                        description=f"Found funding information on Crunchbase profile",
                        source_url=url,
                        source_type=TriggerEventSource.WEB_SCRAPE,
                        details=details
                    )
                    event.signal_strength = event.calculate_signal_strength()
                    events.append(event)

        except Exception as e:
            logger.error(f"Crunchbase scraping error: {e}")

        return events

    async def detect_hiring_signals(
        self,
        company_id: UUID,
        company_name: str,
        domain: Optional[str] = None
    ) -> List[TriggerEvent]:
        """
        Detect hiring activity by scraping company careers pages.

        Args:
            company_id: Company UUID
            company_name: Company name
            domain: Company domain (e.g., "acme.com")

        Returns:
            List of hiring trigger events
        """
        events = []

        if not domain:
            logger.debug(f"No domain for {company_name}, skipping hiring detection")
            return events

        try:
            # Common careers page URLs
            careers_paths = [
                "/careers",
                "/jobs",
                "/about/careers",
                "/company/careers",
                "/join-us",
                "/work-with-us"
            ]

            async with httpx.AsyncClient(timeout=10.0) as client:
                for path in careers_paths:
                    try:
                        url = f"https://{domain}{path}"
                        response = await client.get(url)

                        if response.status_code != 200:
                            continue

                        text = response.text.lower()

                        # Count job-related keywords
                        hiring_score = 0
                        for keyword in self.HIRING_KEYWORDS:
                            if keyword in text:
                                hiring_score += 1

                        # Count job listings (rough estimate)
                        job_count = len(re.findall(r'job-listing|job-item|position-', text))

                        if hiring_score >= 2 or job_count >= 3:
                            event = TriggerEvent(
                                company_id=company_id,
                                event_type=TriggerEventType.HIRING,
                                title=f"{company_name} - Active Hiring ({job_count}+ jobs)",
                                description=f"Found {job_count} job listings on careers page",
                                source_url=url,
                                source_type=TriggerEventSource.WEB_SCRAPE,
                                details={"job_count": job_count, "hiring_score": hiring_score}
                            )
                            event.signal_strength = event.calculate_signal_strength()
                            events.append(event)
                            break  # Found careers page, stop searching

                    except httpx.HTTPError:
                        continue

        except Exception as e:
            logger.error(f"Hiring signal detection error for {company_name}: {e}")

        return events

    async def detect_news_signals(
        self,
        company_id: UUID,
        company_name: str
    ) -> List[TriggerEvent]:
        """
        Detect company news via Google News RSS (free, no API key).

        Args:
            company_id: Company UUID
            company_name: Company name

        Returns:
            List of news trigger events
        """
        events = []

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Google News RSS is free and doesn't require API key
                url = f"https://news.google.com/rss/search?q={company_name}"

                response = await client.get(url)
                response.raise_for_status()

                # Parse XML for recent articles (last 30 days)
                text = response.text

                # Simple XML parsing without lxml
                titles = re.findall(r'<title><!\[CDATA\[(.*?)\]\]></title>', text)
                pub_dates = re.findall(r'<pubDate>(.*?)</pubDate>', text)
                links = re.findall(r'<link>(.*?)</link>', text)

                # Check each article
                for i, title in enumerate(titles[:5]):  # Top 5 articles only
                    # Skip Google News header
                    if company_name.lower() not in title.lower():
                        continue

                    # Check for newsworthy keywords
                    newsworthy_keywords = [
                        "partnership", "acquisition", "acquired", "merger",
                        "launch", "announced", "award", "expansion"
                    ]

                    is_newsworthy = any(kw in title.lower() for kw in newsworthy_keywords)

                    if is_newsworthy:
                        event = TriggerEvent(
                            company_id=company_id,
                            event_type=TriggerEventType.NEWS,
                            title=f"{company_name} - {title[:100]}",
                            description=title,
                            source_url=links[i] if i < len(links) else url,
                            source_type=TriggerEventSource.WEB_SCRAPE,
                            details={"article_title": title}
                        )
                        event.signal_strength = event.calculate_signal_strength()
                        events.append(event)

        except Exception as e:
            logger.error(f"News signal detection error for {company_name}: {e}")

        return events

    async def _save_events(self, events: List[TriggerEvent]) -> None:
        """
        Save trigger events to Supabase.

        Implements deduplication via content_hash unique constraint.
        """
        if not self.supabase:
            logger.warning("Supabase not configured, cannot save events")
            return

        for event in events:
            try:
                # Convert to dict for Supabase
                event_dict = event.dict(exclude_none=True, exclude={"created_at", "updated_at", "event_id"})

                # Insert (will fail silently on duplicate hash)
                result = self.supabase.table("trigger_events").insert(event_dict).execute()

                if result.data:
                    logger.info(f"Saved trigger event: {event.title}")
                else:
                    logger.debug(f"Skipped duplicate event: {event.title}")

            except Exception as e:
                # Duplicate constraint violation is expected and OK
                if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                    logger.debug(f"Skipped duplicate: {event.title}")
                else:
                    logger.error(f"Error saving event: {e}")


# Singleton instance
_detector: Optional[TriggerEventDetector] = None


async def get_trigger_event_detector() -> TriggerEventDetector:
    """Get or create singleton trigger event detector."""
    global _detector
    if _detector is None:
        _detector = TriggerEventDetector()
    return _detector
