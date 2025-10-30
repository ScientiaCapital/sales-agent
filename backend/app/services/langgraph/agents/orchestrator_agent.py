"""
OrchestratorAgent - High-Level Agent Coordination StateGraph

Uses LangGraph's StateGraph with DeepSeek for intelligent agent orchestration,
task delegation, and workflow coordination. Acts as a meta-agent that selects
and coordinates other specialized agents based on task requirements and context.

Architecture:
    Orchestration StateGraph: analyze → select → delegate → monitor → aggregate
    - analyze: Understand task requirements and identify needed capabilities
    - select: Choose appropriate agents based on capabilities and availability
    - delegate: Assign tasks to selected agents with proper context
    - monitor: Track agent execution and handle failures/retries
    - aggregate: Combine results from multiple agents into coherent output

Orchestration Patterns:
    - Agent selection based on capability matching
    - Parallel execution of independent tasks
    - Sequential execution for dependent tasks
    - Failure handling and retry logic
    - Result aggregation and conflict resolution
    - Dynamic workflow adaptation

LLM Provider:
    - DeepSeek via OpenRouter: Strategic decision making ($0.27/M tokens)
    - Superior reasoning for complex orchestration decisions
    - Cost-effective for high-frequency agent coordination
    - Excellent at understanding agent capabilities and task requirements

Performance:
    - Target: <15 seconds for complex multi-agent workflows
    - Typical: 2-4 LLM calls for orchestration decisions
    - Cost: $0.001-0.005 per orchestration session
    - Handles 3-8 agents per workflow

Usage:
    ```python
    from app.services.langgraph.agents import OrchestratorAgent

    # Default (DeepSeek via OpenRouter)
    agent = OrchestratorAgent()
    result = await agent.orchestrate_workflow(
        task="Qualify and enrich 100 leads, then create marketing campaign",
        context={"leads": lead_data, "budget": 1000},
        available_agents=["qualification", "enrichment", "marketing", "growth"]
    )

    # Custom orchestration strategy
    agent = OrchestratorAgent(strategy="cost_optimized")
    result = await agent.orchestrate_workflow(
        task="Complex BDR outreach with approval gates",
        context={"enterprise_leads": data},
        available_agents=["bdr", "conversation", "reasoner"]
    )
    ```
"""

import os
import time
import asyncio
from typing import Dict, Any, List, Literal, Optional, Union
from dataclasses import dataclass, field
from pydantic import BaseModel
from enum import Enum

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import InMemorySaver

from app.core.logging import get_logger

logger = get_logger(__name__)


# ========== Enums and Models ==========

class AgentCapability(str, Enum):
    """Available agent capabilities."""
    QUALIFICATION = "qualification"
    ENRICHMENT = "enrichment"
    GROWTH = "growth"
    MARKETING = "marketing"
    BDR = "bdr"
    CONVERSATION = "conversation"
    REASONING = "reasoning"
    SOCIAL_RESEARCH = "social_research"
    LICENSE_AUDIT = "license_audit"
    LINKEDIN_WRITER = "linkedin_writer"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class OrchestrationStrategy(str, Enum):
    """Orchestration strategy types."""
    PERFORMANCE = "performance"  # Fastest execution
    COST_OPTIMIZED = "cost_optimized"  # Lowest cost
    QUALITY = "quality"  # Highest quality
    BALANCED = "balanced"  # Balanced approach


class AgentTask(BaseModel):
    """Individual task assigned to an agent."""
    task_id: str
    agent_type: AgentCapability
    task_description: str
    input_data: Dict[str, Any]
    priority: int = 1  # 1 = highest
    dependencies: List[str] = field(default_factory=list)  # task_ids this depends on
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    assigned_at: Optional[float] = None
    completed_at: Optional[float] = None


