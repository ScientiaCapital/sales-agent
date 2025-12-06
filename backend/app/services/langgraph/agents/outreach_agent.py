"""
OutreachAgent - Multi-Channel GTM Outreach via Close CRM

LangGraph agent that orchestrates email, SMS, and calling outreach using
Close CRM's connected accounts (tim@coperniq.io).

Features:
- Send emails via Close CRM (tim@coperniq.io default account)
- Send SMS via Close CRM phone numbers
- Log calls after completion
- Create drafts for human review before sending
- Get full outreach history for leads
- Automatic activity logging in Close CRM

Architecture:
    ReAct Agent with Close CRM tools:
    - send_email_tool: Send email immediately
    - create_email_draft_tool: Create draft for review
    - send_sms_tool: Send SMS (TCPA-compliant)
    - log_call_tool: Log completed call
    - get_outreach_history_tool: Get all outreach history

Cost Optimization:
    - Uses DeepSeek by default ($0.27/M tokens)
    - Cost-effective for high-volume outreach coordination
    - Premium providers available for complex personalization

Safety:
    - Respects CLOSE_WRITE_DISABLED safety switch
    - All tools check write permission before executing
    - Error handling with clear messages

Usage:
    ```python
    from app.services.langgraph.agents.outreach_agent import OutreachAgent

    agent = OutreachAgent()

    # Send email to a lead
    result = await agent.process({
        "action": "send_email",
        "lead_id": "lead_xxx",
        "to_email": "john@acme.com",
        "subject": "Quick question about solar",
        "body": "Hi John..."
    })

    # Get outreach history
    result = await agent.process({
        "action": "get_history",
        "lead_id": "lead_xxx"
    })

    # Create draft for review
    result = await agent.process({
        "action": "draft_email",
        "lead_id": "lead_xxx",
        "to_email": "ceo@bigcompany.com",
        "subject": "Partnership opportunity",
        "body": "Dear CEO..."
    })
    ```

Integration:
    - BDRAgent: Delegates email sending to OutreachAgent
    - GrowthAgent: Multi-touch campaigns via OutreachAgent
    - SalesIntelAgent: Triggers follow-up via OutreachAgent
"""

import time
from typing import Dict, Any, Optional

from langchain_core.messages import HumanMessage
from langgraph.prebuilt import create_react_agent

from app.services.langgraph.agents.base_agent import (
    BaseAgent,
    AgentConfig,
    OptimizationTarget,
    ProviderType
)
from app.services.langgraph.tools.outreach_tools import OUTREACH_TOOLS
from app.services.langgraph.tools.sequence_tools import SEQUENCE_TOOLS
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Combined tools for OutreachAgent (email/SMS/call + sequence management)
ALL_OUTREACH_TOOLS = OUTREACH_TOOLS + SEQUENCE_TOOLS


