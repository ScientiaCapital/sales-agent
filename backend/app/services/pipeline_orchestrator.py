"""
Pipeline orchestrator for coordinating 4-stage lead processing
"""
import time
import logging
from typing import Dict, Any, Optional

from app.schemas.pipeline import (
    PipelineTestRequest,
    PipelineTestResponse,
    PipelineStageResult
)

# Import agents (lazy imports to avoid dependency issues in tests)
# These will be mocked in tests anyway
def _lazy_import_agents():
    """Lazy import agents to avoid loading all dependencies during test collection"""
    global QualificationAgent, EnrichmentAgent, DeduplicationService, CloseService

    if QualificationAgent is None:
        from app.services.langgraph.agents.qualification_agent import QualificationAgent as QA
        from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent as EA
        from app.services.crm.deduplication_service import DeduplicationService as DS
        from app.services.crm.close_service import CloseService as CS

        QualificationAgent = QA
        EnrichmentAgent = EA
        DeduplicationService = DS
        CloseService = CS

QualificationAgent = None
EnrichmentAgent = None
DeduplicationService = None
CloseService = None

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates 4-stage lead processing pipeline with performance tracking.

    Pipeline Flow:
    1. Qualification → Lead scoring and tier classification
    2. Enrichment → Company data enhancement (skippable)
    3. Deduplication → Check for existing leads
    4. Close CRM → Create lead in CRM (conditional)

    Tracks latency and cost per stage for observability.
    """

    def __init__(self):
        """Initialize orchestrator with all required services"""
        _lazy_import_agents()  # Import agents only when needed
        self.qualification_agent = QualificationAgent()
        self.enrichment_agent = EnrichmentAgent()
        self.deduplication_service = DeduplicationService()
        self.close_service = CloseService()

    async def execute(self, request: PipelineTestRequest) -> PipelineTestResponse:
        """
        Execute full pipeline with error handling and metrics tracking.

        Args:
            request: Pipeline test request with lead data and options

        Returns:
            PipelineTestResponse with success status, timing, and per-stage results
        """
        lead_name = request.lead.get("name") or request.lead.get("company") or "Unknown Lead"
        stages: Dict[str, PipelineStageResult] = {}
        pipeline_start = time.time()

        try:
            # Stage 1: Qualification
            qual_result = await self._run_qualification(request.lead)
            stages["qualification"] = qual_result

            if qual_result.status == "failed":
                return self._build_error_response(
                    lead_name, stages, "qualification", qual_result.error
                )

            # Stage 2: Enrichment (skippable)
            if request.options.skip_enrichment:
                stages["enrichment"] = PipelineStageResult(
                    status="skipped",
                    latency_ms=0,
                    cost_usd=0.0
                )
            else:
                enrich_result = await self._run_enrichment(request.lead)
                stages["enrichment"] = enrich_result

                if enrich_result.status == "failed":
                    return self._build_error_response(
                        lead_name, stages, "enrichment", enrich_result.error
                    )

            # Stage 3: Deduplication
            dedup_result = await self._run_deduplication(request.lead)
            stages["deduplication"] = dedup_result

            if dedup_result.status == "failed":
                return self._build_error_response(
                    lead_name, stages, "deduplication", dedup_result.error
                )

            # Handle duplicate detection
            if dedup_result.status == "duplicate" or (
                dedup_result.output and dedup_result.output.get("is_duplicate")
            ):
                if request.options.stop_on_duplicate:
                    return self._build_error_response(
                        lead_name,
                        stages,
                        "deduplication",
                        f"Duplicate lead detected (confidence: {dedup_result.confidence or 0:.2f})"
                    )

            # Stage 4: Close CRM (conditional)
            if request.options.create_in_crm and not request.options.dry_run:
                crm_result = await self._run_close_crm(request.lead)
                stages["close_crm"] = crm_result

                if crm_result.status == "failed":
                    return self._build_error_response(
                        lead_name, stages, "close_crm", crm_result.error
                    )
            else:
                stages["close_crm"] = PipelineStageResult(
                    status="skipped" if request.options.dry_run else "dry_run",
                    latency_ms=0,
                    cost_usd=0.0,
                    output={"reason": "Dry run mode" if request.options.dry_run else "CRM creation disabled"}
                )

            # Calculate totals
            total_latency_ms = sum(
                s.latency_ms for s in stages.values() if s.latency_ms is not None
            )
            total_cost_usd = sum(
                s.cost_usd for s in stages.values() if s.cost_usd is not None
            )

            return PipelineTestResponse(
                success=True,
                total_latency_ms=total_latency_ms,
                total_cost_usd=total_cost_usd,
                lead_name=lead_name,
                stages=stages
            )

        except Exception as e:
            logger.exception(f"Pipeline execution failed for lead: {lead_name}")
            return self._build_error_response(
                lead_name,
                stages,
                "unknown",
                str(e)
            )

    async def _run_qualification(self, lead: Dict[str, Any]) -> PipelineStageResult:
        """Run qualification agent and track metrics"""
        start = time.time()
        try:
            result = await self.qualification_agent.qualify(lead)
            latency_ms = int((time.time() - start) * 1000)

            return PipelineStageResult(
                status="success",
                latency_ms=latency_ms,
                cost_usd=0.000006,  # Cerebras cost per request
                output=result
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error(f"Qualification failed: {e}")
            return PipelineStageResult(
                status="failed",
                latency_ms=latency_ms,
                cost_usd=0.0,
                error=str(e)
            )

    async def _run_enrichment(self, lead: Dict[str, Any]) -> PipelineStageResult:
        """Run enrichment agent and track metrics"""
        start = time.time()
        try:
            result = await self.enrichment_agent.enrich(lead)
            latency_ms = int((time.time() - start) * 1000)

            return PipelineStageResult(
                status="success",
                latency_ms=latency_ms,
                cost_usd=0.0001,  # Estimated Apollo/LinkedIn cost
                output=result
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error(f"Enrichment failed: {e}")
            return PipelineStageResult(
                status="failed",
                latency_ms=latency_ms,
                cost_usd=0.0,
                error=str(e)
            )

    async def _run_deduplication(self, lead: Dict[str, Any]) -> PipelineStageResult:
        """Run deduplication check and track metrics"""
        start = time.time()
        try:
            result = await self.deduplication_service.check_duplicate(lead)
            latency_ms = int((time.time() - start) * 1000)

            is_duplicate = result.get("is_duplicate", False)
            confidence = result.get("confidence", 0.0)

            return PipelineStageResult(
                status="duplicate" if is_duplicate else "no_duplicate",
                latency_ms=latency_ms,
                cost_usd=0.0,  # Deduplication is local/free
                confidence=confidence,
                output=result
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error(f"Deduplication failed: {e}")
            return PipelineStageResult(
                status="failed",
                latency_ms=latency_ms,
                cost_usd=0.0,
                error=str(e)
            )

    async def _run_close_crm(self, lead: Dict[str, Any]) -> PipelineStageResult:
        """Create lead in Close CRM and track metrics"""
        start = time.time()
        try:
            result = await self.close_service.create_lead(lead)
            latency_ms = int((time.time() - start) * 1000)

            return PipelineStageResult(
                status="created",
                latency_ms=latency_ms,
                cost_usd=0.0,  # CRM operations are free
                output=result
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error(f"Close CRM creation failed: {e}")
            return PipelineStageResult(
                status="failed",
                latency_ms=latency_ms,
                cost_usd=0.0,
                error=str(e)
            )

    def _build_error_response(
        self,
        lead_name: str,
        stages: Dict[str, PipelineStageResult],
        error_stage: str,
        error_message: str
    ) -> PipelineTestResponse:
        """Build error response with partial stage results"""
        total_latency_ms = sum(
            s.latency_ms for s in stages.values() if s.latency_ms is not None
        )
        total_cost_usd = sum(
            s.cost_usd for s in stages.values() if s.cost_usd is not None
        )

        return PipelineTestResponse(
            success=False,
            total_latency_ms=total_latency_ms,
            total_cost_usd=total_cost_usd,
            lead_name=lead_name,
            stages=stages,
            error_stage=error_stage,
            error_message=error_message
        )
