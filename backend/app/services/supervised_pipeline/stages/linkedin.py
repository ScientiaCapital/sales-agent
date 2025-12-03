"""LinkedIn Stage - Company page and employee scraping."""

import time
from typing import Any, Dict

from app.core.logging import setup_logging
from app.services.browserbase_team_scraper import BrowserbaseTeamScraper
from .base import BaseStage, StageResult

logger = setup_logging(__name__)


class LinkedInStage(BaseStage):
    """
    LinkedIn enrichment stage.

    Uses Browserbase browser automation to scrape:
    - LinkedIn company pages
    - Employee listings (ATL + BTL)
    - LinkedIn profile URLs

    Cost: ~$0.01-0.05 per company (Browserbase session pricing)
    Latency: ~10-15 seconds per company (browser automation)
    """

    name: str = "linkedin"
    cost_per_call: float = 0.03  # Approximate Browserbase session cost

    def __init__(self):
        """Initialize LinkedIn stage."""
        self._scraper = BrowserbaseTeamScraper()
        logger.info("LinkedInStage initialized")

    async def execute(self, company: Dict[str, Any]) -> StageResult:
        """
        Execute LinkedIn enrichment.

        Args:
            company: Company data from Supabase with domain/linkedin_url

        Returns:
            StageResult with employee data and LinkedIn company info
        """
        start_time = time.time()
        domain = company.get("domain")
        company_name = company.get("company_name")

        if not domain and not company_name:
            return StageResult(
                success=False,
                data={},
                error="No domain or company name provided",
                latency_ms=0
            )

        try:
            # Scrape team page using Browserbase
            # The BrowserbaseTeamScraper will attempt to find team pages
            # at common paths like /about, /team, /about-us, etc.
            website_url = f"https://{domain}" if domain else None

            if not website_url:
                return StageResult(
                    success=False,
                    data={},
                    error="No website URL available",
                    latency_ms=0
                )

            contacts = await self._scraper.scrape_team_page(website_url)

            latency_ms = int((time.time() - start_time) * 1000)

            # Separate ATL and BTL contacts
            atl_contacts = [c for c in contacts if c.get("is_atl", False)]
            btl_contacts = [c for c in contacts if not c.get("is_atl", False)]

            return StageResult(
                success=True,
                data={
                    "contacts": contacts,
                    "atl_contacts": atl_contacts,
                    "btl_contacts": btl_contacts,
                    "total_contacts": len(contacts),
                    "atl_count": len(atl_contacts),
                    "btl_count": len(btl_contacts),
                },
                cost_usd=self.cost_per_call,
                latency_ms=latency_ms
            )

        except Exception as e:
            latency_ms = int((time.time() - start_time) * 1000)
            logger.error(f"LinkedIn enrichment failed for {domain}: {e}")

            return StageResult(
                success=False,
                data={},
                error=str(e),
                latency_ms=latency_ms
            )
