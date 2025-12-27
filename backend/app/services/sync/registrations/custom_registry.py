"""Custom field mappings for Coperniq-specific Close fields."""
from typing import List

from ..schemas import FieldMapping, DataType


def get_custom_fields() -> List[FieldMapping]:
    """Get Coperniq-specific custom field mappings for leads."""
    return [
        FieldMapping(
            close_field="custom.qualification_score", supabase_column="qualification_score",
            data_type=DataType.INTEGER, description="ICP qualification score (0-100)"
        ),
        FieldMapping(
            close_field="custom.is_atl", supabase_column="has_atl",
            data_type=DataType.BOOLEAN,
            transform_to_supabase=lambda x: x == "Yes" if isinstance(x, str) else bool(x),
            transform_to_close=lambda x: "Yes" if x else "No",
            description="Has ATL decision maker"
        ),
        FieldMapping(
            close_field="custom.priority_label", supabase_column="priority_label",
            data_type=DataType.STRING, description="Priority label (Hot ATL, Warm, etc.)"
        ),
        FieldMapping(
            close_field="custom.tier", supabase_column="lead_tier",
            data_type=DataType.STRING, description="Lead tier (hot/warm/cold)"
        ),
        FieldMapping(
            close_field="custom.oem_brands", supabase_column="oem_brands",
            data_type=DataType.JSON, description="OEM brands sold"
        ),
        FieldMapping(
            close_field="custom.license_types", supabase_column="license_types",
            data_type=DataType.JSON, description="Contractor license types"
        ),
        FieldMapping(
            close_field="custom.employee_count", supabase_column="employee_count",
            data_type=DataType.INTEGER, description="Number of employees"
        ),
        FieldMapping(
            close_field="custom.annual_revenue", supabase_column="annual_revenue",
            data_type=DataType.FLOAT, description="Annual revenue estimate"
        ),
        FieldMapping(
            close_field="custom.source_campaign", supabase_column="source_campaign",
            data_type=DataType.STRING, description="Marketing source campaign"
        ),
    ]
