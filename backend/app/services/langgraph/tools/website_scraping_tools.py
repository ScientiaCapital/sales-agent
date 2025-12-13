"""
LangChain tools for website scraping integration

Provides LangChain-compatible tools for extracting ATL contacts from company websites.

Tools:
- scrape_company_team_tool: Extract ATL contacts from company team/about pages
- scrape_website_content_tool: Extract landing page content for personalization
- analyze_website_screenshot_tool: VLM-powered screenshot analysis (Qwen 2.5 VL)

Integration:
- Uses existing WebsiteValidator from app.services.website_validator
- Uses BeautifulSoupTeamScraper for FREE scraping
- Uses VLMWebsiteAnalyzer for AI-powered screenshot analysis
- Error handling: ToolException for LangChain compatibility
"""

import logging
import os
from typing import Dict, Any, Tuple, Optional
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


# ========== Additional Input Schemas ==========

class ScrapeWebsiteContentInput(BaseModel):
    """Input schema for scraping website content."""

    website_url: str = Field(
        ...,
        description="Company website URL (e.g., 'https://acme.com')"
    )


class AnalyzeScreenshotInput(BaseModel):
    """Input schema for VLM screenshot analysis."""

    website_url: str = Field(
        ...,
        description="Company website URL to screenshot and analyze"
    )
    analysis_type: str = Field(
        default="website",
        description="Type of analysis: 'website' for homepage, 'team' for team page"
    )


# ========== Website Content Tool ==========

