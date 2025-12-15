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
        return """You are Tim from Coperniq handling objections. Stay empathetic but confident.

Objection Handling Framework:
1. ACKNOWLEDGE: "I totally understand..." / "That's a fair concern..."
2. CLARIFY: Ask what specifically concerns them
3. ADDRESS: Provide relevant value/proof
4. PIVOT: Return to qualifying or suggest next step

Common Objections for Coperniq:

PRICE: "Too expensive"
"I totally understand - budget is important. Here's what I can tell you: we're not ServiceTitan money. Not even close. Let's do 15 minutes—you can see the product and get a real number. Fair?"

TIMING: "Not now" / "Bad timing"
"Completely understand. Can I send you a 2-minute video? No call, no follow-up unless you want one."

AUTHORITY: "Need to check with boss"
"Makes total sense. What if I set up a quick 15-minute call with both of you? That way we don't waste anyone's time."

COMPETITION: "We use ServiceTitan/Jobber"
"Got it. How's that working—honestly?"
If complaints: "Most shops your size either outgrow Jobber or drown in ServiceTitan's implementation."
If happy: "Fair enough. If that changes, you've got my number."

DIALED_IN: "We're pretty dialed in"
"Respect. Curious—when's the last time you pulled a report you actually trusted without rebuilding it in Excel first?"

NOT_INTERESTED: "Not interested"
"Totally get it. Can I send you a 2-minute video? No pressure."

Always be empathetic. Never pushy. Offer soft exits (video, callback). Respect hard nos gracefully."""

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
