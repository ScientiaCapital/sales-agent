"""
Real-time voice pipeline integrating Twilio, STT (Deepgram/AssemblyAI), and Cartesia TTS.

STT Providers:
- Deepgram: Real-time WebSocket streaming, excellent for conversational AI
- AssemblyAI: Real-time streaming with advanced features (sentiment, entity detection)

TTS Provider:
- Cartesia: 58 emotions, ultra-low latency streaming, voice cloning

Voice Cloning:
- Clone Tim Kipper's voice for scalable personalized outreach
- Dynamic emotion based on conversation context

Telephony:
- Twilio: Voice API for outbound/inbound calls
"""
import logging
from typing import Optional, Dict, Any, List, Literal
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# Import voice cloning support
try:
    from .voice_clone import VoiceCloneManager, VoiceProfile, VoiceEmotion
    VOICE_CLONE_AVAILABLE = True
except ImportError:
    VoiceCloneManager = None
    VoiceProfile = None
    VoiceEmotion = None
    VOICE_CLONE_AVAILABLE = False


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

    Voice cloning support:
    - Use Tim Kipper's cloned voice for personalized outreach
    - Dynamic emotion based on conversation context
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
        voice_profile: str = "tim_kipper",
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
            voice_profile: Voice profile to use for TTS (tim_kipper, default)
        """
        self.stt_provider = stt_provider
        self.voice_profile_name = voice_profile

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

        # Initialize Voice Clone Manager
        self.voice_clone_available = VOICE_CLONE_AVAILABLE
        if self.voice_clone_available:
            self.voice_clone_manager = VoiceCloneManager(
                default_profile=voice_profile,
                cartesia_api_key=cartesia_api_key,
            )
            logger.info(f"Voice clone manager initialized with profile: {voice_profile}")
        else:
            self.voice_clone_manager = None
            logger.warning("Voice clone manager not available")

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

    def get_tts_config(
        self,
        text: str,
        context: str = "professional",
        emotion_override: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Get TTS configuration with voice cloning and emotion support.

        Args:
            text: Text to synthesize
            context: Conversation context (greeting, qualifying, objection, closing, farewell)
            emotion_override: Override automatic emotion selection

        Returns:
            Dict with Cartesia TTS parameters including voice_id and emotion
        """
        if self.voice_clone_available and self.voice_clone_manager:
            # Use voice clone manager for emotion-aware config
            emotion = None
            if emotion_override and VoiceEmotion:
                try:
                    emotion = VoiceEmotion(emotion_override)
                except ValueError:
                    logger.warning(f"Unknown emotion: {emotion_override}, using context default")

            return self.voice_clone_manager.get_tts_config(
                text=text,
                context=context,
                emotion_override=emotion,
            )
        else:
            # Fallback to basic config without voice cloning
            return {
                "text": text,
                "voice_id": "",
                "emotion": "professional",
                "speed": 1.0,
            }

    async def generate_tts(
        self,
        text: str,
        context: str = "professional",
        emotion_override: Optional[str] = None,
        stream: bool = True,
    ) -> Any:
        """Generate TTS audio using cloned voice with context-aware emotion.

        Args:
            text: Text to speak
            context: Conversation context for emotion selection
            emotion_override: Override automatic emotion selection
            stream: Whether to stream audio (default True for low latency)

        Returns:
            Audio data or stream from Cartesia
        """
        if not self.cartesia_available or self.cartesia is None:
            logger.error("Cannot generate TTS: Cartesia provider not available")
            raise RuntimeError(
                "Cartesia provider not available. Ensure voice-core is installed."
            )

        # Get voice-cloned TTS config with emotion
        config = self.get_tts_config(
            text=text,
            context=context,
            emotion_override=emotion_override,
        )

        logger.debug(
            f"Generating TTS: voice={self.voice_profile_name}, "
            f"emotion={config.get('emotion')}, text={text[:50]}..."
        )

        try:
            if stream:
                # Streaming mode for low-latency real-time calls
                return await self.cartesia.stream_tts(
                    text=config["text"],
                    voice_id=config["voice_id"],
                    emotion=config.get("emotion"),
                    speed=config.get("speed", 1.0),
                )
            else:
                # Non-streaming mode for complete audio
                return await self.cartesia.generate(
                    text=config["text"],
                    voice_id=config["voice_id"],
                    emotion=config.get("emotion"),
                    speed=config.get("speed", 1.0),
                )
        except Exception as e:
            logger.error(f"TTS generation failed: {e}")
            raise

    def get_voice_profile(self) -> Optional[Any]:
        """Get the current voice profile.

        Returns:
            VoiceProfile if voice cloning is available, None otherwise
        """
        if self.voice_clone_available and self.voice_clone_manager:
            return self.voice_clone_manager.get_profile(self.voice_profile_name)
        return None

    def set_voice_profile(self, profile_name: str) -> bool:
        """Set the active voice profile.

        Args:
            profile_name: Name of the voice profile to use

        Returns:
            True if profile was set successfully
        """
        if self.voice_clone_available and self.voice_clone_manager:
            profile = self.voice_clone_manager.get_profile(profile_name)
            if profile:
                self.voice_profile_name = profile_name
                logger.info(f"Voice profile set to: {profile_name}")
                return True
        logger.warning(f"Could not set voice profile: {profile_name}")
        return False