class OutreachAgent(BaseAgent):
    """
    Multi-channel outreach agent using Close CRM.

    Orchestrates email, SMS, and calling outreach with automatic
    activity logging in Close CRM.
    """

    def __init__(
        self,
        provider: str = "deepseek",  # Cost-effective for outreach coordination
        model: Optional[str] = None,
        temperature: float = 0.3,  # Low temp for consistent outreach
        max_tokens: int = 2000,
        use_cache: bool = True,
        track_costs: bool = True
    ):
        """
        Initialize Outreach agent.

        Args:
            provider: LLM provider ("deepseek", "cerebras", "claude", "ollama")
            model: Model name (auto-selected based on provider if None)
            temperature: Sampling temperature (default: 0.3 for consistent results)
            max_tokens: Maximum tokens per response
            use_cache: Enable caching for repeated queries
            track_costs: Enable cost tracking via ai-cost-optimizer
        """
        # Configure agent with cost-optimization
        config = AgentConfig(
            name="outreach",
            description="Multi-channel GTM outreach agent using Close CRM",
            provider=ProviderType(provider) if provider != "auto" else ProviderType.AUTO,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            optimize_for=OptimizationTarget.COST,  # Optimize for cost
            use_cache=use_cache,
            track_costs=track_costs,
            enable_transfers=True,  # Allow agent transfers
            enable_communication_hub=True,
            grounding_strategy="strict",  # Strict adherence to outreach data
            custom_tools=ALL_OUTREACH_TOOLS  # Email/SMS/Call + Sequences
        )

        super().__init__(config)

        # Initialize ReAct agent with outreach tools
        self.react_agent = create_react_agent(
            model=self.llm,
            tools=self.get_tools(),
            state_modifier=self.get_system_prompt()
        )

        logger.info(
            f"✅ Outreach agent initialized: provider={self.provider.value}, "
            f"model={self.model}, tools={len(ALL_OUTREACH_TOOLS)} "
            f"(outreach={len(OUTREACH_TOOLS)}, sequences={len(SEQUENCE_TOOLS)})"
        )

    def get_system_prompt(self) -> str:
        """
        Get system prompt for Outreach agent.

        Returns:
            System prompt string
        """
        return """You are an Outreach Agent specializing in multi-channel B2B sales communication.

Your primary responsibilities:
1. **Send emails** via Close CRM (tim@coperniq.io account)
2. **Send SMS** for quick follow-ups (keep under 160 chars)
3. **Log calls** after phone conversations
4. **Create drafts** for high-value prospects (human review before sending)
5. **Get outreach history** to understand engagement before reaching out
6. **Manage sequences** - Enroll leads in drip campaigns, pause/resume/stop

Communication Guidelines:
- **Email**: Professional, personalized, value-focused
- **SMS**: Brief, conversational, clear call-to-action
- **Calls**: Always log outcomes (answered, voicemail, no_answer, busy, failed)

Sequence Management:
- **Enroll** cold leads in multi-step email sequences for automated nurturing
- **Pause** sequences when out-of-office replies are detected
- **Stop** sequences when leads reply (to enable human follow-up)
- **Check status** to see where contacts are in their sequence journey

Before any outreach:
1. Check outreach history to avoid over-contacting
2. Check sequence status - don't email if already in active sequence
3. Ensure appropriate channel for the situation
4. Personalize based on available context

For high-value leads (CEOs, VPs, enterprise):
- Create drafts instead of sending directly
- Allow human review before sending
- Consider direct email over sequences for personalization

Sequence Best Practices:
- Use sequences for cold outreach at scale
- Stop sequence immediately when lead replies
- Pause (don't stop) for out-of-office - will auto-resume
- Never enroll warm/hot leads in cold sequences

IMPORTANT:
- All outreach is automatically logged in Close CRM
- Respect lead preferences and do not over-contact
- SMS requires TCPA compliance (business context only)
- Email uses tim@coperniq.io as the sender
- Sequence enrollment respects CLOSE_WRITE_DISABLED safety switch

When asked to reach out, determine the best channel and execute."""

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process outreach request.

        Args:
            input_data: Dict with action and required parameters:
                - action: "send_email", "draft_email", "send_sms", "log_call", "get_history"
                - lead_id: Close CRM lead ID
                - Additional params based on action

        Returns:
            Dict with outreach results
        """
        start_time = time.time()

        try:
            # Build message from input
            action = input_data.get("action", "")
            lead_id = input_data.get("lead_id", "")

            # Construct the prompt based on action
            if action == "send_email":
                prompt = f"""Send an email with the following details:
- Lead ID: {lead_id}
- To: {input_data.get('to_email', '')}
- Subject: {input_data.get('subject', '')}
- Body: {input_data.get('body', '')}

Use the send_email_tool to send this email via Close CRM."""

            elif action == "draft_email":
                prompt = f"""Create an email draft for review:
- Lead ID: {lead_id}
- To: {input_data.get('to_email', '')}
- Subject: {input_data.get('subject', '')}
- Body: {input_data.get('body', '')}

