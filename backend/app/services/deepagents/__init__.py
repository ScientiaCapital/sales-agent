"""
Deep Agents Integration for Sales-Agent

This module provides Deep Agents integration alongside existing LangGraph agents,
enabling long-term memory, subagent coordination, and enhanced workflows.

Key Features:
- Long-term persistent memory across agent sessions
- Subagent architecture for complex multi-agent workflows
- Master Agent coordination of existing LangGraph agents

Architecture:
- BaseDeepAgent: Core Deep Agent functionality
- LongTermMemory: Persistent memory management
- SubagentCoordinator: Multi-agent coordination
- MasterDeepAgent: Orchestrates existing 6 LangGraph agents as subagents

Usage:
    ```python
    from app.services.deepagents import MasterDeepAgent
    
    master_agent = MasterDeepAgent()
    result = await master_agent.execute_workflow(
        workflow_type="lead_processing",
        input_data={"company_name": "TechCorp"}
    )
    ```
"""

from .base import BaseDeepAgent
from .memory import LongTermMemory
from .subagents import SubagentCoordinator
from .master_agent import MasterDeepAgent

__all__ = [
    "BaseDeepAgent",
    "LongTermMemory", 
    "SubagentCoordinator",
    "MasterDeepAgent"
]
