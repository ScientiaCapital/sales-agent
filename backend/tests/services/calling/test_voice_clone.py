"""Tests for Voice Cloning module."""
import pytest
from unittest.mock import MagicMock, patch
from app.services.calling.voice_clone import (
    VoiceCloneManager,
    VoiceProfile,
    VoiceEmotion,
    VOICE_PROFILES,
    get_recording_script,
    create_tim_profile,
)


def test_voice_emotion_enum():
    """VoiceEmotion should have expected values."""
    assert VoiceEmotion.FRIENDLY.value == "friendly"
    assert VoiceEmotion.EMPATHETIC.value == "empathetic"
    assert VoiceEmotion.ENTHUSIASTIC.value == "enthusiastic"
    assert VoiceEmotion.PROFESSIONAL.value == "professional"
    assert VoiceEmotion.CURIOUS.value == "curious"


def test_voice_profile_dataclass():
    """VoiceProfile should initialize with proper defaults."""
    profile = VoiceProfile(
        voice_id="test_voice_123",
        name="Test Voice",
    )

    assert profile.voice_id == "test_voice_123"
    assert profile.name == "Test Voice"
    assert profile.greeting_emotion == VoiceEmotion.FRIENDLY
    assert profile.qualifying_emotion == VoiceEmotion.CURIOUS
    assert profile.objection_emotion == VoiceEmotion.EMPATHETIC
    assert profile.closing_emotion == VoiceEmotion.ENTHUSIASTIC
    assert profile.farewell_emotion == VoiceEmotion.WARM
    assert profile.speed == 1.0
    assert profile.stability == 0.75
    assert profile.similarity_boost == 0.8


def test_voice_profile_custom_emotions():
    """VoiceProfile should accept custom emotion settings."""
    profile = VoiceProfile(
        voice_id="custom_123",
        name="Custom Voice",
        greeting_emotion=VoiceEmotion.ENTHUSIASTIC,
        objection_emotion=VoiceEmotion.REASSURING,
        closing_emotion=VoiceEmotion.PERSUASIVE,
    )

    assert profile.greeting_emotion == VoiceEmotion.ENTHUSIASTIC
    assert profile.objection_emotion == VoiceEmotion.REASSURING
    assert profile.closing_emotion == VoiceEmotion.PERSUASIVE


def test_predefined_profiles_exist():
    """Predefined voice profiles should exist."""
    assert "tim_kipper" in VOICE_PROFILES
    assert "default" in VOICE_PROFILES


def test_tim_kipper_profile():
    """Tim Kipper profile should have expected settings."""
    profile = VOICE_PROFILES["tim_kipper"]

    assert profile.name == "Tim Kipper"
    assert "warm" in profile.description.lower() or "professional" in profile.description.lower()
    assert profile.greeting_emotion == VoiceEmotion.FRIENDLY
    assert profile.farewell_emotion == VoiceEmotion.APPRECIATIVE
    assert profile.stability == 0.8
    assert profile.similarity_boost == 0.85


def test_voice_clone_manager_initialization():
    """VoiceCloneManager should initialize with default profile."""
    manager = VoiceCloneManager(default_profile="tim_kipper")

    assert manager.default_profile == "tim_kipper"
    assert len(manager.profiles) >= 2


def test_voice_clone_manager_get_profile():
    """Manager should return correct profile."""
    manager = VoiceCloneManager(default_profile="tim_kipper")

    profile = manager.get_profile("tim_kipper")
    assert profile.name == "Tim Kipper"

    default_profile = manager.get_profile("default")
    assert default_profile.name == "Alex"


def test_voice_clone_manager_get_profile_fallback():
    """Manager should fallback to default for unknown profile."""
    manager = VoiceCloneManager(default_profile="tim_kipper")

    profile = manager.get_profile("nonexistent_profile")
    assert profile is not None
    # Should return default profile


def test_voice_clone_manager_add_profile():
    """Manager should allow adding custom profiles."""
    manager = VoiceCloneManager()

    custom_profile = VoiceProfile(
        voice_id="custom_voice_123",
        name="Custom Sales Rep",
        description="Custom voice for testing",
    )
    manager.add_profile("custom_rep", custom_profile)

    retrieved = manager.get_profile("custom_rep")
    assert retrieved.voice_id == "custom_voice_123"
    assert retrieved.name == "Custom Sales Rep"


def test_get_emotion_for_context_greeting():
    """Should return greeting emotion for greeting context."""
    manager = VoiceCloneManager()
    profile = manager.get_profile("tim_kipper")

    emotion = manager.get_emotion_for_context(profile, "greeting")
    assert emotion == VoiceEmotion.FRIENDLY

    emotion = manager.get_emotion_for_context(profile, "introduction")
    assert emotion == VoiceEmotion.FRIENDLY


def test_get_emotion_for_context_qualifying():
    """Should return qualifying emotion for qualifying context."""
    manager = VoiceCloneManager()
    profile = manager.get_profile("tim_kipper")

    emotion = manager.get_emotion_for_context(profile, "qualifying")
    assert emotion == VoiceEmotion.CURIOUS

    emotion = manager.get_emotion_for_context(profile, "discovery")
    assert emotion == VoiceEmotion.CURIOUS


