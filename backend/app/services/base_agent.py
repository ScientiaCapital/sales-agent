"""
Base Agent abstract class for all sales automation agents

Provides common interface and utilities for:
- EnrichmentAgent
- GrowthHackerAgent
- TargetedMarketingAgent
- BDRBookingAgent
- WorkflowAgent
- AEHandoffAgent
"""
from abc import ABC, abstractmethod
from typing import Dict, AsyncIterator, Any
from enum import Enum
import time

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class AgentType(str, Enum):
    """Agent types for routing and tracking"""
    ENRICHMENT = "enrichment"
    GROWTH = "growth"
    MARKETING = "marketing"
    BDR = "bdr"
    WORKFLOW = "workflow"
    HANDOFF = "handoff"


class AgentStatus(str, Enum):
    """Agent execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class BaseAgent(ABC):
    """
    Abstract base class for all sales agents
    
    Provides:
    - Standard execute() method for batch processing
    - stream_execute() method for real-time streaming
    - Error handling and logging
    - Cost and latency tracking
    """
    
    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type
        self.logger = setup_logging(f"agent.{agent_type.value}")
    
    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent logic (batch mode)
        
        Args:
            input_data: Agent-specific input parameters
            
        Returns:
            Dict with agent results and metadata
            
        Raises:
            ValueError: Invalid input data
            HTTPException: Critical failures that should propagate to API
        """
        pass
    
    @abstractmethod
    async def stream_execute(self, input_data: Dict[str, Any]) -> AsyncIterator[Dict[str, Any]]:
        """
        Execute agent logic with streaming (real-time mode)
        
        Args:
            input_data: Agent-specific input parameters
            
        Yields:
            Dict with type ("chunk"|"complete"|"error"), content, and metadata
        """
        pass
    
    @abstractmethod
    def validate_input(self, input_data: Dict[str, Any]) -> bool:
        """
        Validate input data before execution
        
        Args:
            input_data: Input to validate
            
        Returns:
            True if valid
            
        Raises:
            ValueError: If input is invalid with detailed error message
        """
        pass
    
    async def _track_execution(
        self,
        lead_id: int,
        workflow_id: str,
        func,
        *args,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Wrap execution with tracking and error handling
        
        Args:
            lead_id: Lead being processed
            workflow_id: Workflow UUID
            func: Async function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Dict with results and execution metadata
        """
        from app.models import AgentExecution, get_db
        from datetime import datetime
        
        execution = AgentExecution(
            agent_type=self.agent_type.value,
            lead_id=lead_id,
            workflow_id=workflow_id,
            status=AgentStatus.RUNNING,
            started_at=datetime.now()
        )
        
        start_time = time.time()
        
        try:
            # Execute function
            result = await func(*args, **kwargs)
            
            # Calculate metrics
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Update execution record
            execution.status = AgentStatus.SUCCESS
            execution.completed_at = datetime.now()
            execution.latency_ms = latency_ms
            execution.output_data = result
            
            # Extract cost if available
            if "metadata" in result and "total_cost_usd" in result["metadata"]:
                execution.cost_usd = result["metadata"]["total_cost_usd"]
                execution.prompt_tokens = result["metadata"].get("input_tokens", 0)
                execution.completion_tokens = result["metadata"].get("output_tokens", 0)
            
            # Save to database
            db = next(get_db())
            db.add(execution)
            db.commit()
            
            self.logger.info(
                f"{self.agent_type.value} execution complete: "
                f"lead_id={lead_id}, latency={latency_ms}ms"
            )
            
            return result
            
        except Exception as e:
            # Calculate failed execution time
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Update execution record
            execution.status = AgentStatus.FAILED
            execution.completed_at = datetime.now()
            execution.latency_ms = latency_ms
            execution.error_message = str(e)
            
            # Save error to database
            db = next(get_db())
            db.add(execution)
            db.commit()
            
            self.logger.error(
                f"{self.agent_type.value} execution failed: "
                f"lead_id={lead_id}, error={str(e)}",
                exc_info=True
            )
            
            raise
    
    def _build_prompt(self, template: str, **kwargs) -> str:
        """
        Build prompt from template with safe substitution
        
        Args:
            template: Prompt template with {placeholders}
            **kwargs: Values to substitute
            
        Returns:
            Formatted prompt string
        """
        try:
            return template.format(**kwargs)
        except KeyError as e:
            self.logger.error(f"Missing template variable: {e}")
            raise ValueError(f"Prompt template missing variable: {e}")
    
    def _extract_json_from_response(self, text: str) -> Dict[str, Any]:
        """
        Extract JSON from model response (handles markdown code blocks)
        
        Args:
            text: Response text that may contain JSON
            
        Returns:
            Parsed JSON dict
            
        Raises:
            ValueError: If JSON cannot be extracted or parsed
        """
        import json
        import re
        
        # Try direct JSON parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract from markdown code block
        json_pattern = r'```(?:json)?\s*(\{.*?\})\s*```'
        match = re.search(json_pattern, text, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in code block: {e}")
        
        # Try to find JSON object anywhere in text
        json_pattern = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
        match = re.search(json_pattern, text, re.DOTALL)
        
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        
        raise ValueError(f"No valid JSON found in response: {text[:200]}...")
    
    async def _call_with_retry(
        self,
        func,
        max_retries: int = 3,
        *args,
        **kwargs
    ) -> Any:
        """
        Call function with exponential backoff retry
        
        Args:
            func: Async function to call
            max_retries: Maximum retry attempts
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            Last exception if all retries fail
        """
        import asyncio
        
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s
                    delay = 2 ** attempt
                    self.logger.warning(
                        f"Retry {attempt + 1}/{max_retries} after {delay}s: {str(e)}"
                    )
                    await asyncio.sleep(delay)
                    
        raise last_exception
