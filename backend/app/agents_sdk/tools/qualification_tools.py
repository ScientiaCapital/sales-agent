"""MCP tools for lead qualification."""
from typing import Dict, Any
from langchain_core.tools import tool

from app.core.logging import setup_logging

logger = setup_logging(__name__)


@tool
async def qualify_lead_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Qualify a lead using the QualificationAgent.

    This tool wraps the existing LangGraph QualificationAgent and calls it
    via direct Python import (no HTTP overhead).

    Args:
        args: Tool arguments
            - company_name (required): Company name
            - company_website (optional): Company website URL
            - company_size (optional): Company size (e.g., "50-200 employees")
            - industry (optional): Industry sector
            - contact_name (optional): Contact person's name
            - contact_title (optional): Contact person's job title
            - notes (optional): Additional context

    Returns:
        Dict with:
            - status: "success", "success_fallback", or "error"
            - data: Qualification result (score, tier, reasoning, etc.)
            - latency_ms: Execution time
            - provider: LLM provider used
    """
    # Import here to avoid circular import and import issues during testing
    from app.services.langgraph.agents.qualification_agent import QualificationAgent
    from app.core.exceptions import CerebrasAPIError

    try:
        # Try primary provider (Cerebras - ultra-fast)
        logger.info(f"Qualifying lead: {args.get('company_name')}")

        agent = QualificationAgent(provider="cerebras", model="llama3.1-8b")
        result, latency, metadata = await agent.qualify(
            company_name=args["company_name"],
            company_website=args.get("company_website"),
            company_size=args.get("company_size"),
            industry=args.get("industry"),
            contact_name=args.get("contact_name"),
            contact_title=args.get("contact_title"),
            notes=args.get("notes")
        )

        return {
            "status": "success",
            "data": {
                "score": result.qualification_score,
                "tier": result.tier,
                "reasoning": result.qualification_reasoning,
                "fit_assessment": result.fit_assessment,
                "contact_quality": result.contact_quality,
                "sales_potential": result.sales_potential,
                "recommendations": result.recommendations
            },
            "latency_ms": latency,
            "provider": "cerebras"
        }

    except CerebrasAPIError as e:
        # Fallback to Claude if Cerebras unavailable
        logger.warning(f"Cerebras unavailable, falling back to Claude: {e}")

        try:
            agent = QualificationAgent(provider="claude", model="claude-3-haiku-20240307")
            result, latency, metadata = await agent.qualify(
                company_name=args["company_name"],
                company_website=args.get("company_website"),
                company_size=args.get("company_size"),
                industry=args.get("industry"),
                contact_name=args.get("contact_name"),
                contact_title=args.get("contact_title"),
                notes=args.get("notes")
            )

            return {
                "status": "success_fallback",
                "data": {
                    "score": result.qualification_score,
                    "tier": result.tier,
                    "reasoning": result.qualification_reasoning,
                    "fit_assessment": result.fit_assessment,
                    "contact_quality": result.contact_quality,
                    "sales_potential": result.sales_potential,
                    "recommendations": result.recommendations
                },
                "latency_ms": latency,
                "provider": "claude"
            }

        except Exception as fallback_error:
            logger.error(f"Claude fallback also failed: {fallback_error}")
            raise

    except Exception as e:
        # Complete failure
        logger.error(f"Qualification tool failed: {e}", exc_info=True)
        return {
            "status": "error",
            "message": f"Unable to qualify lead: {str(e)}",
            "suggestion": "Try enrichment tool to gather more data first"
        }


@tool
async def search_leads_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    Search for leads in the database.

    Args:
        args: Search criteria
            - tier (optional): Filter by tier (hot, warm, cold)
            - min_score (optional): Minimum qualification score
            - max_score (optional): Maximum qualification score
            - industry (optional): Filter by industry
            - state (optional): Filter by state
            - limit (optional): Max results (default: 10)

    Returns:
        List of matching leads with basic info
    """
    # TODO: Implement in Task 8
    return {
        "status": "not_implemented",
        "message": "search_leads tool will be implemented in Task 8"
    }
