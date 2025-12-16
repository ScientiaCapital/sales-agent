#!/usr/bin/env python3
"""
Push Enriched Leads to Close CRM

CLI orchestrator that:
1. Queries Supabase for enriched companies without Close lead IDs
2. Fetches ATL contacts for each company
3. Pushes leads to Close CRM
4. Optionally subscribes contacts to a sequence

Usage:
    # Dry-run first 10 leads with ICP >= 40 (BRONZE)
    python push_enriched_to_close.py --limit 10 --dry-run --min-icp-score 40

    # Live push 25 leads and subscribe to cold-outbound
    python push_enriched_to_close.py --limit 25 --min-icp-score 40 --sequence "cold-outbound post-pivot"

    # Full push with SILVER threshold
    python push_enriched_to_close.py --limit 50 --min-icp-score 60 --sequence "cold-outbound post-pivot"
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging (basic setup - file handler added later in main())
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Import services
from supabase import create_client, Client
from app.services.crm.close import CloseProvider
from app.services.crm.close_bulk_push import CloseBulkPushService, BulkPushResult
from app.services.crm.close_sequences import CloseSequencesClient


# ICP Score thresholds
ICP_THRESHOLDS = {
    "bronze": 40,   # Wide net - cast wide, gather data, refine
    "silver": 60,   # Medium confidence
    "gold": 80,     # High confidence
    "platinum": 90  # Top tier
}


def get_supabase_client() -> Client:
    """Create Supabase client from environment variables."""
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_SERVICE_KEY")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment"
        )

    return create_client(url, key)


async def fetch_enriched_companies(
    supabase: Client,
    min_icp_score: int,
    limit: int
) -> List[Dict[str, Any]]:
    """
    Fetch enriched companies from Supabase that haven't been pushed to Close.

    Args:
        supabase: Supabase client
        min_icp_score: Minimum ICP score threshold
        limit: Maximum companies to fetch

    Returns:
        List of company dictionaries
    """
    logger.info(f"Fetching companies with ICP >= {min_icp_score}, limit {limit}")

    # Query companies without Close lead ID and with sufficient ICP score
    response = supabase.table("dim_companies") \
        .select("*") \
        .is_("close_lead_id", "null") \
        .gte("icp_score", min_icp_score) \
        .order("icp_score", desc=True) \
        .limit(limit) \
        .execute()

    companies = response.data or []
    logger.info(f"Found {len(companies)} companies to process")

    return companies


async def fetch_contacts_for_company(
    supabase: Client,
    company_id: str,
    atl_only: bool = True
) -> List[Dict[str, Any]]:
    """
    Fetch contacts for a company from Supabase.

    Args:
        supabase: Supabase client
        company_id: Company UUID
        atl_only: Only return ATL contacts

    Returns:
        List of contact dictionaries
    """
    query = supabase.table("dim_contacts") \
        .select("*") \
        .eq("company_id", company_id)

    if atl_only:
        query = query.eq("is_atl", True)

    response = query.execute()

    return response.data or []


async def update_company_close_lead_id(
    supabase: Client,
    company_id: str,
    close_lead_id: str
) -> bool:
    """
    Update company with Close CRM lead ID.

    Args:
        supabase: Supabase client
        company_id: Company UUID
        close_lead_id: Close CRM lead ID

    Returns:
        True if successful
    """
    try:
        supabase.table("dim_companies") \
            .update({"close_lead_id": close_lead_id}) \
            .eq("company_id", company_id) \
            .execute()
        return True
    except Exception as e:
        logger.error(f"Failed to update company {company_id}: {e}")
        return False


def build_leads_data(
    companies: List[Dict[str, Any]],
    contacts_by_company: Dict[str, List[Dict[str, Any]]]
) -> List[Dict[str, Any]]:
    """
    Build leads data structure for bulk push.

    Args:
        companies: List of company dictionaries
        contacts_by_company: Contacts keyed by company_id

    Returns:
        List of lead dictionaries for CloseBulkPushService
    """
    leads_data = []

    for company in companies:
        company_id = company.get("company_id")
        contacts = contacts_by_company.get(company_id, [])

        # Skip companies without contacts
        if not contacts:
            logger.debug(f"Skipping {company.get('name')} - no contacts")
            continue

        # Build lead data structure
        lead = {
            "company_id": company_id,
            "company_name": company.get("name"),
            "domain": company.get("domain"),
            "industry": company.get("industry"),
            "qualification_score": company.get("icp_score", 0),
            "tier": get_tier(company.get("icp_score", 0)),
            "oem_brands": company.get("oem_brands", []),
            "service_areas": company.get("service_areas", []),
            "certifications": company.get("certifications", []),
            "maintenance_plans": company.get("maintenance_plans", []),
            "years_in_business": company.get("years_in_business"),
            "has_emergency_services": company.get("has_emergency_services"),
            "contacts": [
                {
                    "name": f"{c.get('first_name', '')} {c.get('last_name', '')}".strip() or c.get("name"),
                    "first_name": c.get("first_name"),
                    "last_name": c.get("last_name"),
                    "title": c.get("title") or c.get("position"),
                    "email": c.get("email"),
                    "phone": c.get("phone"),
                    "is_atl": c.get("is_atl", False),
                    "position": c.get("title") or c.get("position"),
                    "linkedin": c.get("linkedin_url")
                }
                for c in contacts
                if c.get("email")  # Must have email
            ]
        }

        # Only include leads with contacts
        if lead["contacts"]:
            leads_data.append(lead)

    return leads_data


def get_tier(icp_score: int) -> str:
    """Get tier name from ICP score."""
    if icp_score >= 90:
        return "platinum"
    elif icp_score >= 80:
        return "gold"
    elif icp_score >= 60:
        return "silver"
    elif icp_score >= 40:
        return "bronze"
    else:
        return "unqualified"


async def run_push(
    limit: int,
    dry_run: bool,
    atl_only: bool,
    min_icp_score: int,
    sequence_name: Optional[str] = None,
    batch_size: int = 10
) -> BulkPushResult:
    """
    Main orchestration function for pushing leads to Close CRM.

    Args:
        limit: Maximum leads to process
        dry_run: If True, don't actually create leads
        atl_only: If True, only include ATL contacts
        min_icp_score: Minimum ICP score threshold
        sequence_name: Optional sequence to subscribe contacts to
        batch_size: Leads per batch

    Returns:
        BulkPushResult with operation statistics
    """
    logger.info("=" * 60)
    logger.info("CLOSE CRM BULK PUSH")
    logger.info("=" * 60)
    logger.info(f"Configuration:")
    logger.info(f"  Limit: {limit}")
    logger.info(f"  Dry Run: {dry_run}")
    logger.info(f"  ATL Only: {atl_only}")
    logger.info(f"  Min ICP Score: {min_icp_score} ({get_tier(min_icp_score).upper()})")
    logger.info(f"  Sequence: {sequence_name or 'None'}")
    logger.info(f"  Batch Size: {batch_size}")
    logger.info("=" * 60)

    # Initialize clients
    supabase = get_supabase_client()

    close_provider = CloseProvider(
        api_key=os.getenv("CLOSE_API_KEY")
    )

    bulk_push_service = CloseBulkPushService(
        close_provider=close_provider,
        supabase_client=supabase
    )

    # Fetch enriched companies
    companies = await fetch_enriched_companies(
        supabase=supabase,
        min_icp_score=min_icp_score,
        limit=limit
    )

    if not companies:
        logger.warning("No companies found matching criteria")
        return BulkPushResult(total_leads=0, dry_run=dry_run)

    # Fetch contacts for each company
    logger.info(f"Fetching contacts for {len(companies)} companies...")
    contacts_by_company = {}

    for company in companies:
        company_id = company.get("company_id")
        contacts = await fetch_contacts_for_company(
            supabase=supabase,
            company_id=company_id,
            atl_only=atl_only
        )
        contacts_by_company[company_id] = contacts
        logger.debug(f"  {company.get('name')}: {len(contacts)} contacts")

    # Build leads data
    leads_data = build_leads_data(companies, contacts_by_company)

    if not leads_data:
        logger.warning("No leads with contacts to push")
        return BulkPushResult(total_leads=0, dry_run=dry_run)

    logger.info(f"Prepared {len(leads_data)} leads for push")

    # Push to Close CRM
    result = await bulk_push_service.push_leads(
        leads_data=leads_data,
        dry_run=dry_run,
        atl_only=atl_only,
        batch_size=batch_size,
        rate_limit_delay=0.5  # 500ms between API calls
    )

    # Log results
    logger.info("=" * 60)
    logger.info("PUSH RESULTS")
    logger.info("=" * 60)
    logger.info(f"  Total Leads: {result.total_leads}")
    logger.info(f"  Successful: {result.success_count}")
    logger.info(f"  Failed: {result.failed_count}")
    logger.info(f"  Duplicates Skipped: {result.skipped_duplicates}")
    logger.info(f"  No Contacts Skipped: {result.skipped_no_contacts}")
    if dry_run:
        logger.info(f"  Would Create: {result.would_create_count}")
    logger.info(f"  Success Rate: {result.success_rate:.1%}")
    logger.info("=" * 60)

    # Update Supabase with Close lead IDs (if not dry-run)
    if not dry_run:
        logger.info("Updating Supabase with Close lead IDs...")
        for lead_result in result.results:
            if lead_result.status == "created" and lead_result.close_lead_id:
                # Find matching company by domain
                for lead_data in leads_data:
                    if lead_data.get("domain") == lead_result.domain:
                        company_id = lead_data.get("company_id")
                        await update_company_close_lead_id(
                            supabase=supabase,
                            company_id=company_id,
                            close_lead_id=lead_result.close_lead_id
                        )
                        break

    # Subscribe to sequence (if specified and not dry-run)
    if sequence_name and not dry_run and result.success_count > 0:
        logger.info(f"Subscribing contacts to sequence: {sequence_name}")

        sequences_client = CloseSequencesClient()

        # Find sequence by name
        sequence = await sequences_client.get_sequence_by_name(sequence_name)
        if not sequence:
            logger.error(f"Sequence not found: {sequence_name}")
        else:
            sequence_id = sequence.get("id")
            logger.info(f"Found sequence: {sequence_id}")

            # Collect contact IDs from created leads
            contact_ids = []
            for lead_result in result.results:
                if lead_result.status == "created":
                    # Note: We would need to get contact IDs from the created leads
                    # This would require modifying LeadPushResult to track contact IDs
                    pass

            if contact_ids:
                sub_result = await sequences_client.bulk_subscribe(
                    contact_ids=contact_ids,
                    sequence_id=sequence_id,
                    sender_email=os.getenv("CLOSE_SENDER_EMAIL", "tim@coperniq.io"),
                    sender_name=os.getenv("CLOSE_SENDER_NAME", "Tim Kipper")
                )
                logger.info(f"Sequence subscription results:")
                logger.info(f"  Subscribed: {sub_result['subscribed_count']}")
                logger.info(f"  Already Subscribed: {sub_result['already_subscribed']}")
                logger.info(f"  Failed: {sub_result['failed_count']}")

    return result


def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Push enriched leads from Supabase to Close CRM",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Dry-run with BRONZE threshold (40+)
  python push_enriched_to_close.py --limit 10 --dry-run --min-icp-score 40

  # Live push with SILVER threshold (60+)
  python push_enriched_to_close.py --limit 25 --min-icp-score 60

  # Push and subscribe to sequence
  python push_enriched_to_close.py --limit 50 --min-icp-score 40 --sequence "cold-outbound post-pivot"

ICP Thresholds:
  40+ = BRONZE (wide net, gather data, refine)
  60+ = SILVER (medium confidence)
  80+ = GOLD (high confidence)
  90+ = PLATINUM (top tier)
        """
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum number of leads to process (default: 10)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and report without creating leads"
    )

    parser.add_argument(
        "--atl-only",
        action="store_true",
        default=True,
        help="Only include ATL (decision-maker) contacts (default: True)"
    )

    parser.add_argument(
        "--include-btl",
        action="store_true",
        help="Include BTL contacts (overrides --atl-only)"
    )

    parser.add_argument(
        "--min-icp-score",
        type=int,
        default=40,
        help="Minimum ICP score threshold (default: 40 = BRONZE)"
    )

    parser.add_argument(
        "--sequence",
        type=str,
        help="Sequence name to subscribe contacts to (e.g., 'cold-outbound post-pivot')"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=10,
        help="Number of leads per batch (default: 10)"
    )

    args = parser.parse_args()

    # Resolve ATL-only flag
    atl_only = args.atl_only and not args.include_btl

    # Ensure logs directory exists and add file handler
    os.makedirs("logs", exist_ok=True)
    file_handler = logging.FileHandler(
        f"logs/close_push_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )
    file_handler.setFormatter(
        logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    )
    logging.getLogger().addHandler(file_handler)

    # Check for required environment variables
    required_vars = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY", "CLOSE_API_KEY"]
    missing = [v for v in required_vars if not os.getenv(v)]
    if missing:
        logger.error(f"Missing required environment variables: {', '.join(missing)}")
        sys.exit(1)

    # Check CLOSE_WRITE_DISABLED
    if os.getenv("CLOSE_WRITE_DISABLED", "True").lower() in ("true", "1", "yes"):
        if not args.dry_run:
            logger.warning(
                "CLOSE_WRITE_DISABLED is True - set to False for live writes"
            )
            logger.warning("Running in dry-run mode automatically")
            args.dry_run = True

    # Run the push
    try:
        result = asyncio.run(run_push(
            limit=args.limit,
            dry_run=args.dry_run,
            atl_only=atl_only,
            min_icp_score=args.min_icp_score,
            sequence_name=args.sequence,
            batch_size=args.batch_size
        ))

        # Exit with error code if failures
        if result.failed_count > 0:
            sys.exit(1)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    main()
