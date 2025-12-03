"""Apollo Free Tier Stage - Company enrichment (free)."""

import time
from typing import Any, Dict

from app.core.logging import setup_logging
from app.services.apollo_rate_limited import ApolloRateLimitedService
from .base import BaseStage, StageResult

logger = setup_logging(__name__)


class ApolloFreeStage(BaseStage):
    """
    Apollo Free Tier enrichment stage.

    Uses Apollo.io's free company enrichment endpoint to:
    - Verify company exists
    - Get basic company data (employee count, industry, etc.)
    - Get company phone/address
    - Get free contact data (names/titles without emails)

    Cost: $0 (free tier API calls)
    Latency: ~500-1000ms per company
    """

    name: str = "apollo_free"
    cost_per_call: float = 0.0  # Free tier

    def __init__(self):
        """Initialize Apollo free stage."""
        self._apollo = ApolloRateLimitedService()
        logger.info("ApolloFreeStage initialized")

    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute Apollo free tier enrichment.

        Args:
            company: Company data from Supabase with domain field

        Returns:
            StageResult with company data and free contact names/titles
        """
        start_time = time.time()
        domain = company.get("domain")

        if not domain:
            return StageResult(
                success=False,
                data={},
                error="No domain provided",
                latency_ms=0
            )

        try:
            # Enrich company using free endpoint
            company_data = await self._apollo.enrich_company_safe(domain=domain)

            # Search for company contacts (free search, no email reveals)
            contacts_data = await self._apollo.search_company_contacts_safe(
                domain=domain,
                job_titles=[
                    "CEO", "President", "Owner", "Founder", "VP", "Director",
                    "Chief", "CFO", "COO", "CTO", "CMO"
                ],
                max_results=25
            )

            latency_ms = int((time.time() - start_time) * 1000)

            return StageResult(
                success=True,
                data={
                    "company": company_data,
                    "contacts": contacts_data,
                    "contact_count": len(contacts_data),
                },
                cost_usd=0.0,
                latency_ms=latency_ms
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Apollo free enrichment failed for {domain}: {e}")

            return StageResult(
                success=False,
                data={},
                error=str(e),
                latency_ms=latency_ms
            )

    async def close(self):
        """Close Apollo service connections."""
        await self._apollo.close()
