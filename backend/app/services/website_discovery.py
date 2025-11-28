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

        # Domains to skip (not company websites) - NOTE: facebook.com removed
        # Facebook business pages can be valid contact sources for small contractors
        self.skip_domains = {
            "linkedin.com", "twitter.com", "instagram.com",
            "youtube.com", "yelp.com", "yellowpages.com", "bbb.org",
            "google.com", "mapquest.com", "manta.com", "houzz.com",
            "homeadvisor.com", "angieslist.com", "thumbtack.com",
            "nextdoor.com", "reddit.com", "pinterest.com", "tiktok.com"
        }

        # Social domains - we'll extract but flag separately
        self.social_domains = {"facebook.com"}

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

        # Strategy 3: Try Facebook business page search
        facebook_url = await self._search_facebook_page(company_name, city, state)
        if facebook_url:
            logger.info(f"✅ Found Facebook page (no website): {facebook_url}")
            return facebook_url

        logger.info(f"Could not discover website for {company_name}")
        return None

    async def _search_facebook_page(
        self,
        company_name: str,
        city: str = "",
        state: str = ""
    ) -> Optional[str]:
        """
        Search for company's Facebook business page.

        Many small contractors only have Facebook pages, not websites.
        This is a valid contact source for outreach.
        """
        try:
            # Build search query for Facebook page
            query_parts = [company_name]
            if city:
                query_parts.append(city)
            if state:
                query_parts.append(state)
            query_parts.append("facebook")
            query = " ".join(query_parts)

            # Search DuckDuckGo for Facebook page
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

            response = await self.client.get(search_url)

            if response.status_code != 200:
                return None

            # Extract Facebook page names from results (not posts/videos)
            # Pattern: facebook.com/PageName or facebook.com/PageName/
            fb_pattern = r'facebook\.com/([A-Za-z0-9._-]+)/?(?:["\s&?]|$)'
            matches = re.findall(fb_pattern, response.text)

            seen_pages = set()
            for match in matches:
                # Clean up the match
                page_name = match.rstrip('/')

                # Skip generic Facebook pages and subpaths
                skip_names = [
                    'login', 'help', 'pages', 'groups', 'events', 'marketplace',
                    'watch', 'reel', 'posts', 'videos', 'photos', 'about',
                    'reviews', 'services', 'shop', 'offers', 'jobs'
                ]
                if page_name.lower() in skip_names:
                    continue

                # Skip if already checked
                if page_name.lower() in seen_pages:
                    continue
                seen_pages.add(page_name.lower())

                # Only check first 5 unique pages
                if len(seen_pages) > 5:
                    break

                fb_url = f"https://www.facebook.com/{page_name}"

                # Validate the Facebook page exists
                try:
                    check_response = await self.client.head(fb_url, timeout=5)
                    if check_response.status_code < 400:
                        logger.info(f"✅ Found Facebook business page: {fb_url}")
                        return fb_url
                except Exception:
                    continue

            return None

        except Exception as e:
            logger.debug(f"Facebook search failed: {e}")
            return None

    async def discover_google_business(
        self,
        company_name: str,
        city: str = "",
        state: str = ""
    ) -> Optional[dict]:
        """
        Search for Google Business Profile.

        Returns dict with website, phone, address if found.
        Google Business profiles often have contact info even when website is hard to find.
        """
        try:
            # Build search query for Google Business
            query_parts = [company_name]
            if city:
                query_parts.append(city)
            if state:
                query_parts.append(state)
            query = " ".join(query_parts)

            # Search Google Maps (redirects to business profile)
            maps_url = f"https://www.google.com/maps/search/{quote_plus(query)}"

            # Note: This won't work perfectly due to JS rendering,
            # but sometimes we can extract the business listing URL
            response = await self.client.get(
                maps_url,
                follow_redirects=True,
                timeout=10
            )

            # Try to extract website URL from response
            # Google Maps embeds business URLs in the page
            website_pattern = r'"website":"(https?://[^"]+)"'
            phone_pattern = r'"phone":"([^"]+)"'

            website_match = re.search(website_pattern, response.text)
            phone_match = re.search(phone_pattern, response.text)

            result = {}
            if website_match:
                website = website_match.group(1)
                if not any(skip in website for skip in self.skip_domains):
                    result['website'] = website
                    logger.info(f"✅ Found website via Google Business: {website}")

            if phone_match:
                result['phone'] = phone_match.group(1)
                logger.info(f"✅ Found phone via Google Business: {result['phone']}")

            return result if result else None

        except Exception as e:
            logger.debug(f"Google Business search failed: {e}")
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
        - "BROWER MECHANICAL CA LLC" -> "browermechanical"
        """
        name = company_name.lower()

        # Remove common suffixes (order matters - check longer patterns first)
        suffixes = [
            r'\s+llc\s*$', r'\s+inc\s*$', r'\s+corp\s*$', r'\s+co\s*$',
            r'\s+ltd\s*$', r'\s+u\s*s\s*$', r'\s+usa\s*$', r'\s+company\s*$',
            r'\s+services\s*$', r'\s+contractors?\s*$', r'\s+enterprises?\s*$',
            r'\s+group\s*$', r'\s+solutions\s*$', r'\s+systems\s*$',
        ]
        for suffix in suffixes:
            name = re.sub(suffix, '', name, flags=re.IGNORECASE)

        # Remove state abbreviations (at end of name, common in contractor names)
        # Must be done AFTER removing LLC/INC since pattern is: "COMPANY STATE LLC"
        state_abbrevs = [
            r'\s+(?:ca|tx|fl|ny|az|nv|wa|or|co|ga|nc|sc|va|md|pa|oh|mi|il|nj|ma)\s*$'
        ]
        for state in state_abbrevs:
            name = re.sub(state, '', name, flags=re.IGNORECASE)

        # Remove punctuation and special chars
        name = re.sub(r'[^a-z0-9]', '', name)

        return name.strip()

    async def _search_duckduckgo(self, company_name: str, industry: str = "") -> Optional[str]:
        """
        Search DuckDuckGo for company website.

        DuckDuckGo returns static HTML (unlike Google's JS-rendered results).
        Tries multiple search strategies to find elusive websites.
        """
        # Strategy 1: Exact name + industry + "official website"
        # Strategy 2: Just company name (some companies use unrelated domain names)
        # Strategy 3: Company name + city/state if available
        search_queries = [
            f'"{company_name}" {industry} official website' if industry else f'"{company_name}" official website',
            f'"{company_name}" contractor',  # Simpler search
            f'{company_name} site:.com',  # Force .com results
        ]

        all_domains = set()

        for query in search_queries:
            try:
                # DuckDuckGo HTML endpoint
                search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

                response = await self.client.get(search_url)

                if response.status_code != 200:
                    continue

                # Extract domains from results
                domains = self._extract_domains_from_ddg(response.text, company_name)
                all_domains.update(domains)

            except Exception as e:
                logger.debug(f"DuckDuckGo query '{query[:50]}' failed: {e}")
                continue

        if not all_domains:
            # Try Google as last resort (may work for some queries)
            google_result = await self._search_google(company_name, industry)
            if google_result:
                return google_result
            return None

        # Sort by relevance and validate top candidates
        sorted_domains = self._rank_domains(list(all_domains), company_name)

        for domain in sorted_domains[:8]:  # Check more candidates
            website = await self._validate_domain(domain)
            if website:
                return website

        return None

    async def _search_google(self, company_name: str, industry: str = "") -> Optional[str]:
        """
        Search Google as fallback (limited, may not work due to JS rendering).

        Uses Google's "I'm Feeling Lucky" redirect which sometimes works.
        Also parses Google's redirect URLs to extract actual destination.
        """
        try:
            query = f'{company_name} {industry} official site' if industry else f'{company_name} official site'
            # Google's lucky redirect (bypasses JS rendering)
            search_url = f"https://www.google.com/search?q={quote_plus(query)}&btnI=1"

            # Don't follow redirects - we need to parse Google's redirect URL
            response = await self.client.get(
                search_url,
                follow_redirects=False,
                timeout=8
            )

            # Check for redirect location header
            if response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = response.headers.get('location', '')

                # Google sometimes uses /url?q= format
                if 'google.com/url' in redirect_url or '/url?q=' in redirect_url:
                    # Extract actual URL from Google redirect
                    from urllib.parse import parse_qs
                    parsed_redirect = urlparse(redirect_url)
                    query_params = parse_qs(parsed_redirect.query)
                    actual_url = query_params.get('q', [''])[0]
                    if actual_url:
                        redirect_url = actual_url

                # Validate and return
                if redirect_url and 'google.com' not in redirect_url:
                    parsed = urlparse(redirect_url)
                    domain = parsed.netloc.lower()
                    if domain and not any(skip in domain for skip in self.skip_domains):
                        # Validate the domain is accessible
                        validated = await self._validate_domain(domain.replace('www.', ''))
                        if validated:
                            logger.info(f"✅ Found website via Google redirect: {validated}")
                            return validated

            # Also try following redirects and check final URL
            response = await self.client.get(
                search_url,
                follow_redirects=True,
                timeout=8
            )

            final_url = str(response.url)

            # Check if final URL contains a redirect to actual site
            if 'google.com/url' in final_url:
                from urllib.parse import parse_qs
                parsed = urlparse(final_url)
                query_params = parse_qs(parsed.query)
                actual_url = query_params.get('q', [''])[0]
                if actual_url and 'google.com' not in actual_url:
                    parsed_actual = urlparse(actual_url)
                    domain = parsed_actual.netloc.lower()
                    if domain and not any(skip in domain for skip in self.skip_domains):
                        validated = await self._validate_domain(domain.replace('www.', ''))
                        if validated:
                            logger.info(f"✅ Found website via Google URL param: {validated}")
                            return validated

            # If we got redirected to an actual website (not google.com)
            if 'google.com' not in final_url and response.status_code < 400:
                parsed = urlparse(final_url)
                domain = parsed.netloc.lower()
                if domain and not any(skip in domain for skip in self.skip_domains):
                    logger.info(f"✅ Found website via Google redirect: {final_url}")
                    return f"https://{domain}"

            return None

        except Exception as e:
            logger.debug(f"Google search failed: {e}")
            return None

    def _rank_domains(self, domains: List[str], company_name: str) -> List[str]:
        """
        Rank domains by relevance to company name.

        Higher scores for domains that contain company name words.
        """
        clean_name = self._clean_for_domain(company_name)
        # Also get individual words from company name
        name_words = set(re.sub(r'[^a-z\s]', '', company_name.lower()).split())
        name_words = {w for w in name_words if len(w) > 2}  # Skip short words

        def relevance_score(domain: str) -> int:
            domain_clean = domain.replace('.com', '').replace('.net', '').replace('.org', '').replace('www.', '')
            score = 0

            # Exact match gets highest score
            if clean_name in domain_clean:
                score += 100

            # Partial word matches
            for word in name_words:
                if word in domain_clean:
                    score += 10

            # Prefer shorter domains (less likely to be directories/subpages)
            if len(domain) < 20:
                score += 5

            return score

        return sorted(domains, key=relevance_score, reverse=True)

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
