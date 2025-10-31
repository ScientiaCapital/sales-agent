"""
LangGraph Tools Module

Provides LangChain-compatible tools for CRM, enrichment, social media, and voice operations.
All tools follow async patterns and integrate with existing service providers.

Tool Categories:
- CRM Tools (Close CRM): Lead and contact management
- Apollo Tools: Contact enrichment via Apollo.io
- LinkedIn Tools: Profile scraping via Browserbase
- Cartesia Tools: Ultra-fast text-to-speech synthesis

Usage:
    ```python
    from app.services.langgraph.tools import (
        get_crm_tools,
        get_apollo_tools,
        get_linkedin_tools,
        get_cartesia_tools,
        get_all_tools
    )
    from langgraph.prebuilt import create_react_agent

    # Get all tools (CRM + enrichment + voice)
    all_tools = get_all_tools()

    # Create agent with all capabilities
    agent = create_react_agent(llm, all_tools)

    # Or get specific tool categories
    crm_tools = get_crm_tools()
    enrichment_tools = get_apollo_tools() + get_linkedin_tools()
    voice_tools = get_cartesia_tools()
    ```
"""

from .crm_tools import (
    create_lead_tool,
    update_contact_tool,
    search_leads_tool,
    get_lead_tool,
)

from .apollo_tools import (
    enrich_contact_tool,
)

from .linkedin_tools import (
    get_linkedin_profile_tool,
)

from .cartesia_tools import (
    cartesia_text_to_speech,
    cartesia_list_voices,
    get_cartesia_tools as _get_cartesia_tools_impl,
)

from .linkedin_content_tools import (
    scrape_linkedin_company_posts_tool,
    scrape_linkedin_profile_posts_tool,
    track_atl_contact_linkedin_activity_tool,
    analyze_linkedin_content_tool,
    get_linkedin_content_tools,
)

from .contractor_tools import (
    scrape_contractor_reviews_tool,
    verify_contractor_license_tool,
    search_ahj_databases_tool,
    audit_contractor_compliance_tool,
    get_contractor_tools,
)

from .agent_transfer_tools import (
    create_transfer_tools,
    transfer_to_enrichment,
    transfer_to_growth,
    transfer_to_marketing,
    transfer_to_bdr,
    transfer_to_conversation,
    get_allowed_transfers,
    is_transfer_allowed,
    DEFAULT_TRANSFER_TOOLS,
)


# ========== Convenience Functions ==========

def get_crm_tools():
    """
    Get all Close CRM tools for lead and contact management.

    Returns:
        List of CRM tools: [create_lead_tool, update_contact_tool, search_leads_tool, get_lead_tool]

    Example:
        ```python
        from app.services.langgraph.tools import get_crm_tools
        from langgraph.prebuilt import create_react_agent

        crm_tools = get_crm_tools()
        agent = create_react_agent(llm, crm_tools)

        # Agent can now create leads, update contacts, search, and get lead details
        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Create lead for Acme Corp")]
        })
        ```
    """
    return [
        create_lead_tool,
        update_contact_tool,
        search_leads_tool,
        get_lead_tool,
    ]


def get_apollo_tools():
    """
    Get all Apollo.io tools for contact enrichment.

    Returns:
        List of Apollo tools: [enrich_contact_tool]

    Example:
        ```python
        from app.services.langgraph.tools import get_apollo_tools
        from langgraph.prebuilt import create_react_agent

        apollo_tools = get_apollo_tools()
        agent = create_react_agent(llm, apollo_tools)

        # Agent can now enrich contacts with Apollo.io data
        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Enrich john@acme.com")]
        })
        ```
    """
    return [
        enrich_contact_tool,
    ]


def get_linkedin_tools():
    """
    Get all LinkedIn tools for profile scraping.

    Returns:
        List of LinkedIn tools: [get_linkedin_profile_tool]

    Example:
        ```python
        from app.services.langgraph.tools import get_linkedin_tools
        from langgraph.prebuilt import create_react_agent

        linkedin_tools = get_linkedin_tools()
        agent = create_react_agent(llm, linkedin_tools)

        # Agent can now scrape LinkedIn profiles
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Get LinkedIn profile: https://linkedin.com/in/johndoe"
            )]
        })
        ```
    """
    return [
        get_linkedin_profile_tool,
    ]


def get_linkedin_content_tools():
    """
    Get all LinkedIn content scraping tools.

    Returns:
        List of LinkedIn content tools: [
            scrape_linkedin_company_posts_tool,
            scrape_linkedin_profile_posts_tool,
            track_atl_contact_linkedin_activity_tool,
            analyze_linkedin_content_tool
        ]

    Example:
        ```python
        from app.services.langgraph.tools import get_linkedin_content_tools
        from langgraph.prebuilt import create_react_agent

        linkedin_tools = get_linkedin_content_tools()
        agent = create_react_agent(llm, linkedin_tools)

        # Agent can now scrape LinkedIn content and analyze it
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Scrape Acme Corp's LinkedIn posts and analyze sentiment"
            )]
        })
        ```
    """
    return get_linkedin_content_tools()


