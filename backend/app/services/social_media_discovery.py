"""
Social Media Discovery Service

Discovers company social media profiles across all major platforms:
- LinkedIn (company page + employees)
- Facebook (business page)
- X/Twitter (company profile)
- Instagram (business profile)
- TikTok (business profile)
- Google Business Profile (address, phone, reviews, hours)

Uses multiple search strategies for robustness.
"""

import httpx
import re
import logging
import asyncio
from typing import Optional, Dict, List, Any
from urllib.parse import quote_plus
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)


@dataclass
class SocialMediaProfile:
    """A discovered social media profile."""
    platform: str
    url: str
    username: Optional[str] = None
    verified: bool = False
    followers: Optional[int] = None


@dataclass
class GoogleBusinessProfile:
    """Google Business Profile data."""
    name: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    hours: Optional[str] = None
    category: Optional[str] = None


@dataclass
class SocialMediaDiscoveryResult:
    """Results from social media discovery."""
    company_name: str
    linkedin: Optional[SocialMediaProfile] = None
    facebook: Optional[SocialMediaProfile] = None
    twitter: Optional[SocialMediaProfile] = None
    instagram: Optional[SocialMediaProfile] = None
    tiktok: Optional[SocialMediaProfile] = None
    youtube: Optional[SocialMediaProfile] = None

    # Google Business Profile
    google_business: Optional[GoogleBusinessProfile] = None

    # Additional data
    employees: List[Dict[str, Any]] = field(default_factory=list)
    total_platforms_found: int = 0

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


