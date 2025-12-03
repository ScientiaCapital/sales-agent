"""
LangChain tools for website scraping integration

Provides LangChain-compatible tools for extracting ATL contacts from company websites.

Tools:
- scrape_company_team_tool: Extract ATL contacts from company team/about pages

Integration:
- Uses existing WebsiteValidator from app.services.website_validator
- Error handling: ToolException for LangChain compatibility
"""

import logging
from typing import Dict, Any, Tuple
from pydantic import BaseModel, Field

from langchain_core.tools import tool, ToolException

from app.services.website_validator import WebsiteValidator
from app.services.browserbase_team_scraper import get_browserbase_team_scraper

logger = logging.getLogger(__name__)


# ========== Pydantic Input Schemas ==========

class ScrapeCompanyTeamInput(BaseModel):
    """Input schema for scraping company team pages."""

    website_url: str = Field(
        ...,
        description="Company website URL (e.g., 'https://acme.com' or 'acme.com')"
    )


# ========== LangChain Tools ==========

@tool(
    args_schema=ScrapeCompanyTeamInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def scrape_company_team_tool(
    website_url: str
) -> Tuple[str, Dict[str, Any]]:
    """Scrape company website to find Above-The-Line (ATL) team members.

    Discovers additional contacts by scraping team/about pages for ATL titles
    (CEO, CTO, VP, Director, Founder, etc.). Use this AFTER Hunter.io to find
    MORE contacts that may not be in Hunter.io's database.

    Args:
        website_url: Company website URL (e.g., 'https://acme.com')

    Returns:
        Tuple of (summary_message, result_dict) where result_dict contains:
        - contacts: List of ATL team members with name, title, email (if found)
        - total_contacts: Total number of ATL contacts discovered
        - team_page_url: URL of the team/about page scraped
        - status: "success" | "error" | "no_team_page"

    Example:
        >>> result = await scrape_company_team_tool("https://acme.com")
        >>> contacts = result[1]["contacts"]
        >>> # Returns: [{"name": "John Doe", "title": "CEO", "email": "john@acme.com"}, ...]
    """
    validator = WebsiteValidator()

    try:
        logger.info(f"Scraping company team from website: {website_url}")

        # PHASE 1: Try BeautifulSoup first (fast, works for static HTML)
        validation_result = await validator.validate(website_url)

        contacts = validation_result.atl_contacts or []
        team_page_url = validation_result.team_page_url
        scraping_method = "beautifulsoup"

        # PHASE 2: Browserbase fallback if BeautifulSoup found nothing
        if not contacts and validation_result.has_team_page:
            logger.info(
                "BeautifulSoup found team page but no contacts. "
                "Trying Browserbase fallback for JavaScript-rendered content..."
            )

            try:
                browserbase_scraper = await get_browserbase_team_scraper()
                browserbase_contacts = await browserbase_scraper.scrape_team_page(website_url)

                if browserbase_contacts:
                    contacts = browserbase_contacts
                    scraping_method = "browserbase"
                    logger.info(
                        f"Browserbase fallback successful: found {len(contacts)} contacts"
                    )
                else:
                    logger.warning("Browserbase fallback also found no contacts")

            except Exception as browserbase_error:
                logger.error(
                    f"Browserbase fallback failed: {browserbase_error}. "
                    f"Continuing with BeautifulSoup results (empty)."
                )

        # Check if we found anything at all
        if not validation_result.has_team_page:
            logger.warning(f"No team page found for {website_url}")
            return (
                f"No team/about page found at {website_url}. Cannot discover additional contacts.",
                {
                    "status": "no_team_page",
                    "contacts": [],
                    "total_contacts": 0,
                    "team_page_url": None,
                    "scraping_method": None
                }
            )

        # Build result dict
        result_dict = {
            "status": "success" if contacts else "no_contacts",
            "website_url": website_url,
            "team_page_url": team_page_url,
            "contacts": contacts,
            "total_contacts": len(contacts),
            "source": "website_scraping",
            "scraping_method": scraping_method  # "beautifulsoup" or "browserbase"
        }

        # Create summary message
        if result_dict["contacts"]:
            contacts_with_emails = [c for c in result_dict["contacts"] if c.get("email")]
            contacts_without_emails = [c for c in result_dict["contacts"] if not c.get("email")]

            summary = (
                f"Found {result_dict['total_contacts']} ATL contacts on {website_url} "
                f"(via {scraping_method}). "
                f"{len(contacts_with_emails)} have emails, "
                f"{len(contacts_without_emails)} need email discovery. "
                f"Top contacts: {', '.join([c['name'] for c in result_dict['contacts'][:3]])}."
            )
        else:
            summary = (
                f"Found team page at {website_url} but no ATL contacts discovered. "
                f"Team page may be JavaScript-rendered or have unusual HTML structure."
            )

        logger.info(f"Website scraping: {summary}")

        return summary, result_dict

    except Exception as e:
        logger.error(f"Website scraping failed for {website_url}: {e}", exc_info=True)
        raise ToolException(f"Website scraping failed: {str(e)}")
    finally:
        await validator.close()


# Singleton validator instance
_validator_instance: WebsiteValidator = None


def get_website_validator() -> WebsiteValidator:
    """Get or create WebsiteValidator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = WebsiteValidator()
    return _validator_instance