@tool(
    args_schema=ScrapeWebsiteContentInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def scrape_website_content_tool(
    website_url: str
) -> Tuple[str, Dict[str, Any]]:
    """Scrape company website for landing page content and business signals.

    Extracts comprehensive website data for personalization including:
    - Homepage title, description, value proposition
    - Services and products mentioned
    - Hiring signals (is company hiring?)
    - Funding indicators
    - Tech stack detection (Salesforce, AWS, etc.)
    - Social media links

    Use this tool to gather context for personalized outreach.

    Args:
        website_url: Company website URL (e.g., 'https://acme.com')

    Returns:
        Tuple of (summary_message, result_dict) where result_dict contains:
        - homepage_title: Page title
        - homepage_description: Meta description
        - value_proposition: Main value prop text
        - services: List of services found
        - signals: Dict with is_hiring, has_funding, growth_indicators
        - tech_stack: List of technologies detected
        - social_links: Dict of social media URLs
        - status: "success" | "error"

    Example:
        >>> result = await scrape_website_content_tool("https://acme.com")
        >>> signals = result[1]["signals"]
        >>> # Returns: {"is_hiring": true, "has_funding": false, "growth_indicators": [...]}
    """
    try:
        from app.services.website_content_scraper import WebsiteContentScraper

        logger.info(f"Scraping website content from: {website_url}")

        scraper = WebsiteContentScraper()
        content = await scraper.scrape_website(website_url)

        # Build result
        result_dict = {
            "status": "success",
            "website_url": website_url,
            "homepage_title": content.get("homepage_title", ""),
            "homepage_description": content.get("homepage_description", ""),
            "value_proposition": content.get("value_proposition", ""),
            "services": content.get("services", []),
            "products": content.get("products", []),
            "signals": content.get("signals", {}),
            "tech_stack": content.get("tech_stack", []),
            "social_links": content.get("social_links", {}),
            "pages_scraped": len(content.get("pages_scraped", [])),
            "total_text_length": len(content.get("all_text", "")),
        }

        # Build summary
        signals = result_dict["signals"]
        signal_parts = []
        if signals.get("is_hiring"):
            signal_parts.append("HIRING")
        if signals.get("has_funding"):
            signal_parts.append("FUNDED")
        if result_dict["tech_stack"]:
            signal_parts.append(f"Tech: {', '.join(result_dict['tech_stack'][:3])}")

        summary = (
            f"Scraped {website_url}: "
            f"Title='{result_dict['homepage_title'][:50]}...' | "
            f"Value Prop='{result_dict['value_proposition'][:50]}...' | "
            f"Signals: {', '.join(signal_parts) if signal_parts else 'None detected'}"
        )

        logger.info(f"Website content scraped: {summary}")
        return summary, result_dict

    except Exception as e:
        logger.error(f"Website content scraping failed for {website_url}: {e}")
        raise ToolException(f"Website content scraping failed: {str(e)}")


# ========== VLM Screenshot Analysis Tool ==========

@tool(
    args_schema=AnalyzeScreenshotInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def analyze_website_screenshot_tool(
    website_url: str,
    analysis_type: str = "website"
) -> Tuple[str, Dict[str, Any]]:
    """Take screenshot of website and analyze with VLM (Qwen 2.5 VL).

    Uses AI vision model to extract information from website screenshots that
    BeautifulSoup cannot see (JavaScript-rendered content, images, logos).

    Best for:
    - JS-heavy SPAs where BeautifulSoup fails
    - Extracting info from team photos
    - Reading company logos and visual elements
    - Detecting visual signals (awards, certifications)

    Cost: ~$0.0008/image with balanced model.

    Args:
        website_url: Company website URL to screenshot and analyze
        analysis_type: 'website' for full homepage analysis, 'team' for team page

    Returns:
        Tuple of (summary_message, result_dict) where result_dict contains:
        - company_name: Extracted from logo/header
        - value_proposition: Main headline text
        - services: List of services visible
        - industry: Detected industry
        - team_members: List of executives (if team analysis)
        - tech_signals: Technology mentions
        - confidence: AI confidence score (0-1)
        - status: "success" | "error"

    Example:
        >>> result = await analyze_website_screenshot_tool("https://acme.com", "team")
        >>> team = result[1]["team_members"]
        >>> # Returns: [{"name": "Jane Doe", "title": "CEO"}, ...]
    """
    try:
        # Check for OpenRouter API key
        if not os.getenv("OPENROUTER_API_KEY"):
            raise ToolException(
                "OPENROUTER_API_KEY not set. Add to .env to enable VLM analysis."
            )

        from app.services.website_content_scraper import WebsiteScreenshotter
        from app.services.vlm_website_analyzer import VLMWebsiteAnalyzer

        logger.info(f"Taking screenshot and analyzing: {website_url} ({analysis_type})")

        # Step 1: Take screenshot
        async with WebsiteScreenshotter() as screenshotter:
            screenshot_path = await screenshotter.take_screenshot(
                website_url,
                company_id="agent_analysis"
            )

            if not screenshot_path:
                return (
                    f"Failed to capture screenshot of {website_url}. "
                    "Playwright may not be available.",
                    {
                        "status": "error",
                        "error": "Screenshot capture failed",
                        "website_url": website_url,
                    }
                )

        # Step 2: Analyze with VLM
        analyzer = VLMWebsiteAnalyzer(model_tier="balanced")
        result = await analyzer.analyze_screenshot(
            image_path=screenshot_path,
            analysis_type=analysis_type
        )

        if result.get("error"):
            return (
                f"VLM analysis failed for {website_url}: {result['error']}",
                {
                    "status": "error",
                    "error": result["error"],
                    "website_url": website_url,
                }
            )

        # Add metadata
        result["status"] = "success"
        result["website_url"] = website_url
        result["screenshot_path"] = screenshot_path
        result["analysis_type"] = analysis_type

        # Build summary
        company = result.get("company_name", "Unknown")
        confidence = result.get("confidence", 0)
        team_count = len(result.get("team_members", []))

        if analysis_type == "team":
            summary = (
                f"VLM analyzed team page of {company}: "
                f"Found {team_count} executives. "
                f"Confidence: {confidence:.0%}"
            )
        else:
            value_prop = result.get("value_proposition", "")[:50]
            industry = result.get("industry", "Unknown")
            summary = (
                f"VLM analyzed {company}: "
                f"Industry={industry} | "
                f"Value Prop='{value_prop}...' | "
                f"Confidence: {confidence:.0%}"
            )

        logger.info(f"VLM analysis complete: {summary}")
        return summary, result

    except ToolException:
        raise
    except Exception as e:
        logger.error(f"VLM screenshot analysis failed for {website_url}: {e}")
        raise ToolException(f"VLM screenshot analysis failed: {str(e)}")


# ========== FREE BeautifulSoup Scraping Tool ==========

class ScrapeFreeInput(BaseModel):
    """Input schema for free BeautifulSoup scraping."""

    website_url: str = Field(
        ...,
        description="Company website URL (e.g., 'https://acme.com')"
    )


@tool(
    args_schema=ScrapeFreeInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def scrape_team_free_tool(
    website_url: str
) -> Tuple[str, Dict[str, Any]]:
    """Scrape team page for ATL contacts using BeautifulSoup (FREE, no API costs).

    This is the FREE alternative to Browserbase. Uses httpx + BeautifulSoup
    to scrape team/about pages. Works well for static HTML sites.

    Limitations:
    - Won't work on JavaScript-rendered SPAs
    - Use analyze_website_screenshot_tool for JS-heavy sites

    Args:
        website_url: Company website URL (e.g., 'https://acme.com')

    Returns:
        Tuple of (summary_message, result_dict) where result_dict contains:
        - contacts: List of ATL team members with name and title
        - total_contacts: Number of contacts found
        - status: "success" | "no_contacts" | "error"
        - cost: Always $0.00

    Example:
        >>> result = await scrape_team_free_tool("https://stripe.com")
        >>> contacts = result[1]["contacts"]
        >>> # Returns: [{"name": "Patrick Collison", "title": "CEO"}, ...]
    """
    try:
        from app.services.beautifulsoup_team_scraper import BeautifulSoupTeamScraper

        logger.info(f"FREE scraping team page: {website_url}")

        scraper = BeautifulSoupTeamScraper()
        contacts = await scraper.scrape_team_page(website_url)

        result_dict = {
            "status": "success" if contacts else "no_contacts",
            "website_url": website_url,
            "contacts": contacts,
            "total_contacts": len(contacts),
            "scraping_method": "beautifulsoup",
            "cost": "$0.00"
        }

        if contacts:
            top_names = ", ".join([c["name"] for c in contacts[:3]])
            summary = (
                f"FREE scrape found {len(contacts)} ATL contacts at {website_url}. "
                f"Top contacts: {top_names}. Cost: $0.00"
            )
        else:
            summary = (
                f"FREE scrape found no ATL contacts at {website_url}. "
                "Site may be JavaScript-rendered - try analyze_website_screenshot_tool."
            )

        logger.info(summary)
        return summary, result_dict

    except Exception as e:
        logger.error(f"FREE team scraping failed for {website_url}: {e}")
        raise ToolException(f"FREE team scraping failed: {str(e)}")


# ========== Singleton Instances ==========

_validator_instance: WebsiteValidator = None


def get_website_validator() -> WebsiteValidator:
    """Get or create WebsiteValidator instance."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = WebsiteValidator()
    return _validator_instance


# Export all tools
__all__ = [
    "scrape_company_team_tool",
    "scrape_website_content_tool",
    "analyze_website_screenshot_tool",
    "scrape_team_free_tool",
    "get_website_validator",
]
