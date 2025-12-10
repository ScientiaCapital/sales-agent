"""
Voice API Endpoints for Twilio Integration

Handles voice phone calling for sales AI agent:
- POST /voice/incoming - Handle incoming calls with TwiML
- POST /voice/outbound - Initiate outbound calls
- POST /voice/status - Call status callbacks

Architecture:
- Twilio webhooks accept form-encoded data
- TwiML responses for call control
- VoiceSessionLog database tracking
- WebSocket streaming for real-time AI

Security:
- Twilio signature verification (TODO)
- Environment-based credentials
- Database session management

Author: Claude + Tim
Date: 2025-12-09
"""

import os
import logging
from datetime import datetime, timezone
from typing import Optional
from contextlib import contextmanager

from fastapi import APIRouter, Form, HTTPException, BackgroundTasks
from fastapi.responses import Response
from pydantic import BaseModel, Field, validator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


# ========== Environment Configuration ==========

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
WEBSOCKET_URL = os.getenv("VOICE_WEBSOCKET_URL", "wss://example.com/voice/stream")


# ========== Pydantic Models ==========

class OutboundCallRequest(BaseModel):
    """Request model for initiating outbound calls."""
    to: str = Field(..., description="E.164 formatted phone number (+15551234567)")
    lead_id: Optional[str] = Field(None, description="Optional lead ID for tracking")

    @validator("to")
    def validate_e164_format(cls, v):
        """Validate phone number is in E.164 format."""
        if not v.startswith("+"):
            raise ValueError("Phone number must start with + (E.164 format)")
        if not v[1:].isdigit():
            raise ValueError("Phone number must contain only digits after +")
        if len(v) < 10 or len(v) > 16:
            raise ValueError("Phone number length must be between 10-16 characters")
        return v


class OutboundCallResponse(BaseModel):
    """Response model for outbound call creation."""
    call_sid: str
    status: str
    to: str
    from_: str
    message: str


class StatusCallbackResponse(BaseModel):
    """Response model for status callbacks."""
    message: str
    call_sid: str
    status: str


# ========== Helper Functions ==========

def get_twilio_client():
    """
    Get configured Twilio REST client.

    Returns:
        Twilio Client instance or None if not configured
    """
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
        logger.error("Twilio credentials not configured in environment")
        return None

    try:
        from twilio.rest import Client
        return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    except ImportError:
        logger.error("twilio package not installed - run: pip install twilio")
        return None
    except Exception as e:
        logger.error(f"Failed to initialize Twilio client: {e}")
        return None


@contextmanager
def get_db_session():
    """
    Get database session with context manager.

    Yields:
        SQLAlchemy session
    """
    from app.models.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        session.close()


def create_voice_session_log(
    session,
    call_sid: str,
    direction: str,
    from_number: str,
    to_number: str,
    lead_id: Optional[str] = None
):
    """
    Create VoiceSessionLog database record.

    Args:
        session: Database session
        call_sid: Twilio call SID
        direction: inbound or outbound
        from_number: Caller phone number
        to_number: Recipient phone number
        lead_id: Optional lead ID

    Returns:
        VoiceSessionLog instance
    """
    from app.models.voice_models import VoiceSessionLog, VoiceSessionStatus

    voice_session = VoiceSessionLog(
        id=call_sid,  # Use Twilio CallSid as primary key
        lead_id=int(lead_id) if lead_id and lead_id.isdigit() else None,
        voice_id="default",  # TODO: Configure from voice config
        voice_name="Sales AI Agent",
        language="en",
        status=VoiceSessionStatus.ACTIVE,
        total_turns=0,
        context_data={
            "direction": direction,
            "from": from_number,
            "to": to_number,
            "call_sid": call_sid
        }
    )

    session.add(voice_session)
    return voice_session


