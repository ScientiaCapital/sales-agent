"""
Twilio Media Stream WebSocket Handler for Real-Time Voice

Handles real-time audio streaming from Twilio with:
- STT via Deepgram Nova-2
- Intent classification
- LLM response via Cerebras llama-3.3-70b
- TTS via Cartesia sonic-turbo
- Audio format conversion (mulaw 8kHz <-> linear16 16kHz)

Protocol: https://www.twilio.com/docs/voice/twiml/stream
"""

import asyncio
import base64
import logging
import time
import struct
from typing import Dict, Any, Tuple, Optional
import io

# Python 3.13 removed audioop, use pure Python implementation
try:
    import audioop
    HAS_AUDIOOP = True
except ImportError:
    HAS_AUDIOOP = False

from fastapi import APIRouter, WebSocket, WebSocketDisconnect


# ==================== Pure Python Audio Fallbacks (for Python 3.13+) ====================

# Mulaw encoding/decoding tables
# Based on ITU-T G.711 specification
MULAW_BIAS = 0x84
MULAW_CLIP = 32635

# Mulaw decode table (8-bit -> 16-bit linear)
MULAW_DECODE_TABLE = [
    -32124, -31100, -30076, -29052, -28028, -27004, -25980, -24956,
    -23932, -22908, -21884, -20860, -19836, -18812, -17788, -16764,
    -15996, -15484, -14972, -14460, -13948, -13436, -12924, -12412,
    -11900, -11388, -10876, -10364, -9852, -9340, -8828, -8316,
    -7932, -7676, -7420, -7164, -6908, -6652, -6396, -6140,
    -5884, -5628, -5372, -5116, -4860, -4604, -4348, -4092,
    -3900, -3772, -3644, -3516, -3388, -3260, -3132, -3004,
    -2876, -2748, -2620, -2492, -2364, -2236, -2108, -1980,
    -1884, -1820, -1756, -1692, -1628, -1564, -1500, -1436,
    -1372, -1308, -1244, -1180, -1116, -1052, -988, -924,
    -876, -844, -812, -780, -748, -716, -684, -652,
    -620, -588, -556, -524, -492, -460, -428, -396,
    -372, -356, -340, -324, -308, -292, -276, -260,
    -244, -228, -212, -196, -180, -164, -148, -132,
    -120, -112, -104, -96, -88, -80, -72, -64,
    -56, -48, -40, -32, -24, -16, -8, 0,
    32124, 31100, 30076, 29052, 28028, 27004, 25980, 24956,
    23932, 22908, 21884, 20860, 19836, 18812, 17788, 16764,
    15996, 15484, 14972, 14460, 13948, 13436, 12924, 12412,
    11900, 11388, 10876, 10364, 9852, 9340, 8828, 8316,
    7932, 7676, 7420, 7164, 6908, 6652, 6396, 6140,
    5884, 5628, 5372, 5116, 4860, 4604, 4348, 4092,
    3900, 3772, 3644, 3516, 3388, 3260, 3132, 3004,
    2876, 2748, 2620, 2492, 2364, 2236, 2108, 1980,
    1884, 1820, 1756, 1692, 1628, 1564, 1500, 1436,
    1372, 1308, 1244, 1180, 1116, 1052, 988, 924,
    876, 844, 812, 780, 748, 716, 684, 652,
    620, 588, 556, 524, 492, 460, 428, 396,
    372, 356, 340, 324, 308, 292, 276, 260,
    244, 228, 212, 196, 180, 164, 148, 132,
    120, 112, 104, 96, 88, 80, 72, 64,
    56, 48, 40, 32, 24, 16, 8, 0,
]


def _pure_python_ulaw2lin(mulaw_data: bytes) -> bytes:
    """
    Pure Python mulaw to linear16 conversion.

    Args:
        mulaw_data: 8-bit mulaw audio bytes

    Returns:
        16-bit linear PCM audio bytes (little-endian)
    """
    result = bytearray(len(mulaw_data) * 2)
    for i, mulaw_byte in enumerate(mulaw_data):
        linear_sample = MULAW_DECODE_TABLE[mulaw_byte]
        # Pack as signed 16-bit little-endian
        result[i * 2] = linear_sample & 0xFF
        result[i * 2 + 1] = (linear_sample >> 8) & 0xFF
    return bytes(result)


