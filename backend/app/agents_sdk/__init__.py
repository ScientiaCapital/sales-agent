"""
Claude Agent SDK Integration Layer

This package contains conversational agents built with Claude Agent SDK
that provide natural language interfaces over our existing LangGraph automation.

Architecture:
    - Conversational Layer: Claude Agent SDK (session management, NL interface)
    - Automation Layer: LangGraph Agents (qualification, enrichment, growth, etc.)
    - Integration Layer: MCP Tools (bridge between SDK and LangGraph)

Planned Agents (to be implemented):
    - SR/BDR Agent (sr_bdr.py): Sales rep conversational assistant
    - Pipeline Manager (pipeline_manager.py): Interactive license import orchestration
    - Customer Success Agent (cs_agent.py): Onboarding and support assistant

Note: Agent classes are not yet implemented. This module will be populated
as the Claude Agent SDK integration is developed.

Future Usage (once implemented):
    ```python
    from app.agents_sdk.sr_bdr import SRBDRAgent
    
    agent = SRBDRAgent()
    async for message in agent.chat(user_id="rep_123", message="What are my top leads?"):
        print(message)
    ```
"""

__version__ = "0.1.0"

# No exports yet - agent classes are planned but not yet implemented
__all__ = []
