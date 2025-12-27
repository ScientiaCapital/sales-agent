"""Contact field mappings: Close Contacts → dim_contacts."""
from typing import List

from ..schemas import FieldMapping, DataType, FieldDirection
from ..transforms import (
    parse_iso_datetime, clean_name,
    extract_primary_phone, build_phone_array,
    extract_primary_email, build_email_array,
    extract_linkedin_url, build_url_array_with_linkedin,
)


def get_contact_fields() -> List[FieldMapping]:
    """Get Close Contact → Supabase dim_contacts field mappings."""
    return [
        # Core Identity
        FieldMapping(
            close_field="id", supabase_column="close_contact_id",
            data_type=DataType.STRING, direction=FieldDirection.CLOSE_TO_SUPABASE,
            required=True, nullable=False, description="Close CRM Contact ID (cont_xxx)"
        ),
        FieldMapping(
            close_field="lead_id", supabase_column="close_lead_id",
            data_type=DataType.STRING, required=True, description="Parent lead ID"
        ),
        FieldMapping(
            close_field="name", supabase_column="full_name", data_type=DataType.STRING,
            transform_to_supabase=clean_name, description="Full contact name"
        ),
        # Name components
        FieldMapping(
            close_field="first_name", supabase_column="first_name",
            data_type=DataType.STRING, description="First name"
        ),
        FieldMapping(
            close_field="last_name", supabase_column="last_name",
            data_type=DataType.STRING, description="Last name"
        ),
        # Role
        FieldMapping(
            close_field="title", supabase_column="title",
            data_type=DataType.STRING, description="Job title"
        ),
        # Email (from emails array)
        FieldMapping(
            close_field="emails", supabase_column="email", data_type=DataType.EMAIL,
            transform_to_supabase=extract_primary_email,
            transform_to_close=build_email_array,
            description="Primary email address"
        ),
        FieldMapping(
            close_field="emails", supabase_column="emails_all", data_type=DataType.JSON,
            direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="All email addresses (JSON array)"
        ),
        # Phone (from phones array)
        FieldMapping(
            close_field="phones", supabase_column="phone", data_type=DataType.PHONE,
            transform_to_supabase=extract_primary_phone,
            transform_to_close=build_phone_array,
            description="Primary phone number"
        ),
        FieldMapping(
            close_field="phones", supabase_column="phones_all", data_type=DataType.JSON,
            direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="All phone numbers (JSON array)"
        ),
        # URLs (from urls array)
        FieldMapping(
            close_field="urls", supabase_column="linkedin_url", data_type=DataType.URL,
            transform_to_supabase=extract_linkedin_url,
            transform_to_close=build_url_array_with_linkedin,
            description="LinkedIn profile URL"
        ),
        FieldMapping(
            close_field="urls", supabase_column="urls_all", data_type=DataType.JSON,
            direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="All URLs (JSON array)"
        ),
        # User Assignment
        FieldMapping(
            close_field="created_by", supabase_column="close_created_by_id",
            data_type=DataType.STRING, direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="User who created contact"
        ),
        FieldMapping(
            close_field="updated_by", supabase_column="close_updated_by_id",
            data_type=DataType.STRING, direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="User who last updated contact"
        ),
        # Timestamps
        FieldMapping(
            close_field="date_created", supabase_column="close_created_at",
            data_type=DataType.DATETIME, direction=FieldDirection.CLOSE_TO_SUPABASE,
            transform_to_supabase=parse_iso_datetime,
            description="When contact was created"
        ),
        FieldMapping(
            close_field="date_updated", supabase_column="close_updated_at",
            data_type=DataType.DATETIME, direction=FieldDirection.CLOSE_TO_SUPABASE,
            transform_to_supabase=parse_iso_datetime,
            description="When contact was last updated"
        ),
    ]
