"""URL transform functions for Close CRM URL arrays."""
from typing import Dict, List, Optional


def extract_linkedin_url(urls: List[Dict]) -> Optional[str]:
    """Extract LinkedIn URL from urls array.

    Args:
        urls: Close CRM urls array

    Returns:
        LinkedIn profile URL or None
    """
    if not urls or not isinstance(urls, list):
        return None
    for url in urls:
        if isinstance(url, dict):
            url_str = url.get("url", "")
            if "linkedin.com" in url_str.lower():
                return url_str
    return None


def build_url_array_with_linkedin(
    linkedin_url: str,
    existing: List[Dict] = None
) -> List[Dict]:
    """Build URL array including LinkedIn for Close API.

    Args:
        linkedin_url: LinkedIn profile URL
        existing: Existing URLs array to merge with

    Returns:
        Close CRM urls array with LinkedIn added/updated
    """
    result = existing or []
    if linkedin_url:
        # Remove any existing LinkedIn URL
        result = [u for u in result if "linkedin.com" not in u.get("url", "").lower()]
        result.append({"url": linkedin_url, "type": "linkedin"})
    return result
