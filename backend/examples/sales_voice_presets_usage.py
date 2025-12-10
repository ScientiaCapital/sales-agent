"""
Usage Examples: Sales Voice Presets for CartesiaService

This file demonstrates how to use the sales-specific voice presets
added to CartesiaService for different sales scenarios.
"""

import asyncio
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cartesia_service import CartesiaService, SALES_VOICE_PRESETS


async def example_sales_closer():
    """Example: Using the sales_closer preset for closing calls."""
    service = CartesiaService()

    # Get the sales closer voice configuration
    voice_config = service.get_sales_preset("sales_closer")

    # Use it for TTS
    text = "Based on everything we've discussed, I think this solution is perfect for your needs. Shall we move forward with the implementation?"

    async for audio_chunk in service.text_to_speech(text, voice_config, stream=True):
        # Process audio chunks (e.g., stream to client)
        pass

    print(f"Sales closer voice: {voice_config.emotion.value} emotion at {voice_config.speed.value} speed")


async def example_lead_qualifier():
    """Example: Using the lead_qualifier preset for discovery calls."""
    service = CartesiaService()

    # Get the lead qualifier voice configuration
    voice_config = service.get_sales_preset("lead_qualifier")

    # Use it for TTS
    text = "I'd love to learn more about your current process. Can you walk me through how you're handling this today?"

    async for audio_chunk in service.text_to_speech(text, voice_config, stream=True):
        # Process audio chunks
        pass

    print(f"Lead qualifier voice: {voice_config.emotion.value} emotion at {voice_config.speed.value} speed")


async def example_meeting_scheduler():
    """Example: Using the meeting_scheduler preset for booking calls."""
    service = CartesiaService()

    # Get the meeting scheduler voice configuration with sonic-turbo for speed
    voice_config = service.get_sales_preset("meeting_scheduler", model="sonic-turbo")

    # Use it for TTS
    text = "I have Tuesday at 2 PM or Thursday at 10 AM available. Which works better for you?"

    async for audio_chunk in service.text_to_speech(text, voice_config, stream=True):
        # Process audio chunks
        pass

    print(f"Meeting scheduler voice: {voice_config.emotion.value} emotion at {voice_config.speed.value} speed")
    print(f"Using {voice_config.model} model for ultra-fast response")


async def example_warm_transfer():
    """Example: Using the warm_transfer preset for handoffs."""
    service = CartesiaService()

    # Get the warm transfer voice configuration
    voice_config = service.get_sales_preset("warm_transfer")

    # Use it for TTS
    text = "I'm going to connect you with Sarah from our implementation team. She's amazing and will take great care of you. Hold on just a moment."

    async for audio_chunk in service.text_to_speech(text, voice_config, stream=True):
        # Process audio chunks
        pass

    print(f"Warm transfer voice: {voice_config.emotion.value} emotion at {voice_config.speed.value} speed")


async def example_custom_overrides():
    """Example: Using presets with custom overrides."""
    service = CartesiaService()

    # Get sales closer voice but with Spanish language and turbo model
    voice_config = service.get_sales_preset(
        "sales_closer",
        language="es",
        model="sonic-turbo"
    )

    # Use it for TTS
    text = "¿Está listo para comenzar?"

    async for audio_chunk in service.text_to_speech(text, voice_config, stream=True):
        # Process audio chunks
        pass

    print(f"Custom override: {voice_config.language} language with {voice_config.model} model")


def list_all_presets():
    """Display all available sales voice presets."""
    print("\n=== Available Sales Voice Presets ===\n")

    for preset_name, preset_config in SALES_VOICE_PRESETS.items():
        print(f"{preset_name}:")
        print(f"  Description: {preset_config['description']}")
        print(f"  Emotion: {preset_config['emotion'].value}")
        print(f"  Speed: {preset_config['speed'].value}")
        print()


async def example_error_handling():
    """Example: Error handling for invalid preset names."""
    service = CartesiaService()

    try:
        # This will raise ValueError
        voice_config = service.get_sales_preset("invalid_preset")
    except ValueError as e:
        print(f"Error caught: {e}")
        # Error message includes list of available presets


if __name__ == "__main__":
    print("Sales Voice Presets Usage Examples")
    print("=" * 50)

    # List available presets
    list_all_presets()

    # Note: These examples require CARTESIA_API_KEY environment variable
    # and the Cartesia SDK to be installed

    print("\nTo run the async examples:")
    print("1. Set CARTESIA_API_KEY environment variable")
    print("2. Install Cartesia SDK: pip install cartesia")
    print("3. Run: python -m asyncio sales_voice_presets_usage.example_sales_closer")