def _linear_to_mulaw_sample(sample: int) -> int:
    """
    Encode a single linear16 sample to mulaw.

    Args:
        sample: 16-bit signed linear sample (-32768 to 32767)

    Returns:
        8-bit mulaw encoded value (0-255)
    """
    # Get sign bit
    sign = (sample >> 8) & 0x80
    if sign:
        sample = -sample

    # Clip the sample
    if sample > MULAW_CLIP:
        sample = MULAW_CLIP

    # Add bias
    sample = sample + MULAW_BIAS

    # Find the segment and quantization
    exponent = 7
    exp_mask = 0x4000

    while exponent > 0:
        if sample & exp_mask:
            break
        exponent -= 1
        exp_mask >>= 1

    mantissa = (sample >> (exponent + 3)) & 0x0F
    mulaw_byte = ~(sign | (exponent << 4) | mantissa) & 0xFF

    return mulaw_byte


def _pure_python_lin2ulaw(linear_data: bytes) -> bytes:
    """
    Pure Python linear16 to mulaw conversion.

    Args:
        linear_data: 16-bit linear PCM audio bytes (little-endian)

    Returns:
        8-bit mulaw audio bytes
    """
    num_samples = len(linear_data) // 2
    result = bytearray(num_samples)

    for i in range(num_samples):
        # Unpack 16-bit little-endian signed sample
        lo = linear_data[i * 2]
        hi = linear_data[i * 2 + 1]
        sample = lo | (hi << 8)
        # Convert to signed
        if sample >= 32768:
            sample -= 65536
        result[i] = _linear_to_mulaw_sample(sample)

    return bytes(result)


def _pure_python_resample(
    linear_data: bytes,
    in_rate: int,
    out_rate: int
) -> bytes:
    """
    Pure Python sample rate conversion using linear interpolation.

    Args:
        linear_data: 16-bit linear PCM audio bytes (little-endian)
        in_rate: Input sample rate (e.g., 8000)
        out_rate: Output sample rate (e.g., 16000)

    Returns:
        Resampled 16-bit linear PCM audio bytes
    """
    if in_rate == out_rate:
        return linear_data

    # Parse input samples
    num_in_samples = len(linear_data) // 2
    in_samples = []
    for i in range(num_in_samples):
        lo = linear_data[i * 2]
        hi = linear_data[i * 2 + 1]
        sample = lo | (hi << 8)
        if sample >= 32768:
            sample -= 65536
        in_samples.append(sample)

    if num_in_samples == 0:
        return b""

    # Calculate output sample count
    num_out_samples = int(num_in_samples * out_rate / in_rate)

    # Linear interpolation
    result = bytearray(num_out_samples * 2)
    ratio = (num_in_samples - 1) / max(num_out_samples - 1, 1)

    for i in range(num_out_samples):
        pos = i * ratio
        idx = int(pos)
        frac = pos - idx

        if idx >= num_in_samples - 1:
            sample = in_samples[-1]
        else:
            sample = int(in_samples[idx] * (1 - frac) + in_samples[idx + 1] * frac)

        # Clamp to 16-bit range
        sample = max(-32768, min(32767, sample))

        # Convert to unsigned for bytes
        if sample < 0:
            sample += 65536

        result[i * 2] = sample & 0xFF
        result[i * 2 + 1] = (sample >> 8) & 0xFF

    return bytes(result)

from app.services.deepgram_service import DeepgramService, DeepgramConfig
from app.services.cartesia_service import CartesiaService, VoiceConfig, VoiceSpeed
from app.services.cerebras import CerebrasService
from app.services.voice.intent_classifier import SalesIntentClassifier
from app.services.coaching_service import get_coaching_service
from app.api.coaching_websocket import publish_coaching_event
from app.models.database import SessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# ==================== Audio Format Conversion ====================