def test_get_emotion_for_context_objection():
    """Should return empathetic emotion for objection context."""
    manager = VoiceCloneManager()
    profile = manager.get_profile("tim_kipper")

    emotion = manager.get_emotion_for_context(profile, "objection")
    assert emotion == VoiceEmotion.EMPATHETIC

    emotion = manager.get_emotion_for_context(profile, "concern")
    assert emotion == VoiceEmotion.EMPATHETIC


def test_get_emotion_for_context_closing():
    """Should return enthusiastic emotion for closing context."""
    manager = VoiceCloneManager()
    profile = manager.get_profile("tim_kipper")

    emotion = manager.get_emotion_for_context(profile, "closing")
    assert emotion == VoiceEmotion.ENTHUSIASTIC

    emotion = manager.get_emotion_for_context(profile, "booking")
    assert emotion == VoiceEmotion.ENTHUSIASTIC


def test_get_emotion_for_context_farewell():
    """Should return warm emotion for farewell context."""
    manager = VoiceCloneManager()
    profile = manager.get_profile("tim_kipper")

    emotion = manager.get_emotion_for_context(profile, "farewell")
    assert emotion == VoiceEmotion.APPRECIATIVE

    emotion = manager.get_emotion_for_context(profile, "goodbye")
    assert emotion == VoiceEmotion.APPRECIATIVE


def test_get_emotion_for_context_unknown():
    """Should return professional emotion for unknown context."""
    manager = VoiceCloneManager()
    profile = manager.get_profile("tim_kipper")

    emotion = manager.get_emotion_for_context(profile, "random_context")
    assert emotion == VoiceEmotion.PROFESSIONAL


def test_get_tts_config():
    """Should return complete TTS config for Cartesia API."""
    manager = VoiceCloneManager()

    config = manager.get_tts_config(
        text="Hello, this is Tim calling about solar solutions.",
        context="greeting",
    )

    assert "voice_id" in config
    assert "text" in config
    assert "emotion" in config
    assert "speed" in config
    assert "stability" in config
    assert "similarity_boost" in config

    assert config["text"] == "Hello, this is Tim calling about solar solutions."
    assert config["emotion"] == "friendly"


def test_get_tts_config_with_emotion_override():
    """Should use emotion override when provided."""
    manager = VoiceCloneManager()

    config = manager.get_tts_config(
        text="I understand your concerns.",
        context="greeting",  # Would normally use friendly
        emotion_override=VoiceEmotion.EMPATHETIC,  # Override to empathetic
    )

    assert config["emotion"] == "empathetic"


def test_get_tts_config_different_profiles():
    """Should use correct profile settings."""
    manager = VoiceCloneManager()

    tim_config = manager.get_tts_config(
        text="Hello",
        context="greeting",
        profile_name="tim_kipper",
    )

    default_config = manager.get_tts_config(
        text="Hello",
        context="greeting",
        profile_name="default",
    )

    # Tim has higher stability/similarity
    assert tim_config["stability"] == 0.8
    assert tim_config["similarity_boost"] == 0.85
    assert default_config["stability"] == 0.7
    assert default_config["similarity_boost"] == 0.75


def test_get_recording_script():
    """Should return the recording script."""
    script = get_recording_script()

    assert "VOICE CLONE RECORDING SCRIPT" in script
    assert "SECTION 1: INTRODUCTION" in script
    assert "SECTION 2: QUALIFYING QUESTIONS" in script
    assert "SECTION 3: HANDLING OBJECTIONS" in script
    assert "SECTION 4: CLOSING" in script
    assert "SECTION 5: FAREWELL" in script
    assert "Tim Kipper" in script


def test_create_tim_profile():
    """Should create Tim's profile with custom voice ID."""
    profile = create_tim_profile(voice_id="cartesia_tim_voice_abc123")

    assert profile.voice_id == "cartesia_tim_voice_abc123"
    assert profile.name == "Tim Kipper"
    assert "warm" in profile.description.lower() or "professional" in profile.description.lower()
    assert profile.greeting_emotion == VoiceEmotion.FRIENDLY
    assert profile.qualifying_emotion == VoiceEmotion.CURIOUS
    assert profile.objection_emotion == VoiceEmotion.EMPATHETIC
    assert profile.closing_emotion == VoiceEmotion.ENTHUSIASTIC
    assert profile.farewell_emotion == VoiceEmotion.APPRECIATIVE


def test_all_voice_emotions_have_values():
    """All VoiceEmotion enum values should be valid strings."""
    for emotion in VoiceEmotion:
        assert isinstance(emotion.value, str)
        assert len(emotion.value) > 0


def test_voice_profile_speed_range():
    """Voice profile speed should be within valid range."""
    profile = VoiceProfile(
        voice_id="test",
        name="Test",
        speed=0.5,
    )
    assert 0.5 <= profile.speed <= 2.0

    profile2 = VoiceProfile(
        voice_id="test2",
        name="Test2",
        speed=2.0,
    )
    assert 0.5 <= profile2.speed <= 2.0
