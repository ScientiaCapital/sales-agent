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
    "/jobs",       # Jobs - alternate careers page
    "/contact",    # Contact - location info
    "/team",       # Team - leadership
    "/customers",  # Customers - social proof
    "/case-studies",
    "/service-areas",      # Service areas/locations
    "/service-area",       # NEW: Singular variant
    "/reviews",            # NEW: Customer reviews/testimonials (social proof)
    "/testimonials",       # NEW: Testimonials variant
    "/awards",             # NEW: Awards/recognition (social proof)
    "/residential",        # NEW: Residential services
    "/commercial",         # Commercial services
    "/commercial-hvac",    # Commercial HVAC (common variant)
    "/industrial",         # NEW: Industrial services (HIGH VALUE)
    "/generators",         # Generator offerings
    "/home-generators",    # Home generators (common variant)
    "/standby-generators", # Standby generators (common variant)
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

MAINTENANCE_PLAN_SIGNALS = [
    r"preventive\s+maintenance",
    r"preventative\s+maintenance",
    r"maintenance\s+(plan|agreement|contract|program)",
    r"service\s+(plan|agreement|contract)",
    r"annual\s+maintenance",
    r"planned\s+maintenance",
    r"(pm|ppm)\s+program",  # Preventive Maintenance Program
]

GENERATOR_SIGNALS = [
    r"generator\s+(sales|installation|service|repair)",
    r"standby\s+generator",
    r"backup\s+generator",
    r"home\s+generator",
    r"commercial\s+generator",
    r"whole[\s-]house\s+generator",
    r"generac|kohler|cummins",  # Major generator brands
]

COMMERCIAL_SIGNALS = [
    r"commercial\s+(hvac|plumbing|electrical)",
    r"commercial\s+services",
    r"business\s+services",
    r"multi[\s-]family",
    r"property\s+management",
]

# NEW: Industrial signals (HIGH VALUE - factories, plants, manufacturing)
INDUSTRIAL_SIGNALS = [
    r"industrial\s+(hvac|plumbing|electrical|services)",
    r"manufacturing\s+(plants|facilities)",
    r"factory\s+electrical",
    r"plant\s+maintenance",
    r"industrial\s+controls",
    r"process\s+control",
]

# NEW: Membership/MVP program signals (recurring revenue)
MEMBERSHIP_SIGNALS = [
    r"mvp\s+(program|plan|membership)",
    r"membership\s+(program|plan)",
    r"club\s+member",
    r"vip\s+(program|member)",
    r"service\s+club",
    r"protection\s+plan",
    r"priority\s+(service|member)",
]

# NEW: Specials/promotions signals (active marketing)
SPECIALS_SIGNALS = [
    r"special\s+(offer|deal|pricing)",
    r"promotion",
    r"discount",
    r"coupon",
    r"\$\d+\s+off",           # "$50 off"
    r"\d+%\s+off",            # "10% Off", "20% off"
    r"limited\s+time",
    r"save\s+(\$|up\s+to)",
    r"first\s+(service|call)\s+(call|discount)",  # "10% Off Your First Service Call"
]

# NEW: Financing signals (mature company indicator)
FINANCING_SIGNALS = [
    r"financing\s+(available|options)",
    r"payment\s+plans",
    r"0%\s+(apr|financing)",
    r"easy\s+financing",
    r"flexible\s+financing",
]

# NEW: OEM Partnership signals (certified installer = HIGH ICP)
OEM_PARTNERSHIP_SIGNALS = [
    r"carrier|trane|lennox|rheem|ruud|york|american\s+standard|goodman",  # HVAC OEMs
    r"bradford\s+white|a\.?o\.?\s+smith|navien|rinnai|bosch",  # Water heater OEMs
    r"weil[\s-]mclain|burnham|slant[\s-]fin|peerless",  # Boiler OEMs
    r"generac|kohler|cummins|briggs",  # Generator OEMs
    r"authorized\s+(dealer|installer|service\s+provider)",
    r"certified\s+(dealer|installer|technician)",
    r"factory[\s-]authorized",
    r"premier\s+dealer",
]

# NEW: Emergency Service signals (mature operations)
EMERGENCY_SERVICE_SIGNALS = [
    r"24[\s/]7|twenty[\s-]four[\s-]seven",
    r"emergency\s+(service|repair)",
    r"same[\s-]day\s+service",
    r"available\s+24\s+hours",
]

# NEW: Design-Build signals (HIGH VALUE - integrated design + construction)
DESIGN_BUILD_SIGNALS = [
    r"design[\s-]build",
    r"design[\s/]build",
    r"design\s+and\s+build",
    r"turnkey\s+solutions?",
    r"single[\s-]source\s+solution",
]

