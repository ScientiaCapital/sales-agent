"""Activity field mappings: Close Activities → fact_close_activities."""
from typing import List
from ..schemas import FieldMapping
from .activity_core import get_activity_core_fields
from .activity_channels import (
    get_email_fields, get_sms_fields, get_call_fields,
    get_meeting_fields, get_note_fields, get_sequence_fields,
)


def get_activity_fields() -> List[FieldMapping]:
    """Get all Close Activity → Supabase fact_close_activities field mappings."""
    fields = []
    fields.extend(get_activity_core_fields())
    fields.extend(get_email_fields())
    fields.extend(get_sms_fields())
    fields.extend(get_call_fields())
    fields.extend(get_meeting_fields())
    fields.extend(get_note_fields())
    fields.extend(get_sequence_fields())
    return fields
