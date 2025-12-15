"""
Voice API routes for Twilio webhooks and Slack callbacks.
"""
from fastapi import APIRouter, Request, Response, WebSocket
from typing import Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/voice", tags=["voice"])


@router.post("/twilio-webhook")
async def twilio_webhook(request: Request) -> Response:
    """
    Handle Twilio voice webhooks.

    Called when:
    - Call is initiated
    - Call status changes
    - Audio streaming starts
    """
    form_data = await request.form()
    call_sid = form_data.get("CallSid")
    call_status = form_data.get("CallStatus")
    from_number = form_data.get("From")
    to_number = form_data.get("To")

    logger.info(f"Twilio webhook: {call_sid} status={call_status}")

    # Return TwiML to control call
    # In production, this would:
    # 1. Look up lead context
    # 2. Connect to WebSocket for audio streaming
    # 3. Start real-time STT/TTS pipeline

    twiml = '''<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say>Hello, this is your AI sales assistant. How can I help you today?</Say>
    <Pause length="1"/>
</Response>'''

    return Response(
        content=twiml,
        media_type="application/xml",
    )


@router.post("/slack-callback")
async def slack_callback(request: Request) -> Dict[str, Any]:
    """
    Handle Slack interactive component callbacks.

    Called when user clicks approve/skip/confirm buttons.
    """
    from app.services.calling.gates.pre_call import PreCallGate
    from app.services.calling.gates.post_call import PostCallGate

    payload = await request.json()
    actions = payload.get("actions", [])
    user = payload.get("user", {})

    for action in actions:
        action_id = action.get("action_id", "")

        # Pre-call gate actions
        if action_id.startswith("approve_call_"):
            call_id = action_id.replace("approve_call_", "")
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            gate = PreCallGate(slack_webhook_url=slack_url)
            gate.handle_slack_callback(call_id, "approve", user.get("name", "unknown"))
            logger.info(f"Call {call_id} approved by {user.get('name')}")

        elif action_id.startswith("skip_call_"):
            call_id = action_id.replace("skip_call_", "")
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            gate = PreCallGate(slack_webhook_url=slack_url)
            gate.handle_slack_callback(call_id, "skip", user.get("name", "unknown"))
            logger.info(f"Call {call_id} skipped by {user.get('name')}")

        # Post-call gate actions
        elif action_id.startswith("confirm_meeting_"):
            call_id = action_id.replace("confirm_meeting_", "")
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            gate = PostCallGate(slack_webhook_url=slack_url)
            gate.handle_slack_callback(call_id, "confirm", user.get("name", "unknown"))
            logger.info(f"Meeting {call_id} confirmed by {user.get('name')}")

        elif action_id.startswith("reject_meeting_"):
            call_id = action_id.replace("reject_meeting_", "")
            slack_url = os.getenv("SLACK_WEBHOOK_URL", "")
            gate = PostCallGate(slack_webhook_url=slack_url)
            gate.handle_slack_callback(call_id, "reject", user.get("name", "unknown"))
            logger.info(f"Meeting {call_id} rejected by {user.get('name')}")

    return {"ok": True}


@router.websocket("/stream")
async def audio_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time audio streaming.

    Handles bidirectional audio:
    - Receives audio from Twilio
    - Sends audio back to Twilio
    """
    await websocket.accept()

    try:
        while True:
            # Receive audio data from Twilio
            data = await websocket.receive_bytes()

            # TODO: In production:
            # 1. Send to Deepgram STT for transcription
            # 2. Route transcript to LangGraph agent
            # 3. Get agent response
            # 4. Generate Cartesia TTS audio
            # 5. Send audio back to Twilio

            # Placeholder: echo back
            await websocket.send_bytes(data)

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        await websocket.close()
