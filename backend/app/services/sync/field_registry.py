"""Field Registry: Central registry for Close CRM ↔ Supabase field mappings."""
from typing import Any, Dict, List, Optional
import logging

from .schemas import FieldDirection, DataType, FieldMapping, EntityMapping
from .path_utils import extract_nested_value, set_nested_value
from .registrations import (
    get_lead_fields, get_contact_fields, get_activity_fields, get_custom_fields
)
from .parity_report import generate_parity_report

logger = logging.getLogger(__name__)

__all__ = [
    "FieldDirection", "DataType", "FieldMapping", "EntityMapping", "FieldRegistry"
]


class FieldRegistry:
    """Central registry for all field mappings between Close CRM and Supabase."""

    def __init__(self):
        self.entities: Dict[str, EntityMapping] = {}
        self._register_all_mappings()

    def _register_all_mappings(self):
        """Register all entity mappings from registration modules."""
        lead_fields = get_lead_fields()
        lead_fields.extend(get_custom_fields())
        self.entities["lead"] = EntityMapping(
            entity_name="lead", close_endpoint="/lead/",
            supabase_table="dim_companies", id_field_close="id",
            id_field_supabase="company_id", close_id_column="close_lead_id",
            fields=lead_fields
        )
        self.entities["contact"] = EntityMapping(
            entity_name="contact", close_endpoint="/contact/",
            supabase_table="dim_contacts", id_field_close="id",
            id_field_supabase="contact_id", close_id_column="close_contact_id",
            fields=get_contact_fields()
        )
        self.entities["activity"] = EntityMapping(
            entity_name="activity", close_endpoint="/activity/",
            supabase_table="fact_close_activities", id_field_close="id",
            id_field_supabase="activity_id", close_id_column="close_activity_id",
            fields=get_activity_fields()
        )

    def get_entity_mapping(self, entity_name: str) -> Optional[EntityMapping]:
        """Get mapping for an entity type."""
        return self.entities.get(entity_name)

    def get_field_mapping(
        self, entity_name: str, close_field: str = None, supabase_column: str = None
    ) -> Optional[FieldMapping]:
        """Get specific field mapping by Close field or Supabase column."""
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
        """Get all Close CRM field names for an entity."""
        entity = self.entities.get(entity_name)
        return [f.close_field for f in entity.fields] if entity else []

    def get_all_supabase_columns(self, entity_name: str) -> List[str]:
        """Get all Supabase column names for an entity."""
        entity = self.entities.get(entity_name)
        return [f.supabase_column for f in entity.fields] if entity else []

    def transform_close_to_supabase(
        self, entity_name: str, close_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Transform Close CRM data to Supabase row format."""
        entity = self.entities.get(entity_name)
        if not entity:
            raise ValueError(f"Unknown entity type: {entity_name}")
        result = {}
        for field in entity.fields:
            if field.direction == FieldDirection.SUPABASE_TO_CLOSE:
                continue
            value = extract_nested_value(close_data, field.close_field)
            if field.transform_to_supabase and value is not None:
                try:
                    value = field.transform_to_supabase(value)
                except Exception as e:
                    logger.warning(f"Transform error for {field.close_field}: {e}")
                    value = None
            if value is None and field.default_value is not None:
                value = field.default_value
            if value is None and not field.required:
                continue
            result[field.supabase_column] = value
        return result

    def transform_supabase_to_close(
        self, entity_name: str, supabase_data: Dict[str, Any],
        existing_close_data: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Transform Supabase data to Close CRM format."""
        entity = self.entities.get(entity_name)
        if not entity:
            raise ValueError(f"Unknown entity type: {entity_name}")
        result = existing_close_data.copy() if existing_close_data else {}
        for field in entity.fields:
            if field.direction == FieldDirection.CLOSE_TO_SUPABASE:
                continue
            value = supabase_data.get(field.supabase_column)
            if value is None:
                continue
            if field.transform_to_close:
                try:
                    existing = extract_nested_value(result, field.close_field)
                    value = field.transform_to_close(value, existing)
                except TypeError:
                    value = field.transform_to_close(value)
                except Exception as e:
                    logger.warning(f"Transform error: {field.supabase_column}: {e}")
                    continue
            set_nested_value(result, field.close_field, value)
        return result

    def validate_data(
        self, entity_name: str, data: Dict[str, Any], is_close_data: bool = True
    ) -> List[str]:
        """Validate data against field requirements. Returns list of errors."""
        entity = self.entities.get(entity_name)
        if not entity:
            return [f"Unknown entity type: {entity_name}"]
        errors = []
        for field in entity.fields:
            field_name = field.close_field if is_close_data else field.supabase_column
            value = data.get(field_name)
            if field.required and value is None:
                errors.append(f"Required field missing: {field_name}")
            if not field.nullable and value is None:
                errors.append(f"Non-nullable field is null: {field_name}")
            if field.validation_fn and value is not None:
                try:
                    if not field.validation_fn(value):
                        errors.append(f"Validation failed for: {field_name}")
                except Exception as e:
                    errors.append(f"Validation error for {field_name}: {e}")
        return errors

    def get_parity_report(self) -> Dict[str, Any]:
        """Generate field parity report comparing Close CRM and Supabase."""
        return generate_parity_report(self)

    def register_custom_field(
        self, entity_name: str, close_field_id: str, supabase_column: str,
        data_type: DataType, **kwargs
    ) -> None:
        """Dynamically register a new custom field mapping."""
        entity = self.entities.get(entity_name)
        if not entity:
            raise ValueError(f"Unknown entity type: {entity_name}")
        mapping = FieldMapping(
            close_field=f"custom.{close_field_id}",
            supabase_column=supabase_column, data_type=data_type, **kwargs
        )
        for i, existing in enumerate(entity.fields):
            if existing.close_field == mapping.close_field:
                entity.fields[i] = mapping
                logger.info(f"Updated custom field: {mapping.close_field}")
                return
        entity.fields.append(mapping)
        logger.info(f"Registered custom field: {mapping.close_field}")
