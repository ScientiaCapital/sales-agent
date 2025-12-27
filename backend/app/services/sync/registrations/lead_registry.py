"""Lead field mappings: Close Leads → dim_companies."""
from typing import List

from ..schemas import FieldMapping, DataType, FieldDirection
from ..transforms import (
    parse_iso_datetime,
    extract_first_address_field, build_address_array,
    extract_first_phone, build_phone_array,
)


def get_lead_fields() -> List[FieldMapping]:
    """Get Close Lead → Supabase dim_companies field mappings."""
    return [
        # Core Identity Fields
        FieldMapping(
            close_field="id", supabase_column="close_lead_id",
            data_type=DataType.STRING, direction=FieldDirection.CLOSE_TO_SUPABASE,
            required=True, nullable=False, description="Close CRM Lead ID (lead_xxx)"
        ),
        FieldMapping(
            close_field="name", supabase_column="company_name",
            data_type=DataType.STRING, required=True, nullable=False,
            description="Company/Organization name"
        ),
        FieldMapping(
            close_field="display_name", supabase_column="display_name",
            data_type=DataType.STRING, description="Display name (may differ from name)"
        ),
        FieldMapping(
            close_field="description", supabase_column="description",
            data_type=DataType.STRING, description="Lead description/notes"
        ),
        # URL/Domain Fields
        FieldMapping(
            close_field="url", supabase_column="website", data_type=DataType.URL,
            transform_to_supabase=lambda x: x if x else None,
            description="Company website URL"
        ),
        # Status Fields
        FieldMapping(
            close_field="status_id", supabase_column="close_status_id",
            data_type=DataType.STRING, description="Close status ID (stat_xxx)"
        ),
        FieldMapping(
            close_field="status_label", supabase_column="close_status_label",
            data_type=DataType.STRING, direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="Human-readable status label"
        ),
        # Address Fields (from addresses array)
        FieldMapping(
            close_field="addresses[0].address_1", supabase_column="street",
            data_type=DataType.STRING,
            transform_to_supabase=extract_first_address_field("address_1"),
            transform_to_close=build_address_array("address_1"),
            description="Street address line 1"
        ),
        FieldMapping(
            close_field="addresses[0].city", supabase_column="city",
            data_type=DataType.STRING,
            transform_to_supabase=extract_first_address_field("city"),
            transform_to_close=build_address_array("city"),
            description="City"
        ),
        FieldMapping(
            close_field="addresses[0].state", supabase_column="state",
            data_type=DataType.STRING,
            transform_to_supabase=extract_first_address_field("state"),
            transform_to_close=build_address_array("state"),
            description="State/Province"
        ),
        FieldMapping(
            close_field="addresses[0].zipcode", supabase_column="zip",
            data_type=DataType.STRING,
            transform_to_supabase=extract_first_address_field("zipcode"),
            transform_to_close=build_address_array("zipcode"),
            description="ZIP/Postal code"
        ),
        FieldMapping(
            close_field="addresses[0].country", supabase_column="country",
            data_type=DataType.STRING,
            transform_to_supabase=extract_first_address_field("country"),
            transform_to_close=build_address_array("country"),
            description="Country"
        ),
        # Phone (lead-level)
        FieldMapping(
            close_field="phones", supabase_column="phone", data_type=DataType.PHONE,
            transform_to_supabase=extract_first_phone,
            transform_to_close=build_phone_array,
            description="Primary company phone"
        ),
        # User Assignment
        FieldMapping(
            close_field="created_by", supabase_column="close_created_by_id",
            data_type=DataType.STRING, direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="Close user who created the lead"
        ),
        FieldMapping(
            close_field="updated_by", supabase_column="close_updated_by_id",
            data_type=DataType.STRING, direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="Close user who last updated the lead"
        ),
        # Timestamps
        FieldMapping(
            close_field="date_created", supabase_column="close_created_at",
            data_type=DataType.DATETIME, direction=FieldDirection.CLOSE_TO_SUPABASE,
            transform_to_supabase=parse_iso_datetime,
            description="When lead was created in Close"
        ),
        FieldMapping(
            close_field="date_updated", supabase_column="close_updated_at",
            data_type=DataType.DATETIME, direction=FieldDirection.CLOSE_TO_SUPABASE,
            transform_to_supabase=parse_iso_datetime,
            description="When lead was last updated in Close"
        ),
        # JSON aggregates
        FieldMapping(
            close_field="opportunities", supabase_column="opportunities_json",
            data_type=DataType.JSON, direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="Array of opportunities on this lead"
        ),
        FieldMapping(
            close_field="tasks", supabase_column="tasks_json",
            data_type=DataType.JSON, direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="Array of tasks on this lead"
        ),
        # HTML URL (for linking)
        FieldMapping(
            close_field="html_url", supabase_column="close_html_url",
            data_type=DataType.URL, direction=FieldDirection.CLOSE_TO_SUPABASE,
            description="Direct link to lead in Close UI"
        ),
        # Integration Links
        FieldMapping(
            close_field="integration_links", supabase_column="integration_links",
            data_type=DataType.JSON, description="External integration links"
        ),
    ]
