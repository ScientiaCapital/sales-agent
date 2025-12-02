#!/usr/bin/env python3
"""
DEEP Company Scraper (Browserbase + Playwright)
===============================================

Comprehensive scraping of company websites AND LinkedIn using Browserbase.

Pages scraped per company:
1. WEBSITE - Landing page (founder, owner mentions in hero/footer)
2. WEBSITE - /team, /our-team, /leadership, /about-us/team
3. WEBSITE - /about, /about-us, /company
4. WEBSITE - /contact, /contact-us (address, phone, email verification)
5. LINKEDIN - Company page (employee count, visible employees, ATL)

Data extracted:
- ATL contacts (CEO, Owner, President, VP, Director, Founder)
- BTL contacts (Managers, Coordinators, Sales, etc.)
- Phone numbers (with source tracking)
- Emails (general contact + team member emails)
- Addresses (for territory assignment)
- Employee count from LinkedIn

Usage:
    python deep_scrape_companies.py --test 5        # Test with 5 companies
    python deep_scrape_companies.py --top 500       # Top 500 by score
    python deep_scrape_companies.py --all           # All 1,000 companies
    python deep_scrape_companies.py --resume        # Resume from progress

Estimated Time: 1,000 companies @ 30s each = ~8 hours with 10 concurrent
"""

import asyncio
import logging
import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime
import argparse
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field, asdict
from urllib.parse import urljoin, urlparse

# Check critical dependencies early
try:
    import pandas as pd
except ImportError:
    print("ERROR: pandas is not installed. Run: pip install pandas")
    sys.exit(1)

try:
    from supabase import create_client
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("WARNING: supabase not installed. Supabase sync disabled.")
    create_client = None

# Supabase client (lazy init)
_supabase_client = None

def get_supabase():
    """Get or create Supabase client."""
    global _supabase_client
    if _supabase_client is None and create_client:
        url = os.getenv('SUPABASE_URL')
        key = os.getenv('SUPABASE_SERVICE_KEY')
        if url and key:
            _supabase_client = create_client(url, key)
    return _supabase_client

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: Playwright is not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

# Load environment variables (override=True to prefer .env over shell vars)
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Setup logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
log_file = log_dir / f"deep_scrape_{timestamp_str}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

# Browserbase config
BROWSERBASE_API_KEY = os.getenv('BROWSERBASE_API_KEY')
BROWSERBASE_PROJECT_ID = os.getenv('BROWSERBASE_PROJECT_ID')
MAX_CONCURRENT = int(os.getenv('BROWSERBASE_MAX_CONCURRENT', '10'))

# Rate limit: Developer plan = 25 sessions/minute, Startup plan = 50 sessions/minute
# We use 20/min to stay safely under the limit
SESSIONS_PER_MINUTE = int(os.getenv('BROWSERBASE_SESSIONS_PER_MINUTE', '20'))


class RateLimiter:
    """Token bucket rate limiter for Browserbase session creation."""

    def __init__(self, rate_per_minute: int):
        self.rate = rate_per_minute
        self.interval = 60.0 / rate_per_minute  # seconds between tokens
        self.last_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Wait until a session creation token is available."""
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait_time = self.last_time + self.interval - now
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self.last_time = asyncio.get_event_loop().time()


# Global rate limiter (initialized in main)
_rate_limiter: Optional[RateLimiter] = None

# Validate critical environment variables
if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
    logger.error("ERROR: BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID must be set in .env")
    logger.error("Run the validation script: python backend/validate_deep_scrape_prerequisites.py")
    sys.exit(1)

# Paths
INPUT_DIR = Path('data/final_enrichment_output')
OUTPUT_DIR = Path('data/final_enrichment_output')

# ATL and BTL title keywords
ATL_TITLES = [
    'ceo', 'chief executive', 'president', 'owner', 'founder', 'co-founder',
    'cto', 'chief technology', 'cfo', 'chief financial', 'coo', 'chief operating',
    'vp', 'vice president', 'svp', 'evp', 'director', 'head of',
    'general manager', 'partner', 'principal', 'managing director'
]

BTL_TITLES = [
    'manager', 'coordinator', 'supervisor', 'lead', 'specialist',
    'sales', 'account', 'representative', 'technician', 'installer',
    'service', 'operations', 'admin', 'assistant', 'secretary',
    'hr', 'human resources', 'marketing', 'analyst'
]

# Trade detection keywords for multi-trade ICP scoring
TRADE_KEYWORDS = {
    'hvac': ['hvac', 'heating', 'cooling', 'air conditioning', 'a/c', 'ac ', 'furnace', 'heat pump', 'mechanical'],
    'plumbing': ['plumbing', 'plumber', 'drain', 'sewer', 'water heater', 'pipe', 'piping'],
    'electrical': ['electrical', 'electrician', 'wiring', 'panel', 'electric '],
    'roofing': ['roofing', 'roofer', 'shingle', 'roof repair', 'roof installation'],
    'general': ['general contractor', 'self-performing', 'self performing', 'design-build', 'design build'],
    'energy': ['solar', 'battery', 'generator', 'energy', 'ev charger', 'renewable'],
}


def detect_trades(text: str) -> List[str]:
    """Detect trades mentioned in website text."""
    if not text:
        return []
    text_lower = text.lower()
    detected = []
    for trade, keywords in TRADE_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            detected.append(trade)
    return detected


def detect_family_owned(text: str) -> bool:
    """Detect if company is family-owned."""
    if not text:
        return False
    text_lower = text.lower()
    patterns = ['family owned', 'family-owned', 'family business', 'family run', 'family operated']
    return any(p in text_lower for p in patterns)


def detect_years_in_business(text: str) -> int:
    """Extract years in business from 'Since 1962', 'Est. 1985', etc."""
    if not text:
        return 0
    import re
    from datetime import datetime
    current_year = datetime.now().year

    # Patterns: "Since 1962", "Est. 1985", "Established 1970", "Founded in 1990"
    patterns = [
        r'since\s+(\d{4})',
        r'est\.?\s+(\d{4})',
        r'established\s+(\d{4})',
        r'founded\s+(?:in\s+)?(\d{4})',
        r'serving\s+since\s+(\d{4})',
    ]

    for pattern in patterns:
        match = re.search(pattern, text.lower())
        if match:
            year = int(match.group(1))
            if 1900 <= year <= current_year:
                return current_year - year
    return 0


@dataclass
class PhoneRecord:
    number: str
    source: str
    page_url: str


@dataclass
class EmailRecord:
    email: str
    source: str
    person_name: str = ""


@dataclass
class PersonRecord:
    name: str
    title: str
    is_atl: bool
    source: str
    email: str = ""
    phone: str = ""
    linkedin_url: str = ""


@dataclass
class DeepScrapeResult:
    """Complete deep scrape data for one company."""
    company_name: str
    domain: str

    # Existing data from previous enrichment (for audit trail)
    existing_primary_phone: str = ""
    existing_phones: List[str] = field(default_factory=list)

    # Website data
    website_reachable: bool = False
    pages_scraped: List[str] = field(default_factory=list)

    # People found
    atl_contacts: List[Dict] = field(default_factory=list)
    btl_contacts: List[Dict] = field(default_factory=list)

    # Contact info - with audit trail
    phones: List[Dict] = field(default_factory=list)
    emails: List[Dict] = field(default_factory=list)

    # Phone audit trail
    new_phones: List[Dict] = field(default_factory=list)      # Phones NOT in existing data
    verified_phones: List[Dict] = field(default_factory=list)  # Phones that MATCH existing data

    # Address
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""

    # LinkedIn data
    linkedin_url: str = ""
    linkedin_found: bool = False
    linkedin_employee_count: str = ""
    linkedin_employee_count_numeric: int = 0

    # Stats
    atl_count: int = 0
    btl_count: int = 0
    phone_count: int = 0
    email_count: int = 0
    new_phone_count: int = 0
    verified_phone_count: int = 0

    # Multi-trade detection (ICP signal)
    trades_detected: List[str] = field(default_factory=list)  # ['hvac', 'plumbing', 'electrical']
    is_multi_trade: bool = False  # True if 2+ trades detected
    trade_count: int = 0
    family_owned: bool = False  # "Family owned", "Family business"
    years_in_business: int = 0  # Extracted from "Since 1962", "Est. 1985"

    # Meta
    scrape_duration_seconds: float = 0.0
    scrape_errors: List[str] = field(default_factory=list)
    scrape_timestamp: str = ""


def normalize_phone(phone: str) -> str:
    """Normalize phone number to digits only."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    return digits if len(digits) >= 10 else ""


