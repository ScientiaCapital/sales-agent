"""
Outreach Staging Options

Defines staging modes and outreach channel selection for CLI enrichment.
"""

from enum import Enum
from typing import List, Literal
from pydantic import BaseModel


class StagingMode(str, Enum):
    """Outreach staging modes."""
    DRAFT = "draft"           # Create draft, wait for approval
    AUTO_APPROVE = "auto"     # Send immediately (use with caution)
    REVIEW_FIRST = "review"   # Stage + open in dashboard for review


class OutreachChannel(str, Enum):
    """Available outreach channels."""
    EMAIL = "email"
    SMS = "sms"
    LINKEDIN = "linkedin"
    CALL = "call"
    VOICE = "voice"  # Future: automated voice AI


class OutreachRequest(BaseModel):
    """Outreach staging request model."""
    lead_id: str
    channels: List[Literal["email", "sms", "linkedin", "call", "voice"]]
    mode: StagingMode = StagingMode.DRAFT
    priority: Literal["now", "morning", "scheduled"] = "morning"


def parse_channels(channel_str: str) -> List[str]:
    """
    Parse comma-separated channel string into list.

    Args:
        channel_str: Comma-separated channels like "email,sms,linkedin"

    Returns:
        List of channel names

    Examples:
        >>> parse_channels("email,sms")
        ['email', 'sms']
        >>> parse_channels("all")
        ['email', 'sms', 'linkedin', 'call']
    """
    if not channel_str:
        return []

    channel_str = channel_str.lower().strip()

    # Handle "all" special case
    if channel_str == "all":
        return [OutreachChannel.EMAIL.value, OutreachChannel.SMS.value,
                OutreachChannel.LINKEDIN.value, OutreachChannel.CALL.value]

    # Split and validate channels
    channels = [ch.strip() for ch in channel_str.split(",")]
    valid_channels = [ch for ch in channels if ch in [c.value for c in OutreachChannel]]

    return valid_channels


def validate_staging_request(request: OutreachRequest) -> bool:
    """
    Validate outreach staging request.

    Args:
        request: OutreachRequest to validate

    Returns:
        True if valid, raises ValueError if not
    """
    if not request.lead_id:
        raise ValueError("lead_id is required")

    if not request.channels:
        raise ValueError("At least one channel must be specified")

    # Validate channels
    valid_channel_values = [c.value for c in OutreachChannel]
    for channel in request.channels:
        if channel not in valid_channel_values:
            raise ValueError(f"Invalid channel: {channel}")

    return True
