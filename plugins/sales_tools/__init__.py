"""Sales tools plugin for conductor-ai.

Exposes sales-agent capabilities as conductor-ai tools:
- OutreachTool: Send email/SMS/LinkedIn outreach to leads
- QualifyTool: Score and qualify leads for sales
- CRMSyncTool: Sync leads to Close, HubSpot, Apollo

Usage:
    from plugins.sales_tools import register

    # Register with conductor-ai
    register(global_registry)
"""

from plugins.sales_tools.outreach import OutreachTool
from plugins.sales_tools.qualify import QualifyTool
from plugins.sales_tools.crm_sync import CRMSyncTool


def register(global_registry) -> None:
    """Register all sales tools with conductor-ai registry.

    Args:
        global_registry: The conductor-ai ToolRegistry instance
    """
    global_registry.register(OutreachTool())
    global_registry.register(QualifyTool())
    global_registry.register(CRMSyncTool())


__all__ = [
    "OutreachTool",
    "QualifyTool",
    "CRMSyncTool",
    "register",
]
