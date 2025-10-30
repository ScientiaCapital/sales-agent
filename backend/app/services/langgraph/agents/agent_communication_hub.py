"""
Agent Communication Hub - Inter-Agent Communication and Autonomous Operation

Provides a centralized communication system for all LangGraph agents to communicate,
share state, and operate autonomously. Enables agent discovery, message routing,
and collaborative decision-making across the entire agent ecosystem.

Features:
- Agent discovery and registration
- Inter-agent message routing
- Shared state management
- Autonomous operation coordination
- Event-driven communication
- Agent health monitoring
- Load balancing and failover

Architecture:
    Centralized Hub with Redis pub/sub for real-time communication
    - Agent Registry: Tracks all available agents and their capabilities
    - Message Router: Routes messages between agents
    - State Manager: Manages shared state across agents
    - Event Bus: Handles event-driven communication
    - Health Monitor: Monitors agent health and availability

Usage:
    ```python
    from app.services.langgraph.agents import AgentCommunicationHub

    # Initialize the communication hub
    hub = AgentCommunicationHub()

    # Register agents
    await hub.register_agent("reasoner", ReasonerAgent())
    await hub.register_agent("orchestrator", OrchestratorAgent())

    # Send message between agents
    await hub.send_message(
        from_agent="orchestrator",
        to_agent="reasoner",
        message_type="reasoning_request",
        payload={"problem": "Complex strategic decision"}
    )

    # Broadcast to all agents
    await hub.broadcast_message(
        from_agent="orchestrator",
        message_type="system_update",
        payload={"status": "maintenance_mode"}
    )
    ```
"""

import os
import json
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Callable, Union
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

import redis.asyncio as redis
from pydantic import BaseModel, Field

from app.core.logging import setup_logging as get_logger

logger = get_logger(__name__)


# ========== Enums and Models ==========

class MessageType(str, Enum):
    """Types of inter-agent messages."""
    # System messages
    AGENT_REGISTRATION = "agent_registration"
    AGENT_HEARTBEAT = "agent_heartbeat"
    AGENT_SHUTDOWN = "agent_shutdown"
    
    # Task coordination
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    TASK_DELEGATION = "task_delegation"
    TASK_COMPLETION = "task_completion"
    
    # Data sharing
    DATA_SHARE = "data_share"
    STATE_UPDATE = "state_update"
    RESULT_SHARE = "result_share"
    
    # Collaboration
    COLLABORATION_REQUEST = "collaboration_request"
    COLLABORATION_RESPONSE = "collaboration_response"
    EXPERT_CONSULTATION = "expert_consultation"
    
    # Events
    EVENT_NOTIFICATION = "event_notification"
    ALERT = "alert"
    BROADCAST = "broadcast"


class AgentStatus(str, Enum):
    """Agent status states."""
    REGISTERING = "registering"
    ACTIVE = "active"
    BUSY = "busy"
    IDLE = "idle"
    ERROR = "error"
    OFFLINE = "offline"


class MessagePriority(str, Enum):
    """Message priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class AgentCapability:
    """Agent capability definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    max_concurrent_tasks: int = 1
    estimated_latency_ms: int = 1000
    cost_per_request: float = 0.001


