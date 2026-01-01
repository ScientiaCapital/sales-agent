"""
Celery tasks for dealer-scraper pipeline automation

Handles:
- Domain verification (scheduled hourly)
- Push to Supabase (MANUAL - requires review)
- Enrichment pipeline orchestration

Hybrid Mode Design:
- Verify: Automated hourly to maintain fresh domain status
- Push: MANUAL only - user reviews batch before pushing
- Enrich: Triggered after push completes
"""

import asyncio
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import os
import httpx

from celery import chain
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging

logger = setup_logging(__name__)

# Default dealer-scraper database path
DEFAULT_DB_PATH = os.getenv(
    "DEALER_SCRAPER_DB_PATH",
    "/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp/output/pipeline.db"
)

# Domain verification settings
DOMAIN_TIMEOUT = 10  # seconds per domain
MAX_CONCURRENT_CHECKS = 10  # parallel HTTP requests


async def _verify_single_domain(domain: str) -> Dict[str, Any]:
    """Verify if a domain is reachable via HTTP(S)."""
    if not domain:
        return {"domain": domain, "valid": False, "status": "empty"}

    # Normalize URL
    test_url = f"https://{domain}" if not domain.startswith("http") else domain

    try:
        async with httpx.AsyncClient(
            timeout=DOMAIN_TIMEOUT,
            follow_redirects=True
        ) as client:
            response = await client.get(test_url)

            # Consider 200, 301, 302, 403 (behind firewall) as valid
            if response.status_code in [200, 301, 302, 403]:
                return {
                    "domain": domain,
                    "valid": True,
                    "status": response.status_code,
                    "final_url": str(response.url)
                }
            return {
                "domain": domain,
                "valid": False,
                "status": response.status_code
            }

    except httpx.TimeoutException:
        return {"domain": domain, "valid": False, "status": "timeout"}
    except httpx.ConnectError:
        return {"domain": domain, "valid": False, "status": "connection_error"}
    except Exception as e:
        return {"domain": domain, "valid": False, "status": f"error: {str(e)[:50]}"}


async def _verify_domains_batch(domains: List[str]) -> List[Dict]:
    """Verify multiple domains in parallel."""
    tasks = [_verify_single_domain(d) for d in domains]
    return await asyncio.gather(*tasks)