def update_voice_session_status(
    session,
    call_sid: str,
    status: str,
    duration_seconds: Optional[int] = None
):
    """
    Update VoiceSessionLog status from Twilio callback.

    Args:
        session: Database session
        call_sid: Twilio call SID
        status: Twilio call status
        duration_seconds: Call duration in seconds

    Returns:
        Updated VoiceSessionLog or None if not found
    """
    from app.models.voice_models import VoiceSessionLog, VoiceSessionStatus

    voice_session = session.query(VoiceSessionLog).filter(
        VoiceSessionLog.id == call_sid
    ).first()

    if not voice_session:
        logger.warning(f"Voice session not found for CallSid: {call_sid}")
        return None

    # Map Twilio status to our enum
    status_map = {
        "completed": VoiceSessionStatus.COMPLETED,
        "busy": VoiceSessionStatus.ERROR,
        "no-answer": VoiceSessionStatus.ABANDONED,
        "failed": VoiceSessionStatus.ERROR,
        "canceled": VoiceSessionStatus.ABANDONED,
    }

    voice_session.status = status_map.get(status, VoiceSessionStatus.ACTIVE)

    # Store duration if call completed
    if duration_seconds is not None:
        voice_session.total_duration_ms = int(duration_seconds) * 1000

    # Set completion timestamp for terminal states
    if voice_session.status in [
        VoiceSessionStatus.COMPLETED,
        VoiceSessionStatus.ERROR,
        VoiceSessionStatus.ABANDONED
    ]:
        voice_session.completed_at = datetime.now(timezone.utc)

    return voice_session


def generate_twiml_response(from_number: str) -> str:
    """
    Generate TwiML XML response for incoming calls.

    Creates a TwiML response that:
    1. Greets the caller
    2. Connects to WebSocket stream for AI interaction

    Args:
        from_number: Caller's phone number

    Returns:
        TwiML XML string
    """
    # Sanitize phone number for speech
    phone_display = from_number.replace("+1", "").replace("+", "")

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        Thank you for calling. Connecting you to our AI sales agent.
    </Say>
    <Connect>
        <Stream url="{WEBSOCKET_URL}">
            <Parameter name="caller" value="{from_number}" />
        </Stream>
    </Connect>
</Response>"""

    return twiml


# ========== Endpoints ==========

@router.post("/incoming", response_class=Response)
async def handle_incoming_call(
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
    CallStatus: str = Form(default="ringing"),
    Direction: str = Form(default="inbound"),
    background_tasks: BackgroundTasks = None
):
    """
    Handle incoming Twilio call webhook.

    Accepts Twilio's form-encoded webhook data and returns TwiML
    to greet the caller and connect to WebSocket stream for AI interaction.

    Args:
        CallSid: Twilio call identifier
        From: Caller's phone number (E.164)
        To: Recipient phone number (E.164)
        CallStatus: Current call status
        Direction: Call direction (inbound/outbound)
        background_tasks: FastAPI background tasks

    Returns:
        TwiML XML response

    Example Twilio webhook:
        POST /voice/incoming
        CallSid=CA1234...&From=+15551234567&To=+15559876543&CallStatus=ringing
    """
    try:
        logger.info(f"Incoming call from {From} to {To} (CallSid: {CallSid})")

        # Create voice session log in database
        with get_db_session() as session:
            create_voice_session_log(
                session=session,
                call_sid=CallSid,
                direction=Direction,
                from_number=From,
                to_number=To
            )

        # Generate TwiML response
        twiml_xml = generate_twiml_response(from_number=From)

        return Response(
            content=twiml_xml,
            media_type="application/xml"
        )

    except Exception as e:
        logger.error(f"Error handling incoming call: {e}", exc_info=True)
        # Return basic TwiML error response
        error_twiml = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Joanna">
        We're experiencing technical difficulties. Please try again later.
    </Say>
    <Hangup/>
</Response>"""
        return Response(
            content=error_twiml,
            media_type="application/xml",
            status_code=200  # Still return 200 to Twilio
        )


