"""
QualifierAgent - Entry point agent for all calls.

Responsibilities:
1. Greet the lead professionally
2. Verify they're the right contact
3. Qualify budget, authority, need, timeline (BANT)
4. Route to ObjectionHandler or Closer based on signals

Workflow Types:
- cold_outreach: Following up on Max's emails (Frankenstack)
- warm_inbound: Lead came through recently (clicked, signed up)
- cold_call: No prior contact, opening with trade qualification
"""
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path
from enum import Enum

logger = logging.getLogger(__name__)


class WorkflowType(str, Enum):
    """Available calling workflows based on lead source."""
    COLD_OUTREACH = "cold_outreach"  # Following up on Max's emails
    WARM_INBOUND = "warm_inbound"    # Lead clicked/came through
    COLD_CALL = "cold_call"          # No prior contact


@dataclass
class QualificationResult:
    """Result of a qualification turn."""
    next_response: str
    status: str  # gathering_info, qualified, not_qualified, objection
    signals: List[str]
    should_end_call: bool = False
    transfer_to: Optional[str] = None  # "objection_handler", "closer", "human"
    emotion: str = "friendly"  # Cartesia emotion for TTS
    # Coperniq-specific fields
    pain_points: List[str] = field(default_factory=list)  # dispatch, qbo_sync, reporting, etc.
    demo_type: str = ""  # specific_pain, full_demo, video_only
    trade_type: str = ""  # multi_trade, single_trade
    current_tools: List[str] = field(default_factory=list)  # servicetitan, jobber, etc.
    next_action: str = "continue"  # continue, book_meeting, send_video, end_call


