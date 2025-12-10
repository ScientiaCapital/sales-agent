"""Base classes and models for voice handlers."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from app.services.voice.intent_classifier import SalesIntent


@dataclass
class HandlerResponse:
    """Response from a voice handler.

    Attributes:
        response_text: TTS-friendly text to speak to caller (no markdown)
        next_intent: Suggested next intent for routing (or None if complete)
        should_transfer: True if ready to transfer to human representative
        data: Handler-specific data (qualification_data, meeting_data, etc.)
        metadata: Additional tracking info (lead_score, timestamps, etc.)
    """
    response_text: str
    next_intent: Optional[SalesIntent] = None
    should_transfer: bool = False
    data: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

    # Transfer-specific fields
    handoff_summary: Optional[str] = None
    transfer_destination: Optional[Dict[str, str]] = None


class BaseHandler:
    """Base class for voice intent handlers.

    All handlers should:
    1. Return TTS-friendly text (no markdown, no bullet lists)
    2. Keep responses concise (1-3 sentences for voice)
    3. Track conversation state to avoid repeating questions
    4. Handle unclear responses gracefully
    """

    def __init__(self, cerebras_service=None):
        """Initialize handler with optional LLM service.

        Args:
            cerebras_service: Optional CerebrasService for enhanced responses
        """
        self.cerebras_service = cerebras_service

    def handle(
        self,
        transcript: str,
        conversation_history: List[Dict],
        lead_context: Optional[Dict] = None
    ) -> HandlerResponse:
        """Process transcript and generate response.

        Args:
            transcript: Current user speech transcript
            conversation_history: List of conversation turns
            lead_context: Optional lead data from CRM

        Returns:
            HandlerResponse with text and metadata
        """
        raise NotImplementedError("Subclasses must implement handle()")

    def _clean_for_tts(self, text: str) -> str:
        """Remove markdown and formatting that breaks TTS.

        Args:
            text: Raw text that may contain markdown

        Returns:
            Clean text suitable for speech synthesis
        """
        # Remove common markdown
        clean = text.replace("**", "").replace("__", "")
        clean = clean.replace("##", "").replace("###", "")
        clean = clean.replace("```", "").replace("`", "")
        clean = clean.replace("* ", "").replace("- ", "")

        # Remove numbered lists (1. 2. 3.)
        import re
        clean = re.sub(r'^\d+\.\s+', '', clean, flags=re.MULTILINE)

        # Clean up extra whitespace
        clean = ' '.join(clean.split())

        return clean
