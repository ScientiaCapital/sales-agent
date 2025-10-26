"""
LangChain tool for Cartesia text-to-speech conversion

Provides async TTS tool for LangGraph ConversationAgent and other voice workflows.
Integrates with existing CartesiaService for ultra-fast audio generation (<200ms).
"""

import os
import uuid
from pathlib import Path
from typing import Tuple, Dict, Optional
import logging

from langchain_core.tools import tool, ToolException
from pydantic import BaseModel, Field

from app.services.cartesia_service import (
    CartesiaService,
    VoiceConfig,
    VoiceSpeed,
    VoiceEmotion
)

logger = logging.getLogger(__name__)


class CartesiaTTSInput(BaseModel):
    """Input schema for Cartesia text-to-speech tool.

    Attributes:
        text: Text to convert to speech
        voice_id: Cartesia voice ID (use list_voices to see available voices)
        emotion: Voice emotion (neutral, happy, sad, professional, etc.)
        speed: Speech speed (slowest, slow, normal, fast, fastest)
        output_format: Audio file format (wav, mp3, raw)
        save_dir: Optional custom directory for saving audio
    """
    text: str = Field(
        description="Text to convert to speech. Should be clear, natural language."
    )
    voice_id: Optional[str] = Field(
        default=None,
        description="Cartesia voice ID. If not provided, uses default voice."
    )
    emotion: Optional[str] = Field(
        default="neutral",
        description="Voice emotion: neutral, happy, sad, angry, professional, empathetic, etc."
    )
    speed: str = Field(
        default="normal",
        description="Speech speed: slowest, slow, normal, fast, fastest"
    )
    output_format: str = Field(
        default="wav",
        description="Audio output format: wav (best quality), mp3 (smaller), raw"
    )
    save_dir: Optional[str] = Field(
        default=None,
        description="Custom directory to save audio file. Defaults to temp directory."
    )