class QualifierAgent:
    """
    Qualifies leads through natural conversation.

    Supports multiple workflows:
    - cold_outreach: Following up on Max's emails (Frankenstack)
    - warm_inbound: Lead clicked/came through recently
    - cold_call: No prior contact, opening with trade qualification
    """

    # Workflow prompt file mapping
    WORKFLOW_PROMPTS = {
        WorkflowType.COLD_OUTREACH: "cold_outreach.md",
        WorkflowType.WARM_INBOUND: "warm_inbound.md",
        WorkflowType.COLD_CALL: "cold_call.md",
    }

    # Map prompt emotions to Cartesia TTS voice emotions
    EMOTION_MAP = {
        "curiosity": "curious",
        "empathy": "empathetic",
        "determination": "confident",
        "warmth": "warm",
        "enthusiasm": "enthusiastic",
        "gratitude": "appreciative",
        "joy": "excited",
        "sadness": "sympathetic",
        "professional": "professional",
        "friendly": "friendly",
        "confident": "confident",
    }

    def __init__(
        self,
        llm_provider: Any,
        workflow: WorkflowType = WorkflowType.COLD_CALL,
    ):
        self.llm = llm_provider
        self.workflow = workflow
        self.prompt = self._load_prompt(workflow)
        logger.info(f"QualifierAgent initialized with workflow: {workflow.value}")

    def _load_prompt(self, workflow: WorkflowType) -> str:
        """Load workflow-specific prompt from file."""
        prompt_file = self.WORKFLOW_PROMPTS.get(workflow, "cold_call.md")
        prompt_path = Path(__file__).parent.parent / "prompts" / prompt_file
        if prompt_path.exists():
            logger.debug(f"Loading prompt from {prompt_path}")
            return prompt_path.read_text()
        logger.warning(f"Prompt file not found: {prompt_path}, using default")
        return self._default_prompt()

    def set_workflow(self, workflow: WorkflowType) -> None:
        """Change the active workflow and reload prompt."""
        self.workflow = workflow
        self.prompt = self._load_prompt(workflow)
        logger.info(f"Workflow changed to: {workflow.value}")

    def _map_emotion_to_cartesia(self, prompt_emotion: str) -> str:
        """Map prompt emotion names to Cartesia voice emotions.

        Args:
            prompt_emotion: Emotion from prompt (e.g., "curiosity", "empathy")

        Returns:
            Cartesia-compatible emotion string
        """
        # Handle compound emotions (e.g., "empathy + curiosity")
        if "+" in prompt_emotion:
            primary = prompt_emotion.split("+")[0].strip()
            return self.EMOTION_MAP.get(primary, "professional")
        return self.EMOTION_MAP.get(prompt_emotion, "professional")

    @staticmethod
    def detect_workflow(lead_context: Dict[str, Any]) -> WorkflowType:
        """Auto-detect workflow based on lead context.

        Args:
            lead_context: Lead information from CRM

        Returns:
            Appropriate WorkflowType
        """
        source = lead_context.get("source", "").lower()
        sequence = lead_context.get("sequence", "").lower()
        last_activity = lead_context.get("last_activity", "").lower()

        # Max email follow-up
        if "max" in sequence or "frankenstack" in sequence:
            return WorkflowType.COLD_OUTREACH

        # Warm inbound (recent activity)
        if any(indicator in source for indicator in ["inbound", "website", "demo_request", "signup"]):
            return WorkflowType.WARM_INBOUND
        if any(indicator in last_activity for indicator in ["clicked", "opened", "visited"]):
            return WorkflowType.WARM_INBOUND

        # Default to cold call
        return WorkflowType.COLD_CALL

    def _default_prompt(self) -> str:
        return """You are Tim from Coperniq - all-in-one platform for contractors.

Target: Contractors doing $5-50M, multiple trades (resi + commercial).

Pain points to identify:
- Dispatch breaking at 5+ techs
- QuickBooks sync issues
- Reports rebuilt in Excel
- Asset history in spreadsheets
- Multiple disconnected systems

Opening: "Hey [Name], Tim with Coperniq. Quick question—you guys running multiple trades? Resi and commercial?"

Goal: Book a 15-minute demo via Calendly.

Be direct, not salesy. If they're not interested, exit gracefully."""

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
        company_name = lead_context.get("company_name", "Unknown")
        logger.info(f"Processing turn for {company_name} (workflow: {self.workflow.value})")

        # Build context for LLM
        context = {
            "prompt": self.prompt,
            "lead": lead_context,
            "transcript": transcript,
            "history": conversation_history or [],
            "workflow": self.workflow.value,
        }

        # Get LLM response
        llm_result = await self.llm(context)

        # Parse signals
        status = llm_result.get("qualification_status", llm_result.get("status", "gathering_info"))
        signals = llm_result.get("signals", [])

        # Determine routing
        transfer_to = None
        should_end = False
        next_action = llm_result.get("next_action", "continue")

        if status == "not_qualified" or next_action == "end_call":
            should_end = True
            logger.info("Lead not qualified - ending call")
        elif "objection" in status.lower() or any("objection" in s for s in signals):
            transfer_to = "objection_handler"
            logger.info("Objection detected - routing to ObjectionHandler")
        elif status == "qualified" or next_action == "book_meeting":
            transfer_to = "closer"
            logger.info("Lead qualified - routing to Closer")
        elif any(s in signals for s in ["human_requested", "angry", "escalate"]):
            transfer_to = "human"
            logger.info("Human transfer requested")

        # Map LLM emotion to Cartesia-compatible emotion
        raw_emotion = llm_result.get("emotion", "friendly")
        cartesia_emotion = self._map_emotion_to_cartesia(raw_emotion)

        return QualificationResult(
            next_response=llm_result.get("response", ""),
            status=status,
            signals=signals,
            should_end_call=should_end,
            transfer_to=transfer_to,
            emotion=cartesia_emotion,
            pain_points=llm_result.get("pain_points", []),
            demo_type=llm_result.get("demo_type", ""),
            trade_type=llm_result.get("trade_type", ""),
            current_tools=llm_result.get("current_tools", []),
            next_action=next_action,
        )

    def get_opening(self, lead_context: Dict[str, Any]) -> str:
        """Get the opening line for the current workflow.

        Args:
            lead_context: Lead information

        Returns:
            Opening script with lead name interpolated
        """
        name = lead_context.get("contact_name", lead_context.get("name", "there"))

        if self.workflow == WorkflowType.COLD_OUTREACH:
            return f"Hey {name}, Tim with Coperniq. Max sent you a couple emails about your Frankenstack—ring any bells?"
        elif self.workflow == WorkflowType.WARM_INBOUND:
            return f"Hey {name}, Tim with Coperniq. You came through recently—wanted to catch you while it's fresh. What made you click?"
        else:  # COLD_CALL
            return f"Hey {name}, Tim with Coperniq. Quick question—you guys running multiple trades? Resi and commercial?"

    def get_voicemail(self, lead_context: Dict[str, Any]) -> str:
        """Get the voicemail script for the current workflow.

        Args:
            lead_context: Lead information

        Returns:
            Voicemail script (under 20 seconds)
        """
        name = lead_context.get("contact_name", lead_context.get("name", "there"))

        if self.workflow == WorkflowType.COLD_OUTREACH:
            return f"Hey {name}, Tim with Coperniq—following up on Max's emails about your Frankenstack. If any of that landed, call me back. If not, I'll leave you alone. 415-430-9465."
        elif self.workflow == WorkflowType.WARM_INBOUND:
            return f"Hey {name}, Tim with Coperniq. You came through recently—I'd love to know what made you click. Call me back and I'll make sure you get exactly what you need. 415-430-9465."
        else:  # COLD_CALL
            return f"Hey {name}, Tim with Coperniq. Most contractors I talk to doing $5-50M are juggling 3 systems and trust none of them. If that's you—call me back. If not, I'll leave you alone. 415-430-9465."
