"""Core schemas for field registry: enums and dataclasses."""
from typing import Any, Callable, List, Optional
from dataclasses import dataclass, field
from enum import Enum


class FieldDirection(Enum):
    """Direction of field sync between Close CRM and Supabase."""
    BIDIRECTIONAL = "bidirectional"      # Sync both ways
    CLOSE_TO_SUPABASE = "close_to_supabase"  # Read-only from Close
    SUPABASE_TO_CLOSE = "supabase_to_close"  # Write-only to Close
    NONE = "none"                        # Don't sync


class DataType(Enum):
    """Supported data types for field validation."""
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
    """Complete field mapping definition between Close CRM and Supabase.

    Attributes:
        close_field: Close CRM field name (e.g., "name", "custom.cf_xxx")
        supabase_column: Supabase column name
        data_type: Expected data type for validation
        direction: Sync direction (bidirectional, one-way, or none)
        required: Whether this field is required
        nullable: Whether this field can be null
        default_value: Default value if missing
        transform_to_supabase: Transform function for Close → Supabase
        transform_to_close: Transform function for Supabase → Close
        validation_fn: Custom validation function
        description: Human-readable field description
        conflict_strategy: How to resolve sync conflicts
    """
    close_field: str
    supabase_column: str
    data_type: DataType
    direction: FieldDirection = FieldDirection.BIDIRECTIONAL
    required: bool = False
    nullable: bool = True
    default_value: Any = None
    transform_to_supabase: Optional[Callable] = None
    transform_to_close: Optional[Callable] = None
    validation_fn: Optional[Callable] = None
    description: str = ""
    conflict_strategy: str = "newer_wins"  # newer_wins, close_wins, supabase_wins, manual


@dataclass
class EntityMapping:
    """Mapping for a complete entity (Lead, Contact, Activity).

    Attributes:
        entity_name: Entity type ("lead", "contact", "activity")
        close_endpoint: Close API endpoint
        supabase_table: Supabase table name
        id_field_close: Close CRM ID field name
        id_field_supabase: Supabase ID field name
        close_id_column: Supabase column storing Close ID
        fields: List of field mappings for this entity
    """
    entity_name: str
    close_endpoint: str
    supabase_table: str
    id_field_close: str = "id"
    id_field_supabase: str = "company_id"
    close_id_column: str = "close_lead_id"
    fields: List[FieldMapping] = field(default_factory=list)
