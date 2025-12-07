"""
Celery tasks for ScoutAgent (Lead Discovery + Sales Intelligence)

Consolidated from:
- run_lead_scout (LeadScoutAgent)
- run_sales_intel_batch (SalesIntelAgent)

Schedule: Every 30 min
Event Trigger: company_imported
Emits: company_enriched (for RankingAgent)

Usage:
    # Scheduled via Celery Beat
    run_scout_cycle.delay(limit=10)

    # Event-triggered (when company imported)
    run_scout_for_company.delay(company_id="uuid-123")
"""

import asyncio
from typing import Optional
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery_app
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ============================================================================
# SCOUT CYCLE TASKS
# ============================================================================

@celery_app.task(name="run_scout_cycle", bind=True, max_retries=2, soft_time_limit=600)
def run_scout_cycle(
    self,
    limit: int = 10,
    require_domain: bool = True,
    icp_tier: Optional[str] = None
):
    """
    Run ScoutAgent cycle: fetch unenriched leads → scrape → extract intel → save.

    This task runs on a schedule (every 30 min) and processes a batch of
    unenriched companies, extracting:
    - Company story and values
    - Personal hooks (family, pets, hobbies)
    - Pain points and buying signals
    - WHY call recommendations
    - Conversation openers

    Emits `company_enriched` event for each successfully enriched company,
    which triggers RankingAgent to calculate ICP scores.

    Args:
        limit: Maximum companies to process per cycle (default: 10)
        require_domain: Only process companies with domains (default: True)
        icp_tier: Filter by ICP tier (PLATINUM, GOLD, SILVER, BRONZE)

    Returns:
        Dict with:
            - event: "company_enriched" (for event system)
            - total_enriched: Count of successfully enriched companies
            - total_errors: Count of errors
            - duration_ms: Processing time
            - companies: List of enriched company IDs
    """
    try:
        logger.info(f"Starting ScoutAgent cycle: limit={limit}, require_domain={require_domain}")

        # Import and run async scout
        from app.services.langgraph.agents.scout_agent import ScoutAgent

        async def _run_scout():
            scout = ScoutAgent(provider='cerebras')
            return await scout.run_cycle(
                limit=limit,
                require_domain=require_domain,
                icp_tier=icp_tier
            )

        # Run in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_run_scout())
        finally:
            loop.close()

        # Convert to serializable dict
        result_dict = {
            "event": "company_enriched",
            "total_fetched": result.total_fetched,
            "total_enriched": result.total_enriched,
            "total_errors": result.total_errors,
            "errors": result.errors[:5] if result.errors else [],  # Limit error list
            "duration_ms": result.duration_ms,
            "companies": [r.company_id for r in result.results]
        }

        logger.info(
            f"ScoutAgent cycle completed: {result.total_enriched} enriched, "
            f"{result.total_errors} errors, {result.duration_ms}ms"
        )

        return result_dict

    except SoftTimeLimitExceeded:
        logger.warning("ScoutAgent soft time limit exceeded (10 minutes)")
        raise

    except Exception as exc:
        logger.error(f"Error in ScoutAgent cycle: {exc}", exc_info=True)
        countdown = 60 * (2 ** self.request.retries)  # 1 min, 2 min backoff
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(name="run_scout_for_company", bind=True, max_retries=2, soft_time_limit=120)
def run_scout_for_company(self, company_id: str):
    """
    Run ScoutAgent for a single company (event-triggered).

    Triggered by:
    - company_imported event (when new company added to Supabase)
    - Manual enrichment request from dashboard or CLI

    Args:
        company_id: UUID of company in dim_companies

    Returns:
        Dict with:
            - event: "company_enriched"
            - company_id: UUID
            - company_name: Name
            - enriched: True if successful
            - error: Error message if failed
    """
    try:
        logger.info(f"Starting ScoutAgent for single company: {company_id}")

        from app.services.langgraph.agents.scout_agent import ScoutAgent

        async def _run_scout():
            scout = ScoutAgent(provider='cerebras')
            return await scout.enrich_single(company_id)

        # Run in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(_run_scout())
        finally:
            loop.close()

        logger.info(
            f"ScoutAgent enriched {result.company_name}: "
            f"{result.processing_time_ms}ms"
        )

        return {
            "event": "company_enriched",
            "company_id": company_id,
            "company_name": result.company_name,
            "enriched": True,
            "why_call": result.why_call[:200],  # Truncate for result
            "processing_time_ms": result.processing_time_ms
        }

    except SoftTimeLimitExceeded:
        logger.warning(f"ScoutAgent soft time limit exceeded for {company_id}")
        raise

    except Exception as exc:
        logger.error(f"Error enriching company {company_id}: {exc}", exc_info=True)
        countdown = 30 * (2 ** self.request.retries)  # 30s, 60s backoff
        raise self.retry(exc=exc, countdown=countdown)


# ============================================================================
# BATCH SCOUT TASKS
# ============================================================================

@celery_app.task(name="run_scout_batch", bind=True, max_retries=1)
def run_scout_batch(self, company_ids: list[str]):
    """
    Run ScoutAgent for a batch of companies in parallel.

    Useful for:
    - Manual batch enrichment from dashboard
    - Processing CSV imports
    - Backfilling unenriched companies

    Args:
        company_ids: List of company UUIDs

    Returns:
        Dict with batch results
    """
    try:
        from celery import group

        logger.info(f"Starting ScoutAgent batch for {len(company_ids)} companies")

        # Create parallel task group
        job = group([
            run_scout_for_company.s(company_id)
            for company_id in company_ids
        ])

        # Execute in parallel
        results = job.apply_async().get()

        # Count successes and failures
        enriched = sum(1 for r in results if r.get('enriched'))
        errors = len(company_ids) - enriched

        logger.info(
            f"ScoutAgent batch completed: {enriched} enriched, {errors} errors"
        )

        return {
            "event": "batch_enriched",
            "total_requested": len(company_ids),
            "total_enriched": enriched,
            "total_errors": errors,
            "results": results
        }

    except Exception as exc:
        logger.error(f"Error in ScoutAgent batch: {exc}", exc_info=True)
        raise


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    "run_scout_cycle",
    "run_scout_for_company",
    "run_scout_batch"
]
