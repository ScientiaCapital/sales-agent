"""Specialized agents for voice calls."""

from .qualifier import QualifierAgent, QualificationResult
from .objection_handler import ObjectionHandlerAgent, ObjectionResult
from .closer import CloserAgent, CloseResult

__all__ = [
    "QualifierAgent", "QualificationResult",
    "ObjectionHandlerAgent", "ObjectionResult",
    "CloserAgent", "CloseResult"
]
