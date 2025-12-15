"""
Voice Cloning Configuration for Cartesia TTS.

Enables Tim Kipper's cloned voice for AI sales calls,
creating a scalable version of Tim making calls 24/7.

Usage:
    1. Record 3-5 minutes of audio using the sample script
    2. Upload to Cartesia to create voice clone
    3. Get voice_id from Cartesia dashboard
    4. Configure pipeline with cloned voice

Voice Clone Process:
    1. Go to https://play.cartesia.ai/
    2. Click "Create Voice" > "Clone Voice"
    3. Upload your recording (WAV or MP3, 3-5 min)
    4. Name it "Tim Kipper - Sales"
    5. Copy the voice_id
"""
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import os

logger = logging.getLogger(__name__)


class VoiceEmotion(str, Enum):
    """Cartesia voice emotions for dynamic speech."""
    # Positive emotions
    FRIENDLY = "friendly"
    ENTHUSIASTIC = "enthusiastic"
    EXCITED = "excited"
    CHEERFUL = "cheerful"
    WARM = "warm"

    # Professional emotions
    PROFESSIONAL = "professional"
    CONFIDENT = "confident"
    AUTHORITATIVE = "authoritative"

    # Empathetic emotions
    EMPATHETIC = "empathetic"
    SYMPATHETIC = "sympathetic"
    CARING = "caring"
    REASSURING = "reassuring"

    # Conversational
    CASUAL = "casual"
    CURIOUS = "curious"
    THOUGHTFUL = "thoughtful"

    # Closing emotions
    PERSUASIVE = "persuasive"
    ENCOURAGING = "encouraging"
    APPRECIATIVE = "appreciative"


@dataclass
class VoiceProfile:
    """Configuration for a cloned voice."""
    voice_id: str
    name: str
    description: str = ""

    # Default emotion settings per conversation phase
    greeting_emotion: VoiceEmotion = VoiceEmotion.FRIENDLY
    qualifying_emotion: VoiceEmotion = VoiceEmotion.CURIOUS
    objection_emotion: VoiceEmotion = VoiceEmotion.EMPATHETIC
    closing_emotion: VoiceEmotion = VoiceEmotion.ENTHUSIASTIC
    farewell_emotion: VoiceEmotion = VoiceEmotion.WARM

    # Voice settings
    speed: float = 1.0  # 0.5 to 2.0
    stability: float = 0.75  # Higher = more consistent
    similarity_boost: float = 0.8  # How close to original voice


# Pre-configured voice profiles
VOICE_PROFILES: Dict[str, VoiceProfile] = {
    "tim_kipper": VoiceProfile(
        voice_id=os.getenv("CARTESIA_TIM_VOICE_ID", ""),
        name="Tim Kipper",
        description="Founder voice - warm, professional, trustworthy",
        greeting_emotion=VoiceEmotion.FRIENDLY,
        qualifying_emotion=VoiceEmotion.CURIOUS,
        objection_emotion=VoiceEmotion.EMPATHETIC,
        closing_emotion=VoiceEmotion.ENTHUSIASTIC,
        farewell_emotion=VoiceEmotion.APPRECIATIVE,
        speed=1.0,
        stability=0.8,
        similarity_boost=0.85,
    ),
    "default": VoiceProfile(
        voice_id=os.getenv("CARTESIA_DEFAULT_VOICE_ID", ""),
        name="Alex",
        description="Default sales voice - professional, clear",
        speed=1.0,
        stability=0.7,
        similarity_boost=0.75,
    ),
}


class VoiceCloneManager:
    """
    Manages voice cloning and emotion selection for TTS.

    Features:
    - Multiple voice profiles (Tim, default, etc.)
    - Dynamic emotion based on conversation context
    - Speed and stability control
    - Automatic fallback to default voice
    """

    def __init__(
        self,
        default_profile: str = "tim_kipper",
        cartesia_api_key: Optional[str] = None,
    ):
        self.default_profile = default_profile
        self.api_key = cartesia_api_key or os.getenv("CARTESIA_API_KEY")
        self.profiles = VOICE_PROFILES.copy()

        logger.info(f"VoiceCloneManager initialized with default profile: {default_profile}")

    def get_profile(self, profile_name: Optional[str] = None) -> VoiceProfile:
        """Get a voice profile by name."""
        name = profile_name or self.default_profile
        profile = self.profiles.get(name)

        if not profile:
            logger.warning(f"Profile '{name}' not found, using default")
            profile = self.profiles.get("default") or VoiceProfile(
                voice_id="",
                name="Fallback",
            )

        return profile

    def add_profile(self, name: str, profile: VoiceProfile) -> None:
        """Add a custom voice profile."""
        self.profiles[name] = profile
        logger.info(f"Added voice profile: {name}")

    def get_emotion_for_context(
        self,
        profile: VoiceProfile,
        context: str,
    ) -> VoiceEmotion:
        """
        Select appropriate emotion based on conversation context.

        Args:
            profile: Voice profile to use
            context: Conversation context (greeting, qualifying, objection, closing, farewell)

        Returns:
            Appropriate VoiceEmotion
        """
        emotion_map = {
            "greeting": profile.greeting_emotion,
            "introduction": profile.greeting_emotion,
            "qualifying": profile.qualifying_emotion,
            "discovery": profile.qualifying_emotion,
            "objection": profile.objection_emotion,
            "concern": profile.objection_emotion,
            "closing": profile.closing_emotion,
            "booking": profile.closing_emotion,
            "farewell": profile.farewell_emotion,
            "goodbye": profile.farewell_emotion,
        }

        return emotion_map.get(context.lower(), VoiceEmotion.PROFESSIONAL)

    def get_tts_config(
        self,
        text: str,
        context: str = "professional",
        profile_name: Optional[str] = None,
        emotion_override: Optional[VoiceEmotion] = None,
    ) -> Dict[str, Any]:
        """
        Get TTS configuration for Cartesia API.

        Args:
            text: Text to synthesize
            context: Conversation context for emotion selection
            profile_name: Voice profile to use
            emotion_override: Override automatic emotion selection

        Returns:
            Dict with Cartesia TTS parameters
        """
        profile = self.get_profile(profile_name)
        emotion = emotion_override or self.get_emotion_for_context(profile, context)

        config = {
            "voice_id": profile.voice_id,
            "text": text,
            "emotion": emotion.value,
            "speed": profile.speed,
            "stability": profile.stability,
            "similarity_boost": profile.similarity_boost,
        }

        logger.debug(f"TTS config: voice={profile.name}, emotion={emotion.value}")
        return config