# NEW: Engineering capabilities (HIGH VALUE - in-house technical expertise)
ENGINEERING_SIGNALS = [
    r"cad\s+department",
    r"engineering\s+department",
    r"in[\s-]house\s+engineer(s|ing)",
    r"licensed\s+engineer(s)?",
    r"professional\s+engineer(s)?",
    r"pe\s+certified",
    r"project\s+engineer(s)?",
]

# NEW: Medical/Healthcare specialization (HIGH VALUE - regulated/complex work)
MEDICAL_SIGNALS = [
    r"medical\s+gas(\s+piping)?",
    r"healthcare\s+(facilities|projects)",
    r"hospital\s+(projects|hvac|plumbing)",
    r"clean\s+room",
    r"laboratory\s+(hvac|systems)",
    r"surgical\s+suite",
]

# NEW: Building Automation/Controls (HIGH VALUE - smart buildings)
AUTOMATION_SIGNALS = [
    r"building\s+automation",
    r"(bms|bas)\s+system",  # Building Management/Automation System
    r"building\s+controls?",
    r"(hvac|system)\s+controls?",
    r"energy\s+management\s+system",
    r"smart\s+building",
    r"(scada|ddc)\s+system",  # Supervisory Control / Direct Digital Control
]

# NEW: Awards/Recognition (social proof/credibility)
AWARDS_SIGNALS = [
    r"award[\s-]winning",
    r"best\s+of\s+(the\s+)?year",
    r"industry\s+awards?",
    r"excellence\s+award",
    r"top\s+(contractor|company|employer)",
    r"angi\s+(super|elite)\s+service",
    r"carrier\s+president'?s?\s+award",
]

# NEW: Detailed MEP capability detection
MEP_CAPABILITIES = {
    "plumbing": r"plumbing|plumber",
    "drains": r"drain|clog|line\s+cleaning",
    "sewer": r"sewer|septic|waste\s+water",  # NEW: Separate from drains
    "hvac": r"hvac|heating|cooling|air\s+conditioning|furnace",
    "electrical": r"electric|electrician",
    "water_quality": r"water\s+(quality|filtration|softener|purification)",
    "water_heater": r"water\s+heater|tankless",
    "attic": r"attic|insulation",
    "indoor_air_quality": r"indoor\s+air\s+quality|iaq|air\s+purification",
}

