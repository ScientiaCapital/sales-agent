"""
WebSocket streaming API endpoints

Provides real-time agent streaming via WebSocket connections with Redis pub/sub.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException, Depends
from sqlalchemy.orm import Session
from typing import Dict, Set
import redis.asyncio as redis
import asyncio
import json
from uuid import UUID, uuid4
from datetime import datetime

from app.models import get_db, AgentWorkflow, Lead
from app.services.claude_streaming import ClaudeStreamingService
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/api/stream", tags=["streaming"])

# Global connection manager
active_streams: Dict[str, Set[WebSocket]] = {}

# Redis client (will be initialized in lifespan)
redis_client: redis.Redis | None = None


async def get_redis():
    """Get Redis client for pub/sub"""
    global redis_client
    if redis_client is None:
        import os
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        redis_client = await redis.from_url(redis_url)
    return redis_client


class ConnectionManager:
    """Manage WebSocket connections for streaming"""
    
    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, stream_id: str, websocket: WebSocket):
        """Accept and track new WebSocket connection"""
        await websocket.accept()
        
        if stream_id not in self.active_connections:
            self.active_connections[stream_id] = set()
        
        self.active_connections[stream_id].add(websocket)
        logger.info(f"Client connected to stream {stream_id}")
    
    def disconnect(self, stream_id: str, websocket: WebSocket):
        """Remove WebSocket connection"""
        if stream_id in self.active_connections:
            self.active_connections[stream_id].discard(websocket)
            
            # Cleanup empty stream
            if not self.active_connections[stream_id]:
                del self.active_connections[stream_id]
        
        logger.info(f"Client disconnected from stream {stream_id}")
    
    async def send_personal(self, message: str, websocket: WebSocket):
        """Send message to specific connection"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
    
    async def broadcast(self, stream_id: str, message: str):
        """Broadcast message to all connections on stream"""
        if stream_id in self.active_connections:
            for connection in self.active_connections[stream_id].copy():
                try:
                    await connection.send_text(message)
                except Exception as e:
                    logger.error(f"Broadcast failed, removing connection: {e}")
                    self.disconnect(stream_id, connection)


manager = ConnectionManager()

# Initialize Claude streaming service
claude_service = ClaudeStreamingService()


@router.post("/start/{lead_id}", status_code=201)
async def start_agent_stream(
    lead_id: int,
    agent_type: str = "qualification",
    db: Session = Depends(get_db)
):
    """
    Start a streaming agent workflow
    
    Creates a workflow and returns stream ID for WebSocket connection.
    
    Args:
        lead_id: Lead to process
        agent_type: Type of agent workflow (qualification, enrichment, full)
        
    Returns:
        Dict with stream_id and workflow_id for WebSocket connection
    """
    
    # Verify lead exists
    lead = db.query(Lead).filter(Lead.id == lead_id).first()
    if not lead:
        raise HTTPException(status_code=404, detail=f"Lead {lead_id} not found")
    
    # Create workflow
    workflow_id = uuid4()
    workflow = AgentWorkflow(
        id=workflow_id,
        name=f"{agent_type}_stream",
        lead_id=lead_id,
        current_step="initializing",
        status="pending",
        created_at=datetime.now()
    )
    
    db.add(workflow)
    db.commit()
    
    # Generate stream ID (use workflow ID for simplicity)
    stream_id = str(workflow_id)
    
    # Start background streaming task
    asyncio.create_task(
        stream_agent_workflow(stream_id, lead_id, agent_type, db)
    )
    
    logger.info(f"Started stream {stream_id} for lead {lead_id}")
    
    return {
        "stream_id": stream_id,
        "workflow_id": str(workflow_id),
        "status": "streaming",
        "websocket_url": f"/ws/stream/{stream_id}"
    }


