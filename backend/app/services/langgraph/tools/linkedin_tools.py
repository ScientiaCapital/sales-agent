"""
LangChain tools for LinkedIn integration

Provides LangChain-compatible tools for LinkedIn profile enrichment operations.
Uses Browserbase for automated scraping of public LinkedIn profiles.

Tools:
- get_linkedin_profile_tool: Scrape and enrich contact data from LinkedIn profile URL

Integration:
- Uses existing LinkedInProvider from app.services.crm.linkedin
- Database: SessionLocal() for database access
- Redis: Singleton pattern for Redis client (rate limiting)
- Scraping: Browserbase automation for profile data extraction
- Error handling: ToolException for LangChain compatibility
"""

import os
import logging
from typing import Optional, Dict, Any, Tuple
from pydantic import BaseModel, Field
import redis.asyncio as redis

from langchain_core.tools import tool, ToolException

from app.models.database import SessionLocal
from app.services.crm.linkedin import LinkedInProvider
from app.services.crm.base import (
    CRMAuthenticationError,
    CRMRateLimitError,
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

class GetLinkedInProfileInput(BaseModel):
    """Input schema for scraping a LinkedIn profile."""

    profile_url: str = Field(
        ...,
        description="Full LinkedIn profile URL (e.g., https://linkedin.com/in/johndoe)"
    )


# ========== LangChain Tools ==========

@tool(
    args_schema=GetLinkedInProfileInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def get_linkedin_profile_tool(
    profile_url: str
) -> Tuple[str, Dict[str, Any]]:
    """Scrape and enrich contact data from a LinkedIn profile URL.

    This tool uses Browserbase automation to extract rich profile data from
    public LinkedIn profiles. Data includes current position, work history,
    education, skills, and more.

    Use this tool when you need to:
    - Get comprehensive professional background from LinkedIn
    - Find current company and job title
    - Access work experience history
    - Discover skills and education background
    - Enrich contact records with LinkedIn data

    Rate Limits:
    - 100 requests/day for LinkedIn scraping (conservative limit)
    - Rate limit status tracked in Redis

    Prerequisites:
    - BROWSERBASE_API_KEY in environment (for scraping automation)
    - BROWSERBASE_PROJECT_ID in environment
    - Profile must be publicly accessible

    Args:
        profile_url: Full LinkedIn profile URL (e.g., https://linkedin.com/in/johndoe)

    Returns:
        Tuple of:
        - Success message with key profile details (for LLM)
        - Artifact dict with complete profile data (for downstream processing)

    Raises:
        ToolException: If scraping fails (rate limit, invalid URL, scraping error)

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [get_linkedin_profile_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Get LinkedIn profile: https://linkedin.com/in/johndoe"
            )]
        })

        content, artifact = result
        print(content)  # "Successfully scraped LinkedIn profile..."
        print(artifact["experience"])  # Work history
        ```
    """
    db = SessionLocal()

    try:
        # Validate profile URL
        if not profile_url or not profile_url.strip():
            raise ToolException("LinkedIn profile URL is required")

        if "linkedin.com/in/" not in profile_url:
            raise ToolException(
                "Invalid LinkedIn profile URL. "
                "Must be in format: https://linkedin.com/in/username"
            )

        # Check Browserbase credentials
        browserbase_api_key = os.getenv("BROWSERBASE_API_KEY")
        browserbase_project_id = os.getenv("BROWSERBASE_PROJECT_ID")

        if not browserbase_api_key or not browserbase_project_id:
            raise ToolException(
                "BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID not found in environment. "
                "LinkedIn scraping requires Browserbase automation service."
            )

        # Initialize Redis and LinkedIn provider
        redis_client = await get_redis_client()

        # LinkedIn provider requires OAuth credentials, but for scraping we only need Browserbase
        # Pass dummy values for OAuth (they won't be used for scraping)
        linkedin_provider = LinkedInProvider(
            db=db,
            redis_client=redis_client,
            client_id=os.getenv("LINKEDIN_CLIENT_ID", "dummy"),
            client_secret=os.getenv("LINKEDIN_CLIENT_SECRET", "dummy"),
            redirect_uri=os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8001/callback")
        )

        # Scrape LinkedIn profile via Browserbase
        enrichment_result = await linkedin_provider.enrich_contact_from_profile(profile_url)

        if not enrichment_result:
            return (
                f"Failed to scrape LinkedIn profile: {profile_url}. "
                f"The profile may be private or scraping encountered an error.",
                {"profile_url": profile_url, "success": False}
            )

        # Check for scraping errors
        if enrichment_result.get("error"):
            raise ToolException(
                f"LinkedIn scraping error: {enrichment_result.get('error')}"
            )

        # Extract key details from profile
        name = enrichment_result.get("name", "Unknown")
        headline = enrichment_result.get("headline", "No headline")
        current_company = enrichment_result.get("current_company", "No company")
        current_title = enrichment_result.get("current_title", "No title")
        location = enrichment_result.get("location", "Unknown location")
        connections = enrichment_result.get("connections", "Unknown")

        # Count experience and education entries
        experience_count = len(enrichment_result.get("experience", []))
        education_count = len(enrichment_result.get("education", []))
        skills_count = len(enrichment_result.get("skills", []))

        # Build human-readable summary
        content = (
            f"Successfully scraped LinkedIn profile:\n"
            f"- Name: {name}\n"
            f"- Headline: {headline}\n"
            f"- Current Position: {current_title} at {current_company}\n"
            f"- Location: {location}\n"
            f"- Connections: {connections}\n"
            f"- Experience Entries: {experience_count}\n"
            f"- Education Entries: {education_count}\n"
            f"- Skills: {skills_count}\n"
            f"- Scraped At: {enrichment_result.get('scraped_at', 'N/A')}"
        )

        # Build artifact with full profile data
        artifact = {
            "profile_url": profile_url,
            "success": True,
            "source": "linkedin_scraping",
            "name": name,
            "headline": headline,
            "location": location,
            "current_company": current_company,
            "current_title": current_title,
            "connections": connections,
            "experience": enrichment_result.get("experience", []),
            "education": enrichment_result.get("education", []),
            "skills": enrichment_result.get("skills", []),
            "scraped_at": enrichment_result.get("scraped_at")
        }

        logger.info(f"Scraped LinkedIn profile: {profile_url} ({name})")

        return content, artifact

    except CRMRateLimitError as e:
        raise ToolException(
            f"LinkedIn scraping rate limit exceeded: {str(e)}. "
            f"Rate limit: 100 requests/day. Please retry tomorrow."
        )

    except CRMAuthenticationError as e:
        raise ToolException(
            f"Authentication failed: {str(e)}. "
            f"Check BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID in environment."
        )

    except CRMNetworkError as e:
        raise ToolException(f"Network error during LinkedIn scraping: {str(e)}")

    except ToolException:
        raise

    except Exception as e:
        logger.error(f"Unexpected error scraping LinkedIn profile: {e}", exc_info=True)
        raise ToolException(
            f"Failed to scrape LinkedIn profile: {str(e)}. "
            f"This may be due to profile privacy settings or scraping issues."
        )

    finally:
        db.close()


# ========== Exports ==========

__all__ = [
    "get_linkedin_profile_tool",
]
