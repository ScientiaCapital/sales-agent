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
        from app.services.crm.deduplication import DeduplicationEngine as DS
        from app.services.crm.close import CloseProvider as CS

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

    def __init__(self, db=None):
        """Initialize orchestrator with all required services

        Args:
            db: SQLAlchemy database session for CRM services
        """
        _lazy_import_agents()  # Import agents only when needed
        self.qualification_agent = QualificationAgent()
        self.enrichment_agent = EnrichmentAgent()

        # Only create CRM services if database session is provided
        if db:
            self.deduplication_service = DeduplicationService(db=db)
            # TODO: Close service requires credentials - skip for testing
            self.close_service = None
        else:
            self.deduplication_service = None
            self.close_service = None

        self.db = db

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
            # Map lead dict fields to agent parameters
            result = await self.qualification_agent.qualify(
                company_name=lead.get("name") or lead.get("company_name"),
                company_website=lead.get("website"),
                company_size=lead.get("company_size"),
                industry=lead.get("industry"),
                contact_name=lead.get("contact_name"),
                contact_title=lead.get("contact_title"),
                notes=lead.get("notes")
            )

            # DEBUG: Log the raw return value
            logger.info(f"DEBUG: qualify() result type: {type(result)}")
            logger.info(f"DEBUG: qualify() result value: {result}")
            logger.info(f"DEBUG: is tuple: {isinstance(result, tuple)}")
            if isinstance(result, tuple):
                logger.info(f"DEBUG: tuple length: {len(result)}")
                for i, item in enumerate(result):
                    logger.info(f"DEBUG: result[{i}] type: {type(item)}, value: {item}")

            # Handle different return formats
            if isinstance(result, tuple):
                if len(result) == 3:
                    # Format: (LeadQualificationResult, latency_ms, metadata)
                    qualification_result, agent_latency_ms, metadata = result

                    # Extract score - could be object or float
                    if hasattr(qualification_result, 'qualification_score'):
                        output = {
                            "qualification_score": qualification_result.qualification_score,
                            "tier": getattr(qualification_result, 'tier', None),
                            "qualification_reasoning": getattr(qualification_result, 'qualification_reasoning', None),
                            "fit_assessment": getattr(qualification_result, 'fit_assessment', None),
                            "contact_quality": getattr(qualification_result, 'contact_quality', None),
                            "sales_potential": getattr(qualification_result, 'sales_potential', None)
                        }
                    else:
                        # qualification_result is the score itself
                        output = {"qualification_score": float(qualification_result)}

                    # Extract cost - could be dict or float
                    if isinstance(metadata, dict):
                        cost = metadata.get("estimated_cost_usd", 0.000006)
                    else:
                        cost = float(metadata) if isinstance(metadata, (int, float)) else 0.000006
                else:
                    # Unknown tuple format
                    agent_latency_ms = int((time.time() - start) * 1000)
                    output = {"result": str(result)}
                    cost = 0.000006
            else:
                # Unknown format - return as-is
                agent_latency_ms = int((time.time() - start) * 1000)
                output = {"result": str(result)}
                cost = 0.000006

            return PipelineStageResult(
                status="success",
                latency_ms=agent_latency_ms,
                cost_usd=cost,
                output=output
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
            # Map lead dict fields to agent parameters
            result = await self.enrichment_agent.enrich(
                email=lead.get("email"),
                linkedin_url=lead.get("linkedin_url"),
                lead_id=lead.get("id")
            )
            latency_ms = int((time.time() - start) * 1000)

            # Convert result to dict if it's a Pydantic model
            if hasattr(result, 'model_dump'):
                output = result.model_dump()
            elif isinstance(result, dict):
                output = result
            else:
                # Fallback: convert to string representation
                output = {"result": str(result)}

            return PipelineStageResult(
                status="success",
                latency_ms=latency_ms,
                cost_usd=0.0001,  # Estimated Apollo/LinkedIn cost
                output=output
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

        # Skip if no database session (testing mode)
        if not self.deduplication_service:
            return PipelineStageResult(
                status="skipped",
                latency_ms=0,
                cost_usd=0.0,
                output={"is_duplicate": False, "reason": "No database session available"}
            )

        try:
            result = await self.deduplication_service.find_duplicates(
                email=lead.get("email"),
                company=lead.get("name") or lead.get("company_name"),
                linkedin_url=lead.get("linkedin_url"),
                phone=lead.get("phone"),
                company_website=lead.get("website")
            )
            latency_ms = int((time.time() - start) * 1000)

            # Convert DeduplicationResult dataclass to dict
            output = {
                "is_duplicate": result.is_duplicate,
                "confidence": result.confidence,
                "threshold": result.threshold,
                "checked_fields": result.checked_fields,
                "match_count": len(result.matches)
            }

            return PipelineStageResult(
                status="duplicate" if result.is_duplicate else "no_duplicate",
                latency_ms=latency_ms,
                cost_usd=0.0,  # Deduplication is local/free
                confidence=result.confidence,
                output=output
            )
        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)

            # Check if CRM tables don't exist (testing environment)
            if "does not exist" in str(e).lower() or "relation" in str(e).lower():
                logger.warning(f"Deduplication skipped - CRM tables not available: {e}")
                # Rollback transaction to clear failed state
                if self.db:
                    self.db.rollback()
                return PipelineStageResult(
                    status="skipped",
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    output={"is_duplicate": False, "reason": "CRM tables not available"}
                )

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

        # Skip if no CRM service (testing mode)
        if not self.close_service:
            return PipelineStageResult(
                status="skipped",
                latency_ms=0,
                cost_usd=0.0,
                output={"message": "CRM service not available"}
            )

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
