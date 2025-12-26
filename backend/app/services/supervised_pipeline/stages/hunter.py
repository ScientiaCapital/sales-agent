"""Hunter.io Stage - Email discovery and verification."""

import time
from typing import Any, Dict

from app.core.logging import setup_logging
from app.services.hunter_service import HunterService
from .base import BaseStage, StageResult

logger = setup_logging(__name__)


class HunterStage(BaseStage):
    """
    Hunter.io enrichment stage.

    Uses Hunter.io to:
    - Discover emails for known contacts
    - Search for all emails at a domain
    - Verify email deliverability
    - Get confidence scores

    Cost: $0.01 per request (domain search or email finder)
    Latency: ~1-2 seconds per company
    """

    name: str = "hunter"
    cost_per_call: float = 0.01  # $0.01 per Hunter.io API call

    def __init__(self):
        """Initialize Hunter stage."""
        self._hunter = HunterService()
        logger.info("HunterStage initialized")

    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute Hunter.io enrichment.

        Uses a cost-optimized approach:
        1. First check email count (FREE endpoint) to see if Hunter.io has data
        2. Only make paid domain_search call if data exists

        Args:
            company: Company data from Supabase with domain

        Returns:
            StageResult with discovered emails and contact data
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
            # Step 1: Check email count (FREE endpoint) to gate paid calls
            email_count = await self._hunter.get_email_count(domain)

            if not email_count or not email_count.get("has_data"):
                latency_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    f"Hunter: No email data available for {domain} (skipping paid call)"
                )
                return StageResult(
                    success=True,
                    data={
                        "contacts": [],
                        "contact_count": 0,
                        "email_count_check": email_count,
                    },
                    cost_usd=0.0,  # FREE - no paid API call made
                    latency_ms=latency_ms
                )

            # Step 2: Perform domain search to find all emails at company
            contacts = await self._hunter.domain_search(
                domain=domain,
                limit=10,
                atl_only=True  # Only ATL contacts (decision makers)
            )

            latency_ms = int((time.time() - start_time) * 1000)

            if not contacts:
                return StageResult(
                    success=True,
                    data={
                        "contacts": [],
                        "contact_count": 0,
                    },
                    cost_usd=self.cost_per_call,
                    latency_ms=latency_ms
                )

            return StageResult(
                success=True,
                data={
                    "contacts": contacts,
                    "contact_count": len(contacts),
                },
                cost_usd=self.cost_per_call,
                latency_ms=latency_ms
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Hunter enrichment failed for {domain}: {e}")

            return StageResult(
                success=False,
                data={},
                error=str(e),
                latency_ms=latency_ms
            )
