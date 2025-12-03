"""Apollo Paid Tier Stage - Email reveals and phone numbers."""

import time
from typing import Any, Dict

from app.core.logging import setup_logging
from app.services.apollo_rate_limited import ApolloRateLimitedService
from .base import BaseStage, StageResult

logger = setup_logging(__name__)


class ApolloPaidStage(BaseStage):
    """
    Apollo Paid Tier enrichment stage.

    Uses Apollo.io's paid credits to:
    - Reveal verified emails for contacts
    - Reveal direct phone numbers
    - Enrich contact profiles with personal emails

    Cost: ~$1 per contact enriched (email + phone reveal)
    Latency: ~500-1000ms per contact, batched up to 10 at a time

    Cost Optimization:
    - Skips enrichment if company already has 2+ contacts with emails
    - Only enriches ATL contacts (decision makers)
    - Batches up to 10 contacts per API call
    """

    name: str = "apollo_paid"
    cost_per_call: float = 1.0  # Average cost per contact enriched

    def __init__(self):
        """Initialize Apollo paid stage."""
        self._apollo = ApolloRateLimitedService()
        logger.info("ApolloPaidStage initialized")

    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute Apollo paid tier enrichment.

        COST OPTIMIZATION: Skips if company already has 2+ contacts with emails.

        Args:
            company: Company data from Supabase with domain and contacts

        Returns:
            StageResult with enriched contact data (emails + phones)
        """
        start_time = time.time()
        domain = company.get("domain")
        existing_contacts = company.get("contacts", [])

        if not domain:
            return StageResult(
                success=False,
                data={},
                error="No domain provided",
                latency_ms=0
            )

        # COST OPTIMIZATION: Skip if company already has 2+ contacts with emails
        contacts_with_emails = [
            c for c in existing_contacts
            if c.get("email") and "@" in c.get("email", "")
        ]

        if len(contacts_with_emails) >= 2:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.info(
                f"Skipping Apollo paid enrichment for {domain} - "
                f"already has {len(contacts_with_emails)} contacts with emails"
            )

            return StageResult(
                success=True,
                data={
                    "skipped": True,
                    "reason": "sufficient_contacts",
                    "existing_email_count": len(contacts_with_emails),
                },
                cost_usd=0.0,
                latency_ms=latency_ms
            )

        try:
            # Search and enrich contacts with email/phone reveals
            enriched_contacts = await self._apollo.search_and_enrich_contacts_safe(
                domain=domain,
                job_titles=[
                    "CEO", "President", "Owner", "Founder",
                    "VP", "Vice President",
                    "Director", "Head of",
                    "Chief", "CFO", "COO", "CTO", "CMO"
                ],
                max_results=10,  # Limit to 10 to control cost
                reveal_emails=True,  # Reveal verified emails (costs credits)
                reveal_phones=False,  # Skip phones to save credits (can add later)
            )

            latency_ms = int((time.time() - start_time) * 1000)

            # Calculate actual cost based on enriched contacts
            contacts_enriched = len([
                c for c in enriched_contacts
                if c.get("email") or c.get("phone_number")
            ])
            actual_cost = contacts_enriched * self.cost_per_call

            return StageResult(
                success=True,
                data={
                    "contacts": enriched_contacts,
                    "contact_count": len(enriched_contacts),
                    "contacts_enriched": contacts_enriched,
                },
                cost_usd=actual_cost,
                latency_ms=latency_ms
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Apollo paid enrichment failed for {domain}: {e}")

            return StageResult(
                success=False,
                data={},
                error=str(e),
                latency_ms=latency_ms
            )

    async def close(self):
        """Close Apollo service connections."""
        await self._apollo.close()
