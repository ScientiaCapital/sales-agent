"""Address transform functions for Close CRM address arrays."""
from typing import Callable, Dict, List, Optional


def extract_first_address_field(field_name: str) -> Callable:
    """Create function to extract field from first address in array.

    Args:
        field_name: Field to extract (e.g., 'city', 'state', 'zipcode')

    Returns:
        Extractor function for use in FieldMapping.transform_to_supabase
    """
    def extractor(addresses: List[Dict]) -> Optional[str]:
        if not addresses or not isinstance(addresses, list):
            return None
        if len(addresses) > 0 and isinstance(addresses[0], dict):
            return addresses[0].get(field_name)
        return None
    return extractor


def build_address_array(field_name: str) -> Callable:
    """Create function to build address array for Close API.

    Args:
        field_name: Field to set (e.g., 'city', 'state', 'zipcode')

    Returns:
        Builder function for use in FieldMapping.transform_to_close
    """
    def builder(value: str, existing: List[Dict] = None) -> List[Dict]:
        if not value:
            return existing or []
        if existing and len(existing) > 0:
            existing[0][field_name] = value
            return existing
        return [{field_name: value}]
    return builder
