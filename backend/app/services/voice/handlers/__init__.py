"""Voice intent handlers for sales conversations.

Handlers process specific sales intents and generate TTS-friendly responses.
"""

from .lead_handler import LeadQualificationHandler
from .meeting_handler import MeetingSchedulerHandler
from .transfer_handler import TransferHandler
from .base import HandlerResponse

__all__ = [
    "LeadQualificationHandler",
    "MeetingSchedulerHandler",
    "TransferHandler",
    "HandlerResponse",
]
