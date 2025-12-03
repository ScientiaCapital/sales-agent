"""
LangChain tools for Hunter.io integration

Provides LangChain-compatible tools for email discovery using Hunter.io API.

Tools:
- find_company_emails_tool: Discover emails at a company by domain

Integration:
- Uses existing HunterEmailService from app.services.hunter_email_service
- Error handling: ToolException for LangChain compatibility
"""

import logging
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field

from langchain_core.tools import tool, ToolException

from app.services.hunter_email_service import (
    HunterEmailService,
    HunterResult,
    HunterEmailFinderResult
)

logger = logging.getLogger(__name__)


# ========== Pydantic Input Schemas ==========

class FindCompanyEmailsInput(BaseModel):
    """Input schema for finding emails at a company."""

    domain: str = Field(
        ...,
        description="Company domain to search (e.g., 'acme.com' or 'https://acme.com')"
    )
    atl_only: bool = Field(
        True,
        description="Filter for Above-The-Line (ATL) contacts only (CEO, CTO, VP, etc.)"
    )


class FindPersonEmailInput(BaseModel):
    """Input schema for finding email of a specific person."""

    first_name: str = Field(
        ...,
        description="Person's first name (e.g., 'John')"
    )
    last_name: str = Field(
        ...,
        description="Person's last name (e.g., 'Doe')"
    )
    domain: str = Field(
        ...,
        description="Company domain (e.g., 'acme.com' or 'https://acme.com')"
    )


# ========== LangChain Tools ==========

@tool(
    args_schema=FindCompanyEmailsInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def find_company_emails_tool(
    domain: str,
    atl_only: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """Find email addresses at a company using Hunter.io Domain Search API.

    Discovers contact emails by searching company domain. Useful for finding
    decision-makers (C-level, VPs, Directors) at target companies.

    Args:
        domain: Company domain to search (e.g., 'acme.com')
        atl_only: Filter for ATL contacts (CEO, CTO, VP, etc.) - default True

    Returns:
        Tuple of (summary_message, result_dict) where result_dict contains:
        - contacts: List of discovered emails with name, title, confidence
        - total_emails: Total number of emails found
        - domain: Searched domain
        - status: "success" | "error" | "rate_limited"

    Example:
        >>> result = await find_company_emails_tool("acme.com", atl_only=True)
        >>> contacts = result[1]["contacts"]
        >>> ceo_email = contacts[0]["email"]  # First result usually highest confidence
    """
    hunter_service = HunterEmailService()

    try:
        logger.info(f"Finding emails at domain: {domain} (ATL only: {atl_only})")

        result: HunterResult = await hunter_service.find_emails(
            domain=domain,
            atl_only=atl_only
        )

        if result.status == "error":
            error_msg = result.error_message or "Unknown error"
            logger.error(f"Hunter.io error for {domain}: {error_msg}")
            raise ToolException(f"Hunter.io failed: {error_msg}")

        if result.status == "rate_limited":
            logger.warning(f"Hunter.io rate limit hit for {domain}")
            raise ToolException("Hunter.io rate limit exceeded. Try again later.")

        # Convert to dict for tool output
        result_dict = {
            "domain": result.domain,
            "contacts": [
                {
                    "email": contact.email,
                    "first_name": contact.first_name,
                    "last_name": contact.last_name,
                    "position": contact.position,
                    "department": contact.department,
                    "confidence": contact.confidence,
                    "source": "hunter.io"
                }
                for contact in result.contacts
            ],
            "total_emails": result.total_emails,
            "status": result.status,
            "atl_only": atl_only
        }

        # Create summary message
        if result.contacts:
            summary = (
                f"Found {len(result.contacts)} "
                f"{'ATL ' if atl_only else ''}contacts at {domain}. "
                f"Top match: {result.contacts[0].email} "
                f"({result.contacts[0].position or 'Unknown title'}) "
                f"- {result.contacts[0].confidence}% confidence."
            )
        else:
            summary = f"No {'ATL ' if atl_only else ''}contacts found at {domain}."

        logger.info(f"Hunter.io: {summary}")

        return summary, result_dict

    except ToolException:
        # Re-raise ToolException as-is
        raise
    except Exception as e:
        logger.error(f"Hunter.io tool failed for {domain}: {e}", exc_info=True)
        raise ToolException(f"Email discovery failed: {str(e)}")


@tool(
    args_schema=FindPersonEmailInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def find_person_email_tool(
    first_name: str,
    last_name: str,
    domain: str
) -> Tuple[str, Dict[str, Any]]:
    """Find email address for a specific person at a company using Hunter.io Email Finder API.

    Use this tool when you have a person's name (from website scraping) but no email.
    Hunter.io will find the most likely email address for that person at the company.

    Args:
        first_name: Person's first name (e.g., "John")
        last_name: Person's last name (e.g., "Doe")
        domain: Company domain (e.g., "acme.com")

    Returns:
        Tuple of (summary_message, result_dict) where result_dict contains:
        - email: Discovered email address (or None if not found)
        - confidence: Confidence score 0-100
        - status: "success" | "not_found" | "error" | "rate_limited"

    Example:
        >>> result = await find_person_email_tool("John", "Doe", "acme.com")
        >>> email = result[1]["email"]  # "john.doe@acme.com"
    """
    hunter_service = HunterEmailService()

    try:
        logger.info(f"Finding email for {first_name} {last_name} at {domain}")

        result: HunterEmailFinderResult = await hunter_service.find_email(
            first_name=first_name,
            last_name=last_name,
            domain=domain
        )

        if result.status == "error":
            error_msg = result.error_message or "Unknown error"
            logger.error(f"Hunter.io error for {first_name} {last_name}: {error_msg}")
            raise ToolException(f"Hunter.io failed: {error_msg}")

        if result.status == "rate_limited":
            logger.warning(f"Hunter.io rate limit hit for {first_name} {last_name}")
            raise ToolException("Hunter.io rate limit exceeded. Try again later.")

        # Convert to dict for tool output
        result_dict = {
            "email": result.email,
            "first_name": result.first_name,
            "last_name": result.last_name,
            "domain": result.domain,
            "confidence": result.confidence,
            "status": result.status,
            "source": "hunter.io"
        }

        # Create summary message
        if result.status == "success" and result.email:
            summary = (
                f"Found email for {first_name} {last_name}: {result.email} "
                f"(confidence: {result.confidence}%)"
            )
        elif result.status == "not_found":
            summary = f"No email found for {first_name} {last_name} at {domain}"
        else:
            summary = f"Could not find email for {first_name} {last_name}"

        logger.info(f"Hunter.io: {summary}")

        return summary, result_dict

    except ToolException:
        # Re-raise ToolException as-is
        raise
    except Exception as e:
        logger.error(f"Hunter.io tool failed for {first_name} {last_name}: {e}", exc_info=True)
        raise ToolException(f"Email finder failed: {str(e)}")


# Singleton Hunter service instance
_hunter_service: HunterEmailService = None


def get_hunter_service() -> HunterEmailService:
    """Get or create Hunter.io service instance."""
    global _hunter_service
    if _hunter_service is None:
        _hunter_service = HunterEmailService()
    return _hunter_service
