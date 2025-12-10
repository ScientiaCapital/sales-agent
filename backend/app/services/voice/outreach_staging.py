"""Outreach Staging Service for Human-in-the-Loop workflows.

AI prepares response options, human reviews and approves, then AI executes.
Enables quality control while maintaining AI efficiency.
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class StagedActionType(str, Enum):
    """Types of staged actions."""
    EMAIL = "email"
    SMS = "sms"
    CALL = "call"
    VOICEMAIL_DROP = "voicemail_drop"


class StagedActionStatus(str, Enum):
    """Status of staged actions."""
    PENDING = "pending"  # Awaiting human review
    APPROVED = "approved"  # Human approved, ready to execute
    REJECTED = "rejected"  # Human rejected
    EXECUTED = "executed"  # Action completed
    EXPIRED = "expired"  # Timed out waiting for approval
    EDITED = "edited"  # Human edited and approved


@dataclass
class StagedAction:
    """A staged outreach action awaiting human approval."""
    id: str
    lead_id: str
    action_type: StagedActionType
    status: StagedActionStatus
    content: Dict[str, Any]  # Action-specific content
    created_at: datetime
    created_by: str  # "ai" or user ID
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    notes: Optional[str] = None  # Human reviewer notes


@dataclass
class VMTranscription:
    """Transcription of an inbound voicemail."""
    id: str
    lead_id: str
    recording_url: str
    transcript: str
    duration_seconds: int
    caller_phone: str
    sentiment: Optional[str] = None  # positive, negative, neutral
    intent: Optional[str] = None  # callback_request, inquiry, complaint, etc.
    urgency: Optional[str] = None  # low, medium, high
    created_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ResponseOptions:
    """AI-generated response options for human review."""
    vm_transcription: VMTranscription
    staged_actions: List[StagedAction]
    recommended_action: Optional[str] = None  # ID of recommended action
    analysis_summary: Optional[str] = None


class OutreachStagingService:
    """Service for Human-in-the-Loop outreach workflows.

    Workflow:
    1. Inbound voicemail received → AI transcribes & analyzes
    2. AI stages response options (email, SMS, call, VM drop)
    3. Human reviews staged content in dashboard
    4. Human approves, edits, or rejects
    5. If approved → AI executes the action

    Features:
    - VM transcription with sentiment/intent analysis
    - Multiple response option generation
    - Approval queue management
    - Execution tracking
    - Expiration handling

    Example:
        >>> service = OutreachStagingService()
        >>> options = await service.process_inbound_voicemail(
        ...     recording_url="https://...",
        ...     lead_id="lead_123"
        ... )
        >>> # Human reviews in dashboard, clicks approve
        >>> await service.approve_and_execute(staged_id, "approved")
    """

    def __init__(
        self,
        deepgram_service: Optional[Any] = None,
        cerebras_service: Optional[Any] = None,
        close_sms_client: Optional[Any] = None,
        close_calling_client: Optional[Any] = None,
        voicemail_service: Optional[Any] = None,
        supabase_client: Optional[Any] = None
    ):
        """Initialize outreach staging service.

        Args:
            deepgram_service: For VM transcription
            cerebras_service: For analysis and content generation
            close_sms_client: For SMS execution
            close_calling_client: For call logging
            voicemail_service: For VM drops
            supabase_client: For persistence
        """
        self.deepgram = deepgram_service
        self.cerebras = cerebras_service
        self.sms_client = close_sms_client
        self.calling_client = close_calling_client
        self.vm_service = voicemail_service
        self.supabase = supabase_client

        # In-memory staging (would use Supabase in production)
        self._staged_actions: Dict[str, StagedAction] = {}
        self._vm_transcriptions: Dict[str, VMTranscription] = {}

        logger.info("OutreachStagingService initialized")

    async def process_inbound_voicemail(
        self,
        recording_url: str,
        lead_id: str,
        caller_phone: Optional[str] = None,
        lead_context: Optional[Dict[str, Any]] = None
    ) -> ResponseOptions:
        """Transcribe VM, analyze intent, and stage response options.

        Main entry point for inbound voicemail processing. Creates
        multiple response options for human review.

        Args:
            recording_url: URL to voicemail recording
            lead_id: Close CRM lead ID
            caller_phone: Caller's phone number
            lead_context: Additional lead data from CRM

        Returns:
            ResponseOptions with transcription and staged actions
        """
        # Step 1: Transcribe the voicemail
        transcription = await self._transcribe_voicemail(
            recording_url=recording_url,
            lead_id=lead_id,
            caller_phone=caller_phone or ""
        )

        # Step 2: Analyze intent and sentiment
        analysis = await self._analyze_voicemail(transcription, lead_context)
        transcription.sentiment = analysis.get("sentiment", "neutral")
        transcription.intent = analysis.get("intent", "inquiry")
        transcription.urgency = analysis.get("urgency", "medium")

        # Store transcription
        self._vm_transcriptions[transcription.id] = transcription

        # Step 3: Generate response options
        staged_actions = await self._generate_response_options(
            transcription=transcription,
            lead_context=lead_context
        )

        # Store staged actions
        for action in staged_actions:
            self._staged_actions[action.id] = action

        # Step 4: Determine recommended action
        recommended = self._get_recommended_action(staged_actions, transcription)

        return ResponseOptions(
            vm_transcription=transcription,
            staged_actions=staged_actions,
            recommended_action=recommended,
            analysis_summary=analysis.get("summary")
        )

    async def _transcribe_voicemail(
        self,
        recording_url: str,
        lead_id: str,
        caller_phone: str
    ) -> VMTranscription:
        """Transcribe voicemail audio.

        Args:
            recording_url: URL to voicemail
            lead_id: Lead identifier
            caller_phone: Caller's phone

        Returns:
            VMTranscription object
        """
        transcript = ""
        duration = 0

        # Use Deepgram for transcription if available
        if self.deepgram:
            try:
                result = await self.deepgram.transcribe_url(recording_url)
                transcript = result.get("transcript", "")
                duration = result.get("duration", 0)
            except Exception as e:
                logger.error(f"Deepgram transcription failed: {e}")
                transcript = "[Transcription failed - manual review required]"

        return VMTranscription(
            id=f"vm_{uuid4().hex[:12]}",
            lead_id=lead_id,
            recording_url=recording_url,
            transcript=transcript,
            duration_seconds=duration,
            caller_phone=caller_phone,
            created_at=datetime.utcnow()
        )

    async def _analyze_voicemail(
        self,
        transcription: VMTranscription,
        lead_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Analyze voicemail for intent, sentiment, and urgency.

        Args:
            transcription: VM transcription
            lead_context: Lead data for context

        Returns:
            Dict with sentiment, intent, urgency, summary
        """
        # Default analysis
        analysis = {
            "sentiment": "neutral",
            "intent": "inquiry",
            "urgency": "medium",
            "summary": "Voicemail received from lead."
        }

        if not transcription.transcript:
            return analysis

        transcript_lower = transcription.transcript.lower()

        # Simple rule-based analysis (use Cerebras for production)
        # Sentiment detection
        positive_words = ["thank", "great", "interested", "excited", "love"]
        negative_words = ["frustrated", "angry", "disappointed", "problem", "issue", "urgent"]

        if any(word in transcript_lower for word in negative_words):
            analysis["sentiment"] = "negative"
        elif any(word in transcript_lower for word in positive_words):
            analysis["sentiment"] = "positive"

        # Intent detection
        if any(word in transcript_lower for word in ["call me back", "callback", "return my call"]):
            analysis["intent"] = "callback_request"
        elif any(word in transcript_lower for word in ["price", "pricing", "cost", "quote"]):
            analysis["intent"] = "pricing_inquiry"
        elif any(word in transcript_lower for word in ["demo", "see it", "show me"]):
            analysis["intent"] = "demo_request"
        elif any(word in transcript_lower for word in ["problem", "issue", "help", "support"]):
            analysis["intent"] = "support_request"
        elif any(word in transcript_lower for word in ["cancel", "stop", "unsubscribe"]):
            analysis["intent"] = "cancellation"

        # Urgency detection
        if any(word in transcript_lower for word in ["urgent", "asap", "immediately", "emergency"]):
            analysis["urgency"] = "high"
        elif any(word in transcript_lower for word in ["when you can", "no rush", "whenever"]):
            analysis["urgency"] = "low"

        # Generate summary
        contact_name = lead_context.get("contact_name", "Lead") if lead_context else "Lead"
        analysis["summary"] = (
            f"{contact_name} left a {analysis['sentiment']} voicemail. "
            f"Intent: {analysis['intent'].replace('_', ' ')}. "
            f"Urgency: {analysis['urgency']}."
        )

        return analysis

    async def _generate_response_options(
        self,
        transcription: VMTranscription,
        lead_context: Optional[Dict[str, Any]] = None
    ) -> List[StagedAction]:
        """Generate response options based on VM analysis.

        Args:
            transcription: Analyzed VM transcription
            lead_context: Lead data

        Returns:
            List of staged actions for human review
        """
        contact_name = lead_context.get("contact_name", "there") if lead_context else "there"
        company = lead_context.get("company", "") if lead_context else ""
        our_company = os.getenv("COMPANY_NAME", "Our Team")

        staged_actions = []
        now = datetime.utcnow()

        # Option 1: SMS Response
        sms_content = self._generate_sms_response(transcription, contact_name, our_company)
        staged_actions.append(StagedAction(
            id=f"staged_{uuid4().hex[:12]}",
            lead_id=transcription.lead_id,
            action_type=StagedActionType.SMS,
            status=StagedActionStatus.PENDING,
            content={
                "to": transcription.caller_phone,
                "message": sms_content,
                "template": "vm_response"
            },
            created_at=now,
            created_by="ai",
            metadata={"vm_id": transcription.id}
        ))

        # Option 2: Outbound Call
        call_notes = self._generate_call_notes(transcription, contact_name, company)
        staged_actions.append(StagedAction(
            id=f"staged_{uuid4().hex[:12]}",
            lead_id=transcription.lead_id,
            action_type=StagedActionType.CALL,
            status=StagedActionStatus.PENDING,
            content={
                "to": transcription.caller_phone,
                "script_notes": call_notes,
                "vm_preset": self._select_vm_preset(transcription)
            },
            created_at=now,
            created_by="ai",
            metadata={"vm_id": transcription.id}
        ))

        # Option 3: Voicemail Drop Only (if we can't reach them)
        vm_message = self._generate_vm_message(transcription, contact_name, our_company)
        staged_actions.append(StagedAction(
            id=f"staged_{uuid4().hex[:12]}",
            lead_id=transcription.lead_id,
            action_type=StagedActionType.VOICEMAIL_DROP,
            status=StagedActionStatus.PENDING,
            content={
                "to": transcription.caller_phone,
                "preset_id": self._select_vm_preset(transcription),
                "custom_message": vm_message
            },
            created_at=now,
            created_by="ai",
            metadata={"vm_id": transcription.id}
        ))

        return staged_actions

    def _generate_sms_response(
        self,
        transcription: VMTranscription,
        contact_name: str,
        company: str
    ) -> str:
        """Generate SMS response based on VM intent."""
        intent = transcription.intent or "inquiry"

        if intent == "callback_request":
            return (
                f"Hi {contact_name}, we received your voicemail and will call you back shortly. "
                f"- {company}"
            )
        elif intent == "pricing_inquiry":
            return (
                f"Hi {contact_name}, thanks for your interest in our pricing! "
                f"I'll follow up with details soon. Feel free to reply with any questions. - {company}"
            )
        elif intent == "demo_request":
            return (
                f"Hi {contact_name}, we'd love to show you a demo! "
                f"When works best for you this week? - {company}"
            )
        elif intent == "support_request":
            return (
                f"Hi {contact_name}, we received your message and a team member will "
                f"reach out shortly to help. - {company}"
            )
        else:
            return (
                f"Hi {contact_name}, thanks for your voicemail! "
                f"We'll get back to you soon. - {company}"
            )

    def _generate_call_notes(
        self,
        transcription: VMTranscription,
        contact_name: str,
        company: str
    ) -> str:
        """Generate call script notes based on VM."""
        intent = transcription.intent or "inquiry"
        urgency = transcription.urgency or "medium"

        notes = f"Callback to {contact_name}"
        if company:
            notes += f" at {company}"
        notes += f"\n\nVM Summary: {transcription.transcript[:200]}..."
        notes += f"\n\nIntent: {intent.replace('_', ' ').title()}"
        notes += f"\nUrgency: {urgency.title()}"

        if intent == "callback_request":
            notes += "\n\nTalking points:\n- Acknowledge their VM\n- Ask how you can help\n- Qualify their needs"
        elif intent == "pricing_inquiry":
            notes += "\n\nTalking points:\n- Understand their use case\n- Discuss pricing tiers\n- Offer demo if interested"
        elif intent == "demo_request":
            notes += "\n\nTalking points:\n- Confirm demo interest\n- Schedule convenient time\n- Ask about specific features"

        return notes

    def _generate_vm_message(
        self,
        transcription: VMTranscription,
        contact_name: str,
        company: str
    ) -> str:
        """Generate custom VM message."""
        return (
            f"Hi {contact_name}, this is {company} returning your call. "
            f"We're sorry we missed you. Please call us back or reply to the text message "
            f"we just sent. Looking forward to connecting with you."
        )

    def _select_vm_preset(self, transcription: VMTranscription) -> str:
        """Select appropriate VM preset based on intent."""
        intent = transcription.intent or "inquiry"

        preset_map = {
            "callback_request": "followup_demo",
            "pricing_inquiry": "followup_pricing",
            "demo_request": "followup_demo",
            "support_request": "intro_smb",
            "inquiry": "intro_smb"
        }

        return preset_map.get(intent, "intro_smb")

    def _get_recommended_action(
        self,
        actions: List[StagedAction],
        transcription: VMTranscription
    ) -> Optional[str]:
        """Determine recommended action based on analysis."""
        urgency = transcription.urgency or "medium"
        intent = transcription.intent or "inquiry"

        # High urgency → call
        if urgency == "high":
            for action in actions:
                if action.action_type == StagedActionType.CALL:
                    return action.id

        # Callback request → call
        if intent == "callback_request":
            for action in actions:
                if action.action_type == StagedActionType.CALL:
                    return action.id

        # Demo/pricing → SMS first (less intrusive)
        if intent in ["demo_request", "pricing_inquiry"]:
            for action in actions:
                if action.action_type == StagedActionType.SMS:
                    return action.id

        # Default to SMS
        for action in actions:
            if action.action_type == StagedActionType.SMS:
                return action.id

        return actions[0].id if actions else None

    async def stage_response_options(
        self,
        lead_id: str,
        vm_transcript: str,
        lead_context: Optional[Dict[str, Any]] = None
    ) -> ResponseOptions:
        """Create staged response options from transcript (alternative entry point).

        Use when you already have a transcript and don't need to process audio.

        Args:
            lead_id: Lead identifier
            vm_transcript: Pre-transcribed voicemail
            lead_context: Lead data

        Returns:
            ResponseOptions for human review
        """
        # Create transcription object
        transcription = VMTranscription(
            id=f"vm_{uuid4().hex[:12]}",
            lead_id=lead_id,
            recording_url="",
            transcript=vm_transcript,
            duration_seconds=len(vm_transcript) // 10,  # Estimate
            caller_phone=lead_context.get("phone", "") if lead_context else "",
            created_at=datetime.utcnow()
        )

        # Analyze
        analysis = await self._analyze_voicemail(transcription, lead_context)
        transcription.sentiment = analysis.get("sentiment", "neutral")
        transcription.intent = analysis.get("intent", "inquiry")
        transcription.urgency = analysis.get("urgency", "medium")

        # Store
        self._vm_transcriptions[transcription.id] = transcription

        # Generate options
        staged_actions = await self._generate_response_options(transcription, lead_context)
        for action in staged_actions:
            self._staged_actions[action.id] = action

        recommended = self._get_recommended_action(staged_actions, transcription)

        return ResponseOptions(
            vm_transcription=transcription,
            staged_actions=staged_actions,
            recommended_action=recommended,
            analysis_summary=analysis.get("summary")
        )

    async def get_pending_approvals(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[StagedAction]:
        """Get all staged actions awaiting approval.

        Args:
            user_id: Filter by assigned user (not implemented yet)
            limit: Maximum number to return

        Returns:
            List of pending StagedActions
        """
        pending = [
            action for action in self._staged_actions.values()
            if action.status == StagedActionStatus.PENDING
        ]

        # Sort by created_at descending
        pending.sort(key=lambda a: a.created_at, reverse=True)

        return pending[:limit]

    async def get_staged_action(self, staged_id: str) -> Optional[StagedAction]:
        """Get a specific staged action by ID.

        Args:
            staged_id: Staged action ID

        Returns:
            StagedAction or None
        """
        return self._staged_actions.get(staged_id)

    async def approve_and_execute(
        self,
        staged_id: str,
        action: str,
        reviewer_id: Optional[str] = None,
        edited_content: Optional[Dict[str, Any]] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Process human decision and execute if approved.

        Args:
            staged_id: Staged action ID
            action: "approve", "reject", or "edit"
            reviewer_id: ID of human reviewer
            edited_content: Modified content (for "edit" action)
            notes: Reviewer notes

        Returns:
            Dict with execution result
        """
        staged = self._staged_actions.get(staged_id)
        if not staged:
            return {"success": False, "error": "Staged action not found"}

        now = datetime.utcnow()
        staged.reviewed_by = reviewer_id
        staged.reviewed_at = now
        staged.notes = notes

        if action == "reject":
            staged.status = StagedActionStatus.REJECTED
            logger.info(f"Staged action {staged_id} rejected by {reviewer_id}")
            return {"success": True, "status": "rejected"}

        if action == "edit" and edited_content:
            staged.content = edited_content
            staged.status = StagedActionStatus.EDITED

        staged.status = StagedActionStatus.APPROVED

        # Execute the action
        result = await self._execute_staged_action(staged)

        if result.get("success"):
            staged.status = StagedActionStatus.EXECUTED
            staged.executed_at = datetime.utcnow()
            logger.info(f"Staged action {staged_id} executed successfully")
        else:
            logger.error(f"Staged action {staged_id} execution failed: {result.get('error')}")

        return result

    async def _execute_staged_action(self, staged: StagedAction) -> Dict[str, Any]:
        """Execute an approved staged action.

        Args:
            staged: Approved StagedAction

        Returns:
            Dict with execution result
        """
        try:
            if staged.action_type == StagedActionType.SMS:
                if not self.sms_client:
                    return {"success": False, "error": "SMS client not configured"}

                result = await self.sms_client.send_sms(
                    phone=staged.content.get("to", ""),
                    message=staged.content.get("message", ""),
                    lead_id=staged.lead_id
                )
                return {"success": True, "sms_id": result.get("id"), "type": "sms"}

            elif staged.action_type == StagedActionType.CALL:
                if not self.calling_client:
                    return {"success": False, "error": "Calling client not configured"}

                result = await self.calling_client.trigger_call(
                    phone=staged.content.get("to", ""),
                    lead_id=staged.lead_id,
                    script_notes=staged.content.get("script_notes", "")
                )
                return {"success": True, "call_id": result.get("id"), "type": "call"}

            elif staged.action_type == StagedActionType.VOICEMAIL_DROP:
                if not self.vm_service:
                    return {"success": False, "error": "VM service not configured"}

                # VM drop is part of call flow, just log intent
                return {
                    "success": True,
                    "type": "voicemail_drop",
                    "preset_id": staged.content.get("preset_id"),
                    "note": "VM drop will be triggered during call if machine detected"
                }

            else:
                return {"success": False, "error": f"Unknown action type: {staged.action_type}"}

        except Exception as e:
            logger.error(f"Execution failed for {staged.id}: {e}")
            return {"success": False, "error": str(e)}

    async def trigger_outbound_with_vm_drop(
        self,
        lead_id: str,
        phone: str,
        vm_preset: str,
        script_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Trigger outbound call with VM drop ready.

        Human triggers call → AI handles → drops VM if voicemail detected.

        Args:
            lead_id: Lead identifier
            phone: Phone to call
            vm_preset: VM preset to use if machine detected
            script_notes: Call script notes

        Returns:
            Dict with call initiation result
        """
        if not self.calling_client:
            return {"success": False, "error": "Calling client not configured"}

        try:
            # Trigger call via Close
            result = await self.calling_client.trigger_call(
                phone=phone,
                lead_id=lead_id,
                script_notes=script_notes or f"Outbound call with VM preset: {vm_preset}"
            )

            # Store VM preset for this call (would be retrieved by AMD callback)
            call_id = result.get("id")
            if call_id:
                # In production, store in Redis or Supabase
                logger.info(f"Call {call_id} initiated with VM preset {vm_preset}")

            return {
                "success": True,
                "call_id": call_id,
                "vm_preset": vm_preset,
                "lead_id": lead_id
            }

        except Exception as e:
            logger.error(f"Failed to trigger outbound call: {e}")
            return {"success": False, "error": str(e)}

    async def cancel_staged_action(self, staged_id: str) -> bool:
        """Cancel a pending staged action.

        Args:
            staged_id: Staged action ID

        Returns:
            True if cancelled successfully
        """
        staged = self._staged_actions.get(staged_id)
        if staged and staged.status == StagedActionStatus.PENDING:
            staged.status = StagedActionStatus.REJECTED
            staged.notes = "Cancelled"
            return True
        return False
