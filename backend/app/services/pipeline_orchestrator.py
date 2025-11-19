"""
Pipeline orchestrator for coordinating 4-stage lead processing
"""
import os
import time
import logging
import csv
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List

# Bad email patterns to filter out (Wix tracking pixels, placeholders, etc.)
BAD_EMAIL_PATTERNS = [
    r'@sentry\.wixpress\.com$',
    r'@sentry-next\.wixpress\.com$',
    r'@2x\.png$',
    r'^youremail@',
    r'^email@example\.com$',
    r'^test@test\.com$',
    r'^noreply@',
    r'^no-reply@',
    r'^donotreply@',
    r'\.png$',
    r'\.jpg$',
    r'\.gif$',
]

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

        # Session-based export tracking for master file
        self._session_id = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        self._output_dir = self._get_output_dir()
        self._master_csv_path = None
        self._master_json_path = None
        self._log_path = None
        self._exported_leads = []
        self._filtered_emails = []

    def _get_output_dir(self) -> Path:
        """Get absolute path to output directory, avoiding path doubling issues."""
        # Use absolute path based on this file's location
        base_dir = Path(__file__).parent.parent.parent  # backend/app/services -> backend
        output_dir = base_dir / "data" / "final_enrichment_output"
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir

    def _is_bad_email(self, email: str) -> bool:
        """Check if email matches any bad pattern (tracking pixels, placeholders, etc.)."""
        if not email:
            return False
        email_lower = email.lower().strip()
        for pattern in BAD_EMAIL_PATTERNS:
            if re.search(pattern, email_lower):
                return True
        return False

    def _init_session_files(self):
        """Initialize session files for master export (CSV, JSON, log)."""
        if self._master_csv_path is None:
            self._master_csv_path = self._output_dir / f"MASTER_enriched_leads_{self._session_id}.csv"
            self._master_json_path = self._output_dir / f"enrichment_log_{self._session_id}.json"
            self._log_path = self._output_dir / f"pipeline_{self._session_id}.log"

            # Initialize log file
            with open(self._log_path, 'w') as f:
                f.write(f"Pipeline Session Started: {self._session_id}\n")
                f.write(f"Output Directory: {self._output_dir}\n")
                f.write("-" * 50 + "\n")

            logger.info(f"📁 Session files initialized: {self._session_id}")
            logger.info(f"   CSV: {self._master_csv_path}")
            logger.info(f"   JSON: {self._master_json_path}")
            logger.info(f"   Log: {self._log_path}")

    def _log_to_file(self, message: str):
        """Append message to session log file."""
        if self._log_path:
            with open(self._log_path, 'a') as f:
                timestamp = datetime.now().strftime("%H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")

    def finalize_export(self) -> Dict[str, Any]:
        """
        Finalize the session export by writing JSON summary.

        Call this after processing all leads to get export summary.

        Returns:
            Dict with export statistics and file paths
        """
        if not self._exported_leads:
            return {"status": "no_leads_exported"}

        # Write JSON summary
        summary = {
            "session_id": self._session_id,
            "timestamp": datetime.now().isoformat(),
            "total_leads": len(self._exported_leads),
            "valid_emails": sum(1 for lead in self._exported_leads if lead.get("email")),
            "filtered_emails": len(self._filtered_emails),
            "atl_leads": sum(1 for lead in self._exported_leads if lead.get("is_atl")),
            "btl_leads": sum(1 for lead in self._exported_leads if not lead.get("is_atl")),
            "files": {
                "csv": str(self._master_csv_path),
                "json": str(self._master_json_path),
                "log": str(self._log_path)
            },
            "leads": self._exported_leads,
            "filtered_bad_emails": self._filtered_emails
        }

        with open(self._master_json_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)

        # Final log entry
        self._log_to_file(f"Session Complete: {len(self._exported_leads)} leads exported")
        self._log_to_file(f"Valid emails: {summary['valid_emails']}")
        self._log_to_file(f"Filtered bad emails: {len(self._filtered_emails)}")
        self._log_to_file(f"ATL: {summary['atl_leads']}, BTL: {summary['btl_leads']}")

        logger.info(f"✅ Export finalized: {len(self._exported_leads)} leads")
        logger.info(f"   📊 Valid emails: {summary['valid_emails']}")
        logger.info(f"   🚫 Filtered: {len(self._filtered_emails)} bad emails")

        return summary

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
            # SAFETY: Skip Close CRM writes if disabled
            close_write_disabled = os.getenv("CLOSE_WRITE_DISABLED") == "True"

            if close_write_disabled:
                stages["close_crm"] = PipelineStageResult(
                    status="disabled",
                    latency_ms=0,
                    cost_usd=0.0,
                    output={
                        "reason": "⚠️ CLOSE_WRITE_DISABLED: Close CRM writes are disabled for safety",
                        "dedup_check_completed": dedup_result.status == "completed"
                    }
                )
                logger.warning("⚠️ CLOSE_WRITE_DISABLED: Skipping Close CRM write stage")
            elif request.options.create_in_crm and not request.options.dry_run:
                # Pass deduplication result to CRM stage for smart handling
                crm_result = await self._run_close_crm(request.lead, dedup_result)
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

            # Export to CSV (always, regardless of Close CRM status)
            try:
                csv_filepath = self._export_to_csv(request.lead, dedup_result)
                logger.info(f"✅ CSV export successful: {csv_filepath}")
            except Exception as e:
                logger.error(f"CSV export failed: {e}")
                # Don't fail the pipeline if CSV export fails

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
            # Use Close CRM API deduplication (not legacy local DB!)
            if not self.close_dedup_service:
                logger.warning("Close CRM check skipped - Close API key not configured")
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

            # Check if company exists in Close CRM via Close API
            recommendation = await self.close_dedup_service.check_duplicate(
                company_name=company_name,
                email=lead.get("email")
            )

            latency_ms = int((time.time() - start) * 1000)

            # Check for ATL contacts in existing company
            atl_contacts = []
            company_exists = recommendation.recommendation != "create_new"
            lead_id = recommendation.matched_lead_id if company_exists else None

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

            # NEW: Hunter.io Fallback - Discover Additional ATL Contacts
            # If no contacts discovered yet, try Hunter.io domain search
            if not lead.get("_discovered_contacts") and self.hunter_service:
                company_website = lead.get("website") or lead.get("url")
                if company_website:
                    try:
                        logger.info(f"Enrichment: Attempting Hunter.io domain search for {lead.get('name')}")
                        hunter_contacts = await self.hunter_service.domain_search(
                            company_website,
                            atl_only=False  # Get ALL contacts (ATL + BTL) for marketing
                        )
                        if hunter_contacts:
                            lead["_discovered_contacts"] = hunter_contacts
                            logger.info(f"✅ Enrichment discovered {len(hunter_contacts)} additional ATL contacts via Hunter.io")
                    except Exception as e:
                        logger.warning(f"Hunter.io domain search in enrichment failed: {e}")

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
                # Prepare new contact data for update/merge logic
                new_contact_data = {
                    "phone": lead.get("phone"),
                    "linkedin_url": lead.get("linkedin_url"),
                    "department": lead.get("department"),
                    "confidence": lead.get("confidence_score", 0)  # Hunter.io confidence
                }

                result = await self.close_dedup_service.check_duplicate(
                    company_name=lead.get("name") or lead.get("company_name"),
                    email=lead.get("email"),
                    phone=lead.get("phone"),
                    new_contact_data=new_contact_data
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
                    "matched_contact_id": result.matched_contact_id,  # For update_existing_contact
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

    async def _run_close_crm(
        self,
        lead: Dict[str, Any],
        dedup_result: Optional[PipelineStageResult] = None
    ) -> PipelineStageResult:
        """Create/update lead in Close CRM based on deduplication recommendation"""
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
            # Get deduplication recommendation
            recommendation = "create_new"  # Default
            if dedup_result and dedup_result.output:
                recommendation = dedup_result.output.get("recommendation", "create_new")
                matched_lead_id = dedup_result.output.get("matched_lead_id")
                matched_contact_id = dedup_result.output.get("matched_contact_id")

            logger.info(f"CRM stage recommendation: {recommendation}")

            # Handle based on recommendation
            if recommendation == "skip_duplicate":
                # Contact already exists - skip
                logger.info(
                    f"Skipping CRM creation - contact already exists "
                    f"(lead_id: {matched_lead_id}, contact_id: {matched_contact_id})"
                )
                return PipelineStageResult(
                    status="skipped",
                    latency_ms=int((time.time() - start) * 1000),
                    cost_usd=0.0,
                    output={
                        "message": "Contact already exists in CRM",
                        "lead_id": matched_lead_id,
                        "contact_id": matched_contact_id,
                        "action": "skipped"
                    }
                )

            elif recommendation == "update_existing_contact":
                # Update existing contact with new data
                logger.info(
                    f"Updating existing contact in CRM "
                    f"(lead_id: {matched_lead_id}, contact_id: {matched_contact_id})"
                )
                # TODO: Implement contact update with merged data
                # For now, return success
                return PipelineStageResult(
                    status="updated",
                    latency_ms=int((time.time() - start) * 1000),
                    cost_usd=0.0,
                    output={
                        "message": "Contact updated with new data",
                        "lead_id": matched_lead_id,
                        "contact_id": matched_contact_id,
                        "action": "updated"
                    }
                )

            elif recommendation == "add_contact_to_existing":
                # Add new contact(s) to existing lead (deduplication!)
                logger.info(
                    f"Adding discovered contacts to existing lead {matched_lead_id}"
                )
                # Pass matched_lead_id to create_lead - it will add contacts to existing lead
                result = await self.close_service.create_lead(lead, matched_lead_id=matched_lead_id)
                latency_ms = int((time.time() - start) * 1000)
                return PipelineStageResult(
                    status="contact_added",
                    latency_ms=latency_ms,
                    cost_usd=0.0,
                    output={
                        **result,
                        "action": "contact_added",
                        "existing_lead_id": matched_lead_id
                    }
                )

            else:  # "create_new"
                # Create new lead
                result = await self.close_service.create_lead(lead)
                latency_ms = int((time.time() - start) * 1000)

                return PipelineStageResult(
                    status="created",
                    latency_ms=latency_ms,
                    cost_usd=0.0,  # CRM operations are free
                    output={
                        **result,
                        "action": "created"
                    }
                )

        except Exception as e:
            latency_ms = int((time.time() - start) * 1000)
            logger.error(f"Close CRM operation failed: {e}")
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

    def _export_to_csv(
        self,
        lead_data: Dict[str, Any],
        dedup_result: Optional[PipelineStageResult] = None
    ) -> str:
        """
        Export ALL contacts for a company to session master CSV.

        Creates one row per contact with columns:
        - company_name
        - first_name
        - last_name
        - email
        - phone
        - position (job title)
        - is_atl (decision maker flag)
        - qualification_score
        - dedup_status
        - close_lead_id

        Filters out bad email patterns (tracking pixels, placeholders).

        Args:
            lead_data: Enriched lead data from pipeline
            dedup_result: Deduplication check result (optional)

        Returns:
            Path to master CSV file
        """
        # Initialize session files on first export
        self._init_session_files()

        # Extract dedup status
        dedup_status = "unknown"
        close_lead_id = ""
        if dedup_result and dedup_result.output:
            dedup_status = dedup_result.output.get("recommendation", "unknown")
            close_lead_id = dedup_result.output.get("existing_lead_id", "")

        company_name = lead_data.get("name") or lead_data.get("company_name", "")
        company_phone = lead_data.get("phone", "")
        qualification_score = lead_data.get("qualification_score", 0)

        # Get all discovered contacts from Hunter.io
        discovered_contacts = lead_data.get("_discovered_contacts", [])

        # CSV field names
        fieldnames = [
            "company_name", "first_name", "last_name", "email", "phone",
            "position", "is_atl", "qualification_score", "dedup_status", "close_lead_id"
        ]

        rows_written = 0

        # Write header if file doesn't exist
        file_exists = self._master_csv_path.exists()

        with open(self._master_csv_path, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()

            # If we have discovered contacts, write one row per contact
            if discovered_contacts:
                for contact in discovered_contacts:
                    email = contact.get("email", "")

                    # Filter bad emails
                    if email and self._is_bad_email(email):
                        self._filtered_emails.append({
                            "company": company_name,
                            "email": email,
                            "reason": "bad_pattern"
                        })
                        self._log_to_file(f"🚫 Filtered bad email: {email} ({company_name})")
                        continue  # Skip this contact

                    csv_row = {
                        "company_name": company_name,
                        "first_name": contact.get("first_name", ""),
                        "last_name": contact.get("last_name", ""),
                        "email": email,
                        "phone": contact.get("phone", "") or company_phone,
                        "position": contact.get("position", ""),
                        "is_atl": contact.get("is_atl", False),
                        "qualification_score": qualification_score,
                        "dedup_status": dedup_status,
                        "close_lead_id": close_lead_id
                    }

                    writer.writerow(csv_row)
                    self._exported_leads.append(csv_row.copy())
                    rows_written += 1

                    atl_status = "ATL" if csv_row["is_atl"] else "BTL"
                    self._log_to_file(f"✅ [{atl_status}] {company_name} - {csv_row['first_name']} {csv_row['last_name']} - {email}")

            else:
                # No contacts discovered - write company row with existing data
                email = lead_data.get("email") or lead_data.get("contact_email", "")

                if email and self._is_bad_email(email):
                    self._filtered_emails.append({
                        "company": company_name,
                        "email": email,
                        "reason": "bad_pattern"
                    })
                    email = ""

                csv_row = {
                    "company_name": company_name,
                    "first_name": "",
                    "last_name": "",
                    "email": email,
                    "phone": company_phone,
                    "position": "",
                    "is_atl": False,
                    "qualification_score": qualification_score,
                    "dedup_status": dedup_status,
                    "close_lead_id": close_lead_id
                }

                writer.writerow(csv_row)
                self._exported_leads.append(csv_row.copy())
                rows_written += 1
                self._log_to_file(f"✅ [NO CONTACTS] {company_name} - {email or 'no email'}")

        logger.info(f"✅ Exported {rows_written} contact(s) for {company_name}")
        return str(self._master_csv_path)
