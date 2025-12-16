"""
WebsiteScraper - Browserbase-powered contractor website enrichment.

Extracted from run_enrichment.py for use in Celery tasks.

Features:
- Persistent session pool (2-3 warm Browserbase sessions)
- Exponential backoff retry (3 attempts)
- Sequential scraping (one domain at a time)
- 3-layer garbage contact filtering
- ATL/BTL contact extraction
- OEM brand detection
- Service area extraction
"""

import asyncio
import logging
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv
from playwright.async_api import Browser, Page, async_playwright

logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURATION
# ============================================================================

# Load environment variables from root .env with override=True
# This ensures Celery workers get fresh values, not stale cached ones
_project_root = Path(__file__).parent.parent.parent.parent.parent  # backend/../
_env_file = _project_root / ".env"
if _env_file.exists():
    load_dotenv(_env_file, override=True)
    logger.debug(f"[WebsiteScraper] Loaded env from {_env_file}")

BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

# Load contact blocklist
BLOCKLIST_FILE = Path(__file__).parent.parent.parent.parent / "data" / "contact_blocklist.txt"

# Team page paths to check (prioritized)
TEAM_PAGE_PATHS = [
    "/about", "/about-us", "/about/staff", "/about/team", "/about/our-team",
    "/team", "/our-team", "/meet-the-team", "/staff", "/our-staff",
    "/leadership", "/management", "/meet-our-team", "/people", "/who-we-are",
    "/company", "/company/team", "/company/about",
    "/commercial", "/commercial-projects", "/commercial-services",
    "/our-work", "/projects", "/portfolio",
]

SERVICE_AREA_PATHS = [
    "/service-area", "/service-areas", "/areas-served", "/areas-we-serve",
    "/locations", "/coverage", "/cities-served", "/cities-we-serve",
    "/where-we-serve", "/communities", "/neighborhoods",
]

# ATL titles (decision makers)
ATL_TITLES = [
    "owner", "co-owner", "founder", "co-founder", "president", "ceo", "chief executive",
    "chairman", "cfo", "coo", "cto", "executive", "general manager", "gm", "director",
    "vp", "vice president", "partner", "principal", "managing", "operations manager",
    "head of", "division head", "department head", "branch manager", "regional manager",
]

# BTL titles (technicians, staff)
BTL_TITLES = [
    "office manager", "technician", "tech", "installer", "installation", "service",
    "hvac tech", "plumber", "electrician", "apprentice", "helper", "assistant",
    "dispatcher", "coordinator", "scheduler", "admin", "administrator",
    "permits", "compliance", "sales", "estimator", "supervisor", "foreman",
    "lead", "senior", "junior", "specialist", "representative", "rep",
    "project manager", "field operations", "operations", "commander",
    "crew", "team member", "office", "bookkeeper", "accounting",
    "warehouse", "inventory", "logistics", "fleet", "driver",
]

ALL_TITLES = ATL_TITLES + BTL_TITLES

# OEM Brands (100+ brands across HVAC, Solar, Battery, EV)
OEM_BRANDS = [
    # HVAC Premium
    "Carrier", "Trane", "Lennox", "Bryant", "Rheem", "Ruud", "Goodman", "Daikin",
    "American Standard", "York", "Amana", "Mitsubishi", "Fujitsu", "LG", "Samsung",
    "Bosch", "Honeywell", "Nest", "Ecobee", "Aprilaire", "Coleman", "Heil",
    # Generators
    "Generac", "Kohler", "Cummins", "Briggs & Stratton", "Champion",
    # Water Heaters
    "Navien", "Rinnai", "Noritz", "Takagi", "Bradford White", "A.O. Smith",
    # Solar Inverters
    "Enphase", "SolarEdge", "SMA", "Fronius", "Tesla", "SunPower",
    "Sungrow", "Huawei", "GoodWe", "Growatt", "Delta", "Schneider Electric",
    # Solar Panels
    "Q Cells", "Canadian Solar", "JinkoSolar", "Trina Solar", "Silfab",
    "Mission Solar", "Hanwha", "LONGi", "JA Solar", "Panasonic Solar", "REC Solar",
    # Batteries
    "Tesla Powerwall", "Enphase IQ Battery", "LG Chem", "Sonnen", "Generac PWRcell",
    "Franklin WholePower", "Panasonic EverVolt", "BYD", "Tesla Megapack",
    # EV Chargers
    "ChargePoint", "JuiceBox", "Wallbox", "Emporia", "Grizzl-E",
    "Tesla Wall Connector", "ClipperCreek", "ABB Terra", "Tritium",
    # VRF/Commercial
    "Daikin VRV", "Mitsubishi City Multi", "LG Multi V", "Samsung DVM",
]

