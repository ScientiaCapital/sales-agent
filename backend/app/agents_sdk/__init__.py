"""
Claude Agent SDK Integration Layer

Conversational agents built with Claude Agent SDK that provide
natural language interfaces over existing LangGraph automation.

Architecture:
    - Conversational Layer: Claude Agent SDK (session management, NL)
    - Automation Layer: LangGraph Agents (qualification, enrichment, etc.)
    - Integration Layer: MCP Tools (bridge between SDK and LangGraph)

Agents:
    - SR/BDR Agent: Sales rep conversational assistant
    - Pipeline Manager: Interactive license import orchestration
    - Customer Success: Onboarding and support assistant
"""

__version__ = "0.1.0"

__all__ = [
    "SRBDRAgent",
    "PipelineManagerAgent",
    "CustomerSuccessAgent",
]
