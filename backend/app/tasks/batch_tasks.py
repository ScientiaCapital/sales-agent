"""
Celery Batch Tasks - Parallel Lead Processing with Rate Limiting

Provides Celery tasks for batch lead processing with:
- Chord pattern: group of lead tasks -> finalization callback
- Priority queues: high/medium/low based on ICP tier
- Rate limiting: Apollo, Hunter, Browserbase quotas enforced
- Progress tracking: Redis pub/sub for real-time WebSocket updates

Architecture:
    start_batch_task
         │
         ▼
    chord([process_single_lead.s(lead1), ...], finalize.s())
         │
         ├─→ Lead 1 ──→ ParallelPipeline ──→ Results
         ├─→ Lead 2 ──→ ParallelPipeline ──→ Results
         └─→ Lead N ──→ ParallelPipeline ──→ Results
                                │
                                ▼
                    batch_finalize_task (aggregate)
                                │
                                ▼
                    Update BatchJob status + notify

Usage:
    from app.tasks.batch_tasks import start_batch_task

    # Start batch processing
    result = start_batch_task.delay(
        batch_id="uuid",
        company_ids=["id1", "id2", ...],
        options={"skip_enrichment": False}
    )
"""

import os
import time
import asyncio
from typing import Dict, List, Any, Optional
from datetime import datetime

from celery import group, chord
from celery.exceptions import SoftTimeLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy import update

from app.celery_app import celery_app
from app.models.database import SessionLocal
from app.models.batch_job import BatchJob, BatchJobLead
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_db_session() -> Session:
    """Get a database session for Celery tasks."""
    return SessionLocal()


async def publish_progress(batch_id: str, progress: Dict[str, Any]) -> None:
    """
    Publish progress update to Redis for WebSocket consumers.

    Args:
        batch_id: Batch job ID
        progress: Progress dictionary
    """
    try:
        import redis.asyncio as aioredis
        redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

        async with aioredis.from_url(redis_url) as redis:
            channel = f"batch:{batch_id}:progress"
            import json
            await redis.publish(channel, json.dumps(progress))

    except Exception as e:
        logger.warning(f"Failed to publish progress: {e}")


def publish_progress_sync(batch_id: str, progress: Dict[str, Any]) -> None:
    """Synchronous wrapper for publish_progress."""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(publish_progress(batch_id, progress))
        finally:
            loop.close()
    except Exception as e:
        logger.warning(f"Failed to publish progress sync: {e}")


# ============================================================================
# BATCH ORCHESTRATION TASKS
# ============================================================================

@celery_app.task(
    name="start_batch",
    bind=True,
    max_retries=1,
    soft_time_limit=600,  # 10 minutes
    time_limit=660,
)
def start_batch_task(
    self,
    batch_id: str,
    company_ids: List[str],
    options: Optional[Dict[str, Any]] = None,
    priority: str = "medium",
) -> Dict[str, Any]:
    """
    Start batch processing for a list of company IDs.

    Creates a Celery chord:
    - Group: Process each lead in parallel (with concurrency limits)
    - Callback: Finalize batch and update status

    Args:
        batch_id: UUID of the batch job
        company_ids: List of company UUIDs to process
        options: Pipeline options (skip_enrichment, etc.)
        priority: Queue priority (high, medium, low)

    Returns:
        Dictionary with batch start confirmation
    """
    logger.info(f"Starting batch {batch_id} with {len(company_ids)} leads, priority={priority}")

    db = get_db_session()

    try:
        # Update batch status to running
        batch_job = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
        if not batch_job:
            raise ValueError(f"Batch job {batch_id} not found")

        batch_job.status = "running"
        batch_job.started_at = datetime.utcnow()
        db.commit()

        # Create lead records if not exists
        existing_lead_ids = set(
            str(lead.company_id)
            for lead in db.query(BatchJobLead).filter(
                BatchJobLead.batch_job_id == batch_id
            ).all()
        )

        new_leads = []
        for company_id in company_ids:
            if company_id not in existing_lead_ids:
                new_leads.append(BatchJobLead(
                    batch_job_id=batch_id,
                    company_id=company_id,
                    status="pending",
                ))

        if new_leads:
            db.bulk_save_objects(new_leads)
            db.commit()

        db.close()

        # Determine queue based on priority
        queue_map = {
            "high": "batch_priority_high",
            "medium": "batch_priority_medium",
            "low": "batch_priority_low",
        }
        queue = queue_map.get(priority, "batch_priority_medium")

        # Create chord: process all leads, then finalize
        lead_tasks = [
            process_single_lead.s(batch_id, company_id, options or {})
            for company_id in company_ids
        ]

        job = chord(
            group(lead_tasks),
            batch_finalize_task.s(batch_id=batch_id)
        )

        # Execute with specified queue
        job.apply_async(queue=queue)

        # Publish initial progress
        publish_progress_sync(batch_id, {
            "type": "batch_started",
            "batch_id": batch_id,
            "total": len(company_ids),
            "status": "running",
        })

        return {
            "batch_id": batch_id,
            "status": "started",
            "total_leads": len(company_ids),
            "priority": priority,
            "queue": queue,
        }

    except Exception as e:
        logger.error(f"Failed to start batch {batch_id}: {e}")

        # Update batch status to failed
        try:
            db = get_db_session()
            stmt = (
                update(BatchJob)
                .where(BatchJob.id == batch_id)
                .values(status="failed", error_message=str(e))
            )
            db.execute(stmt)
            db.commit()
            db.close()
        except Exception:
            pass

        raise


