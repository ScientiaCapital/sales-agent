"""Hunter.io API integration for email discovery"""
import os
import logging
import httpx
from typing import Optional, Dict, List
from urllib.parse import urlparse

from app.services.circuit_breaker_registry import get_circuit_breaker
from app.services.circuit_breaker import CircuitBreakerError

logger = logging.getLogger(__name__)


# ATL (Above-The-Line) contact titles - decision makers
ATL_TITLES = [
    "ceo", "chief executive", "president", "owner", "founder", "co-founder",
    "cto", "chief technology", "vp", "vice president", "director",
    "head of", "manager", "partner", "principal"
]


def extract_domain(url: str) -> str:
    """
    Extract domain from URL.

    Examples:
        "https://example.com" -> "example.com"
        "https://example.com/about" -> "example.com"
        "example.com" -> "example.com"

    Args:
        url: URL or domain string

    Returns:
        Extracted domain
    """
    if not url:
        return ""

    # Add protocol if missing (urlparse needs it)
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    parsed = urlparse(url)
    return parsed.netloc or parsed.path


class HunterService:
    """Hunter.io API client for email discovery"""

    def __init__(self):
        self.api_key = os.getenv("HUNTER_API_KEY")
        self.base_url = "https://api.hunter.io/v2"
        self.timeout = 10  # seconds
        self._circuit_breaker = get_circuit_breaker("hunter")

        if not self.api_key:
            logger.warning("HUNTER_API_KEY not set - Hunter.io email discovery disabled")

    async def find_email(
        self,
        domain: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> Optional[Dict]:
        """
        Find email using Hunter.io Email Finder API.

        Args:
            domain: Company domain (e.g., "example.com")
            first_name: Contact first name (optional)
            last_name: Contact last name (optional)

        Returns:
            {
                "email": "john@example.com",
                "score": 95,
                "sources": [...],
                "cost": 0.01
            } or None on failure
        """
        if not self.api_key:
            logger.warning("Hunter.io API key not configured")
            return None

        try:
            params = {
                "domain": domain,
                "api_key": self.api_key
            }

            if first_name:
                params["first_name"] = first_name
            if last_name:
                params["last_name"] = last_name

            async def _make_request():
                async with httpx.AsyncClient() as client:
                    return await client.get(
                        f"{self.base_url}/email-finder",
                        params=params,
                        timeout=self.timeout
                    )

            response = await self._circuit_breaker.call(_make_request)

            if response.status_code == 200:
                data = response.json().get("data", {})
                score = data.get("score", 0)

                # Filter out low-confidence results
                if score <= 70:
                    logger.info(f"Hunter.io returned low confidence email (score: {score})")
                    return None

                return {
                    "email": data.get("email"),
                    "score": score,
                    "sources": data.get("sources", []),
                    "cost": 0.01  # Hunter.io cost per request
                }
            else:
                logger.warning(f"Hunter.io API returned status {response.status_code}")
                return None

        except CircuitBreakerError as e:
            logger.warning(f"Hunter.io circuit breaker open for domain {domain}: {e}")
            return None
        except httpx.TimeoutException:
            logger.warning(f"Hunter.io API timeout for domain {domain}")
            return None
        except Exception as e:
            logger.error(f"Hunter.io API error for domain {domain}: {e}")
            return None

    async def domain_search(
        self,
        domain: str,
        limit: int = 10,
        atl_only: bool = True
    ) -> Optional[List[Dict]]:
        """
        Search for all emails at a company domain using Hunter.io Domain Search API.

        This is the PRIMARY method for discovering contacts - returns ALL employees
        at a company with their job titles, allowing us to filter for ATL contacts.

        Args:
            domain: Company domain (e.g., "example.com")
            limit: Max number of results to return (default: 10)
            atl_only: Only return ATL (decision-maker) contacts (default: True)

        Returns:
            List of contacts:
            [
                {
                    "email": "john@example.com",
                    "first_name": "John",
                    "last_name": "Smith",
                    "position": "CEO",
                    "confidence": 95,
                    "is_atl": True
                },
                ...
            ] or None on failure
        """
        if not self.api_key:
            logger.warning("Hunter.io API key not configured")
            return None

        # Clean domain - remove www., https://, http://, trailing slashes
        clean_domain = domain.replace("https://", "").replace("http://", "")
        clean_domain = clean_domain.replace("www.", "").rstrip("/").split("/")[0]

        try:
            params = {
                "domain": clean_domain,
                "api_key": self.api_key,
                "limit": limit
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/domain-search",
                    params=params,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    emails = data.get("emails", [])

                    # Transform to our format
                    contacts = []
                    for email_data in emails:
                        # Handle None position (Hunter.io can return null)
                        position = (email_data.get("position") or "").lower()

                        # Check if ATL contact
                        is_atl = any(title in position for title in ATL_TITLES)

                        # Skip if atl_only=True and not ATL
                        if atl_only and not is_atl:
                            continue

                        contacts.append({
                            "email": email_data.get("value"),  # Hunter.io uses "value" for email
                            "first_name": email_data.get("first_name"),
                            "last_name": email_data.get("last_name"),
                            "position": email_data.get("position"),
                            "phone_number": email_data.get("phone_number"),  # Direct phone from Hunter
                            "confidence": email_data.get("confidence", 0),
                            "is_atl": is_atl,
                            "linkedin": email_data.get("linkedin"),
                            "twitter": email_data.get("twitter"),
                            "seniority": email_data.get("seniority"),  # junior/senior/executive
                            "department": email_data.get("department"),  # sales/marketing/etc
                            "email_type": email_data.get("type"),  # personal vs generic
                            "verification": email_data.get("verification"),  # verification status
                        })

                    logger.info(
                        f"Hunter.io domain search for {domain}: "
                        f"found {len(contacts)} contacts "
                        f"({'ATL only' if atl_only else 'all'})"
                    )

                    return contacts if contacts else None

                elif response.status_code == 429:
                    logger.warning("Hunter.io API rate limit exceeded")
                    return None
                else:
                    logger.warning(
                        f"Hunter.io domain search returned status {response.status_code}"
                    )
                    return None

        except httpx.TimeoutException:
            logger.warning(f"Hunter.io domain search timeout for {domain}")
            return None
        except Exception as e:
            logger.error(f"Hunter.io domain search error for {domain}: {e}")
            return None

    async def verify_email(self, email: str) -> Optional[Dict]:
        """
        Verify email deliverability using Hunter.io Email Verifier API.

        This is the fallback verification method to ensure email quality
        before outreach. Returns verification status and confidence score.

        Args:
            email: Email address to verify (e.g., "john@example.com")

        Returns:
            {
                "email": "john@example.com",
                "status": "valid",  # valid, invalid, accept_all, unknown
                "score": 100,
                "is_deliverable": True,
                "is_disposable": False,
                "is_webmail": False,
                "cost": 0.01
            } or None on failure
        """
        if not self.api_key:
            logger.warning("Hunter.io API key not configured")
            return None

        if not email or "@" not in email:
            logger.warning(f"Invalid email format for verification: {email}")
            return None

        try:
            params = {
                "email": email,
                "api_key": self.api_key
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/email-verifier",
                    params=params,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    status = data.get("status", "unknown")
                    score = data.get("score", 0)

                    # Determine deliverability
                    is_deliverable = status == "valid" or (
                        status == "accept_all" and score >= 70
                    )

                    logger.info(
                        f"Hunter.io verified {email}: "
                        f"status={status}, score={score}, deliverable={is_deliverable}"
                    )

                    return {
                        "email": email,
                        "status": status,
                        "score": score,
                        "is_deliverable": is_deliverable,
                        "is_disposable": data.get("disposable", False),
                        "is_webmail": data.get("webmail", False),
                        "mx_records": data.get("mx_records", False),
                        "smtp_check": data.get("smtp_check", False),
                        "cost": 0.01  # Hunter.io cost per verification
                    }
                elif response.status_code == 202:
                    # Verification still in progress - retry later
                    logger.info(f"Hunter.io verification in progress for {email}")
                    return None
                elif response.status_code == 429:
                    logger.warning("Hunter.io API rate limit exceeded for verification")
                    return None
                else:
                    logger.warning(
                        f"Hunter.io email verification returned status {response.status_code}"
                    )
                    return None

        except httpx.TimeoutException:
            logger.warning(f"Hunter.io email verification timeout for {email}")
            return None
        except Exception as e:
            logger.error(f"Hunter.io email verification error for {email}: {e}")
            return None

    async def get_email_count(self, domain: str) -> Optional[Dict]:
        """
        Get email count for a domain using Hunter.io Email Count API.

        This is a FREE endpoint (no credits) to check if Hunter.io has
        emails for a domain before making paid API calls.

        Args:
            domain: Company domain (e.g., "example.com")

        Returns:
            {
                "total": 81,
                "personal_emails": 65,
                "generic_emails": 16,
                "has_data": True
            } or None on failure
        """
        if not self.api_key:
            logger.warning("Hunter.io API key not configured")
            return None

        # Clean domain
        clean_domain = domain.replace("https://", "").replace("http://", "")
        clean_domain = clean_domain.replace("www.", "").rstrip("/").split("/")[0]

        try:
            params = {
                "domain": clean_domain,
                "api_key": self.api_key
            }

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/email-count",
                    params=params,
                    timeout=self.timeout
                )

                if response.status_code == 200:
                    data = response.json().get("data", {})
                    total = data.get("total", 0)

                    return {
                        "total": total,
                        "personal_emails": data.get("personal_emails", 0),
                        "generic_emails": data.get("generic_emails", 0),
                        "has_data": total > 0
                    }
                else:
                    logger.warning(
                        f"Hunter.io email count returned status {response.status_code}"
                    )
                    return None

        except httpx.TimeoutException:
            logger.warning(f"Hunter.io email count timeout for {domain}")
            return None
        except Exception as e:
            logger.error(f"Hunter.io email count error for {domain}: {e}")
            return None
