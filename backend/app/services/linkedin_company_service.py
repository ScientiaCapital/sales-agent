"""
LinkedIn Company Search Service

Finds LinkedIn company profile from domain/name.
Uses Google search to find company LinkedIn pages.

Performance: ~1000ms per search
Strategy: Google search "site:linkedin.com/company {domain|name}"
"""

from typing import Optional
import httpx
from pydantic import BaseModel, HttpUrl
import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LinkedInCompany(BaseModel):
    """LinkedIn company profile"""
    name: str
    linkedin_url: str  # Using str instead of HttpUrl for flexibility
    company_id: Optional[str] = None  # LinkedIn company ID (e.g., "acme-corp")
    industry: Optional[str] = None
    employee_count: Optional[int] = None
    description: Optional[str] = None
    website: Optional[str] = None
    source: str = "linkedin"


class LinkedInCompanyResult(BaseModel):
    """Result from LinkedIn company search"""
    company: Optional[LinkedInCompany] = None
    status: str  # "success" | "not_found" | "error"
    error_message: Optional[str] = None


class LinkedInCompanyService:
    """LinkedIn company search service"""

    def __init__(self):
        self.timeout = 10.0
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

    async def find_company(
        self,
        company_name: str,
        website: Optional[str] = None
    ) -> LinkedInCompanyResult:
        """
        Find LinkedIn company profile

        Args:
            company_name: Company name to search
            website: Optional website domain for verification

        Returns:
            LinkedInCompanyResult with company profile
        """
        try:
            logger.info(f"Searching for LinkedIn company: {company_name}")

            # Strategy 1: Search by domain (most accurate)
            if website:
                result = await self._search_by_domain(website, company_name)
                if result.status == "success":
                    logger.info(f"Found LinkedIn company by domain: {result.company.linkedin_url}")
                    return result

            # Strategy 2: Search by company name
            logger.info(f"Fallback to name search for: {company_name}")
            result = await self._search_by_name(company_name)

            if result.status == "success":
                logger.info(f"Found LinkedIn company by name: {result.company.linkedin_url}")
            else:
                logger.warning(f"LinkedIn company not found for: {company_name}")

            return result

        except Exception as e:
            logger.error(f"LinkedIn company search failed: {e}")
            return LinkedInCompanyResult(
                company=None,
                status="error",
                error_message=str(e)
            )

    async def _search_by_domain(self, website: str, company_name: str) -> LinkedInCompanyResult:
        """Search LinkedIn by domain using Google"""
        # Clean domain
        domain = website.replace("https://", "").replace("http://", "").split("/")[0]

        # Google search query
        query = f"site:linkedin.com/company {domain}"

        return await self._google_search(query, company_name)

    async def _search_by_name(self, company_name: str) -> LinkedInCompanyResult:
        """Search LinkedIn by company name using Google"""
        # Google search query
        query = f'site:linkedin.com/company "{company_name}"'

        return await self._google_search(query, company_name)

    async def _google_search(self, query: str, company_name: str) -> LinkedInCompanyResult:
        """
        Perform Google search to find LinkedIn company page

        Note: This is a simplified implementation. In production, you might want to:
        1. Use Google Custom Search API
        2. Use a proxy service
        3. Implement more sophisticated scraping
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    "https://www.google.com/search",
                    params={"q": query, "num": 5},
                    headers={"User-Agent": self.user_agent},
                    follow_redirects=True
                )

                if response.status_code != 200:
                    logger.warning(f"Google search returned {response.status_code}")
                    return LinkedInCompanyResult(
                        company=None,
                        status="error",
                        error_message=f"Google search failed: HTTP {response.status_code}"
                    )

                # Parse HTML to extract LinkedIn URLs
                soup = BeautifulSoup(response.text, 'html.parser')

                # Find all links in search results
                linkedin_urls = []
                for link in soup.find_all('a', href=True):
                    href = link['href']

                    # Google wraps URLs in /url?q=... format
                    if '/url?q=' in href:
                        # Extract actual URL
                        match = re.search(r'/url\?q=(https?://[^&]+)', href)
                        if match:
                            url = match.group(1)
                            if 'linkedin.com/company/' in url:
                                linkedin_urls.append(url)
                    elif 'linkedin.com/company/' in href:
                        linkedin_urls.append(href)

                if not linkedin_urls:
                    return LinkedInCompanyResult(
                        company=None,
                        status="not_found",
                        error_message="No LinkedIn company page found"
                    )

                # Use first result
                linkedin_url = linkedin_urls[0]

                # Clean URL (remove query params)
                linkedin_url = linkedin_url.split('?')[0].rstrip('/')

                # Extract company ID
                company_id = self._extract_company_id(linkedin_url)

                return LinkedInCompanyResult(
                    company=LinkedInCompany(
                        name=company_name,
                        linkedin_url=linkedin_url,
                        company_id=company_id
                    ),
                    status="success"
                )

        except httpx.TimeoutException:
            logger.error("Google search timeout")
            return LinkedInCompanyResult(
                company=None,
                status="error",
                error_message="Request timeout"
            )
        except Exception as e:
            logger.error(f"Google search error: {e}")
            return LinkedInCompanyResult(
                company=None,
                status="error",
                error_message=str(e)
            )

    def _extract_company_id(self, linkedin_url: str) -> str:
        """Extract company ID from LinkedIn URL"""
        # linkedin.com/company/acme-corp -> acme-corp
        # linkedin.com/company/acme-corp/about -> acme-corp
        match = re.search(r'linkedin\.com/company/([^/\?]+)', linkedin_url)
        if match:
            return match.group(1)
        return linkedin_url.rstrip("/").split("/")[-1]


# Singleton
_linkedin_company_service: Optional[LinkedInCompanyService] = None


async def get_linkedin_company_service() -> LinkedInCompanyService:
    """Get or create LinkedIn company service singleton"""
    global _linkedin_company_service
    if _linkedin_company_service is None:
        _linkedin_company_service = LinkedInCompanyService()
    return _linkedin_company_service