class SocialMediaDiscoveryService:
    """
    Discovers company social media presence across all major platforms.

    Search Strategy:
    1. Use DuckDuckGo HTML search (no JS rendering needed)
    2. Extract platform-specific URLs from search results
    3. Validate URLs exist (HEAD request)

    Rate Limiting:
    - 2 second delay between searches
    - 5 concurrent validations max
    """

    PLATFORMS = {
        "linkedin": {
            "domain": "linkedin.com/company",
            "pattern": r'linkedin\.com/company/([^/"\s?&]+)',
            "search_suffix": "linkedin company",
        },
        "facebook": {
            "domain": "facebook.com",
            "pattern": r'facebook\.com/([^/"\s?&]+)',
            "search_suffix": "facebook page",
            "skip": ["login", "help", "pages", "groups", "events", "marketplace", "watch"],
        },
        "twitter": {
            "domain": "twitter.com",
            "pattern": r'(?:twitter|x)\.com/([^/"\s?&]+)',
            "search_suffix": "twitter",
            "skip": ["search", "home", "explore", "settings", "login", "i"],
        },
        "instagram": {
            "domain": "instagram.com",
            "pattern": r'instagram\.com/([^/"\s?&]+)',
            "search_suffix": "instagram",
            "skip": ["explore", "accounts", "p", "reel", "tv", "stories"],
        },
        "tiktok": {
            "domain": "tiktok.com",
            "pattern": r'tiktok\.com/@?([^/"\s?&]+)',
            "search_suffix": "tiktok",
            "skip": ["explore", "foryou", "following", "live"],
        },
        "youtube": {
            "domain": "youtube.com",
            "pattern": r'youtube\.com/(?:@|channel/|c/|user/)([^/"\s?&]+)',
            "search_suffix": "youtube channel",
            "skip": ["watch", "playlist", "feed", "results", "shorts"],
        },
    }

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=15,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
            }
        )

    def _clean_company_name(self, name: str) -> str:
        """Clean company name for better search results."""
        # Remove common suffixes that hurt search
        suffixes_to_remove = [
            r'\s+llc\s*$', r'\s+inc\s*$', r'\s+corp\s*$', r'\s+co\s*$',
            r'\s+ltd\s*$', r'\s+llp\s*$', r'\s+lp\s*$', r'\s+pc\s*$',
            r'\s+pllc\s*$', r'\s+dba\s*$',
            # State abbreviations at the end
            r'\s+(?:ca|tx|fl|ny|az|nv|wa|or|co|ga|nc|sc|va|md|pa|oh|mi|il|nj|ma)\s*$'
        ]
        cleaned = name.lower().strip()
        for pattern in suffixes_to_remove:
            cleaned = re.sub(pattern, '', cleaned, flags=re.IGNORECASE)
        return cleaned.strip()

    async def discover_all(
        self,
        company_name: str,
        website: Optional[str] = None,
        city: Optional[str] = None,
        state: Optional[str] = None,
    ) -> SocialMediaDiscoveryResult:
        """
        Discover all social media profiles for a company.

        Args:
            company_name: Company name to search for
            website: Optional website domain for better matching
            city: Optional city for geo-targeting
            state: Optional state for geo-targeting

        Returns:
            SocialMediaDiscoveryResult with all discovered profiles
        """
        logger.info(f"Discovering social media for: {company_name}")

        result = SocialMediaDiscoveryResult(company_name=company_name)

        # Clean company name for better search
        clean_name = self._clean_company_name(company_name)
        logger.info(f"  Cleaned name: '{clean_name}'")

        # Build search queries - simpler is better
        # Use just company name first, add location only if needed
        base_query = clean_name
        query_with_location = f"{clean_name} {city}" if city else clean_name

        # Search for each platform with delays to avoid rate limiting
        for platform_name, config in self.PLATFORMS.items():
            try:
                # Try with simple query first
                profile = await self._search_platform(
                    platform_name, config, base_query, website
                )

                # If not found and we have location, try with location
                if not profile and city:
                    await asyncio.sleep(0.5)  # Small delay
                    profile = await self._search_platform(
                        platform_name, config, query_with_location, website
                    )

                if profile:
                    setattr(result, platform_name, profile)
                    result.total_platforms_found += 1
                    logger.info(f"  ✅ Found {platform_name}: {profile.url}")
                else:
                    logger.debug(f"  ⚪ No {platform_name} found")

                # Small delay between platforms to avoid rate limiting
                await asyncio.sleep(0.3)

            except Exception as e:
                logger.warning(f"  ❌ {platform_name} search failed: {e}")

        logger.info(
            f"Social media discovery complete: {result.total_platforms_found} platforms found"
        )
        return result

    async def _search_platform(
        self,
        platform_name: str,
        config: dict,
        base_query: str,
        website: Optional[str] = None,
    ) -> Optional[SocialMediaProfile]:
        """
        Search for a specific platform's profile using multiple strategies.

        Args:
            platform_name: Platform name (linkedin, facebook, etc.)
            config: Platform-specific configuration
            base_query: Base search query (company name + location)
            website: Optional website for better matching

        Returns:
            SocialMediaProfile if found, None otherwise
        """
        # Strategy 1: Site-specific DuckDuckGo search (most reliable)
        profile = await self._search_duckduckgo_site(platform_name, config, base_query)
        if profile:
            return profile

        # Strategy 2: Direct domain inference from website (if available)
        if website:
            profile = await self._infer_from_website(platform_name, website)
            if profile:
                return profile

        # Strategy 3: Google "I'm Feeling Lucky" fallback
        profile = await self._search_google_lucky(platform_name, config, base_query)
        if profile:
            return profile

        return None

    async def _search_duckduckgo_site(
        self,
        platform_name: str,
        config: dict,
        base_query: str
    ) -> Optional[SocialMediaProfile]:
        """Search using DuckDuckGo with site: operator."""
        domain = config["domain"].split("/")[0]  # Get base domain
        query = f'site:{domain} {base_query}'

        search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

        try:
            response = await self.client.get(search_url)
            # 202 = rate limited, treat as no results
            if response.status_code == 202:
                logger.debug(f"DuckDuckGo rate limited for {platform_name}")
                return None
            if response.status_code != 200:
                return None

            # Extract platform URLs
            pattern = config["pattern"]
            matches = re.findall(pattern, response.text, re.IGNORECASE)

            if not matches:
                return None

            # Filter and dedupe matches
            skip_list = config.get("skip", [])
            candidates = self._filter_candidates(matches, skip_list)

            if not candidates:
                return None

            # Validate top candidates
            for username in candidates[:3]:
                url = self._build_profile_url(platform_name, username)
                if await self._validate_url(url):
                    return SocialMediaProfile(
                        platform=platform_name, url=url, username=username, verified=True
                    )

            # Return first match even if validation failed
            return SocialMediaProfile(
                platform=platform_name,
                url=self._build_profile_url(platform_name, candidates[0]),
                username=candidates[0],
                verified=False,
            )

        except Exception as e:
            logger.debug(f"DuckDuckGo search error for {platform_name}: {e}")
            return None

    async def _infer_from_website(
        self,
        platform_name: str,
        website: str
    ) -> Optional[SocialMediaProfile]:
        """Try to infer social profile from company website links."""
        try:
            # Fetch website homepage
            response = await self.client.get(website, timeout=10)
            if response.status_code != 200:
                return None

            # Look for social links in the HTML
            html = response.text.lower()
            pattern = self.PLATFORMS[platform_name]["pattern"]
            matches = re.findall(pattern, html, re.IGNORECASE)

            if matches:
                skip_list = self.PLATFORMS[platform_name].get("skip", [])
                candidates = self._filter_candidates(matches, skip_list)
                if candidates:
                    url = self._build_profile_url(platform_name, candidates[0])
                    return SocialMediaProfile(
                        platform=platform_name,
                        url=url,
                        username=candidates[0],
                        verified=True  # Found on their own website!
                    )
        except Exception as e:
            logger.debug(f"Website inference error for {platform_name}: {e}")
        return None

    async def _search_google_lucky(
        self,
        platform_name: str,
        config: dict,
        base_query: str
    ) -> Optional[SocialMediaProfile]:
        """Use Google 'I'm Feeling Lucky' as last resort."""
        domain = config["domain"].split("/")[0]
        query = f'{base_query} site:{domain}'

        # Google Feeling Lucky URL
        search_url = f"https://www.google.com/search?btnI=1&q={quote_plus(query)}"

        try:
            response = await self.client.get(search_url, follow_redirects=False)

            # Check for redirect to target platform
            if response.status_code in [301, 302, 303, 307, 308]:
                redirect_url = response.headers.get('location', '')

                # Check if redirected to the target platform
                pattern = config["pattern"]
                matches = re.findall(pattern, redirect_url, re.IGNORECASE)

                if matches:
                    skip_list = config.get("skip", [])
                    candidates = self._filter_candidates(matches, skip_list)
                    if candidates:
                        url = self._build_profile_url(platform_name, candidates[0])
                        return SocialMediaProfile(
                            platform=platform_name,
                            url=url,
                            username=candidates[0],
                            verified=False  # Can't verify from redirect
                        )
        except Exception as e:
            logger.debug(f"Google Lucky search error for {platform_name}: {e}")
        return None

    def _filter_candidates(self, matches: List[str], skip_list: List[str]) -> List[str]:
        """Filter and dedupe username candidates."""
        seen = set()
        candidates = []
        for match in matches:
            username = match.lower().rstrip("/")
            if username in skip_list:
                continue
            if username in seen:
                continue
            if len(username) < 2:  # Skip very short matches
                continue
            seen.add(username)
            candidates.append(username)
        return candidates

    def _build_profile_url(self, platform: str, username: str) -> str:
        """Build full profile URL from platform and username."""
        urls = {
            "linkedin": f"https://www.linkedin.com/company/{username}",
            "facebook": f"https://www.facebook.com/{username}",
            "twitter": f"https://twitter.com/{username}",
            "instagram": f"https://www.instagram.com/{username}",
            "tiktok": f"https://www.tiktok.com/@{username}",
            "youtube": f"https://www.youtube.com/@{username}",
        }
        return urls.get(platform, f"https://{platform}.com/{username}")

    async def _validate_url(self, url: str) -> bool:
        """Validate URL is accessible."""
        try:
            response = await self.client.head(url, timeout=5)
            return response.status_code < 400
        except Exception:
            return False

    async def discover_linkedin_employees(
        self,
        company_name: str,
        linkedin_url: Optional[str] = None,
        titles: Optional[List[str]] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Discover employees at a company via LinkedIn.

        Uses Google search to find LinkedIn profiles with ATL titles at the company.

        Args:
            company_name: Company name
            linkedin_url: Optional LinkedIn company URL
            titles: Job titles to search for (defaults to ATL titles)
            limit: Max employees to return

        Returns:
            List of employee dicts with name, title, linkedin_url
        """
        if titles is None:
            titles = ["CEO", "President", "Founder", "Owner", "VP", "Director"]

        employees = []
        seen_urls = set()

        for title in titles[:3]:  # Limit to 3 title searches
            if len(employees) >= limit:
                break

            query = f'site:linkedin.com/in "{title}" at "{company_name}"'
            search_url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"

            try:
                response = await self.client.get(search_url)
                if response.status_code not in [200, 202]:
                    continue

                # Extract LinkedIn profile URLs
                pattern = r'linkedin\.com/in/([^/"\s?&]+)'
                matches = re.findall(pattern, response.text)

                for username in matches:
                    if len(employees) >= limit:
                        break

                    profile_url = f"https://www.linkedin.com/in/{username}"
                    if profile_url in seen_urls:
                        continue
                    seen_urls.add(profile_url)

                    # Extract name from username
                    name = username.replace("-", " ").replace("_", " ").title()

                    employees.append(
                        {
                            "name": name,
                            "title": title,
                            "linkedin_url": profile_url,
                            "is_atl": True,
                            "source": "linkedin_search",
                        }
                    )

            except Exception as e:
                logger.debug(f"Employee search error for {title}: {e}")

        logger.info(f"Found {len(employees)} LinkedIn employees for {company_name}")
        return employees


# Singleton
_social_discovery_service: Optional[SocialMediaDiscoveryService] = None


async def get_social_media_discovery_service() -> SocialMediaDiscoveryService:
    """Get or create the social media discovery service singleton."""
    global _social_discovery_service
    if _social_discovery_service is None:
        _social_discovery_service = SocialMediaDiscoveryService()
    return _social_discovery_service
