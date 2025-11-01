"""
LangChain tools for Lead Qualification

Provides LangChain-compatible tool for lead qualification using QualificationAgent.
Integrates with existing QualificationAgent for fast lead scoring.

Tool:
- qualify_lead_tool: Qualify and score a lead using ICP criteria

Integration:
- Uses QualificationAgent from app.services.langgraph.agents.qualification_agent
- Returns structured results compatible with LangGraph agents
- Supports multiple LLM providers (Cerebras, Claude, DeepSeek, Ollama)
"""

from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field

from langchain_core.tools import tool, ToolException

from app.services.langgraph.agents.qualification_agent import QualificationAgent
from app.core.exceptions import CerebrasAPIError
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# ========== Pydantic Input Schema ==========

class QualifyLeadInput(BaseModel):
    """Input schema for qualifying a lead."""

    company_name: str = Field(
        ...,
        description="Company name (required)"
    )
    company_website: Optional[str] = Field(
        default=None,
        description="Company website URL"
    )
    company_size: Optional[str] = Field(
        default=None,
        description="Company size (e.g., '50-200 employees')"
    )
    industry: Optional[str] = Field(
        default=None,
        description="Industry sector"
    )
    contact_name: Optional[str] = Field(
        default=None,
        description="Contact person's name"
    )
    contact_title: Optional[str] = Field(
        default=None,
        description="Contact person's job title"
    )
    notes: Optional[str] = Field(
        default=None,
        description="Additional context or notes"
    )


# ========== LangChain Tool ==========

