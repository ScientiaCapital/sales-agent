"""
LeadBatchProcessor - Batch Processing with Asyncio Semaphore Control

Orchestrates parallel lead processing with:
- Concurrent execution limited by asyncio.Semaphore (default: 10 leads)
- Integration with ParallelPipeline StateGraph
- Real-time progress tracking via callbacks
- Error isolation (failed leads don't block others)
- Resume capability for interrupted batches

Architecture:
    ┌─────────────────────────────────────────────────────────────┐
    │                   LeadBatchProcessor                         │
    │  ┌─────────────────────────────────────────────────────────┐│
    │  │  Semaphore (max_concurrent=10)                          ││
    │  └─────────────────────────────────────────────────────────┘│
    │                            │                                 │
    │     ┌──────────────────────┼──────────────────────┐         │
    │     │                      │                      │         │
    │     ▼                      ▼                      ▼         │
    │  ┌──────┐              ┌──────┐              ┌──────┐       │
    │  │Lead 1│              │Lead 2│              │Lead N│       │
    │  │Worker│              │Worker│              │Worker│       │
    │  └──────┘              └──────┘              └──────┘       │
    │     │                      │                      │         │
    │     └──────────────────────┼──────────────────────┘         │
    │                            ▼                                 │
    │                    Progress Callback                         │
    │                    (WebSocket/Redis)                         │
    └─────────────────────────────────────────────────────────────┘

Usage:
    processor = LeadBatchProcessor(max_concurrent=10)
    results = await processor.process_batch(
        batch_job_id="uuid",
        leads=[...],
        options={...},
        progress_callback=lambda p: websocket.send(p)
    )
"""

import asyncio
import time
from typing import Dict, Any, List, Optional, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import update

from app.core.logging import setup_logging
from app.services.parallel_pipeline import ParallelPipeline

logger = setup_logging(__name__)


class LeadStatus(str, Enum):
    """Status for individual leads within a batch."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BatchStatus(str, Enum):
    """Status for the overall batch job."""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    COMPLETED_WITH_ERRORS = "completed_with_errors"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class LeadProgress:
    """Progress update for a single lead."""
    company_id: str
    company_name: str
    status: LeadStatus
    latency_ms: Optional[int] = None
    cost_usd: Optional[float] = None
    error: Optional[str] = None
    result: Optional[Dict[str, Any]] = None


@dataclass
class BatchProgress:
    """Progress update for the entire batch."""
    batch_job_id: str
    status: BatchStatus
    total: int
    processed: int
    successful: int
    failed: int
    skipped: int
    current_lead: Optional[str] = None
    percent_complete: float = 0.0
    elapsed_ms: int = 0
    estimated_remaining_ms: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for WebSocket/API."""
        return {
            "type": "batch_progress",
            "batch_job_id": self.batch_job_id,
            "status": self.status.value,
            "total": self.total,
            "processed": self.processed,
            "successful": self.successful,
            "failed": self.failed,
            "skipped": self.skipped,
            "current_lead": self.current_lead,
            "percent_complete": self.percent_complete,
            "elapsed_ms": self.elapsed_ms,
            "estimated_remaining_ms": self.estimated_remaining_ms,
        }


