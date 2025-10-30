"""
Master Deep Agent - Subagent Coordination System

This Master Deep Agent orchestrates your existing 6 LangGraph agents as subagents:
1. QualificationAgent - Lead scoring
2. EnrichmentAgent - Multi-source enrichment  
3. SocialResearchAgent - Social media research
4. GrowthAgent - Market analysis
5. MarketingAgent - Campaign generation
6. BDRAgent - Meeting booking
7. ConversationAgent - Voice-enabled AI

The Master Agent provides:
- Intelligent task routing based on input type
- Parallel execution of independent tasks
- Sequential workflows with dependencies
- Result synthesis and aggregation
- Long-term memory across all subagents
- Enhanced human-in-the-loop coordination
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Union, Literal
from datetime import datetime
from dataclasses import dataclass, field

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_core.tools import BaseTool

from .base import BaseDeepAgent, DeepAgentConfig, DeepAgentState
from .subagents import SubagentCoordinator, SubagentTask, SubagentResult, SubagentStatus
from .memory import LongTermMemory
# Human-in-the-loop functionality will be implemented later

# Import your existing agents
from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
from app.services.langgraph.agents.social_research_agent import SocialResearchAgent
from app.services.langgraph.agents.growth_agent import GrowthAgent
from app.services.langgraph.agents.marketing_agent import MarketingAgent
from app.services.langgraph.agents.bdr_agent import BDRAgent
from app.services.langgraph.agents.conversation_agent import ConversationAgent

from app.core.logging import setup_logging
from app.core.exceptions import ValidationError

logger = setup_logging(__name__)


@dataclass
class MasterAgentWorkflow:
    """Workflow definition for Master Agent execution."""
    workflow_id: str
    workflow_type: Literal["lead_processing", "research_analysis", "campaign_generation", "conversation", "custom"]
    tasks: List[SubagentTask]
    execution_mode: Literal["parallel", "sequential", "conditional"] = "parallel"
    human_checkpoints: List[str] = field(default_factory=list)
    expected_duration_ms: int = 5000


class MasterDeepAgent(BaseDeepAgent):
    """
    Master Deep Agent that coordinates all existing LangGraph agents as subagents.
    
    This agent acts as the central orchestrator for your sales automation platform,
    intelligently routing tasks to the appropriate subagents and synthesizing results.
    
    Workflow Types:
    - lead_processing: Qualification → Enrichment → Social Research
    - research_analysis: Social Research → Growth Analysis → Insights
    - campaign_generation: Growth Analysis → Marketing → BDR
    - conversation: Voice-enabled interaction with Conversation Agent
    - custom: User-defined workflow
    """
    
    def __init__(
        self,
        config: Optional[DeepAgentConfig] = None,
        llm: Optional[BaseLanguageModel] = None,
        tools: Optional[List[BaseTool]] = None
    ):
        """
        Initialize Master Deep Agent with subagent coordination.
        
        Args:
            config: Deep Agent configuration
            llm: Language model for master agent reasoning
            tools: Additional tools for master agent
        """
        # Default config for Master Agent
        if not config:
            config = DeepAgentConfig(
                agent_id="master_deep_agent",
                agent_type="master_coordinator",
                memory_enabled=True,
                subagents_enabled=True,
                human_in_loop_enabled=True,
                max_iterations=100,
                timeout_seconds=600
            )
        
        super().__init__(config, llm, tools)
        
        # Initialize subagent coordinator
        self.subagent_coordinator = SubagentCoordinator(
            max_subagents=6,  # All 6 existing agents
            default_timeout=300,
            max_retries=2
        )
        
        # Register all existing agents as subagents
        self._register_subagents()
        
        # Workflow definitions
        self.workflows = self._define_workflows()
        
        logger.info("MasterDeepAgent initialized with 6 subagents")
    
    def _register_subagents(self) -> None:
        """Register all existing LangGraph agents as subagents."""
        subagents = {
            "qualification": QualificationAgent,
            "enrichment": EnrichmentAgent,
            "social_research": SocialResearchAgent,
            "growth": GrowthAgent,
            "marketing": MarketingAgent,
            "bdr": BDRAgent,
            "conversation": ConversationAgent
        }
        
        for agent_type, agent_class in subagents.items():
            self.subagent_coordinator.register_subagent(agent_type, agent_class)
        
        logger.info(f"Registered {len(subagents)} subagents")
    
    def _define_workflows(self) -> Dict[str, MasterAgentWorkflow]:
        """Define common workflows for the Master Agent."""
        return {
            "lead_processing": MasterAgentWorkflow(
                workflow_id="lead_processing",
                workflow_type="lead_processing",
                tasks=[
                    SubagentTask(
                        task_id="qualify_lead",
                        agent_type="qualification",
                        input_data={},
                        priority=1,
                        expected_output_keys=["score", "confidence", "reasoning"]
                    ),
                    SubagentTask(
                        task_id="enrich_lead",
                        agent_type="enrichment",
                        input_data={},
                        priority=2,
                        dependencies=["qualify_lead"],
                        expected_output_keys=["enriched_data", "data_sources"]
                    ),
                    SubagentTask(
                        task_id="research_social",
                        agent_type="social_research",
                        input_data={},
                        priority=3,
                        dependencies=["enrich_lead"],
                        expected_output_keys=["total_mentions", "sentiment", "insights"]
                    )
                ],
                execution_mode="sequential",
                human_checkpoints=["qualify_lead"],
                expected_duration_ms=8000
            ),
            
            "research_analysis": MasterAgentWorkflow(
                workflow_id="research_analysis",
                workflow_type="research_analysis",
                tasks=[
                    SubagentTask(
                        task_id="social_research",
                        agent_type="social_research",
                        input_data={},
                        priority=1,
                        expected_output_keys=["total_mentions", "platforms", "insights"]
                    ),
                    SubagentTask(
                        task_id="growth_analysis",
                        agent_type="growth",
                        input_data={},
                        priority=2,
                        dependencies=["social_research"],
                        expected_output_keys=["opportunities", "market_analysis"]
                    )
                ],
                execution_mode="sequential",
                expected_duration_ms=6000
            ),
            
            "campaign_generation": MasterAgentWorkflow(
                workflow_id="campaign_generation",
                workflow_type="campaign_generation",
                tasks=[
                    SubagentTask(
                        task_id="growth_analysis",
                        agent_type="growth",
                        input_data={},
                        priority=1,
                        expected_output_keys=["opportunities", "market_analysis"]
                    ),
                    SubagentTask(
                        task_id="marketing_campaign",
                        agent_type="marketing",
                        input_data={},
                        priority=2,
                        dependencies=["growth_analysis"],
                        expected_output_keys=["campaigns", "recommendations"]
                    ),
                    SubagentTask(
                        task_id="bdr_outreach",
                        agent_type="bdr",
                        input_data={},
                        priority=3,
                        dependencies=["marketing_campaign"],
                        expected_output_keys=["meeting_requests", "outreach_plan"]
                    )
                ],
                execution_mode="sequential",
                human_checkpoints=["bdr_outreach"],
                expected_duration_ms=10000
            ),
            
            "conversation": MasterAgentWorkflow(
                workflow_id="conversation",
                workflow_type="conversation",
                tasks=[
                    SubagentTask(
                        task_id="voice_conversation",
                        agent_type="conversation",
                        input_data={},
                        priority=1,
                        expected_output_keys=["response", "intent", "next_action"]
                    )
                ],
                execution_mode="sequential",
                expected_duration_ms=2000
            )
        }
    
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute Master Agent workflow based on input type.
        
        Args:
            input_data: Input data containing workflow type and parameters
            
        Returns:
            Master Agent execution results
        """
        start_time = time.time()
        
        try:
            # Determine workflow type
            workflow_type = input_data.get("workflow_type", "lead_processing")
            workflow = self.workflows.get(workflow_type)
            
            if not workflow:
                raise ValidationError(f"Unknown workflow type: {workflow_type}")
            
            logger.info(f"Executing workflow: {workflow_type}")
            
            # Prepare tasks with input data
            prepared_tasks = self._prepare_tasks(workflow, input_data)
            
            # Execute tasks based on workflow mode
            if workflow.execution_mode == "parallel":
                results = await self.subagent_coordinator.execute_parallel(prepared_tasks)
            elif workflow.execution_mode == "sequential":
                results = await self.subagent_coordinator.execute_sequential(prepared_tasks)
            else:  # conditional
                results = await self.subagent_coordinator.execute_with_dependencies(prepared_tasks)
            
            # Synthesize results
            synthesized_results = await self._synthesize_results(results, workflow)
            
            # Calculate execution metrics
            execution_time_ms = int((time.time() - start_time) * 1000)
            total_cost = sum(result.cost_usd for result in results)
            
            # Build final result
            final_result = {
                "workflow_type": workflow_type,
                "workflow_id": workflow.workflow_id,
                "status": "completed",
                "results": synthesized_results,
                "subagent_results": results,
                "execution_metrics": {
                    "execution_time_ms": execution_time_ms,
                    "expected_duration_ms": workflow.expected_duration_ms,
                    "total_cost_usd": total_cost,
                    "tasks_completed": len([r for r in results if r.status == SubagentStatus.COMPLETED]),
                    "tasks_failed": len([r for r in results if r.status == SubagentStatus.FAILED])
                },
                "timestamp": datetime.now().isoformat()
            }
            
            logger.info(f"Workflow completed: {workflow_type} in {execution_time_ms}ms")
            return final_result
            
        except Exception as e:
            execution_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Master Agent execution failed: {str(e)}", exc_info=True)
            
            return {
                "workflow_type": input_data.get("workflow_type", "unknown"),
                "status": "failed",
                "error": str(e),
                "execution_time_ms": execution_time_ms,
                "timestamp": datetime.now().isoformat()
            }
    
    def _prepare_tasks(
        self,
        workflow: MasterAgentWorkflow,
        input_data: Dict[str, Any]
    ) -> List[SubagentTask]:
        """Prepare tasks with input data for execution."""
        prepared_tasks = []
        
        for task in workflow.tasks:
            # Enhance input data with context
            enhanced_input = {
                **input_data,
                "task_id": task.task_id,
                "agent_type": task.agent_type,
                "priority": task.priority
            }
            
            # Create new task with enhanced input
            prepared_task = SubagentTask(
                task_id=task.task_id,
                agent_type=task.agent_type,
                input_data=enhanced_input,
                priority=task.priority,
                timeout_seconds=task.timeout_seconds,
                retry_attempts=task.retry_attempts,
                dependencies=task.dependencies,
                expected_output_keys=task.expected_output_keys
            )
            
            prepared_tasks.append(prepared_task)
        
        return prepared_tasks
    
    async def _synthesize_results(
        self,
        results: List[SubagentResult],
        workflow: MasterAgentWorkflow
    ) -> Dict[str, Any]:
        """Synthesize results from multiple subagents."""
        synthesized = {
            "workflow_summary": {
                "total_tasks": len(results),
                "completed_tasks": len([r for r in results if r.status == SubagentStatus.COMPLETED]),
                "failed_tasks": len([r for r in results if r.status == SubagentStatus.FAILED]),
                "success_rate": len([r for r in results if r.status == SubagentStatus.COMPLETED]) / len(results) if results else 0
            },
            "agent_outputs": {},
            "insights": [],
            "recommendations": [],
            "next_steps": []
        }
        
        # Aggregate outputs by agent type
        for result in results:
            if result.status == SubagentStatus.COMPLETED:
                synthesized["agent_outputs"][result.agent_type] = result.output_data
                
                # Extract insights and recommendations
                if "insights" in result.output_data:
                    synthesized["insights"].extend(result.output_data["insights"])
                if "recommendations" in result.output_data:
                    synthesized["recommendations"].extend(result.output_data["recommendations"])
        
        # Generate workflow-specific synthesis
        if workflow.workflow_type == "lead_processing":
            synthesized.update(await self._synthesize_lead_processing(results))
        elif workflow.workflow_type == "research_analysis":
            synthesized.update(await self._synthesize_research_analysis(results))
        elif workflow.workflow_type == "campaign_generation":
            synthesized.update(await self._synthesize_campaign_generation(results))
        elif workflow.workflow_type == "conversation":
            synthesized.update(await self._synthesize_conversation(results))
        
        return synthesized
    
    async def _synthesize_lead_processing(self, results: List[SubagentResult]) -> Dict[str, Any]:
        """Synthesize results from lead processing workflow."""
        qualification_result = next((r for r in results if r.agent_type == "qualification"), None)
        enrichment_result = next((r for r in results if r.agent_type == "enrichment"), None)
        social_result = next((r for r in results if r.agent_type == "social_research"), None)
        
        synthesis = {
            "lead_summary": {
                "qualification_score": qualification_result.output_data.get("score", 0) if qualification_result else 0,
                "enrichment_confidence": enrichment_result.output_data.get("confidence_score", 0) if enrichment_result else 0,
                "social_mentions": social_result.output_data.get("total_mentions", 0) if social_result else 0
            },
            "data_quality": "high" if all(r.status == SubagentStatus.COMPLETED for r in results) else "partial",
            "recommended_action": "proceed" if qualification_result and qualification_result.output_data.get("score", 0) > 70 else "review"
        }
        
        return synthesis
    
    async def _synthesize_research_analysis(self, results: List[SubagentResult]) -> Dict[str, Any]:
        """Synthesize results from research analysis workflow."""
        social_result = next((r for r in results if r.agent_type == "social_research"), None)
        growth_result = next((r for r in results if r.agent_type == "growth"), None)
        
        synthesis = {
            "research_summary": {
                "social_presence": social_result.output_data.get("total_mentions", 0) if social_result else 0,
                "market_opportunities": len(growth_result.output_data.get("opportunities", [])) if growth_result else 0
            },
            "confidence_level": "high" if all(r.status == SubagentStatus.COMPLETED for r in results) else "medium"
        }
        
        return synthesis
    
    async def _synthesize_campaign_generation(self, results: List[SubagentResult]) -> Dict[str, Any]:
        """Synthesize results from campaign generation workflow."""
        growth_result = next((r for r in results if r.agent_type == "growth"), None)
        marketing_result = next((r for r in results if r.agent_type == "marketing"), None)
        bdr_result = next((r for r in results if r.agent_type == "bdr"), None)
        
        synthesis = {
            "campaign_summary": {
                "opportunities_identified": len(growth_result.output_data.get("opportunities", [])) if growth_result else 0,
                "campaigns_generated": len(marketing_result.output_data.get("campaigns", [])) if marketing_result else 0,
                "meeting_requests": len(bdr_result.output_data.get("meeting_requests", [])) if bdr_result else 0
            },
            "readiness": "ready" if all(r.status == SubagentStatus.COMPLETED for r in results) else "needs_review"
        }
        
        return synthesis
    
    async def _synthesize_conversation(self, results: List[SubagentResult]) -> Dict[str, Any]:
        """Synthesize results from conversation workflow."""
        conversation_result = next((r for r in results if r.agent_type == "conversation"), None)
        
        synthesis = {
            "conversation_summary": {
                "intent_identified": conversation_result.output_data.get("intent", "unknown") if conversation_result else "unknown",
                "response_generated": bool(conversation_result.output_data.get("response")) if conversation_result else False
            },
            "next_action": conversation_result.output_data.get("next_action", "continue") if conversation_result else "end"
        }
        
        return synthesis
    
    async def execute_workflow(
        self,
        workflow_type: str,
        input_data: Dict[str, Any],
        session_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Execute a specific workflow with memory context.
        
        Args:
            workflow_type: Type of workflow to execute
            input_data: Input data for the workflow
            session_id: Session ID for memory persistence
            
        Returns:
            Workflow execution results
        """
        # Add workflow type to input data
        enhanced_input = {
            **input_data,
            "workflow_type": workflow_type
        }
        
        # Execute with memory if available
        if self.memory and session_id:
            return await self.execute_with_memory(enhanced_input, session_id)
        else:
            return await self.execute(enhanced_input)
    
    async def get_workflow_status(self, workflow_id: str) -> Dict[str, Any]:
        """Get status of a specific workflow execution."""
        # Basic workflow status - can be enhanced with Redis tracking later
        return {
            "workflow_id": workflow_id,
            "status": "completed",
            "timestamp": datetime.now().isoformat()
        }
    
    def get_available_workflows(self) -> List[Dict[str, Any]]:
        """Get list of available workflows."""
        return [
            {
                "workflow_id": workflow.workflow_id,
                "workflow_type": workflow.workflow_type,
                "execution_mode": workflow.execution_mode,
                "expected_duration_ms": workflow.expected_duration_ms,
                "human_checkpoints": workflow.human_checkpoints
            }
            for workflow in self.workflows.values()
        ]
    
    def get_subagent_status(self) -> Dict[str, Any]:
        """Get status of all subagents."""
        return self.subagent_coordinator.get_execution_stats()
