"""
Close CRM Agent - LangGraph Agent for Close CRM Integration

Manages lead/contact operations in Close CRM with built-in deduplication.
Automatically prevents duplicate/triplicate leads while maintaining CRM hygiene.

Features:
- Multi-field deduplication (email, domain, LinkedIn, company, phone)
- Smart data merging for duplicates
- Search and enrichment workflows
- Cost tracking via ai-cost-optimizer
- Redis caching for duplicate checks (24-hour TTL)

Usage:
    ```python
    from app.services.langgraph.agents.close_crm_agent import CloseCRMAgent

    agent = CloseCRMAgent()

    # Add lead with automatic deduplication
    result = await agent.process({
        "action": "create_lead",
        "company_name": "Acme Corp",
        "contact_email": "john@acme.com",
        "contact_name": "John Doe"
    })

    # Search for leads
    result = await agent.process({
        "action": "search",
        "query": "Acme Corp"
    })
    ```

Integration:
- Connects to Close CRM via CloseProvider
- Uses deduplication engine for duplicate prevention
- Tracks costs with ai-cost-optimizer
- Caches duplicate checks in Redis (reduces API calls)
"""

import os
import time
import logging
from typing import Dict, Any, List, Optional

from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import create_react_agent

from app.services.langgraph.agents.base_agent import (
    BaseAgent,
    AgentConfig,
    OptimizationTarget,
    ProviderType
)
from app.services.langgraph.tools.crm_tools import (
    create_lead_tool,
    update_contact_tool,
    search_leads_tool,
    get_lead_tool,
    check_duplicate_leads_tool
)
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class CloseCRMAgent(BaseAgent):
    """
    Close CRM agent with automatic deduplication and lead management.

    Handles:
    - Lead creation with mandatory deduplication checks
    - Lead search and retrieval
    - Contact updates
    - Duplicate detection and prevention
    - Cost tracking for all CRM operations
    """

    def __init__(
        self,
        provider: str = "deepseek",  # Cost-effective for CRM ops
        model: Optional[str] = None,
        temperature: float = 0.2,  # Low temp for consistent CRM operations
        max_tokens: int = 2000,
        use_cache: bool = True,
        track_costs: bool = True
    ):
        """
        Initialize Close CRM agent.

        Args:
            provider: LLM provider ("deepseek", "cerebras", "claude", "ollama")
            model: Model name (auto-selected based on provider if None)
            temperature: Sampling temperature (default: 0.2 for consistent results)
            max_tokens: Maximum tokens per response
            use_cache: Enable caching for duplicate checks (24-hour TTL)
            track_costs: Enable cost tracking via ai-cost-optimizer
        """
        # Configure agent with cost-optimization
        config = AgentConfig(
            name="close_crm",
            description="Close CRM agent for lead management with deduplication",
            provider=ProviderType(provider) if provider != "auto" else ProviderType.AUTO,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            optimize_for=OptimizationTarget.COST,  # Optimize for cost
            use_cache=use_cache,
            track_costs=track_costs,
            enable_transfers=True,  # Allow agent transfers
            enable_communication_hub=True,
            grounding_strategy="strict",  # Strict adherence to CRM data
            custom_tools=[
                create_lead_tool,
                update_contact_tool,
                search_leads_tool,
                get_lead_tool,
                check_duplicate_leads_tool
            ]
        )

        super().__init__(config)

        # Initialize ReAct agent with tools
        self.react_agent = create_react_agent(
            model=self.llm,
            tools=self.get_tools(),
            state_modifier=self.get_system_prompt()
        )

        logger.info(
            f"✅ Close CRM agent initialized: provider={self.provider.value}, "
            f"model={self.model}, deduplication=enabled"
        )

    def get_system_prompt(self) -> str:
        """
        Get system prompt for Close CRM agent.

        Returns:
            System prompt string
        """
        return f"""You are a Close CRM management agent with automatic deduplication.

Your primary responsibilities:
1. **PREVENT DUPLICATES**: Always check for duplicates before creating leads (use check_duplicate_leads_tool)
2. **Create leads**: Add new prospects to Close CRM after deduplication check
3. **Search leads**: Find existing leads by company name, email, or other criteria
4. **Update contacts**: Modify existing contact information
5. **Maintain CRM hygiene**: Keep data clean, complete, and duplicate-free

**CRITICAL DEDUPLICATION RULES**:
- ALWAYS check for duplicates before creating a new lead
- If duplicate found (confidence >= 85%), DO NOT create - suggest updating existing contact instead
- Duplicate matching uses: email (exact), domain (@company.com), LinkedIn URL, company name (fuzzy), phone
- When in doubt, check duplicates first to save time and maintain data quality

**Best Practices**:
- Ask clarifying questions if lead information is incomplete
- Use search_leads_tool to verify lead doesn't exist before creating
- When updating, provide specific fields to change (don't overwrite everything)
- Log duplicate prevention actions for audit trail

**Tools Available**:
- check_duplicate_leads_tool: Check if lead already exists (use FIRST before creating)
- create_lead_tool: Create new lead (has built-in deduplication)
- search_leads_tool: Search for existing leads
- update_contact_tool: Update existing contact details
- get_lead_tool: Get full lead information by ID

**Current Context**:
- CRM Platform: Close CRM
- Provider: {self.provider.value}
- Model: {self.model}
- Deduplication Threshold: 85% confidence
- Cost Tracking: {'Enabled' if self.config.track_costs else 'Disabled'}

{self._get_grounding_instructions()}

Remember: Duplicate prevention is MANDATORY. Every lead must be checked before creation.
"""

    def get_tools(self) -> List:
        """
        Get agent-specific tools.

        Returns:
            List of LangChain tools
        """
        return [
            create_lead_tool,
            update_contact_tool,
            search_leads_tool,
            get_lead_tool,
            check_duplicate_leads_tool
        ]

    async def process(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process Close CRM agent request.

        Args:
            input_data: Request data with action and parameters
                - action: "create_lead", "search", "update", "get", "check_duplicates"
                - Additional fields based on action

        Returns:
            Result dictionary with agent response
        """
        start_time = time.time()

        try:
            action = input_data.get("action", "search")

            # Build prompt based on action
            if action == "create_lead":
                prompt = self._build_create_lead_prompt(input_data)
            elif action == "search":
                prompt = self._build_search_prompt(input_data)
            elif action == "update":
                prompt = self._build_update_prompt(input_data)
            elif action == "get":
                prompt = self._build_get_prompt(input_data)
            elif action == "check_duplicates":
                prompt = self._build_check_duplicates_prompt(input_data)
            else:
                prompt = input_data.get("prompt", str(input_data))

            # Execute via ReAct agent
            logger.info(f"Close CRM agent processing action: {action}")

            result = await self.react_agent.ainvoke({
                "messages": [HumanMessage(content=prompt)]
            })

            # Extract response
            messages = result.get("messages", [])
            final_response = messages[-1].content if messages else "No response"

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Log agent execution to cost optimizer
            if self.config.track_costs:
                await self.log_agent_execution(
                    agent_type="close_crm",
                    latency_ms=latency_ms,
                    success=True,
                    metadata={
                        "action": action,
                        "provider": self.provider.value,
                        "model": self.model
                    }
                )

            logger.info(f"Close CRM agent completed in {latency_ms}ms")

            return {
                "success": True,
                "response": final_response,
                "action": action,
                "latency_ms": latency_ms,
                "cost_usd": self.total_cost_usd,
                "provider": self.provider.value,
                "model": self.model
            }

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Close CRM agent error: {e}", exc_info=True)

            # Log failure
            if self.config.track_costs:
                await self.log_agent_execution(
                    agent_type="close_crm",
                    latency_ms=latency_ms,
                    success=False,
                    error_message=str(e),
                    metadata={
                        "action": input_data.get("action"),
                        "error": str(e)
                    }
                )

            return {
                "success": False,
                "error": str(e),
                "action": input_data.get("action"),
                "latency_ms": latency_ms
            }

    # ========== Prompt Builders ==========

    def _build_create_lead_prompt(self, data: Dict[str, Any]) -> str:
        """Build prompt for lead creation"""
        return f"""Create a new lead in Close CRM with the following information:

Company: {data.get('company_name', 'N/A')}
Contact Name: {data.get('contact_name', 'N/A')}
Contact Email: {data.get('contact_email', 'REQUIRED')}
Contact Title: {data.get('contact_title', 'N/A')}
Contact Phone: {data.get('contact_phone', 'N/A')}
Industry: {data.get('industry', 'N/A')}
Notes: {data.get('notes', 'N/A')}

IMPORTANT:
1. First check for duplicates using check_duplicate_leads_tool
2. If no duplicates (or confidence < 85%), create the lead using create_lead_tool
3. If duplicate found, DO NOT create - inform me of the existing contact details

Please proceed with duplicate check and lead creation if safe."""

    def _build_search_prompt(self, data: Dict[str, Any]) -> str:
        """Build prompt for lead search"""
        query = data.get('query', data.get('company_name', ''))
        limit = data.get('limit', 10)

        return f"""Search for leads in Close CRM matching: "{query}"

Return up to {limit} results with:
- Company name
- Contact email
- Contact name and title
- Lead ID

Use search_leads_tool to find matching leads."""

    def _build_update_prompt(self, data: Dict[str, Any]) -> str:
        """Build prompt for contact update"""
        external_id = data.get('external_id') or data.get('contact_id')

        fields_to_update = []
        if data.get('first_name'):
            fields_to_update.append(f"First Name: {data['first_name']}")
        if data.get('last_name'):
            fields_to_update.append(f"Last Name: {data['last_name']}")
        if data.get('email'):
            fields_to_update.append(f"Email: {data['email']}")
        if data.get('title'):
            fields_to_update.append(f"Title: {data['title']}")
        if data.get('phone'):
            fields_to_update.append(f"Phone: {data['phone']}")

        fields_str = "\n".join(fields_to_update) if fields_to_update else "No fields specified"

        return f"""Update contact in Close CRM:

Contact ID: {external_id}

Fields to update:
{fields_str}

Use update_contact_tool to apply these changes."""

    def _build_get_prompt(self, data: Dict[str, Any]) -> str:
        """Build prompt for getting lead details"""
        lead_id = data.get('lead_id') or data.get('contact_id')

        return f"""Retrieve full details for lead: {lead_id}

Use get_lead_tool to fetch:
- Contact information
- Company details
- Enrichment data
- Last sync status

Provide a comprehensive summary of the lead."""

    def _build_check_duplicates_prompt(self, data: Dict[str, Any]) -> str:
        """Build prompt for duplicate checking"""
        return f"""Check for duplicate leads in the database:

Email: {data.get('email', 'N/A')}
Company: {data.get('company', 'N/A')}
Phone: {data.get('phone', 'N/A')}
LinkedIn URL: {data.get('linkedin_url', 'N/A')}

Use check_duplicate_leads_tool with threshold: {data.get('threshold', 85.0)}%

Report:
1. Whether duplicates were found
2. Confidence scores for each match
3. Details of matched contacts
4. Recommendation (create new vs update existing)"""


# ========== Factory Function ==========

def get_close_crm_agent(
    provider: str = "deepseek",
    model: Optional[str] = None,
    use_cache: bool = True,
    track_costs: bool = True
) -> CloseCRMAgent:
    """
    Factory function to create Close CRM agent.

    Args:
        provider: LLM provider ("deepseek", "cerebras", "claude", "ollama")
        model: Model name (optional, auto-selected based on provider)
        use_cache: Enable caching for duplicate checks
        track_costs: Enable cost tracking

    Returns:
        Configured CloseCRMAgent instance
    """
    return CloseCRMAgent(
        provider=provider,
        model=model,
        use_cache=use_cache,
        track_costs=track_costs
    )
