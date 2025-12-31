"""
War Room WebSocket - Real-time Dashboard Updates.

Provides WebSocket connection for real-time War Room dashboard updates:
- Subscribe to specific event types
- Receive aggregated state updates
- Push notifications for high-priority events

Uses Redis pub/sub for cross-process event distribution.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Set, Optional

import redis.asyncio as redis
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends

from app.models.database import async_session_maker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/war-room", tags=["war-room-ws"])


class WarRoomConnectionManager:
    """Manages WebSocket connections for War Room dashboard."""

    def __init__(self):
        self.connections: Set[WebSocket] = set()
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub_task: Optional[asyncio.Task] = None
        self.refresh_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        """Accept new War Room WebSocket connection."""
        await websocket.accept()
        self.connections.add(websocket)
        logger.info(f"War Room client connected. Total: {len(self.connections)}")

        if not self.redis_client:
            await self._init_redis()

    def disconnect(self, websocket: WebSocket):
        """Remove War Room WebSocket connection."""
        self.connections.discard(websocket)
        logger.info(f"War Room client disconnected. Total: {len(self.connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected War Room clients."""
        if not self.connections:
            return

        dead_connections = set()
        for ws in self.connections:
            try:
                await ws.send_json(message)
            except Exception as e:
                logger.warning(f"Failed to send to War Room client: {e}")
                dead_connections.add(ws)

        # Clean up dead connections
        self.connections -= dead_connections

    async def _init_redis(self):
        """Initialize Redis pub/sub for War Room events."""
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        try:
            self.redis_client = await redis.from_url(redis_url)
            await self.redis_client.ping()
            self.pubsub_task = asyncio.create_task(self._listen_redis())
            logger.info("War Room Redis pub/sub initialized")
        except Exception as e:
            logger.error(f"War Room Redis connection failed: {e}")

    async def _listen_redis(self):
        """Listen to War Room event channels."""
        if not self.redis_client:
            return

        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe(
                "war_room:coaching",
                "war_room:intent",
                "war_room:account",
                "war_room:elite_team",
            )
            logger.info("War Room listening to Redis channels")

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                if message and message["type"] == "message":
                    try:
                        data = json.loads(message["data"].decode())
                        channel = message["channel"].decode()
                        data["channel"] = channel
                        await self.broadcast(data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in War Room message: {e}")

                await asyncio.sleep(0.05)

        except asyncio.CancelledError:
            logger.info("War Room pub/sub listener cancelled")
        except Exception as e:
            logger.error(f"War Room pub/sub error: {e}")


manager = WarRoomConnectionManager()


@router.websocket("/stream")
async def war_room_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time War Room updates.

    Clients receive:
    - coaching_update: Active call and coaching events
    - intent_signal: New buyer intent signals
    - account_update: Account engagement changes
    - elite_team_update: Agent status changes
    - summary_refresh: Periodic summary metrics (every 5s)
    """
    await manager.connect(websocket)

    # Send initial connection confirmation
    await websocket.send_json({
        "type": "connected",
        "timestamp": datetime.utcnow().isoformat(),
        "message": "Connected to War Room real-time stream",
    })

    # Start periodic summary refresh for this client
    refresh_task = asyncio.create_task(
        _periodic_summary_refresh(websocket)
    )

    try:
        while True:
            # Wait for client messages (subscriptions, pings, etc.)
            data = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=30.0
            )
            try:
                message = json.loads(data)
                await _handle_client_message(websocket, message)
            except json.JSONDecodeError:
                logger.warning(f"Invalid JSON from War Room client: {data}")

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
        logger.info("War Room client disconnected")

    finally:
        refresh_task.cancel()
        manager.disconnect(websocket)


async def _handle_client_message(websocket: WebSocket, message: dict):
    """Handle incoming client messages."""
    msg_type = message.get("type")

    if msg_type == "ping":
        await websocket.send_json({
            "type": "pong",
            "timestamp": datetime.utcnow().isoformat(),
        })

    elif msg_type == "subscribe":
        # Client can subscribe to specific channels
        channels = message.get("channels", [])
        logger.info(f"War Room client subscribing to: {channels}")
        await websocket.send_json({
            "type": "subscribed",
            "channels": channels,
            "timestamp": datetime.utcnow().isoformat(),
        })

    elif msg_type == "request_full_state":
        # Client requests full state refresh
        await _send_full_state(websocket)


async def _periodic_summary_refresh(websocket: WebSocket):
    """Send periodic summary metrics to client."""
    from app.services.war_room_service import WarRoomService

    while True:
        try:
            await asyncio.sleep(5)  # Every 5 seconds

            async with async_session_maker() as db:
                service = WarRoomService(db)
                metrics = await service.get_summary_metrics()

            await websocket.send_json({
                "type": "summary_refresh",
                "data": metrics,
                "timestamp": datetime.utcnow().isoformat(),
            })

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Summary refresh failed: {e}")


async def _send_full_state(websocket: WebSocket):
    """Send full War Room state to client."""
    from app.services.war_room_service import WarRoomService

    try:
        async with async_session_maker() as db:
            service = WarRoomService(db)
            state = await service.get_full_state()

        # Convert dataclasses to dicts for JSON serialization
        state_dict = {
            "active_calls": [
                {
                    "call_sid": c.call_sid,
                    "agent_id": c.agent_id,
                    "started_at": c.started_at.isoformat() if c.started_at else None,
                    "duration_seconds": c.duration_seconds,
                    "suggestions_shown": c.suggestions_shown,
                    "suggestions_used": c.suggestions_used,
                }
                for c in state.active_calls
            ],
            "coaching_acceptance_rate": state.coaching_acceptance_rate,
            "hot_accounts": [
                {
                    "id": a.id,
                    "name": a.name,
                    "stage": a.stage,
                    "stakeholder_score": a.stakeholder_score,
                }
                for a in state.hot_accounts
            ],
            "total_dealers": state.total_dealers,
            "intent_feed": [
                {
                    "id": l.id,
                    "name": l.name,
                    "intent_score": l.intent_score,
                }
                for l in state.intent_feed
            ],
            "agent_statuses": [
                {
                    "agent_name": a.agent_name,
                    "status": a.status,
                }
                for a in state.agent_statuses
            ],
        }

        await websocket.send_json({
            "type": "full_state",
            "data": state_dict,
            "timestamp": datetime.utcnow().isoformat(),
        })

    except Exception as e:
        logger.error(f"Failed to send full state: {e}")
        await websocket.send_json({
            "type": "error",
            "message": "Failed to fetch full state",
            "timestamp": datetime.utcnow().isoformat(),
        })


async def publish_war_room_event(
    channel: str,
    event_type: str,
    data: dict,
):
    """
    Publish event to War Room Redis channel.

    Called from other services when events occur:
    - coaching_websocket: coaching events
    - intent scoring: new intent signals
    - account service: engagement updates
    - elite team hub: agent status changes
    """
    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = await redis.from_url(redis_url)

        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        await client.publish(f"war_room:{channel}", json.dumps(event))
        await client.close()

        logger.debug(f"Published War Room event: {channel}/{event_type}")

    except Exception as e:
        logger.error(f"Failed to publish War Room event: {e}")


__all__ = ["router", "manager", "publish_war_room_event"]
