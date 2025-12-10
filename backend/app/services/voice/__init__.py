"""Voice services for sales agent."""

from .intent_classifier import SalesIntent, SalesIntentClassifier
from .voicemail_service import (
    VoicemailDropService,
    VMPreset,
    VMDropResult,
    VMDropStatus,
    AMDResult,
)
from .sms_handler import (
    SMSFollowupHandler,
    SMSFollowupResult,
    CallOutcome,
    SMSTemplate,
)
from .outreach_staging import (
    OutreachStagingService,
    StagedAction,
    StagedActionType,
    StagedActionStatus,
    VMTranscription,
    ResponseOptions,
)

__all__ = [
    # Intent classification
    "SalesIntent",
    "SalesIntentClassifier",
    # Voicemail drops
    "VoicemailDropService",
    "VMPreset",
    "VMDropResult",
    "VMDropStatus",
    "AMDResult",
    # SMS follow-ups
    "SMSFollowupHandler",
    "SMSFollowupResult",
    "CallOutcome",
    "SMSTemplate",
    # Human-in-the-loop staging
    "OutreachStagingService",
    "StagedAction",
    "StagedActionType",
    "StagedActionStatus",
    "VMTranscription",
    "ResponseOptions",
]