# Sample recording script for voice cloning
VOICE_CLONE_RECORDING_SCRIPT = """
================================================================================
VOICE CLONE RECORDING SCRIPT FOR TIM KIPPER
================================================================================

INSTRUCTIONS:
1. Find a quiet room with minimal echo
2. Use a good microphone (phone is OK, headset is better)
3. Speak naturally - this is how you'll sound on calls
4. Record all sections in one take if possible (3-5 minutes total)
5. Save as WAV or MP3

================================================================================
SECTION 1: INTRODUCTION (60 seconds)
================================================================================

[FRIENDLY, WARM TONE]
"Hi there, this is Tim Kipper calling from Solar Solutions. How are you doing today?"

"Great to hear! I'm reaching out because I noticed your company does solar installations,
and I wanted to connect with you about something that might help your business."

"We help solar installers like yourself generate more qualified leads and close more deals.
Do you have a quick minute to chat?"

================================================================================
SECTION 2: QUALIFYING QUESTIONS (60 seconds)
================================================================================

[CURIOUS, ENGAGED TONE]
"That's really interesting. So tell me, how many installations are you doing per month these days?"

"And what would you say is your biggest challenge right now - is it finding new leads,
closing deals, or something else entirely?"

"I hear that a lot. Many installers we work with were facing the same issue before we
started working together."

================================================================================
SECTION 3: HANDLING OBJECTIONS (60 seconds)
================================================================================

[EMPATHETIC, UNDERSTANDING TONE]
"I totally understand your concern about the pricing. Budget is always an important consideration."

"You know, what we've found is that most of our clients actually see a positive ROI
within the first three months. Would it help if I shared some specific numbers with you?"

"I hear you - now might not be the perfect time. When would be a better time for us
to reconnect and explore this further?"

================================================================================
SECTION 4: CLOSING (60 seconds)
================================================================================

[ENTHUSIASTIC, CONFIDENT TONE]
"This sounds like it could be a great fit! I'd love to show you exactly how this works
in a quick demo."

"I have Tuesday at 2pm or Wednesday at 10am available. Which works better for you?"

"Perfect! I've got you down for Tuesday at 2pm. You'll get a calendar invite shortly.
I'm really looking forward to showing you what we can do."

================================================================================
SECTION 5: FAREWELL (30 seconds)
================================================================================

[WARM, APPRECIATIVE TONE]
"Thanks so much for your time today, I really appreciate it."

"Have a great rest of your day, and I'll talk to you soon!"

"Take care!"

================================================================================
ADDITIONAL PHRASES (Optional - 30 seconds)
================================================================================

[VARIOUS TONES]
"That's a great question."
"Let me think about that for a second."
"Absolutely, I can help with that."
"I completely understand where you're coming from."
"That makes total sense."
"Here's what I'd suggest..."

================================================================================
END OF SCRIPT
================================================================================

TIPS FOR BEST RESULTS:
- Vary your pitch naturally (don't be monotone)
- Include some natural pauses
- Smile while speaking (it comes through in your voice)
- Speak at your normal conversational pace
- Don't read robotically - imagine you're actually on a call

After recording, upload to: https://play.cartesia.ai/
"""


def get_recording_script() -> str:
    """Get the voice clone recording script."""
    return VOICE_CLONE_RECORDING_SCRIPT


def create_tim_profile(voice_id: str) -> VoiceProfile:
    """
    Create Tim Kipper's voice profile after cloning.

    Args:
        voice_id: Voice ID from Cartesia after uploading clone

    Returns:
        Configured VoiceProfile for Tim
    """
    return VoiceProfile(
        voice_id=voice_id,
        name="Tim Kipper",
        description="Founder voice - warm, professional, trustworthy solar sales expert",
        greeting_emotion=VoiceEmotion.FRIENDLY,
        qualifying_emotion=VoiceEmotion.CURIOUS,
        objection_emotion=VoiceEmotion.EMPATHETIC,
        closing_emotion=VoiceEmotion.ENTHUSIASTIC,
        farewell_emotion=VoiceEmotion.APPRECIATIVE,
        speed=1.0,
        stability=0.8,
        similarity_boost=0.85,
    )