@tool(
    args_schema=CartesiaTTSInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def cartesia_text_to_speech(
    text: str,
    voice_id: Optional[str] = None,
    emotion: str = "neutral",
    speed: str = "normal",
    output_format: str = "wav",
    save_dir: Optional[str] = None
) -> Tuple[str, Dict[str, str]]:
    """Convert text to speech using Cartesia AI with ultra-low latency.

    This tool generates high-quality speech audio from text using Cartesia's
    ultra-fast TTS engine (target: <200ms latency). The audio is saved to a
    file and the path is returned for use in voice conversations.

    Use this tool when you need to:
    - Generate voice responses for conversational agents
    - Create audio from text for playback to users
    - Produce speech with specific emotions or speaking styles

    Args:
        text: Text to convert to speech. Should be clear, natural language.
        voice_id: Cartesia voice ID. If not provided, uses default voice.
        emotion: Voice emotion (neutral, happy, sad, professional, etc.)
        speed: Speech speed (slowest, slow, normal, fast, fastest)
        output_format: Audio format - wav (best quality), mp3 (smaller), raw
        save_dir: Custom directory to save audio. Defaults to temp directory.

    Returns:
        Tuple of:
        - Success message with file path (for LLM)
        - Artifact dict with file_path, format, duration, metadata (for downstream processing)

    Raises:
        ToolException: If TTS generation fails (API error, invalid voice, etc.)

    Example:
        ```python
        from langchain_core.messages import HumanMessage
        from langgraph.prebuilt import create_react_agent

        # Create agent with TTS tool
        agent = create_react_agent(llm, [cartesia_text_to_speech])

        # Generate speech
        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Generate speech: Welcome to our platform!")]
        })

        # Access artifact
        file_path = result["artifact"]["file_path"]
        ```
    """
    try:
        # Validate inputs
        if not text or not text.strip():
            raise ToolException("Text cannot be empty")

        if len(text) > 5000:
            raise ToolException(
                f"Text too long ({len(text)} characters). Maximum is 5000 characters."
            )

        # Map emotion string to VoiceEmotion enum
        try:
            emotion_enum = VoiceEmotion(emotion.lower()) if emotion else None
        except ValueError:
            logger.warning(f"Invalid emotion '{emotion}', using neutral")
            emotion_enum = VoiceEmotion.NEUTRAL

        # Map speed string to VoiceSpeed enum
        try:
            speed_enum = VoiceSpeed(speed.lower())
        except ValueError:
            logger.warning(f"Invalid speed '{speed}', using normal")
            speed_enum = VoiceSpeed.NORMAL

        # Initialize Cartesia service
        try:
            cartesia_service = CartesiaService()
        except Exception as e:
            raise ToolException(
                f"Failed to initialize Cartesia service: {str(e)}. "
                f"Ensure CARTESIA_API_KEY is set in environment."
            )

        # Get default voice if not provided
        if not voice_id:
            # Use a sensible default voice ID (English, neutral)
            # This should match a voice from your Cartesia account
            voice_id = os.getenv(
                "CARTESIA_DEFAULT_VOICE_ID",
                "a0e99841-438c-4a64-b679-ae501e7d6091"  # Common English voice
            )

        # Configure voice settings
        voice_config = VoiceConfig(
            voice_id=voice_id,
            language="en",
            emotion=emotion_enum,
            speed=speed_enum,
            sample_rate=44100,
            encoding="pcm_f32le",
            container="raw"  # Use raw for fastest processing
        )

        # Determine save directory
        if save_dir:
            output_dir = Path(save_dir)
        else:
            # Use temp directory for TTS audio
            output_dir = Path(os.getenv("TTS_OUTPUT_DIR", "/tmp/tts_audio"))

        # Create directory if it doesn't exist
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        file_id = str(uuid.uuid4())
        file_ext = output_format if output_format != "raw" else "raw"
        file_name = f"speech_{file_id}.{file_ext}"
        file_path = output_dir / file_name

        # Generate speech audio (non-streaming for simplicity)
        audio_chunks = []
        audio_generator = cartesia_service.text_to_speech(
            text=text,
            voice_config=voice_config,
            stream=False  # Get complete audio at once
        )

        async for chunk in audio_generator:
            audio_chunks.append(chunk)

        if not audio_chunks:
            raise ToolException("Cartesia returned empty audio data")

        # Combine audio chunks
        audio_data = b"".join(audio_chunks)

        # Save to file
        with open(file_path, "wb") as f:
            f.write(audio_data)

        # Get performance stats
        stats = cartesia_service.get_performance_stats()
        tts_latency = stats.get("tts_latency", {})

        # Calculate audio duration (rough estimate)
        # For PCM F32LE at 44100 Hz: bytes / (sample_rate * 4 bytes_per_sample)
        duration_seconds = len(audio_data) / (44100 * 4)
        duration_ms = int(duration_seconds * 1000)

        # Build success message for LLM
        content = (
            f"Successfully generated speech audio ({duration_ms}ms duration) "
            f"and saved to {file_path.name}. "
            f"Voice: {emotion} at {speed} speed."
        )

        # Build artifact for downstream processing
        artifact = {
            "file_path": str(file_path),
            "format": output_format,
            "voice_id": voice_id,
            "emotion": emotion,
            "speed": speed,
            "text_length": len(text),
            "audio_duration_ms": duration_ms,
            "audio_size_bytes": len(audio_data),
            "latency_stats": tts_latency,
        }

        logger.info(
            f"TTS generated: {file_path.name} "
            f"({len(text)} chars → {duration_ms}ms audio)"
        )

        return content, artifact

    except ToolException:
        # Re-raise tool exceptions as-is
        raise

    except ValueError as e:
        raise ToolException(f"Invalid input parameter: {str(e)}")

    except FileNotFoundError as e:
        raise ToolException(f"File system error: {str(e)}")

    except PermissionError as e:
        raise ToolException(
            f"Permission denied when saving audio: {str(e)}. "
            f"Check directory permissions for {output_dir}"
        )

    except Exception as e:
        logger.error(f"Unexpected error in Cartesia TTS tool: {e}", exc_info=True)
        raise ToolException(
            f"Unexpected error generating speech: {str(e)}. "
            f"This may be a Cartesia API issue or network problem."
        )


@tool(parse_docstring=True)
async def cartesia_list_voices() -> str:
    """List all available Cartesia AI voices.

    Use this tool to discover available voice IDs and their descriptions
    before generating speech. Each voice has a unique ID, name, and may
    have specific language or accent characteristics.

    Returns:
        Formatted string listing all available voices with IDs and descriptions

    Raises:
        ToolException: If unable to retrieve voice list

    Example:
        ```python
        voices = await cartesia_list_voices.ainvoke({})
        print(voices)  # Shows all available voices
        ```
    """
    try:
        cartesia_service = CartesiaService()
        voices = await cartesia_service.list_voices()

        if not voices:
            return "No voices available. Check Cartesia API configuration."

        # Format voice list for LLM
        voice_list = ["Available Cartesia Voices:\n"]
        for voice in voices:
            voice_list.append(
                f"- {voice['name']} (ID: {voice['id']})\n"
                f"  Language: {voice.get('language', 'Unknown')}\n"
                f"  {voice.get('description', 'No description')}\n"
            )

        return "\n".join(voice_list)

    except Exception as e:
        logger.error(f"Failed to list Cartesia voices: {e}", exc_info=True)
        raise ToolException(f"Failed to retrieve voice list: {str(e)}")


def get_cartesia_tools():
    """Convenience function to get all Cartesia tools for agent configuration.

    Returns:
        List of Cartesia tools: [cartesia_text_to_speech, cartesia_list_voices]

    Example:
        ```python
        from app.services.langchain.cartesia_tts_tool import get_cartesia_tools
        from langgraph.prebuilt import create_react_agent

        # Create agent with Cartesia tools
        cartesia_tools = get_cartesia_tools()
        agent = create_react_agent(llm, cartesia_tools)
        ```
    """
    return [cartesia_text_to_speech, cartesia_list_voices]
