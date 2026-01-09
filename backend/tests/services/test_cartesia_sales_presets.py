"""
Tests for Cartesia Sales Voice Presets

This module tests the sales-specific voice preset functionality in CartesiaService.
Following TDD approach: write tests first, then implement.
"""

import sys
import importlib.util
from pathlib import Path
import pytest
from unittest.mock import Mock, patch

# Direct module import bypassing __init__.py to avoid OpenAI dependency issues
# Use dynamic path relative to this test file
SERVICE_PATH = Path(__file__).parent.parent.parent / "app" / "services" / "cartesia_service.py"
spec = importlib.util.spec_from_file_location(
    "cartesia_service",
    str(SERVICE_PATH)
)
cartesia_module = importlib.util.module_from_spec(spec)
sys.modules["cartesia_service"] = cartesia_module
spec.loader.exec_module(cartesia_module)

CartesiaService = cartesia_module.CartesiaService
VoiceConfig = cartesia_module.VoiceConfig
VoiceEmotion = cartesia_module.VoiceEmotion
VoiceSpeed = cartesia_module.VoiceSpeed

# Import SALES_VOICE_PRESETS - this will fail initially (TDD)
try:
    SALES_VOICE_PRESETS = cartesia_module.SALES_VOICE_PRESETS
except AttributeError:
    SALES_VOICE_PRESETS = None


class TestSalesVoicePresets:
    """Test suite for sales voice presets functionality."""

    def test_sales_voice_presets_constant_exists(self):
        """Test that SALES_VOICE_PRESETS constant is defined."""
        # Arrange & Act
        # Import already done at top

        # Assert
        assert SALES_VOICE_PRESETS is not None
        assert isinstance(SALES_VOICE_PRESETS, dict)
        assert len(SALES_VOICE_PRESETS) > 0

    def test_sales_voice_presets_has_required_presets(self):
        """Test that all required sales presets are defined."""
        # Arrange
        required_presets = [
            "sales_closer",
            "lead_qualifier",
            "meeting_scheduler",
            "warm_transfer"
        ]

        # Act & Assert
        for preset in required_presets:
            assert preset in SALES_VOICE_PRESETS, f"Missing required preset: {preset}"

    def test_sales_closer_preset_structure(self):
        """Test that sales_closer preset has correct structure."""
        # Arrange
        preset = SALES_VOICE_PRESETS["sales_closer"]

        # Assert
        assert "voice_id" in preset
        assert "description" in preset
        assert "emotion" in preset
        assert "speed" in preset

        # Verify values
        assert preset["voice_id"] == "a0e99841-438c-4a64-b679-ae501e7d6091"
        assert preset["description"] == "Confident, persuasive sales closer"
        assert preset["emotion"] == VoiceEmotion.PROFESSIONAL
        assert preset["speed"] == VoiceSpeed.NORMAL

    def test_lead_qualifier_preset_structure(self):
        """Test that lead_qualifier preset has correct structure."""
        # Arrange
        preset = SALES_VOICE_PRESETS["lead_qualifier"]

        # Assert
        assert preset["voice_id"] == "79a125e8-cd45-4c13-8a67-188112f4dd22"
        assert preset["description"] == "Friendly, curious lead qualifier"
        assert preset["emotion"] == VoiceEmotion.CURIOUS
        assert preset["speed"] == VoiceSpeed.NORMAL

    def test_meeting_scheduler_preset_structure(self):
        """Test that meeting_scheduler preset has correct structure."""
        # Arrange
        preset = SALES_VOICE_PRESETS["meeting_scheduler"]

        # Assert
        assert preset["voice_id"] == "694f9389-aac1-45b6-b726-9d9369183238"
        assert preset["description"] == "Efficient, helpful scheduler"
        assert preset["emotion"] == VoiceEmotion.NEUTRAL
        assert preset["speed"] == VoiceSpeed.FAST

    def test_warm_transfer_preset_structure(self):
        """Test that warm_transfer preset has correct structure."""
        # Arrange
        preset = SALES_VOICE_PRESETS["warm_transfer"]

        # Assert
        assert preset["voice_id"] == "a0e99841-438c-4a64-b679-ae501e7d6091"
        assert preset["description"] == "Smooth, reassuring handoff voice"
        assert preset["emotion"] == VoiceEmotion.EMPATHETIC
        assert preset["speed"] == VoiceSpeed.SLOW


