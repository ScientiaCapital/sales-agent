"""
Master Agent System - LangGraph-based Multi-Agent Orchestration

Implements a comprehensive multi-agent system using LangGraph best practices:
- StateGraph with shared state across all agents
- Inter-agent communication via LangGraph channels
- Redis persistence and durable execution
- Streaming support for real-time communication
- Subgraphs for modular agent composition
- Autonomous operation and decision making

Architecture:
    Master StateGraph containing all agents as subgraphs:
    - Shared state management via TypedDict
    - Inter-agent communication via channels
    - Redis checkpointer for persistence
    - Streaming support for real-time updates
    - Autonomous agent orchestration

Based on LangGraph documentation:
- https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph
- https://docs.langchain.com/oss/python/langgraph/workflows-agents
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/durable-execution
- https://docs.langchain.com/oss/python/langgraph/streaming
- https://docs.langchain.com/oss/python/langgraph/use-subgraphs
- https://docs.langchain.com/oss/python/langgraph/add-memory
- https://docs.langchain.com/oss/python/langgraph/pregel

Usage:
    ```python
    from app.services.langgraph.agents import MasterAgentSystem

    # Initialize the master agent system
    master_system = MasterAgentSystem()
    await master_system.initialize()

    # Process a complex task that requires multiple agents
    result = await master_system.process_task(
        task_type="contractor_research",
        task_data={
            "contractor_name": "ABC Construction",
            "business_address": "123 Main St, San Francisco, CA",
            "research_depth": "comprehensive"
        }
    )

    # Stream real-time updates
    async for update in master_system.stream_task(task_id=result.task_id):
        print(f"Agent {update.agent_id}: {update.status}")
    ```
"""

import os
import asyncio
import uuid
from typing import Dict, Any, List, Optional, Literal, TypedDict, Annotated
from datetime import datetime
from dataclasses import dataclass, field

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisCheckpointer
from langgraph.channels import Topic, LastValue
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage

from app.core.logging import get_logger

logger = get_logger(__name__)


# ========== Master Agent State Schema ==========

class MasterAgentState(TypedDict):
    """
    Shared state schema for all agents in the master system.
    
    This state is shared across all agents and persists throughout
    the entire task execution lifecycle.
    """
    # Task information
    task_id: str
    task_type: str
    task_data: Dict[str, Any]
    task_status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    updated_at: datetime
    
    # Agent coordination
    current_agent: Optional[str]
    agent_queue: List[str]
    completed_agents: List[str]
    failed_agents: List[str]
    
    # Inter-agent communication
    agent_messages: Annotated[List[Dict[str, Any]], Topic]
    shared_data: Dict[str, Any]
    agent_results: Dict[str, Any]
    
    # Task results
    final_result: Optional[Dict[str, Any]]
    confidence_score: float
    execution_metadata: Dict[str, Any]
    
    # Error handling
    errors: List[Dict[str, Any]]
    retry_count: int
    max_retries: int


# ========== Agent Capability Definitions ==========

