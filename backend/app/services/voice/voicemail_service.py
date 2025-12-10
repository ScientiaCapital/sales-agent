"""Voicemail Drop Service for AI voice calls.

Handles answering machine detection (AMD) and pre-recorded voicemail drops.
Integrates with Twilio for AMD and Supabase for VM preset storage.
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any

import httpx

logger = logging.getLogger(__name__)


class AMDResult(str, Enum):
    """Twilio Answering Machine Detection results."""
    HUMAN = "human"
    MACHINE_START = "machine_start"
    MACHINE_END_BEEP = "machine_end_beep"
    MACHINE_END_SILENCE = "machine_end_silence"
    MACHINE_END_OTHER = "machine_end_other"
    FAX = "fax"
    UNKNOWN = "unknown"


class VMDropStatus(str, Enum):
    """Voicemail drop status."""
    PENDING = "pending"
    PLAYING = "playing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # Human answered, no VM needed


@dataclass
class VMPreset:
    """Voicemail preset configuration."""
    id: str
    name: str
    description: str
    audio_url: str
    duration_seconds: int
    segment: str  # Lead segment (e.g., "enterprise", "smb", "trial")
    active: bool = True
    created_at: Optional[datetime] = None


@dataclass
class VMDropResult:
    """Result of a voicemail drop operation."""
    call_sid: str
    preset_id: str
    status: VMDropStatus
    amd_result: Optional[AMDResult] = None
    duration_played: Optional[int] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None


# Default VM presets (can be stored in Supabase for production)
DEFAULT_VM_PRESETS: Dict[str, VMPreset] = {
    "intro_enterprise": VMPreset(
        id="vm_intro_enterprise",
        name="Enterprise Introduction",
        description="Professional intro for enterprise prospects",
        audio_url="",  # Set via environment or Supabase
        duration_seconds=30,
        segment="enterprise"
    ),
    "intro_smb": VMPreset(
        id="vm_intro_smb",
        name="SMB Introduction",
        description="Friendly intro for small/medium businesses",
        audio_url="",
        duration_seconds=25,
        segment="smb"
    ),
    "followup_demo": VMPreset(
        id="vm_followup_demo",
        name="Demo Follow-up",
        description="Follow-up after demo request",
        audio_url="",
        duration_seconds=20,
        segment="demo"
    ),
    "followup_pricing": VMPreset(
        id="vm_followup_pricing",
        name="Pricing Follow-up",
        description="Follow-up after pricing inquiry",
        audio_url="",
        duration_seconds=22,
        segment="pricing"
    ),
    "reengagement": VMPreset(
        id="vm_reengagement",
        name="Re-engagement",
        description="Re-engage cold leads",
        audio_url="",
        duration_seconds=28,
        segment="cold"
    ),
}


class VoicemailDropService:
    """Service for managing voicemail drops during outbound calls.

    Features:
    - Answering Machine Detection (AMD) via Twilio
    - Pre-recorded voicemail drops
    - A/B testing of VM messages
    - Segment-based VM selection
    - Success tracking for optimization

    Example:
        >>> service = VoicemailDropService()
        >>> # Check AMD result from Twilio callback
        >>> is_machine = await service.detect_answering_machine("CA123", "machine_end_beep")
        >>> if is_machine:
        ...     result = await service.drop_voicemail("CA123", "intro_enterprise")
    """

    def __init__(
        self,
        twilio_account_sid: Optional[str] = None,
        twilio_auth_token: Optional[str] = None,
        supabase_client: Optional[Any] = None
    ):
        """Initialize voicemail drop service.

        Args:
            twilio_account_sid: Twilio account SID (or from env)
            twilio_auth_token: Twilio auth token (or from env)
            supabase_client: Optional Supabase client for preset storage
        """
        self.account_sid = twilio_account_sid or os.getenv("TWILIO_ACCOUNT_SID")
        self.auth_token = twilio_auth_token or os.getenv("TWILIO_AUTH_TOKEN")
        self.supabase = supabase_client

        # VM presets (loaded from Supabase or defaults)
        self._presets: Dict[str, VMPreset] = DEFAULT_VM_PRESETS.copy()

        # A/B test tracking
        self._ab_tests: Dict[str, List[str]] = {}

        logger.info("VoicemailDropService initialized")

    async def detect_answering_machine(
        self,
        call_sid: str,
        amd_status: str
    ) -> bool:
        """Process AMD result from Twilio callback.

        Called from Twilio's async AMD status callback to determine
        if the call was answered by a machine.

        Args:
            call_sid: Twilio call SID
            amd_status: AMD status from Twilio callback:
                - human: Human answered
                - machine_start: Machine detected, still talking
                - machine_end_beep: Machine greeting ended with beep
                - machine_end_silence: Machine greeting ended with silence
                - machine_end_other: Machine greeting ended otherwise
                - fax: Fax machine detected
                - unknown: Could not determine

        Returns:
            True if machine detected and ready for VM drop, False otherwise
        """
        try:
            result = AMDResult(amd_status.lower())
        except ValueError:
            result = AMDResult.UNKNOWN

        logger.info(f"AMD result for {call_sid}: {result.value}")

        # Machine detected and ready for VM drop
        if result in [
            AMDResult.MACHINE_END_BEEP,
            AMDResult.MACHINE_END_SILENCE,
            AMDResult.MACHINE_END_OTHER
        ]:
            return True

        # Human answered - no VM needed
        if result == AMDResult.HUMAN:
            logger.info(f"Human answered call {call_sid}")
            return False

        # Fax or unknown - skip VM
        if result in [AMDResult.FAX, AMDResult.UNKNOWN]:
            logger.warning(f"Call {call_sid} AMD result: {result.value}, skipping VM")
            return False

        # Machine still talking (machine_start) - wait for end
        if result == AMDResult.MACHINE_START:
            logger.info(f"Machine detected on {call_sid}, waiting for greeting to end")
            return False

        return False

    async def drop_voicemail(
        self,
        call_sid: str,
        preset_id: str
    ) -> VMDropResult:
        """Play pre-recorded voicemail and end call.

        Uses Twilio's REST API to modify the call and play the VM audio,
        then hangs up after the message completes.

        Args:
            call_sid: Twilio call SID
            preset_id: VM preset ID (e.g., "intro_enterprise")

        Returns:
            VMDropResult with status and details
        """
        # Get preset
        preset = self._presets.get(preset_id)
        if not preset:
            logger.error(f"VM preset not found: {preset_id}")
            return VMDropResult(
                call_sid=call_sid,
                preset_id=preset_id,
                status=VMDropStatus.FAILED,
                error=f"Preset not found: {preset_id}",
                timestamp=datetime.utcnow()
            )

        if not preset.audio_url:
            logger.error(f"VM preset {preset_id} has no audio URL configured")
            return VMDropResult(
                call_sid=call_sid,
                preset_id=preset_id,
                status=VMDropStatus.FAILED,
                error="No audio URL configured for preset",
                timestamp=datetime.utcnow()
            )

        if not self.account_sid or not self.auth_token:
            logger.error("Twilio credentials not configured")
            return VMDropResult(
                call_sid=call_sid,
                preset_id=preset_id,
                status=VMDropStatus.FAILED,
                error="Twilio credentials not configured",
                timestamp=datetime.utcnow()
            )

        try:
            # Generate TwiML to play VM and hang up
            twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Play>{preset.audio_url}</Play>
    <Hangup/>
</Response>"""

            # Update call with TwiML
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Calls/{call_sid}.json",
                    auth=(self.account_sid, self.auth_token),
                    data={"Twiml": twiml},
                    timeout=30.0
                )

                if response.status_code == 200:
                    logger.info(f"VM drop initiated for {call_sid}: {preset_id}")
                    return VMDropResult(
                        call_sid=call_sid,
                        preset_id=preset_id,
                        status=VMDropStatus.PLAYING,
                        duration_played=preset.duration_seconds,
                        timestamp=datetime.utcnow()
                    )
                else:
                    error_msg = response.text
                    logger.error(f"Twilio VM drop failed: {response.status_code} - {error_msg}")
                    return VMDropResult(
                        call_sid=call_sid,
                        preset_id=preset_id,
                        status=VMDropStatus.FAILED,
                        error=f"Twilio API error: {response.status_code}",
                        timestamp=datetime.utcnow()
                    )

        except Exception as e:
            logger.error(f"VM drop error for {call_sid}: {e}")
            return VMDropResult(
                call_sid=call_sid,
                preset_id=preset_id,
                status=VMDropStatus.FAILED,
                error=str(e),
                timestamp=datetime.utcnow()
            )

    async def get_vm_preset(
        self,
        lead_id: str,
        lead_segment: Optional[str] = None,
        previous_interactions: Optional[int] = None
    ) -> str:
        """Select appropriate VM preset based on lead data.

        Uses segment, interaction history, and A/B testing to select
        the most appropriate voicemail message.

        Args:
            lead_id: Lead identifier
            lead_segment: Lead segment (enterprise, smb, etc.)
            previous_interactions: Number of previous call attempts

        Returns:
            VM preset ID to use
        """
        # Check for A/B test assignment
        if lead_id in self._ab_tests:
            test_presets = self._ab_tests[lead_id]
            if test_presets:
                # Return assigned test variant
                return test_presets[0]

        # Select based on segment
        segment_map = {
            "enterprise": "intro_enterprise",
            "smb": "intro_smb",
            "demo": "followup_demo",
            "pricing": "followup_pricing",
            "cold": "reengagement",
            "trial": "intro_smb",
        }

        if lead_segment and lead_segment.lower() in segment_map:
            return segment_map[lead_segment.lower()]

        # Select based on interaction count (re-engagement for cold leads)
        if previous_interactions and previous_interactions >= 3:
            return "reengagement"

        # Default to SMB intro
        return "intro_smb"

    async def register_ab_test(
        self,
        test_name: str,
        preset_ids: List[str],
        lead_ids: List[str]
    ) -> Dict[str, str]:
        """Register leads for A/B testing VM messages.

        Assigns leads to different VM presets for testing effectiveness.

        Args:
            test_name: Name of the A/B test
            preset_ids: List of preset IDs to test
            lead_ids: List of lead IDs to include in test

        Returns:
            Dict mapping lead_id to assigned preset_id
        """
        assignments = {}

        for i, lead_id in enumerate(lead_ids):
            # Simple round-robin assignment
            preset_id = preset_ids[i % len(preset_ids)]
            self._ab_tests[lead_id] = [preset_id]
            assignments[lead_id] = preset_id

        logger.info(f"A/B test '{test_name}' registered: {len(assignments)} leads")
        return assignments

    async def get_preset(self, preset_id: str) -> Optional[VMPreset]:
        """Get a VM preset by ID.

        Args:
            preset_id: Preset identifier

        Returns:
            VMPreset or None if not found
        """
        return self._presets.get(preset_id)

    async def list_presets(self, active_only: bool = True) -> List[VMPreset]:
        """List all available VM presets.

        Args:
            active_only: Only return active presets

        Returns:
            List of VMPreset objects
        """
        presets = list(self._presets.values())
        if active_only:
            presets = [p for p in presets if p.active]
        return presets

    async def add_preset(self, preset: VMPreset) -> VMPreset:
        """Add a new VM preset.

        Args:
            preset: VMPreset to add

        Returns:
            Added VMPreset
        """
        self._presets[preset.id] = preset
        logger.info(f"VM preset added: {preset.id}")
        return preset

    async def update_preset_audio_url(
        self,
        preset_id: str,
        audio_url: str
    ) -> Optional[VMPreset]:
        """Update the audio URL for a preset.

        Args:
            preset_id: Preset to update
            audio_url: New audio URL

        Returns:
            Updated VMPreset or None if not found
        """
        preset = self._presets.get(preset_id)
        if preset:
            # Create new preset with updated URL (dataclass is immutable-ish)
            updated = VMPreset(
                id=preset.id,
                name=preset.name,
                description=preset.description,
                audio_url=audio_url,
                duration_seconds=preset.duration_seconds,
                segment=preset.segment,
                active=preset.active,
                created_at=preset.created_at
            )
            self._presets[preset_id] = updated
            logger.info(f"VM preset {preset_id} audio URL updated")
            return updated
        return None

    async def track_vm_result(
        self,
        result: VMDropResult,
        lead_id: str,
        callback_received: bool = False
    ) -> Dict[str, Any]:
        """Track VM drop result for analytics.

        Logs the result for tracking success rates and optimizing
        VM preset selection.

        Args:
            result: VMDropResult from drop_voicemail
            lead_id: Lead identifier
            callback_received: Whether lead called back

        Returns:
            Dict with tracking data
        """
        tracking_data = {
            "call_sid": result.call_sid,
            "lead_id": lead_id,
            "preset_id": result.preset_id,
            "status": result.status.value,
            "amd_result": result.amd_result.value if result.amd_result else None,
            "duration_played": result.duration_played,
            "callback_received": callback_received,
            "timestamp": result.timestamp.isoformat() if result.timestamp else None,
            "error": result.error
        }

        logger.info(f"VM drop tracked: {tracking_data}")

        # In production, store to Supabase
        if self.supabase:
            try:
                # Would insert to voicemail_drops table
                pass
            except Exception as e:
                logger.error(f"Failed to store VM tracking: {e}")

        return tracking_data
