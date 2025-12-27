"""Core activity fields: identity, type, direction, timestamps."""
from typing import List
from ..schemas import FieldMapping, DataType, FieldDirection
from ..transforms import parse_iso_datetime, normalize_activity_type


def get_activity_core_fields() -> List[FieldMapping]:
    """Get core activity fields: identity, type, timestamps."""
    return [
        # Core Identity
        FieldMapping(
            close_field="id", supabase_column="close_activity_id",
            data_type=DataType.STRING, direction=FieldDirection.CLOSE_TO_SUPABASE,
            required=True, nullable=False, description="Close Activity ID"
        ),
        FieldMapping(
            close_field="lead_id", supabase_column="close_lead_id",
            data_type=DataType.STRING, required=True, description="Parent lead ID"
        ),
        FieldMapping(
            close_field="contact_id", supabase_column="close_contact_id",
            data_type=DataType.STRING, description="Associated contact ID"
        ),
        FieldMapping(
            close_field="user_id", supabase_column="close_user_id",
            data_type=DataType.STRING, description="User who performed activity"
        ),
        # Activity Type
        FieldMapping(
            close_field="_type", supabase_column="activity_type",
            data_type=DataType.STRING, transform_to_supabase=normalize_activity_type,
            required=True, description="Activity type (Email, SMS, Call, etc.)"
        ),
        FieldMapping(
            close_field="direction", supabase_column="direction",
            data_type=DataType.STRING, description="Direction (inbound/outbound)"
        ),
        # Timestamps
        FieldMapping(
            close_field="date_created", supabase_column="date_created",
            data_type=DataType.DATETIME, direction=FieldDirection.CLOSE_TO_SUPABASE,
            required=True, transform_to_supabase=parse_iso_datetime,
            description="When activity was created"
        ),
        FieldMapping(
            close_field="date_updated", supabase_column="date_updated",
            data_type=DataType.DATETIME, direction=FieldDirection.CLOSE_TO_SUPABASE,
            transform_to_supabase=parse_iso_datetime,
            description="When activity was last updated"
        ),
        FieldMapping(
            close_field="date_sent", supabase_column="date_sent",
            data_type=DataType.DATETIME, transform_to_supabase=parse_iso_datetime,
            description="When email/SMS was sent"
        ),
        FieldMapping(
            close_field="date_scheduled", supabase_column="date_scheduled",
            data_type=DataType.DATETIME, transform_to_supabase=parse_iso_datetime,
            description="Scheduled send time"
        ),
        FieldMapping(
            close_field="activity_at", supabase_column="activity_at",
            data_type=DataType.DATETIME, transform_to_supabase=parse_iso_datetime,
            description="When activity occurred"
        ),
    ]