@dataclass
class AgentCapability:
    """Agent capability definition for the master system."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    estimated_latency_ms: int = 1000
    cost_per_request: float = 0.001
    max_concurrent_tasks: int = 1
    dependencies: List[str] = field(default_factory=list)


# ========== Master Agent System ==========

class MasterAgentSystem:
    """
    Master agent system using LangGraph best practices.
    
    Implements a comprehensive multi-agent system with:
    - Shared state management
    - Inter-agent communication via channels
    - Redis persistence and durable execution
    - Streaming support
    - Autonomous operation
    """

    def __init__(
        self,
        redis_url: str = None,
        namespace: str = "master_agent_system"
    ):
        """
        Initialize the master agent system.
        
        Args:
            redis_url: Redis connection URL for persistence
            namespace: Redis namespace for this system
        """
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.namespace = namespace
        
        # Initialize Redis checkpointer
        self.checkpointer = RedisCheckpointer.from_conn_string(self.redis_url)
        
        # Agent capabilities registry
        self.agent_capabilities: Dict[str, AgentCapability] = {}
        
        # Master graph
        self.master_graph: Optional[StateGraph] = None
        self.compiled_graph = None
        
        # Streaming support
        self.streaming_tasks: Dict[str, asyncio.Task] = {}
        
        logger.info(f"MasterAgentSystem initialized with namespace: {namespace}")

    async def initialize(self):
        """Initialize the master agent system and build the graph."""
        try:
            # Register all agent capabilities
            await self._register_agent_capabilities()
            
            # Build the master graph
            await self._build_master_graph()
            
            # Compile the graph with persistence
            self.compiled_graph = self.master_graph.compile(
                checkpointer=self.checkpointer,
                interrupt_before=["human_review"],  # Human-in-the-loop support
                interrupt_after=["agent_completion"]  # Post-agent processing
            )
            
            logger.info("MasterAgentSystem initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MasterAgentSystem: {e}")
            raise

    async def _register_agent_capabilities(self):
        """Register all available agent capabilities."""
        # Reasoner Agent
        self.agent_capabilities["reasoner"] = AgentCapability(
            name="reasoner",
            description="Advanced reasoning and problem solving using DeepSeek",
            input_schema={
                "problem": "str",
                "context": "Dict[str, Any]",
                "constraints": "List[str]"
            },
            output_schema={
                "recommendation": "Dict[str, Any]",
                "confidence_score": "float",
                "reasoning_steps": "List[Dict[str, Any]]"
            },
            estimated_latency_ms=10000,
            cost_per_request=0.003
        )
        
        # Orchestrator Agent
        self.agent_capabilities["orchestrator"] = AgentCapability(
            name="orchestrator",
            description="High-level agent coordination and task delegation",
            input_schema={
                "task": "str",
                "context": "Dict[str, Any]",
                "available_agents": "List[str]"
            },
            output_schema={
                "execution_plan": "List[Dict[str, Any]]",
                "agent_assignments": "Dict[str, Any]",
                "estimated_duration": "int"
            },
            estimated_latency_ms=5000,
            cost_per_request=0.002
        )
        
        # Social Research Agent
        self.agent_capabilities["social_research"] = AgentCapability(
            name="social_research",
            description="Social media research across multiple platforms",
            input_schema={
                "company_name": "str",
                "platforms": "List[str]",
                "research_depth": "str"
            },
            output_schema={
                "total_mentions": "int",
                "overall_sentiment": "str",
                "platform_data": "Dict[str, Any]"
            },
            estimated_latency_ms=8000,
            cost_per_request=0.001
        )
        
        # LinkedIn Content Agent
        self.agent_capabilities["linkedin_content"] = AgentCapability(
            name="linkedin_content",
            description="LinkedIn content scraping and analysis",
            input_schema={
                "company_url": "str",
                "profile_urls": "List[str]",
                "content_types": "List[str]"
            },
            output_schema={
                "company_posts": "List[Dict[str, Any]]",
                "profile_posts": "List[Dict[str, Any]]",
                "engagement_metrics": "Dict[str, Any]"
            },
            estimated_latency_ms=6000,
            cost_per_request=0.001
        )
        
        # Contractor Reviews Agent
        self.agent_capabilities["contractor_reviews"] = AgentCapability(
            name="contractor_reviews",
            description="Contractor review scraping from Google, Yelp, BBB",
            input_schema={
                "contractor_name": "str",
                "business_address": "str",
                "platforms": "List[str]"
            },
            output_schema={
                "total_reviews": "int",
                "overall_rating": "float",
                "platform_summaries": "Dict[str, Any]"
            },
            estimated_latency_ms=5000,
            cost_per_request=0.001
        )
        
        # License Auditor Agent
        self.agent_capabilities["license_auditor"] = AgentCapability(
            name="license_auditor",
            description="Contractor license verification and compliance auditing",
            input_schema={
                "contractor_name": "str",
                "business_address": "str",
                "license_types": "List[str]"
            },
            output_schema={
                "licenses": "List[Dict[str, Any]]",
                "compliance_score": "float",
                "recommendations": "List[str]"
            },
            estimated_latency_ms=7000,
            cost_per_request=0.002
        )
        
        logger.info(f"Registered {len(self.agent_capabilities)} agent capabilities")

    async def _build_master_graph(self):
        """Build the master StateGraph with all agents as subgraphs."""
        # Create the master graph
        self.master_graph = StateGraph(MasterAgentState)
        
        # Add agent subgraphs
        await self._add_agent_subgraphs()
        
        # Add orchestration nodes
        self._add_orchestration_nodes()
        
        # Add edges and routing
        self._add_graph_edges()
        
        logger.info("Master graph built successfully")

    async def _add_agent_subgraphs(self):
        """Add all agent subgraphs to the master graph."""
        # Import agent subgraphs
        from .reasoner_agent import create_reasoner_subgraph
        from .orchestrator_agent import create_orchestrator_subgraph
        from .social_research_agent import create_social_research_subgraph
        from .linkedin_content_agent import create_linkedin_content_subgraph
        from .contractor_reviews_agent import create_contractor_reviews_subgraph
        from .license_auditor_agent import create_license_auditor_subgraph
        
        # Add each agent as a subgraph
        self.master_graph.add_subgraph("reasoner", create_reasoner_subgraph())
        self.master_graph.add_subgraph("orchestrator", create_orchestrator_subgraph())
        self.master_graph.add_subgraph("social_research", create_social_research_subgraph())
        self.master_graph.add_subgraph("linkedin_content", create_linkedin_content_subgraph())
        self.master_graph.add_subgraph("contractor_reviews", create_contractor_reviews_subgraph())
        self.master_graph.add_subgraph("license_auditor", create_license_auditor_subgraph())

    def _add_orchestration_nodes(self):
        """Add orchestration nodes for agent coordination."""
        # Task initialization
        self.master_graph.add_node("initialize_task", self._initialize_task_node)
        
        # Agent selection and routing
        self.master_graph.add_node("select_agents", self._select_agents_node)
        
        # Agent execution coordination
        self.master_graph.add_node("coordinate_execution", self._coordinate_execution_node)
        
        # Result aggregation
        self.master_graph.add_node("aggregate_results", self._aggregate_results_node)
        
        # Human review (interrupt point)
        self.master_graph.add_node("human_review", self._human_review_node)
        
        # Final processing
        self.master_graph.add_node("finalize_task", self._finalize_task_node)

    def _add_graph_edges(self):
        """Add edges and routing logic to the master graph."""
        # Set entry point
        self.master_graph.set_entry_point("initialize_task")
        
        # Linear flow
        self.master_graph.add_edge("initialize_task", "select_agents")
        self.master_graph.add_edge("select_agents", "coordinate_execution")
        self.master_graph.add_edge("coordinate_execution", "aggregate_results")
        self.master_graph.add_edge("aggregate_results", "human_review")
        self.master_graph.add_edge("human_review", "finalize_task")
        self.master_graph.add_edge("finalize_task", END)
        
        # Conditional routing for agent execution
        self.master_graph.add_conditional_edges(
            "coordinate_execution",
            self._route_agent_execution,
            {
                "reasoner": "reasoner",
                "orchestrator": "orchestrator",
                "social_research": "social_research",
                "linkedin_content": "linkedin_content",
                "contractor_reviews": "contractor_reviews",
                "license_auditor": "license_auditor",
                "continue": "aggregate_results",
                "retry": "coordinate_execution"
            }
        )

    # ========== Orchestration Node Functions ==========

    async def _initialize_task_node(self, state: MasterAgentState) -> Dict[str, Any]:
        """Initialize a new task."""
        task_id = str(uuid.uuid4())
        current_time = datetime.now()
        
        return {
            "task_id": task_id,
            "task_status": "running",
            "created_at": current_time,
            "updated_at": current_time,
            "agent_queue": [],
            "completed_agents": [],
            "failed_agents": [],
            "agent_messages": [],
            "shared_data": {},
            "agent_results": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3
        }

    async def _select_agents_node(self, state: MasterAgentState) -> Dict[str, Any]:
        """Select appropriate agents for the task."""
        task_type = state["task_type"]
        task_data = state["task_data"]
        
        # Agent selection logic based on task type
        selected_agents = []
        
        if task_type == "contractor_research":
            selected_agents = ["contractor_reviews", "license_auditor", "social_research"]
        elif task_type == "social_media_analysis":
            selected_agents = ["social_research", "linkedin_content"]
        elif task_type == "complex_reasoning":
            selected_agents = ["reasoner", "orchestrator"]
        elif task_type == "comprehensive_analysis":
            selected_agents = ["orchestrator", "reasoner", "social_research", "linkedin_content"]
        
        return {
            "agent_queue": selected_agents,
            "current_agent": selected_agents[0] if selected_agents else None
        }

    async def _coordinate_execution_node(self, state: MasterAgentState) -> Dict[str, Any]:
        """Coordinate agent execution."""
        if not state["agent_queue"]:
            return {"task_status": "completed"}
        
        current_agent = state["agent_queue"][0]
        task_data = state["task_data"]
        
        # Send message to current agent
        agent_message = {
            "from_agent": "master",
            "to_agent": current_agent,
            "message_type": "task_request",
            "payload": {
                "task_data": task_data,
                "shared_data": state["shared_data"]
            },
            "timestamp": datetime.now().isoformat()
        }
        
        return {
            "current_agent": current_agent,
            "agent_messages": state["agent_messages"] + [agent_message]
        }

    async def _aggregate_results_node(self, state: MasterAgentState) -> Dict[str, Any]:
        """Aggregate results from all agents."""
        agent_results = state["agent_results"]
        completed_agents = state["completed_agents"]
        
        # Aggregate results based on agent types
        aggregated_result = {
            "total_agents": len(completed_agents),
            "agent_results": agent_results,
            "aggregation_timestamp": datetime.now().isoformat()
        }
        
        # Calculate overall confidence score
        confidence_scores = [
            result.get("confidence_score", 0.5) 
            for result in agent_results.values()
        ]
        overall_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.5
        
        return {
            "final_result": aggregated_result,
            "confidence_score": overall_confidence,
            "task_status": "completed"
        }

    async def _human_review_node(self, state: MasterAgentState) -> Dict[str, Any]:
        """Human review node (interrupt point)."""
        # This node will interrupt for human review
        # The human can approve, reject, or modify the results
        return {
            "task_status": "awaiting_human_review"
        }

    async def _finalize_task_node(self, state: MasterAgentState) -> Dict[str, Any]:
        """Finalize the task and prepare results."""
        return {
            "task_status": "completed",
            "updated_at": datetime.now(),
            "execution_metadata": {
                "total_execution_time": (datetime.now() - state["created_at"]).total_seconds(),
                "agents_used": state["completed_agents"],
                "final_confidence": state["confidence_score"]
            }
        }

    def _route_agent_execution(self, state: MasterAgentState) -> str:
        """Route to appropriate agent or continue processing."""
        if state["agent_queue"]:
            return state["agent_queue"][0]
        else:
            return "continue"

    # ========== Public Interface ==========

    async def process_task(
        self,
        task_type: str,
        task_data: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a task using the master agent system.
        
        Args:
            task_type: Type of task to process
            task_data: Task-specific data
            config: Optional configuration
            
        Returns:
            Task result with execution metadata
        """
        if not self.compiled_graph:
            raise RuntimeError("MasterAgentSystem not initialized")
        
        # Create initial state
        initial_state = {
            "task_id": str(uuid.uuid4()),
            "task_type": task_type,
            "task_data": task_data,
            "task_status": "pending",
            "created_at": datetime.now(),
            "updated_at": datetime.now(),
            "current_agent": None,
            "agent_queue": [],
            "completed_agents": [],
            "failed_agents": [],
            "agent_messages": [],
            "shared_data": {},
            "agent_results": {},
            "final_result": None,
            "confidence_score": 0.0,
            "execution_metadata": {},
            "errors": [],
            "retry_count": 0,
            "max_retries": 3
        }
        
        # Execute the graph
        result = await self.compiled_graph.ainvoke(
            initial_state,
            config=config or {}
        )
        
        return result

    async def stream_task(
        self,
        task_id: str,
        config: Optional[Dict[str, Any]] = None
    ):
        """
        Stream real-time updates for a task.
        
        Args:
            task_id: Task ID to stream
            config: Optional configuration
            
        Yields:
            Real-time task updates
        """
        if not self.compiled_graph:
            raise RuntimeError("MasterAgentSystem not initialized")
        
        # Stream the graph execution
        async for chunk in self.compiled_graph.astream(
            {"task_id": task_id},
            config=config or {}
        ):
            yield chunk

    async def get_task_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of a task."""
        if not self.compiled_graph:
            raise RuntimeError("MasterAgentSystem not initialized")
        
        # Get task state from checkpointer
        try:
            state = await self.compiled_graph.aget_state({"task_id": task_id})
            return state.values if state else None
        except Exception as e:
            logger.error(f"Failed to get task status: {e}")
            return None

    async def resume_task(
        self,
        task_id: str,
        action: str = "continue",
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Resume a paused task (e.g., after human review).
        
        Args:
            task_id: Task ID to resume
            action: Action to take (continue, retry, cancel)
            config: Optional configuration
            
        Returns:
            Updated task result
        """
        if not self.compiled_graph:
            raise RuntimeError("MasterAgentSystem not initialized")
        
        # Resume the graph execution
        result = await self.compiled_graph.ainvoke(
            {"task_id": task_id, "action": action},
            config=config or {}
        )
        
        return result

    # ========== Agent Management ==========

    def get_available_agents(self) -> List[str]:
        """Get list of available agent types."""
        return list(self.agent_capabilities.keys())

    def get_agent_capability(self, agent_type: str) -> Optional[AgentCapability]:
        """Get capability information for a specific agent."""
        return self.agent_capabilities.get(agent_type)

    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on the master system."""
        try:
            # Test Redis connection
            await self.checkpointer.aget_tuple({"test": "health_check"})
            redis_status = "healthy"
        except Exception as e:
            redis_status = f"unhealthy: {e}"
        
        return {
            "system_status": "healthy" if redis_status == "healthy" else "degraded",
            "redis_status": redis_status,
            "available_agents": len(self.agent_capabilities),
            "agent_types": list(self.agent_capabilities.keys()),
            "timestamp": datetime.now().isoformat()
        }
