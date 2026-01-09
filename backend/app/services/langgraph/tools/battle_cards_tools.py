"""
LangGraph tools for Battle Cards competitive intelligence.

Provides real-time access to competitor data, objection handlers,
and AI feature comparisons during sales conversations.

Tools:
- get_competitor_tool: Get detailed competitor intel
- find_objection_handler_tool: Find response to sales objection
- search_battle_cards_tool: Search across all content

Integration:
- Uses BattleCardsAPIService for API operations
- Error handling: ToolException for LangChain compatibility
"""

import logging
from typing import Dict, Any, Tuple, Optional, List
from pydantic import BaseModel, Field

from langchain_core.tools import tool, ToolException

from app.services.battle_cards_api_service import BattleCardsAPIService
from app.core.exceptions import (
    MissingAPIKeyError,
    APIConnectionError,
    APIAuthenticationError,
    APITimeoutError,
)

logger = logging.getLogger(__name__)


# ========== Pydantic Input Schemas ==========

class GetCompetitorInput(BaseModel):
    """Input for getting competitor intelligence."""
    competitor_name: str = Field(
        ...,
        description="Name of the competitor (e.g., 'ServiceTitan', 'Procore', 'BuildOps', 'Salesforce')"
    )


class ObjectionInput(BaseModel):
    """Input for finding objection handler."""
    objection_text: str = Field(
        ...,
        description="The objection or concern raised by the prospect (e.g., 'too expensive', 'we already have a CRM', 'need to think about it')"
    )


class SearchBattleCardsInput(BaseModel):
    """Input for searching battle cards."""
    query: str = Field(
        ...,
        description="Search query (e.g., 'solar monitoring', 'field service pricing', 'asset tracking')"
    )
    types: Optional[List[str]] = Field(
        default=None,
        description="Filter by type: 'competitors', 'objections', 'ai_features'. Leave empty to search all."
    )


# ========== LangChain Tools ==========

