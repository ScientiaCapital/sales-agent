"""
Crawler Intelligence - Learning System for Page Discovery

Tracks which URL patterns yield the best contacts/signals per industry.
Builds a competitive moat by learning what works over time.

Usage:
    from app.services.crawler_intelligence import CrawlerIntelligence

    intel = CrawlerIntelligence(supabase)
    intel.record_discovery(
        company_id="...",
        page_url="/about/leadership",
        contacts_found=5,
        signals_found=3,
        industry="electrical_contractor"
    )

    # Get best pages for an industry
    best_pages = intel.get_priority_pages(industry="hvac_contractor")
"""

import logging
from datetime import datetime
from typing import Optional
from collections import defaultdict

from supabase import Client

logger = logging.getLogger(__name__)


# Default industry-specific page patterns (learned over time)
INDUSTRY_PAGE_PATTERNS = {
    "solar": [
        "/team", "/about", "/our-team", "/leadership",
        "/about-us", "/company", "/people",
    ],
    "electrical_contractor": [
        "/team", "/about-us", "/leadership", "/our-team",
        "/about/team", "/staff", "/management",
    ],
    "hvac_contractor": [
        "/about", "/about-us", "/our-team", "/team",
        "/meet-the-team", "/staff", "/technicians",
    ],
    "general_contractor": [
        "/leadership", "/team", "/about/our-team",
        "/executives", "/management", "/people",
    ],
    "default": [
        "/team", "/about", "/our-team", "/leadership",
        "/staff", "/people", "/management", "/executives",
        "/about-us", "/about/team", "/about/leadership",
        "/company/team", "/company/leadership",
        "/meet-the-team", "/our-people",
        "/contact", "/contact-us",
        "/services", "/careers",
    ],
}


class CrawlerIntelligence:
    """
    Learning system for crawler page discovery.

    Tracks which URL patterns yield best results per industry.
    Uses this data to prioritize crawling for new companies.
    """

    def __init__(self, supabase: Client):
        self.supabase = supabase
        self._cache = {}

    def record_discovery(
        self,
        company_id: str,
        page_url: str,
        contacts_found: int,
        signals_found: int,
        industry: str = "default",
        page_type: str = "unknown",
    ):
        """
        Record a successful page discovery for learning.

        Args:
            company_id: Company UUID
            page_url: Full URL of the page
            contacts_found: Number of contacts extracted
            signals_found: Number of ICP signals detected
            industry: Industry classification
            page_type: Type of page (team, about, contact, etc.)
        """
        # Extract URL pattern (remove domain, normalize)
        pattern = self._extract_pattern(page_url)

        try:
            self.supabase.table("fact_crawler_intelligence").insert({
                "company_id": company_id,
                "page_url": page_url,
                "url_pattern": pattern,
                "contacts_found": contacts_found,
                "signals_found": signals_found,
                "industry": industry,
                "page_type": page_type,
                "discovered_at": datetime.utcnow().isoformat(),
            }).execute()

            logger.debug(f"Recorded discovery: {pattern} -> {contacts_found} contacts")

        except Exception as e:
            # Table might not exist yet - fail silently
            logger.debug(f"Failed to record discovery: {e}")

    def get_priority_pages(
        self,
        industry: str = "default",
        min_success_rate: float = 0.1,
    ) -> list[str]:
        """
        Get prioritized page patterns for an industry.

        Returns patterns sorted by historical success rate.
        Falls back to default patterns if no data.

        Args:
            industry: Industry classification
            min_success_rate: Minimum success rate to include

        Returns:
            List of URL patterns sorted by effectiveness
        """
        # Try to get learned patterns from database
        try:
            result = self.supabase.table("fact_crawler_intelligence") \
                .select("url_pattern,contacts_found,signals_found") \
                .eq("industry", industry) \
                .execute()

            if result.data:
                # Aggregate by pattern
                pattern_scores = defaultdict(lambda: {"hits": 0, "contacts": 0, "signals": 0})
                for row in result.data:
                    pattern = row["url_pattern"]
                    pattern_scores[pattern]["hits"] += 1
                    pattern_scores[pattern]["contacts"] += row["contacts_found"] or 0
                    pattern_scores[pattern]["signals"] += row["signals_found"] or 0

                # Score and sort
                scored = []
                for pattern, data in pattern_scores.items():
                    # Score = average contacts + signals per hit
                    avg_yield = (data["contacts"] + data["signals"]) / max(data["hits"], 1)
                    if avg_yield >= min_success_rate:
                        scored.append((pattern, avg_yield, data["hits"]))

                # Sort by yield (descending), then by sample size
                scored.sort(key=lambda x: (-x[1], -x[2]))

                if scored:
                    logger.info(f"Using learned patterns for {industry}: {len(scored)} patterns")
                    return [p[0] for p in scored]

        except Exception as e:
            logger.debug(f"Could not fetch learned patterns: {e}")

        # Fall back to industry defaults
        patterns = INDUSTRY_PAGE_PATTERNS.get(industry, INDUSTRY_PAGE_PATTERNS["default"])
        logger.debug(f"Using default patterns for {industry}: {len(patterns)} patterns")
        return patterns

    def get_stats(self, industry: str = None) -> dict:
        """Get crawler intelligence statistics."""
        try:
            query = self.supabase.table("fact_crawler_intelligence") \
                .select("industry,url_pattern,contacts_found,signals_found")

            if industry:
                query = query.eq("industry", industry)

            result = query.execute()

            if not result.data:
                return {"status": "no_data"}

            # Aggregate
            industries = defaultdict(lambda: {"discoveries": 0, "contacts": 0, "signals": 0})
            top_patterns = defaultdict(lambda: {"hits": 0, "contacts": 0})

            for row in result.data:
                ind = row["industry"]
                industries[ind]["discoveries"] += 1
                industries[ind]["contacts"] += row["contacts_found"] or 0
                industries[ind]["signals"] += row["signals_found"] or 0

                pattern = row["url_pattern"]
                top_patterns[pattern]["hits"] += 1
                top_patterns[pattern]["contacts"] += row["contacts_found"] or 0

            # Top 10 patterns by contacts
            sorted_patterns = sorted(
                top_patterns.items(),
                key=lambda x: -x[1]["contacts"]
            )[:10]

            return {
                "total_discoveries": len(result.data),
                "industries": dict(industries),
                "top_patterns": [
                    {"pattern": p, "hits": d["hits"], "contacts": d["contacts"]}
                    for p, d in sorted_patterns
                ],
            }

        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _extract_pattern(self, url: str) -> str:
        """Extract URL pattern from full URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        path = parsed.path.rstrip("/") or "/"

        # Normalize common variations
        path = path.lower()

        return path


# SQL to create the intelligence table (run in Supabase):
"""
CREATE TABLE IF NOT EXISTS fact_crawler_intelligence (
    id BIGSERIAL PRIMARY KEY,
    company_id UUID REFERENCES dim_companies(company_id),
    page_url TEXT NOT NULL,
    url_pattern TEXT NOT NULL,
    contacts_found INTEGER DEFAULT 0,
    signals_found INTEGER DEFAULT 0,
    industry TEXT DEFAULT 'default',
    page_type TEXT,
    discovered_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_crawler_intel_industry ON fact_crawler_intelligence(industry);
CREATE INDEX idx_crawler_intel_pattern ON fact_crawler_intelligence(url_pattern);
"""
