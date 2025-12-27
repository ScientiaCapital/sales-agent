"""Path utilities for nested dict value extraction and setting."""
import re
from typing import Any, Dict


def extract_nested_value(data: Dict, path: str) -> Any:
    """Extract value from nested dict using dot notation.

    Supports:
    - Simple paths: "name"
    - Nested paths: "address.city"
    - Array paths: "addresses[0].city"
    - Custom fields: "custom.cf_xxx"

    Args:
        data: Source dictionary
        path: Dot-notation path (e.g., "addresses[0].city")

    Returns:
        Extracted value or None if not found
    """
    if not data or not path:
        return None

    # Handle array notation (e.g., addresses[0].city)
    array_match = re.match(r'^(\w+)\[(\d+)\]\.?(.*)$', path)
    if array_match:
        array_key, index, remainder = array_match.groups()
        array_data = data.get(array_key, [])
        if isinstance(array_data, list) and len(array_data) > int(index):
            if remainder:
                return extract_nested_value(array_data[int(index)], remainder)
            return array_data[int(index)]
        return None

    # Handle dot notation
    parts = path.split(".", 1)
    value = data.get(parts[0])

    if len(parts) == 1:
        return value

    if isinstance(value, dict):
        return extract_nested_value(value, parts[1])

    return None


def set_nested_value(data: Dict, path: str, value: Any) -> None:
    """Set value in nested dict using dot notation.

    Creates intermediate dicts/arrays as needed.

    Supports:
    - Simple paths: "name"
    - Nested paths: "address.city"
    - Array paths: "addresses[0].city"
    - Custom fields: "custom.cf_xxx"

    Args:
        data: Target dictionary (modified in place)
        path: Dot-notation path
        value: Value to set
    """
    if not path:
        return

    # Handle array notation
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
            set_nested_value(data[array_key][index], remainder, value)
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
        set_nested_value(data[parts[0]], parts[1], value)