def mulaw_to_linear16(mulaw_data: bytes, target_sample_rate: int = 16000) -> bytes:
    """
    Convert mulaw 8kHz audio to linear16 PCM at target sample rate.

    Twilio sends mulaw 8kHz mono. Deepgram expects linear16 16kHz.

    Args:
        mulaw_data: Raw mulaw audio bytes (8-bit, 8kHz)
        target_sample_rate: Target sample rate (default: 16000 for Deepgram)

    Returns:
        Linear16 PCM audio bytes (16-bit, target sample rate)
    """
    try:
        if HAS_AUDIOOP:
            # Use audioop if available (Python < 3.13)
            # Step 1: Decode mulaw to linear16 PCM (still 8kHz)
            linear_8khz = audioop.ulaw2lin(mulaw_data, 2)  # 2 = 16-bit samples

            # Step 2: Upsample from 8kHz to target sample rate
            if target_sample_rate == 8000:
                return linear_8khz

            # Upsample using audioop.ratecv
            upsampled, _ = audioop.ratecv(
                linear_8khz,
                2,  # width: 2 bytes (16-bit)
                1,  # nchannels: mono
                8000,  # inrate: 8kHz
                target_sample_rate,  # outrate: 16kHz
                None  # state: None for first call
            )
            return upsampled
        else:
            # Pure Python fallback (Python 3.13+)
            # Step 1: Decode mulaw to linear16 PCM (still 8kHz)
            linear_8khz = _pure_python_ulaw2lin(mulaw_data)

            # Step 2: Upsample from 8kHz to target sample rate
            if target_sample_rate == 8000:
                return linear_8khz

            return _pure_python_resample(linear_8khz, 8000, target_sample_rate)

    except Exception as e:
        logger.error(f"mulaw to linear16 conversion failed: {e}")
        raise


def linear16_to_mulaw(linear16_data: bytes, source_sample_rate: int = 16000) -> bytes:
    """
    Convert linear16 PCM to mulaw 8kHz audio for Twilio.

    Cartesia returns PCM at various sample rates. Twilio expects mulaw 8kHz.

    Args:
        linear16_data: Linear16 PCM audio bytes (16-bit, source sample rate)
        source_sample_rate: Source sample rate (e.g., 16000, 44100)

    Returns:
        Mulaw audio bytes (8-bit, 8kHz)
    """
    try:
        if HAS_AUDIOOP:
            # Use audioop if available (Python < 3.13)
            # Step 1: Downsample to 8kHz if needed
            if source_sample_rate == 8000:
                linear_8khz = linear16_data
            else:
                # Downsample using audioop.ratecv
                linear_8khz, _ = audioop.ratecv(
                    linear16_data,
                    2,  # width: 2 bytes (16-bit)
                    1,  # nchannels: mono
                    source_sample_rate,  # inrate
                    8000,  # outrate: 8kHz for Twilio
                    None  # state
                )

            # Step 2: Encode linear16 to mulaw
            mulaw_data = audioop.lin2ulaw(linear_8khz, 2)  # 2 = 16-bit input
            return mulaw_data
        else:
            # Pure Python fallback (Python 3.13+)
            # Step 1: Downsample to 8kHz if needed
            if source_sample_rate == 8000:
                linear_8khz = linear16_data
            else:
                linear_8khz = _pure_python_resample(linear16_data, source_sample_rate, 8000)

            # Step 2: Encode linear16 to mulaw
            return _pure_python_lin2ulaw(linear_8khz)

    except Exception as e:
        logger.error(f"linear16 to mulaw conversion failed: {e}")
        raise


def decode_twilio_audio(base64_payload: str) -> bytes:
    """
    Decode base64-encoded mulaw audio from Twilio.

    Args:
        base64_payload: Base64-encoded mulaw audio string

    Returns:
        Raw mulaw audio bytes
    """
    return base64.b64decode(base64_payload)


def encode_twilio_audio(mulaw_data: bytes) -> str:
    """
    Encode mulaw audio to base64 for Twilio.

    Args:
        mulaw_data: Raw mulaw audio bytes

    Returns:
        Base64-encoded audio string
    """
    return base64.b64encode(mulaw_data).decode('utf-8')


# ==================== Twilio Event Helpers ====================

def create_media_event(stream_sid: str, mulaw_audio: bytes) -> Dict[str, Any]:
    """
    Create Twilio media event with audio payload.

    Args:
        stream_sid: Twilio stream SID
        mulaw_audio: Mulaw audio bytes to send

    Returns:
        Twilio media event dict
    """
    return {
        "event": "media",
        "streamSid": stream_sid,
        "media": {
            "payload": encode_twilio_audio(mulaw_audio)
        }
    }


def create_mark_event(stream_sid: str, mark_name: str) -> Dict[str, Any]:
    """
    Create Twilio mark event for timing synchronization.

    Args:
        stream_sid: Twilio stream SID
        mark_name: Name of the mark (e.g., "response_start", "response_end")

    Returns:
        Twilio mark event dict
    """
    return {
        "event": "mark",
        "streamSid": stream_sid,
        "mark": {
            "name": mark_name
        }
    }


# ==================== Audio Processing Pipeline ====================