@celery_app.task(
    name="app.tasks.dealer_scraper_tasks.verify_dealer_domains_task",
    bind=True,
    max_retries=1,
    soft_time_limit=600,  # 10 min soft limit
    time_limit=660,  # 11 min hard limit
)
def verify_dealer_domains_task(
    self,
    batch_size: int = 100,
    db_path: str = None,
) -> Dict[str, Any]:
    """
    Verify dealer-scraper domains (SCHEDULED - runs hourly).

    Checks HTTP reachability of domains that haven't been verified yet.
    Updates SQLite with verification status.

    Args:
        batch_size: Number of domains to verify per run
        db_path: Path to dealer-scraper SQLite database

    Returns:
        Dict with verification stats
    """
    db_path = db_path or DEFAULT_DB_PATH

    if not Path(db_path).exists():
        logger.error(f"[DealerVerify] Database not found: {db_path}")
        return {"status": "error", "error": f"Database not found: {db_path}"}

    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Ensure columns exist
        for col, default in [
            ("domain_verified_at", "TEXT"),
            ("domain_is_valid", "INTEGER DEFAULT 0"),
            ("domain_check_status", "TEXT"),
        ]:
            try:
                cursor.execute(f"ALTER TABLE contractors ADD COLUMN {col} {default}")
            except sqlite3.OperationalError:
                pass  # Column exists

        conn.commit()

        # Query unverified domains with ICP filters
        query = """
            SELECT id, company_name, primary_domain
            FROM contractors
            WHERE is_deleted = 0
                AND primary_domain IS NOT NULL
                AND primary_domain != ''
                AND domain_verified_at IS NULL
                AND LOWER(company_name) NOT LIKE '%sheet metal%'
                AND LOWER(company_name) NOT LIKE '%aluminum%'
                AND LOWER(company_name) NOT LIKE '%siding%'
                AND LOWER(company_name) NOT LIKE '%window%'
                AND LOWER(company_name) NOT LIKE '%landscap%'
                AND LOWER(company_name) NOT LIKE '%painting%'
                AND LOWER(company_name) NOT LIKE '%drywall%'
                AND LOWER(company_name) NOT LIKE '%concrete%'
                AND LOWER(company_name) NOT LIKE '%masonry%'
                AND LOWER(company_name) NOT LIKE '%flooring%'
                AND LOWER(company_name) NOT LIKE '%carpenter%'
            LIMIT ?
        """

        cursor.execute(query, (batch_size,))
        companies = [dict(row) for row in cursor.fetchall()]

        if not companies:
            logger.info("[DealerVerify] No unverified domains found")
            conn.close()
            return {"status": "complete", "checked": 0, "valid": 0, "invalid": 0}

        logger.info(f"[DealerVerify] Checking {len(companies)} domains...")

        # Verify in batches
        valid_count = 0
        invalid_count = 0

        for i in range(0, len(companies), MAX_CONCURRENT_CHECKS):
            chunk = companies[i:i + MAX_CONCURRENT_CHECKS]
            domains = [c["primary_domain"] for c in chunk]

            results = asyncio.run(_verify_domains_batch(domains))

            for company, result in zip(chunk, results):
                cursor.execute("""
                    UPDATE contractors
                    SET domain_verified_at = ?,
                        domain_is_valid = ?,
                        domain_check_status = ?
                    WHERE id = ?
                """, (
                    datetime.now(timezone.utc).isoformat(),
                    1 if result["valid"] else 0,
                    str(result["status"]),
                    company["id"]
                ))

                if result["valid"]:
                    valid_count += 1
                else:
                    invalid_count += 1

            conn.commit()

        conn.close()

        logger.info(
            f"[DealerVerify] Complete: {len(companies)} checked, "
            f"{valid_count} valid, {invalid_count} invalid"
        )

        return {
            "status": "complete",
            "checked": len(companies),
            "valid": valid_count,
            "invalid": invalid_count,
            "event": "domains_verified",
        }

    except SoftTimeLimitExceeded:
        logger.warning("[DealerVerify] Task timeout - partial completion")
        return {"status": "timeout", "error": "Task exceeded time limit"}
    except Exception as e:
        logger.error(f"[DealerVerify] Error: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.tasks.dealer_scraper_tasks.push_verified_dealers_task",
    bind=True,
    max_retries=1,
    soft_time_limit=300,  # 5 min
    time_limit=360,  # 6 min
)
def push_verified_dealers_task(
    self,
    batch_size: int = 5,
    min_icp_score: int = 40,
    db_path: str = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """
    Push verified dealers to Supabase (MANUAL - requires user trigger).

    NOT scheduled - user reviews batch via CLI before pushing:
        celery -A app.celery_app call app.tasks.dealer_scraper_tasks.push_verified_dealers_task

    Args:
        batch_size: Number of companies to push
        min_icp_score: Minimum ICP score threshold
        db_path: Path to dealer-scraper SQLite database
        dry_run: If True, preview only (no writes)

    Returns:
        Dict with push results
    """
    from dotenv import load_dotenv
    from supabase import create_client

    db_path = db_path or DEFAULT_DB_PATH
    load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

    if not supabase_url or not supabase_key:
        return {"status": "error", "error": "Missing Supabase credentials"}

    if not Path(db_path).exists():
        return {"status": "error", "error": f"Database not found: {db_path}"}

    try:
        # Get verified companies from SQLite
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        query = f"""
            SELECT
                id, company_name, normalized_name, primary_domain,
                website_url, primary_phone, primary_email,
                street, city, state, zip, company_linkedin_url,
                year_founded, employee_count, estimated_revenue,
                icp_score, icp_tier, is_resimercial
            FROM contractors
            WHERE is_deleted = 0
                AND pushed_to_sales_agent = 0
                AND primary_domain IS NOT NULL
                AND primary_domain != ''
                AND domain_verified_at IS NOT NULL
                AND domain_is_valid = 1
                AND (icp_score IS NULL OR icp_score >= ?)
            ORDER BY icp_score DESC NULLS LAST
            LIMIT ?
        """

        cursor.execute(query, (min_icp_score, batch_size))
        companies = [dict(row) for row in cursor.fetchall()]

        if not companies:
            conn.close()
            return {"status": "complete", "pushed": 0, "skipped": 0}

        logger.info(f"[DealerPush] Found {len(companies)} companies to push")

        supabase = create_client(supabase_url, supabase_key)
        pushed_ids = []
        skipped_count = 0
        dealer_ids = []

        for company in companies:
            domain = company["primary_domain"]

            # Dedup check in Supabase
            existing = (
                supabase.table("dim_companies")
                .select("company_id")
                .eq("domain", domain)
                .execute()
            )

            if existing.data:
                logger.info(f"[DealerPush] Skipping duplicate: {domain}")
                skipped_count += 1
                continue

            if dry_run:
                logger.info(f"[DealerPush] [DRY RUN] Would push: {company['company_name']}")
                continue

            # Insert to Supabase
            data = {
                "company_name": company["company_name"],
                "normalized_name": company["normalized_name"],
                "domain": domain,
                "website": company["website_url"],
                "phone": company["primary_phone"],
                "street": company["street"],
                "city": company["city"],
                "state": company["state"],
                "zip": company["zip"],
                "icp_score": company["icp_score"] or 0,
                "icp_tier": company["icp_tier"] or "BRONZE",
                "source_type": "dealer-scraper",
                "current_stage": "imported",
                "first_seen_at": datetime.now(timezone.utc).isoformat(),
            }

            try:
                response = supabase.table("dim_companies").insert(data).execute()
                company_id = response.data[0]["company_id"]
                pushed_ids.append(company_id)
                dealer_ids.append(company["id"])
                logger.info(f"[DealerPush] Pushed: {company['company_name']} -> {company_id}")
            except Exception as e:
                logger.error(f"[DealerPush] Insert error for {domain}: {e}")

        # Mark as pushed in SQLite
        if not dry_run and dealer_ids:
            for dealer_id in dealer_ids:
                cursor.execute(
                    "UPDATE contractors SET pushed_to_sales_agent = 1, pushed_at = ? WHERE id = ?",
                    (datetime.now(timezone.utc).isoformat(), dealer_id)
                )
            conn.commit()

        conn.close()

        result = {
            "status": "complete",
            "pushed": len(pushed_ids),
            "skipped": skipped_count,
            "company_ids": pushed_ids,
            "dry_run": dry_run,
        }

        # Trigger enrichment pipeline if companies were pushed
        if pushed_ids and not dry_run:
            result["event"] = "dealers_pushed"
            result["trigger_enrichment"] = True

        return result

    except Exception as e:
        logger.error(f"[DealerPush] Error: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


@celery_app.task(
    name="app.tasks.dealer_scraper_tasks.run_dealer_enrichment_pipeline",
    bind=True,
    max_retries=0,
)
def run_dealer_enrichment_pipeline(
    self,
    company_ids: List[str],
) -> Dict[str, Any]:
    """
    Orchestrate 4-stage enrichment pipeline for pushed dealers.

    Stages (sequential, stop on failure):
    1. Free enrichment (company info, LinkedIn)
    2. VLM enrichment (screenshot analysis)
    3. Browserbase enrichment (contact scraping)
    4. Hunter enrichment (email verification)

    Args:
        company_ids: List of company UUIDs to enrich

    Returns:
        Dict with pipeline status
    """
    from app.tasks.enrichment_tasks import run_website_enrichment_batch

    if not company_ids:
        return {"status": "skipped", "reason": "No company IDs provided"}

    logger.info(f"[DealerPipeline] Starting enrichment for {len(company_ids)} companies")

    # For now, trigger the standard enrichment batch
    # Future: Chain multiple enrichment stages
    try:
        # Trigger enrichment (will pick up new companies)
        run_website_enrichment_batch.delay(batch_size=len(company_ids))

        return {
            "status": "triggered",
            "companies": len(company_ids),
            "event": "enrichment_pipeline_started",
        }

    except Exception as e:
        logger.error(f"[DealerPipeline] Error triggering enrichment: {e}")
        return {"status": "error", "error": str(e)}


@celery_app.task(name="app.tasks.dealer_scraper_tasks.get_dealer_pipeline_stats")
def get_dealer_pipeline_stats(db_path: str = None) -> Dict[str, Any]:
    """
    Get current dealer pipeline statistics.

    Returns counts for each stage:
    - Total contractors
    - Unverified domains
    - Verified valid domains
    - Verified invalid domains
    - Pushed to sales-agent
    - Pending push (verified but not pushed)
    """
    db_path = db_path or DEFAULT_DB_PATH

    if not Path(db_path).exists():
        return {"status": "error", "error": f"Database not found: {db_path}"}

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        stats = {}

        # Total non-deleted contractors
        cursor.execute("SELECT COUNT(*) FROM contractors WHERE is_deleted = 0")
        stats["total"] = cursor.fetchone()[0]

        # With domains
        cursor.execute("""
            SELECT COUNT(*) FROM contractors
            WHERE is_deleted = 0 AND primary_domain IS NOT NULL AND primary_domain != ''
        """)
        stats["with_domain"] = cursor.fetchone()[0]

        # Unverified
        cursor.execute("""
            SELECT COUNT(*) FROM contractors
            WHERE is_deleted = 0
                AND primary_domain IS NOT NULL
                AND domain_verified_at IS NULL
        """)
        stats["unverified"] = cursor.fetchone()[0]

        # Verified valid
        cursor.execute("""
            SELECT COUNT(*) FROM contractors
            WHERE is_deleted = 0 AND domain_is_valid = 1
        """)
        stats["verified_valid"] = cursor.fetchone()[0]

        # Verified invalid
        cursor.execute("""
            SELECT COUNT(*) FROM contractors
            WHERE is_deleted = 0
                AND domain_verified_at IS NOT NULL
                AND domain_is_valid = 0
        """)
        stats["verified_invalid"] = cursor.fetchone()[0]

        # Pushed to sales-agent
        cursor.execute("""
            SELECT COUNT(*) FROM contractors
            WHERE is_deleted = 0 AND pushed_to_sales_agent = 1
        """)
        stats["pushed"] = cursor.fetchone()[0]

        # Pending push (verified valid but not pushed)
        cursor.execute("""
            SELECT COUNT(*) FROM contractors
            WHERE is_deleted = 0
                AND domain_is_valid = 1
                AND pushed_to_sales_agent = 0
        """)
        stats["pending_push"] = cursor.fetchone()[0]

        conn.close()

        stats["status"] = "complete"
        return stats

    except Exception as e:
        return {"status": "error", "error": str(e)}