Use the create_email_draft_tool to create this draft in Close CRM."""

            elif action == "send_sms":
                prompt = f"""Send an SMS message:
- Lead ID: {lead_id}
- Phone: {input_data.get('phone', '')}
- Message: {input_data.get('message', '')}

Use the send_sms_tool to send this SMS via Close CRM."""

            elif action == "log_call":
                prompt = f"""Log a completed call:
- Lead ID: {lead_id}
- Phone: {input_data.get('phone', '')}
- Duration: {input_data.get('duration_seconds', 0)} seconds
- Outcome: {input_data.get('disposition', 'answered')}
- Notes: {input_data.get('notes', '')}

Use the log_call_tool to log this call in Close CRM."""

            elif action == "get_history":
                prompt = f"""Get the outreach history for lead {lead_id}.

Use the get_outreach_history_tool to retrieve all email, SMS, and call activities."""

            else:
                # Generic outreach request - let agent decide
                prompt = f"""Handle this outreach request:
Lead ID: {lead_id}
Details: {input_data}

Determine the appropriate action and execute using the available tools."""

            # Invoke ReAct agent
            messages = [HumanMessage(content=prompt)]
            result = await self.react_agent.ainvoke({"messages": messages})

            latency_ms = int((time.time() - start_time) * 1000)

            # Extract final response
            final_message = result["messages"][-1].content if result.get("messages") else ""

            logger.info(
                f"Outreach agent processed {action} for lead {lead_id} "
                f"in {latency_ms}ms"
            )

            return {
                "success": True,
                "action": action,
                "lead_id": lead_id,
                "result": final_message,
                "latency_ms": latency_ms,
                "provider": self.provider.value,
                "model": self.model
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Outreach agent error: {e}")

            return {
                "success": False,
                "action": input_data.get("action", "unknown"),
                "lead_id": input_data.get("lead_id", ""),
                "error": str(e),
                "latency_ms": latency_ms
            }

    async def send_email(
        self,
        lead_id: str,
        to_email: str,
        subject: str,
        body: str,
        as_draft: bool = False
    ) -> Dict[str, Any]:
        """
        Convenience method to send email or create draft.

        Args:
            lead_id: Close CRM lead ID
            to_email: Recipient email
            subject: Email subject
            body: Email body (plain text)
            as_draft: If True, create draft instead of sending

        Returns:
            Dict with result
        """
        return await self.process({
            "action": "draft_email" if as_draft else "send_email",
            "lead_id": lead_id,
            "to_email": to_email,
            "subject": subject,
            "body": body
        })

    async def send_sms(
        self,
        lead_id: str,
        phone: str,
        message: str
    ) -> Dict[str, Any]:
        """
        Convenience method to send SMS.

        Args:
            lead_id: Close CRM lead ID
            phone: Recipient phone number
            message: SMS message (keep under 160 chars)

        Returns:
            Dict with result
        """
        return await self.process({
            "action": "send_sms",
            "lead_id": lead_id,
            "phone": phone,
            "message": message
        })

    async def log_call(
        self,
        lead_id: str,
        phone: str,
        duration_seconds: int,
        disposition: str = "answered",
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Convenience method to log a call.

        Args:
            lead_id: Close CRM lead ID
            phone: Phone number called
            duration_seconds: Call duration
            disposition: Call outcome (answered, voicemail, no_answer, busy, failed)
            notes: Call notes

        Returns:
            Dict with result
        """
        return await self.process({
            "action": "log_call",
            "lead_id": lead_id,
            "phone": phone,
            "duration_seconds": duration_seconds,
            "disposition": disposition,
            "notes": notes
        })

    async def get_history(self, lead_id: str) -> Dict[str, Any]:
        """
        Convenience method to get outreach history.

        Args:
            lead_id: Close CRM lead ID

        Returns:
            Dict with outreach history
        """
        return await self.process({
            "action": "get_history",
            "lead_id": lead_id
        })
