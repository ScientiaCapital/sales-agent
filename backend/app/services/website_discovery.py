"""
Website Discovery Service - Fixed Version

Finds company websites when missing from CSV data.
Uses domain inference + validation (Google scraping is broken due to JS rendering).

Security: Includes SSRF protection to block requests to private IP ranges.
"""

import httpx
import ipaddress
import re
import socket
from typing import Optional, List
from urllib.parse import urlparse, quote_plus

from app.core.logging import setup_logging

logger = setup_logging(__name__)

# =============================================================================
# SSRF Protection (Ported from conductor-ai)
# =============================================================================

# Private IP ranges for SSRF protection
PRIVATE_IP_RANGES = [
    ipaddress.ip_network("127.0.0.0/8"),      # Loopback
    ipaddress.ip_network("10.0.0.0/8"),       # Private class A
    ipaddress.ip_network("172.16.0.0/12"),    # Private class B
    ipaddress.ip_network("192.168.0.0/16"),   # Private class C
    ipaddress.ip_network("169.254.0.0/16"),   # Link-local (AWS metadata!)
    ipaddress.ip_network("::1/128"),          # IPv6 loopback
    ipaddress.ip_network("fc00::/7"),         # IPv6 private
    ipaddress.ip_network("fe80::/10"),        # IPv6 link-local
]


def validate_not_private_ip(hostname: str) -> None:
    """
    Resolve hostname and validate it's not a private IP.

    SSRF Protection: Blocks requests to internal network resources.

    Args:
        hostname: Hostname to resolve and validate

    Raises:
        ValueError: If hostname resolves to private IP
    """
    try:
        addr_info = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
        for addr in addr_info:
            ip_str = addr[4][0]
            ip = ipaddress.ip_address(ip_str)
            for private_range in PRIVATE_IP_RANGES:
                if ip in private_range:
                    logger.warning(f"SSRF blocked: {hostname} resolves to private IP {ip}")
                    raise ValueError(f"Access to private IP address blocked: {ip}")
    except socket.gaierror:
        # DNS resolution failed - let HTTP request handle the error
        pass


def validate_url_not_private(url: str) -> None:
    """
    Validate URL doesn't point to private IP (direct or via DNS).

    Args:
        url: URL to validate

    Raises:
        ValueError: If URL points to private IP
    """
    try:
        parsed = urlparse(url)
        if not parsed.hostname:
            raise ValueError("URL must have a hostname")

        # Check if hostname is a direct IP address
        try:
            ip = ipaddress.ip_address(parsed.hostname)
            for private_range in PRIVATE_IP_RANGES:
                if ip in private_range:
                    logger.warning(f"SSRF blocked: Direct private IP in URL: {url}")
                    raise ValueError(f"Access to private IP address blocked: {ip}")
        except ValueError as e:
            if "private IP" in str(e):
                raise
            # Not an IP address - it's a domain name, validate via DNS
            validate_not_private_ip(parsed.hostname)

    except Exception as e:
        if "private IP" in str(e) or "blocked" in str(e):
            raise
        # Other parsing errors - let HTTP request handle


