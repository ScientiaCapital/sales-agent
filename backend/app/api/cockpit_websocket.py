"""
BDR Cockpit WebSocket API

Provides real-time updates for Tim's BDR Control Center via WebSocket connections.
Uses Redis pub/sub for message distribution across multiple workers.

Events:
- agent_started - Agent execution begins
- agent_completed - Agent execution finishes
- agent_failed - Agent execution fails
- alert - New high-priority alert (HOT lead reply, etc.)
- draft_created - New BDR draft ready for review
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict, Set, Optional
import redis.asyncio as redis
import asyncio
import json
from datetime import datetime

from app.core.logging import setup_logging
from app.auth.supabase_auth import get_supabase_client

logger = setup_logging(__name__)

router = APIRouter(prefix="/ws", tags=["websocket"])


# ========== Connection Manager ==========

class CockpitConnectionManager:
    """Manages WebSocket connections for the BDR Cockpit."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub_task: Optional[asyncio.Task] = None

    async def connect(self, websocket: WebSocket):
        """Accept and track new WebSocket connection."""
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"Cockpit WebSocket connected - total connections: {len(self.active_connections)}")

        # Initialize Redis pub/sub if not already running
        if not self.redis_client:
            await self._init_redis()

    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection."""
        self.active_connections.discard(websocket)
        logger.info(f"Cockpit WebSocket disconnected - remaining: {len(self.active_connections)}")

    async def broadcast(self, message: Dict):
        """
        Broadcast message to all connected clients.

        Args:
            message: Event data to broadcast
        """
        message_json = json.dumps(message)

        # Send to all active connections
        disconnected = set()
        for connection in self.active_connections.copy():
            try:
                await connection.send_text(message_json)
            except Exception as e:
                logger.error(f"Failed to send message to client: {e}")
                disconnected.add(connection)

        # Clean up disconnected clients
        for connection in disconnected:
            self.disconnect(connection)

    async def _init_redis(self):
        """Initialize Redis client and start pub/sub listener."""
        import os

        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        try:
            self.redis_client = await redis.from_url(redis_url)
            await self.redis_client.ping()
            logger.info("Redis connection established for Cockpit WebSocket")

            # Start pub/sub listener task
            self.pubsub_task = asyncio.create_task(self._listen_redis())

        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            self.redis_client = None

    async def _listen_redis(self):
        """
        Listen to Redis pub/sub channel and broadcast to WebSocket clients.

        Channel: cockpit:events
        """
        if not self.redis_client:
            return

        try:
            pubsub = self.redis_client.pubsub()
            await pubsub.subscribe("cockpit:events")

            logger.info("Listening to Redis channel: cockpit:events")

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )

                if message and message["type"] == "message":
                    try:
                        # Decode and parse message
                        data = json.loads(message["data"].decode())
                        logger.debug(f"Broadcasting event to {len(self.active_connections)} clients: {data.get('type')}")

                        # Broadcast to all WebSocket clients
                        await self.broadcast(data)

                    except json.JSONDecodeError as e:
                        logger.error(f"Invalid JSON in Redis message: {e}")

                await asyncio.sleep(0.1)  # Prevent tight loop

        except asyncio.CancelledError:
            logger.info("Redis pub/sub listener cancelled")
        except Exception as e:
            logger.error(f"Error in Redis pub/sub listener: {e}", exc_info=True)
        finally:
            if pubsub:
                await pubsub.unsubscribe("cockpit:events")


# Global connection manager instance
manager = CockpitConnectionManager()


# ========== WebSocket Endpoint ==========

async def _authenticate_websocket(websocket: WebSocket, token: Optional[str]) -> Optional[dict]:
    """
    Authenticate WebSocket connection using JWT token.

    Args:
        websocket: WebSocket connection
        token: JWT token from query param or first message

    Returns:
        User dict if authenticated, None otherwise
    """
    if not token:
        return None

    try:
        supabase_client = get_supabase_client()
        user = await supabase_client.get_user_from_token(token)

        if user:
            logger.info(f"WebSocket authenticated: {user.get('email')}")
            return user

        return None

    except Exception as e:
        logger.warning(f"WebSocket authentication failed: {e}")
        return None


@router.websocket("/cockpit")
async def websocket_cockpit_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(default=None, description="JWT token for authentication")
):
    """
    WebSocket endpoint for real-time BDR Cockpit updates.

    Clients connect to this endpoint to receive live updates about:
    - Agent executions (started, completed, failed)
    - New alerts (HOT lead replies, etc.)
    - Draft creation events
    - System status changes

    Connection Flow:
    1. Client connects with valid JWT token
    2. Server validates token and sends initial state
    3. Client receives real-time events via Redis pub/sub
    4. Client disconnects when done

    Authentication (REQUIRED):
    - JWT token sent in query param: ws://host/ws/cockpit?token=<jwt>
    - OR in first message after connect: {"type": "auth", "token": "<jwt>"}

    Example (JavaScript):
        ```javascript
        const token = localStorage.getItem('supabase_token');
        const ws = new WebSocket(`ws://localhost:8001/api/v1/ws/cockpit?token=${token}`);

        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Event:', data.type, data);

            if (data.type === 'agent_completed') {
                // Update UI with agent results
            }
        };
        ```

    Event Schema:
        ```json
        {
            "type": "agent_started",
            "agent": "lead_scout",
            "task_id": "abc-123",
            "timestamp": "2025-12-06T20:30:00Z"
        }
        ```
    """
    # Accept connection first (WebSocket protocol requires this)
    await websocket.accept()

    # Authenticate via query param
    user = await _authenticate_websocket(websocket, token)

    # If no token in query param, wait for auth message
    if not user:
        try:
            # Wait for auth message (5 second timeout)
            auth_data = await asyncio.wait_for(
                websocket.receive_text(),
                timeout=5.0
            )

            try:
                auth_msg = json.loads(auth_data)
                if auth_msg.get("type") == "auth" and auth_msg.get("token"):
                    user = await _authenticate_websocket(websocket, auth_msg["token"])
            except json.JSONDecodeError:
                pass

        except asyncio.TimeoutError:
            pass

    # Reject if still not authenticated
    if not user:
        await websocket.send_json({
            "type": "error",
            "code": "AUTH_REQUIRED",
            "message": "Authentication required. Provide token in query param or auth message.",
            "timestamp": datetime.utcnow().isoformat()
        })
        await websocket.close(code=4001, reason="Authentication required")
        return

    # Add to connection manager (authentication passed)
    manager.active_connections.add(websocket)

    # Initialize Redis pub/sub if needed
    if not manager.redis_client:
        await manager._init_redis()

    logger.info(f"Cockpit WebSocket connected - user: {user.get('email')} - total: {len(manager.active_connections)}")

    try:
        # Send initial connection confirmation with user info
        await websocket.send_json({
            "type": "connected",
            "user_email": user.get("email"),
            "timestamp": datetime.utcnow().isoformat(),
            "message": "BDR Cockpit WebSocket connected - authenticated"
        })

        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for messages from client (e.g., ping/pong)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0  # 30 second timeout
                )

                # Parse client message
                try:
                    message = json.loads(data)

                    if message.get("type") == "ping":
                        # Respond to ping with pong
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        })

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON from client: {data}")

            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({
                        "type": "keepalive",
                        "timestamp": datetime.utcnow().isoformat()
                    })
                except Exception:
                    # Client disconnected
                    break

    except WebSocketDisconnect:
        logger.info("Cockpit WebSocket disconnected normally")

    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)

    finally:
        manager.disconnect(websocket)


# ========== Helper Functions for Publishing Events ==========

async def publish_agent_event(
    event_type: str,
    agent_name: str,
    task_id: Optional[str] = None,
    result: Optional[Dict] = None,
    error: Optional[str] = None,
    duration_ms: Optional[int] = None
):
    """
    Publish an agent event to the cockpit:events Redis channel.

    This function should be called from Celery tasks to broadcast
    real-time updates to the BDR Cockpit.

    Args:
        event_type: Event type (agent_started, agent_completed, agent_failed)
        agent_name: Name of the agent
        task_id: Celery task ID
        result: Result data (for completed events)
        error: Error message (for failed events)
        duration_ms: Execution duration in milliseconds

    Example (from Celery task):
        ```python
        from app.api.cockpit_websocket import publish_agent_event

        # At task start
        await publish_agent_event("agent_started", "lead_scout", task_id=self.request.id)

        # At task completion
        await publish_agent_event(
            "agent_completed",
            "lead_scout",
            task_id=self.request.id,
            result={"leads_found": 5},
            duration_ms=45000
        )
        ```
    """
    import os

    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = await redis.from_url(redis_url)

        event = {
            "type": event_type,
            "agent": agent_name,
            "task_id": task_id,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if result:
            event["result"] = result
        if error:
            event["error"] = error
        if duration_ms is not None:
            event["duration_ms"] = duration_ms

        await client.publish("cockpit:events", json.dumps(event))
        await client.close()

        logger.debug(f"Published event to cockpit:events - {event_type} for {agent_name}")

    except Exception as e:
        logger.error(f"Failed to publish agent event: {e}")


async def publish_alert_event(
    severity: str,
    title: str,
    message: str,
    lead_id: Optional[str] = None,
    draft_id: Optional[str] = None
):
    """
    Publish an alert event to the cockpit.

    Args:
        severity: Alert severity (low, medium, high, critical)
        title: Alert title
        message: Alert message
        lead_id: Optional lead ID this alert relates to
        draft_id: Optional draft ID this alert relates to

    Example:
        ```python
        await publish_alert_event(
            severity="high",
            title="HOT Lead Reply",
            message="John Smith replied: interested",
            lead_id="lead_123"
        )
        ```
    """
    import os

    try:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        client = await redis.from_url(redis_url)

        event = {
            "type": "alert",
            "severity": severity,
            "title": title,
            "message": message,
            "timestamp": datetime.utcnow().isoformat(),
        }

        if lead_id:
            event["lead_id"] = lead_id
        if draft_id:
            event["draft_id"] = draft_id

        await client.publish("cockpit:events", json.dumps(event))
        await client.close()

        logger.info(f"Published alert: {severity} - {title}")

    except Exception as e:
        logger.error(f"Failed to publish alert event: {e}")


# ========== Exports ==========

__all__ = [
    "router",
    "manager",
    "publish_agent_event",
    "publish_alert_event",
]