def is_valid_email(email: str) -> bool:
    """Check if email looks valid."""
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def is_atl(title: str) -> bool:
    """Check if title is Above The Line."""
    if not title:
        return False
    title_lower = title.lower()
    return any(t in title_lower for t in ATL_TITLES)


def is_btl(title: str) -> bool:
    """Check if title is Below The Line."""
    if not title:
        return False
    title_lower = title.lower()
    return any(t in title_lower for t in BTL_TITLES) and not is_atl(title)


async def create_browserbase_session(max_retries: int = 3) -> tuple:
    """Create a Browserbase browser session with rate limiting and retry on 429."""
    import httpx

    # Respect rate limit (Developer plan = 25/min, Startup = 50/min)
    global _rate_limiter
    if _rate_limiter:
        await _rate_limiter.acquire()

    last_error = None
    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.browserbase.com/v1/sessions",
                    headers={
                        "x-bb-api-key": BROWSERBASE_API_KEY,
                        "Content-Type": "application/json"
                    },
                    json={"projectId": BROWSERBASE_PROJECT_ID}
                )

                # Handle rate limit with exponential backoff
                if response.status_code == 429:
                    wait_time = (2 ** attempt) * 5  # 5s, 10s, 20s
                    logger.warning(f"Rate limited (429), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                    await asyncio.sleep(wait_time)
                    continue

                response.raise_for_status()
                data = response.json()
                session_id = data["id"]
                connect_url = data.get("connectUrl")
                if not connect_url:
                    # SECURITY: Never construct URL with API key - it would appear in logs
                    raise ValueError(f"Browserbase API did not return connectUrl for session {session_id[:8]}...")
                return session_id, connect_url

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                wait_time = (2 ** attempt) * 5
                logger.warning(f"Rate limited (429), waiting {wait_time}s before retry {attempt + 1}/{max_retries}")
                await asyncio.sleep(wait_time)
                last_error = e
            else:
                raise
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                await asyncio.sleep(2)

    raise last_error or Exception("Failed to create session after retries")


async def close_browserbase_session(session_id: str):
    """Close a Browserbase session."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.browserbase.com/v1/sessions/{session_id}/stop",
                headers={"x-bb-api-key": BROWSERBASE_API_KEY}
            )
    except Exception as e:
        logger.warning(f"Failed to close Browserbase session {session_id}: {str(e)}")
        # Session cleanup failure is not critical - session will auto-expire


async def extract_phones_from_page(page, result: DeepScrapeResult, page_url: str):
    """Extract phone numbers from current page - with audit trail (NEW vs VERIFIED)."""
    try:
        content = await page.content()

        # US phone pattern - must have separators or parentheses to be a real phone
        patterns = [
            r'\(\d{3}\)\s*\d{3}[-.\s]\d{4}',           # (123) 456-7890
            r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',            # 123-456-7890 or 123.456.7890
            r'\+1[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]\d{4}',  # +1 (123) 456-7890
            r'tel:\+?1?\d{10}',                         # tel: links
        ]

        found_phones: Set[str] = set()
        for pattern in patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                normalized = normalize_phone(match)

                # Validate: must be exactly 10 digits, valid area code
                if not normalized or len(normalized) != 10:
                    continue

                # Skip obvious invalid patterns
                area_code = normalized[:3]
                if area_code in ['000', '111', '123', '555', '800', '888', '877', '866', '900']:
                    continue
                if normalized.startswith('0') or normalized.startswith('1'):
                    continue

                # Check it's not already found in this scrape
                existing_in_scrape = {normalize_phone(p['number']) for p in result.phones}
                if normalized in existing_in_scrape or normalized in found_phones:
                    continue

                found_phones.add(normalized)

                phone_record = {
                    'number': match.strip(),
                    'normalized': normalized,
                    'source': page_url
                }

                result.phones.append(phone_record)

                # AUDIT TRAIL: Check if this phone was already in existing data
                if normalized in result.existing_phones:
                    # VERIFIED - same phone found again
                    phone_record['audit_status'] = 'VERIFIED'
                    result.verified_phones.append(phone_record)
                    logger.info(f"    📞 VERIFIED: {match} (matches existing)")
                else:
                    # NEW - phone not in existing data
                    phone_record['audit_status'] = 'NEW'
                    result.new_phones.append(phone_record)
                    logger.info(f"    📞 NEW: {match} (from {page_url})")

    except Exception as e:
        logger.debug(f"Phone extraction error: {e}")


async def extract_emails_from_page(page, result: DeepScrapeResult, page_url: str):
    """Extract email addresses from current page."""
    try:
        content = await page.content()

        # Email regex
        pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        matches = re.findall(pattern, content)

        existing = {e['email'].lower() for e in result.emails}

        for email in matches:
            email_lower = email.lower()
            # Skip common non-person emails
            skip_patterns = ['example.com', 'domain.com', 'email.com', 'test.', 'noreply', 'no-reply']
            if any(skip in email_lower for skip in skip_patterns):
                continue

            if email_lower not in existing:
                existing.add(email_lower)
                result.emails.append({
                    'email': email,
                    'source': page_url,
                    'person_name': ''
                })

    except Exception as e:
        logger.debug(f"Email extraction error: {e}")


async def extract_people_from_page(page, result: DeepScrapeResult, page_url: str):
    """Extract people (ATL/BTL) from team/about pages - structured AND text-based."""
    try:
        # METHOD 1: Structured team member cards
        card_selectors = [
            '[class*="team-member"]',
            '[class*="team_member"]',
            '[class*="staff-member"]',
            '[class*="person"]',
            '[class*="bio"]',
            '[class*="leadership"]',
            '[class*="executive"]',
            'div[class*="team"] > div',
            'section[class*="team"] div[class*="card"]',
            'article[class*="team"]'
        ]

        for selector in card_selectors:
            cards = await page.query_selector_all(selector)
            if not cards:
                continue

            for card in cards[:30]:
                try:
                    name_elem = await card.query_selector('h2, h3, h4, strong, [class*="name"], [class*="title"]')
                    name = await name_elem.inner_text() if name_elem else None

                    if not name or len(name) < 3 or len(name) > 50:
                        continue

                    title_elem = await card.query_selector('p, span[class*="role"], span[class*="position"], [class*="job"]')
                    title = await title_elem.inner_text() if title_elem else ""

                    email_elem = await card.query_selector('a[href^="mailto:"]')
                    email = ""
                    if email_elem:
                        href = await email_elem.get_attribute('href')
                        email = href.replace('mailto:', '') if href else ""

                    name = name.strip()
                    title = title.strip()[:100] if title else ""

                    person_is_atl = is_atl(title)
                    person_is_btl = is_btl(title) if not person_is_atl else False

                    existing_names = {p['name'].lower() for p in result.atl_contacts + result.btl_contacts}
                    if name.lower() in existing_names:
                        continue

                    person = {
                        'name': name,
                        'title': title,
                        'email': email,
                        'source': page_url,
                        'extraction_method': 'structured_card'
                    }

                    if person_is_atl:
                        result.atl_contacts.append(person)
                        logger.info(f"    👤 ATL (card): {name} - {title}")
                    elif person_is_btl or title:
                        result.btl_contacts.append(person)

                except Exception:
                    continue

        # METHOD 2: Text-based extraction for small business websites
        # Look for patterns like "Founded by John Smith", "Owner: Jane Doe"
        content = await page.inner_text('body')

        # ATL text patterns - common on small HVAC company websites
        atl_patterns = [
            # "Founded by John Smith" / "Founded in 1985 by John Smith"
            r'[Ff]ounded\s+(?:in\s+\d{4}\s+)?by\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
            # "Owner: John Smith" / "Owner - Jane Doe"
            r'[Oo]wner[:\s-]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
            # "President: John Smith"
            r'[Pp]resident[:\s-]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
            # "CEO: John Smith"
            r'CEO[:\s-]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)',
            # "John Smith, Owner"
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),\s*(?:[Oo]wner|[Ff]ounder|[Pp]resident|CEO)',
            # "Meet John Smith, our founder"
            r'[Mm]eet\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),?\s*(?:our\s+)?(?:[Oo]wner|[Ff]ounder|[Pp]resident)',
            # "John Smith is the owner"
            r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s+is\s+the\s+(?:[Oo]wner|[Ff]ounder|[Pp]resident|CEO)',
        ]

        existing_names = {p['name'].lower() for p in result.atl_contacts + result.btl_contacts}

        for pattern in atl_patterns:
            matches = re.findall(pattern, content)
            for match in matches:
                name = match.strip()
                # Validate it looks like a person name (2-4 words, capitalized)
                if not name or len(name) < 5 or len(name) > 40:
                    continue
                words = name.split()
                if len(words) < 2 or len(words) > 4:
                    continue
                if not all(w[0].isupper() for w in words if len(w) > 1):
                    continue

                if name.lower() in existing_names:
                    continue

                # Determine title from the pattern
                title = "Owner/Founder"  # Default for text-based extraction
                if 'president' in pattern.lower():
                    title = "President"
                elif 'ceo' in pattern.lower():
                    title = "CEO"

                person = {
                    'name': name,
                    'title': title,
                    'email': '',
                    'source': page_url,
                    'extraction_method': 'text_pattern'
                }

                result.atl_contacts.append(person)
                existing_names.add(name.lower())
                logger.info(f"    👤 ATL (text): {name} - {title}")

    except Exception as e:
        logger.debug(f"People extraction error: {e}")


async def extract_address_from_page(page, result: DeepScrapeResult):
    """Extract company address from contact page."""
    try:
        content = await page.content()

        # State abbreviations
        states = r'(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)'

        # Address patterns
        # Format: 123 Main St, City, ST 12345
        pattern = rf'(\d+[^,\n]+),?\s*([A-Za-z\s]+),?\s*{states}\s*(\d{{5}}(?:-\d{{4}})?)'
        match = re.search(pattern, content)

        if match and not result.address:
            result.address = match.group(1).strip()
            result.city = match.group(2).strip()
            result.state = match.group(3)
            result.zip_code = match.group(4)
            logger.info(f"    📍 Address: {result.city}, {result.state} {result.zip_code}")

    except Exception as e:
        logger.debug(f"Address extraction error: {e}")


async def scrape_website_pages(page, result: DeepScrapeResult, base_url: str):
    """Scrape multiple pages on the company website."""

    # Pages to scrape (in order of priority for ATL/BTL)
    pages_to_try = [
        ('/', 'Landing Page'),
        ('/team', 'Team'),
        ('/our-team', 'Our Team'),
        ('/about/team', 'About Team'),
        ('/leadership', 'Leadership'),
        ('/management', 'Management'),
        ('/about-us', 'About Us'),
        ('/about', 'About'),
        ('/company', 'Company'),
        ('/contact', 'Contact'),
        ('/contact-us', 'Contact Us'),
    ]

    for path, page_name in pages_to_try:
        try:
            full_url = urljoin(base_url, path)

            response = await page.goto(full_url, wait_until="domcontentloaded", timeout=15000)

            if not response or response.status >= 400:
                continue

            result.pages_scraped.append(full_url)
            await asyncio.sleep(1)  # Let page render

            # Extract data from page
            await extract_phones_from_page(page, result, full_url)
            await extract_emails_from_page(page, result, full_url)

            # Team/About pages - extract people
            if any(x in path for x in ['team', 'about', 'leadership', 'management', 'company']):
                await extract_people_from_page(page, result, full_url)

            # Contact page - extract address
            if 'contact' in path:
                await extract_address_from_page(page, result)

            # Landing page - also extract people (founder/owner mentions)
            if path == '/':
                await extract_people_from_page(page, result, full_url)

            # Detect trades and ICP signals from ALL pages (services often mentioned on about/services pages)
            try:
                page_text = await page.inner_text('body')
                trades = detect_trades(page_text)
                for trade in trades:
                    if trade not in result.trades_detected:
                        result.trades_detected.append(trade)
                # Update counts after each page (accumulative)
                result.trade_count = len(result.trades_detected)
                result.is_multi_trade = result.trade_count >= 2
                # Check for family-owned (only need to find once)
                if not result.family_owned:
                    result.family_owned = detect_family_owned(page_text)
                # Check years in business (take the best value)
                years = detect_years_in_business(page_text)
                if years > result.years_in_business:
                    result.years_in_business = years
            except Exception:
                pass

        except Exception as e:
            result.scrape_errors.append(f"{page_name}: {str(e)[:50]}")
            continue

    # Log multi-trade summary after all pages scraped
    if result.is_multi_trade:
        logger.info(f"    🔧 MULTI-TRADE: {', '.join(result.trades_detected)} ({result.trade_count} trades)")
    if result.family_owned:
        logger.info(f"    👨‍👩‍👧 Family-owned business detected")
    if result.years_in_business > 0:
        logger.info(f"    📅 {result.years_in_business} years in business")


async def scrape_linkedin(page, result: DeepScrapeResult, company_name: str):
    """Scrape LinkedIn company page."""
    try:
        # Search Google for LinkedIn company page
        search_query = f"site:linkedin.com/company {company_name}"
        google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

        await page.goto(google_url, wait_until="domcontentloaded", timeout=20000)
        await asyncio.sleep(2)

        # Find LinkedIn URL
        linkedin_url = None
        links = await page.query_selector_all('a[href*="linkedin.com/company"]')

        for link in links[:5]:
            href = await link.get_attribute('href')
            if href and 'linkedin.com/company/' in href:
                match = re.search(r'(https?://[^/]*linkedin\.com/company/[a-zA-Z0-9_-]+)', href)
                if match:
                    linkedin_url = match.group(1)
                    break

        if not linkedin_url:
            return

        result.linkedin_url = linkedin_url
        result.linkedin_found = True
        logger.info(f"    🔗 LinkedIn: {linkedin_url}")

        # Navigate to LinkedIn
        await asyncio.sleep(3)  # Rate limit

        try:
            await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)

            # Extract employee count
            content = await page.content()
            emp_match = re.search(r'([\d,]+(?:-[\d,]+)?)\s*employees?', content, re.IGNORECASE)
            if emp_match:
                result.linkedin_employee_count = emp_match.group(1)
                count_str = result.linkedin_employee_count.split('-')[-1].replace(',', '')
                result.linkedin_employee_count_numeric = int(count_str) if count_str.isdigit() else 0
                logger.info(f"    👥 LinkedIn employees: {result.linkedin_employee_count}")

            # Try to access /people/ page
            await asyncio.sleep(2)
            people_url = f"{linkedin_url}/people/"
            await page.goto(people_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(2)

            # Extract visible employees
            cards = await page.query_selector_all('[class*="org-people-profile-card"], [class*="profile-card"]')
            for card in cards[:20]:
                try:
                    name_elem = await card.query_selector('span[class*="title"], h3, a[href*="/in/"]')
                    name = await name_elem.inner_text() if name_elem else None

                    title_elem = await card.query_selector('span[class*="subtitle"], p')
                    title = await title_elem.inner_text() if title_elem else ""

                    if name and name.strip():
                        name = name.strip()
                        title = title.strip()[:100] if title else ""

                        existing_names = {p['name'].lower() for p in result.atl_contacts + result.btl_contacts}
                        if name.lower() in existing_names:
                            continue

                        person = {
                            'name': name,
                            'title': title,
                            'source': 'linkedin',
                            'email': ''
                        }

                        if is_atl(title):
                            result.atl_contacts.append(person)
                            logger.info(f"    👤 LinkedIn ATL: {name} - {title}")
                        elif is_btl(title):
                            result.btl_contacts.append(person)

                except Exception:
                    continue

        except Exception as e:
            result.scrape_errors.append(f"LinkedIn nav: {str(e)[:50]}")

    except Exception as e:
        result.scrape_errors.append(f"LinkedIn search: {str(e)[:50]}")


async def deep_scrape_company(
    company_name: str,
    domain: str,
    semaphore: asyncio.Semaphore,
    existing_phones: List[str] = None  # For audit trail
) -> DeepScrapeResult:
    """
    Perform comprehensive deep scrape of one company.

    Args:
        company_name: Company name
        domain: Website domain
        semaphore: Concurrency limiter
        existing_phones: List of normalized phone numbers already known (for audit trail)
    """
    from playwright.async_api import async_playwright

    start_time = datetime.now()

    result = DeepScrapeResult(
        company_name=company_name,
        domain=domain,
        scrape_timestamp=start_time.isoformat(),
        existing_phones=existing_phones or []
    )

    async with semaphore:
        session_id = None
        try:
            # Create Browserbase session
            session_id, connect_url = await create_browserbase_session()

            async with async_playwright() as p:
                browser = await p.chromium.connect_over_cdp(connect_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()

                # Build base URL
                base_url = f"https://{domain}" if not domain.startswith('http') else domain

                logger.info(f"[{company_name}] Starting deep scrape...")

                # Step 1: Scrape company website (multiple pages)
                try:
                    await scrape_website_pages(page, result, base_url)
                    result.website_reachable = len(result.pages_scraped) > 0
                except Exception as e:
                    result.scrape_errors.append(f"Website: {str(e)[:50]}")

                # Step 2: Scrape LinkedIn
                try:
                    await scrape_linkedin(page, result, company_name)
                except Exception as e:
                    result.scrape_errors.append(f"LinkedIn: {str(e)[:50]}")

                await browser.close()

        except Exception as e:
            result.scrape_errors.append(f"Session: {str(e)[:100]}")
            logger.error(f"[{company_name}] Session error: {e}")

        finally:
            if session_id:
                await close_browserbase_session(session_id)

        # Calculate stats
        result.atl_count = len(result.atl_contacts)
        result.btl_count = len(result.btl_contacts)
        result.phone_count = len(result.phones)
        result.email_count = len(result.emails)
        result.scrape_duration_seconds = (datetime.now() - start_time).total_seconds()

        logger.info(f"[{company_name}] ✅ Done: {result.atl_count} ATL, {result.btl_count} BTL, {result.phone_count} phones, {result.email_count} emails ({result.scrape_duration_seconds:.1f}s)")

        return result


async def run_deep_scrape(
    df: pd.DataFrame,
    max_concurrent: int = 10,
    progress_callback=None,
    save_every: int = 25,
    output_file: Path = None
) -> List[DeepScrapeResult]:
    """Run deep scraping on all companies with phone audit trail and incremental saves."""
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    last_save_count = 0

    total = len(df)
    logger.info(f"Deep scraping {total} companies (max {max_concurrent} concurrent)")
    logger.info(f"Incremental save every {save_every} companies to {output_file}")

    # Process in batches
    batch_size = max_concurrent * 2

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_df = df.iloc[batch_start:batch_end]

        tasks = []
        for _, row in batch_df.iterrows():
            company_name = row.get('company_name', '')
            domain = row.get('domain', '')

            # Extract existing phones from input data for audit trail
            existing_phones = []
            if 'primary_phone' in row and pd.notna(row['primary_phone']):
                existing_phones.append(normalize_phone(str(row['primary_phone'])))
            # Check for all_phones_json column
            if 'all_phones_json' in row and pd.notna(row['all_phones_json']):
                try:
                    phones_data = json.loads(row['all_phones_json'])
                    for p in phones_data:
                        if 'normalized' in p:
                            existing_phones.append(p['normalized'])
                        elif 'phone' in p:
                            existing_phones.append(normalize_phone(p['phone']))
                except:
                    pass
            # Filter out empty
            existing_phones = [p for p in existing_phones if p]

            if domain:
                # Wrap each scrape in a timeout to prevent hanging
                async def scrape_with_timeout(name, dom, sem, phones):
                    try:
                        return await asyncio.wait_for(
                            deep_scrape_company(name, dom, sem, phones),
                            timeout=120  # 2 minute timeout per company
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"[{name}] ⏰ TIMEOUT after 120s")
                        return DeepScrapeResult(
                            company_name=name,
                            domain=dom,
                            scrape_errors=['TIMEOUT: Scrape took >120s']
                        )

                tasks.append(scrape_with_timeout(company_name, domain, semaphore, existing_phones))

        batch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Task exception: {result}")
            else:
                results.append(result)

        # Progress
        pct = (batch_end / total) * 100
        logger.info(f"Progress: {batch_end}/{total} ({pct:.1f}%)")

        # Incremental save every N companies
        if output_file and len(results) >= last_save_count + save_every:
            save_deep_scrape_results(results, output_file)
            # Sync to Supabase on each save
            new_results = results[last_save_count:]  # Only sync new results
            sync_results_to_supabase(new_results)
            logger.info(f"💾 INCREMENTAL SAVE: {len(results)} companies saved to {output_file.name}")
            last_save_count = len(results)

        # Rate limit between batches
        if batch_end < total:
            await asyncio.sleep(5)

    return results


def save_deep_scrape_results(results: List[DeepScrapeResult], output_file: Path):
    """Save deep scrape results to CSV, JSON, and Close CRM export."""
    records = []
    close_crm_records = []  # For Close CRM import

    for r in results:
        # Calculate audit stats
        r.new_phone_count = len(r.new_phones)
        r.verified_phone_count = len(r.verified_phones)

        record = {
            'company_name': r.company_name,
            'domain': r.domain,
            'website_reachable': r.website_reachable,
            'pages_scraped_count': len(r.pages_scraped),
            'atl_count': r.atl_count,
            'btl_count': r.btl_count,
            'phone_count': r.phone_count,
            'email_count': r.email_count,
            # Phone audit trail
            'new_phone_count': r.new_phone_count,
            'verified_phone_count': r.verified_phone_count,
            'new_phones': ', '.join([p['number'] for p in r.new_phones]),
            'verified_phones': ', '.join([p['number'] for p in r.verified_phones]),
            # LinkedIn
            'linkedin_found': r.linkedin_found,
            'linkedin_url': r.linkedin_url,
            'linkedin_employee_count': r.linkedin_employee_count,
            'linkedin_employee_count_numeric': r.linkedin_employee_count_numeric,
            # Address
            'address': r.address,
            'city': r.city,
            'state': r.state,
            'zip_code': r.zip_code,
            # Meta
            'scrape_duration_seconds': r.scrape_duration_seconds,
            'scrape_errors': '; '.join(r.scrape_errors),
            # Multi-trade ICP signals
            'trades_detected': ', '.join(r.trades_detected),
            'is_multi_trade': r.is_multi_trade,
            'trade_count': r.trade_count,
            'family_owned': r.family_owned,
            'years_in_business': r.years_in_business,
            # JSON data
            'atl_contacts_json': json.dumps(r.atl_contacts),
            'btl_contacts_json': json.dumps(r.btl_contacts),
            'phones_json': json.dumps(r.phones),
            'emails_json': json.dumps(r.emails),
        }

        # Flatten ATL contacts
        for i, atl in enumerate(r.atl_contacts[:5], 1):
            record[f'atl_{i}_name'] = atl.get('name', '')
            record[f'atl_{i}_title'] = atl.get('title', '')
            record[f'atl_{i}_email'] = atl.get('email', '')
            record[f'atl_{i}_method'] = atl.get('extraction_method', '')

        # First phone and email
        if r.phones:
            record['primary_phone'] = r.phones[0]['number']
        if r.emails:
            record['primary_email'] = r.emails[0]['email']

        records.append(record)

        # === CLOSE CRM EXPORT ===
        # Create one row per ATL contact found (for importing as leads with contacts)
        if r.atl_contacts:
            for atl in r.atl_contacts:
                close_record = {
                    # Lead fields
                    'Company': r.company_name,
                    'Company Domain': r.domain,
                    'Company Phone': r.phones[0]['number'] if r.phones else '',
                    'Company Address': r.address,
                    'Company City': r.city,
                    'Company State': r.state,
                    'Company Zip': r.zip_code,
                    # Contact fields
                    'Contact Name': atl.get('name', ''),
                    'Contact Title': atl.get('title', ''),
                    'Contact Email': atl.get('email', ''),
                    # Custom fields for Tim
                    'Lead Source': 'Deep Scrape (Browserbase)',
                    'LinkedIn URL': r.linkedin_url,
                    'LinkedIn Employees': r.linkedin_employee_count,
                    'ATL Count': r.atl_count,
                    'Extraction Method': atl.get('extraction_method', ''),
                    'Phone Audit': f"{r.new_phone_count} new, {r.verified_phone_count} verified",
                    # Multi-trade ICP signals
                    'Trades Detected': ', '.join(r.trades_detected),
                    'Is Multi-Trade': 'Yes' if r.is_multi_trade else 'No',
                    'Trade Count': r.trade_count,
                    'Family Owned': 'Yes' if r.family_owned else 'No',
                    'Years in Business': r.years_in_business if r.years_in_business > 0 else '',
                }
                close_crm_records.append(close_record)
        else:
            # Company with no ATL - still include for reference
            close_record = {
                'Company': r.company_name,
                'Company Domain': r.domain,
                'Company Phone': r.phones[0]['number'] if r.phones else '',
                'Company Address': r.address,
                'Company City': r.city,
                'Company State': r.state,
                'Company Zip': r.zip_code,
                'Contact Name': '',
                'Contact Title': '',
                'Contact Email': r.emails[0]['email'] if r.emails else '',
                'Lead Source': 'Deep Scrape (Browserbase)',
                'LinkedIn URL': r.linkedin_url,
                'LinkedIn Employees': r.linkedin_employee_count,
                'ATL Count': 0,
                'Extraction Method': '',
                'Phone Audit': f"{r.new_phone_count} new, {r.verified_phone_count} verified",
                # Multi-trade ICP signals
                'Trades Detected': ', '.join(r.trades_detected),
                'Is Multi-Trade': 'Yes' if r.is_multi_trade else 'No',
                'Trade Count': r.trade_count,
                'Family Owned': 'Yes' if r.family_owned else 'No',
                'Years in Business': r.years_in_business if r.years_in_business > 0 else '',
            }
            close_crm_records.append(close_record)

    # Ensure output directory exists
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Save main results
    df = pd.DataFrame(records)
    df.to_csv(output_file, index=False)
    logger.info(f"Saved: {output_file}")

    # JSON backup
    json_file = output_file.with_suffix('.json')
    with open(json_file, 'w') as f:
        json.dump([asdict(r) for r in results], f, indent=2, default=str)
    logger.info(f"Saved: {json_file}")

    # === CLOSE CRM EXPORT (ready for Tim to review and import) ===
    close_file = output_file.parent / f"CLOSE_CRM_IMPORT_{output_file.stem.replace('DEEP_SCRAPE_', '')}.csv"
    close_df = pd.DataFrame(close_crm_records)
    close_df.to_csv(close_file, index=False)
    logger.info(f"Saved Close CRM export: {close_file}")
    logger.info(f"  → {len([r for r in close_crm_records if r['Contact Name']])} leads with ATL contacts")
    logger.info(f"  → {len([r for r in close_crm_records if not r['Contact Name']])} leads without ATL (company only)")

    # === FAILED COMPANIES EXPORT (for re-running with longer timeouts) ===
    # A company is considered "failed" if:
    # 1. It has scrape_errors, OR
    # 2. Website was not reachable AND no data was extracted (ATL=0, phones=0, emails=0)
    failed_records = []
    for r in results:
        has_errors = bool(r.scrape_errors)
        no_data = (r.atl_count == 0 and r.btl_count == 0 and
                   r.phone_count == 0 and r.email_count == 0 and
                   not r.linkedin_found)
        website_issue = not r.website_reachable

        if has_errors or (website_issue and no_data):
            failed_records.append({
                'company_name': r.company_name,
                'domain': r.domain,
                'website_reachable': r.website_reachable,
                'scrape_errors': '; '.join(r.scrape_errors),
                'scrape_duration_seconds': r.scrape_duration_seconds,
                'failure_reason': 'scrape_error' if has_errors else 'unreachable_no_data',
                # Include any partial data we did get
                'atl_count': r.atl_count,
                'phone_count': r.phone_count,
                'email_count': r.email_count,
                'linkedin_found': r.linkedin_found,
            })

    if failed_records:
        failed_file = output_file.parent / f"FAILED_TO_SCRAPE_{output_file.stem.replace('DEEP_SCRAPE_', '')}.csv"
        failed_df = pd.DataFrame(failed_records)
        failed_df.to_csv(failed_file, index=False)
        logger.info(f"⚠️ Saved {len(failed_records)} failed companies for re-run: {failed_file}")
        logger.info(f"  → Re-run with: python deep_scrape_companies.py --input {failed_file} --concurrent 5 --rate 10")
    else:
        logger.info("✅ No failed companies - all scraped successfully!")


def sync_results_to_supabase(results: List[DeepScrapeResult]):
    """Sync deep scrape results to Supabase dim_companies and dim_contacts."""
    supabase = get_supabase()
    if not supabase:
        logger.warning("Supabase not configured - skipping sync")
        return

    # Normalize company name for matching
    def normalize_name(name):
        if not name:
            return None
        n = str(name).lower().strip()
        n = re.sub(r'[^\w\s-]', ' ', n)
        suffixes = [r'\s+inc\.?\s*$', r'\s+llc\.?\s*$', r'\s+corp\.?\s*$',
                    r'\s+co\.?\s*$', r'\s+ltd\.?\s*$']
        for s in suffixes:
            n = re.sub(s, '', n, flags=re.IGNORECASE)
        return re.sub(r'\s+', ' ', n).strip()

    # Get existing companies by normalized_name for matching
    try:
        existing = supabase.table('dim_companies').select('company_id, normalized_name, linkedin_url').execute()
        name_to_id = {r['normalized_name']: r['company_id'] for r in existing.data if r['normalized_name']}
    except Exception as e:
        logger.error(f"Failed to fetch existing companies: {e}")
        return

    companies_updated = 0
    contacts_added = 0

    for r in results:
        norm_name = normalize_name(r.company_name)
        company_id = name_to_id.get(norm_name)

        if not company_id:
            continue  # Company not in our universe

        # Build update data (only non-empty fields)
        update_data = {}
        if r.linkedin_url:
            update_data['linkedin_url'] = r.linkedin_url
        if r.linkedin_employee_count_numeric and r.linkedin_employee_count_numeric > 0:
            update_data['employee_count'] = r.linkedin_employee_count_numeric
        if r.address:
            update_data['address'] = r.address
        if r.city:
            update_data['city'] = r.city
        if r.state:
            update_data['state'] = r.state
        if r.zip_code:
            update_data['zip_code'] = r.zip_code
        if r.is_multi_trade:
            update_data['is_multi_trade'] = True
            update_data['trades_detected'] = ', '.join(r.trades_detected)
        if r.family_owned:
            update_data['family_owned'] = True
        if r.years_in_business > 0:
            update_data['years_in_business'] = r.years_in_business
        # Update last_enriched_at
        update_data['last_enriched_at'] = datetime.now().isoformat()
        update_data['enrichment_source'] = 'browserbase_deep_scrape'

        if update_data:
            try:
                supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
                companies_updated += 1
            except Exception as e:
                logger.error(f"Failed to update {r.company_name}: {e}")

        # Add ATL contacts to dim_contacts
        for atl in r.atl_contacts:
            if not atl.get('name'):
                continue
            contact_data = {
                'company_id': company_id,
                'name': atl['name'],
                'title': atl.get('title', ''),
                'email': atl.get('email'),
                'is_atl': True,
                'source': 'browserbase_deep_scrape',
                'extraction_method': atl.get('extraction_method', ''),
                'discovered_at': datetime.now().isoformat()
            }
            try:
                # Upsert by company_id + name
                existing_contact = supabase.table('dim_contacts').select('contact_id').eq('company_id', company_id).eq('name', atl['name']).execute()
                if existing_contact.data:
                    supabase.table('dim_contacts').update(contact_data).eq('contact_id', existing_contact.data[0]['contact_id']).execute()
                else:
                    supabase.table('dim_contacts').insert(contact_data).execute()
                    contacts_added += 1
            except Exception as e:
                logger.error(f"Failed to add contact {atl['name']}: {e}")

    logger.info(f"☁️ SUPABASE SYNC: {companies_updated} companies updated, {contacts_added} contacts added")


def find_latest_input() -> Path:
    """Find the most recent enriched/filtered leads file."""
    patterns = [
        'ENRICHED_1000_ICP_COMPLETE_*.csv',
        'TOP_500_FOR_HUNTER_*.csv',
        'TOP_1000_UNIQUE_ICP_*.csv'
    ]
    for pattern in patterns:
        files = list(INPUT_DIR.glob(pattern))
        if files:
            return max(files, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError("No input file found")


async def main():
    global _rate_limiter

    parser = argparse.ArgumentParser(description='Deep company scraper using Browserbase')
    parser.add_argument('--test', type=int, help='Test with N companies')
    parser.add_argument('--top', type=int, help='Process top N companies')
    parser.add_argument('--all', action='store_true', help='Process all companies')
    parser.add_argument('--input', type=str, help='Specific input file')
    parser.add_argument('--concurrent', type=int, default=10, help='Max concurrent scrapes')
    parser.add_argument('--rate', type=int, default=SESSIONS_PER_MINUTE, help='Sessions per minute (rate limit)')
    parser.add_argument('--skip', type=int, default=0, help='Skip first N companies (for resuming)')
    parser.add_argument('--save-every', type=int, default=25, help='Save progress every N companies')

    args = parser.parse_args()

    if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
        logger.error("BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID must be set!")
        return

    # Initialize rate limiter to prevent 429 errors
    _rate_limiter = RateLimiter(args.rate)

    # Find input file
    if args.input:
        input_file = Path(args.input)
    else:
        input_file = find_latest_input()

    logger.info(f"{'='*60}")
    logger.info(f"DEEP COMPANY SCRAPER (Browserbase)")
    logger.info(f"{'='*60}")
    logger.info(f"Input: {input_file}")
    logger.info(f"Max concurrent: {args.concurrent}")
    logger.info(f"Rate limit: {args.rate} sessions/min (~{60.0/args.rate:.1f}s between session starts)")
    logger.info(f"Log: {log_file}")

    # Load data
    df = pd.read_csv(input_file)
    logger.info(f"Loaded {len(df)} companies")

    # Apply filters
    if args.test:
        df = df.head(args.test)
        logger.info(f"TEST MODE: {args.test} companies")
    elif args.top:
        df = df.head(args.top)
        logger.info(f"TOP {args.top} companies")

    # Apply skip for resuming
    if args.skip > 0:
        df = df.iloc[args.skip:]
        logger.info(f"RESUMING: Skipping first {args.skip} companies")

    # Output file for incremental saves
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = OUTPUT_DIR / f"DEEP_SCRAPE_incremental_{timestamp}.csv"

    # Run deep scrape with incremental saves
    results = await run_deep_scrape(
        df,
        max_concurrent=args.concurrent,
        save_every=args.save_every,
        output_file=output_file
    )

    if not results:
        logger.info("No companies scraped")
        return

    # Final save (full results)
    final_output = OUTPUT_DIR / f"DEEP_SCRAPE_{len(results)}_{datetime.now().strftime('%Y%m%d')}.csv"
    save_deep_scrape_results(results, final_output)

    # Final sync to Supabase (any remaining that weren't incrementally synced)
    sync_results_to_supabase(results)

    # Summary
    website_ok = sum(1 for r in results if r.website_reachable)
    linkedin_ok = sum(1 for r in results if r.linkedin_found)
    with_atl = sum(1 for r in results if r.atl_count > 0)
    total_atl = sum(r.atl_count for r in results)
    total_btl = sum(r.btl_count for r in results)
    total_phones = sum(r.phone_count for r in results)
    total_emails = sum(r.email_count for r in results)

    logger.info(f"\n{'='*60}")
    logger.info(f"DEEP SCRAPE COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Companies scraped: {len(results)}")
    logger.info(f"Website reachable: {website_ok} ({website_ok/len(results)*100:.1f}%)")
    logger.info(f"LinkedIn found: {linkedin_ok} ({linkedin_ok/len(results)*100:.1f}%)")
    logger.info(f"With ATL contacts: {with_atl} ({with_atl/len(results)*100:.1f}%)")
    logger.info(f"Total ATL: {total_atl}")
    logger.info(f"Total BTL: {total_btl}")
    logger.info(f"Total phones: {total_phones}")
    logger.info(f"Total emails: {total_emails}")

    # Show sample ATL
    if total_atl > 0:
        logger.info(f"\nSAMPLE ATL CONTACTS:")
        for r in results[:20]:
            if r.atl_contacts:
                for atl in r.atl_contacts[:2]:
                    logger.info(f"  • {atl['name']} ({atl['title']}) @ {r.company_name}")


if __name__ == '__main__':
    asyncio.run(main())
