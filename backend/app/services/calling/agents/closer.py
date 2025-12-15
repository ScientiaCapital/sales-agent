"""
CloserAgent - Books meetings with qualified leads.

Responsibilities:
1. Propose available meeting times
2. Handle scheduling preferences
3. Confirm meeting details
4. Trigger post-call review gate
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CloseResult:
    """Result of closing attempt."""
    response: str
    action: str  # propose_times, meeting_confirmed, reschedule, declined
    proposed_times: List[str] = field(default_factory=list)
    meeting_time: Optional[str] = None
    emotion: str = "enthusiastic"


class CloserAgent:
    """
    Books meetings with qualified leads.

    Flow:
    1. Summarize value proposition
    2. Propose 2-3 specific times
    3. Handle their preference
    4. Confirm and set expectations
    """

    def __init__(self, llm_provider: Any):
        self.llm = llm_provider
        self.prompt = self._load_prompt()

    def _load_prompt(self) -> str:
        prompt_path = Path(__file__).parent.parent / "prompts" / "closer.md"
        if prompt_path.exists():
            return prompt_path.read_text()
        return self._default_prompt()

    def _default_prompt(self) -> str:
        return """You are closing a qualified lead by booking a meeting.

Closing Framework:
1. SUMMARIZE: Briefly recap the value they'll get
2. PROPOSE: Offer 2-3 specific times (be concrete)
3. CONFIRM: Repeat back the chosen time
4. SET EXPECTATIONS: Tell them what happens next

Tips:
- Use assumptive language ("When we meet..." not "If we meet...")
- Be specific with times, not vague
- If they hesitate, offer alternative (shorter call, different day)
- Always confirm email for calendar invite"""

    async def close(
        self,
        transcript: str,
        lead_context: Dict[str, Any],
        available_times: Optional[List[str]] = None,
    ) -> CloseResult:
        """Attempt to book a meeting."""
        logger.info(f"Closing lead: {lead_context.get('company_name', 'Unknown')}")

        context = {
            "prompt": self.prompt,
            "transcript": transcript,
            "lead": lead_context,
            "available_times": available_times or [],
        }

        result = await self.llm(context)

        action = result.get("action", "propose_times")
        meeting_time = result.get("meeting_time")

        if action == "meeting_confirmed" and meeting_time:
            logger.info(f"Meeting confirmed for {meeting_time}")
        elif action == "declined":
            logger.info("Lead declined meeting")

        return CloseResult(
            response=result.get("response", ""),
            action=action,
            proposed_times=result.get("proposed_times", []),
            meeting_time=meeting_time,
            emotion=result.get("emotion", "enthusiastic"),
        )
