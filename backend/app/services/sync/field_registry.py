"""
Field Registry: Complete Field Parity Mapping
==============================================

Maps ALL Close CRM fields to Supabase columns with:
- Data type validation
- Transform functions
- Bidirectional mapping support
- Custom field handling

Close CRM API Reference: https://developer.close.com/resources/
"""

from typing import Any, Callable, Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class FieldDirection(Enum):
    """Direction of field sync"""
    BIDIRECTIONAL = "bidirectional"  # Sync both ways
    CLOSE_TO_SUPABASE = "close_to_supabase"  # Read-only from Close
    SUPABASE_TO_CLOSE = "supabase_to_close"  # Write-only to Close
    NONE = "none"  # Don't sync


class DataType(Enum):
    """Supported data types"""
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    JSON = "json"
    ARRAY = "array"
    EMAIL = "email"
    PHONE = "phone"
    URL = "url"
    UUID = "uuid"


@dataclass
class FieldMapping:
    """Complete field mapping definition"""
    close_field: str                    # Close CRM field name (e.g., "name", "custom.cf_xxx")
    supabase_column: str                # Supabase column name
    data_type: DataType
    direction: FieldDirection = FieldDirection.BIDIRECTIONAL
    required: bool = False              # Is this field required?
    nullable: bool = True               # Can this field be null?
    default_value: Any = None           # Default if missing
    transform_to_supabase: Optional[Callable] = None  # Transform Close → Supabase
    transform_to_close: Optional[Callable] = None     # Transform Supabase → Close
    validation_fn: Optional[Callable] = None          # Custom validation
    description: str = ""
    # Conflict resolution
    conflict_strategy: str = "newer_wins"  # newer_wins, close_wins, supabase_wins, manual


@dataclass
class EntityMapping:
    """Mapping for a complete entity (Lead, Contact, Activity)"""
    entity_name: str                    # "lead", "contact", "activity"
    close_endpoint: str                 # Close API endpoint
    supabase_table: str                 # Supabase table name
    id_field_close: str = "id"          # Close CRM ID field
    id_field_supabase: str = "company_id"  # Supabase ID field
    close_id_column: str = "close_lead_id"  # Supabase column storing Close ID
    fields: List[FieldMapping] = field(default_factory=list)


