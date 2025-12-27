"""Phone number transform functions for Close CRM phone arrays."""
from typing import Dict, List, Optional


def extract_first_phone(phones: List[Dict]) -> Optional[str]:
    """Extract first phone number from phones array.

    Args:
        phones: Close CRM phones array

    Returns:
        First phone number or None
    """
    if not phones or not isinstance(phones, list):
        return None
    if len(phones) > 0 and isinstance(phones[0], dict):
        return phones[0].get("phone")
    return None


def extract_primary_phone(phones: List[Dict]) -> Optional[str]:
    """Extract primary phone (priority: direct > mobile > office > any).

    Args:
        phones: Close CRM phones array with type annotations

    Returns:
        Best available phone number or None
    """
    if not phones or not isinstance(phones, list):
        return None

    # Priority order for phone types
    for phone_type in ["direct", "mobile", "office"]:
        for phone in phones:
            if isinstance(phone, dict) and phone.get("type") == phone_type:
                return phone.get("phone")

    # Fallback to first available
    if len(phones) > 0 and isinstance(phones[0], dict):
        return phones[0].get("phone")
    return None


def build_phone_array(value: str, phone_type: str = "office") -> List[Dict]:
    """Build phone array for Close API.

    Args:
        value: Phone number string
        phone_type: Type annotation (office, direct, mobile, etc.)

    Returns:
        Close CRM phones array format
    """
    if not value:
        return []
    return [{"phone": value, "type": phone_type}]
