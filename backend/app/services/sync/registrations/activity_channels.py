"""Activity fields for communication channels: email, SMS, call, meeting, note."""
from typing import List
from ..schemas import FieldMapping, DataType, FieldDirection
from ..transforms import parse_iso_datetime


def get_email_fields() -> List[FieldMapping]:
    """Get email-specific activity fields."""
    return [
        FieldMapping(
            close_field="status", supabase_column="email_status",
            data_type=DataType.STRING, description="Email status"
        ),
        FieldMapping(
            close_field="subject", supabase_column="email_subject",
            data_type=DataType.STRING, description="Email subject line"
        ),
        FieldMapping(
            close_field="body_text", supabase_column="email_body_text",
            data_type=DataType.STRING, description="Plain text email body"
        ),
        FieldMapping(
            close_field="body_html", supabase_column="email_body_html",
            data_type=DataType.STRING, description="HTML email body"
        ),
        FieldMapping(
            close_field="sender", supabase_column="email_sender",
            data_type=DataType.EMAIL, description="Email sender address"
        ),
        FieldMapping(
            close_field="to", supabase_column="email_recipients",
            data_type=DataType.JSON, description="Email recipients (TO)"
        ),
        FieldMapping(
            close_field="cc", supabase_column="email_cc",
            data_type=DataType.JSON, description="Email CC recipients"
        ),
        FieldMapping(
            close_field="bcc", supabase_column="email_bcc",
            data_type=DataType.JSON, description="Email BCC recipients"
        ),
        FieldMapping(
            close_field="opens", supabase_column="email_opens",
            data_type=DataType.INTEGER, description="Number of email opens"
        ),
        FieldMapping(
            close_field="clicks", supabase_column="email_clicks",
            data_type=DataType.INTEGER, description="Number of link clicks"
        ),
        FieldMapping(
            close_field="envelope", supabase_column="email_envelope",
            data_type=DataType.JSON, direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="Email envelope metadata"
        ),
        FieldMapping(
            close_field="template_id", supabase_column="email_template_id",
            data_type=DataType.STRING, description="Email template used"
        ),
        FieldMapping(
            close_field="attachments", supabase_column="email_attachments",
            data_type=DataType.JSON, description="Email attachments metadata"
        ),
    ]


def get_sms_fields() -> List[FieldMapping]:
    """Get SMS-specific activity fields."""
    return [
        FieldMapping(
            close_field="text", supabase_column="sms_text",
            data_type=DataType.STRING, description="SMS message text"
        ),
        FieldMapping(
            close_field="sms_status", supabase_column="sms_status",
            data_type=DataType.STRING, description="SMS delivery status"
        ),
        FieldMapping(
            close_field="remote_phone", supabase_column="sms_phone_to",
            data_type=DataType.PHONE, description="SMS recipient phone"
        ),
        FieldMapping(
            close_field="local_phone", supabase_column="sms_phone_from",
            data_type=DataType.PHONE, description="SMS sender phone"
        ),
        FieldMapping(
            close_field="sms_attachments", supabase_column="sms_attachments",
            data_type=DataType.JSON, description="SMS attachments (MMS)"
        ),
    ]


def get_call_fields() -> List[FieldMapping]:
    """Get call-specific activity fields."""
    return [
        FieldMapping(
            close_field="duration", supabase_column="call_duration_seconds",
            data_type=DataType.INTEGER, description="Call duration in seconds"
        ),
        FieldMapping(
            close_field="disposition", supabase_column="call_disposition",
            data_type=DataType.STRING, description="Call outcome"
        ),
        FieldMapping(
            close_field="remote_phone", supabase_column="call_phone_to",
            data_type=DataType.PHONE, description="Call recipient phone"
        ),
        FieldMapping(
            close_field="local_phone", supabase_column="call_phone_from",
            data_type=DataType.PHONE, description="Call sender phone"
        ),
        FieldMapping(
            close_field="recording_url", supabase_column="call_recording_url",
            data_type=DataType.URL, description="Call recording URL"
        ),
        FieldMapping(
            close_field="voicemail_url", supabase_column="call_voicemail_url",
            data_type=DataType.URL, description="Voicemail recording URL"
        ),
        FieldMapping(
            close_field="note", supabase_column="call_notes",
            data_type=DataType.STRING, description="Call notes"
        ),
        FieldMapping(
            close_field="transferred_from", supabase_column="call_transferred_from",
            data_type=DataType.STRING, description="Call transferred from user"
        ),
        FieldMapping(
            close_field="transferred_to", supabase_column="call_transferred_to",
            data_type=DataType.STRING, description="Call transferred to user"
        ),
    ]


def get_meeting_fields() -> List[FieldMapping]:
    """Get meeting-specific activity fields."""
    return [
        FieldMapping(
            close_field="title", supabase_column="meeting_title",
            data_type=DataType.STRING, description="Meeting title"
        ),
        FieldMapping(
            close_field="location", supabase_column="meeting_location",
            data_type=DataType.STRING, description="Meeting location"
        ),
        FieldMapping(
            close_field="starts_at", supabase_column="meeting_start_at",
            data_type=DataType.DATETIME, transform_to_supabase=parse_iso_datetime,
            description="Meeting start time"
        ),
        FieldMapping(
            close_field="ends_at", supabase_column="meeting_end_at",
            data_type=DataType.DATETIME, transform_to_supabase=parse_iso_datetime,
            description="Meeting end time"
        ),
        FieldMapping(
            close_field="attendees", supabase_column="meeting_attendees",
            data_type=DataType.JSON, description="Meeting attendees"
        ),
        FieldMapping(
            close_field="calendar_event_link", supabase_column="meeting_calendar_link",
            data_type=DataType.URL, description="Calendar event link"
        ),
    ]


def get_note_fields() -> List[FieldMapping]:
    """Get note-specific activity fields."""
    return [
        FieldMapping(
            close_field="note", supabase_column="note_content",
            data_type=DataType.STRING, description="Note content"
        ),
        FieldMapping(
            close_field="note_html", supabase_column="note_content_html",
            data_type=DataType.STRING, description="Note content (HTML)"
        ),
    ]


def get_sequence_fields() -> List[FieldMapping]:
    """Get sequence-specific activity fields."""
    return [
        FieldMapping(
            close_field="sequence_id", supabase_column="sequence_id",
            data_type=DataType.STRING, description="Sequence ID"
        ),
        FieldMapping(
            close_field="sequence_name", supabase_column="sequence_name",
            data_type=DataType.STRING, description="Sequence name"
        ),
        FieldMapping(
            close_field="sequence_step", supabase_column="sequence_step",
            data_type=DataType.INTEGER, description="Sequence step number"
        ),
        FieldMapping(
            close_field="sequence_subscription_id", supabase_column="sequence_subscription_id",
            data_type=DataType.STRING, description="Sequence subscription ID"
        ),
    ]