async def process_stt(
    mulaw_audio: bytes,
    deepgram: DeepgramService
) -> Tuple[str, float, int]:
    """
    Process speech-to-text with Deepgram.

    Args:
        mulaw_audio: Mulaw audio bytes from Twilio
        deepgram: Deepgram service instance

    Returns:
        Tuple of (transcript, confidence, latency_ms)
    """
    start_time = time.perf_counter()

    try:
        # Convert mulaw 8kHz to linear16 16kHz for Deepgram
        linear16_audio = mulaw_to_linear16(mulaw_audio, target_sample_rate=16000)

        # Transcribe with Deepgram
        result = await deepgram.transcribe(linear16_audio)

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            f"STT completed: '{result.transcript}' "
            f"(confidence: {result.confidence:.2f}, latency: {latency_ms}ms)"
        )

        return result.transcript, result.confidence, latency_ms

    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"STT failed after {latency_ms}ms: {e}")
        raise


async def process_tts(
    text: str,
    voice_config: VoiceConfig,
    cartesia: CartesiaService
) -> Tuple[bytes, int]:
    """
    Process text-to-speech with Cartesia and convert to mulaw.

    Args:
        text: Text to synthesize
        voice_config: Voice configuration
        cartesia: Cartesia service instance

    Returns:
        Tuple of (mulaw_audio, latency_ms)
    """
    start_time = time.perf_counter()

    try:
        # Generate speech with Cartesia (returns PCM)
        pcm_chunks = []

        async for chunk in cartesia.text_to_speech(
            text=text,
            voice_config=voice_config,
            stream=True
        ):
            pcm_chunks.append(chunk)

        # Combine PCM chunks
        pcm_audio = b"".join(pcm_chunks)

        # Convert PCM to mulaw 8kHz for Twilio
        mulaw_audio = linear16_to_mulaw(
            pcm_audio,
            source_sample_rate=voice_config.sample_rate
        )

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            f"TTS completed: {len(text)} chars -> {len(mulaw_audio)} bytes "
            f"(latency: {latency_ms}ms)"
        )

        return mulaw_audio, latency_ms

    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"TTS failed after {latency_ms}ms: {e}")
        raise


async def generate_llm_response(
    transcript: str,
    intent: SalesIntent,
    cerebras: CerebrasService,
    lead_context: Optional[Dict[str, Any]] = None
) -> Tuple[str, int]:
    """
    Generate response using Cerebras LLM based on intent.

    Args:
        transcript: User's speech transcript
        intent: Classified sales intent
        cerebras: Cerebras service instance
        lead_context: Optional lead context data

    Returns:
        Tuple of (response_text, latency_ms)
    """
    start_time = time.perf_counter()

    try:
        # Intent-based response prompts
        intent_prompts = {
            SalesIntent.LEAD_QUALIFICATION: (
                "You are a sales qualification assistant. "
                "Ask qualifying questions about the prospect's company, role, and needs. "
                "Be professional and conversational."
            ),
            SalesIntent.MEETING_SCHEDULE: (
                "You are a meeting scheduler. "
                "Help schedule a demo or sales call. "
                "Ask about availability and preferred times."
            ),
            SalesIntent.PRODUCT_INFO: (
                "You are a product specialist. "
                "Explain product features and benefits clearly. "
                "Match features to the prospect's needs."
            ),
            SalesIntent.PRICING_INQUIRY: (
                "You are a pricing consultant. "
                "Provide high-level pricing information. "
                "Qualify the prospect before detailed pricing discussions."
            ),
            SalesIntent.WARM_TRANSFER: (
                "You are a transfer specialist. "
                "Acknowledge the request and prepare for human handoff. "
                "Gather context for the human representative."
            ),
            SalesIntent.OBJECTION: (
                "You are an objection handler. "
                "Address concerns empathetically. "
                "Reframe objections as opportunities."
            ),
            SalesIntent.GENERAL: (
                "You are a helpful sales assistant. "
                "Engage conversationally and guide toward qualification."
            )
        }

        system_prompt = intent_prompts.get(intent, intent_prompts[SalesIntent.GENERAL])

        # Add lead context if available
        context_str = ""
        if lead_context:
            context_str = f"\n\nLead Context: {lead_context}"

        # Generate response using Cerebras (synchronous method)
        # Note: Using qualify_lead as a proxy for general inference
        # In production, would use a chat completion method
        score, reasoning, llm_latency = cerebras.qualify_lead(
            company_name=lead_context.get("company", "Prospect") if lead_context else "Prospect",
            notes=f"{system_prompt}\n\nUser said: {transcript}{context_str}"
        )

        # For demo, use reasoning as response
        # In production, this would be a proper chat completion
        response_text = f"Thank you for your interest. {reasoning}"

        latency_ms = int((time.perf_counter() - start_time) * 1000)

        logger.info(
            f"LLM response generated: intent={intent.value}, "
            f"latency={latency_ms}ms"
        )

        return response_text, latency_ms

    except Exception as e:
        latency_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error(f"LLM generation failed after {latency_ms}ms: {e}")
        raise