class WebsiteDiscoveryService:
    """
    Discovers company websites using multiple strategies.

    Strategy 1: Domain inference from company name + HTTP validation
    Strategy 2: DuckDuckGo search (returns static HTML, unlike Google)

    Note: Google scraping doesn't work - returns JS-rendered content without URLs.
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
        Discover company website via domain inference and search.

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

        logger.info(f"Searching for website: {company_name}")

        # Strategy 1: Try domain inference (fast, free)
        website = await self._infer_domain(company_name)
        if website:
            logger.info(f"✅ Found website via inference: {website}")
            return website

        # Strategy 2: Search DuckDuckGo (static HTML, actually works)
        website = await self._search_duckduckgo(company_name, industry)
        if website:
            logger.info(f"✅ Found website via DuckDuckGo: {website}")
            return website

        logger.info(f"Could not discover website for {company_name}")
        return None

    async def _infer_domain(self, company_name: str) -> Optional[str]:
        """
        Infer domain from company name and validate via HTTP.

        Most contractor websites follow predictable patterns:
        - companyname.com
        - companynameservices.com
        - companynamellc.com
        """
        # Clean company name for domain
        clean_name = self._clean_for_domain(company_name)

        if not clean_name:
            return None

        # Generate candidate domains
        candidates = [
            f"{clean_name}.com",
            f"{clean_name}inc.com",
            f"{clean_name}llc.com",
            f"{clean_name}services.com",
            f"{clean_name}hvac.com",
            f"{clean_name}plumbing.com",
            f"{clean_name}mechanical.com",
            f"{clean_name}electric.com",
            f"{clean_name}energy.com",
            f"www.{clean_name}.com",
        ]

        # Remove duplicates while preserving order
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                unique_candidates.append(c)

        # Validate each candidate
        for domain in unique_candidates[:8]:  # Check top 8
            website = await self._validate_domain(domain)
            if website:
                return website

        return None

    def _clean_for_domain(self, company_name: str) -> str:
        """
        Clean company name for domain generation.

        Examples:
        - "TRANE U S INC" -> "trane"
        - "Atlanta Roofing LLC" -> "atlantaroofing"
        - "A & B Contractors" -> "abcontractors"
        """
        name = company_name.lower()

        # Remove common suffixes
        suffixes = [
            r'\s+llc\s*$', r'\s+inc\s*$', r'\s+corp\s*$', r'\s+co\s*$',
            r'\s+ltd\s*$', r'\s+u\s*s\s*$', r'\s+usa\s*$', r'\s+company\s*$',
            r'\s+services\s*$', r'\s+contractors?\s*$', r'\s+enterprises?\s*$'
        ]
        for suffix in suffixes:
            name = re.sub(suffix, '', name, flags=re.IGNORECASE)

        # Remove punctuation and special chars
        name = re.sub(r'[^a-z0-9]', '', name)

        return name.strip()

    async def _search_duckduckgo(self, company_name: str, industry: str = "") -> Optional[str]:
        """
        Search DuckDuckGo for company website.

        DuckDuckGo returns static HTML (unlike Google's JS-rendered results).
        """
        try:
            # Build search query
            query_parts = [f'"{company_name}"']
            if industry:
                query_parts.append(industry)
            query_parts.append("official website")
            query = " ".join(query_parts)

            # DuckDuckGo HTML endpoint
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

            response = await self.client.get(search_url)

            if response.status_code != 200:
                logger.warning(f"DuckDuckGo search failed: HTTP {response.status_code}")
                return None

            # Extract domains from results
            domains = self._extract_domains_from_ddg(response.text, company_name)

            if not domains:
                return None

            # Validate top candidates
            for domain in domains[:5]:
                website = await self._validate_domain(domain)
                if website:
                    return website

            return None

        except Exception as e:
            logger.error(f"DuckDuckGo search failed: {e}")
            return None

    def _extract_domains_from_ddg(self, html: str, company_name: str) -> List[str]:
        """
        Extract domains from DuckDuckGo search results.

        DuckDuckGo's HTML structure has result URLs in specific patterns.
        """
        domains = set()

        # DuckDuckGo result URL pattern
        # Results appear as: href="//duckduckgo.com/l/?uddg=https://..."
        uddg_pattern = r'uddg=(https?://[^&"]+)'
        uddg_urls = re.findall(uddg_pattern, html)

        # Also try direct href pattern
        href_pattern = r'href="(https?://[^"]+)"'
        href_urls = re.findall(href_pattern, html)

        # Process all found URLs
        for url in uddg_urls + href_urls:
            try:
                from urllib.parse import unquote
                url = unquote(url)
                parsed = urlparse(url)
                domain = parsed.netloc.lower()

                # Skip unwanted domains
                if any(skip in domain for skip in self.skip_domains):
                    continue
                if 'duckduckgo' in domain:
                    continue

                if domain:
                    domains.add(domain)

            except Exception:
                continue

        # Sort by relevance to company name
        company_words = set(self._clean_for_domain(company_name))

        def relevance_score(domain):
            domain_clean = domain.replace('.com', '').replace('.net', '').replace('.org', '').replace('www.', '')
            # Higher score = more relevant
            if company_words and any(word in domain_clean for word in company_words if len(word) > 2):
                return 1
            return 0

        sorted_domains = sorted(domains, key=relevance_score, reverse=True)

        return list(sorted_domains)

    async def _validate_domain(self, domain: str) -> Optional[str]:
        """
        Validate domain is accessible and return full URL.

        Args:
            domain: Domain to validate (e.g., "example.com")

        Returns:
            Full URL if accessible (e.g., "https://example.com"), None otherwise

        Security:
            Includes SSRF protection - blocks private IP ranges.
        """
        # Ensure domain doesn't have protocol
        if domain.startswith('http'):
            return None

        # SSRF Protection: Validate domain doesn't resolve to private IP
        try:
            validate_not_private_ip(domain)
        except ValueError as e:
            logger.warning(f"SSRF protection blocked domain: {domain} - {e}")
            return None

        # Try HTTPS first, then HTTP
        for protocol in ['https', 'http']:
            url = f"{protocol}://{domain}"
            try:
                response = await self.client.head(url, timeout=5)
                if response.status_code < 400:
                    return url
            except Exception:
                continue

        return None


# Singleton instance
_service_instance = None


async def get_website_discovery_service() -> WebsiteDiscoveryService:
    """Get or create the website discovery service singleton."""
    global _service_instance
    if _service_instance is None:
        _service_instance = WebsiteDiscoveryService()
    return _service_instance


# Export SSRF protection functions for use by other services
__all__ = [
    "WebsiteDiscoveryService",
    "get_website_discovery_service",
    "validate_not_private_ip",
    "validate_url_not_private",
    "PRIVATE_IP_RANGES",
]