# NEW: Service area patterns for multi-location detection
LOCATION_PATTERNS = [
    r"(\d+)\s+(locations?|offices?|branches?)",
    r"serving\s+(\d+)\s+(cities|areas|counties)",
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
                "has_maintenance_plan": False,
                "has_generators": False,
                "has_commercial": False,
                "has_industrial": False,        # NEW: Industrial clients (HIGH VALUE)
                "has_membership": False,        # NEW: MVP/membership program
                "has_specials": False,          # NEW: Active promotions
                "has_financing": False,         # NEW: Offers financing (mature company)
                "has_oem_partnerships": False,  # NEW: Carrier, Generac, etc. (certified installer)
                "has_emergency_service": False, # NEW: 24/7 service (mature operations)
                "has_design_build": False,      # NEW: Design-build capability (HIGH VALUE)
                "has_engineering": False,       # NEW: In-house engineering/CAD (HIGH VALUE)
                "has_medical_specialization": False,  # NEW: Medical gas/healthcare (HIGH VALUE)
                "has_building_automation": False,     # NEW: Building automation/controls (HIGH VALUE)
                "has_awards": False,            # NEW: Awards/recognition (social proof)
                "growth_indicators": [],
            },
            "mep_capabilities": {},  # NEW: Detailed MEP breakdown
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

                        # Don't detect hiring from text - will check page existence after loop

                        if self._detect_funding(text):
                            result["signals"]["has_funding"] = True

                        # NEW: Detect maintenance plans
                        if self._detect_maintenance_plans(text):
                            result["signals"]["has_maintenance_plan"] = True

                        # NEW: Detect generators
                        if self._detect_generators(text):
                            result["signals"]["has_generators"] = True

                        # NEW: Detect commercial capability
                        if self._detect_commercial(text):
                            result["signals"]["has_commercial"] = True

                        # NEW: Detect industrial capability (HIGH VALUE)
                        if self._detect_industrial(text):
                            result["signals"]["has_industrial"] = True

                        # NEW: Detect membership/MVP program
                        if self._detect_membership_program(text):
                            result["signals"]["has_membership"] = True

                        # NEW: Detect specials/promotions
                        if self._detect_specials(text):
                            result["signals"]["has_specials"] = True

                        # NEW: Detect financing options
                        if self._detect_financing(text):
                            result["signals"]["has_financing"] = True

                        # NEW: Detect OEM partnerships (Carrier, Generac, etc.)
                        if self._detect_oem_partnerships(text):
                            result["signals"]["has_oem_partnerships"] = True

                        # NEW: Detect emergency service (24/7)
                        if self._detect_emergency_service(text):
                            result["signals"]["has_emergency_service"] = True

                        # NEW: Detect design-build capability (HIGH VALUE)
                        if self._detect_design_build(text):
                            result["signals"]["has_design_build"] = True

                        # NEW: Detect in-house engineering (HIGH VALUE)
                        if self._detect_engineering(text):
                            result["signals"]["has_engineering"] = True

                        # NEW: Detect medical/healthcare specialization (HIGH VALUE)
                        if self._detect_medical_specialization(text):
                            result["signals"]["has_medical_specialization"] = True

                        # NEW: Detect building automation/controls (HIGH VALUE)
                        if self._detect_building_automation(text):
                            result["signals"]["has_building_automation"] = True

                        # NEW: Detect awards/recognition
                        if self._detect_awards(text):
                            result["signals"]["has_awards"] = True

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

            # FIXED: Detect hiring by checking if careers/jobs page exists (not text keywords)
            result["signals"]["is_hiring"] = self._detect_hiring(result["pages_scraped"])

            # NEW: Detect detailed MEP capabilities from all scraped text
            result["mep_capabilities"] = self._detect_mep_capabilities(result["all_text"])

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

    def _detect_hiring(self, pages_scraped: list) -> bool:
        """
        Detect if company is hiring.

        FIXED: Only returns TRUE if /careers or /jobs page was successfully scraped.
        This prevents false positives from homepage text like "we're hiring!"
        """
        for page in pages_scraped:
            if page["path"] in ["/careers", "/jobs"]:
                return True  # Careers/Jobs page exists and loaded
        return False  # No careers page found

    def _detect_maintenance_plans(self, text: str) -> bool:
        """Detect if company offers maintenance plans/agreements."""
        text_lower = text.lower()
        for pattern in MAINTENANCE_PLAN_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_generators(self, text: str) -> bool:
        """Detect if company sells/installs generators."""
        text_lower = text.lower()
        for pattern in GENERATOR_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_commercial(self, text: str) -> bool:
        """Detect if company serves commercial clients."""
        text_lower = text.lower()
        for pattern in COMMERCIAL_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_industrial(self, text: str) -> bool:
        """Detect if company serves industrial clients (HIGH VALUE)."""
        text_lower = text.lower()
        for pattern in INDUSTRIAL_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_membership_program(self, text: str) -> bool:
        """Detect if company offers membership/MVP program (recurring revenue)."""
        text_lower = text.lower()
        for pattern in MEMBERSHIP_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_specials(self, text: str) -> bool:
        """Detect if company has active specials/promotions."""
        text_lower = text.lower()
        for pattern in SPECIALS_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_financing(self, text: str) -> bool:
        """Detect if company offers financing (mature company signal)."""
        text_lower = text.lower()
        # Simple keyword check is enough for financing
        if "financing" in text_lower:
            return True
        for pattern in FINANCING_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_oem_partnerships(self, text: str) -> bool:
        """Detect if company has OEM partnerships/certifications (HIGH ICP signal)."""
        text_lower = text.lower()
        for pattern in OEM_PARTNERSHIP_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_emergency_service(self, text: str) -> bool:
        """Detect if company offers 24/7 emergency service (mature operations)."""
        text_lower = text.lower()
        for pattern in EMERGENCY_SERVICE_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_design_build(self, text: str) -> bool:
        """Detect design-build capability (HIGH VALUE - integrated design + construction)."""
        text_lower = text.lower()
        for pattern in DESIGN_BUILD_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_engineering(self, text: str) -> bool:
        """Detect in-house engineering capability (HIGH VALUE - technical expertise)."""
        text_lower = text.lower()
        for pattern in ENGINEERING_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_medical_specialization(self, text: str) -> bool:
        """Detect medical/healthcare specialization (HIGH VALUE - regulated/complex work)."""
        text_lower = text.lower()
        for pattern in MEDICAL_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_building_automation(self, text: str) -> bool:
        """Detect building automation/controls (HIGH VALUE - smart buildings)."""
        text_lower = text.lower()
        for pattern in AUTOMATION_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_awards(self, text: str) -> bool:
        """Detect awards/recognition (social proof/credibility)."""
        text_lower = text.lower()
        for pattern in AWARDS_SIGNALS:
            if re.search(pattern, text_lower):
                return True
        return False

    def _detect_mep_capabilities(self, text: str) -> dict:
        """
        Detect detailed MEP capabilities.

        Returns dict like:
        {
            "plumbing": True,
            "drains": True,
            "hvac": True,
            "electrical": True,
            "water_quality": False,
            ...
        }
        """
        text_lower = text.lower()
        capabilities = {}

        for capability, pattern in MEP_CAPABILITIES.items():
            capabilities[capability] = bool(re.search(pattern, text_lower))

        return capabilities

    def _count_mep_capabilities(self, capabilities: dict) -> int:
        """Count how many MEP capabilities company offers."""
        return sum(1 for v in capabilities.values() if v)

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
