"""Hunter.io API integration for email discovery"""
import os
import logging
import httpx
from typing import Optional, Dict
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


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

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/email-finder",
                    params=params,
                    timeout=self.timeout
                )

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

        except httpx.TimeoutException:
            logger.warning(f"Hunter.io API timeout for domain {domain}")
            return None
        except Exception as e:
            logger.error(f"Hunter.io API error for domain {domain}: {e}")
            return None
