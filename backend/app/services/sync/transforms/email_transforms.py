"""Email transform functions for Close CRM email arrays."""
from typing import Dict, List, Optional


def extract_primary_email(emails: List[Dict]) -> Optional[str]:
    """Extract primary email from emails array.

    Args:
        emails: Close CRM emails array

    Returns:
        First email address or None
    """
    if not emails or not isinstance(emails, list):
        return None
    if len(emails) > 0 and isinstance(emails[0], dict):
        return emails[0].get("email")
    return None


def build_email_array(value: str, email_type: str = "office") -> List[Dict]:
    """Build email array for Close API.

    Args:
        value: Email address string
        email_type: Type annotation (office, direct, personal, etc.)

    Returns:
        Close CRM emails array format
    """
    if not value:
        return []
    return [{"email": value, "type": email_type}]