def get_contractor_tools():
    """
    Get all contractor industry tools.

    Returns:
        List of contractor tools: [
            scrape_contractor_reviews_tool,
            verify_contractor_license_tool,
            search_ahj_databases_tool,
            audit_contractor_compliance_tool
        ]

    Example:
        ```python
        from app.services.langgraph.tools import get_contractor_tools
        from langgraph.prebuilt import create_react_agent

        contractor_tools = get_contractor_tools()
        agent = create_react_agent(llm, contractor_tools)

        # Agent can now research contractors comprehensively
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Research and audit 'ABC Construction' for compliance"
            )]
        })
        ```
    """
    return get_contractor_tools()


def get_transfer_tools(agent_name: str):
    """
    Get agent transfer tools for multi-agent workflows.

    Args:
        agent_name: Name of current agent

    Returns:
        List of transfer tools specific to this agent

    Example:
        ```python
        from app.services.langgraph.tools import get_transfer_tools
        from langgraph.prebuilt import create_react_agent

        # Get transfer tools for qualification agent
        transfer_tools = get_transfer_tools("qualification")
        agent = create_react_agent(llm, transfer_tools)

        # Agent can now transfer to enrichment, growth, etc.
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Transfer to enrichment for LinkedIn scraping"
            )]
        })
        ```
    """
    allowed_transfers = get_allowed_transfers(agent_name)
    return create_transfer_tools(agent_name, allowed_transfers)


def get_cartesia_tools():
    """
    Get all Cartesia voice tools for ultra-fast TTS synthesis.

    Returns:
        List of Cartesia tools: [cartesia_text_to_speech, cartesia_list_voices]

    Example:
        ```python
        from app.services.langgraph.tools import get_cartesia_tools
        from langgraph.prebuilt import create_react_agent

        voice_tools = get_cartesia_tools()
        agent = create_react_agent(llm, voice_tools)

        # Agent can now synthesize speech and list available voices
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Say 'Hello!' in a happy voice using sonic-turbo for low latency"
            )]
        })
        ```
    """
    return _get_cartesia_tools_impl()


def get_all_integration_tools():
    """
    Get all CRM integration tools (CRM + Apollo + LinkedIn).

    Returns:
        List of all integration tools (6 total)

    Example:
        ```python
        from app.services.langgraph.tools import get_all_integration_tools
        from langgraph.prebuilt import create_react_agent

        all_tools = get_all_integration_tools()
        agent = create_react_agent(llm, all_tools)

        # Agent has access to all CRM, Apollo, and LinkedIn tools
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Create lead for Acme Corp, enrich john@acme.com, and get LinkedIn profile"
            )]
        })
        ```
    """
    return get_crm_tools() + get_apollo_tools() + get_linkedin_tools()


def get_all_tools():
    """
    Get ALL available tools (CRM + enrichment + voice).

    Returns:
        List of all tools (8 total): 4 CRM + 1 Apollo + 1 LinkedIn + 2 Cartesia

    Example:
        ```python
        from app.services.langgraph.tools import get_all_tools
        from langgraph.prebuilt import create_react_agent

        all_tools = get_all_tools()
        agent = create_react_agent(llm, all_tools)

        # Agent has full capabilities: CRM, enrichment, and voice
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content=\"\"\"Create lead for Acme Corp, enrich john@acme.com,
                get LinkedIn profile, and generate a personalized voice greeting\"\"\"
            )]
        })
        ```
    """
    return get_all_integration_tools() + get_cartesia_tools()


# ========== Exports ==========

__all__ = [
    # CRM Tools
    "create_lead_tool",
    "update_contact_tool",
    "search_leads_tool",
    "get_lead_tool",

    # Apollo Tools
    "enrich_contact_tool",

    # LinkedIn Tools
    "get_linkedin_profile_tool",

    # Cartesia Voice Tools
    "cartesia_text_to_speech",
    "cartesia_list_voices",

    # Agent Transfer Tools
    "create_transfer_tools",
    "transfer_to_enrichment",
    "transfer_to_growth",
    "transfer_to_marketing",
    "transfer_to_bdr",
    "transfer_to_conversation",
    "get_allowed_transfers",
    "is_transfer_allowed",
    "DEFAULT_TRANSFER_TOOLS",

    # Convenience Functions
    "get_crm_tools",
    "get_apollo_tools",
    "get_linkedin_tools",
    "get_cartesia_tools",
    "get_transfer_tools",
    "get_all_integration_tools",
    "get_all_tools",
]
