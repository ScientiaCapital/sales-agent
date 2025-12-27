"""Pipeline orchestrator for coordinating 6-stage lead processing."""
import os
import logging
from typing import Dict, Any

from app.schemas.pipeline import (
    PipelineTestRequest,
    PipelineTestResponse,
    PipelineStageResult
)
from app.services.lead_audit_service import LeadAuditService

from .stages import (
    run_qualification, check_close_crm_for_atl, run_enrichment,
    run_marketing, run_staging, run_deduplication, run_close_crm,
    run_cold_reach_enrollment,
)
from .export import export_to_csv, SessionManager
from .audit import log_audit
from ._imports import get_agents

logger = logging.getLogger(__name__)


class PipelineOrchestrator:
    """Orchestrates 6-stage GTM lead processing pipeline."""

    def __init__(self, db=None):
        agents = get_agents()
        self.qualification_agent = agents["QualificationAgent"]()
        self.enrichment_agent = agents["EnrichmentAgent"](
            provider="openrouter", model="deepseek/deepseek-chat"
        )
        self.marketing_agent = agents["MarketingAgent"]()

        close_api_key = os.getenv("CLOSE_API_KEY")
        self.close_dedup_service = agents["CloseDeduplicationService"](
            api_key=close_api_key) if close_api_key else None
        self.close_service = agents["CloseService"](
            api_key=close_api_key) if close_api_key else None
        self.deduplication_service = agents["DeduplicationService"](db=db) if db else None

        cold_reach_url = os.getenv("COLD_REACH_API_URL", "http://localhost:8002")
        self.cold_reach_client = agents["ColdReachClient"](
            base_url=cold_reach_url,
            api_key=os.getenv("COLD_REACH_API_KEY", ""),
        ) if cold_reach_url else None

        self.db = db
        self._session = SessionManager()
        self._audit_service = LeadAuditService(db) if db else None

    async def _log_audit(self, **kwargs) -> None:
        await log_audit(self._audit_service, self._session.session_id, **kwargs)

    def finalize_export(self) -> Dict[str, Any]:
        return self._session.finalize_export()

    async def execute(self, request: PipelineTestRequest) -> PipelineTestResponse:
        lead_name = request.lead.get("name") or request.lead.get("company") or "Unknown"
        stages: Dict[str, PipelineStageResult] = {}

        try:
            # Stage 1: Qualification
            stages["qualification"] = await run_qualification(
                request.lead, self.qualification_agent, self._log_audit)
            if stages["qualification"].status == "failed":
                return self._error(lead_name, stages, "qualification", stages["qualification"].error)
            self._extract_qual_metadata(request, stages["qualification"])

            # Stage 2: CRM Check
            stages["crm_check"] = await check_close_crm_for_atl(
                request.lead, self.close_dedup_service, self._log_audit)

            # Stage 3: Enrichment
            if self._should_enrich(request, stages["crm_check"]):
                stages["enrichment"] = await run_enrichment(
                    request.lead, self.enrichment_agent, None, self._log_audit)
                self._merge_contacts(request, stages["enrichment"])
            else:
                stages["enrichment"] = PipelineStageResult(
                    status="skipped", latency_ms=0, cost_usd=0.0,
                    output={"reason": "ATL in CRM or skip requested"})

            # Stage 4: Marketing
            if request.lead.get("_discovered_contacts") and request.options.generate_marketing:
                stages["marketing"] = await run_marketing(request.lead, self.marketing_agent)
            else:
                stages["marketing"] = PipelineStageResult(
                    status="skipped", latency_ms=0, cost_usd=0.0,
                    output={"reason": "No contacts or disabled"})

            # Stage 4.5: Staging
            if request.options.stage_to_crm and request.lead.get("_marketing_content"):
                stages["staging"] = await run_staging(request.lead, self._log_audit)

            # Stage 5: Deduplication
            stages["deduplication"] = await run_deduplication(
                request.lead, self.close_dedup_service,
                self.deduplication_service, self.db, self._log_audit)

            # Stage 6: Close CRM
            stages["close_crm"] = await self._close_crm_stage(request, stages["deduplication"])

            # Stage 7: Cold Reach
            stages["cold_reach"] = await self._cold_reach_stage(request, stages)

            # Export
            try:
                export_to_csv(request.lead, self._session, stages["deduplication"])
            except Exception as e:
                logger.error(f"CSV export failed: {e}")

            return self._success(lead_name, stages)
        except Exception as e:
            logger.exception(f"Pipeline failed: {lead_name}")
            return self._error(lead_name, stages, "unknown", str(e))

    def _extract_qual_metadata(self, request, result):
        if result.output and "metadata" in result.output:
            meta = result.output["metadata"]
            if meta.get("extracted_email") and not request.lead.get("email"):
                request.lead["email"] = meta["extracted_email"]
            if meta.get("discovered_contacts"):
                request.lead["_discovered_contacts"] = meta["discovered_contacts"]

    def _should_enrich(self, request, crm_result) -> bool:
        if request.options.skip_enrichment:
            return False
        return crm_result.output.get("recommendation") == "run_enrichment" if crm_result.output else True

    def _merge_contacts(self, request, result):
        if result.output and result.status != "failed":
            contacts = result.output.get("atl_contacts", [])
            if contacts:
                existing = request.lead.get("_discovered_contacts", [])
                emails = {c.get("email") for c in existing if c.get("email")}
                new = [c for c in contacts if c.get("email") not in emails]
                request.lead["_discovered_contacts"] = existing + new if existing else contacts

    async def _close_crm_stage(self, request, dedup) -> PipelineStageResult:
        if os.getenv("CLOSE_WRITE_DISABLED") == "True":
            return PipelineStageResult(status="disabled", latency_ms=0, cost_usd=0.0,
                                       output={"reason": "CLOSE_WRITE_DISABLED"})
        if request.options.create_in_crm and not request.options.dry_run:
            return await run_close_crm(request.lead, self.close_service, dedup)
        return PipelineStageResult(status="skipped", latency_ms=0, cost_usd=0.0,
                                   output={"reason": "Dry run or disabled"})

    async def _cold_reach_stage(self, request, stages) -> PipelineStageResult:
        tier = (stages.get("qualification", PipelineStageResult(
            status="", latency_ms=0, cost_usd=0.0)).output or {}).get("tier") or "C"
        if tier in ["A", "B"] and not request.options.dry_run:
            return await run_cold_reach_enrollment(request.lead, tier, self.cold_reach_client)
        return PipelineStageResult(status="skipped", latency_ms=0, cost_usd=0.0,
                                   output={"reason": f"Tier {tier}", "tier": tier})

    def _success(self, name, stages) -> PipelineTestResponse:
        return PipelineTestResponse(
            success=True, lead_name=name, stages=stages,
            total_latency_ms=sum(s.latency_ms or 0 for s in stages.values()),
            total_cost_usd=sum(s.cost_usd or 0 for s in stages.values()))

    def _error(self, name, stages, stage, msg) -> PipelineTestResponse:
        return PipelineTestResponse(
            success=False, lead_name=name, stages=stages,
            error_stage=stage, error_message=msg,
            total_latency_ms=sum(s.latency_ms or 0 for s in stages.values()),
            total_cost_usd=sum(s.cost_usd or 0 for s in stages.values()))