async def classify_and_route(
    transcript: str,
    classifier: SalesIntentClassifier,
    cerebras: CerebrasService,
    lead_context: Optional[Dict[str, Any]] = None
) -> Tuple[SalesIntent, str]:
    """
    Classify intent and generate appropriate response.

    Args:
        transcript: User's speech transcript
        classifier: Intent classifier instance
        cerebras: Cerebras service instance
        lead_context: Optional lead context

    Returns:
        Tuple of (intent, response_text)
    """
    # Classify intent
    intent = classifier.classify_intent(transcript)

    # Generate response based on intent
    response_text, _ = await generate_llm_response(
        transcript=transcript,
        intent=intent,
        cerebras=cerebras,
        lead_context=lead_context
    )

    return intent, response_text


async def process_audio_turn(
    audio_mulaw: bytes,
    deepgram: DeepgramService,
    cartesia: CartesiaService,
    cerebras: CerebrasService,
    classifier: SalesIntentClassifier,
    voice_config: VoiceConfig,
    lead_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Process complete audio turn: STT -> Intent -> LLM -> TTS.

    Args:
        audio_mulaw: Input mulaw audio from Twilio
        deepgram: Deepgram service
        cartesia: Cartesia service
        cerebras: Cerebras service
        classifier: Intent classifier
        voice_config: Voice configuration for TTS
        lead_context: Optional lead context

    Returns:
        Dict with transcript, intent, response_text, response_audio, and latency breakdown
    """
    turn_start = time.perf_counter()

    # Step 1: Speech-to-Text
    transcript, confidence, stt_latency = await process_stt(audio_mulaw, deepgram)

    # Step 2: Intent Classification + LLM Response
    intent, response_text = await classify_and_route(
        transcript=transcript,
        classifier=classifier,
        cerebras=cerebras,
        lead_context=lead_context
    )

    llm_latency = int((time.perf_counter() - turn_start) * 1000) - stt_latency

    # Step 3: Text-to-Speech
    response_audio, tts_latency = await process_tts(
        text=response_text,
        voice_config=voice_config,
        cartesia=cartesia
    )

    total_latency = int((time.perf_counter() - turn_start) * 1000)

    return {
        "transcript": transcript,
        "confidence": confidence,
        "intent": intent.value,
        "response_text": response_text,
        "response_audio": response_audio,  # mulaw bytes
        "latency_breakdown": {
            "stt_ms": stt_latency,
            "llm_ms": llm_latency,
            "tts_ms": tts_latency,
            "total_ms": total_latency
        }
    }


# ==================== WebSocket Handler ====================

@router.websocket("/media")
async def handle_voice_websocket(websocket: WebSocket):
    """
    Twilio Media Stream WebSocket endpoint for real-time voice.

    Accepts Twilio Media Stream connection and processes audio in real-time:
    1. Receive mulaw audio from Twilio
    2. Transcribe with Deepgram
    3. Classify intent
    4. Generate response with Cerebras
    5. Synthesize audio with Cartesia
    6. Send mulaw audio back to Twilio

    Protocol: https://www.twilio.com/docs/voice/twiml/stream

    Events:
    - connected: Connection established
    - start: Stream started with metadata
    - media: Audio chunk received
    - stop: Stream ended
    """
    await websocket.accept()
    logger.info("Twilio Media Stream WebSocket connected")

    # Initialize services
    try:
        deepgram = DeepgramService(DeepgramConfig(
            model="nova-2",
            sample_rate=16000,
            encoding="linear16",
            language="en"
        ))

        cartesia = CartesiaService()

        cerebras = CerebrasService()

        classifier = SalesIntentClassifier()

        # Initialize coaching service with database session
        db = SessionLocal()
        coaching_service = get_coaching_service(db)

        # Voice configuration for TTS (sonic-turbo for speed)
        voice_config = VoiceConfig(
            voice_id="a0e99841-438c-4a64-b679-ae501e7d6091",  # Sales closer voice
            model="sonic-turbo",  # Fastest model (40ms)
            sample_rate=8000,  # Match Twilio sample rate for efficiency
            speed=VoiceSpeed.NORMAL
        )

    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        await websocket.close(code=1011, reason="Service initialization failed")
        return

    # Stream state
    stream_sid = None
    call_sid = None
    audio_buffer = bytearray()
    conversation_history = []  # Track conversation for coaching context
    BUFFER_THRESHOLD = 8000  # ~1 second of audio at 8kHz mulaw

    try:
        while True:
            # Receive event from Twilio
            event = await websocket.receive_json()
            event_type = event.get("event")

            if event_type == "connected":
                logger.info(f"Twilio connected: protocol={event.get('protocol')}, version={event.get('version')}")

            elif event_type == "start":
                stream_sid = event.get("streamSid")
                start_data = event.get("start", {})
                call_sid = start_data.get("callSid")
                logger.info(f"Stream started: streamSid={stream_sid}, callSid={call_sid}")

                # Send initial greeting
                greeting = "Hello! Thanks for calling. How can I help you today?"
                greeting_audio, _ = await process_tts(greeting, voice_config, cartesia)

                # Send greeting to Twilio
                await websocket.send_json(create_mark_event(stream_sid, "greeting_start"))
                await websocket.send_json(create_media_event(stream_sid, greeting_audio))
                await websocket.send_json(create_mark_event(stream_sid, "greeting_end"))

            elif event_type == "media":
                # Receive audio chunk
                media = event.get("media", {})
                payload = media.get("payload")

                if payload:
                    # Decode mulaw audio
                    mulaw_chunk = decode_twilio_audio(payload)
                    audio_buffer.extend(mulaw_chunk)

                    # Process when buffer reaches threshold (VAD would be better)
                    if len(audio_buffer) >= BUFFER_THRESHOLD:
                        logger.info(f"Processing audio buffer: {len(audio_buffer)} bytes")

                        # Process audio turn
                        try:
                            result = await process_audio_turn(
                                audio_mulaw=bytes(audio_buffer),
                                deepgram=deepgram,
                                cartesia=cartesia,
                                cerebras=cerebras,
                                classifier=classifier,
                                voice_config=voice_config
                            )

                            # Log turn metrics
                            logger.info(
                                f"Turn completed: transcript='{result['transcript']}', "
                                f"intent={result['intent']}, "
                                f"latency={result['latency_breakdown']['total_ms']}ms"
                            )

                            # Update conversation history for coaching context
                            conversation_history.append({
                                "speaker": "prospect",
                                "text": result["transcript"],
                            })

                            # Generate real-time coaching (target: <200ms)
                            if call_sid and result["transcript"]:
                                try:
                                    coaching = await coaching_service.get_real_time_coaching(
                                        transcript=result["transcript"],
                                        conversation_history=conversation_history[-10:],
                                        lead_context=None,  # Add lead lookup if available
                                    )

                                    # Publish coaching to agent via Redis
                                    await publish_coaching_event(
                                        call_sid=call_sid,
                                        event_type="coaching_suggestion",
                                        suggestions=coaching.suggestions,
                                        battle_cards=coaching.battle_cards,
                                        urgency=coaching.urgency,
                                        latency_ms=coaching.latency_ms,
                                    )

                                    logger.info(
                                        f"Coaching published in {coaching.latency_ms}ms: "
                                        f"{len(coaching.suggestions)} suggestions"
                                    )
                                except Exception as coach_err:
                                    logger.error(f"Coaching generation failed: {coach_err}")

                            # Send response audio to Twilio
                            await websocket.send_json(create_mark_event(stream_sid, "response_start"))
                            await websocket.send_json(
                                create_media_event(stream_sid, result["response_audio"])
                            )
                            await websocket.send_json(create_mark_event(stream_sid, "response_end"))

                            # Track agent response in history
                            conversation_history.append({
                                "speaker": "agent",
                                "text": result["response_text"],
                            })

                            # Clear buffer
                            audio_buffer.clear()

                        except Exception as e:
                            logger.error(f"Audio turn processing failed: {e}")
                            # Clear buffer on error to avoid getting stuck
                            audio_buffer.clear()

            elif event_type == "stop":
                logger.info(f"Stream stopped: streamSid={stream_sid}")
                break

            else:
                logger.warning(f"Unknown event type: {event_type}")

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected by client")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)

    finally:
        # Clean up database session
        if 'db' in locals():
            db.close()
        await websocket.close()
        logger.info("Twilio Media Stream WebSocket closed")