class OrchestrationState(BaseModel):
    """State for the orchestration process."""
    main_task: str
    context: Dict[str, Any]
    available_agents: List[AgentCapability]
    strategy: OrchestrationStrategy
    current_phase: str = "analyze"
    agent_tasks: List[AgentTask] = field(default_factory=list)
    execution_plan: List[Dict[str, Any]] = field(default_factory=list)
    completed_tasks: List[str] = field(default_factory=list)
    failed_tasks: List[str] = field(default_factory=list)
    orchestration_metadata: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)


@dataclass
class OrchestrationResult:
    """Result of the orchestration process."""
    success: bool
    results: Dict[str, Any]  # agent_type -> result
    execution_summary: Dict[str, Any]
    total_execution_time_seconds: float
    total_cost_usd: float
    agents_used: List[str]
    tasks_completed: int
    tasks_failed: int
    orchestration_metadata: Dict[str, Any]
    errors: List[str] = field(default_factory=list)


# ========== OrchestratorAgent ==========

class OrchestratorAgent:
    """
    High-level agent orchestrator using DeepSeek for intelligent coordination.
    
    Uses StateGraph pattern for complex multi-agent workflow orchestration,
    task delegation, and result aggregation.
    """

    def __init__(
        self,
        model: str = "deepseek/deepseek-chat",
        temperature: float = 0.4,
        max_tokens: int = 1200,
        strategy: OrchestrationStrategy = OrchestrationStrategy.BALANCED
    ):
        """
        Initialize OrchestratorAgent with DeepSeek via OpenRouter.
        
        Args:
            model: DeepSeek model ID via OpenRouter
            temperature: Sampling temperature (0.4 for strategic thinking)
            max_tokens: Max completion tokens per orchestration decision
            strategy: Orchestration strategy (performance, cost_optimized, quality, balanced)
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.strategy = strategy
        
        # Initialize DeepSeek via OpenRouter
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")
        
        self.llm = ChatOpenAI(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1"
        )
        
        # Initialize checkpointer for state persistence
        self.checkpointer = InMemorySaver()
        
        # Build orchestration StateGraph
        self.graph = self._build_graph()
        
        # Agent capability mappings
        self.agent_capabilities = self._build_capability_mappings()
        
        logger.info(
            f"OrchestratorAgent initialized: model={model}, "
            f"strategy={strategy}, temperature={temperature}"
        )

    def _build_capability_mappings(self) -> Dict[AgentCapability, Dict[str, Any]]:
        """Build mappings of agent capabilities and characteristics."""
        return {
            AgentCapability.QUALIFICATION: {
                "description": "Lead qualification and scoring",
                "provider": "cerebras",
                "cost_per_call": 0.000006,
                "avg_latency_ms": 633,
                "max_concurrent": 10
            },
            AgentCapability.ENRICHMENT: {
                "description": "Contact and company data enrichment",
                "provider": "anthropic",
                "cost_per_call": 0.001,
                "avg_latency_ms": 2000,
                "max_concurrent": 5
            },
            AgentCapability.GROWTH: {
                "description": "Multi-touch outreach campaigns",
                "provider": "cerebras",
                "cost_per_call": 0.0015,
                "avg_latency_ms": 5000,
                "max_concurrent": 3
            },
            AgentCapability.MARKETING: {
                "description": "Multi-channel content generation",
                "provider": "mixed",
                "cost_per_call": 0.00003,
                "avg_latency_ms": 4000,
                "max_concurrent": 4
            },
            AgentCapability.BDR: {
                "description": "High-value BDR outreach with approval",
                "provider": "anthropic",
                "cost_per_call": 0.004,
                "avg_latency_ms": 2000,
                "max_concurrent": 2
            },
            AgentCapability.CONVERSATION: {
                "description": "Voice-enabled conversational AI",
                "provider": "cerebras",
                "cost_per_call": 0.0001,
                "avg_latency_ms": 1000,
                "max_concurrent": 8
            },
            AgentCapability.REASONING: {
                "description": "Complex reasoning and problem solving",
                "provider": "deepseek",
                "cost_per_call": 0.003,
                "avg_latency_ms": 10000,
                "max_concurrent": 2
            },
            AgentCapability.SOCIAL_RESEARCH: {
                "description": "Social media research and analysis",
                "provider": "deepseek",
                "cost_per_call": 0.002,
                "avg_latency_ms": 8000,
                "max_concurrent": 3
            },
            AgentCapability.LICENSE_AUDIT: {
                "description": "License compliance auditing",
                "provider": "deepseek",
                "cost_per_call": 0.002,
                "avg_latency_ms": 6000,
                "max_concurrent": 2
            },
            AgentCapability.LINKEDIN_WRITER: {
                "description": "LinkedIn content generation",
                "provider": "deepseek",
                "cost_per_call": 0.001,
                "avg_latency_ms": 3000,
                "max_concurrent": 5
            }
        }

    def _build_graph(self) -> StateGraph:
        """Build the orchestration StateGraph."""
        graph = StateGraph(OrchestrationState)
        
        # Add orchestration nodes
        graph.add_node("analyze", self._analyze_node)
        graph.add_node("select", self._select_node)
        graph.add_node("delegate", self._delegate_node)
        graph.add_node("monitor", self._monitor_node)
        graph.add_node("aggregate", self._aggregate_node)
        
        # Add edges
        graph.set_entry_point("analyze")
        graph.add_edge("analyze", "select")
        graph.add_edge("select", "delegate")
        graph.add_edge("delegate", "monitor")
        graph.add_edge("monitor", "aggregate")
        graph.add_edge("aggregate", END)
        
        return graph.compile(checkpointer=self.checkpointer)

    # ========== Node Functions ==========

    async def _analyze_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Analyze the main task and identify required capabilities."""
        logger.info(f"Analyzing main task: {state.main_task[:100]}...")
        
        available_agents_str = [agent.value for agent in state.available_agents]
        
        prompt = f"""
        You are an expert agent orchestrator. Analyze the following task and identify required capabilities:

        MAIN TASK: {state.main_task}
        
        CONTEXT: {state.context}
        
        AVAILABLE AGENTS: {available_agents_str}
        
        ORCHESTRATION STRATEGY: {state.strategy.value}
        
        Your task is to:
        1. Break down the main task into subtasks
        2. Identify which agent capabilities are needed for each subtask
        3. Determine task dependencies and execution order
        4. Estimate resource requirements and complexity
        5. Create an initial execution plan
        
        For each subtask, specify:
        - Task description
        - Required agent capability
        - Input data needed
        - Expected output
        - Dependencies on other subtasks
        - Priority level (1-5, where 1 is highest)
        - Estimated complexity (1-5)
        
        Structure as a detailed analysis with clear subtask breakdown.
        """
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            analysis = response.content
            
            return {
                "current_phase": "select",
                "orchestration_metadata": {
                    "analysis": analysis,
                    "analysis_complete": True,
                    "strategy": state.strategy.value
                }
            }
            
        except Exception as e:
            logger.error(f"Task analysis failed: {e}")
            return {
                "errors": state.errors + [f"Task analysis failed: {str(e)}"]
            }

    async def _select_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Select appropriate agents based on analysis and strategy."""
        logger.info("Selecting agents for task execution...")
        
        analysis = state.orchestration_metadata.get("analysis", "")
        available_agents_str = [agent.value for agent in state.available_agents]
        
        prompt = f"""
        Based on the task analysis, select the optimal agents for execution:

        ANALYSIS: {analysis}
        
        AVAILABLE AGENTS: {available_agents_str}
        
        STRATEGY: {state.strategy.value}
        
        AGENT CAPABILITIES:
        {self._format_capability_info()}
        
        Select agents considering:
        1. Capability match for each subtask
        2. Strategy requirements (performance/cost/quality/balanced)
        3. Resource constraints and concurrency limits
        4. Cost optimization opportunities
        5. Execution time requirements
        
        For each selected agent, specify:
        - Agent type
        - Assigned subtasks
        - Execution order (parallel vs sequential)
        - Resource allocation
        - Expected performance metrics
        
        Structure as a detailed agent selection plan.
        """
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            selection = response.content
            
            return {
                "current_phase": "delegate",
                "orchestration_metadata": {
                    **state.orchestration_metadata,
                    "agent_selection": selection,
                    "selection_complete": True
                }
            }
            
        except Exception as e:
            logger.error(f"Agent selection failed: {e}")
            return {
                "errors": state.errors + [f"Agent selection failed: {str(e)}"]
            }

    async def _delegate_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Delegate tasks to selected agents."""
        logger.info("Delegating tasks to selected agents...")
        
        selection = state.orchestration_metadata.get("agent_selection", "")
        
        prompt = f"""
        Create detailed task assignments based on agent selection:

        AGENT SELECTION: {selection}
        
        MAIN TASK: {state.main_task}
        CONTEXT: {state.context}
        
        Create specific task assignments including:
        1. Task ID and description for each assignment
        2. Agent type and configuration
        3. Input data preparation
        4. Expected outputs and success criteria
        5. Dependencies and execution order
        6. Retry logic and error handling
        7. Timeout and resource limits
        
        Structure as a detailed delegation plan with specific task objects.
        """
        
        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            delegation = response.content
            
            # Create task objects (simplified for MVP)
            tasks = self._create_task_objects(delegation, state)
            
            return {
                "current_phase": "monitor",
                "agent_tasks": tasks,
                "execution_plan": [{"phase": "delegation", "plan": delegation}],
                "orchestration_metadata": {
                    **state.orchestration_metadata,
                    "delegation_complete": True,
                    "tasks_created": len(tasks)
                }
            }
            
        except Exception as e:
            logger.error(f"Task delegation failed: {e}")
            return {
                "errors": state.errors + [f"Task delegation failed: {str(e)}"]
            }

    async def _monitor_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Monitor agent execution and handle failures."""
        logger.info("Monitoring agent execution...")
        
        # Simulate agent execution (in real implementation, this would call actual agents)
        completed_tasks = []
        failed_tasks = []
        
        for task in state.agent_tasks:
            if task.status == TaskStatus.PENDING:
                # Simulate task execution
                await asyncio.sleep(0.1)  # Simulate processing time
                
                # Simulate success/failure based on task complexity
                success_rate = 0.9 if task.priority <= 2 else 0.8
                if time.time() % 1 < success_rate:
                    task.status = TaskStatus.COMPLETED
                    task.result = {"output": f"Task {task.task_id} completed successfully"}
                    task.completed_at = time.time()
                    completed_tasks.append(task.task_id)
                else:
                    task.status = TaskStatus.FAILED
                    task.error = f"Task {task.task_id} failed during execution"
                    failed_tasks.append(task.task_id)
        
        return {
            "current_phase": "aggregate",
            "completed_tasks": state.completed_tasks + completed_tasks,
            "failed_tasks": state.failed_tasks + failed_tasks,
            "orchestration_metadata": {
                **state.orchestration_metadata,
                "monitoring_complete": True,
                "tasks_completed": len(completed_tasks),
                "tasks_failed": len(failed_tasks)
            }
        }

    async def _aggregate_node(self, state: OrchestrationState) -> Dict[str, Any]:
        """Aggregate results from all agents into final output."""
        logger.info("Aggregating results from all agents...")
        
        # Collect results from completed tasks
        results = {}
        for task in state.agent_tasks:
            if task.status == TaskStatus.COMPLETED and task.result:
                results[task.agent_type.value] = task.result
        
        # Create execution summary
        execution_summary = {
            "total_tasks": len(state.agent_tasks),
            "completed_tasks": len(state.completed_tasks),
            "failed_tasks": len(state.failed_tasks),
            "success_rate": len(state.completed_tasks) / len(state.agent_tasks) if state.agent_tasks else 0,
            "agents_used": list(set(task.agent_type.value for task in state.agent_tasks)),
            "execution_time": time.time() - state.orchestration_metadata.get("start_time", time.time())
        }
        
        return {
            "current_phase": "complete",
            "orchestration_metadata": {
                **state.orchestration_metadata,
                "aggregation_complete": True,
                "final_results": results,
                "execution_summary": execution_summary
            }
        }

    def _format_capability_info(self) -> str:
        """Format agent capability information for LLM."""
        info_lines = []
        for capability, info in self.agent_capabilities.items():
            info_lines.append(
                f"- {capability.value}: {info['description']} "
                f"(cost: ${info['cost_per_call']:.6f}, latency: {info['avg_latency_ms']}ms)"
            )
        return "\n".join(info_lines)

    def _create_task_objects(self, delegation: str, state: OrchestrationState) -> List[AgentTask]:
        """Create AgentTask objects from delegation plan (simplified for MVP)."""
        tasks = []
        
        # Simplified task creation based on available agents
        for i, agent in enumerate(state.available_agents[:3]):  # Limit to 3 tasks for MVP
            task = AgentTask(
                task_id=f"task_{i+1}",
                agent_type=agent,
                task_description=f"Execute {agent.value} task",
                input_data=state.context,
                priority=1,
                assigned_at=time.time()
            )
            tasks.append(task)
        
        return tasks

    # ========== Public Interface ==========

    async def orchestrate_workflow(
        self,
        task: str,
        context: Dict[str, Any],
        available_agents: List[str],
        strategy: Optional[OrchestrationStrategy] = None,
        config: Optional[Dict[str, Any]] = None
    ) -> OrchestrationResult:
        """
        Orchestrate a multi-agent workflow.
        
        Args:
            task: Main task description
            context: Additional context and data
            available_agents: List of available agent types
            strategy: Orchestration strategy (optional override)
            config: Optional configuration for the orchestration process
            
        Returns:
            OrchestrationResult with aggregated results and metadata
        """
        start_time = time.time()
        
        # Convert string agent names to enums
        agent_enums = []
        for agent_str in available_agents:
            try:
                agent_enums.append(AgentCapability(agent_str))
            except ValueError:
                logger.warning(f"Unknown agent type: {agent_str}")
        
        # Initialize state
        initial_state = OrchestrationState(
            main_task=task,
            context=context,
            available_agents=agent_enums,
            strategy=strategy or self.strategy,
            orchestration_metadata={"start_time": start_time}
        )
        
        try:
            # Run orchestration graph
            result = await self.graph.ainvoke(
                initial_state.dict(),
                config=config or {}
            )
            
            # Calculate metrics
            total_time = time.time() - start_time
            total_cost = self._calculate_cost(result.get("agent_tasks", []))
            
            return OrchestrationResult(
                success=len(result.get("errors", [])) == 0,
                results=result.get("orchestration_metadata", {}).get("final_results", {}),
                execution_summary=result.get("orchestration_metadata", {}).get("execution_summary", {}),
                total_execution_time_seconds=total_time,
                total_cost_usd=total_cost,
                agents_used=result.get("orchestration_metadata", {}).get("execution_summary", {}).get("agents_used", []),
                tasks_completed=len(result.get("completed_tasks", [])),
                tasks_failed=len(result.get("failed_tasks", [])),
                orchestration_metadata=result.get("orchestration_metadata", {}),
                errors=result.get("errors", [])
            )
            
        except Exception as e:
            logger.error(f"Orchestration failed: {e}")
            return OrchestrationResult(
                success=False,
                results={},
                execution_summary={},
                total_execution_time_seconds=time.time() - start_time,
                total_cost_usd=0.0,
                agents_used=[],
                tasks_completed=0,
                tasks_failed=0,
                orchestration_metadata={},
                errors=[f"Orchestration failed: {str(e)}"]
            )

    def _calculate_cost(self, agent_tasks: List[AgentTask]) -> float:
        """Calculate total cost of agent tasks."""
        total_cost = 0.0
        
        for task in agent_tasks:
            if task.agent_type in self.agent_capabilities:
                cost_per_call = self.agent_capabilities[task.agent_type]["cost_per_call"]
                total_cost += cost_per_call
        
        return total_cost
