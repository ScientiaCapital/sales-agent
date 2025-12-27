"""Activity-related transform functions."""
from typing import Optional


def normalize_activity_type(value: str) -> str:
    """Normalize Close activity type to standard types.

    Args:
        value: Close CRM activity _type value

    Returns:
        Normalized lowercase activity type
    """
    type_map = {
        "Email": "email",
        "SMS": "sms",
        "Call": "call",
        "Meeting": "meeting",
        "Note": "note",
        "Task": "task",
        "LeadStatusChange": "lead_status_change",
        "Created": "created",
        "OpportunityStatusChange": "opportunity_status_change",
    }
    return type_map.get(value, value.lower())


def clean_name(value: str) -> Optional[str]:
    """Clean and normalize name string.

    Args:
        value: Raw name string

    Returns:
        Trimmed name or None if empty
    """
    if not value:
        return None
    return value.strip()
