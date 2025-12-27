"""Datetime transform functions for field conversions."""
from datetime import datetime
from typing import Any, Optional


def parse_iso_datetime(value: Any) -> Optional[datetime]:
    """Parse ISO datetime string to datetime object.

    Args:
        value: ISO datetime string or datetime object

    Returns:
        datetime object or None if invalid
    """
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None
