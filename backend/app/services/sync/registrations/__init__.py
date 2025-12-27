"""Field mapping registrations for Close CRM ↔ Supabase sync."""
from .lead_registry import get_lead_fields
from .contact_registry import get_contact_fields
from .activity_registry import get_activity_fields
from .custom_registry import get_custom_fields

__all__ = [
    "get_lead_fields",
    "get_contact_fields",
    "get_activity_fields",
    "get_custom_fields",
]
