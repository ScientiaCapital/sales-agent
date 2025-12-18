"""
Content module - bridges GTME playbooks to agent systems.

Loads sequences, templates, and intel from coperniq-forge.
"""
from .gtme_loader import (
    GTMEContentLoader,
    EmailSequence,
    SequenceStep,
    get_sequence_for_engine,
    list_available_sequences,
    get_personalization_context,
)

__all__ = [
    "GTMEContentLoader",
    "EmailSequence", 
    "SequenceStep",
    "get_sequence_for_engine",
    "list_available_sequences",
    "get_personalization_context",
]