@tool(
    args_schema=GetCompetitorInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def get_competitor_tool(
    competitor_name: str
) -> Tuple[str, Dict[str, Any]]:
    """Get competitive intelligence for a specific competitor.

    This tool retrieves battle card data for positioning against a competitor.
    Returns killer questions, value propositions, competitor gaps, and
    Coperniq advantages to use in the sales conversation.

    Use this tool when:
    - A prospect mentions they're using or evaluating a competitor
    - You need to position Coperniq against a specific product
    - You need the killer question to expose competitor weaknesses
    - You need talking points for competitive differentiation

    Available competitors:
    ServiceTitan, Procore, BuildOps, Buildertrend, Monday.com,
    Salesforce, Pipedrive, HubSpot, SubcontractorHub, Scoop Solar,
    Sunbase, Enerflo

    Args:
        competitor_name: Name of the competitor to get intel on

    Returns:
        Tuple of:
        - Formatted summary with key talking points (for LLM)
        - Full competitor data artifact (for downstream use)
    """
    try:
        service = BattleCardsAPIService()
        competitor = await service.get_competitor_by_name(competitor_name)
        await service.close()

        if not competitor:
            return (
                f"No competitive intelligence found for '{competitor_name}'. "
                f"Available competitors: ServiceTitan, Procore, BuildOps, "
                f"Buildertrend, Monday.com, Salesforce, Pipedrive, HubSpot, "
                f"SubcontractorHub, Scoop Solar, Sunbase, Enerflo",
                {"found": False, "query": competitor_name}
            )

        # Build conversational summary for the LLM
        killer_q = competitor.get("killerQuestion", {})
        cant_do = competitor.get("cantDo", [])[:3]
        advantages = competitor.get("coperniqAdvantages", [])[:3]

        content = f"""**Competitor: {competitor.get('name')}**
Target Market: {competitor.get('targetMarket')}

**Opener:** {competitor.get('opener')}

**Killer Question:** {killer_q.get('question', 'N/A')}
Expected Answer: {killer_q.get('answer', 'N/A')}

**Key Gaps (What They Can't Do):**
{chr(10).join('- ' + gap for gap in cant_do)}

**Coperniq Advantages:**
{chr(10).join('- ' + adv for adv in advantages)}
"""

        return content, {"found": True, "competitor": competitor}

    except MissingAPIKeyError:
        raise ToolException(
            "Battle Cards API key not configured. Contact administrator."
        )
    except (APIConnectionError, APITimeoutError) as e:
        logger.error(f"Battle Cards API error: {e}")
        raise ToolException(f"Failed to fetch competitor data: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in get_competitor_tool: {e}")
        raise ToolException(f"Error retrieving competitor intel: {str(e)}")


@tool(
    args_schema=ObjectionInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def find_objection_handler_tool(
    objection_text: str
) -> Tuple[str, Dict[str, Any]]:
    """Find the best response to a sales objection.

    This tool searches battle cards for proven responses to common
    sales objections. Returns recommended response text and context.

    Use this tool when:
    - A prospect raises a concern or objection
    - You need a proven response to overcome resistance
    - The conversation has stalled due to a specific concern
    - Prospect says things like "too expensive", "we're too small",
      "we already have [competitor]", "need to think about it"

    Common objections covered:
    - "We're too small"
    - "We already have [Competitor]"
    - "It looks expensive"
    - "We need to think about it"
    - "Our team won't adopt it"

    Args:
        objection_text: The objection or concern raised by the prospect

    Returns:
        Tuple of:
        - Recommended response text (for LLM to use)
        - Full objection data and alternatives (for context)
    """
    try:
        service = BattleCardsAPIService()
        results = await service.search(
            query=objection_text,
            types=["objections"],
            limit=3
        )
        await service.close()

        if not results:
            return (
                "No specific handler found for this objection. "
                "Use discovery questions to understand the real concern. "
                "Ask: 'Help me understand - what specifically concerns you about this?'",
                {"found": False, "query": objection_text}
            )

        best_match = results[0]
        content = f"""**Objection: {best_match.get('name', objection_text)}**

**Recommended Response:**
{best_match.get('matchContext', 'No response template available')}
"""

        return content, {
            "found": True,
            "objection": best_match,
            "alternatives": results[1:] if len(results) > 1 else []
        }

    except MissingAPIKeyError:
        raise ToolException(
            "Battle Cards API key not configured. Contact administrator."
        )
    except (APIConnectionError, APITimeoutError) as e:
        logger.error(f"Battle Cards API error: {e}")
        raise ToolException(f"Failed to fetch objection handler: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in find_objection_handler_tool: {e}")
        raise ToolException(f"Error finding objection handler: {str(e)}")


@tool(
    args_schema=SearchBattleCardsInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def search_battle_cards_tool(
    query: str,
    types: Optional[List[str]] = None
) -> Tuple[str, Dict[str, Any]]:
    """Search battle cards for competitive intelligence.

    This tool performs full-text search across all battle card content
    including competitors, objection handlers, and AI features.

    Use this tool when:
    - You need to find information about a specific topic
    - The conversation touches on features or capabilities
    - You need quick access to relevant talking points
    - You want to find related competitive intelligence

    Search covers:
    - Competitor names, taglines, and target markets
    - Value propositions and competitive gaps
    - Killer questions and openers
    - Objection responses
    - AI feature descriptions and ROI

    Args:
        query: Search query string
        types: Optional filter by type (competitors, objections, ai_features)

    Returns:
        Tuple of:
        - Formatted search results summary (for LLM)
        - Full search results data (for downstream use)
    """
    try:
        service = BattleCardsAPIService()
        results = await service.search(query=query, types=types, limit=5)
        await service.close()

        if not results:
            return (
                f"No results found for '{query}'. "
                "Try broader search terms or check spelling.",
                {"found": False, "query": query}
            )

        content = f"**Search Results for '{query}':**\n\n"
        for result in results:
            result_type = result.get("type", "unknown").replace("_", " ").title()
            name = result.get("name", "Unknown")
            context = result.get("matchContext", "")[:100]
            content += f"- **{name}** ({result_type}): {context}...\n"

        return content, {
            "found": True,
            "results": results,
            "query": query,
            "count": len(results)
        }

    except MissingAPIKeyError:
        raise ToolException(
            "Battle Cards API key not configured. Contact administrator."
        )
    except (APIConnectionError, APITimeoutError) as e:
        logger.error(f"Battle Cards API error: {e}")
        raise ToolException(f"Failed to search battle cards: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error in search_battle_cards_tool: {e}")
        raise ToolException(f"Error searching battle cards: {str(e)}")


# ========== Exports ==========

__all__ = [
    "get_competitor_tool",
    "find_objection_handler_tool",
    "search_battle_cards_tool",
]
