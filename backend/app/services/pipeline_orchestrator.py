"""
Pipeline orchestrator for coordinating 4-stage lead processing
"""
import os
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
    global QualificationAgent, EnrichmentAgent, DeduplicationService, CloseService, CloseDeduplicationService

    if QualificationAgent is None:
        from app.services.langgraph.agents.qualification_agent import QualificationAgent as QA
        from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent as EA
        from app.services.crm.deduplication import DeduplicationEngine as DS
        from app.services.crm.close import CloseProvider as CS
        from app.services.crm.close_deduplication import CloseDeduplicationService as CDS

        QualificationAgent = QA
        EnrichmentAgent = EA
        DeduplicationService = DS
        CloseService = CS
        CloseDeduplicationService = CDS

QualificationAgent = None
EnrichmentAgent = None
DeduplicationService = None
CloseService = None
CloseDeduplicationService = None

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

        # Close CRM deduplication (checks Close API, not local database)
        close_api_key = os.getenv("CLOSE_API_KEY")
        if close_api_key:
            self.close_dedup_service = CloseDeduplicationService(api_key=close_api_key)
            logger.info("Close CRM deduplication enabled")
        else:
            self.close_dedup_service = None
            logger.warning("Close CRM deduplication disabled (no CLOSE_API_KEY)")

        # Legacy local database deduplication (fallback)
        if db:
            self.deduplication_service = DeduplicationService(db=db)
        else:
            self.deduplication_service = None

        # Initialize Close CRM service for lead creation
        if close_api_key:
            self.close_service = CloseService(api_key=close_api_key)
            logger.info("Close CRM service enabled")
        else:
            self.close_service = None
            logger.warning("Close CRM service disabled (no CLOSE_API_KEY)")

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

            # Extract email and discovered contacts from qualification metadata
            if qual_result.output and "metadata" in qual_result.output:
                metadata = qual_result.output["metadata"]
                extracted_email = metadata.get("extracted_email")
                discovered_contacts = metadata.get("discovered_contacts", [])

                if extracted_email and not request.lead.get("email"):
                    request.lead["email"] = extracted_email
                    logger.info(f"Using extracted email from qualification: {extracted_email}")

                # Store discovered contacts for later use
                if discovered_contacts:
                    request.lead["_discovered_contacts"] = discovered_contacts
                    logger.info(f"Qualification discovered {len(discovered_contacts)} ATL contacts via Hunter.io")

            # Stage 2: Close CRM Check (check for existing company + ATL contacts)
            crm_check_result = await self._check_close_crm_for_atl(request.lead)
            stages["crm_check"] = crm_check_result

            # Stage 3: Enrichment (only if no ATL contacts found in CRM)
            should_enrich = True
            if crm_check_result.output:
                recommendation = crm_check_result.output.get("recommendation", "run_enrichment")
                should_enrich = recommendation == "run_enrichment"

                if crm_check_result.status == "found_atl":
                    logger.info(
                        f"Skipping enrichment for {lead_name} - "
                        f"{len(crm_check_result.output.get('atl_contacts', []))} ATL contacts already in Close CRM"
                    )

            if request.options.skip_enrichment or not should_enrich:
                reason = "User requested skip" if request.options.skip_enrichment else "ATL contacts already in CRM"
                stages["enrichment"] = PipelineStageResult(
                    status="skipped",
                    latency_ms=0,
                    cost_usd=0.0,
                    output={"reason": reason}
                )
            else:
                logger.info(f"Running enrichment for {lead_name} - no ATL contacts in CRM")
                enrich_result = await self._run_enrichment(request.lead)
                stages["enrichment"] = enrich_result

                if enrich_result.status == "failed":
                    # Don't fail the entire pipeline - continue to CRM creation
                    logger.warning(f"Enrichment failed for {lead_name}, continuing to CRM creation")

            # Stage 4: Deduplication (final check before CRM creation)
            dedup_result = await self._run_deduplication(request.lead)
            stages["deduplication"] = dedup_result

            if dedup_result.status == "failed":
                logger.warning(f"Deduplication failed for {lead_name}, continuing to CRM creation")

            # Handle duplicate detection (but don't fail - we already checked CRM)
            if dedup_result.status == "duplicate" or (
                dedup_result.output and dedup_result.output.get("is_duplicate")
            ):
                if request.options.stop_on_duplicate:
                    logger.info(
                        f"Duplicate detected for {lead_name} - "
                        f"will update existing lead instead of creating new"
                    )

            # Stage 5: Close CRM Create/Update (with all discovered contacts)
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
                contact_email=lead.get("email") or lead.get("contact_email"),
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
                            "sales_potential": getattr(qualification_result, 'sales_potential', None),
                            "metadata": metadata  # Include metadata for downstream use (extracted_email, etc.)
                        }
                    else:
                        # qualification_result is the score itself
                        output = {"qualification_score": float(qualification_result), "metadata": metadata}

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

    async def _check_close_crm_for_atl(self, lead: Dict[str, Any]) -> PipelineStageResult:
        """
        Check Close CRM for existing company and ATL contacts.

        Returns:
            PipelineStageResult with:
            - status: "found_atl" | "found_no_atl" | "not_found" | "failed"
            - output: {
                "company_exists": bool,
                "lead_id": str | None,
                "atl_contacts": List[Dict],
                "recommendation": "skip_enrichment" | "run_enrichment"
              }
        """
        start = time.time()
        try:
            if not self.deduplication_service:
                logger.warning("Close CRM check skipped - deduplication service not configured")
                return PipelineStageResult(
                    status="skipped",
                    latency_ms=0,
                    cost_usd=0.0,
                    output={"recommendation": "run_enrichment"}
                )

            company_name = lead.get("name") or lead.get("company")
            if not company_name:
                return PipelineStageResult(
                    status="failed",
                    latency_ms=0,
                    cost_usd=0.0,
                    error="Company name required for Close CRM check"
                )

            # Check if company exists in Close CRM
            recommendation = await self.deduplication_service.check_duplicate(
                company_name=company_name,
                contact_email=lead.get("email")
            )

            latency_ms = int((time.time() - start) * 1000)

            # Check for ATL contacts in existing company
            atl_contacts = []
            company_exists = recommendation.recommendation != "create_new"
            lead_id = recommendation.existing_lead_id if company_exists else None

            if company_exists and recommendation.existing_contacts:
                # ATL titles to look for
                ATL_KEYWORDS = ["ceo", "cto", "vp", "vice president", "director",
                                "founder", "co-founder", "owner", "president",
                                "head of", "manager", "partner", "principal"]

                for contact in recommendation.existing_contacts:
                    title = (contact.get("title") or "").lower()
                    if any(keyword in title for keyword in ATL_KEYWORDS):
                        atl_contacts.append(contact)

                logger.info(
                    f"Close CRM check for {company_name}: "
                    f"company_exists=True, atl_contacts={len(atl_contacts)}"
                )

                if atl_contacts:
                    # Company exists with ATL contacts - skip enrichment
                    return PipelineStageResult(
                        status="found_atl",
                        latency_ms=latency_ms,
                        cost_usd=0.0,
                        output={
                            "company_exists": True,
                            "lead_id": lead_id,
                            "atl_contacts": atl_contacts,
                            "recommendation": "skip_enrichment",
                            "message": f"Found {len(atl_contacts)} ATL contacts in Close CRM"
                        }
                    )
                else:
                    # Company exists but no ATL contacts - run enrichment
                    return PipelineStageResult(
                        status="found_no_atl",
                        latency_ms=latency_ms,
                        cost_usd=0.0,
                        output={
                            "company_exists": True,
                            "lead_id": lead_id,
                            "atl_contacts": [],
                            "recommendation": "run_enrichment",
                            "message": "Company exists but no ATL contacts found - enrichment needed"
                        }
                    )
            else:
                # Company doesn't exist - run enrichment
                logger.info(f"Close CRM check for {company_name}: company_exists=False")
                return PipelineStageResult(
                    status="not_found",
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    output={
                        "company_exists": False,
                        "lead_id": None,
                        "atl_contacts": [],
                        "recommendation": "run_enrichment",
                        "message": "Company not in Close CRM - enrichment needed"
                    }
                )

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error(f"Close CRM check failed: {e}")
            return PipelineStageResult(
                status="failed",
                latency_ms=latency_ms,
                cost_usd=0.0,
                error=str(e),
                output={"recommendation": "run_enrichment"}  # Default to enrichment on error
            )

    async def _run_enrichment(self, lead: Dict[str, Any]) -> PipelineStageResult:
        """Run enrichment agent and track metrics"""
        start = time.time()
        try:
            # Check if we have any identifiers for enrichment
            has_email = bool(lead.get("email"))
            has_linkedin = bool(lead.get("linkedin_url"))
            has_lead_id = bool(lead.get("id"))

            if not (has_email or has_linkedin or has_lead_id):
                # Company-only lead (no people identified yet)
                # Skip enrichment for now - company will still be created in Close CRM
                # Future: Add Hunter.io domain search here to discover people
                logger.info(
                    f"Skipping enrichment for {lead.get('name')} - no contact identifiers. "
                    f"Company will be created in Close CRM for future enrichment."
                )
                return PipelineStageResult(
                    status="skipped",
                    latency_ms=0,
                    cost_usd=0.0,
                    output={"reason": "company_only_lead", "message": "No contact identifiers - skipping enrichment"}
                )

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
        """Run deduplication check against Close CRM API and track metrics"""
        start = time.time()

        # Use Close CRM API deduplication (preferred)
        if self.close_dedup_service:
            try:
                result = await self.close_dedup_service.check_duplicate(
                    company_name=lead.get("name") or lead.get("company_name"),
                    email=lead.get("email"),
                    phone=lead.get("phone")
                )
                latency_ms = int((time.time() - start) * 1000)

                # Convert DuplicationCheckResult to dict
                output = {
                    "is_duplicate": result.is_duplicate,
                    "company_match_found": result.company_match_found,
                    "company_confidence": result.company_confidence,
                    "contact_match_found": result.contact_match_found,
                    "contact_confidence": result.contact_confidence,
                    "matched_lead_id": result.matched_lead_id,
                    "matched_company_name": result.matched_company_name,
                    "recommendation": result.recommendation,
                    "source": "close_crm_api"
                }

                # Set status based on duplicate detection
                status = "duplicate" if result.is_duplicate else "success"

                logger.info(
                    f"Close CRM deduplication: {status}, "
                    f"company_match={result.company_match_found} ({result.company_confidence:.1f}%), "
                    f"contact_match={result.contact_match_found}"
                )

                return PipelineStageResult(
                    status=status,
                    latency_ms=latency_ms,
                    cost_usd=0.0,  # Close API calls are free for deduplication
                    output=output,
                    confidence=result.company_confidence if result.company_match_found else 0.0
                )

            except Exception as e:
                latency_ms = int((time.time() - start) * 1000)
                logger.error(f"Close CRM deduplication failed: {e}")
                # Fall through to local deduplication as fallback

        # Fallback: Local database deduplication (legacy)
        if not self.deduplication_service:
            return PipelineStageResult(
                status="skipped",
                latency_ms=0,
                cost_usd=0.0,
                output={"is_duplicate": False, "reason": "No deduplication service available"}
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
                "match_count": len(result.matches),
                "source": "local_database"
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