# Garbage contact filtering
DEFINITELY_GARBAGE_NAMES = {
    "log in", "login", "sign up", "signup", "sign in", "check continue",
    "apply now", "get started", "read more", "learn more", "click here",
    "view all", "see all", "show more", "load more", "submit",
    "membership careers", "create account", "my account", "forgot password",
    "los angeles", "new york", "san francisco", "san diego", "san jose",
    "las vegas", "santa monica", "santa ana", "long beach", "fort worth",
    "salt lake", "palm springs", "palm beach", "newport beach",
    "service area", "areas served", "cities served", "we serve",
    "preventative maintenance", "preventive maintenance", "routine maintenance",
    "customer service", "technical support", "emergency service",
    "free estimate", "free quote", "contact us", "about us",
}

CITY_NAME_PREFIXES = {"los", "las", "san", "santa", "new", "fort", "palm", "salt", "long", "newport"}

GARBAGE_NAME_WORDS = {
    "as", "a", "an", "the", "to", "of", "in", "on", "at", "by", "for", "with",
    "and", "or", "but", "so", "co", "is", "it", "we", "us", "our", "be", "has",
    "have", "been", "was", "are", "were", "will", "can", "may", "must", "shall",
    "click", "here", "read", "more", "view", "see", "learn", "call", "contact",
    "schedule", "book", "get", "your", "my", "his", "her", "their", "this", "that",
    "maintenance", "preventative", "preventive", "customer", "service", "support",
    "financing", "commercial", "residential", "emergency", "repair", "installation",
}


