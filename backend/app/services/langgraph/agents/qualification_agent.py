"""
QualificationAgent - Backward compatibility shim.

This module has been refactored into the qualification/ package.
Import from there directly for new code:
    from app.services.langgraph.agents.qualification import QualificationAgent

This shim maintains backward compatibility for existing imports.
"""
from app.services.langgraph.agents.qualification import (
    QualificationAgent,
    LeadQualificationResult,
)

__all__ = [
    "QualificationAgent",
    "LeadQualificationResult",
]