@dataclass
class AgentInfo:
    """Agent registration information."""
    agent_id: str
    agent_type: str
    instance: Any
    capabilities: List[AgentCapability]
    status: AgentStatus = AgentStatus.REGISTERING
    last_heartbeat: datetime = field(default_factory=datetime.now)
    current_tasks: int = 0
    total_tasks_completed: int = 0
    error_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class InterAgentMessage(BaseModel):
    """Inter-agent message structure."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str
    to_agent: Optional[str] = None  # None for broadcast messages
    message_type: MessageType
    priority: MessagePriority = MessagePriority.NORMAL
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    ttl_seconds: int = 3600  # Time to live


class AgentCommunicationHub:
    """
    Centralized communication hub for all LangGraph agents.
    
    Enables autonomous operation, inter-agent communication, and collaborative
    decision-making across the entire agent ecosystem.
    """

    def __init__(
        self,
        redis_url: str = None,
        namespace: str = "agent_hub",
        heartbeat_interval: int = 30,
        message_ttl: int = 3600
    ):
        """
        Initialize the Agent Communication Hub.
        
        Args:
            redis_url: Redis connection URL for pub/sub
            namespace: Redis key namespace for this hub
            heartbeat_interval: Heartbeat interval in seconds
            message_ttl: Message time-to-live in seconds
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.namespace = namespace
        self.heartbeat_interval = heartbeat_interval
        self.message_ttl = message_ttl
        
        # Initialize Redis connection
        self.redis_client = None
        self.pubsub = None
        
        # Agent registry
        self.agents: Dict[str, AgentInfo] = {}
        self.agent_capabilities: Dict[str, List[AgentCapability]] = {}
        
        # Message handlers
        self.message_handlers: Dict[MessageType, List[Callable]] = {}
        
        # Health monitoring
        self.health_check_interval = 60
        self.agent_timeout = 300  # 5 minutes
        
        # Event callbacks
        self.event_callbacks: Dict[str, List[Callable]] = {}
        
        logger.info(f"AgentCommunicationHub initialized with namespace: {namespace}")

    async def initialize(self):
        """Initialize Redis connection and start background tasks."""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            self.pubsub = self.redis_client.pubsub()
            
            # Subscribe to all agent messages
            await self.pubsub.subscribe(f"{self.namespace}:messages")
            
            # Start background tasks
            asyncio.create_task(self._heartbeat_monitor())
            asyncio.create_task(self._message_processor())
            asyncio.create_task(self._health_monitor())
            
            logger.info("AgentCommunicationHub initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AgentCommunicationHub: {e}")
            raise

    async def register_agent(
        self,
        agent_id: str,
        agent_type: str,
        instance: Any,
        capabilities: List[AgentCapability],
        metadata: Dict[str, Any] = None
    ) -> bool:
        """
        Register an agent with the communication hub.
        
        Args:
            agent_id: Unique identifier for the agent
            agent_type: Type of agent (reasoner, orchestrator, etc.)
            instance: Agent instance
            capabilities: List of agent capabilities
            metadata: Additional agent metadata
            
        Returns:
            True if registration successful, False otherwise
        """
        try:
            agent_info = AgentInfo(
                agent_id=agent_id,
                agent_type=agent_type,
                instance=instance,
                capabilities=capabilities,
                status=AgentStatus.ACTIVE,
                metadata=metadata or {}
            )
            
            self.agents[agent_id] = agent_info
            self.agent_capabilities[agent_id] = capabilities
            
            # Notify other agents of new registration
            await self.broadcast_message(
                from_agent="system",
                message_type=MessageType.AGENT_REGISTRATION,
                payload={
                    "agent_id": agent_id,
                    "agent_type": agent_type,
                    "capabilities": [cap.name for cap in capabilities]
                }
            )
            
            logger.info(f"Agent registered: {agent_id} ({agent_type})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register agent {agent_id}: {e}")
            return False

    async def send_message(
        self,
        from_agent: str,
        to_agent: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        correlation_id: str = None,
        reply_to: str = None
    ) -> str:
        """
        Send a message from one agent to another.
        
        Args:
            from_agent: Sender agent ID
            to_agent: Recipient agent ID
            message_type: Type of message
            payload: Message payload
            priority: Message priority
            correlation_id: Correlation ID for tracking
            reply_to: Reply-to message ID
            
        Returns:
            Message ID for tracking
        """
        message = InterAgentMessage(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type=message_type,
            priority=priority,
            payload=payload,
            correlation_id=correlation_id,
            reply_to=reply_to
        )
        
        # Publish message to Redis
        channel = f"{self.namespace}:agent:{to_agent}"
        await self.redis_client.publish(channel, message.json())
        
        # Store message for persistence
        message_key = f"{self.namespace}:message:{message.message_id}"
        await self.redis_client.setex(
            message_key,
            self.message_ttl,
            message.json()
        )
        
        logger.debug(f"Message sent: {from_agent} -> {to_agent} ({message_type})")
        return message.message_id

    async def broadcast_message(
        self,
        from_agent: str,
        message_type: MessageType,
        payload: Dict[str, Any],
        priority: MessagePriority = MessagePriority.NORMAL,
        exclude_agents: List[str] = None
    ) -> str:
        """
        Broadcast a message to all agents.
        
        Args:
            from_agent: Sender agent ID
            message_type: Type of message
            payload: Message payload
            priority: Message priority
            exclude_agents: List of agent IDs to exclude
            
        Returns:
            Message ID for tracking
        """
        message = InterAgentMessage(
            from_agent=from_agent,
            to_agent=None,  # None indicates broadcast
            message_type=message_type,
            priority=priority,
            payload=payload
        )
        
        # Publish to broadcast channel
        channel = f"{self.namespace}:broadcast"
        await self.redis_client.publish(channel, message.json())
        
        # Store message for persistence
        message_key = f"{self.namespace}:broadcast:{message.message_id}"
        await self.redis_client.setex(
            message_key,
            self.message_ttl,
            message.json()
        )
        
        logger.debug(f"Broadcast message: {from_agent} ({message_type})")
        return message.message_id

    async def request_agent_capability(
        self,
        from_agent: str,
        capability_name: str,
        payload: Dict[str, Any],
        timeout: int = 30
    ) -> Optional[Dict[str, Any]]:
        """
        Request a specific capability from any available agent.
        
        Args:
            from_agent: Requesting agent ID
            capability_name: Name of capability to request
            payload: Request payload
            timeout: Request timeout in seconds
            
        Returns:
            Response payload or None if timeout/no response
        """
        # Find agents with the requested capability
        capable_agents = [
            agent_id for agent_id, capabilities in self.agent_capabilities.items()
            if any(cap.name == capability_name for cap in capabilities)
        ]
        
        if not capable_agents:
            logger.warning(f"No agents found with capability: {capability_name}")
            return None
        
        # Select best agent (simple round-robin for now)
        selected_agent = capable_agents[0]
        
        # Send capability request
        correlation_id = str(uuid.uuid4())
        message_id = await self.send_message(
            from_agent=from_agent,
            to_agent=selected_agent,
            message_type=MessageType.TASK_REQUEST,
            payload={
                "capability": capability_name,
                "request_payload": payload
            },
            correlation_id=correlation_id
        )
        
        # Wait for response (simplified - in production would use proper async waiting)
        await asyncio.sleep(1)  # Placeholder for actual response handling
        
        logger.info(f"Capability request sent: {capability_name} to {selected_agent}")
        return {"status": "requested", "message_id": message_id}

    async def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get status information for a specific agent."""
        if agent_id not in self.agents:
            return None
        
        agent = self.agents[agent_id]
        return {
            "agent_id": agent.agent_id,
            "agent_type": agent.agent_type,
            "status": agent.status.value,
            "capabilities": [cap.name for cap in agent.capabilities],
            "current_tasks": agent.current_tasks,
            "total_tasks_completed": agent.total_tasks_completed,
            "error_count": agent.error_count,
            "last_heartbeat": agent.last_heartbeat.isoformat(),
            "metadata": agent.metadata
        }

    async def get_all_agents(self) -> Dict[str, Dict[str, Any]]:
        """Get status information for all registered agents."""
        return {
            agent_id: await self.get_agent_status(agent_id)
            for agent_id in self.agents.keys()
        }

    async def get_agents_by_capability(self, capability_name: str) -> List[str]:
        """Get list of agent IDs that have a specific capability."""
        return [
            agent_id for agent_id, capabilities in self.agent_capabilities.items()
            if any(cap.name == capability_name for cap in capabilities)
        ]

    # ========== Background Tasks ==========

    async def _heartbeat_monitor(self):
        """Monitor agent heartbeats and update status."""
        while True:
            try:
                current_time = datetime.now()
                
                for agent_id, agent in self.agents.items():
                    if agent.status == AgentStatus.OFFLINE:
                        continue
                    
                    # Check if agent is overdue for heartbeat
                    time_since_heartbeat = (current_time - agent.last_heartbeat).total_seconds()
                    
                    if time_since_heartbeat > self.agent_timeout:
                        logger.warning(f"Agent {agent_id} heartbeat timeout")
                        agent.status = AgentStatus.OFFLINE
                        
                        # Notify other agents
                        await self.broadcast_message(
                            from_agent="system",
                            message_type=MessageType.AGENT_SHUTDOWN,
                            payload={"agent_id": agent_id, "reason": "heartbeat_timeout"}
                        )
                
                await asyncio.sleep(self.heartbeat_interval)
                
            except Exception as e:
                logger.error(f"Heartbeat monitor error: {e}")
                await asyncio.sleep(5)

    async def _message_processor(self):
        """Process incoming messages from Redis pub/sub."""
        while True:
            try:
                message = await self.pubsub.get_message(timeout=1.0)
                
                if message and message['type'] == 'message':
                    try:
                        message_data = json.loads(message['data'])
                        await self._handle_message(message_data)
                    except json.JSONDecodeError as e:
                        logger.error(f"Failed to parse message: {e}")
                
            except Exception as e:
                logger.error(f"Message processor error: {e}")
                await asyncio.sleep(1)

    async def _health_monitor(self):
        """Monitor overall system health."""
        while True:
            try:
                active_agents = len([a for a in self.agents.values() if a.status == AgentStatus.ACTIVE])
                total_agents = len(self.agents)
                
                health_status = {
                    "active_agents": active_agents,
                    "total_agents": total_agents,
                    "health_score": (active_agents / total_agents * 100) if total_agents > 0 else 0,
                    "timestamp": datetime.now().isoformat()
                }
                
                # Store health status
                health_key = f"{self.namespace}:health"
                await self.redis_client.setex(
                    health_key,
                    300,  # 5 minutes
                    json.dumps(health_status)
                )
                
                await asyncio.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Health monitor error: {e}")
                await asyncio.sleep(30)

    async def _handle_message(self, message_data: Dict[str, Any]):
        """Handle incoming message."""
        try:
            message = InterAgentMessage(**message_data)
            
            # Update agent heartbeat if it's a heartbeat message
            if message.message_type == MessageType.AGENT_HEARTBEAT:
                if message.from_agent in self.agents:
                    self.agents[message.from_agent].last_heartbeat = datetime.now()
                    self.agents[message.from_agent].status = AgentStatus.ACTIVE
            
            # Call registered message handlers
            if message.message_type in self.message_handlers:
                for handler in self.message_handlers[message.message_type]:
                    try:
                        await handler(message)
                    except Exception as e:
                        logger.error(f"Message handler error: {e}")
            
        except Exception as e:
            logger.error(f"Failed to handle message: {e}")

    # ========== Event System ==========

    def register_message_handler(
        self,
        message_type: MessageType,
        handler: Callable[[InterAgentMessage], None]
    ):
        """Register a message handler for a specific message type."""
        if message_type not in self.message_handlers:
            self.message_handlers[message_type] = []
        self.message_handlers[message_type].append(handler)

    def register_event_callback(
        self,
        event_name: str,
        callback: Callable[[Dict[str, Any]], None]
    ):
        """Register an event callback."""
        if event_name not in self.event_callbacks:
            self.event_callbacks[event_name] = []
        self.event_callbacks[event_name].append(callback)

    async def emit_event(self, event_name: str, data: Dict[str, Any]):
        """Emit an event to all registered callbacks."""
        if event_name in self.event_callbacks:
            for callback in self.event_callbacks[event_name]:
                try:
                    await callback(data)
                except Exception as e:
                    logger.error(f"Event callback error: {e}")

    # ========== Cleanup ==========

    async def shutdown(self):
        """Shutdown the communication hub."""
        try:
            # Notify all agents of shutdown
            await self.broadcast_message(
                from_agent="system",
                message_type=MessageType.AGENT_SHUTDOWN,
                payload={"reason": "hub_shutdown"}
            )
            
            # Close Redis connections
            if self.pubsub:
                await self.pubsub.close()
            if self.redis_client:
                await self.redis_client.close()
            
            logger.info("AgentCommunicationHub shutdown complete")
            
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")


# ========== Global Hub Instance ==========

# Global communication hub instance
_global_hub: Optional[AgentCommunicationHub] = None

async def get_communication_hub() -> AgentCommunicationHub:
    """Get the global communication hub instance."""
    global _global_hub
    
    if _global_hub is None:
        _global_hub = AgentCommunicationHub()
        await _global_hub.initialize()
    
    return _global_hub

async def shutdown_communication_hub():
    """Shutdown the global communication hub."""
    global _global_hub
    
    if _global_hub:
        await _global_hub.shutdown()
        _global_hub = None
