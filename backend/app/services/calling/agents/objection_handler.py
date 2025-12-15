"""
ObjectionHandlerAgent - Handles common sales objections.

Objection types:
- Price: "Too expensive"
- Timing: "Not now"
- Authority: "Need to check with boss"
- Competition: "Using someone else"
- Trust: "Never heard of you"
"""
import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ObjectionResult:
    """Result of objection handling."""
    response: str
    objection_type: str
    objection_handled: bool
    next_action: str  # continue_qualifying, schedule_callback, transfer_closer, end_call, schedule_with_dm
    emotion: str = "empathetic"


class ObjectionHandlerAgent:
    """
    Handles objections with empathy and pivots.

    Strategy:
    1. Acknowledge the concern (don't dismiss)
    2. Ask clarifying question or provide value
    3. Pivot back to qualification or close
    """

    def __init__(self, llm_provider: Any):
        self.llm = llm_provider
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "objection_handler.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        return self._default_prompt()

    def _default_prompt(self) -> str:
        return """You handle sales objections with empathy.

Objection Handling Framework:
1. ACKNOWLEDGE: "I totally understand..." / "That's a fair concern..."
2. CLARIFY: Ask what specifically concerns them
3. ADDRESS: Provide relevant value/proof
4. PIVOT: Return to qualifying or suggest next step

Common Objections:
- PRICE: Focus on ROI, payment plans, cost of inaction
- TIMING: Offer callback, understand their timeline
- AUTHORITY: Offer to include decision maker
- COMPETITION: Ask what they like/dislike about current
- TRUST: Share testimonials, offer trial/demo"""

    async def handle_objection(
        self,
        transcript: str,
        objection_context: Dict[str, Any],
        lead_context: Optional[Dict] = None,
    ) -> ObjectionResult:
        """Handle an objection and determine next action."""
        logger.info(f"Handling objection type: {objection_context.get('type', 'unknown')}")

        context = {
            "prompt": self.prompt,
            "transcript": transcript,
            "objection": objection_context,
            "lead": lead_context or {},
        }

        result = await self.llm(context)

        objection_handled = result.get("objection_handled", False)
        next_action = result.get("next_action", "continue_qualifying")

        if objection_handled:
            logger.info(f"Objection handled, next action: {next_action}")
        else:
            logger.info("Objection not handled, may need to end call")

        return ObjectionResult(
            response=result.get("response", ""),
            objection_type=result.get("objection_type", "unknown"),
            objection_handled=objection_handled,
            next_action=next_action,
            emotion=result.get("emotion", "empathetic"),
        )
