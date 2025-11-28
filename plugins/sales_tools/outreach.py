"""OutreachTool - Send sales outreach to leads.

Wraps existing outreach services to send emails, SMS, or other
communication channels to qualified leads.

Usage:
    tool = OutreachTool()
    result = await tool.run({
        "lead_id": "lead-abc",
        "channel": "email",
        "template": "intro",  # optional
    })
"""

from plugins.sales_tools.base import BaseTool, ToolCategory, ToolDefinition, ToolResult


VALID_CHANNELS = ["email", "sms", "linkedin"]


class OutreachTool(BaseTool):
    """Send outreach messages to leads.

    Supports multiple channels:
    - email: Send personalized email using templates
    - sms: Send SMS messages
    - linkedin: Queue LinkedIn connection/message
    """

    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="outreach_send",
            description=(
                "Send sales outreach to a lead via email, SMS, or LinkedIn. "
                "Uses personalized templates based on lead data and engagement history."
            ),
            category=ToolCategory.SALES,
            parameters={
                "type": "object",
                "properties": {
                    "lead_id": {
                        "type": "string",
                        "description": "Lead ID to send outreach to",
                    },
                    "channel": {
                        "type": "string",
                        "enum": VALID_CHANNELS,
                        "description": "Communication channel (email, sms, linkedin)",
                    },
                    "template": {
                        "type": "string",
                        "description": "Template name to use (e.g., 'intro', 'followup', 'demo_request')",
                    },
                    "custom_message": {
                        "type": "string",
                        "description": "Custom message content (overrides template)",
                    },
                },
                "required": ["lead_id", "channel"],
            },
            requires_approval=True,  # Outreach needs approval
        )

    def _send_outreach(
        self,
        lead_id: str,
        channel: str,
        template: str = None,
        custom_message: str = None,
    ) -> dict:
        """Send outreach via specified channel.

        This is a placeholder that should be replaced with actual
        outreach service integration.

        Args:
            lead_id: Lead to contact
            channel: Communication channel
            template: Template name
            custom_message: Custom message content

        Returns:
            Outreach result dictionary
        """
        # TODO: Integrate with backend/app/services/outreach/
        return {
            "message_id": f"msg-{lead_id[:8]}",
            "channel": channel,
            "status": "sent" if channel == "email" else "queued",
            "template_used": template or "default",
        }

    async def run(self, arguments: dict) -> ToolResult:
        """Execute outreach send.

        Args:
            arguments: Must contain 'lead_id' and 'channel'

        Returns:
            ToolResult with outreach status
        """
        lead_id = arguments.get("lead_id", "")
        channel = arguments.get("channel", "")
        template = arguments.get("template")
        custom_message = arguments.get("custom_message")

        try:
            # Validate channel
            if channel not in VALID_CHANNELS:
                return ToolResult(
                    tool_name="outreach_send",
                    success=False,
                    result=None,
                    execution_time_ms=0,
                    error=f"Invalid channel: {channel}. Use: {', '.join(VALID_CHANNELS)}",
                )

            # Send outreach
            result = self._send_outreach(
                lead_id=lead_id,
                channel=channel,
                template=template,
                custom_message=custom_message,
            )

            return ToolResult(
                tool_name="outreach_send",
                success=True,
                result=result,
                execution_time_ms=0,
            )

        except Exception as e:
            return ToolResult(
                tool_name="outreach_send",
                success=False,
                result=None,
                execution_time_ms=0,
                error=f"Outreach failed: {str(e)}",
            )