class FieldRegistry:
    """
    Central registry for all field mappings between Close CRM and Supabase.
    
    Features:
    - Complete field parity validation
    - Bidirectional transform support
    - Custom field registration
    - Validation rules
    - Conflict resolution strategies
    """
    
    def __init__(self):
        self.entities: Dict[str, EntityMapping] = {}
        self._register_all_mappings()
    
    def _register_all_mappings(self):
        """Register all entity mappings"""
        self._register_lead_mappings()
        self._register_contact_mappings()
        self._register_activity_mappings()
        self._register_custom_field_mappings()
    
    # =========================================================================
    # LEAD MAPPINGS (Close Leads → dim_companies)
    # =========================================================================
    
    def _register_lead_mappings(self):
        """Register Close Lead → Supabase dim_companies field mappings"""
        
        lead_fields = [
            # Core Identity Fields
            FieldMapping(
                close_field="id",
                supabase_column="close_lead_id",
                data_type=DataType.STRING,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                required=True,
                nullable=False,
                description="Close CRM Lead ID (lead_xxx)"
            ),
            FieldMapping(
                close_field="name",
                supabase_column="company_name",
                data_type=DataType.STRING,
                required=True,
                nullable=False,
                description="Company/Organization name"
            ),
            FieldMapping(
                close_field="display_name",
                supabase_column="display_name",
                data_type=DataType.STRING,
                description="Display name (may differ from name)"
            ),
            FieldMapping(
                close_field="description",
                supabase_column="description",
                data_type=DataType.STRING,
                description="Lead description/notes"
            ),
            
            # URL/Domain Fields
            FieldMapping(
                close_field="url",
                supabase_column="website",
                data_type=DataType.URL,
                transform_to_supabase=lambda x: x if x else None,
                description="Company website URL"
            ),
            
            # Status Fields
            FieldMapping(
                close_field="status_id",
                supabase_column="close_status_id",
                data_type=DataType.STRING,
                description="Close status ID (stat_xxx)"
            ),
            FieldMapping(
                close_field="status_label",
                supabase_column="close_status_label",
                data_type=DataType.STRING,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="Human-readable status label"
            ),
            
            # Address Fields (from addresses array)
            FieldMapping(
                close_field="addresses[0].address_1",
                supabase_column="street",
                data_type=DataType.STRING,
                transform_to_supabase=self._extract_first_address_field("address_1"),
                transform_to_close=self._build_address_array("address_1"),
                description="Street address line 1"
            ),
            FieldMapping(
                close_field="addresses[0].city",
                supabase_column="city",
                data_type=DataType.STRING,
                transform_to_supabase=self._extract_first_address_field("city"),
                transform_to_close=self._build_address_array("city"),
                description="City"
            ),
            FieldMapping(
                close_field="addresses[0].state",
                supabase_column="state",
                data_type=DataType.STRING,
                transform_to_supabase=self._extract_first_address_field("state"),
                transform_to_close=self._build_address_array("state"),
                description="State/Province"
            ),
            FieldMapping(
                close_field="addresses[0].zipcode",
                supabase_column="zip",
                data_type=DataType.STRING,
                transform_to_supabase=self._extract_first_address_field("zipcode"),
                transform_to_close=self._build_address_array("zipcode"),
                description="ZIP/Postal code"
            ),
            FieldMapping(
                close_field="addresses[0].country",
                supabase_column="country",
                data_type=DataType.STRING,
                transform_to_supabase=self._extract_first_address_field("country"),
                transform_to_close=self._build_address_array("country"),
                description="Country"
            ),
            
            # Phone (from lead-level phone if exists)
            FieldMapping(
                close_field="phones",
                supabase_column="phone",
                data_type=DataType.PHONE,
                transform_to_supabase=self._extract_first_phone,
                transform_to_close=self._build_phone_array,
                description="Primary company phone"
            ),
            
            # User Assignment
            FieldMapping(
                close_field="created_by",
                supabase_column="close_created_by_id",
                data_type=DataType.STRING,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="Close user who created the lead"
            ),
            FieldMapping(
                close_field="updated_by",
                supabase_column="close_updated_by_id", 
                data_type=DataType.STRING,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="Close user who last updated the lead"
            ),
            
            # Timestamps
            FieldMapping(
                close_field="date_created",
                supabase_column="close_created_at",
                data_type=DataType.DATETIME,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                transform_to_supabase=self._parse_iso_datetime,
                description="When lead was created in Close"
            ),
            FieldMapping(
                close_field="date_updated",
                supabase_column="close_updated_at",
                data_type=DataType.DATETIME,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                transform_to_supabase=self._parse_iso_datetime,
                description="When lead was last updated in Close"
            ),
            
            # Opportunities aggregate
            FieldMapping(
                close_field="opportunities",
                supabase_column="opportunities_json",
                data_type=DataType.JSON,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="Array of opportunities on this lead"
            ),
            
            # Tasks aggregate
            FieldMapping(
                close_field="tasks",
                supabase_column="tasks_json",
                data_type=DataType.JSON,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="Array of tasks on this lead"
            ),
            
            # HTML URL (for linking)
            FieldMapping(
                close_field="html_url",
                supabase_column="close_html_url",
                data_type=DataType.URL,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="Direct link to lead in Close UI"
            ),
            
            # Integration Links
            FieldMapping(
                close_field="integration_links",
                supabase_column="integration_links",
                data_type=DataType.JSON,
                description="External integration links"
            ),
        ]
        
        self.entities["lead"] = EntityMapping(
            entity_name="lead",
            close_endpoint="/lead/",
            supabase_table="dim_companies",
            id_field_close="id",
            id_field_supabase="company_id",
            close_id_column="close_lead_id",
            fields=lead_fields
        )
    
    # =========================================================================
    # CONTACT MAPPINGS (Close Contacts → dim_contacts)
    # =========================================================================
    
    def _register_contact_mappings(self):
        """Register Close Contact → Supabase dim_contacts field mappings"""
        
        contact_fields = [
            # Core Identity
            FieldMapping(
                close_field="id",
                supabase_column="close_contact_id",
                data_type=DataType.STRING,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                required=True,
                nullable=False,
                description="Close CRM Contact ID (cont_xxx)"
            ),
            FieldMapping(
                close_field="lead_id",
                supabase_column="close_lead_id",
                data_type=DataType.STRING,
                required=True,
                description="Parent lead ID"
            ),
            FieldMapping(
                close_field="name",
                supabase_column="full_name",
                data_type=DataType.STRING,
                transform_to_supabase=self._clean_name,
                description="Full contact name"
            ),
            
            # Name components
            FieldMapping(
                close_field="first_name",
                supabase_column="first_name",
                data_type=DataType.STRING,
                description="First name"
            ),
            FieldMapping(
                close_field="last_name",
                supabase_column="last_name",
                data_type=DataType.STRING,
                description="Last name"
            ),
            
            # Role
            FieldMapping(
                close_field="title",
                supabase_column="title",
                data_type=DataType.STRING,
                description="Job title"
            ),
            
            # Email (from emails array)
            FieldMapping(
                close_field="emails",
                supabase_column="email",
                data_type=DataType.EMAIL,
                transform_to_supabase=self._extract_primary_email,
                transform_to_close=self._build_email_array,
                description="Primary email address"
            ),
            FieldMapping(
                close_field="emails",
                supabase_column="emails_all",
                data_type=DataType.JSON,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="All email addresses (JSON array)"
            ),
            
            # Phone (from phones array)
            FieldMapping(
                close_field="phones",
                supabase_column="phone",
                data_type=DataType.PHONE,
                transform_to_supabase=self._extract_primary_phone,
                transform_to_close=self._build_phone_array,
                description="Primary phone number"
            ),
            FieldMapping(
                close_field="phones",
                supabase_column="phones_all",
                data_type=DataType.JSON,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="All phone numbers (JSON array)"
            ),
            
            # URLs (from urls array)
            FieldMapping(
                close_field="urls",
                supabase_column="linkedin_url",
                data_type=DataType.URL,
                transform_to_supabase=self._extract_linkedin_url,
                transform_to_close=self._build_url_array_with_linkedin,
                description="LinkedIn profile URL"
            ),
            FieldMapping(
                close_field="urls",
                supabase_column="urls_all",
                data_type=DataType.JSON,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="All URLs (JSON array)"
            ),
            
            # User Assignment
            FieldMapping(
                close_field="created_by",
                supabase_column="close_created_by_id",
                data_type=DataType.STRING,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="User who created contact"
            ),
            FieldMapping(
                close_field="updated_by",
                supabase_column="close_updated_by_id",
                data_type=DataType.STRING,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="User who last updated contact"
            ),
            
            # Timestamps
            FieldMapping(
                close_field="date_created",
                supabase_column="close_created_at",
                data_type=DataType.DATETIME,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                transform_to_supabase=self._parse_iso_datetime,
                description="When contact was created"
            ),
            FieldMapping(
                close_field="date_updated",
                supabase_column="close_updated_at",
                data_type=DataType.DATETIME,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                transform_to_supabase=self._parse_iso_datetime,
                description="When contact was last updated"
            ),
        ]
        
        self.entities["contact"] = EntityMapping(
            entity_name="contact",
            close_endpoint="/contact/",
            supabase_table="dim_contacts",
            id_field_close="id",
            id_field_supabase="contact_id",
            close_id_column="close_contact_id",
            fields=contact_fields
        )
    
    # =========================================================================
    # ACTIVITY MAPPINGS (Close Activities → fact_close_activities)
    # =========================================================================
    
    def _register_activity_mappings(self):
        """Register Close Activity → Supabase fact_close_activities field mappings"""
        
        activity_fields = [
            # Core Identity
            FieldMapping(
                close_field="id",
                supabase_column="close_activity_id",
                data_type=DataType.STRING,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                required=True,
                nullable=False,
                description="Close Activity ID (acti_xxx)"
            ),
            FieldMapping(
                close_field="lead_id",
                supabase_column="close_lead_id",
                data_type=DataType.STRING,
                required=True,
                description="Parent lead ID"
            ),
            FieldMapping(
                close_field="contact_id",
                supabase_column="close_contact_id",
                data_type=DataType.STRING,
                description="Associated contact ID"
            ),
            FieldMapping(
                close_field="user_id",
                supabase_column="close_user_id",
                data_type=DataType.STRING,
                description="User who performed activity"
            ),
            
            # Activity Type
            FieldMapping(
                close_field="_type",
                supabase_column="activity_type",
                data_type=DataType.STRING,
                transform_to_supabase=self._normalize_activity_type,
                required=True,
                description="Activity type (Email, SMS, Call, etc.)"
            ),
            FieldMapping(
                close_field="direction",
                supabase_column="direction",
                data_type=DataType.STRING,
                description="Direction (inbound/outbound)"
            ),
            
            # ===== EMAIL FIELDS =====
            FieldMapping(
                close_field="status",
                supabase_column="email_status",
                data_type=DataType.STRING,
                description="Email status (draft, sent, inbox, etc.)"
            ),
            FieldMapping(
                close_field="subject",
                supabase_column="email_subject",
                data_type=DataType.STRING,
                description="Email subject line"
            ),
            FieldMapping(
                close_field="body_text",
                supabase_column="email_body_text",
                data_type=DataType.STRING,
                description="Plain text email body"
            ),
            FieldMapping(
                close_field="body_html",
                supabase_column="email_body_html",
                data_type=DataType.STRING,
                description="HTML email body"
            ),
            FieldMapping(
                close_field="sender",
                supabase_column="email_sender",
                data_type=DataType.EMAIL,
                description="Email sender address"
            ),
            FieldMapping(
                close_field="to",
                supabase_column="email_recipients",
                data_type=DataType.JSON,
                description="Email recipients (TO)"
            ),
            FieldMapping(
                close_field="cc",
                supabase_column="email_cc",
                data_type=DataType.JSON,
                description="Email CC recipients"
            ),
            FieldMapping(
                close_field="bcc",
                supabase_column="email_bcc",
                data_type=DataType.JSON,
                description="Email BCC recipients"
            ),
            FieldMapping(
                close_field="opens",
                supabase_column="email_opens",
                data_type=DataType.INTEGER,
                description="Number of email opens"
            ),
            FieldMapping(
                close_field="clicks",
                supabase_column="email_clicks",
                data_type=DataType.INTEGER,
                description="Number of link clicks"
            ),
            FieldMapping(
                close_field="envelope",
                supabase_column="email_envelope",
                data_type=DataType.JSON,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                description="Email envelope metadata"
            ),
            FieldMapping(
                close_field="template_id",
                supabase_column="email_template_id",
                data_type=DataType.STRING,
                description="Email template used"
            ),
            FieldMapping(
                close_field="attachments",
                supabase_column="email_attachments",
                data_type=DataType.JSON,
                description="Email attachments metadata"
            ),
            
            # ===== SMS FIELDS =====
            FieldMapping(
                close_field="text",
                supabase_column="sms_text",
                data_type=DataType.STRING,
                description="SMS message text"
            ),
            FieldMapping(
                close_field="sms_status",
                supabase_column="sms_status",
                data_type=DataType.STRING,
                description="SMS delivery status"
            ),
            FieldMapping(
                close_field="remote_phone",
                supabase_column="sms_phone_to",
                data_type=DataType.PHONE,
                description="SMS recipient phone"
            ),
            FieldMapping(
                close_field="local_phone",
                supabase_column="sms_phone_from",
                data_type=DataType.PHONE,
                description="SMS sender phone"
            ),
            FieldMapping(
                close_field="sms_attachments",
                supabase_column="sms_attachments",
                data_type=DataType.JSON,
                description="SMS attachments (MMS)"
            ),
            
            # ===== CALL FIELDS =====
            FieldMapping(
                close_field="duration",
                supabase_column="call_duration_seconds",
                data_type=DataType.INTEGER,
                description="Call duration in seconds"
            ),
            FieldMapping(
                close_field="disposition",
                supabase_column="call_disposition",
                data_type=DataType.STRING,
                description="Call outcome (connected, voicemail, etc.)"
            ),
            FieldMapping(
                close_field="remote_phone",
                supabase_column="call_phone_to",
                data_type=DataType.PHONE,
                description="Call recipient phone"
            ),
            FieldMapping(
                close_field="local_phone",
                supabase_column="call_phone_from",
                data_type=DataType.PHONE,
                description="Call sender phone"
            ),
            FieldMapping(
                close_field="recording_url",
                supabase_column="call_recording_url",
                data_type=DataType.URL,
                description="Call recording URL"
            ),
            FieldMapping(
                close_field="voicemail_url",
                supabase_column="call_voicemail_url",
                data_type=DataType.URL,
                description="Voicemail recording URL"
            ),
            FieldMapping(
                close_field="note",
                supabase_column="call_notes",
                data_type=DataType.STRING,
                description="Call notes"
            ),
            FieldMapping(
                close_field="transferred_from",
                supabase_column="call_transferred_from",
                data_type=DataType.STRING,
                description="Call transferred from user"
            ),
            FieldMapping(
                close_field="transferred_to",
                supabase_column="call_transferred_to",
                data_type=DataType.STRING,
                description="Call transferred to user"
            ),
            
            # ===== MEETING FIELDS =====
            FieldMapping(
                close_field="title",
                supabase_column="meeting_title",
                data_type=DataType.STRING,
                description="Meeting title"
            ),
            FieldMapping(
                close_field="location",
                supabase_column="meeting_location",
                data_type=DataType.STRING,
                description="Meeting location"
            ),
            FieldMapping(
                close_field="starts_at",
                supabase_column="meeting_start_at",
                data_type=DataType.DATETIME,
                transform_to_supabase=self._parse_iso_datetime,
                description="Meeting start time"
            ),
            FieldMapping(
                close_field="ends_at",
                supabase_column="meeting_end_at",
                data_type=DataType.DATETIME,
                transform_to_supabase=self._parse_iso_datetime,
                description="Meeting end time"
            ),
            FieldMapping(
                close_field="attendees",
                supabase_column="meeting_attendees",
                data_type=DataType.JSON,
                description="Meeting attendees"
            ),
            FieldMapping(
                close_field="calendar_event_link",
                supabase_column="meeting_calendar_link",
                data_type=DataType.URL,
                description="Calendar event link"
            ),
            
            # ===== NOTE FIELDS =====
            FieldMapping(
                close_field="note",
                supabase_column="note_content",
                data_type=DataType.STRING,
                description="Note content"
            ),
            FieldMapping(
                close_field="note_html",
                supabase_column="note_content_html",
                data_type=DataType.STRING,
                description="Note content (HTML)"
            ),
            
            # ===== SEQUENCE FIELDS =====
            FieldMapping(
                close_field="sequence_id",
                supabase_column="sequence_id",
                data_type=DataType.STRING,
                description="Sequence ID"
            ),
            FieldMapping(
                close_field="sequence_name",
                supabase_column="sequence_name",
                data_type=DataType.STRING,
                description="Sequence name"
            ),
            FieldMapping(
                close_field="sequence_step",
                supabase_column="sequence_step",
                data_type=DataType.INTEGER,
                description="Sequence step number"
            ),
            FieldMapping(
                close_field="sequence_subscription_id",
                supabase_column="sequence_subscription_id",
                data_type=DataType.STRING,
                description="Sequence subscription ID"
            ),
            
            # ===== TIMESTAMPS =====
            FieldMapping(
                close_field="date_created",
                supabase_column="date_created",
                data_type=DataType.DATETIME,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                required=True,
                transform_to_supabase=self._parse_iso_datetime,
                description="When activity was created"
            ),
            FieldMapping(
                close_field="date_updated",
                supabase_column="date_updated",
                data_type=DataType.DATETIME,
                direction=FieldDirection.CLOSE_TO_SUPABASE,
                transform_to_supabase=self._parse_iso_datetime,
                description="When activity was last updated"
            ),
            FieldMapping(
                close_field="date_sent",
                supabase_column="date_sent",
                data_type=DataType.DATETIME,
                transform_to_supabase=self._parse_iso_datetime,
                description="When email/SMS was sent"
            ),
            FieldMapping(
                close_field="date_scheduled",
                supabase_column="date_scheduled",
                data_type=DataType.DATETIME,
                transform_to_supabase=self._parse_iso_datetime,
                description="Scheduled send time"
            ),
            FieldMapping(
                close_field="activity_at",
                supabase_column="activity_at",
                data_type=DataType.DATETIME,
                transform_to_supabase=self._parse_iso_datetime,
                description="When activity occurred"
            ),
        ]
        
        self.entities["activity"] = EntityMapping(
            entity_name="activity",
            close_endpoint="/activity/",
            supabase_table="fact_close_activities",
            id_field_close="id",
            id_field_supabase="activity_id",
            close_id_column="close_activity_id",
            fields=activity_fields
        )
    
    # =========================================================================
    # CUSTOM FIELD MAPPINGS (Dynamic)
    # =========================================================================
    
    def _register_custom_field_mappings(self):
        """Register standard Close custom fields used by Coperniq"""
        
        # These are Coperniq-specific custom fields
        # Add custom field mappings dynamically based on Close schema
        custom_fields = [
            # Lead custom fields
            FieldMapping(
                close_field="custom.qualification_score",
                supabase_column="qualification_score",
                data_type=DataType.INTEGER,
                description="ICP qualification score (0-100)"
            ),
            FieldMapping(
                close_field="custom.is_atl",
                supabase_column="has_atl",
                data_type=DataType.BOOLEAN,
                transform_to_supabase=lambda x: x == "Yes" if isinstance(x, str) else bool(x),
                transform_to_close=lambda x: "Yes" if x else "No",
                description="Has ATL decision maker"
            ),
            FieldMapping(
                close_field="custom.priority_label",
                supabase_column="priority_label",
                data_type=DataType.STRING,
                description="Priority label (Hot ATL, Warm, etc.)"
            ),
            FieldMapping(
                close_field="custom.tier",
                supabase_column="lead_tier",
                data_type=DataType.STRING,
                description="Lead tier (hot/warm/cold)"
            ),
            FieldMapping(
                close_field="custom.oem_brands",
                supabase_column="oem_brands",
                data_type=DataType.JSON,
                description="OEM brands sold"
            ),
            FieldMapping(
                close_field="custom.license_types",
                supabase_column="license_types",
                data_type=DataType.JSON,
                description="Contractor license types"
            ),
            FieldMapping(
                close_field="custom.employee_count",
                supabase_column="employee_count",
                data_type=DataType.INTEGER,
                description="Number of employees"
            ),
            FieldMapping(
                close_field="custom.annual_revenue",
                supabase_column="annual_revenue",
                data_type=DataType.FLOAT,
                description="Annual revenue estimate"
            ),
            FieldMapping(
                close_field="custom.source_campaign",
                supabase_column="source_campaign",
                data_type=DataType.STRING,
                description="Marketing source campaign"
            ),
        ]
        
        # Merge with lead entity
        if "lead" in self.entities:
            self.entities["lead"].fields.extend(custom_fields)
    
    # =========================================================================
    # TRANSFORM HELPER FUNCTIONS
    # =========================================================================
    
    @staticmethod
    def _parse_iso_datetime(value: Any) -> Optional[datetime]:
        """Parse ISO datetime string to datetime object"""
        if not value:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(value.replace('Z', '+00:00'))
        except (ValueError, AttributeError):
            return None
    
    @staticmethod
    def _clean_name(value: str) -> Optional[str]:
        """Clean and normalize name string"""
        if not value:
            return None
        return value.strip()
    
    @staticmethod
    def _normalize_activity_type(value: str) -> str:
        """Normalize Close activity type to our standard types"""
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
    
    @staticmethod
    def _extract_first_address_field(field_name: str) -> Callable:
        """Create function to extract field from first address in array"""
        def extractor(addresses: List[Dict]) -> Optional[str]:
            if not addresses or not isinstance(addresses, list):
                return None
            if len(addresses) > 0 and isinstance(addresses[0], dict):
                return addresses[0].get(field_name)
            return None
        return extractor
    
    @staticmethod
    def _build_address_array(field_name: str) -> Callable:
        """Create function to build address array for Close API"""
        def builder(value: str, existing: List[Dict] = None) -> List[Dict]:
            if not value:
                return existing or []
            if existing and len(existing) > 0:
                existing[0][field_name] = value
                return existing
            return [{field_name: value}]
        return builder
    
    @staticmethod
    def _extract_first_phone(phones: List[Dict]) -> Optional[str]:
        """Extract first phone number from phones array"""
        if not phones or not isinstance(phones, list):
            return None
        if len(phones) > 0 and isinstance(phones[0], dict):
            return phones[0].get("phone")
        return None
    
    @staticmethod
    def _extract_primary_phone(phones: List[Dict]) -> Optional[str]:
        """Extract primary phone (first direct > mobile > any)"""
        if not phones or not isinstance(phones, list):
            return None
        
        # Priority: direct > mobile > office > any
        for phone_type in ["direct", "mobile", "office"]:
            for phone in phones:
                if isinstance(phone, dict) and phone.get("type") == phone_type:
                    return phone.get("phone")
        
        # Fallback to first
        if len(phones) > 0 and isinstance(phones[0], dict):
            return phones[0].get("phone")
        return None
    
    @staticmethod
    def _build_phone_array(value: str, phone_type: str = "office") -> List[Dict]:
        """Build phone array for Close API"""
        if not value:
            return []
        return [{"phone": value, "type": phone_type}]
    
    @staticmethod
    def _extract_primary_email(emails: List[Dict]) -> Optional[str]:
        """Extract primary email from emails array"""
        if not emails or not isinstance(emails, list):
            return None
        if len(emails) > 0 and isinstance(emails[0], dict):
            return emails[0].get("email")
        return None
    
    @staticmethod
    def _build_email_array(value: str, email_type: str = "office") -> List[Dict]:
        """Build email array for Close API"""
        if not value:
            return []
        return [{"email": value, "type": email_type}]
    
    @staticmethod
    def _extract_linkedin_url(urls: List[Dict]) -> Optional[str]:
        """Extract LinkedIn URL from urls array"""
        if not urls or not isinstance(urls, list):
            return None
        for url in urls:
            if isinstance(url, dict):
                url_str = url.get("url", "")
                if "linkedin.com" in url_str.lower():
                    return url_str
        return None
    
    @staticmethod
    def _build_url_array_with_linkedin(linkedin_url: str, existing: List[Dict] = None) -> List[Dict]:
        """Build URL array including LinkedIn for Close API"""
        result = existing or []
        if linkedin_url:
            # Remove existing LinkedIn URL
            result = [u for u in result if "linkedin.com" not in u.get("url", "").lower()]
            result.append({"url": linkedin_url, "type": "linkedin"})
        return result
    
    # =========================================================================
    # PUBLIC API
    # =========================================================================
    
    def get_entity_mapping(self, entity_name: str) -> Optional[EntityMapping]:
        """Get mapping for an entity type"""
        return self.entities.get(entity_name)
    
    def get_field_mapping(
        self, 
        entity_name: str, 
        close_field: str = None,
        supabase_column: str = None
    ) -> Optional[FieldMapping]:
        """Get specific field mapping by Close field or Supabase column"""
        entity = self.entities.get(entity_name)
        if not entity:
            return None
        
        for field in entity.fields:
            if close_field and field.close_field == close_field:
                return field
            if supabase_column and field.supabase_column == supabase_column:
                return field
        return None
    
    def get_all_close_fields(self, entity_name: str) -> List[str]:
        """Get all Close CRM field names for an entity"""
        entity = self.entities.get(entity_name)
        if not entity:
            return []
        return [f.close_field for f in entity.fields]
    
    def get_all_supabase_columns(self, entity_name: str) -> List[str]:
        """Get all Supabase column names for an entity"""
        entity = self.entities.get(entity_name)
        if not entity:
            return []
        return [f.supabase_column for f in entity.fields]
    
    def transform_close_to_supabase(
        self, 
        entity_name: str, 
        close_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Transform Close CRM data to Supabase row format.
        
        Args:
            entity_name: Entity type (lead, contact, activity)
            close_data: Raw Close CRM API response
            
        Returns:
            Dict ready for Supabase insert/update
        """
        entity = self.entities.get(entity_name)
        if not entity:
            raise ValueError(f"Unknown entity type: {entity_name}")
        
        result = {}
        
        for field in entity.fields:
            # Skip fields that don't sync to Supabase
            if field.direction == FieldDirection.SUPABASE_TO_CLOSE:
                continue
            
            # Extract value from Close data (handle nested paths)
            value = self._extract_nested_value(close_data, field.close_field)
            
            # Apply transform if defined
            if field.transform_to_supabase and value is not None:
                try:
                    value = field.transform_to_supabase(value)
                except Exception as e:
                    logger.warning(f"Transform error for {field.close_field}: {e}")
                    value = None
            
            # Apply default if null and default exists
            if value is None and field.default_value is not None:
                value = field.default_value
            
            # Skip null values unless column is required
            if value is None and not field.required:
                continue
            
            result[field.supabase_column] = value
        
        return result
    
    def transform_supabase_to_close(
        self,
        entity_name: str,
        supabase_data: Dict[str, Any],
        existing_close_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Transform Supabase data to Close CRM format.
        
        Args:
            entity_name: Entity type (lead, contact, activity)
            supabase_data: Supabase row data
            existing_close_data: Existing Close data for merge (optional)
            
        Returns:
            Dict ready for Close CRM API POST/PUT
        """
        entity = self.entities.get(entity_name)
        if not entity:
            raise ValueError(f"Unknown entity type: {entity_name}")
        
        result = existing_close_data.copy() if existing_close_data else {}
        
        for field in entity.fields:
            # Skip fields that don't sync to Close
            if field.direction == FieldDirection.CLOSE_TO_SUPABASE:
                continue
            
            value = supabase_data.get(field.supabase_column)
            
            # Skip None values
            if value is None:
                continue
            
            # Apply transform if defined
            if field.transform_to_close:
                try:
                    # Some transforms need existing data
                    existing_value = self._extract_nested_value(result, field.close_field)
                    value = field.transform_to_close(value, existing_value)
                except TypeError:
                    # Transform doesn't accept existing value
                    value = field.transform_to_close(value)
                except Exception as e:
                    logger.warning(f"Transform error for {field.supabase_column}: {e}")
                    continue
            
            # Handle nested paths (e.g., addresses[0].city)
            self._set_nested_value(result, field.close_field, value)
        
        return result
    
    def validate_data(
        self,
        entity_name: str,
        data: Dict[str, Any],
        is_close_data: bool = True
    ) -> List[str]:
        """
        Validate data against field requirements.
        
        Returns:
            List of validation error messages (empty if valid)
        """
        entity = self.entities.get(entity_name)
        if not entity:
            return [f"Unknown entity type: {entity_name}"]
        
        errors = []
        
        for field in entity.fields:
            field_name = field.close_field if is_close_data else field.supabase_column
            value = data.get(field_name)
            
            # Check required fields
            if field.required and value is None:
                errors.append(f"Required field missing: {field_name}")
            
            # Check nullable
            if not field.nullable and value is None:
                errors.append(f"Non-nullable field is null: {field_name}")
            
            # Run custom validation
            if field.validation_fn and value is not None:
                try:
                    if not field.validation_fn(value):
                        errors.append(f"Validation failed for: {field_name}")
                except Exception as e:
                    errors.append(f"Validation error for {field_name}: {e}")
        
        return errors
    
    def get_parity_report(self) -> Dict[str, Any]:
        """
        Generate field parity report comparing Close CRM and Supabase.
        
        Returns:
            Report with coverage statistics and missing fields
        """
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "entities": {}
        }
        
        for entity_name, entity in self.entities.items():
            bidirectional = 0
            close_to_supabase = 0
            supabase_to_close = 0
            required_fields = 0
            
            for field in entity.fields:
                if field.direction == FieldDirection.BIDIRECTIONAL:
                    bidirectional += 1
                elif field.direction == FieldDirection.CLOSE_TO_SUPABASE:
                    close_to_supabase += 1
                elif field.direction == FieldDirection.SUPABASE_TO_CLOSE:
                    supabase_to_close += 1
                
                if field.required:
                    required_fields += 1
            
            report["entities"][entity_name] = {
                "table": entity.supabase_table,
                "total_fields": len(entity.fields),
                "bidirectional": bidirectional,
                "close_to_supabase_only": close_to_supabase,
                "supabase_to_close_only": supabase_to_close,
                "required_fields": required_fields,
                "parity_percentage": round(bidirectional / len(entity.fields) * 100, 1) if entity.fields else 0
            }
        
        return report
    
    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    @staticmethod
    def _extract_nested_value(data: Dict, path: str) -> Any:
        """
        Extract value from nested dict using dot notation.
        
        Supports:
        - Simple paths: "name"
        - Nested paths: "address.city"
        - Array paths: "addresses[0].city"
        - Custom fields: "custom.cf_xxx"
        """
        if not data or not path:
            return None
        
        # Handle array notation (e.g., addresses[0].city)
        import re
        array_match = re.match(r'^(\w+)\[(\d+)\]\.?(.*)$', path)
        if array_match:
            array_key, index, remainder = array_match.groups()
            array_data = data.get(array_key, [])
            if isinstance(array_data, list) and len(array_data) > int(index):
                if remainder:
                    return FieldRegistry._extract_nested_value(
                        array_data[int(index)], remainder
                    )
                return array_data[int(index)]
            return None
        
        # Handle dot notation
        parts = path.split(".", 1)
        value = data.get(parts[0])
        
        if len(parts) == 1:
            return value
        
        if isinstance(value, dict):
            return FieldRegistry._extract_nested_value(value, parts[1])
        
        return None
    
    @staticmethod
    def _set_nested_value(data: Dict, path: str, value: Any) -> None:
        """
        Set value in nested dict using dot notation.
        
        Supports same path formats as _extract_nested_value.
        """
        if not path:
            return
        
        # Handle array notation
        import re
        array_match = re.match(r'^(\w+)\[(\d+)\]\.?(.*)$', path)
        if array_match:
            array_key, index_str, remainder = array_match.groups()
            index = int(index_str)
            
            if array_key not in data:
                data[array_key] = []
            
            # Extend array if needed
            while len(data[array_key]) <= index:
                data[array_key].append({})
            
            if remainder:
                FieldRegistry._set_nested_value(data[array_key][index], remainder, value)
            else:
                data[array_key][index] = value
            return
        
        # Handle dot notation
        parts = path.split(".", 1)
        
        if len(parts) == 1:
            data[parts[0]] = value
        else:
            if parts[0] not in data:
                data[parts[0]] = {}
            FieldRegistry._set_nested_value(data[parts[0]], parts[1], value)
    
    def register_custom_field(
        self,
        entity_name: str,
        close_field_id: str,
        supabase_column: str,
        data_type: DataType,
        **kwargs
    ) -> None:
        """
        Dynamically register a new custom field mapping.
        
        Args:
            entity_name: Entity type
            close_field_id: Close custom field ID (cf_xxx)
            supabase_column: Supabase column name
            data_type: Data type for the field
            **kwargs: Additional FieldMapping parameters
        """
        entity = self.entities.get(entity_name)
        if not entity:
            raise ValueError(f"Unknown entity type: {entity_name}")
        
        mapping = FieldMapping(
            close_field=f"custom.{close_field_id}",
            supabase_column=supabase_column,
            data_type=data_type,
            **kwargs
        )
        
        # Check for duplicate
        for i, existing in enumerate(entity.fields):
            if existing.close_field == mapping.close_field:
                entity.fields[i] = mapping
                logger.info(f"Updated custom field mapping: {mapping.close_field}")
                return
        
        entity.fields.append(mapping)
        logger.info(f"Registered new custom field mapping: {mapping.close_field}")
