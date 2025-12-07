"""
CLI Enrich Command

Drop-in enrichment from terminal with automatic Close CRM deduplication.

Usage:
    python -m cli.enrich "https://acme-hvac.com"
    python -m cli.enrich "Acme HVAC" --type name
    python -m cli.enrich "lead_abc123" --type close_id
    python -m cli.enrich "John Smith, Acme HVAC" --type person
    python -m cli.enrich "https://acme.com" --stage email,sms
    python -m cli.enrich "https://acme.com" --stage all --auto-trigger
"""

import os
import sys
import asyncio
from enum import Enum
from typing import Optional, Dict, Any

import typer
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from cli.formatters import (
    print_checking_dedup,
    print_duplicate_found,
    print_starting_enrichment,
    print_enrichment_progress,
    print_enrichment_result,
    print_staging_options,
    print_staging_complete,
    print_error,
    print_info,
    print_success,
)
from cli.staging import parse_channels, OutreachRequest, StagingMode

app = typer.Typer(
    name="enrich",
    help="Drop-in enrichment command for sales-agent platform",
    add_completion=False
)


class InputType(str, Enum):
    """Input type detection modes."""
    AUTO = "auto"
    URL = "url"
    NAME = "name"
    CLOSE_ID = "close_id"
    PERSON = "person"
    LINKEDIN = "linkedin"


def detect_input_type(input_text: str) -> InputType:
    """
    Auto-detect input type from text.

    Args:
        input_text: Input string to classify

    Returns:
        InputType enum value
    """
    input_lower = input_text.lower().strip()

    # URL detection
    if input_lower.startswith(("http://", "https://", "www.")):
        if "linkedin.com" in input_lower:
            return InputType.LINKEDIN
        return InputType.URL

    # Close lead ID
    if input_text.startswith("lead_"):
        return InputType.CLOSE_ID

    # Person format: "Name, Company" or "Name at Company"
    if "," in input_text or " at " in input_lower:
        return InputType.PERSON

    # Default: company name
    return InputType.NAME


def parse_input(input_text: str, input_type: InputType) -> Dict[str, Any]:
    """
    Parse input into structured data.

    Args:
        input_text: Raw input string
        input_type: Detected or specified input type

    Returns:
        Dict with parsed fields (domain, company_name, person_name, etc.)
    """
    parsed = {
        "raw_input": input_text,
        "input_type": input_type.value,
        "domain": None,
        "company_name": None,
        "person_name": None,
        "close_lead_id": None,
    }

    if input_type == InputType.URL:
        # Extract domain from URL
        from urllib.parse import urlparse
        domain = urlparse(input_text).netloc
        if domain.startswith("www."):
            domain = domain[4:]
        parsed["domain"] = domain

    elif input_type == InputType.LINKEDIN:
        parsed["linkedin_url"] = input_text

    elif input_type == InputType.CLOSE_ID:
        parsed["close_lead_id"] = input_text

    elif input_type == InputType.PERSON:
        # Parse "John Smith, Acme HVAC" or "John Smith at Acme HVAC"
        if "," in input_text:
            parts = input_text.split(",", 1)
            parsed["person_name"] = parts[0].strip()
            parsed["company_name"] = parts[1].strip()
        elif " at " in input_text.lower():
            parts = input_text.lower().split(" at ", 1)
            parsed["person_name"] = parts[0].strip()
            parsed["company_name"] = parts[1].strip()

    elif input_type == InputType.NAME:
        parsed["company_name"] = input_text.strip()

    return parsed


