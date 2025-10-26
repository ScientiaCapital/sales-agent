"""
LangChain tools for Apollo.io integration

Provides LangChain-compatible tools for contact enrichment operations
using Apollo.io API. Integrates with existing ApolloProvider for API operations.

Tools:
- enrich_contact_tool: Enrich contact data using email address

Integration:
- Uses existing ApolloProvider from app.services.crm.apollo
- Database: SessionLocal() for database access
- Redis: Singleton pattern for Redis client (rate limiting)
- Error handling: ToolException for LangChain compatibility
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
import redis.asyncio as redis

from langchain_core.tools import tool, ToolException

from app.models.database import SessionLocal
from app.services.crm.apollo import ApolloProvider
from app.services.crm.base import (
    CRMAuthenticationError,
    CRMRateLimitError,
    CRMNotFoundError,
    CRMNetworkError,
)

logger = logging.getLogger(__name__)

# ========== Redis Client Singleton ==========

_redis_client: Optional[redis.Redis] = None


async def get_redis_client() -> redis.Redis:
    """
    Get or create global Redis client for rate limiting.

    Returns:
        Redis client instance
    """
    global _redis_client

    if _redis_client is None:
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        _redis_client = redis.from_url(redis_url, decode_responses=True)
        logger.info(f"Initialized Redis client: {redis_url}")

    return _redis_client


# ========== Pydantic Input Schemas ==========

class EnrichContactInput(BaseModel):
    """Input schema for enriching a contact with Apollo.io."""

    email: str = Field(
        ...,
        description="Email address of the contact to enrich (required)"
    )


# ========== LangChain Tools ==========

@tool(
    args_schema=EnrichContactInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def enrich_contact_tool(
    email: str
) -> Tuple[str, Dict[str, Any]]:
    """Enrich contact data using Apollo.io People Match API.

    This tool enriches a contact's profile using their email address.
    Apollo.io provides data including job title, company, location,
    social profiles, and employment history.

    Use this tool when you need to:
    - Find detailed information about a contact from their email
    - Enrich sparse contact records with professional details
    - Get current company and job title information
    - Discover social media profiles (LinkedIn, Twitter)

    Rate Limits:
    - 600 requests/hour for Apollo.io API
    - Rate limit status tracked in Redis

    Args:
        email: Email address of the contact to enrich (required)

    Returns:
        Tuple of:
        - Success message with key enrichment details (for LLM)
        - Artifact dict with complete Apollo.io response (for downstream processing)

    Raises:
        ToolException: If enrichment fails (not found, rate limit, API error)

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [enrich_contact_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(content="Enrich contact: john@acme.com")]
        })

        content, artifact = result
        print(content)  # "Successfully enriched john@acme.com..."
        print(artifact["apollo_person"])  # Full Apollo.io response
        ```
    """
    db = SessionLocal()

    try:
        # Validate email
        if not email or "@" not in email:
            raise ToolException("Valid email address is required for enrichment")

        # Get API credentials
        api_key = os.getenv("APOLLO_API_KEY")
        if not api_key:
            raise ToolException(
                "APOLLO_API_KEY not found in environment. "
                "Please configure Apollo.io credentials."
            )

        # Initialize Redis and Apollo provider
        redis_client = await get_redis_client()
        apollo_provider = ApolloProvider(
            db=db,
            redis_client=redis_client,
            api_key=api_key
        )

        # Call Apollo.io enrichment API
        enrichment_result = await apollo_provider.enrich_contact(email)

        if not enrichment_result:
            return (
                f"No enrichment data found for {email} in Apollo.io. "
                f"The email may not be in Apollo's database.",
                {"email": email, "found": False}
            )

        # Extract key details from Apollo response
        contact = enrichment_result.get("contact", {})
        apollo_person = enrichment_result.get("apollo_person", {})

        # Build human-readable summary
        name = contact.get("first_name", "") + " " + contact.get("last_name", "")
        name = name.strip() or email
        title = contact.get("title") or "Unknown title"
        company = contact.get("company") or "Unknown company"
        linkedin_url = contact.get("linkedin_url", "Not available")

        content = (
            f"Successfully enriched {email} via Apollo.io:\n"
            f"- Name: {name}\n"
            f"- Title: {title}\n"
            f"- Company: {company}\n"
            f"- LinkedIn: {linkedin_url}\n"
            f"- Enrichment Date: {enrichment_result.get('enrichment_date', 'N/A')}"
        )

        # Build artifact with full Apollo data
        artifact = {
            "email": email,
            "found": True,
            "contact": contact,
            "apollo_person": apollo_person,
            "enrichment_date": enrichment_result.get("enrichment_date"),
            "source": "apollo.io"
        }

        logger.info(f"Enriched contact via Apollo.io: {email}")

        return content, artifact

    except CRMNotFoundError as e:
        # Contact not found in Apollo (not an error, just no data)
        logger.info(f"Contact not found in Apollo.io: {email}")
        return (
            f"Contact {email} not found in Apollo.io database.",
            {"email": email, "found": False, "error": str(e)}
        )

    except CRMRateLimitError as e:
        raise ToolException(
            f"Apollo.io rate limit exceeded: {str(e)}. "
            f"Rate limit: 600 requests/hour. Please retry in 1 hour."
        )

    except CRMAuthenticationError as e:
        raise ToolException(
            f"Authentication failed: {str(e)}. "
            f"Check APOLLO_API_KEY in environment."
        )

    except CRMNetworkError as e:
        raise ToolException(f"Network error connecting to Apollo.io: {str(e)}")

    except ToolException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error enriching contact: {e}", exc_info=True)
        raise ToolException(
            f"Failed to enrich contact via Apollo.io: {str(e)}. "
            f"This may be an API issue or network problem."
        )

    finally:
        db.close()


# ========== Exports ==========

__all__ = [
    "enrich_contact_tool",
]
