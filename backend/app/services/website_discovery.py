"""
Website Discovery Service

Finds company websites when missing from CSV data.
Uses Google search + domain validation to discover websites.
"""

import httpx
import re
from typing import Optional, List
from urllib.parse import urlparse, quote_plus

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class WebsiteDiscoveryService:
    """
    Discovers company websites using Google search when not provided in CSV.

    Flow:
    1. Search Google for company name + industry keywords
    2. Extract potential domains from search results
    3. Validate domain is accessible and relevant
    4. Return best match
    """

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=10,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

        # Domains to skip (not company websites)
        self.skip_domains = {
            "facebook.com", "linkedin.com", "twitter.com", "instagram.com",
            "youtube.com", "yelp.com", "yellowpages.com", "bbb.org",
            "google.com", "mapquest.com", "manta.com", "houzz.com",
            "homeadvisor.com", "angieslist.com", "thumbtack.com",
            "nextdoor.com", "reddit.com", "pinterest.com", "tiktok.com"
        }

    async def discover_website(
        self,
        company_name: str,
        industry: str = "",
        city: str = "",
        state: str = ""
    ) -> Optional[str]:
        """
        Discover company website via Google search.

        Args:
            company_name: Company name to search for
            industry: Industry/service type (e.g., "plumbing", "HVAC")
            city: City for geo-targeting
            state: State for geo-targeting

        Returns:
            Website URL if found, None otherwise
        """
        if not company_name:
            return None

        # Build search query
        query_parts = [f'"{company_name}"']
        if industry:
            query_parts.append(industry)
        if city:
            query_parts.append(city)
        if state:
            query_parts.append(state)
        query_parts.append("official website")

        query = " ".join(query_parts)

        logger.info(f"Searching for website: {company_name}")

        try:
            # Search Google
            search_url = f"https://www.google.com/search?q={quote_plus(query)}&num=10"
            response = await self.client.get(search_url)

            if response.status_code != 200:
                logger.warning(f"Google search failed: HTTP {response.status_code}")
                return None

            # Extract URLs from search results
            html = response.text
            domains = self._extract_domains(html, company_name)

            if not domains:
                logger.info(f"No domains found for {company_name}")
                return None

            # Validate and return first accessible domain
            for domain in domains[:5]:  # Check top 5
                website = await self._validate_domain(domain)
                if website:
                    logger.info(f"Found website for {company_name}: {website}")
                    return website

            logger.info(f"No valid website found for {company_name}")
            return None

        except Exception as e:
            logger.error(f"Website discovery failed for {company_name}: {e}")
            return None

    def _extract_domains(self, html: str, company_name: str) -> List[str]:
        """
        Extract potential company domains from Google search HTML.

        Args:
            html: Google search results HTML
            company_name: Company name for relevance scoring

        Returns:
            List of domains sorted by relevance
        """
        # Find all URLs in the search results
        url_pattern = r'https?://([a-zA-Z0-9][-a-zA-Z0-9]*\.)+[a-zA-Z]{2,}'
        urls = re.findall(url_pattern, html)

        # Also try to find href patterns
        href_pattern = r'href="(https?://[^"]+)"'
        hrefs = re.findall(href_pattern, html)

        # Extract domains
        domains = set()
        for url in urls + hrefs:
            try:
                if isinstance(url, str) and url.startswith('http'):
                    parsed = urlparse(url)
                    domain = parsed.netloc.lower()
                else:
                    domain = url.lower().rstrip('.')

                # Skip unwanted domains
                if any(skip in domain for skip in self.skip_domains):
                    continue

                # Skip Google's own domains
                if 'google' in domain:
                    continue

                # Clean domain
                domain = domain.replace('www.', '')
                if domain:
                    domains.add(domain)

            except Exception:
                continue

        # Sort by relevance (prefer domains that match company name)
        company_words = set(company_name.lower().split())

        def relevance_score(domain: str) -> int:
            score = 0
            domain_lower = domain.lower()

            # Exact match in domain
            for word in company_words:
                if len(word) > 2 and word in domain_lower:
                    score += 10

            # Shorter domains often better
            score -= len(domain) // 5

            return score

        sorted_domains = sorted(domains, key=relevance_score, reverse=True)
        return sorted_domains

    async def _validate_domain(self, domain: str) -> Optional[str]:
        """
        Validate that a domain is accessible.

        Args:
            domain: Domain to validate

        Returns:
            Full URL if accessible, None otherwise
        """
        urls_to_try = [
            f"https://{domain}",
            f"https://www.{domain}",
            f"http://{domain}"
        ]

        for url in urls_to_try:
            try:
                response = await self.client.head(url, timeout=5)
                if response.status_code < 400:
                    # Follow redirects to get final URL
                    if response.has_redirect_location:
                        return str(response.headers.get('location', url))
                    return url
            except Exception:
                continue

        return None

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


# Singleton instance
_discovery_service: Optional[WebsiteDiscoveryService] = None


def get_website_discovery_service() -> WebsiteDiscoveryService:
    """Get or create website discovery service instance."""
    global _discovery_service
    if _discovery_service is None:
        _discovery_service = WebsiteDiscoveryService()
    return _discovery_service
