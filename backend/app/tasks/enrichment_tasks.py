"""
Celery tasks for continuous website enrichment

Runs in the background to scrape contractor websites and extract:
- ATL contacts (owners, presidents, VPs)
- OEM brands
- Service areas
- Maintenance plans
- Company info

Uses WebsiteScraper with Browserbase for cloud browser automation.
"""

# LangSmith tracing is configured centrally in celery_app.py
# Do NOT override here - let the central config control tracing
import asyncio
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging

# Suppress LangSmith warning logs when tracing is disabled
logging.getLogger("langsmith.client").setLevel(logging.ERROR)
logging.getLogger("langsmith.utils").setLevel(logging.ERROR)

logger = setup_logging(__name__)


@celery_app.task(
    name="run_website_enrichment_batch",
    bind=True,
    max_retries=1,
    soft_time_limit=720,  # 12 minutes max per batch (10 sites @ ~1 min each + buffer)
    time_limit=780,  # Hard limit 13 minutes
)
def run_website_enrichment_batch(
    self,
    batch_size: int = 5,
    icp_tier: Optional[str] = None,
    priority_domains: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Run website enrichment on a batch of companies.

    Queries Supabase for companies that:
    1. Have a domain
    2. Don't have ai_enriched_at set (not yet enriched)
    3. Optionally filtered by ICP tier

    Args:
        batch_size: Number of companies to enrich per run (default 5)
        icp_tier: Filter by ICP tier (PLATINUM, GOLD, SILVER, BRONZE)
        priority_domains: Specific domains to prioritize

    Returns:
        Dict with enrichment results
    """
    enriched_count = 0
    errors = []

    try:
        from dotenv import load_dotenv
        from supabase import create_client

        # Load env
        load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if not supabase_url or not supabase_key:
            logger.error("[Enrichment] Missing Supabase credentials")
            return {"status": "error", "error": "Missing Supabase credentials"}

        supabase = create_client(supabase_url, supabase_key)

        logger.info(f"[Enrichment] Starting batch: size={batch_size}, tier={icp_tier}")

        # Query companies needing enrichment
        query = (
            supabase.table("dim_companies")
            .select("company_id", "company_name", "domain")
            .not_.is_("domain", "null")
            .is_("ai_enriched_at", "null")
        )

        if icp_tier:
            query = query.eq("icp_tier", icp_tier)

        # Prioritize by ICP tier (Platinum first, then Gold, etc.)
        query = query.order("icp_score", desc=True).limit(batch_size)

        result = query.execute()
        companies = result.data

        if not companies:
            logger.info("[Enrichment] No companies needing enrichment")
            return {
                "status": "success",
                "enriched": 0,
                "message": "No companies needing enrichment",
            }

        logger.info(f"[Enrichment] Found {len(companies)} companies to enrich")

        # Import and run the async scraper
        from app.services.scrapers.website_scraper import WebsiteScraper

        async def run_enrichment():
            nonlocal enriched_count, errors

            scraper = WebsiteScraper(pool_size=2, max_retries=3)
            await scraper.initialize()

            try:
                for company in companies:
                    company_id = company["company_id"]
                    domain = company["domain"]
                    company_name = company["company_name"]

                    try:
                        logger.info(f"[Enrichment] Scraping: {domain}")

                        # Run the scraper
                        scrape_result = await scraper.scrape_domain(domain)

                        if scrape_result.get("success"):
                            # Update company with enriched data
                            update_data = {
                                "ai_enriched_at": datetime.now(timezone.utc).isoformat(),
                                "oem_brands": scrape_result.get("oem_brands", []),
                                "service_areas": scrape_result.get("service_areas", []),
                                "has_maintenance_plan": scrape_result.get(
                                    "has_maintenance_plan", False
                                ),
                            }

                            supabase.table("dim_companies").update(update_data).eq(
                                "company_id", company_id
                            ).execute()

                            # Add any ATL contacts found
                            contacts = scrape_result.get("contacts", [])
                            for contact in contacts:
                                if contact.get("is_atl"):
                                    # Check if contact already exists
                                    existing = (
                                        supabase.table("dim_contacts")
                                        .select("contact_id")
                                        .eq("company_id", company_id)
                                        .eq("full_name", contact["name"])
                                        .execute()
                                    )

                                    if not existing.data:
                                        supabase.table("dim_contacts").insert(
                                            {
                                                "company_id": company_id,
                                                "full_name": contact["name"],
                                                "title": contact.get("title"),
                                                "is_atl": True,
                                                "source": "celery_enrichment",
                                            }
                                        ).execute()

                            enriched_count += 1
                            logger.info(f"[Enrichment] ✅ Enriched: {company_name}")

                            # Log to audit trail
                            try:
                                supabase.table("lead_audit_log").insert(
                                    {
                                        "company_id": company_id,
                                        "company_name": company_name,
                                        "event_type": "enrichment_complete",
                                        "details": {
                                            "source": "celery_enrichment",
                                            "contacts_found": len(contacts),
                                            "oem_brands": len(
                                                scrape_result.get("oem_brands", [])
                                            ),
                                            "service_areas": len(
                                                scrape_result.get("service_areas", [])
                                            ),
                                        },
                                    }
                                ).execute()
                            except Exception:
                                pass  # Audit log is non-critical

                        else:
                            logger.warning(f"[Enrichment] ⚠️ Scrape failed: {domain}")
                            errors.append(
                                {
                                    "domain": domain,
                                    "error": scrape_result.get("error", "Unknown error"),
                                }
                            )

                    except Exception as e:
                        logger.error(f"[Enrichment] ❌ Error on {domain}: {e}")
                        errors.append({"domain": domain, "error": str(e)})

            finally:
                await scraper.close()

        # Run async code in sync context
        asyncio.run(run_enrichment())

        logger.info(
            f"[Enrichment] Batch complete: {enriched_count}/{len(companies)} enriched"
        )

        return {
            "status": "success",
            "enriched": enriched_count,
            "total": len(companies),
            "errors": len(errors),
            "error_details": errors[:5],  # Limit error details
        }

    except SoftTimeLimitExceeded:
        logger.error("[Enrichment] Task timeout")
        return {
            "status": "error",
            "error": "Task timeout after 10 minutes",
            "enriched": enriched_count,
        }

    except Exception as e:
        logger.error(f"[Enrichment] Task failed: {e}")
        return {"status": "error", "error": str(e), "enriched": enriched_count}


@celery_app.task(name="run_priority_enrichment", bind=True, max_retries=2)
def run_priority_enrichment(self, company_id: str) -> Dict[str, Any]:
    """
    Run priority enrichment on a specific company.

    Called when a lead is imported or manually triggered.

    Args:
        company_id: UUID of the company to enrich

    Returns:
        Dict with enrichment result
    """
    try:
        from dotenv import load_dotenv
        from supabase import create_client

        load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

        supabase = create_client(
            os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_SERVICE_KEY")
        )

        # Get company
        result = (
            supabase.table("dim_companies")
            .select("company_id", "company_name", "domain")
            .eq("company_id", company_id)
            .single()
            .execute()
        )

        company = result.data

        if not company:
            return {"status": "error", "error": "Company not found"}

        if not company.get("domain"):
            return {"status": "error", "error": "Company has no domain"}

        # Enrich using batch task with size=1
        return run_website_enrichment_batch(
            batch_size=1, priority_domains=[company["domain"]]
        )

    except Exception as e:
        logger.error(f"[Priority Enrichment] Failed: {e}")
        return {"status": "error", "error": str(e)}


# ========== Exports ==========

__all__ = ["run_website_enrichment_batch", "run_priority_enrichment"]
