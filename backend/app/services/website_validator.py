"""
Website Validator Service

Validates company websites and extracts key information:
- HTTP status check (ICP qualifier)
- Team/About Us pages discovery
- Contact information extraction
- ATL (Above The Line) contact discovery
- Company phone number extraction

Used as early ICP filter in pipeline.
"""
import httpx
import time
import re
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


@dataclass
class WebsiteValidationResult:
    """Result of website validation check"""
    is_valid: bool  # True if website is reachable
    status_code: Optional[int]  # HTTP status code
    response_time_ms: int  # Latency to reach website

    # Website content
    has_team_page: bool
    has_about_page: bool
    has_contact_page: bool

    # Extracted data
    team_page_url: Optional[str]
    about_page_url: Optional[str]
    contact_page_url: Optional[str]

    # ATL contacts found on team page
    atl_contacts: List[Dict[str, str]]  # [{name, title, email?}]

    # Company phone (extracted from website)
    company_phone: Optional[str] = None
    phone_source: Optional[str] = None  # "tel_link", "contact_page", "footer", "header"

    # Error details
    error_message: Optional[str] = None


class WebsiteValidator:
    """
    Validates company websites and extracts team/contact information.

    ICP Qualifier: If website is not reachable, lead is not ICP.
    """

    # HTTP timeout settings
    TIMEOUT_SECONDS = 10
    MAX_REDIRECTS = 5

    # Common team/about page paths
    TEAM_PAGE_PATHS = [
        "/team", "/about/team", "/our-team", "/leadership",
        "/about-us/team", "/company/team", "/people"
    ]

    ABOUT_PAGE_PATHS = [
        "/about", "/about-us", "/company", "/about-company",
        "/who-we-are", "/our-story"
    ]

    CONTACT_PAGE_PATHS = [
        "/contact", "/contact-us", "/get-in-touch", "/reach-us"
    ]

    # ATL titles to look for
    ATL_TITLES = [
        "ceo", "chief executive",
        "cto", "chief technology",
        "cmo", "chief marketing",
        "vp sales", "vice president sales",
        "vp marketing", "vice president marketing",
        "director sales", "director marketing",
        "president", "founder", "co-founder"
    ]

    # US phone regex patterns (captures various formats)
    PHONE_PATTERN = re.compile(
        r'''
        (?:
            \+?1[-.\s]?                    # Optional country code
        )?
        \(?([2-9]\d{2})\)?                 # Area code (can't start with 0 or 1)
        [-.\s]?
        ([2-9]\d{2})                       # Exchange (can't start with 0 or 1)
        [-.\s]?
        (\d{4})                            # Subscriber number
        ''',
        re.VERBOSE
    )

    def __init__(self):
        """Initialize website validator with HTTP client"""
        self.client = httpx.AsyncClient(
            timeout=self.TIMEOUT_SECONDS,
            follow_redirects=True,
            max_redirects=self.MAX_REDIRECTS,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; SalesAgentBot/1.0; +http://example.com/bot)"
            }
        )

    async def validate(self, website_url: str) -> WebsiteValidationResult:
        """
        Validate company website and extract information.

        Args:
            website_url: Company website URL (e.g., "https://example.com")

        Returns:
            WebsiteValidationResult with validation status and extracted data
        """
        start_time = time.time()

        # Normalize URL
        if not website_url.startswith(("http://", "https://")):
            website_url = f"https://{website_url}"

        try:
            # Check if website is reachable
            response = await self.client.get(website_url)
            response_time_ms = int((time.time() - start_time) * 1000)

            if response.status_code != 200:
                logger.warning(f"Website returned status {response.status_code}: {website_url}")
                return WebsiteValidationResult(
                    is_valid=False,
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                    has_team_page=False,
                    has_about_page=False,
                    has_contact_page=False,
                    team_page_url=None,
                    about_page_url=None,
                    contact_page_url=None,
                    atl_contacts=[],
                    error_message=f"HTTP {response.status_code}"
                )

            # Parse homepage HTML
            soup = BeautifulSoup(response.text, 'html.parser')

            # Discover key pages
            team_url = await self._find_page(website_url, soup, self.TEAM_PAGE_PATHS)
            about_url = await self._find_page(website_url, soup, self.ABOUT_PAGE_PATHS)
            contact_url = await self._find_page(website_url, soup, self.CONTACT_PAGE_PATHS)

            # Extract ATL contacts from team page
            atl_contacts = []
            if team_url:
                atl_contacts = await self._extract_atl_contacts(team_url)

            # Extract company phone from homepage
            company_phone, phone_source = self._extract_phone_from_soup(soup)

            # If no phone on homepage, try contact page
            if not company_phone and contact_url:
                try:
                    contact_response = await self.client.get(contact_url)
                    if contact_response.status_code == 200:
                        contact_soup = BeautifulSoup(contact_response.text, 'html.parser')
                        company_phone, phone_source = self._extract_phone_from_soup(contact_soup)
                        if phone_source:
                            phone_source = "contact_page"
                except Exception as e:
                    logger.debug(f"Failed to fetch contact page for phone: {e}")

            logger.info(
                f"Website validated: {website_url} "
                f"(status={response.status_code}, "
                f"team={bool(team_url)}, "
                f"atl_contacts={len(atl_contacts)}, "
                f"phone={company_phone})"
            )

            return WebsiteValidationResult(
                is_valid=True,
                status_code=response.status_code,
                response_time_ms=response_time_ms,
                has_team_page=bool(team_url),
                has_about_page=bool(about_url),
                has_contact_page=bool(contact_url),
                team_page_url=team_url,
                about_page_url=about_url,
                contact_page_url=contact_url,
                atl_contacts=atl_contacts,
                company_phone=company_phone,
                phone_source=phone_source
            )

        except httpx.TimeoutException:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Website timeout after {response_time_ms}ms: {website_url}")
            return WebsiteValidationResult(
                is_valid=False,
                status_code=None,
                response_time_ms=response_time_ms,
                has_team_page=False,
                has_about_page=False,
                has_contact_page=False,
                team_page_url=None,
                about_page_url=None,
                contact_page_url=None,
                atl_contacts=[],
                error_message=f"Timeout after {response_time_ms}ms"
            )

        except Exception as e:
            response_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Website validation failed: {website_url} - {e}")
            return WebsiteValidationResult(
                is_valid=False,
                status_code=None,
                response_time_ms=response_time_ms,
                has_team_page=False,
                has_about_page=False,
                has_contact_page=False,
                team_page_url=None,
                about_page_url=None,
                contact_page_url=None,
                atl_contacts=[],
                error_message=str(e)
            )

    def _normalize_phone(self, phone: str) -> Optional[str]:
        """
        Normalize a phone number to standard format (XXX) XXX-XXXX.

        Returns None if invalid.
        """
        # Remove all non-digit characters
        digits = re.sub(r'\D', '', phone)

        # Handle country code
        if len(digits) == 11 and digits[0] == '1':
            digits = digits[1:]

        # Must be exactly 10 digits
        if len(digits) != 10:
            return None

        # Format as (XXX) XXX-XXXX
        return f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"

    def _extract_phone_from_soup(self, soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract company phone number from parsed HTML.

        Priority:
        1. tel: links (highest confidence - explicitly marked as phone)
        2. Contact page content
        3. Footer
        4. Header area

        Returns:
            Tuple of (phone_number, source) or (None, None)
        """
        phones_found = []

        # Strategy 1: Look for tel: links (highest confidence)
        tel_links = soup.find_all('a', href=re.compile(r'^tel:', re.IGNORECASE))
        for link in tel_links:
            href = link.get('href', '')
            # Extract number from tel:+1-555-123-4567 or tel:5551234567
            phone_digits = re.sub(r'\D', '', href)
            normalized = self._normalize_phone(phone_digits)
            if normalized:
                phones_found.append((normalized, "tel_link"))
                logger.debug(f"Found tel: link phone: {normalized}")

        # Strategy 2: Look in footer (common location for company phone)
        footer = soup.find('footer') or soup.find(class_=re.compile(r'footer', re.IGNORECASE))
        if footer:
            footer_text = footer.get_text()
            for match in self.PHONE_PATTERN.finditer(footer_text):
                phone = f"{match.group(1)}{match.group(2)}{match.group(3)}"
                normalized = self._normalize_phone(phone)
                if normalized:
                    phones_found.append((normalized, "footer"))
                    logger.debug(f"Found footer phone: {normalized}")

        # Strategy 3: Look in header/nav area
        header = soup.find('header') or soup.find(class_=re.compile(r'header|nav', re.IGNORECASE))
        if header:
            header_text = header.get_text()
            for match in self.PHONE_PATTERN.finditer(header_text):
                phone = f"{match.group(1)}{match.group(2)}{match.group(3)}"
                normalized = self._normalize_phone(phone)
                if normalized:
                    phones_found.append((normalized, "header"))
                    logger.debug(f"Found header phone: {normalized}")

        # Strategy 4: Look for "Call" or "Phone" nearby text
        call_patterns = soup.find_all(string=re.compile(r'call\s*us|phone|contact\s*us', re.IGNORECASE))
        for pattern in call_patterns[:3]:  # Limit to first 3
            parent = pattern.find_parent()
            if parent:
                parent_text = parent.get_text()
                for match in self.PHONE_PATTERN.finditer(parent_text):
                    phone = f"{match.group(1)}{match.group(2)}{match.group(3)}"
                    normalized = self._normalize_phone(phone)
                    if normalized:
                        phones_found.append((normalized, "call_text"))
                        logger.debug(f"Found call text phone: {normalized}")

        # Deduplicate by phone number, prioritize by source
        priority = {"tel_link": 0, "header": 1, "footer": 2, "call_text": 3}
        if phones_found:
            # Sort by priority (tel_link first)
            phones_found.sort(key=lambda x: priority.get(x[1], 99))
            return phones_found[0]

        return None, None

    async def _find_page(
        self,
        base_url: str,
        homepage_soup: BeautifulSoup,
        possible_paths: List[str]
    ) -> Optional[str]:
        """
        Find a specific page type (team/about/contact) from homepage links.

        Args:
            base_url: Website base URL
            homepage_soup: Parsed homepage HTML
            possible_paths: List of possible page paths to check

        Returns:
            Full URL to the page if found, None otherwise
        """
        # Look for links in navigation
        for link in homepage_soup.find_all('a', href=True):
            href = link['href'].lower()

            # Check if link matches any of the possible paths
            for path in possible_paths:
                if path in href:
                    # Construct full URL
                    if href.startswith('http'):
                        return href
                    elif href.startswith('/'):
                        return f"{base_url.rstrip('/')}{href}"
                    else:
                        return f"{base_url.rstrip('/')}/{href}"

        return None

    async def _extract_atl_contacts(self, team_page_url: str) -> List[Dict[str, str]]:
        """
        Extract Above The Line (ATL) contacts from team page.

        Args:
            team_page_url: URL to team page

        Returns:
            List of ATL contacts with name, title, email (if found)
        """
        try:
            response = await self.client.get(team_page_url)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            atl_contacts = []

            # Look for team member cards/sections
            # Common patterns: <div class="team-member">, <div class="person">, etc.
            team_sections = soup.find_all(['div', 'article', 'section'], class_=lambda x: x and any(
                keyword in str(x).lower() for keyword in ['team', 'member', 'person', 'employee', 'leadership']
            ))

            for section in team_sections:
                # Extract name (usually in h2, h3, or strong tag)
                name_tag = section.find(['h2', 'h3', 'h4', 'strong', 'span'], class_=lambda x: x and 'name' in str(x).lower())
                if not name_tag:
                    name_tag = section.find(['h2', 'h3', 'h4'])

                # Extract title/role
                title_tag = section.find(['p', 'span', 'div'], class_=lambda x: x and any(
                    keyword in str(x).lower() for keyword in ['title', 'role', 'position', 'job']
                ))

                if name_tag and title_tag:
                    name = name_tag.get_text(strip=True)
                    title = title_tag.get_text(strip=True).lower()

                    # Check if title matches ATL criteria
                    if any(atl_title in title for atl_title in self.ATL_TITLES):
                        # Look for email
                        email_tag = section.find('a', href=lambda x: x and x.startswith('mailto:'))
                        email = email_tag['href'].replace('mailto:', '') if email_tag else None

                        atl_contacts.append({
                            "name": name,
                            "title": title_tag.get_text(strip=True),  # Original case
                            "email": email
                        })

            logger.info(f"Extracted {len(atl_contacts)} ATL contacts from {team_page_url}")
            return atl_contacts

        except Exception as e:
            logger.error(f"Failed to extract ATL contacts from {team_page_url}: {e}")
            return []

    async def close(self):
        """Close HTTP client"""
        await self.client.aclose()


# Singleton instance
_validator_instance: Optional[WebsiteValidator] = None


async def get_website_validator() -> WebsiteValidator:
    """Get or create website validator singleton"""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = WebsiteValidator()
    return _validator_instance
