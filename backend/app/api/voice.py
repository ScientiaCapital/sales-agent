"""
Voice API endpoints for real-time voice interaction

Provides WebSocket and REST endpoints for voice sessions with <2000ms turn latency.
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Dict, Optional, List
import asyncio
import json
import base64
from datetime import datetime
from uuid import uuid4
import io

from app.models import get_db, Lead
from app.services.voice_agent import VoiceAgent, VoiceEmotion, ConversationState
from app.services.cartesia_service import VoiceSpeed
from app.core.logging import setup_logging
from app.core.exceptions import LeadNotFoundError, VoiceSessionNotFoundError

logger = setup_logging(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])

# Global voice agent instance
voice_agent: Optional[VoiceAgent] = None


async def get_voice_agent() -> VoiceAgent:
    """Get or initialize the voice agent."""
    global voice_agent
    if voice_agent is None:
        voice_agent = VoiceAgent()
        await voice_agent.initialize()
    return voice_agent


class VoiceConnectionManager:
    """Manage WebSocket connections for voice streaming."""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.session_websockets: Dict[str, str] = {}  # session_id -> connection_id

    async def connect(self, websocket: WebSocket, connection_id: str):
        """Accept and track new WebSocket connection."""
        await websocket.accept()
        self.active_connections[connection_id] = websocket
        logger.info(f"Voice WebSocket connected: {connection_id}")

    def disconnect(self, connection_id: str):
        """Remove WebSocket connection."""
        if connection_id in self.active_connections:
            del self.active_connections[connection_id]

        # Remove from session mapping
        for session_id, conn_id in list(self.session_websockets.items()):
            if conn_id == connection_id:
                del self.session_websockets[session_id]

        logger.info(f"Voice WebSocket disconnected: {connection_id}")

    async def send_message(self, connection_id: str, message: Dict):
        """Send JSON message to specific connection."""
        if connection_id in self.active_connections:
            websocket = self.active_connections[connection_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                logger.error(f"Failed to send voice message: {e}")
                self.disconnect(connection_id)

    def link_session(self, session_id: str, connection_id: str):
        """Link a voice session to a WebSocket connection."""
        self.session_websockets[session_id] = connection_id


manager = VoiceConnectionManager()


@router.post("/sessions", status_code=201)
async def create_voice_session(
    lead_id: Optional[int] = None,
    voice_id: str = "a0e99841-438c-4a64-b679-ae501e7d6091",
    language: str = "en",
    emotion: str = "professional",
    db: Session = Depends(get_db)
):
    """
    Create a new voice session.

    Args:
        lead_id: Optional lead ID for context
        voice_id: Cartesia voice ID
        language: Language code (en, es, fr, etc.)
        emotion: Initial voice emotion

    Returns:
        Session metadata including WebSocket URL
    """
    # Validate lead if provided
    if lead_id:
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            raise LeadNotFoundError(f"Lead {lead_id} not found", context={"lead_id": lead_id})

    # Map emotion string to enum
    try:
        voice_emotion = VoiceEmotion(emotion.lower())
    except ValueError:
        voice_emotion = VoiceEmotion.PROFESSIONAL

    # Get voice agent
    agent = await get_voice_agent()

    # Create session
    session = await agent.create_session(
        lead_id=lead_id,
        voice_id=voice_id,
        language=language,
        emotion=voice_emotion
    )

    return {
        "session_id": session.session_id,
        "status": "created",
        "voice_id": voice_id,
        "language": language,
        "emotion": emotion,
        "websocket_url": f"/ws/voice/{session.session_id}",
        "created_at": session.created_at.isoformat()
    }


@router.websocket("/ws/{session_id}")
async def websocket_voice_endpoint(websocket: WebSocket, session_id: str):
    """
    WebSocket endpoint for real-time voice interaction.

    Protocol:
    1. Client connects with session_id
    2. Client sends audio chunks as base64-encoded JSON
    3. Server processes and streams back response
    4. Repeat for continuous conversation

    Message format (client -> server):
    {
        "type": "audio",
        "data": "base64_encoded_audio",
        "sample_rate": 16000,
        "format": "pcm"  // or "wav"
    }

    Message format (server -> client):
    {
        "type": "state" | "transcript" | "response" | "audio" | "complete" | "error",
        ... additional fields based on type
    }
    """
    connection_id = str(uuid4())
    await manager.connect(websocket, connection_id)
    manager.link_session(session_id, connection_id)

    # Get voice agent
    agent = await get_voice_agent()

    # Validate session exists
    try:
        metrics = await agent.get_session_metrics(session_id)
        logger.info(f"WebSocket connected to voice session {session_id}")
    except ValueError:
        await websocket.send_json({
            "type": "error",
            "error": f"Session {session_id} not found"
        })
        await websocket.close()
        return

    try:
        # Main message loop
        while True:
            # Receive message from client
            try:
                message = await asyncio.wait_for(
                    websocket.receive_json(),
                    timeout=30.0  # 30 second timeout
                )
            except asyncio.TimeoutError:
                # Send keepalive ping
                await websocket.send_json({"type": "ping"})
                continue

            # Process message based on type
            if message.get("type") == "audio":
                # Decode audio data
                audio_base64 = message.get("data")
                if not audio_base64:
                    await websocket.send_json({
                        "type": "error",
                        "error": "Missing audio data"
                    })
                    continue

                try:
                    audio_data = base64.b64decode(audio_base64)
                except Exception as e:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Invalid base64 audio data: {e}"
                    })
                    continue

                sample_rate = message.get("sample_rate", 16000)

                # Process voice turn and stream response
                async for chunk in agent.process_audio_turn(
                    session_id=session_id,
                    audio_data=audio_data,
                    sample_rate=sample_rate
                ):
                    # Convert audio bytes to base64 if present
                    if chunk["type"] == "audio" and "data" in chunk:
                        chunk["data"] = base64.b64encode(chunk["data"]).decode()

                    await websocket.send_json(chunk)

            elif message.get("type") == "adjust_emotion":
                # Adjust voice emotion
                emotion_str = message.get("emotion", "professional")
                try:
                    emotion = VoiceEmotion(emotion_str.lower())
                    await agent.adjust_voice_emotion(session_id, emotion)
                    await websocket.send_json({
                        "type": "emotion_changed",
                        "emotion": emotion_str
                    })
                except ValueError:
                    await websocket.send_json({
                        "type": "error",
                        "error": f"Invalid emotion: {emotion_str}"
                    })

            elif message.get("type") == "ping":
                # Respond to ping
                await websocket.send_json({"type": "pong"})

            elif message.get("type") == "close":
                # Client requested close
                break

            else:
                await websocket.send_json({
                    "type": "error",
                    "error": f"Unknown message type: {message.get('type')}"
                })

    except WebSocketDisconnect:
        logger.info(f"Voice WebSocket disconnected: {session_id}")

    except Exception as e:
        logger.error(f"Voice WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_json({
                "type": "error",
                "error": str(e)
            })
        except Exception as ws_error:
            logger.warning(f"Failed to send error message to voice WebSocket: {ws_error}")

    finally:
        manager.disconnect(connection_id)


@router.post("/sessions/{session_id}/audio")
async def process_voice_audio(
    session_id: str,
    audio_file: UploadFile = File(...),
    sample_rate: int = 16000
):
    """
    Process audio via REST API (alternative to WebSocket).

    Args:
        session_id: Voice session ID
        audio_file: Audio file upload
        sample_rate: Audio sample rate

    Returns:
        Streaming audio response
    """
    # Get voice agent
    agent = await get_voice_agent()

    # Read audio data
    audio_data = await audio_file.read()

    # Collect response chunks
    response_audio = bytearray()
    response_text = ""
    metrics = {}

    async for chunk in agent.process_audio_turn(
        session_id=session_id,
        audio_data=audio_data,
        sample_rate=sample_rate
    ):
        if chunk["type"] == "audio":
            response_audio.extend(chunk["data"])
        elif chunk["type"] == "response":
            response_text = chunk["text"]
        elif chunk["type"] == "complete":
            metrics = chunk.get("metrics", {})

    # Return audio as streaming response
    return StreamingResponse(
        io.BytesIO(response_audio),
        media_type="audio/raw",
        headers={
            "X-Response-Text": response_text,
            "X-Latency-MS": str(metrics.get("total_latency_ms", 0))
        }
    )


@router.delete("/sessions/{session_id}")
async def close_voice_session(session_id: str):
    """
    Close a voice session.

    Args:
        session_id: Session to close

    Returns:
        Final session metrics
    """
    # Get voice agent
    agent = await get_voice_agent()

    # Get final metrics
    try:
        metrics = await agent.get_session_metrics(session_id)
    except ValueError:
        raise VoiceSessionNotFoundError(f"Session {session_id} not found", context={"session_id": session_id})

    # Close session
    await agent.close_session(session_id)

    return {
        "session_id": session_id,
        "status": "closed",
        "metrics": metrics
    }


@router.get("/sessions/{session_id}/metrics")
async def get_session_metrics(session_id: str):
    """
    Get performance metrics for a voice session.

    Args:
        session_id: Session ID

    Returns:
        Session performance metrics
    """
    # Get voice agent
    agent = await get_voice_agent()

    try:
        metrics = await agent.get_session_metrics(session_id)
    except ValueError:
        raise VoiceSessionNotFoundError(f"Session {session_id} not found", context={"session_id": session_id})

    return metrics


@router.get("/metrics")
async def get_global_voice_metrics():
    """
    Get global voice performance metrics.

    Returns:
        Global performance statistics
    """
    # Get voice agent
    agent = await get_voice_agent()

    return agent.get_global_metrics()


@router.get("/voices")
async def list_available_voices():
    """
    List all available Cartesia voices.

    Returns:
        List of voice options
    """
    # Get voice agent
    agent = await get_voice_agent()

    voices = await agent.cartesia.list_voices()

    return {
        "total": len(voices),
        "voices": voices
    }


@router.post("/voices/clone")
async def clone_voice(
    name: str,
    description: str = "",
    mode: str = "similarity",
    audio_file: UploadFile = File(...)
):
    """
    Clone a voice from an audio sample.

    Args:
        name: Name for the cloned voice
        description: Voice description
        mode: Cloning mode (similarity or stability)
        audio_file: Audio sample file

    Returns:
        Cloned voice ID
    """
    # Get voice agent
    agent = await get_voice_agent()

    # Save uploaded file temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
        tmp_file.write(await audio_file.read())
        tmp_path = tmp_file.name

    try:
        voice_id = await agent.cartesia.clone_voice(
            audio_file_path=tmp_path,
            name=name,
            description=description,
            mode=mode
        )

        return {
            "voice_id": voice_id,
            "name": name,
            "status": "cloned"
        }
    finally:
        # Clean up temp file
        import os
        os.unlink(tmp_path)


@router.get("/status")
async def get_voice_service_status():
    """
    Get voice service status and capabilities.

    Returns:
        Service status and feature list
    """
    # Get voice agent
    agent = await get_voice_agent()

    # Get Cartesia performance stats
    cartesia_stats = agent.cartesia.get_performance_stats()

    return {
        "status": "operational",
        "capabilities": {
            "text_to_speech": True,
            "speech_to_text": True,
            "voice_cloning": True,
            "emotion_control": True,
            "multi_language": True,
            "streaming": True
        },
        "performance": {
            "target_latency_ms": 2000,
            "tts_target_ms": 200,
            "stt_target_ms": 150,
            "inference_target_ms": 633
        },
        "cartesia_stats": cartesia_stats,
        "supported_emotions": [e.value for e in VoiceEmotion],
        "supported_speeds": [s.value for s in VoiceSpeed]
    }