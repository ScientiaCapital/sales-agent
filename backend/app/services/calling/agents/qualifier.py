"""
QualifierAgent - Entry point agent for all calls.

Responsibilities:
1. Greet the lead professionally
2. Verify they're the right contact
3. Qualify budget, authority, need, timeline (BANT)
4. Route to ObjectionHandler or Closer based on signals
"""
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class QualificationResult:
    """Result of a qualification turn."""
    next_response: str
    status: str  # gathering_info, qualified, not_qualified, objection
    signals: List[str]
    should_end_call: bool = False
    transfer_to: Optional[str] = None  # "objection_handler", "closer", "human"
    emotion: str = "friendly"  # Cartesia emotion for TTS


class QualifierAgent:
    """
    Qualifies leads through natural conversation.

    Uses BANT framework:
    - Budget: Can they afford our solution?
    - Authority: Are they the decision maker?
    - Need: Do they have a problem we solve?
    - Timeline: When are they looking to act?
    """

    def __init__(self, llm_provider: Any):
        self.llm = llm_provider
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        """Load qualification prompt from file."""
        prompt_path = Path(__file__).parent.parent / "prompts" / "qualifier.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        return self._default_prompt()

    def _default_prompt(self) -> str:
        return """You are a professional sales qualifier for a solar/energy company.

Your job is to:
1. Greet warmly and verify you're speaking with the right person
2. Briefly explain why you're calling (without being pushy)
3. Ask qualifying questions naturally
4. Listen for buying signals and objections

Qualification signals:
- POSITIVE: mentions growth, expanding, frustrated with current solution, budget approved
- NEGATIVE: not interested, wrong person, no budget, just browsing
- OBJECTION: price concern, timing issue, need to check with someone

Always be respectful. If they're not interested, thank them and end gracefully.
Never be pushy or aggressive."""

    async def process_turn(
        self,
        transcript: str,
        lead_context: Dict[str, Any],
        conversation_history: Optional[List[Dict]] = None,
    ) -> QualificationResult:
        """
        Process a conversation turn and decide next action.

        Args:
            transcript: What the lead just said
            lead_context: Company info from Supabase
            conversation_history: Previous turns

        Returns:
            QualificationResult with response and routing decision
        """
        logger.info(f"Processing turn for {lead_context.get('company_name', 'Unknown')}")

        # Build context for LLM
        context = {
            "prompt": self.prompt,
            "lead": lead_context,
            "transcript": transcript,
            "history": conversation_history or [],
        }

        # Get LLM response
        llm_result = await self.llm(context)

        # Parse signals
        status = llm_result.get("qualification_status", "gathering_info")
        signals = llm_result.get("signals", [])

        # Determine routing
        transfer_to = None
        should_end = False

        if status == "not_qualified":
            should_end = True
            logger.info("Lead not qualified - ending call")
        elif "objection" in status.lower() or any("objection" in s for s in signals):
            transfer_to = "objection_handler"
            logger.info("Objection detected - routing to ObjectionHandler")
        elif status == "qualified":
            transfer_to = "closer"
            logger.info("Lead qualified - routing to Closer")
        elif any(s in signals for s in ["human_requested", "angry", "escalate"]):
            transfer_to = "human"
            logger.info("Human transfer requested")

        return QualificationResult(
            next_response=llm_result.get("response", ""),
            status=status,
            signals=signals,
            should_end_call=should_end,
            transfer_to=transfer_to,
            emotion=llm_result.get("emotion", "friendly"),
        )
