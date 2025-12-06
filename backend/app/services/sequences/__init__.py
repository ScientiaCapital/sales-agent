"""
Sequence engine and email sender for multi-step cold outreach campaigns.

This module provides the core orchestration for:
- Enrolling prospects into email sequences
- Executing scheduled email steps
- Processing replies and triggering signals
- Coordinating with VozLux for call triggers

Migrated from cold-reach into sales-agent for native integration.
"""
from .engine import SequenceEngine
from .sender import EmailSender, ReplyClassifier

__all__ = ["SequenceEngine", "EmailSender", "ReplyClassifier"]