@celery_app.task(
    name="process_single_lead",
    bind=True,
    max_retries=3,
    soft_time_limit=180,  # 3 minutes per lead
    time_limit=240,
    acks_late=True,  # Acknowledge after completion (for retry on worker crash)
    reject_on_worker_lost=True,  # Requeue if worker dies
)
def process_single_lead(
    self,
    batch_id: str,
    company_id: str,
    options: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Process a single lead through the parallel pipeline.

    This task is rate-limited and uses the rate-limited Apollo service.

    Args:
        batch_id: Batch job ID
        company_id: Company UUID to process
        options: Pipeline options

    Returns:
        Dictionary with processing result
    """
    logger.info(f"Processing lead {company_id} in batch {batch_id}")

    db = get_db_session()
    start_time = time.time()

    try:
        # Update lead status to processing
        lead_record = db.query(BatchJobLead).filter(
            BatchJobLead.batch_job_id == batch_id,
            BatchJobLead.company_id == company_id
        ).first()

        if lead_record:
            lead_record.status = "processing"
            lead_record.started_at = datetime.utcnow()
            db.commit()

        # Fetch company data from Supabase/database
        lead_data = _fetch_company_data(company_id, db)

        if not lead_data:
            raise ValueError(f"Company {company_id} not found")

        # Run pipeline with rate limiting
        result = asyncio.run(
            _run_pipeline_with_rate_limiting(lead_data, options, batch_id, company_id)
        )

        latency_ms = int((time.time() - start_time) * 1000)

        # Update lead status
        if lead_record:
            lead_record.status = "completed" if result.get("success") else "failed"
            lead_record.completed_at = datetime.utcnow()
            lead_record.latency_ms = latency_ms
            lead_record.cost_usd = result.get("cost_usd", 0)
            lead_record.result_json = result
            lead_record.error_message = result.get("error")
            db.commit()

        # Update batch progress counter
        _increment_batch_progress(batch_id, result.get("success", False), db)

        # Publish progress
        publish_progress_sync(batch_id, {
            "type": "lead_completed",
            "batch_id": batch_id,
            "company_id": company_id,
            "company_name": lead_data.get("name", "Unknown"),
            "status": "completed" if result.get("success") else "failed",
            "latency_ms": latency_ms,
        })

        db.close()

        logger.info(f"Lead {company_id} completed in {latency_ms}ms")

        return {
            "company_id": company_id,
            "success": result.get("success", False),
            "latency_ms": latency_ms,
            "cost_usd": result.get("cost_usd", 0),
            "error": result.get("error"),
        }

    except SoftTimeLimitExceeded:
        logger.warning(f"Lead {company_id} soft timeout")
        _mark_lead_failed(batch_id, company_id, "Processing timeout", db)
        db.close()
        raise

    except Exception as e:
        latency_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Lead {company_id} failed: {e}")

        # Update retry count
        if lead_record:
            lead_record.retry_count = (lead_record.retry_count or 0) + 1
            db.commit()

        # Check if should retry
        if self.request.retries < self.max_retries:
            countdown = 2 ** self.request.retries * 10  # 10s, 20s, 40s
            logger.info(f"Retrying lead {company_id} in {countdown}s (attempt {self.request.retries + 1})")
            db.close()
            raise self.retry(exc=e, countdown=countdown)

        # Max retries exceeded
        _mark_lead_failed(batch_id, company_id, str(e), db)
        db.close()

        return {
            "company_id": company_id,
            "success": False,
            "latency_ms": latency_ms,
            "error": str(e),
        }


@celery_app.task(
    name="batch_finalize",
    bind=True,
    max_retries=1,
)
def batch_finalize_task(
    self,
    lead_results: List[Dict[str, Any]],
    batch_id: str,
) -> Dict[str, Any]:
    """
    Finalize batch processing after all leads complete.

    Called as the chord callback after all process_single_lead tasks complete.

    Args:
        lead_results: List of results from each lead task
        batch_id: Batch job ID

    Returns:
        Dictionary with final batch status
    """
    logger.info(f"Finalizing batch {batch_id} with {len(lead_results)} results")

    db = get_db_session()

    try:
        # Calculate aggregates
        successful = sum(1 for r in lead_results if r.get("success"))
        failed = sum(1 for r in lead_results if not r.get("success"))
        total_cost = sum(r.get("cost_usd", 0) for r in lead_results)
        total_latency = sum(r.get("latency_ms", 0) for r in lead_results)

        # Determine final status
        if failed == 0:
            final_status = "completed"
        elif successful > 0:
            final_status = "completed_with_errors"
        else:
            final_status = "failed"

        # Update batch job
        batch_job = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
        if batch_job:
            batch_job.status = final_status
            batch_job.completed_at = datetime.utcnow()
            batch_job.successful_leads = successful
            batch_job.failed_leads = failed
            batch_job.processed_leads = len(lead_results)
            batch_job.result_summary_json = {
                "total_leads": len(lead_results),
                "successful": successful,
                "failed": failed,
                "total_cost_usd": total_cost,
                "total_latency_ms": total_latency,
                "avg_latency_ms": total_latency // len(lead_results) if lead_results else 0,
            }
            db.commit()

        db.close()

        # Publish final progress
        publish_progress_sync(batch_id, {
            "type": "batch_completed",
            "batch_id": batch_id,
            "status": final_status,
            "total": len(lead_results),
            "successful": successful,
            "failed": failed,
            "total_cost_usd": total_cost,
        })

        logger.info(
            f"Batch {batch_id} finalized: {successful}/{len(lead_results)} successful, "
            f"${total_cost:.4f} total cost"
        )

        return {
            "batch_id": batch_id,
            "status": final_status,
            "total_leads": len(lead_results),
            "successful": successful,
            "failed": failed,
            "total_cost_usd": total_cost,
        }

    except Exception as e:
        logger.error(f"Failed to finalize batch {batch_id}: {e}")
        db.close()
        raise


# ============================================================================
# BATCH CONTROL TASKS
# ============================================================================

@celery_app.task(name="pause_batch")
def pause_batch_task(batch_id: str) -> Dict[str, Any]:
    """Pause a running batch (stops processing new leads)."""
    db = get_db_session()

    try:
        batch_job = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
        if not batch_job:
            return {"error": f"Batch {batch_id} not found"}

        if batch_job.status != "running":
            return {"error": f"Batch {batch_id} is not running (status: {batch_job.status})"}

        batch_job.status = "paused"
        db.commit()
        db.close()

        publish_progress_sync(batch_id, {"type": "batch_paused", "batch_id": batch_id})

        return {"batch_id": batch_id, "status": "paused"}

    except Exception as e:
        db.close()
        return {"error": str(e)}


@celery_app.task(name="resume_batch")
def resume_batch_task(batch_id: str) -> Dict[str, Any]:
    """Resume a paused batch."""
    db = get_db_session()

    try:
        batch_job = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
        if not batch_job:
            return {"error": f"Batch {batch_id} not found"}

        if batch_job.status != "paused":
            return {"error": f"Batch {batch_id} is not paused (status: {batch_job.status})"}

        # Get pending leads
        pending_leads = db.query(BatchJobLead).filter(
            BatchJobLead.batch_job_id == batch_id,
            BatchJobLead.status == "pending"
        ).all()

        if not pending_leads:
            batch_job.status = "completed"
            db.commit()
            db.close()
            return {"batch_id": batch_id, "status": "completed", "message": "No pending leads"}

        batch_job.status = "running"
        db.commit()

        # Requeue pending leads
        company_ids = [str(lead.company_id) for lead in pending_leads]
        options = batch_job.options_json or {}

        db.close()

        # Restart with pending leads
        start_batch_task.delay(
            batch_id=batch_id,
            company_ids=company_ids,
            options=options,
            priority=batch_job.priority or "medium"
        )

        return {"batch_id": batch_id, "status": "resumed", "pending_leads": len(company_ids)}

    except Exception as e:
        db.close()
        return {"error": str(e)}


@celery_app.task(name="cancel_batch")
def cancel_batch_task(batch_id: str) -> Dict[str, Any]:
    """Cancel a batch and mark remaining leads as skipped."""
    db = get_db_session()

    try:
        batch_job = db.query(BatchJob).filter(BatchJob.id == batch_id).first()
        if not batch_job:
            return {"error": f"Batch {batch_id} not found"}

        # Mark pending leads as skipped
        pending_count = db.query(BatchJobLead).filter(
            BatchJobLead.batch_job_id == batch_id,
            BatchJobLead.status.in_(["pending", "processing"])
        ).update({"status": "skipped"}, synchronize_session=False)

        batch_job.status = "cancelled"
        batch_job.completed_at = datetime.utcnow()
        batch_job.skipped_leads = pending_count
        db.commit()
        db.close()

        publish_progress_sync(batch_id, {
            "type": "batch_cancelled",
            "batch_id": batch_id,
            "skipped": pending_count
        })

        return {"batch_id": batch_id, "status": "cancelled", "skipped": pending_count}

    except Exception as e:
        db.close()
        return {"error": str(e)}


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _fetch_company_data(company_id: str, db: Session) -> Optional[Dict[str, Any]]:
    """Fetch company data from database or Supabase."""
    try:
        # Try to fetch from Supabase via the dim_companies table
        from supabase import create_client
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")

        if supabase_url and supabase_key:
            supabase = create_client(supabase_url, supabase_key)
            result = supabase.table("dim_companies").select("*").eq("company_id", company_id).single().execute()

            if result.data:
                return result.data

    except Exception as e:
        logger.warning(f"Failed to fetch from Supabase: {e}")

    # Fallback: return minimal data
    return {"company_id": company_id, "name": f"Company {company_id}"}


async def _run_pipeline_with_rate_limiting(
    lead_data: Dict[str, Any],
    options: Dict[str, Any],
    batch_id: str,
    company_id: str,
) -> Dict[str, Any]:
    """
    Run pipeline with rate limiting checks.

    Uses ApolloRateLimitedService and BatchRateLimiter for quota management.
    """
    from app.services.parallel_pipeline import ParallelPipeline
    from app.services.batch_rate_limiter import create_rate_limiter

    rate_limiter = create_rate_limiter()

    try:
        # Check Apollo rate limit before enrichment
        if not options.get("skip_enrichment"):
            can_proceed = await rate_limiter.can_use_apollo()
            if not can_proceed:
                logger.warning(f"Apollo rate limit reached for lead {company_id}")
                # Wait for rate limit to clear
                allowed = await rate_limiter.wait_for_apollo_rate_limit(max_wait_seconds=60)
                if not allowed:
                    return {
                        "success": False,
                        "error": "Apollo rate limit exceeded",
                        "cost_usd": 0,
                    }

        # Run the parallel pipeline
        pipeline = ParallelPipeline()
        result = await pipeline.execute(
            lead=lead_data,
            options=options,
            batch_job_id=batch_id,
            company_id=company_id,
        )

        # Record Apollo usage if enrichment was performed
        if result.enrichment and not options.get("skip_enrichment"):
            await rate_limiter.record_apollo_usage(credits=1)

        return {
            "success": result.success,
            "cost_usd": result.total_cost_usd,
            "latency_ms": result.total_latency_ms,
            "errors": result.errors if result.errors else None,
        }

    except Exception as e:
        logger.error(f"Pipeline failed for {company_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "cost_usd": 0,
        }


def _mark_lead_failed(batch_id: str, company_id: str, error: str, db: Session) -> None:
    """Mark a lead as failed in the database."""
    try:
        lead_record = db.query(BatchJobLead).filter(
            BatchJobLead.batch_job_id == batch_id,
            BatchJobLead.company_id == company_id
        ).first()

        if lead_record:
            lead_record.status = "failed"
            lead_record.completed_at = datetime.utcnow()
            lead_record.error_message = error
            db.commit()

        _increment_batch_progress(batch_id, success=False, db=db)

    except Exception as e:
        logger.error(f"Failed to mark lead {company_id} as failed: {e}")


def _increment_batch_progress(batch_id: str, success: bool, db: Session) -> None:
    """Atomically increment batch progress counters using SQL UPDATE."""
    try:
        # Use atomic SQL update to prevent race conditions
        # Multiple concurrent workers can safely increment counters
        stmt = (
            update(BatchJob)
            .where(BatchJob.id == batch_id)
            .values(
                processed_leads=BatchJob.processed_leads + 1,
                successful_leads=BatchJob.successful_leads + (1 if success else 0),
                failed_leads=BatchJob.failed_leads + (0 if success else 1),
            )
        )
        db.execute(stmt)
        db.commit()

    except Exception as e:
        logger.error(f"Failed to increment batch progress: {e}")
