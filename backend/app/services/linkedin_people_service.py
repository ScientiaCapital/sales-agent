"""
LinkedIn People Search Service

Finds ATL contacts at a company on LinkedIn.
Searches by company and filters for executive titles.

Performance: ~1500ms per search
Strategy: Google search "site:linkedin.com/in {ATL_title} at {company}"
"""

from typing import List, Optional
import httpx
from pydantic import BaseModel
import logging
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class LinkedInPerson(BaseModel):
    """LinkedIn person profile"""
    name: str
    linkedin_url: str  # Using str for flexibility
    title: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None  # If available
    is_atl: bool = True  # Pre-filtered for ATL
    source: str = "linkedin"


class LinkedInPeopleResult(BaseModel):
    """Result from LinkedIn people search"""
    people: List[LinkedInPerson]
    company_name: str
    total_found: int
    status: str  # "success" | "error"
    error_message: Optional[str] = None


class LinkedInPeopleService:
    """LinkedIn people search service"""

    ATL_TITLES = [
        "CEO", "Chief Executive Officer",
        "CTO", "Chief Technology Officer",
        "CFO", "Chief Financial Officer",
        "COO", "Chief Operating Officer",
        "President", "Vice President", "VP",
        "Founder", "Co-Founder",
        "Owner", "Managing Director",
        "Head of", "Director",
        "Partner"
    ]

    def __init__(self):
        self.timeout = 15.0
        self.user_agent = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

    async def find_atl_contacts(
        self,
        company_linkedin_url: str,
        company_name: str,
        limit: int = 10
    ) -> LinkedInPeopleResult:
        """
        Find ATL contacts at company

        Args:
            company_linkedin_url: LinkedIn company page URL
            company_name: Company name for search
            limit: Max contacts to return

        Returns:
            LinkedInPeopleResult with ATL contacts
        """
        try:
            logger.info(f"Searching for ATL contacts at: {company_name}")

            # Extract company ID from URL
            company_id = self._extract_company_id(company_linkedin_url)

            # Search for people at company with ATL titles
            people = await self._search_people(company_id, company_name, limit)

            logger.info(f"Found {len(people)} ATL contacts at {company_name}")

            return LinkedInPeopleResult(
                people=people,
                company_name=company_name,
                total_found=len(people),
                status="success"
            )

        except Exception as e:
            logger.error(f"LinkedIn people search failed: {e}")
            return LinkedInPeopleResult(
                people=[],
                company_name=company_name,
                total_found=0,
                status="error",
                error_message=str(e)
            )

    async def _search_people(
        self,
        company_id: str,
        company_name: str,
        limit: int
    ) -> List[LinkedInPerson]:
        """
        Search for people at company using Google

        Strategy: Google search for each ATL title at company
        Example: site:linkedin.com/in "CEO at {company_name}"
        """
        all_people = []
        seen_urls = set()

        # Search for top 3 ATL titles
        priority_titles = ["CEO", "President", "Founder"]

        for title in priority_titles:
            if len(all_people) >= limit:
                break

            logger.info(f"Searching for {title} at {company_name}")

            # Google search query
            query = f'site:linkedin.com/in "{title} at {company_name}"'

            people = await self._google_search_people(query, company_name, title)

            # Add people, avoiding duplicates
            for person in people:
                if person.linkedin_url not in seen_urls:
                    all_people.append(person)
                    seen_urls.add(person.linkedin_url)

                    if len(all_people) >= limit:
                        break

        return all_people[:limit]

    async def _google_search_people(
        self,
        query: str,
        company_name: str,
        expected_title: str
    ) -> List[LinkedInPerson]:
        """
        Perform Google search for LinkedIn profiles

        Returns list of LinkedInPerson objects
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
                    return []

                # Parse HTML to extract LinkedIn profile URLs
                soup = BeautifulSoup(response.text, 'html.parser')

                people = []
                for link in soup.find_all('a', href=True):
                    href = link['href']

                    # Extract LinkedIn profile URL
                    linkedin_url = None
                    if '/url?q=' in href:
                        match = re.search(r'/url\?q=(https?://[^&]+)', href)
                        if match:
                            url = match.group(1)
                            if 'linkedin.com/in/' in url:
                                linkedin_url = url
                    elif 'linkedin.com/in/' in href:
                        linkedin_url = href

                    if linkedin_url:
                        # Clean URL
                        linkedin_url = linkedin_url.split('?')[0].rstrip('/')

                        # Extract name from URL or link text
                        name = self._extract_name(linkedin_url, link.get_text())

                        people.append(LinkedInPerson(
                            name=name,
                            linkedin_url=linkedin_url,
                            title=expected_title,
                            company=company_name,
                            email=None  # Not available from Google search
                        ))

                return people

        except httpx.TimeoutException:
            logger.warning("Google search timeout for LinkedIn people")
            return []
        except Exception as e:
            logger.error(f"Google search error: {e}")
            return []

    def _extract_company_id(self, linkedin_url: str) -> str:
        """Extract company ID from LinkedIn URL"""
        # linkedin.com/company/acme-corp -> acme-corp
        match = re.search(r'linkedin\.com/company/([^/\?]+)', linkedin_url)
        if match:
            return match.group(1)
        return linkedin_url.rstrip("/").split("/")[-1]

    def _extract_name(self, linkedin_url: str, link_text: str) -> str:
        """
        Extract person name from LinkedIn URL or link text

        Examples:
        - linkedin.com/in/john-smith -> John Smith
        - link text: "John Smith - CEO at Company"
        """
        # Try to extract from link text first
        if link_text and len(link_text) > 2:
            # Remove common suffixes
            name = re.sub(r'\s*-\s*(CEO|CTO|President|Director|Founder).*', '', link_text)
            name = name.strip()
            if len(name) > 2 and len(name) < 50:
                return name

        # Fallback: Extract from URL
        match = re.search(r'linkedin\.com/in/([^/\?]+)', linkedin_url)
        if match:
            slug = match.group(1)
            # Convert slug to name: john-smith -> John Smith
            name = slug.replace('-', ' ').replace('_', ' ').title()
            return name

        return "Unknown"

    def _is_atl_title(self, title: str) -> bool:
        """Check if title is ATL"""
        if not title:
            return False
        title_lower = title.lower()
        return any(atl.lower() in title_lower for atl in self.ATL_TITLES)


# Singleton
_linkedin_people_service: Optional[LinkedInPeopleService] = None


async def get_linkedin_people_service() -> LinkedInPeopleService:
    """Get or create LinkedIn people service singleton"""
    global _linkedin_people_service
    if _linkedin_people_service is None:
        _linkedin_people_service = LinkedInPeopleService()
    return _linkedin_people_service
