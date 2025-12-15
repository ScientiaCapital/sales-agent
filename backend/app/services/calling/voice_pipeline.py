"""
Real-time voice pipeline integrating Twilio, Deepgram STT, and Cartesia TTS.
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from voice_core.providers.deepgram import DeepgramSTT
    from voice_core.providers.cartesia import CartesiaTTS
    from voice_core.providers.twilio import TwilioVoice
except ImportError:
    DeepgramSTT = None
    CartesiaTTS = None
    TwilioVoice = None


@dataclass
class CallState:
    """State for an active call."""
    call_sid: str
    lead_id: str
    current_agent: str = "qualifier"
    transcript: List[str] = field(default_factory=list)


class VoicePipeline:
    """Orchestrates real-time voice AI calls."""

    def __init__(
        self,
        deepgram_api_key: str,
        cartesia_api_key: str,
        twilio_account_sid: str,
        twilio_auth_token: str,
        twilio_from_number: Optional[str] = None,
    ):
        # Track provider availability
        self.deepgram_available = DeepgramSTT is not None
        self.cartesia_available = CartesiaTTS is not None
        self.twilio_available = TwilioVoice is not None

        if self.deepgram_available:
            self.deepgram = DeepgramSTT(api_key=deepgram_api_key)
        else:
            self.deepgram = None
            logger.warning("Deepgram STT not available - voice-core not installed")

        if self.cartesia_available:
            self.cartesia = CartesiaTTS(api_key=cartesia_api_key)
        else:
            self.cartesia = None
            logger.warning("Cartesia TTS not available - voice-core not installed")

        if self.twilio_available:
            self.twilio = TwilioVoice(
                account_sid=twilio_account_sid,
                auth_token=twilio_auth_token,
                from_number=twilio_from_number,
            )
        else:
            self.twilio = None
            logger.warning("Twilio Voice not available - voice-core not installed")

        self.active_calls: Dict[str, CallState] = {}

    async def start_call(
        self,
        to_number: str,
        webhook_url: str,
        lead_id: Optional[str] = None,
    ) -> Dict[str, str]:
        """Initiate an outbound call to a lead."""
        # Check Twilio availability
        if not self.twilio_available or self.twilio is None:
            logger.error("Cannot start call: Twilio provider not available")
            raise RuntimeError(
                "Twilio provider not available. Ensure voice-core is installed."
            )

        logger.info(f"Starting call to {to_number}")

        try:
            result = await self.twilio.make_call(
                to=to_number,
                url=webhook_url,
            )
        except Exception as e:
            logger.error(f"Failed to initiate call to {to_number}: {e}")
            raise

        call_sid = result.get("sid")
        if not call_sid:
            logger.error(f"Twilio API returned no call_sid: {result}")
            raise ValueError("Twilio API did not return a valid call_sid")

        self.active_calls[call_sid] = CallState(
            call_sid=call_sid,
            lead_id=lead_id or "",
        )
        logger.info(f"Call initiated successfully: {call_sid}")

        return {"call_sid": call_sid, "status": "initiated"}

    async def end_call(self, call_sid: str) -> bool:
        """End an active call and cleanup. Returns True if call was active."""
        if call_sid in self.active_calls:
            del self.active_calls[call_sid]
            logger.info(f"Call ended and cleaned up: {call_sid}")
            return True
        logger.warning(f"Attempted to end non-existent call: {call_sid}")
        return False
