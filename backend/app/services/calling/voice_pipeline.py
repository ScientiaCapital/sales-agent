"""
Real-time voice pipeline integrating Twilio, STT (Deepgram/AssemblyAI), and Cartesia TTS.

STT Providers:
- Deepgram: Real-time WebSocket streaming, excellent for conversational AI
- AssemblyAI: Real-time streaming with advanced features (sentiment, entity detection)

TTS Provider:
- Cartesia: 58 emotions, ultra-low latency streaming

Telephony:
- Twilio: Voice API for outbound/inbound calls
"""
import logging
from typing import Optional, Dict, Any, List, Literal
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class STTProvider(str, Enum):
    """Available Speech-to-Text providers."""
    DEEPGRAM = "deepgram"
    ASSEMBLYAI = "assemblyai"


try:
    from voice_core.providers.deepgram import DeepgramSTT
except ImportError:
    DeepgramSTT = None

try:
    from voice_core.providers.assemblyai import AssemblyAISTT
except ImportError:
    AssemblyAISTT = None

try:
    from voice_core.providers.cartesia import CartesiaTTS
except ImportError:
    CartesiaTTS = None

try:
    from voice_core.providers.twilio import TwilioVoice
except ImportError:
    TwilioVoice = None


@dataclass
class CallState:
    """State for an active call."""
    call_sid: str
    lead_id: str
    current_agent: str = "qualifier"
    transcript: List[str] = field(default_factory=list)


class VoicePipeline:
    """Orchestrates real-time voice AI calls.

    Supports multiple STT providers with automatic fallback:
    1. Primary: Deepgram (real-time WebSocket streaming)
    2. Fallback: AssemblyAI (real-time streaming with sentiment/entity detection)
    """

    def __init__(
        self,
        deepgram_api_key: Optional[str] = None,
        cartesia_api_key: str = "",
        twilio_account_sid: str = "",
        twilio_auth_token: str = "",
        twilio_from_number: Optional[str] = None,
        assemblyai_api_key: Optional[str] = None,
        stt_provider: STTProvider = STTProvider.DEEPGRAM,
    ):
        """Initialize the voice pipeline with provider credentials.

        Args:
            deepgram_api_key: Deepgram API key for STT
            cartesia_api_key: Cartesia API key for TTS
            twilio_account_sid: Twilio account SID
            twilio_auth_token: Twilio auth token
            twilio_from_number: Twilio phone number to call from
            assemblyai_api_key: AssemblyAI API key for STT (alternative)
            stt_provider: Preferred STT provider (deepgram or assemblyai)
        """
        self.stt_provider = stt_provider

        # Track provider availability
        self.deepgram_available = DeepgramSTT is not None and deepgram_api_key
        self.assemblyai_available = AssemblyAISTT is not None and assemblyai_api_key
        self.cartesia_available = CartesiaTTS is not None
        self.twilio_available = TwilioVoice is not None

        # Initialize Deepgram STT
        if self.deepgram_available:
            self.deepgram = DeepgramSTT(api_key=deepgram_api_key)
            logger.info("Deepgram STT initialized")
        else:
            self.deepgram = None
            if deepgram_api_key:
                logger.warning("Deepgram STT not available - voice-core not installed")

        # Initialize AssemblyAI STT
        if self.assemblyai_available:
            self.assemblyai = AssemblyAISTT(api_key=assemblyai_api_key)
            logger.info("AssemblyAI STT initialized")
        else:
            self.assemblyai = None
            if assemblyai_api_key:
                logger.warning("AssemblyAI STT not available - voice-core not installed")

        # Initialize Cartesia TTS
        if self.cartesia_available:
            self.cartesia = CartesiaTTS(api_key=cartesia_api_key)
            logger.info("Cartesia TTS initialized")
        else:
            self.cartesia = None
            logger.warning("Cartesia TTS not available - voice-core not installed")

        # Initialize Twilio Voice
        if self.twilio_available:
            self.twilio = TwilioVoice(
                account_sid=twilio_account_sid,
                auth_token=twilio_auth_token,
                from_number=twilio_from_number,
            )
            logger.info("Twilio Voice initialized")
        else:
            self.twilio = None
            logger.warning("Twilio Voice not available - voice-core not installed")

        self.active_calls: Dict[str, CallState] = {}

        # Log active STT provider
        self._log_stt_status()

    def _log_stt_status(self) -> None:
        """Log which STT provider will be used."""
        if self.stt_provider == STTProvider.DEEPGRAM and self.deepgram_available:
            logger.info("Using Deepgram as primary STT provider")
        elif self.stt_provider == STTProvider.ASSEMBLYAI and self.assemblyai_available:
            logger.info("Using AssemblyAI as primary STT provider")
        elif self.deepgram_available:
            logger.info("Falling back to Deepgram STT")
        elif self.assemblyai_available:
            logger.info("Falling back to AssemblyAI STT")
        else:
            logger.warning("No STT provider available!")

    def get_active_stt(self):
        """Get the active STT provider instance.

        Returns the preferred provider if available, otherwise falls back.
        """
        if self.stt_provider == STTProvider.DEEPGRAM:
            if self.deepgram_available:
                return self.deepgram
            elif self.assemblyai_available:
                logger.warning("Deepgram unavailable, falling back to AssemblyAI")
                return self.assemblyai
        elif self.stt_provider == STTProvider.ASSEMBLYAI:
            if self.assemblyai_available:
                return self.assemblyai
            elif self.deepgram_available:
                logger.warning("AssemblyAI unavailable, falling back to Deepgram")
                return self.deepgram
        return None

    @property
    def stt_available(self) -> bool:
        """Check if any STT provider is available."""
        return self.deepgram_available or self.assemblyai_available

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