class WebsiteScraper:
    """
    Browserbase-powered website scraper for contractor enrichment.

    Usage:
        scraper = WebsiteScraper(pool_size=2)
        await scraper.initialize()
        try:
            result = await scraper.scrape_domain("example-hvac.com")
        finally:
            await scraper.close()
    """

    def __init__(self, pool_size: int = 2, max_retries: int = 3):
        """
        Initialize scraper.

        Args:
            pool_size: Number of Browserbase sessions to keep warm
            max_retries: Max retry attempts with exponential backoff
        """
        self.pool_size = pool_size
        self.max_retries = max_retries
        self._sessions: List[Tuple[str, str]] = []  # (session_id, connect_url)
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._contact_blocklist: set = set()
        self._load_blocklist()

    def _load_blocklist(self):
        """Load contact blocklist patterns from file."""
        if BLOCKLIST_FILE.exists():
            with open(BLOCKLIST_FILE, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        self._contact_blocklist.add(line.lower())
            logger.info(f"Loaded {len(self._contact_blocklist)} blocklist patterns")

    # ========================================================================
    # SESSION MANAGEMENT
    # ========================================================================

    async def initialize(self) -> None:
        """Initialize Playwright and create session pool."""
        if not BROWSERBASE_API_KEY:
            raise ValueError("BROWSERBASE_API_KEY not found in environment")

        self._playwright = await async_playwright().start()

        # Create initial session pool
        for _ in range(self.pool_size):
            session = await self._create_session()
            if session:
                self._sessions.append(session)

        logger.info(f"WebsiteScraper initialized with {len(self._sessions)} sessions")

    async def close(self) -> None:
        """Close all sessions and cleanup."""
        for session_id, _ in self._sessions:
            await self._close_session(session_id)
        self._sessions.clear()

        if self._browser:
            await self._browser.close()
            self._browser = None

        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

        logger.info("WebsiteScraper closed")

    async def _create_session(self) -> Optional[Tuple[str, str]]:
        """Create a new Browserbase session."""
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    "https://api.browserbase.com/v1/sessions",
                    headers={
                        "x-bb-api-key": BROWSERBASE_API_KEY,
                        "Content-Type": "application/json",
                    },
                    json={"projectId": BROWSERBASE_PROJECT_ID},
                )
                response.raise_for_status()
                data = response.json()
                return (data["id"], data.get("connectUrl"))
        except Exception as e:
            logger.error(f"Failed to create Browserbase session: {e}")
            return None

    async def _close_session(self, session_id: str) -> None:
        """Close a Browserbase session."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    f"https://api.browserbase.com/v1/sessions/{session_id}/stop",
                    headers={"x-bb-api-key": BROWSERBASE_API_KEY},
                )
        except Exception:
            pass  # Ignore cleanup errors

    async def _get_session(self) -> Tuple[str, str]:
        """Get a session from pool, creating one if needed."""
        if not self._sessions:
            session = await self._create_session()
            if not session:
                raise RuntimeError("Failed to create Browserbase session")
            return session
        return self._sessions[0]  # Use first session (simple strategy)

    # ========================================================================
    # CORE SCRAPING
    # ========================================================================

    async def scrape_domain(self, domain: str) -> Dict[str, Any]:
        """
        Scrape a contractor website and extract enrichment data.

        Args:
            domain: Domain to scrape (e.g., "example-hvac.com")

        Returns:
            Dict with success status, contacts, brands, service areas, etc.
        """
        result = {
            "success": False,
            "domain": domain,
            "contacts": [],
            "oem_brands": [],
            "service_areas": [],
            "has_maintenance_plan": False,
            "maintenance_plans": [],
            "company_story": None,
            "pages_scraped": [],
            "scrape_time_ms": 0,
            "retry_count": 0,
            "error": None,
        }

        start_time = time.time()

        # Retry with exponential backoff
        for attempt in range(self.max_retries):
            try:
                result = await self._scrape_with_session(domain, result)
                if result["success"]:
                    break
            except Exception as e:
                result["retry_count"] = attempt + 1
                result["error"] = str(e)[:200]
                if attempt < self.max_retries - 1:
                    wait_time = (2 ** attempt) * 1  # 1s, 2s, 4s
                    logger.warning(f"Retry {attempt + 1} for {domain} after {wait_time}s: {e}")
                    await asyncio.sleep(wait_time)

        result["scrape_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    async def _scrape_with_session(self, domain: str, result: Dict) -> Dict:
        """Execute scrape using a Browserbase session."""
        session_id, connect_url = await self._get_session()

        try:
            browser = await self._playwright.chromium.connect_over_cdp(connect_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()

            base_url = f"https://{domain}"
            all_content = ""

            # Scrape landing page
            try:
                response = await page.goto(base_url, wait_until="domcontentloaded", timeout=30000)
                if response and response.status < 400:
                    result["pages_scraped"].append("/")
                    content = await page.inner_text("body")
                    all_content += content + "\n"
            except Exception as e:
                if "timeout" in str(e).lower():
                    result["error"] = "Landing page timeout"
                else:
                    result["error"] = str(e)[:100]
                return result

            # Scrape secondary pages (team, about, service areas)
            pages_to_check = [f"{base_url}{path}" for path in TEAM_PAGE_PATHS[:8]]
            pages_to_check += [f"{base_url}{path}" for path in SERVICE_AREA_PATHS[:4]]

            for page_url in pages_to_check:
                try:
                    response = await page.goto(page_url, wait_until="domcontentloaded", timeout=15000)
                    if response and response.status < 400:
                        path = page_url.replace(base_url, "") or "/"
                        result["pages_scraped"].append(path)
                        content = await page.inner_text("body")
                        all_content += content + "\n"
                except Exception:
                    continue  # Skip failed pages

            # Extract all data from combined content
            result["contacts"] = self.extract_contacts(all_content)
            result["oem_brands"] = self.extract_brands(all_content)
            result["service_areas"] = self.extract_service_areas(all_content)
            result["maintenance_plans"] = self.extract_maintenance_plans(all_content)
            result["has_maintenance_plan"] = len(result["maintenance_plans"]) > 0

            # Mark success if we got any useful data
            result["success"] = (
                len(result["contacts"]) > 0
                or len(result["oem_brands"]) > 0
                or len(result["service_areas"]) > 0
            )

            await browser.close()
            return result

        except Exception as e:
            logger.error(f"Scrape error for {domain}: {e}")
            result["error"] = str(e)[:200]
            return result

    # ========================================================================
    # DATA EXTRACTION (Static Methods)
    # ========================================================================

    @staticmethod
    def extract_phones(content: str) -> List[str]:
        """Extract phone numbers from content."""
        patterns = [r"\(\d{3}\)\s*\d{3}[-.\s]\d{4}", r"\d{3}[-.\s]\d{3}[-.\s]\d{4}"]
        phones = set()
        for pattern in patterns:
            for match in re.findall(pattern, content):
                digits = re.sub(r"\D", "", match)
                if len(digits) == 10 and digits[:3] not in ["000", "111", "555", "800", "888"]:
                    phones.add(match.strip())
        return list(phones)

    @staticmethod
    def decode_cloudflare_email(encoded: str) -> Optional[str]:
        """
        Decode Cloudflare-protected email addresses.

        Cloudflare encodes emails using XOR with a key (first 2 hex chars).
        Example: data-cfemail="cda4a3aba28d..." -> info@domain.com
        """
        if not encoded or len(encoded) < 4:
            return None
        try:
            key = int(encoded[:2], 16)
            decoded = ''.join([
                chr(int(encoded[i:i+2], 16) ^ key)
                for i in range(2, len(encoded), 2)
            ])
            if '@' in decoded and '.' in decoded:
                return decoded.lower()
            return None
        except (ValueError, IndexError):
            return None

    @staticmethod
    def extract_emails(content: str) -> List[str]:
        """Extract email addresses from content, including Cloudflare-protected ones."""
        emails = set()

        # Method 1: Standard email pattern
        pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        for email in re.findall(pattern, content):
            if not any(x in email.lower() for x in ["example.com", "domain.com", "noreply"]):
                emails.add(email.lower())

        # Method 2: Cloudflare-encoded emails (data-cfemail="xxx")
        cf_pattern = r'data-cfemail=["\']([a-fA-F0-9]+)["\']'
        for cf_encoded in re.findall(cf_pattern, content):
            decoded = WebsiteScraper.decode_cloudflare_email(cf_encoded)
            if decoded and not any(x in decoded for x in ["example.com", "domain.com", "noreply"]):
                emails.add(decoded)
                logger.debug(f"Decoded Cloudflare email: {decoded}")

        return list(emails)

    def extract_contacts(self, content: str) -> List[Dict]:
        """Extract ATL and BTL contacts from content."""
        contacts = []
        seen = set()

        # Method 1: Text patterns like "Founded by X", "Owner: X"
        text_patterns = [
            (r"[Ff]ounded\s+(?:in\s+\d{4}\s+)?by\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)", "Founder"),
            (r"[Oo]wner[:\s-]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)", "Owner"),
            (r"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),\s*(?:[Oo]wner|[Ff]ounder|CEO|President)", "Owner/Founder"),
        ]

        for pattern, title in text_patterns:
            for match in re.findall(pattern, content):
                name = match.strip()
                if name and 5 <= len(name) <= 40 and name.lower() not in seen:
                    if not self.is_garbage_contact(name, title):
                        contacts.append({"name": name, "title": title, "is_atl": True})
                        seen.add(name.lower())

        # Method 2: "Name - Title" patterns
        for title_keyword in ALL_TITLES:
            is_atl = title_keyword in ATL_TITLES
            pattern = rf"([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s*[-–,/]\s*{title_keyword}"
            for match in re.findall(pattern, content, re.IGNORECASE):
                name = match.strip()
                if name and name.lower() not in seen and not self.is_garbage_contact(name, title_keyword):
                    contacts.append({"name": name, "title": title_keyword.title(), "is_atl": is_atl})
                    seen.add(name.lower())

        return contacts

    def is_garbage_contact(self, name: str, title: str = "") -> bool:
        """Check if contact name matches garbage patterns (3-layer defense)."""
        name_lower = (name or "").strip().lower()
        title_lower = (title or "").strip().lower()

        # Layer 1: Exact match
        if name_lower in DEFINITELY_GARBAGE_NAMES:
            return True

        # Layer 2: Blocklist patterns
        for pattern in self._contact_blocklist:
            if pattern in name_lower or pattern in title_lower:
                return True

        # Layer 3: Structural checks
        words = name_lower.split()
        if len(words) >= 2 and words[0] in CITY_NAME_PREFIXES:
            return True
        if len(name_lower) < 5:
            return True
        if len(words) < 2:
            return True
        if any(c.isdigit() for c in name_lower):
            return True
        for word in words:
            if word in GARBAGE_NAME_WORDS:
                return True

        return False

    @staticmethod
    def extract_brands(content: str) -> List[str]:
        """Extract OEM brands mentioned in content."""
        content_lower = content.lower()
        found = []
        for brand in OEM_BRANDS:
            if brand.lower() in content_lower:
                found.append(brand)
        return found

    @staticmethod
    def extract_service_areas(content: str) -> List[str]:
        """Extract service areas/cities from content."""
        areas = set()
        lines = content.split("\n")
        in_service_section = False

        skip_words = {
            "home", "about", "contact", "services", "team", "blog",
            "heating", "cooling", "hvac", "air", "conditioning", "repair",
            "service", "areas", "we", "serve", "our", "the", "and", "or",
            "facebook", "instagram", "twitter", "linkedin", "youtube",
        }

        for line in lines:
            line_lower = line.strip().lower()

            if any(phrase in line_lower for phrase in ["service area", "areas served", "cities served"]):
                in_service_section = True
                continue

            if in_service_section:
                if line_lower.startswith(("about", "contact", "services")):
                    in_service_section = False
                    continue

                line_clean = line.strip()
                if 3 < len(line_clean) < 40 and line_clean[0].isupper():
                    words = line_clean.lower().split()
                    if not any(w in skip_words for w in words):
                        areas.add(line_clean)

        return sorted(list(areas))[:20]

    @staticmethod
    def extract_maintenance_plans(content: str) -> List[str]:
        """Extract maintenance plan names (BDR gold for openers)."""
        plans = []
        content_lower = content.lower()

        plan_keywords = [
            "comfort club", "service club", "priority club", "vip club",
            "maintenance plan", "maintenance agreement", "service agreement",
            "service plan", "protection plan", "home protection",
            "membership", "priority member", "preferred customer",
        ]

        for keyword in plan_keywords:
            if keyword in content_lower:
                plans.append(keyword.title())

        return list(set(plans))[:5]


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = ["WebsiteScraper"]
