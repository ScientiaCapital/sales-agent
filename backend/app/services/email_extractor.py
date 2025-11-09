"""Email extraction from company websites."""
import re
import httpx
from typing import List, Set
from bs4 import BeautifulSoup
import logging

logger = logging.getLogger(__name__)


class EmailExtractor:
    """Extract and validate emails from company websites."""

    # Email regex patterns (from simplest to most complex)
    PATTERNS = [
        # Standard format
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}',
        # With whitespace
        r'[a-zA-Z0-9._%+-]+\s*@\s*[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}',
        # Obfuscated: name (at) domain
        r'[a-zA-Z0-9._%+-]+\s*\(at\)\s*[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}',
        # Obfuscated: name [at] domain
        r'[a-zA-Z0-9._%+-]+\s*\[at\]\s*[a-zA-Z0-9.-]+\.[A-Z|a-z]{2,}',
    ]

    # Common contact page URL patterns
    CONTACT_PAGES = [
        '/contact', '/contact-us', '/about', '/team',
        '/leadership', '/get-in-touch', '/reach-us', '/company'
    ]

    # Generic emails to filter out
    GENERIC_FILTERS = [
        'info@', 'admin@', 'webmaster@', 'noreply@',
        'no-reply@', 'support@', 'help@', 'contact@'
    ]

    def __init__(self, timeout: int = 10):
        """
        Initialize EmailExtractor.

        Args:
            timeout: HTTP request timeout in seconds
        """
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def extract_emails(
        self,
        website: str,
        max_pages: int = 3
    ) -> List[str]:
        """
        Extract emails from website.

        Args:
            website: Company website URL
            max_pages: Maximum pages to crawl

        Returns:
            List of emails, prioritized (decision-makers first)
        """
        emails: Set[str] = set()

        # Try main page
        main_emails = await self._extract_from_page(website)
        emails.update(main_emails)

        # Try contact pages
        for pattern in self.CONTACT_PAGES[:max_pages]:
            contact_url = f"{website.rstrip('/')}{pattern}"
            page_emails = await self._extract_from_page(contact_url)
            emails.update(page_emails)

        # Filter and prioritize
        filtered = self._filter_generic(list(emails))
        prioritized = self._prioritize_emails(filtered, website)

        logger.info(f"Extracted {len(prioritized)} emails from {website}")
        return prioritized

    async def _extract_from_page(self, url: str) -> Set[str]:
        """
        Extract emails from single page.

        Args:
            url: Page URL to scrape

        Returns:
            Set of found emails
        """
        try:
            response = await self.client.get(url, follow_redirects=True)
            if response.status_code != 200:
                return set()

            html = response.text
            return await self._extract_from_html(html, url)

        except Exception as e:
            logger.warning(f"Failed to extract from {url}: {e}")
            return set()

    async def _extract_from_html(self, html: str, url: str) -> Set[str]:
        """
        Extract emails from HTML content.

        Args:
            html: HTML content
            url: Source URL (for logging)

        Returns:
            Set of found emails
        """
        emails: Set[str] = set()

        # Apply all regex patterns
        for pattern in self.PATTERNS:
            matches = re.findall(pattern, html, re.IGNORECASE)
            # Clean obfuscated emails
            cleaned = [
                m.replace(' (at) ', '@')
                 .replace(' [at] ', '@')
                 .replace('(at)', '@')
                 .replace('[at]', '@')
                 .replace(' @ ', '@')
                 .strip()
                for m in matches
            ]
            emails.update(cleaned)

        # Also check mailto: links
        soup = BeautifulSoup(html, 'html.parser')
        for link in soup.find_all('a', href=re.compile(r'^mailto:')):
            email = link['href'].replace('mailto:', '').strip()
            # Remove query params (?subject=, etc)
            email = email.split('?')[0]
            emails.add(email)

        logger.debug(f"Found {len(emails)} raw emails from {url}")
        return emails

    def _filter_generic(self, emails: List[str]) -> List[str]:
        """
        Remove generic emails (info@, admin@, etc.).

        Args:
            emails: List of emails to filter

        Returns:
            Filtered list
        """
        return [
            email for email in emails
            if not any(email.lower().startswith(prefix) for prefix in self.GENERIC_FILTERS)
        ]

    def _prioritize_emails(self, emails: List[str], website: str) -> List[str]:
        """
        Prioritize emails by likelihood of decision-maker.

        Priority order:
        1. Personal names (john.smith@, jane.doe@)
        2. Sales/business related (sales@, business@)
        3. Other valid emails

        Args:
            emails: List of emails to prioritize
            website: Company website

        Returns:
            Prioritized list
        """
        personal = []
        business = []
        other = []

        for email in emails:
            local_part = email.split('@')[0].lower()

            # Personal name patterns (firstname.lastname or firstname)
            if '.' in local_part and len(local_part.split('.')) >= 2:
                personal.append(email)
            # Business-related
            elif any(keyword in local_part for keyword in [
                'sales', 'business', 'owner', 'ceo', 'president', 'founder'
            ]):
                business.append(email)
            else:
                other.append(email)

        return personal + business + other

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()
