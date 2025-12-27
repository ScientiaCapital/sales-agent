"""Parity report generation for field registry analysis."""
from datetime import datetime
from typing import Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from .field_registry import FieldRegistry

from .schemas import FieldDirection


def generate_parity_report(registry: "FieldRegistry") -> Dict[str, Any]:
    """Generate field parity report comparing Close CRM and Supabase.

    Args:
        registry: FieldRegistry instance to analyze

    Returns:
        Report with coverage statistics per entity
    """
    report = {"timestamp": datetime.utcnow().isoformat(), "entities": {}}

    for entity_name, entity in registry.entities.items():
        bi, c2s, s2c, req = 0, 0, 0, 0
        for f in entity.fields:
            if f.direction == FieldDirection.BIDIRECTIONAL:
                bi += 1
            elif f.direction == FieldDirection.CLOSE_TO_SUPABASE:
                c2s += 1
            elif f.direction == FieldDirection.SUPABASE_TO_CLOSE:
                s2c += 1
            if f.required:
                req += 1

        total = len(entity.fields)
        report["entities"][entity_name] = {
            "table": entity.supabase_table,
            "total_fields": total,
            "bidirectional": bi,
            "close_to_supabase_only": c2s,
            "supabase_to_close_only": s2c,
            "required_fields": req,
            "parity_percentage": round(bi / total * 100, 1) if total else 0
        }

    return report