async def check_close_dedup(parsed_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Check Close CRM for existing leads (FIRST STEP - ALWAYS).

    Args:
        parsed_input: Parsed input dict with domain, company_name, etc.

    Returns:
        Existing lead dict if found, None otherwise
    """
    try:
        from app.services.crm.close_deduplication import CloseDeduplicationService

        api_key = os.getenv("CLOSE_API_KEY")
        if not api_key:
            print_error("CLOSE_API_KEY not found in environment")
            return None

        dedup_service = CloseDeduplicationService(api_key=api_key)

        # Check by domain if available
        domain = parsed_input.get("domain")
        company_name = parsed_input.get("company_name")

        if not domain and not company_name:
            # Try to extract from Close lead ID
            close_lead_id = parsed_input.get("close_lead_id")
            if close_lead_id:
                # Lead ID provided - fetch it directly
                print_info(f"Fetching existing lead: {close_lead_id}")
                # TODO: Implement fetch_lead_by_id
                return None

            print_error("No domain or company name to check")
            return None

        # Run deduplication check
        result = await dedup_service.check_duplicate(
            company_name=company_name or domain,
            email=None  # Not checking contacts yet
        )

        if result.is_duplicate or result.company_match_found:
            return {
                "lead_id": result.matched_lead_id,
                "company_name": result.matched_company_name,
                "confidence": result.company_confidence,
                "url": f"https://app.close.com/lead/{result.matched_lead_id}/",
                "contacts": result.existing_contacts or []
            }

        return None

    except Exception as e:
        print_error(f"Error checking Close CRM: {str(e)}")
        return None


async def run_enrichment(parsed_input: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Run enrichment pipeline on parsed input.

    Args:
        parsed_input: Parsed input dict

    Returns:
        Enrichment result dict
    """
    # TODO: Implement actual enrichment logic
    # This is a placeholder that would call:
    # - ScoutAgent for website scraping
    # - Apollo/Hunter for contact discovery
    # - RankingAgent for ICP scoring

    print_enrichment_progress("Fetching company data from Supabase...")
    print_enrichment_progress("Scraping website for contacts...")
    print_enrichment_progress("Discovering ATL contacts via Apollo...")
    print_enrichment_progress("Calculating ICP score...")
    print_enrichment_progress("Assigning quality tier...")

    # Mock result for now
    return {
        "company_name": parsed_input.get("company_name", "Unknown Company"),
        "domain": parsed_input.get("domain", "N/A"),
        "icp_score": 75,
        "icp_tier": "GOLD",
        "quality_tier": "WARM",
        "contacts": [],
        "atl_count": 0,
        "has_email": False,
        "has_phone": False,
        "oem_brands": [],
        "service_areas": [],
    }


async def stage_outreach(
    lead_id: str,
    channels: list[str],
    auto_trigger: bool = False
) -> int:
    """
    Stage outreach drafts for specified channels.

    Args:
        lead_id: Supabase company ID or Close lead ID
        channels: List of channel names
        auto_trigger: If True, send immediately

    Returns:
        Number of drafts created
    """
    # TODO: Implement actual staging logic
    # This would call OutreachAgent to generate drafts

    print_staging_options(channels)

    mode = StagingMode.AUTO_APPROVE if auto_trigger else StagingMode.DRAFT

    # Mock staging
    drafts_created = len(channels)

    return drafts_created


@app.command()
def enrich(
    input: str = typer.Argument(..., help="Company URL, name, Close lead ID, or person name"),
    type: InputType = typer.Option(InputType.AUTO, "--type", "-t", help="Input type (auto-detected by default)"),
    stage: Optional[str] = typer.Option(None, "--stage", "-s", help="Outreach channels to stage (comma-separated: email,sms,linkedin,call or 'all')"),
    auto_trigger: bool = typer.Option(False, "--auto-trigger", help="Auto-send outreach (skips approval)"),
    verbose: bool = typer.Option(True, "--verbose", "-v", help="Show detailed progress"),
):
    """
    Enrich a company or person. Always checks Close CRM first.

    Examples:

        python -m cli.enrich "https://acme-hvac.com"

        python -m cli.enrich "Acme HVAC" --type name

        python -m cli.enrich "lead_abc123" --type close_id

        python -m cli.enrich "https://acme.com" --stage email,sms

        python -m cli.enrich "https://acme.com" --stage all --auto-trigger
    """
    async def async_enrich():
        # 1. Parse input
        if type == InputType.AUTO:
            detected_type = detect_input_type(input)
        else:
            detected_type = type

        parsed = parse_input(input, detected_type)

        if verbose:
            print_info(f"Input type: {detected_type.value}")
            if parsed.get("domain"):
                print_info(f"Domain: {parsed['domain']}")
            if parsed.get("company_name"):
                print_info(f"Company: {parsed['company_name']}")

        # 2. CRITICAL: Check Close CRM FIRST (dedup)
        print_checking_dedup()
        existing_lead = await check_close_dedup(parsed)

        if existing_lead:
            print_duplicate_found(existing_lead)
            return

        # 3. Run enrichment
        print_starting_enrichment()
        result = await run_enrichment(parsed)

        if not result:
            print_error("Enrichment failed")
            return

        # 4. Display results
        print_enrichment_result(result)

        # 5. Handle staging if requested
        if stage:
            channels = parse_channels(stage)
            if channels:
                # Use result to get lead ID (would come from enrichment)
                lead_id = result.get("lead_id", "mock_lead_id")
                drafts_created = await stage_outreach(lead_id, channels, auto_trigger)
                print_staging_complete(drafts_created)
            else:
                print_error(f"Invalid channels specified: {stage}")

        print_success("Enrichment complete!")

    # Run async function
    asyncio.run(async_enrich())


@app.command()
def version():
    """Show CLI version."""
    from cli import __version__
    print(f"sales-agent CLI v{__version__}")


if __name__ == "__main__":
    app()
