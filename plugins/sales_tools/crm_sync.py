"""CRMSyncTool - Sync leads to CRM systems.

Wraps CRM integrations (Close, HubSpot, Apollo) to sync
lead data to external CRM platforms.

Usage:
    tool = CRMSyncTool()
    result = await tool.run({
        "lead_id": "lead-abc",
        "crm": "close",
    })
"""

from plugins.sales_tools.base import BaseTool, ToolCategory, ToolDefinition, ToolResult


SUPPORTED_CRMS = ["close", "hubspot", "apollo"]


class CRMSyncTool(BaseTool):
    """Sync leads to CRM platforms.

    Supports:
    - Close CRM: Lead and contact sync
    - HubSpot: Contact and deal sync
    - Apollo: Contact enrichment sync
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="crm_sync",
            description=(
                "Sync lead data to CRM platform (Close, HubSpot, or Apollo). "
                "Creates or updates contacts/leads in the target CRM."
            ),
            category=ToolCategory.SALES,
            parameters={
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "string",
                        "description": "Lead ID to sync to CRM",
                    },
                    "crm": {
                        "type": "string",
                        "enum": SUPPORTED_CRMS,
                        "description": "Target CRM platform (close, hubspot, apollo)",
                    },
                    "force_update": {
                        "type": "boolean",
                        "description": "Force update even if already synced (default: false)",
                        "default": False,
                    },
                },
                "required": ["lead_id", "crm"],
            },
            requires_approval=False,
        )

    def _sync_to_crm(
        self,
        lead_id: str,
        crm: str,
        force_update: bool = False,
    ) -> dict:
        """Sync lead to specified CRM.

        This is a placeholder that should be replaced with actual
        CRM integration from backend/app/services/crm/.

        Args:
            lead_id: Lead to sync
            crm: Target CRM platform
            force_update: Force update existing record

        Returns:
            Sync result dictionary
        """
        # TODO: Integrate with backend/app/services/crm/
        crm_ids = {
            "close": f"lead_{lead_id[:8]}",
            "hubspot": f"hs-contact-{lead_id[:8]}",
            "apollo": f"apollo-{lead_id[:8]}",
        }

        return {
            "crm": crm,
            "crm_id": crm_ids.get(crm, f"{crm}-{lead_id[:8]}"),
            "status": "updated" if force_update else "created",
            "synced_fields": ["name", "email", "phone", "company"],
        }

    async def run(self, arguments: dict) -> ToolResult:
        """Execute CRM sync.

        Args:
            arguments: Must contain 'lead_id' and 'crm'

        Returns:
            ToolResult with sync status
        """
        lead_id = arguments.get("lead_id", "")
        crm = arguments.get("crm", "")
        force_update = arguments.get("force_update", False)

        try:
            # Validate CRM
            if crm not in SUPPORTED_CRMS:
                return ToolResult(
                    tool_name="crm_sync",
                    success=False,
                    result=None,
                    execution_time_ms=0,
                    error=f"Unsupported CRM: {crm}. Use: {', '.join(SUPPORTED_CRMS)}",
                )

            # Sync to CRM
            result = self._sync_to_crm(
                lead_id=lead_id,
                crm=crm,
                force_update=force_update,
            )

            return ToolResult(
                tool_name="crm_sync",
                success=True,
                result=result,
                execution_time_ms=0,
            )

        except Exception as e:
            return ToolResult(
                tool_name="crm_sync",
                success=False,
                result=None,
                execution_time_ms=0,
                error=f"CRM sync failed: {str(e)}",
            )