async def stream_agent_workflow(
    stream_id: str,
    lead_id: int,
    agent_type: str,
    db: Session
):
    """
    Background task to stream agent responses via Redis
    
    Args:
        stream_id: Stream identifier
        lead_id: Lead being processed
        agent_type: Agent workflow type
        db: Database session
    """
    
    try:
        # Get lead data
        lead = db.query(Lead).filter(Lead.id == lead_id).first()
        if not lead:
            await publish_error(stream_id, f"Lead {lead_id} not found")
            return
        
        # Build lead context
        lead_data = {
            "company_name": lead.company_name,
            "company_website": lead.company_website,
            "industry": lead.industry,
            "company_size": lead.company_size,
            "contact_name": lead.contact_name,
            "contact_title": lead.contact_title
        }
        
        # System prompt based on agent type
        system_prompts = {
            "qualification": """You are an AI sales qualification specialist.
Analyze the lead and provide a qualification score (0-100) with detailed reasoning.
Focus on company fit, decision-maker quality, and sales potential.""",
            
            "enrichment": """You are a lead enrichment specialist.
Enhance the provided lead data with insights about the company, industry trends, and potential pain points.""",
            
            "growth": """You are a growth hacking strategist.
Analyze this lead and provide market expansion opportunities and growth strategies."""
        }
        
        system_prompt = system_prompts.get(agent_type, system_prompts["qualification"])
        
        # Get Redis client
        r = await get_redis()
        
        # Publish start event
        await r.publish(
            f"stream:{stream_id}",
            json.dumps({
                "type": "start",
                "stream_id": stream_id,
                "agent_type": agent_type,
                "timestamp": datetime.now().isoformat()
            })
        )
        
        # Stream from Claude
        async for chunk in claude_service.stream_agent_response(
            agent_type=agent_type,
            lead_data=lead_data,
            system_prompt=system_prompt,
            temperature=0.7,
            max_tokens=1024
        ):
            # Publish to Redis channel
            await r.publish(
                f"stream:{stream_id}",
                json.dumps(chunk)
            )
            
            # Check if complete or error
            if chunk["type"] in ["complete", "error"]:
                break
        
        logger.info(f"Stream {stream_id} completed successfully")
        
    except Exception as e:
        logger.error(f"Stream {stream_id} failed: {e}", exc_info=True)
        await publish_error(stream_id, str(e))


async def publish_error(stream_id: str, error_message: str):
    """Publish error message to stream"""
    r = await get_redis()
    await r.publish(
        f"stream:{stream_id}",
        json.dumps({
            "type": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        })
    )


@router.websocket("/ws/{stream_id}")
async def websocket_stream_endpoint(websocket: WebSocket, stream_id: str):
    """
    WebSocket endpoint for receiving agent stream
    
    Connects to Redis pub/sub and forwards messages to client in real-time.
    
    Args:
        websocket: WebSocket connection
        stream_id: Stream identifier from /start endpoint
    """
    
    await manager.connect(stream_id, websocket)
    
    try:
        # Get Redis client and subscribe to channel
        r = await get_redis()
        
        async with r.pubsub() as pubsub:
            await pubsub.subscribe(f"stream:{stream_id}")
            
            logger.info(f"WebSocket subscribed to stream:{stream_id}")
            
            # Listen for messages
            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                
                if message is not None:
                    # Forward to WebSocket
                    data = message["data"].decode()
                    await manager.send_personal(data, websocket)
                    
                    # Parse and check if stream complete
                    try:
                        parsed = json.loads(data)
                        if parsed["type"] in ["complete", "error"]:
                            logger.info(f"Stream {stream_id} finished: {parsed['type']}")
                            break
                    except json.JSONDecodeError:
                        pass
                
                # Check if client still connected
                try:
                    await asyncio.wait_for(
                        websocket.receive_text(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    # No message from client, continue listening
                    pass
                except Exception:
                    # Client disconnected
                    break
        
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected from stream {stream_id}")
    
    except Exception as e:
        logger.error(f"WebSocket error on stream {stream_id}: {e}", exc_info=True)
    
    finally:
        manager.disconnect(stream_id, websocket)


@router.get("/status/{stream_id}")
async def get_stream_status(stream_id: str, db: Session = Depends(get_db)):
    """
    Get status of a streaming workflow
    
    Args:
        stream_id: Stream/workflow identifier
        
    Returns:
        Workflow status and metadata
    """
    
    try:
        workflow_uuid = UUID(stream_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid stream_id format")
    
    workflow = db.query(AgentWorkflow).filter(AgentWorkflow.id == workflow_uuid).first()
    
    if not workflow:
        raise HTTPException(status_code=404, detail=f"Stream {stream_id} not found")
    
    # Check active connections
    active_connections = len(manager.active_connections.get(stream_id, set()))
    
    return {
        "stream_id": stream_id,
        "workflow_id": str(workflow.id),
        "status": workflow.status,
        "current_step": workflow.current_step,
        "active_connections": active_connections,
        "total_latency_ms": workflow.total_latency_ms,
        "total_cost_usd": workflow.total_cost_usd,
        "created_at": workflow.created_at.isoformat() if workflow.created_at else None,
        "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None
    }
