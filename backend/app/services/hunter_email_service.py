"""
Hunter.io Email Discovery Service

Finds email addresses for ATL contacts at a company by domain.
Uses Hunter.io Domain Search API to discover contact emails.

Performance: ~500ms per domain search
Cost: $0.0001 per search (free tier: 50 searches/month)
"""

from typing import List, Optional
import httpx
from pydantic import BaseModel, EmailStr
import os
import logging

logger = logging.getLogger(__name__)


class HunterContact(BaseModel):
    """Single contact from Hunter.io"""
    email: EmailStr
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    position: Optional[str] = None  # Job title
    department: Optional[str] = None
    confidence: int  # 0-100 confidence score
    source: str = "hunter"


class HunterResult(BaseModel):
    """Result from Hunter.io domain search"""
    domain: str
    contacts: List[HunterContact]
    total_emails: int
    status: str  # "success" | "error" | "rate_limited"
    error_message: Optional[str] = None


class HunterEmailService:
    """Hunter.io email discovery service"""

    # ATL title keywords for filtering
    ATL_KEYWORDS = [
        "ceo", "chief executive",
        "cto", "chief technology",
        "cfo", "chief financial",
        "coo", "chief operating",
        "president", "vp", "vice president",
        "founder", "co-founder", "owner",
        "director", "head of",
        "partner", "managing director"
    ]

    def __init__(self):
        self.api_key = os.getenv("HUNTER_API_KEY")
        self.base_url = "https://api.hunter.io/v2"
        self.timeout = 5.0

        if not self.api_key:
            logger.warning("HUNTER_API_KEY not set - Hunter.io service will return empty results")

    async def find_emails(
        self,
        domain: str,
        atl_only: bool = True
    ) -> HunterResult:
        """
        Find emails at a domain using Hunter.io

        Args:
            domain: Company domain (e.g., "acsfixit.com")
            atl_only: Filter for ATL titles only (CEO, CTO, VP, etc.)

        Returns:
            HunterResult with discovered contacts
        """
        # Clean domain
        domain = domain.replace("https://", "").replace("http://", "").split("/")[0]

        # Check API key
        if not self.api_key:
            logger.warning("Hunter.io API key not configured")
            return HunterResult(
                domain=domain,
                contacts=[],
                total_emails=0,
                status="error",
                error_message="HUNTER_API_KEY not configured"
            )

        try:
            logger.info(f"Starting Hunter.io domain search for: {domain}")

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/domain-search",
                    params={
                        "domain": domain,
                        "api_key": self.api_key,
                        "limit": 50,  # Max contacts to return
                        "type": "personal"  # Personal emails only
                    }
                )

                # Handle rate limiting
                if response.status_code == 429:
                    logger.warning(f"Hunter.io rate limit hit for {domain}")
                    return HunterResult(
                        domain=domain,
                        contacts=[],
                        total_emails=0,
                        status="rate_limited",
                        error_message="Hunter.io API rate limit exceeded"
                    )

                # Handle other errors
                if response.status_code != 200:
                    logger.error(f"Hunter.io API error: {response.status_code}")
                    return HunterResult(
                        domain=domain,
                        contacts=[],
                        total_emails=0,
                        status="error",
                        error_message=f"HTTP {response.status_code}"
                    )

                data = response.json()

                # Parse contacts
                contacts = []
                emails_data = data.get("data", {}).get("emails", [])

                for email_data in emails_data:
                    position = email_data.get("position", "")

                    # Filter for ATL titles if requested
                    if atl_only and not self._is_atl_title(position):
                        continue

                    contacts.append(HunterContact(
                        email=email_data["value"],
                        first_name=email_data.get("first_name"),
                        last_name=email_data.get("last_name"),
                        position=position,
                        department=email_data.get("department"),
                        confidence=email_data.get("confidence", 0)
                    ))

                logger.info(
                    f"Hunter.io found {len(contacts)} ATL contacts at {domain} "
                    f"(total: {len(emails_data)})"
                )

                return HunterResult(
                    domain=domain,
                    contacts=contacts,
                    total_emails=len(contacts),
                    status="success"
                )

        except httpx.TimeoutException:
            logger.error(f"Hunter.io timeout for {domain}")
            return HunterResult(
                domain=domain,
                contacts=[],
                total_emails=0,
                status="error",
                error_message="Request timeout"
            )
        except Exception as e:
            logger.error(f"Hunter.io error for {domain}: {e}")
            return HunterResult(
                domain=domain,
                contacts=[],
                total_emails=0,
                status="error",
                error_message=str(e)
            )

    def _is_atl_title(self, title: str) -> bool:
        """Check if title is Above The Line"""
        if not title:
            return False

        title_lower = title.lower()
        return any(keyword in title_lower for keyword in self.ATL_KEYWORDS)


# Singleton pattern
_hunter_service: Optional[HunterEmailService] = None


async def get_hunter_service() -> HunterEmailService:
    """Get or create Hunter.io service singleton"""
    global _hunter_service
    if _hunter_service is None:
        _hunter_service = HunterEmailService()
    return _hunter_service