@tool(
    args_schema=QualifyLeadInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def qualify_lead_tool(
    company_name: str,
    company_website: Optional[str] = None,
    company_size: Optional[str] = None,
    industry: Optional[str] = None,
    contact_name: Optional[str] = None,
    contact_title: Optional[str] = None,
    notes: Optional[str] = None
) -> Tuple[str, Dict[str, Any]]:
    """Qualify and score a lead using ICP criteria.

    This tool wraps the QualificationAgent to provide lead qualification
    capabilities to LangGraph agents. It uses Cerebras for ultra-fast inference
    (<1000ms) with automatic fallback to Claude or DeepSeek if needed.

    The qualification process evaluates:
    - Company fit (size, industry alignment, market presence)
    - Contact quality (decision-maker level, relevance)
    - Sales potential (buying signals, readiness indicators)

    Use this tool when you need to:
    - Score a lead from 0-100 based on ICP criteria
    - Determine qualification tier (hot/warm/cold/unqualified)
    - Get detailed reasoning for the qualification score
    - Evaluate multiple leads quickly and efficiently

    Performance:
    - Cerebras (default): <1000ms, ~$0.000006 per lead
    - Claude fallback: <3000ms, ~$0.0005 per lead
    - DeepSeek fallback: <3000ms, ~$0.00003 per lead

    Args:
        company_name: Company name (required)
        company_website: Company website URL
        company_size: Company size (e.g., "50-200 employees")
        industry: Industry sector
        contact_name: Contact person's name
        contact_title: Contact person's job title
        notes: Additional context or notes

    Returns:
        Tuple of:
        - Success message with key qualification details (for LLM)
        - Artifact dict with complete qualification data (for downstream processing)

    Raises:
        ToolException: If qualification fails (API error, validation error)

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [qualify_lead_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Qualify Acme Corp, industry SaaS, company size 100-500"
            )]
        })

        content, artifact = result
        print(content)  # "Qualified Acme Corp: Score 85 (hot tier)..."
        print(artifact["score"])  # 85
        print(artifact["tier"])  # "hot"
        ```
    """
    try:
        # Validate required field
        if not company_name or not company_name.strip():
            raise ToolException("company_name is required and cannot be empty")

        # Initialize QualificationAgent (defaults to Cerebras for speed)
        agent = QualificationAgent(
            provider="cerebras",
            model="llama3.1-8b",
            use_cache=True,
            track_costs=True
        )

        # Qualify the lead
        result, latency_ms, metadata = await agent.qualify(
            company_name=company_name,
            company_website=company_website,
            company_size=company_size,
            industry=industry,
            contact_name=contact_name,
            contact_title=contact_title,
            notes=notes
        )

        # Format success message for LLM
        tier_emoji = {
            "hot": "🔥",
            "warm": "🟠",
            "cold": "🔵",
            "unqualified": "⚪"
        }.get(result.tier, "❓")

        success_message = (
            f"Qualified {company_name}: "
            f"Score {result.qualification_score:.1f} ({result.tier} tier {tier_emoji}). "
            f"Reasoning: {result.qualification_reasoning[:150]}..."
        )

        # Build artifact dict for downstream processing
        artifact = {
            "status": "success",
            "company_name": company_name,
            "qualification_score": result.qualification_score,
            "tier": result.tier,
            "qualification_reasoning": result.qualification_reasoning,
            "fit_assessment": result.fit_assessment,
            "contact_quality": result.contact_quality,
            "sales_potential": result.sales_potential,
            "recommendations": result.recommendations or [],
            "latency_ms": latency_ms,
            "provider": metadata.get("provider", "cerebras"),
            "model": metadata.get("model", "llama3.1-8b"),
            "tokens_used": metadata.get("tokens_used", 0),
            "cost_usd": metadata.get("cost_usd", 0.0),
            "cache_hit": metadata.get("cache_hit", False)
        }

        logger.info(
            f"Qualified lead: {company_name} - "
            f"Score: {result.qualification_score}, Tier: {result.tier}, "
            f"Latency: {latency_ms}ms"
        )

        return success_message, artifact

    except CerebrasAPIError as e:
        logger.warning(f"Cerebras API error during qualification: {e}")
        # Try fallback to Claude
        try:
            logger.info("Attempting Claude fallback for qualification")
            agent = QualificationAgent(
                provider="claude",
                model="claude-3-haiku-20240307",
                use_cache=True,
                track_costs=True
            )

            result, latency_ms, metadata = await agent.qualify(
                company_name=company_name,
                company_website=company_website,
                company_size=company_size,
                industry=industry,
                contact_name=contact_name,
                contact_title=contact_title,
                notes=notes
            )

            tier_emoji = {
                "hot": "🔥",
                "warm": "🟠",
                "cold": "🔵",
                "unqualified": "⚪"
            }.get(result.tier, "❓")

            success_message = (
                f"Qualified {company_name} (Claude fallback): "
                f"Score {result.qualification_score:.1f} ({result.tier} tier {tier_emoji}). "
                f"Reasoning: {result.qualification_reasoning[:150]}..."
            )

            artifact = {
                "status": "success_fallback",
                "company_name": company_name,
                "qualification_score": result.qualification_score,
                "tier": result.tier,
                "qualification_reasoning": result.qualification_reasoning,
                "fit_assessment": result.fit_assessment,
                "contact_quality": result.contact_quality,
                "sales_potential": result.sales_potential,
                "recommendations": result.recommendations or [],
                "latency_ms": latency_ms,
                "provider": metadata.get("provider", "claude"),
                "model": metadata.get("model", "claude-3-haiku-20240307"),
                "tokens_used": metadata.get("tokens_used", 0),
                "cost_usd": metadata.get("cost_usd", 0.0),
                "cache_hit": metadata.get("cache_hit", False),
                "fallback_reason": "Cerebras API unavailable"
            }

            logger.info(
                f"Qualified lead (Claude fallback): {company_name} - "
                f"Score: {result.qualification_score}, Tier: {result.tier}"
            )

            return success_message, artifact

        except Exception as fallback_error:
            logger.error(
                f"Both Cerebras and Claude failed for {company_name}. "
                f"Cerebras error: {e}, Claude error: {fallback_error}",
                exc_info=True
            )
            raise ToolException(
                f"Unable to qualify lead: both Cerebras and Claude providers unavailable. "
                f"Please try again later or contact support."
            )

    except ValueError as e:
        # Validation errors from QualificationAgent
        logger.error(f"Validation error during qualification: {e}")
        raise ToolException(f"Invalid input: {str(e)}")

    except Exception as e:
        logger.error(f"Unexpected error during qualification: {e}", exc_info=True)
        raise ToolException(f"Failed to qualify lead: {str(e)}")


# ========== Convenience Functions ==========

def get_qualification_tools():
    """
    Get all qualification tools.

    Returns:
        List of LangChain tools for lead qualification

    Example:
        ```python
        from app.services.langgraph.tools import get_qualification_tools
        from langgraph.prebuilt import create_react_agent

        qualification_tools = get_qualification_tools()
        agent = create_react_agent(llm, qualification_tools)
        ```
    """
    return [qualify_lead_tool]


# ========== Exports ==========

__all__ = [
    "qualify_lead_tool",
    "get_qualification_tools",
    "QualifyLeadInput",
]