@dataclass
class BatchResult:
    """Final result from batch processing."""
    batch_job_id: str
    status: BatchStatus
    total_leads: int
    successful_leads: int
    failed_leads: int
    skipped_leads: int
    total_cost_usd: float
    total_latency_ms: int
    lead_results: List[LeadProgress] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage/API."""
        return {
            "batch_job_id": self.batch_job_id,
            "status": self.status.value,
            "total_leads": self.total_leads,
            "successful_leads": self.successful_leads,
            "failed_leads": self.failed_leads,
            "skipped_leads": self.skipped_leads,
            "total_cost_usd": self.total_cost_usd,
            "total_latency_ms": self.total_latency_ms,
            "errors": self.errors,
        }


# Type alias for progress callback
ProgressCallback = Callable[[BatchProgress], Awaitable[None]]


class LeadBatchProcessor:
    """
    Process leads in parallel batches with concurrency control.

    Features:
    - Asyncio semaphore limits concurrent leads
    - Progress callbacks for real-time updates
    - Error isolation per lead
    - Database status updates
    - Pause/resume support
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        db_session: Optional[Session] = None,
    ):
        """
        Initialize batch processor.

        Args:
            max_concurrent: Maximum concurrent leads (default: 10)
            db_session: Optional SQLAlchemy session for status updates
        """
        self.max_concurrent = max_concurrent
        self.db_session = db_session

        # Concurrency control
        self._semaphore = asyncio.Semaphore(max_concurrent)

        # Pipeline instance (lazy loaded)
        self._pipeline: Optional[ParallelPipeline] = None

        # Control flags
        self._paused = False
        self._cancelled = False
        self._pause_event = asyncio.Event()
        self._pause_event.set()  # Not paused initially

        logger.info(f"LeadBatchProcessor initialized with max_concurrent={max_concurrent}")

    def _get_pipeline(self) -> ParallelPipeline:
        """Lazy load the ParallelPipeline."""
        if self._pipeline is None:
            self._pipeline = ParallelPipeline()
        return self._pipeline

    async def process_batch(
        self,
        batch_job_id: str,
        leads: List[Dict[str, Any]],
        options: Optional[Dict[str, Any]] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> BatchResult:
        """
        Process a batch of leads with parallel execution.

        Args:
            batch_job_id: UUID of the batch job for tracking
            leads: List of lead dictionaries to process
            options: Pipeline options passed to each lead
            progress_callback: Async callback for progress updates

        Returns:
            BatchResult with aggregated results and metrics
        """
        total_leads = len(leads)
        logger.info(f"Starting batch {batch_job_id} with {total_leads} leads")

        # Initialize counters
        processed = 0
        successful = 0
        failed = 0
        skipped = 0
        total_cost = 0.0
        lead_results: List[LeadProgress] = []
        errors: List[str] = []

        # Timing
        start_time = time.time()

        # Update batch status to running
        await self._update_batch_status(batch_job_id, BatchStatus.RUNNING)

        # Process leads concurrently with semaphore control
        async def process_single_lead(lead: Dict[str, Any], index: int) -> LeadProgress:
            """Process a single lead with semaphore."""
            nonlocal processed, successful, failed, skipped, total_cost

            company_id = str(lead.get("company_id") or lead.get("id") or f"lead_{index}")
            company_name = lead.get("name") or lead.get("company") or f"Lead {index}"

            # Wait if paused
            await self._pause_event.wait()

            # Check if cancelled
            if self._cancelled:
                return LeadProgress(
                    company_id=company_id,
                    company_name=company_name,
                    status=LeadStatus.SKIPPED,
                )

            async with self._semaphore:
                lead_start = time.time()

                # Send progress update for current lead
                if progress_callback:
                    progress = self._create_progress(
                        batch_job_id=batch_job_id,
                        total=total_leads,
                        processed=processed,
                        successful=successful,
                        failed=failed,
                        skipped=skipped,
                        current_lead=company_name,
                        start_time=start_time,
                    )
                    await progress_callback(progress)

                # Update lead status to processing
                await self._update_lead_status(
                    batch_job_id, company_id, LeadStatus.PROCESSING
                )

                try:
                    # Execute pipeline
                    pipeline = self._get_pipeline()
                    result = await pipeline.execute(
                        lead=lead,
                        options=options,
                        batch_job_id=batch_job_id,
                        company_id=company_id,
                    )

                    latency_ms = int((time.time() - lead_start) * 1000)

                    if result.success:
                        successful += 1
                        status = LeadStatus.COMPLETED
                        total_cost += result.total_cost_usd
                    else:
                        failed += 1
                        status = LeadStatus.FAILED
                        errors.extend(result.errors)

                    processed += 1

                    # Update lead status in DB
                    await self._update_lead_status(
                        batch_job_id,
                        company_id,
                        status,
                        latency_ms=latency_ms,
                        cost_usd=result.total_cost_usd,
                        result_json=result.to_dict(),
                        error=result.errors[0] if result.errors else None,
                    )

                    logger.info(
                        f"[Batch {batch_job_id}] {company_name}: "
                        f"{status.value} ({latency_ms}ms, ${result.total_cost_usd:.6f})"
                    )

                    return LeadProgress(
                        company_id=company_id,
                        company_name=company_name,
                        status=status,
                        latency_ms=latency_ms,
                        cost_usd=result.total_cost_usd,
                        error=result.errors[0] if result.errors else None,
                        result=result.to_dict(),
                    )

                except Exception as e:
                    latency_ms = int((time.time() - lead_start) * 1000)
                    failed += 1
                    processed += 1
                    error_msg = f"Lead {company_name} failed: {str(e)}"
                    errors.append(error_msg)

                    logger.error(f"[Batch {batch_job_id}] {error_msg}")

                    # Update lead status
                    await self._update_lead_status(
                        batch_job_id,
                        company_id,
                        LeadStatus.FAILED,
                        latency_ms=latency_ms,
                        error=str(e),
                    )

                    return LeadProgress(
                        company_id=company_id,
                        company_name=company_name,
                        status=LeadStatus.FAILED,
                        latency_ms=latency_ms,
                        error=str(e),
                    )

        # Create tasks for all leads
        tasks = [
            process_single_lead(lead, i)
            for i, lead in enumerate(leads)
        ]

        # Execute all tasks concurrently (semaphore limits actual concurrency)
        lead_results = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle any exceptions from gather
        for i, result in enumerate(lead_results):
            if isinstance(result, Exception):
                error_msg = f"Lead {i} task failed: {str(result)}"
                errors.append(error_msg)
                logger.error(error_msg)
                lead_results[i] = LeadProgress(
                    company_id=f"lead_{i}",
                    company_name=f"Lead {i}",
                    status=LeadStatus.FAILED,
                    error=str(result),
                )

        # Calculate final metrics
        total_latency = int((time.time() - start_time) * 1000)

        # Determine final status
        if self._cancelled:
            final_status = BatchStatus.CANCELLED
        elif failed > 0 and successful > 0:
            final_status = BatchStatus.COMPLETED_WITH_ERRORS
        elif failed == total_leads:
            final_status = BatchStatus.FAILED
        else:
            final_status = BatchStatus.COMPLETED

        # Update batch status
        await self._update_batch_status(
            batch_job_id,
            final_status,
            processed=processed,
            successful=successful,
            failed=failed,
            skipped=skipped,
        )

        # Final progress callback
        if progress_callback:
            progress = self._create_progress(
                batch_job_id=batch_job_id,
                total=total_leads,
                processed=processed,
                successful=successful,
                failed=failed,
                skipped=skipped,
                current_lead=None,
                start_time=start_time,
                status=final_status,
            )
            await progress_callback(progress)

        logger.info(
            f"Batch {batch_job_id} completed: "
            f"{successful}/{total_leads} successful, "
            f"{failed} failed, ${total_cost:.6f} total, {total_latency}ms"
        )

        return BatchResult(
            batch_job_id=batch_job_id,
            status=final_status,
            total_leads=total_leads,
            successful_leads=successful,
            failed_leads=failed,
            skipped_leads=skipped,
            total_cost_usd=total_cost,
            total_latency_ms=total_latency,
            lead_results=lead_results,
            errors=errors,
        )

    def _create_progress(
        self,
        batch_job_id: str,
        total: int,
        processed: int,
        successful: int,
        failed: int,
        skipped: int,
        current_lead: Optional[str],
        start_time: float,
        status: Optional[BatchStatus] = None,
    ) -> BatchProgress:
        """Create a BatchProgress update."""
        elapsed_ms = int((time.time() - start_time) * 1000)
        percent = (processed / total * 100) if total > 0 else 0

        # Estimate remaining time
        estimated_remaining = None
        if processed > 0 and processed < total:
            avg_time_per_lead = elapsed_ms / processed
            remaining_leads = total - processed
            estimated_remaining = int(avg_time_per_lead * remaining_leads)

        return BatchProgress(
            batch_job_id=batch_job_id,
            status=status or BatchStatus.RUNNING,
            total=total,
            processed=processed,
            successful=successful,
            failed=failed,
            skipped=skipped,
            current_lead=current_lead,
            percent_complete=round(percent, 2),
            elapsed_ms=elapsed_ms,
            estimated_remaining_ms=estimated_remaining,
        )

    async def _update_batch_status(
        self,
        batch_job_id: str,
        status: BatchStatus,
        processed: Optional[int] = None,
        successful: Optional[int] = None,
        failed: Optional[int] = None,
        skipped: Optional[int] = None,
    ) -> None:
        """Update batch job status in database."""
        if not self.db_session:
            return

        try:
            from app.models.batch_job import BatchJob

            updates = {"status": status.value}

            if status == BatchStatus.RUNNING:
                updates["started_at"] = datetime.utcnow()
            elif status in (BatchStatus.COMPLETED, BatchStatus.COMPLETED_WITH_ERRORS,
                           BatchStatus.FAILED, BatchStatus.CANCELLED):
                updates["completed_at"] = datetime.utcnow()

            if processed is not None:
                updates["processed_leads"] = processed
            if successful is not None:
                updates["successful_leads"] = successful
            if failed is not None:
                updates["failed_leads"] = failed
            if skipped is not None:
                updates["skipped_leads"] = skipped

            stmt = (
                update(BatchJob)
                .where(BatchJob.id == batch_job_id)
                .values(**updates)
            )
            self.db_session.execute(stmt)
            self.db_session.commit()

        except Exception as e:
            logger.error(f"Failed to update batch status: {e}")

    async def _update_lead_status(
        self,
        batch_job_id: str,
        company_id: str,
        status: LeadStatus,
        latency_ms: Optional[int] = None,
        cost_usd: Optional[float] = None,
        result_json: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Update individual lead status in database."""
        if not self.db_session:
            return

        try:
            from app.models.batch_job import BatchJobLead

            updates = {"status": status.value}

            if status == LeadStatus.PROCESSING:
                updates["started_at"] = datetime.utcnow()
            elif status in (LeadStatus.COMPLETED, LeadStatus.FAILED, LeadStatus.SKIPPED):
                updates["completed_at"] = datetime.utcnow()

            if latency_ms is not None:
                updates["latency_ms"] = latency_ms
            if cost_usd is not None:
                updates["cost_usd"] = cost_usd
            if result_json is not None:
                updates["result_json"] = result_json
            if error is not None:
                updates["error_message"] = error

            stmt = (
                update(BatchJobLead)
                .where(BatchJobLead.batch_job_id == batch_job_id)
                .where(BatchJobLead.company_id == company_id)
                .values(**updates)
            )
            self.db_session.execute(stmt)
            self.db_session.commit()

        except Exception as e:
            logger.error(f"Failed to update lead status: {e}")

    # ========== Control Methods ==========

    def pause(self) -> None:
        """Pause batch processing after current leads complete."""
        logger.info("Pausing batch processor")
        self._paused = True
        self._pause_event.clear()

    def resume(self) -> None:
        """Resume paused batch processing."""
        logger.info("Resuming batch processor")
        self._paused = False
        self._pause_event.set()

    def cancel(self) -> None:
        """Cancel batch processing."""
        logger.info("Cancelling batch processor")
        self._cancelled = True
        self._pause_event.set()  # Unblock any paused waits

    @property
    def is_paused(self) -> bool:
        """Check if processor is paused."""
        return self._paused

    @property
    def is_cancelled(self) -> bool:
        """Check if processor is cancelled."""
        return self._cancelled


# ========== Factory Function ==========

def create_batch_processor(
    max_concurrent: int = 10,
    db_session: Optional[Session] = None,
) -> LeadBatchProcessor:
    """
    Factory function to create a LeadBatchProcessor.

    Args:
        max_concurrent: Maximum concurrent leads (default: 10)
        db_session: Optional SQLAlchemy session

    Returns:
        Configured LeadBatchProcessor instance
    """
    return LeadBatchProcessor(
        max_concurrent=max_concurrent,
        db_session=db_session,
    )
