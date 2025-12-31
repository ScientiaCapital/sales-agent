"""
Real-Time Coaching WebSocket for Agent Earpiece/UI

Provides a separate WebSocket channel for delivering coaching to agents
during live calls. Receives coaching events via Redis pub/sub.

Events:
- coaching_suggestion: Real-time suggestions for the agent
- battle_card: Battle card triggered by conversation
- coaching_accepted: Agent used a coaching recommendation
"""

import asyncio
import json
import logging
from datetime import datetime
from typing import Optional, Set

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.models.database import SessionLocal
from app.models.coaching_session import CoachingSession

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coaching", tags=["coaching"])


class CoachingConnectionManager:
    """Manages WebSocket connections for coaching delivery."""

    def __init__(self):
        self.connections: dict[str, WebSocket] = {}  # call_sid -> websocket
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket, call_sid: str):
        """Accept coaching WebSocket for a specific call."""
        await websocket.accept()
        self.connections[call_sid] = websocket
        logger.info(f"Coaching WebSocket connected for call {call_sid}")

        if not self.redis_client:
            await self._init_redis()

    def disconnect(self, call_sid: str):
        """Remove coaching WebSocket connection."""
        self.connections.pop(call_sid, None)
        logger.info(f"Coaching WebSocket disconnected for call {call_sid}")

    async def send_to_call(self, call_sid: str, message: dict):
        """Send coaching event to a specific call's agent."""
        websocket = self.connections.get(call_sid)
        if websocket:
            try:
                await websocket.send_json(message)
                return True
            except Exception as e:
                logger.error(f"Failed to send coaching to {call_sid}: {e}")
                self.disconnect(call_sid)
        return False

    async def _init_redis(self):
        """Initialize Redis pub/sub for coaching events."""
        import os

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.redis_client = await redis.from_url(redis_url)
            await self.redis_client.ping()
            self.pubsub_task = asyncio.create_task(self._listen_redis())
            logger.info("Redis connected for coaching pub/sub")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")

    async def _listen_redis(self):
        """Listen to coaching:events channel and route to agents."""
        if not self.redis_client:
            return

        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe("coaching:events")
            logger.info("Listening to Redis channel: coaching:events")

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"].decode())
                        call_sid = data.get("call_sid")
                        if call_sid and call_sid in self.connections:
                            await self.send_to_call(call_sid, data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in coaching message: {e}")
                await asyncio.sleep(0.05)
        except asyncio.CancelledError:
            logger.info("Coaching pub/sub listener cancelled")
        except Exception as e:
            logger.error(f"Coaching pub/sub error: {e}")


manager = CoachingConnectionManager()


@router.websocket("/stream/{call_sid}")
async def coaching_stream_endpoint(
    websocket: WebSocket,
    call_sid: str,
    agent_id: Optional[str] = Query(default=None),
):
    """
    WebSocket endpoint for real-time coaching delivery to agent.

    The agent's UI/earpiece connects here to receive coaching during calls.
    Coaching events are published via Redis from the voice processing pipeline.
    """
    await manager.connect(websocket, call_sid)

    # Create coaching session record
    db = SessionLocal()
    try:
        session = CoachingSession(
            call_sid=call_sid,
            agent_id=agent_id,
            is_active=True,
        )
        db.add(session)
        db.commit()
        session_id = session.id
    except Exception as e:
        logger.error(f"Failed to create coaching session: {e}")
        session_id = None
    finally:
        db.close()

    # Send connection confirmation
    await websocket.send_json({
        "type": "connected",
        "call_sid": call_sid,
        "timestamp": datetime.utcnow().isoformat(),
    })

    try:
        while True:
            data = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=30.0
            )
            try:
                message = json.loads(data)
                await _handle_agent_message(message, call_sid, session_id)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from agent: {data}")

    except asyncio.TimeoutError:
        # Send keepalive
        try:
            await websocket.send_json({
                "type": "keepalive",
                "timestamp": datetime.utcnow().isoformat(),
            })
        except Exception:
            pass

    except WebSocketDisconnect:
        logger.info(f"Coaching WebSocket disconnected: {call_sid}")

    finally:
        manager.disconnect(call_sid)
        await _finalize_session(session_id, call_sid)


async def _handle_agent_message(
    message: dict,
    call_sid: str,
    session_id: Optional[str],
):
    """Handle messages from agent (e.g., coaching accepted events)."""
    msg_type = message.get("type")

    if msg_type == "coaching_accepted":
        coaching_type = message.get("coaching_type")
        coaching_id = message.get("coaching_id")
        logger.info(f"Coaching accepted: {coaching_type} {coaching_id}")

        if session_id:
            await _record_coaching_usage(session_id, coaching_type)

    elif msg_type == "ping":
        pass  # Handled by keepalive


async def _record_coaching_usage(session_id: str, coaching_type: str):
    """Update coaching session with usage data."""
    db = SessionLocal()
    try:
        session = db.query(CoachingSession).filter(
            CoachingSession.id == session_id
        ).first()

        if session:
            if coaching_type == "suggestion":
                session.suggestions_used += 1
            elif coaching_type == "battle_card":
                session.battle_cards_used += 1
            session.coaching_accepted_count += 1
            session.calculate_rates()
            db.commit()
    except Exception as e:
        logger.error(f"Failed to record coaching usage: {e}")
    finally:
        db.close()


async def _finalize_session(session_id: Optional[str], call_sid: str):
    """Finalize coaching session when call ends."""
    if not session_id:
        return

    db = SessionLocal()
    try:
        session = db.query(CoachingSession).filter(
            CoachingSession.id == session_id
        ).first()

        if session:
            session.ended_at = datetime.utcnow()
            if session.started_at:
                delta = session.ended_at - session.started_at
                session.duration_seconds = int(delta.total_seconds())
            session.is_active = False
            session.calculate_rates()
            db.commit()
            logger.info(f"Coaching session finalized: {call_sid}")
    except Exception as e:
        logger.error(f"Failed to finalize session: {e}")
    finally:
        db.close()


async def publish_coaching_event(
    call_sid: str,
    event_type: str,
    suggestions: Optional[list] = None,
    battle_cards: Optional[list] = None,
    urgency: str = "medium",
    latency_ms: int = 0,
):
    """
    Publish coaching event to Redis for WebSocket delivery.

    Called from voice_websocket.py after coaching is generated.
    """
    import os

    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = await redis.from_url(redis_url)

        event = {
            "type": event_type,
            "call_sid": call_sid,
            "timestamp": datetime.utcnow().isoformat(),
            "urgency": urgency,
            "latency_ms": latency_ms,
        }

        if suggestions:
            event["suggestions"] = suggestions
        if battle_cards:
            event["battle_cards"] = battle_cards

        await client.publish("coaching:events", json.dumps(event))
        await client.close()

        logger.debug(f"Published coaching event for call {call_sid}")

    except Exception as e:
        logger.error(f"Failed to publish coaching event: {e}")


__all__ = ["router", "manager", "publish_coaching_event"]