class TestCartesiaServiceSalesPresets:
    """Test suite for CartesiaService sales preset methods."""

    @pytest.fixture
    def mock_cartesia_service(self):
        """Create a mocked CartesiaService instance."""
        # Create a mock service that bypasses the Cartesia SDK requirement
        # We only need the get_sales_preset method, which doesn't use the SDK
        mock_service = Mock(spec=CartesiaService)
        # Bind the actual method to the mock
        mock_service.get_sales_preset = CartesiaService.get_sales_preset.__get__(mock_service, CartesiaService)
        return mock_service

    def test_get_sales_preset_method_exists(self, mock_cartesia_service):
        """Test that get_sales_preset method exists on CartesiaService."""
        # Assert
        assert hasattr(mock_cartesia_service, "get_sales_preset")
        assert callable(getattr(mock_cartesia_service, "get_sales_preset"))

    def test_get_sales_preset_returns_voice_config(self, mock_cartesia_service):
        """Test that get_sales_preset returns a VoiceConfig object."""
        # Act
        config = mock_cartesia_service.get_sales_preset("sales_closer")

        # Assert
        assert isinstance(config, VoiceConfig)

    def test_get_sales_preset_sales_closer(self, mock_cartesia_service):
        """Test get_sales_preset for sales_closer."""
        # Act
        config = mock_cartesia_service.get_sales_preset("sales_closer")

        # Assert
        assert config.voice_id == "a0e99841-438c-4a64-b679-ae501e7d6091"
        assert config.emotion == VoiceEmotion.PROFESSIONAL
        assert config.speed == VoiceSpeed.NORMAL
        assert config.language == "en"
        assert config.model == "sonic-2"

    def test_get_sales_preset_lead_qualifier(self, mock_cartesia_service):
        """Test get_sales_preset for lead_qualifier."""
        # Act
        config = mock_cartesia_service.get_sales_preset("lead_qualifier")

        # Assert
        assert config.voice_id == "79a125e8-cd45-4c13-8a67-188112f4dd22"
        assert config.emotion == VoiceEmotion.CURIOUS
        assert config.speed == VoiceSpeed.NORMAL

    def test_get_sales_preset_meeting_scheduler(self, mock_cartesia_service):
        """Test get_sales_preset for meeting_scheduler."""
        # Act
        config = mock_cartesia_service.get_sales_preset("meeting_scheduler")

        # Assert
        assert config.voice_id == "694f9389-aac1-45b6-b726-9d9369183238"
        assert config.emotion == VoiceEmotion.NEUTRAL
        assert config.speed == VoiceSpeed.FAST

    def test_get_sales_preset_warm_transfer(self, mock_cartesia_service):
        """Test get_sales_preset for warm_transfer."""
        # Act
        config = mock_cartesia_service.get_sales_preset("warm_transfer")

        # Assert
        assert config.voice_id == "a0e99841-438c-4a64-b679-ae501e7d6091"
        assert config.emotion == VoiceEmotion.EMPATHETIC
        assert config.speed == VoiceSpeed.SLOW

    def test_get_sales_preset_invalid_name_raises_error(self, mock_cartesia_service):
        """Test that get_sales_preset raises ValueError for invalid preset name."""
        # Act & Assert
        with pytest.raises(ValueError, match="Unknown sales preset"):
            mock_cartesia_service.get_sales_preset("invalid_preset_name")

    def test_get_sales_preset_with_custom_model(self, mock_cartesia_service):
        """Test get_sales_preset with custom model override."""
        # Act
        config = mock_cartesia_service.get_sales_preset(
            "sales_closer",
            model="sonic-turbo"
        )

        # Assert
        assert config.model == "sonic-turbo"
        assert config.voice_id == "a0e99841-438c-4a64-b679-ae501e7d6091"

    def test_get_sales_preset_with_custom_language(self, mock_cartesia_service):
        """Test get_sales_preset with custom language override."""
        # Act
        config = mock_cartesia_service.get_sales_preset(
            "sales_closer",
            language="es"
        )

        # Assert
        assert config.language == "es"
        assert config.voice_id == "a0e99841-438c-4a64-b679-ae501e7d6091"

    def test_all_presets_accessible(self, mock_cartesia_service):
        """Test that all presets can be accessed without errors."""
        # Act & Assert
        for preset_name in SALES_VOICE_PRESETS.keys():
            config = mock_cartesia_service.get_sales_preset(preset_name)
            assert isinstance(config, VoiceConfig)
            assert config.voice_id is not None
            assert config.emotion is not None
            assert config.speed is not None
