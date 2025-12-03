"""Supervised Orchestrator - Asyncio-based Enrichment Pipeline."""

import asyncio
import logging
from typing import Dict, List, Any

from .stages.apollo_free import ApolloFreeStage
from .stages.linkedin import LinkedInStage
from .stages.hunter import HunterStage
from .stages.apollo_paid import ApolloPaidStage
from .stages.base import StageResult, BaseStage
from .state_manager import StateManager
from .budget_tracker import BudgetTracker

logger = logging.getLogger(__name__)


class SupervisedOrchestrator:
    """Orchestrates enrichment pipeline with manual checkpoints."""

    def __init__(
        self,
        state_manager: StateManager,
        budget_tracker: BudgetTracker,
    ):
        """Initialize orchestrator with dependencies.

        Args:
            state_manager: StateManager instance for tracking enrichment state
            budget_tracker: BudgetTracker instance for cost control
        """
        self.state_manager = state_manager
        self.budget_tracker = budget_tracker

        # Initialize pipeline stages
        self.stages: List[BaseStage] = [
            ApolloFreeStage(),
            LinkedInStage(),
            HunterStage(),
            ApolloPaidStage(),
        ]

        logger.info(f"Initialized SupervisedOrchestrator with {len(self.stages)} stages")

    async def enrich_company(self, company: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a single company through all stages sequentially.

        Args:
            company: Company data dict with id, name, domain

        Returns:
            Result dict with success status, merged data, costs, and metrics
        """
        company_id = company.get("id", "unknown")
        company_name = company.get("name", "Unknown")

        logger.info(f"Starting enrichment for {company_name} (ID: {company_id})")

        # Initialize company in state manager
        await self.state_manager.init_company(company_id)

        # Track aggregated metrics
        total_cost_usd = 0.0
        total_latency_ms = 0
        stages_completed = 0
        merged_contacts = []
        merged_data = {}
        budget_exceeded = False
        any_stage_failed = False

        try:
            for stage in self.stages:
                stage_name = stage.name

                # Check budget before each stage
                if not await self.budget_tracker.can_proceed():
                    logger.warning(f"Budget exceeded before {stage_name} for {company_name}")
                    budget_exceeded = True
                    break

                # Update stage status to running
                await self.state_manager.update_stage_status(
                    company_id=company_id,
                    stage=stage_name,
                    status="running",
                    cost_usd=0.0,
                )

                logger.info(f"Executing {stage_name} for {company_name}")

                # Execute stage
                try:
                    result: StageResult = await stage.execute(company)

                    # Track costs and metrics
                    total_cost_usd += result.cost_usd
                    total_latency_ms += result.latency_ms

                    # Add cost to budget tracker
                    await self.budget_tracker.add_cost(result.cost_usd)

                    if result.success:
                        stages_completed += 1

                        # Merge contacts (deduplicate by name)
                        if "contacts" in result.data:
                            new_contacts = result.data["contacts"]
                            existing_names = {c.get("name", "").lower() for c in merged_contacts}
                            for contact in new_contacts:
                                contact_name = contact.get("name", "").lower()
                                if contact_name and contact_name not in existing_names:
                                    merged_contacts.append(contact)
                                    existing_names.add(contact_name)

                        # Merge other data
                        for key, value in result.data.items():
                            if key != "contacts" and value is not None:
                                merged_data[key] = value

                        # Update stage status to success
                        await self.state_manager.update_stage_status(
                            company_id=company_id,
                            stage=stage_name,
                            status="success",
                            cost_usd=result.cost_usd,
                        )

                        logger.info(
                            f"{stage_name} succeeded for {company_name}: "
                            f"{len(result.data.get('contacts', []))} contacts, "
                            f"${result.cost_usd:.4f}, {result.latency_ms}ms"
                        )
                    else:
                        # Stage failed but continue pipeline
                        any_stage_failed = True
                        logger.warning(f"{stage_name} failed for {company_name}: {result.error}")
                        await self.state_manager.update_stage_status(
                            company_id=company_id,
                            stage=stage_name,
                            status="failed",
                            cost_usd=result.cost_usd,
                        )

                except Exception as e:
                    any_stage_failed = True
                    logger.error(f"Exception in {stage_name} for {company_name}: {e}", exc_info=True)
                    await self.state_manager.update_stage_status(
                        company_id=company_id,
                        stage=stage_name,
                        status="failed",
                        cost_usd=0.0,
                    )

            # Mark company as complete (or partial if budget exceeded)
            if budget_exceeded:
                logger.warning(f"Enrichment incomplete for {company_name} due to budget")
            else:
                await self.state_manager.mark_complete(company_id)
                await self.budget_tracker.increment_processed()
                logger.info(f"Enrichment complete for {company_name}: {stages_completed}/{len(self.stages)} stages")

            # Determine overall success: all stages completed without budget issues or failures
            overall_success = not budget_exceeded and not any_stage_failed and stages_completed > 0

            return {
                "success": overall_success,
                "company_id": company_id,
                "company_name": company_name,
                "stages_completed": stages_completed,
                "total_stages": len(self.stages),
                "total_cost_usd": total_cost_usd,
                "total_latency_ms": total_latency_ms,
                "contacts": merged_contacts,
                "data": merged_data,
                "budget_exceeded": budget_exceeded,
            }

        except Exception as e:
            logger.error(f"Critical error enriching {company_name}: {e}", exc_info=True)
            await self.state_manager.mark_failed(company_id, str(e))
            return {
                "success": False,
                "company_id": company_id,
                "company_name": company_name,
                "error": str(e),
                "stages_completed": stages_completed,
                "total_cost_usd": total_cost_usd,
                "total_latency_ms": total_latency_ms,
            }

    async def process_batch(self, companies: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process multiple companies in parallel.

        Args:
            companies: List of company dicts to enrich

        Returns:
            List of enrichment results (one per company)
        """
        logger.info(f"Starting batch enrichment for {len(companies)} companies")

        # Run enrich_company in parallel using asyncio.gather
        tasks = [self.enrich_company(company) for company in companies]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to error results
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                company = companies[i]
                logger.error(f"Batch processing exception for {company.get('name', 'unknown')}: {result}")
                processed_results.append({
                    "success": False,
                    "company_id": company.get("id", "unknown"),
                    "company_name": company.get("name", "Unknown"),
                    "error": str(result),
                    "stages_completed": 0,
                    "total_cost_usd": 0.0,
                    "total_latency_ms": 0,
                })
            else:
                processed_results.append(result)

        successful = sum(1 for r in processed_results if r["success"])
        total_cost = sum(r.get("total_cost_usd", 0.0) for r in processed_results)

        logger.info(
            f"Batch enrichment complete: {successful}/{len(companies)} successful, "
            f"total cost ${total_cost:.4f}"
        )

        return processed_results