@router.post("/outbound", response_model=OutboundCallResponse)
async def initiate_outbound_call(request: OutboundCallRequest):
    """
    Initiate an outbound call via Twilio.

    Creates a new call to the specified phone number and returns
    the Twilio CallSid for tracking.

    Args:
        request: OutboundCallRequest with 'to' and optional 'lead_id'

    Returns:
        OutboundCallResponse with call_sid and status

    Example:
        POST /voice/outbound
        {
            "to": "+15551234567",
            "lead_id": "lead_123"
        }

    Response:
        {
            "call_sid": "CA1234567890abcdef...",
            "status": "queued",
            "to": "+15551234567",
            "from_": "+15559876543",
            "message": "Outbound call initiated successfully"
        }
    """
    try:
        # Get Twilio client
        client = get_twilio_client()
        if not client:
            raise HTTPException(
                status_code=503,
                detail="Twilio service not available - credentials not configured"
            )

        logger.info(f"Initiating outbound call to {request.to} (lead_id: {request.lead_id})")

        # Create call via Twilio API
        call = client.calls.create(
            to=request.to,
            from_=TWILIO_PHONE_NUMBER,
            url=f"{os.getenv('API_BASE_URL', 'https://example.com')}/voice/incoming",
            status_callback=f"{os.getenv('API_BASE_URL', 'https://example.com')}/voice/status",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
            status_callback_method="POST"
        )

        # Create voice session log in database
        with get_db_session() as session:
            create_voice_session_log(
                session=session,
                call_sid=call.sid,
                direction="outbound-api",
                from_number=TWILIO_PHONE_NUMBER,
                to_number=request.to,
                lead_id=request.lead_id
            )

        return OutboundCallResponse(
            call_sid=call.sid,
            status=call.status,
            to=call.to,
            from_=call.from_,
            message="Outbound call initiated successfully"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating outbound call: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate outbound call: {str(e)}"
        )


@router.post("/status", response_model=StatusCallbackResponse)
async def handle_status_callback(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
    CallDuration: str = Form(default="0"),
    Direction: str = Form(default="outbound-api"),
    From: str = Form(default=""),
    To: str = Form(default="")
):
    """
    Handle Twilio call status callback webhook.

    Updates the voice_session record in the database with current
    call status and duration.

    Args:
        CallSid: Twilio call identifier
        CallStatus: Current status (queued, ringing, in-progress, completed, etc.)
        CallDuration: Call duration in seconds (for completed calls)
        Direction: Call direction
        From: Caller phone number
        To: Recipient phone number

    Returns:
        StatusCallbackResponse with status update confirmation

    Example Twilio webhook:
        POST /voice/status
        CallSid=CA1234...&CallStatus=completed&CallDuration=45

    Twilio Call Statuses:
        - queued: Call is queued
        - ringing: Phone is ringing
        - in-progress: Call is active
        - completed: Call ended normally
        - busy: Recipient busy
        - no-answer: No answer
        - failed: Call failed
        - canceled: Call canceled
    """
    try:
        logger.info(
            f"Status callback for CallSid {CallSid}: "
            f"status={CallStatus}, duration={CallDuration}s"
        )

        # Update voice session in database
        with get_db_session() as session:
            voice_session = update_voice_session_status(
                session=session,
                call_sid=CallSid,
                status=CallStatus,
                duration_seconds=int(CallDuration) if CallDuration.isdigit() else None
            )

            if not voice_session:
                # Session not found - possibly race condition or missing initial webhook
                logger.warning(f"Creating voice session retroactively for CallSid: {CallSid}")
                voice_session = create_voice_session_log(
                    session=session,
                    call_sid=CallSid,
                    direction=Direction,
                    from_number=From,
                    to_number=To
                )
                update_voice_session_status(
                    session=session,
                    call_sid=CallSid,
                    status=CallStatus,
                    duration_seconds=int(CallDuration) if CallDuration.isdigit() else None
                )

        return StatusCallbackResponse(
            message=f"Status updated to {CallStatus}",
            call_sid=CallSid,
            status=CallStatus
        )

    except Exception as e:
        logger.error(f"Error handling status callback: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update call status: {str(e)}"
        )


# ========== Health Check ==========

@router.get("/health")
async def voice_health():
    """
    Health check for voice endpoints.

    Returns configuration status and Twilio connectivity.
    """
    client = get_twilio_client()

    return {
        "status": "healthy" if client else "degraded",
        "twilio": {
            "configured": bool(client),
            "account_sid": TWILIO_ACCOUNT_SID[:8] + "..." if TWILIO_ACCOUNT_SID else None,
            "phone_number": TWILIO_PHONE_NUMBER,
        },
        "websocket": {
            "url": WEBSOCKET_URL,
        }
    }


# ========== Exports ==========

__all__ = ["router"]
