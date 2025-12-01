#!/usr/bin/env python3
"""
LinkedIn Enrichment Pipeline Orchestrator
==========================================

Coordinates the full LinkedIn enrichment pipeline:
1. Load leads from Supabase (dim_companies without LinkedIn data)
2. Scrape LinkedIn company pages for employee lists
3. Search for LinkedIn profiles of discovered ATL contacts
4. Sync all results back to Supabase

Usage:
    # Enrich 10 companies (test)
    python run_linkedin_enrichment.py --limit 10

    # Enrich all companies without LinkedIn data
    python run_linkedin_enrichment.py --all

    # Dry run (no writes)
    python run_linkedin_enrichment.py --limit 10 --dry-run

    # Save results to JSON (for debugging)
    python run_linkedin_enrichment.py --limit 10 --output results.json

Rate Limits:
    - Company scraping: 30/hour (2 min average per company)
    - Profile search: 10/hour (6 min average per profile)
    - Estimated time for 100 companies: ~4-5 hours

Environment Variables:
    - BROWSERBASE_API_KEY: Browserbase API key
    - BROWSERBASE_PROJECT_ID: Browserbase project ID
    - SUPABASE_URL: Supabase project URL
    - SUPABASE_SERVICE_KEY: Supabase service role key
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Imports from local modules
from parallel_linkedin_company_scraper import (
    ParallelLinkedInCompanyScraper,
    LinkedInCompanyResult,
)
from parallel_linkedin_profile_scraper import (
    ParallelLinkedInProfileScraper,
    ProfileSearchResult,
)
from sync_linkedin_to_supabase import LinkedInSupabaseSync
from app.services.browserbase_session_pool import (
    get_session_pool,
    close_session_pool,
)


class LinkedInEnrichmentPipeline:
    """
    Orchestrates the full LinkedIn enrichment pipeline.

    Flow:
    1. Fetch companies from Supabase that need LinkedIn enrichment
    2. Scrape LinkedIn company pages (get employees)
    3. Search for ATL contact LinkedIn profiles
    4. Sync all results back to Supabase

    Architecture:
    - Uses shared Browserbase session pool for efficiency
    - Company scraping and profile search run sequentially (rate limits)
    - Results synced in batches to reduce API calls
    """

    def __init__(
        self,
        max_workers: int = 3,
        company_scrape_enabled: bool = True,
        profile_search_enabled: bool = True,
        dry_run: bool = False,
    ):
        """
        Initialize the pipeline.

        Args:
            max_workers: Max concurrent browser sessions (default: 3)
            company_scrape_enabled: Enable company page scraping
            profile_search_enabled: Enable profile URL searching
            dry_run: If True, don't write to Supabase
        """
        self.max_workers = max_workers
        self.company_scrape_enabled = company_scrape_enabled
        self.profile_search_enabled = profile_search_enabled
        self.dry_run = dry_run

        # Supabase client (for reading leads)
        self._init_supabase()

        # Scrapers initialized lazily
        self._company_scraper: Optional[ParallelLinkedInCompanyScraper] = None
        self._profile_scraper: Optional[ParallelLinkedInProfileScraper] = None
        self._supabase_sync: Optional[LinkedInSupabaseSync] = None

    def _init_supabase(self):
        """Initialize Supabase client for reading leads."""
        supabase_url = os.getenv('SUPABASE_URL')
        supabase_key = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')

        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set")

        from supabase import create_client
        self.supabase = create_client(supabase_url, supabase_key)
        logger.info("Supabase client initialized")

    async def fetch_leads_to_enrich(
        self,
        limit: Optional[int] = None,
        icp_tier: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch companies from Supabase that need LinkedIn enrichment.

        Criteria:
        - Has website/domain
        - No LinkedIn URL yet (linkedin_url IS NULL)
        - Optionally filter by ICP tier

        Args:
            limit: Max companies to fetch (None = all)
            icp_tier: Filter by ICP tier (PLATINUM, GOLD, SILVER, BRONZE)

        Returns:
            List of company dicts with name and domain
        """
        logger.info(f"Fetching leads to enrich (limit={limit}, tier={icp_tier})...")

        query = self.supabase.table('dim_companies').select(
            'company_id, company_name, normalized_name, domain, website'
        ).is_('linkedin_url', 'null')

        # Filter by ICP tier if specified
        if icp_tier:
            query = query.eq('icp_tier', icp_tier)

        # Only companies with a domain/website
        query = query.not_.is_('domain', 'null')

        # Apply limit
        if limit:
            query = query.limit(limit)

        result = query.execute()

        leads = []
        for row in result.data:
            domain = row.get('domain') or row.get('website') or ''
            if domain:
                leads.append({
                    'company_id': row['company_id'],
                    'name': row['company_name'],
                    'normalized_name': row['normalized_name'],
                    'domain': domain,
                })

        logger.info(f"Found {len(leads)} leads to enrich")
        return leads

    async def run(
        self,
        limit: Optional[int] = None,
        icp_tier: Optional[str] = None,
        output_file: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Run the full LinkedIn enrichment pipeline.

        Args:
            limit: Max companies to enrich
            icp_tier: Filter by ICP tier
            output_file: Optional JSON file to save results

        Returns:
            Stats dict with counts and timing
        """
        start_time = datetime.utcnow()
        stats = {
            'leads_fetched': 0,
            'companies_scraped': 0,
            'company_errors': 0,
            'atl_employees_found': 0,
            'profiles_searched': 0,
            'profiles_found': 0,
            'supabase_synced': False,
            'duration_seconds': 0,
        }

        try:
            # Step 1: Fetch leads
            leads = await self.fetch_leads_to_enrich(limit=limit, icp_tier=icp_tier)
            stats['leads_fetched'] = len(leads)

            if not leads:
                logger.info("No leads to enrich")
                return stats

            # Step 2: Scrape LinkedIn company pages
            company_results: List[LinkedInCompanyResult] = []
            if self.company_scrape_enabled:
                company_results = await self._scrape_companies(leads)
                stats['companies_scraped'] = sum(1 for r in company_results if not r.error)
                stats['company_errors'] = sum(1 for r in company_results if r.error)
                stats['atl_employees_found'] = sum(len(r.atl_employees) for r in company_results)

            # Step 3: Search for ATL profile URLs
            profile_results: List[ProfileSearchResult] = []
            if self.profile_search_enabled and company_results:
                profile_results = await self._search_profiles(company_results)
                stats['profiles_searched'] = len(profile_results)
                stats['profiles_found'] = sum(1 for r in profile_results if r.linkedin_url)

            # Step 4: Sync to Supabase
            if not self.dry_run and (company_results or profile_results):
                await self._sync_to_supabase(company_results, profile_results)
                stats['supabase_synced'] = True

            # Save results to file if requested
            if output_file:
                self._save_results(output_file, company_results, profile_results)

            # Calculate duration
            end_time = datetime.utcnow()
            stats['duration_seconds'] = (end_time - start_time).total_seconds()

            self._log_summary(stats)
            return stats

        finally:
            await self._cleanup()

    async def _scrape_companies(
        self,
        leads: List[Dict[str, Any]]
    ) -> List[LinkedInCompanyResult]:
        """
        Scrape LinkedIn company pages for all leads.

        Args:
            leads: List of lead dicts with name and domain

        Returns:
            List of LinkedInCompanyResult objects
        """
        logger.info(f"Starting company scraping for {len(leads)} leads...")

        # Initialize scraper
        self._company_scraper = ParallelLinkedInCompanyScraper(
            max_workers=self.max_workers,
            scroll_cycles=5,
            timeout_ms=30000,
        )
        await self._company_scraper.initialize()

        # Prepare company list
        companies = [
            {'name': lead['name'], 'domain': lead['domain']}
            for lead in leads
        ]

        # Scrape
        results = await self._company_scraper.scrape_companies(companies)

        logger.info(
            f"Company scraping complete: "
            f"{sum(1 for r in results if not r.error)}/{len(results)} successful"
        )

        return results

    async def _search_profiles(
        self,
        company_results: List[LinkedInCompanyResult]
    ) -> List[ProfileSearchResult]:
        """
        Search for LinkedIn profiles of ATL employees.

        Args:
            company_results: Results from company scraping

        Returns:
            List of ProfileSearchResult objects
        """
        # Collect ATL employees to search
        atl_contacts = []
        for result in company_results:
            if result.error:
                continue
            for emp in result.atl_employees:
                atl_contacts.append({
                    'id': f"{result.company_name}_{emp.name}",
                    'name': emp.name,
                    'company': result.company_name,
                    'title': emp.title,
                })

        if not atl_contacts:
            logger.info("No ATL employees to search for profiles")
            return []

        logger.info(f"Searching LinkedIn profiles for {len(atl_contacts)} ATL contacts...")

        # Initialize profile scraper with shared session pool
        pool = await get_session_pool()
        self._profile_scraper = ParallelLinkedInProfileScraper(
            session_pool=pool,
            max_per_hour=10,
            max_per_day=50,
            min_delay=45.0,
            max_delay=90.0,
        )

        # Search profiles (sequential due to rate limits)
        results = await self._profile_scraper.search_profiles_batch(atl_contacts)

        logger.info(
            f"Profile search complete: "
            f"{sum(1 for r in results if r.linkedin_url)}/{len(results)} found"
        )

        return results

    async def _sync_to_supabase(
        self,
        company_results: List[LinkedInCompanyResult],
        profile_results: List[ProfileSearchResult],
    ) -> None:
        """
        Sync all results to Supabase.

        Args:
            company_results: Company scraping results
            profile_results: Profile search results
        """
        logger.info("Syncing results to Supabase...")

        self._supabase_sync = LinkedInSupabaseSync()

        # Convert dataclasses to dicts for sync
        company_dicts = []
        for result in company_results:
            if result.error:
                continue
            company_dicts.append({
                'company_name': result.company_name,
                'linkedin_url': result.linkedin_url,
                'employee_count': result.employee_count,
                'employees': [
                    {
                        'name': emp.name,
                        'title': emp.title,
                        'profile_url': emp.profile_url,
                        'is_atl': emp.is_atl,
                    }
                    for emp in result.employees
                ],
            })

        profile_dicts = []
        for result in profile_results:
            profile_dicts.append({
                'contact_id': result.contact_id,
                'contact_name': result.contact_name,
                'linkedin_url': result.linkedin_url,
                'confidence': result.confidence,
            })

        # Sync to Supabase
        sync_stats = await self._supabase_sync.sync_all(company_dicts, profile_dicts)
        logger.info(f"Supabase sync complete: {sync_stats}")

    def _save_results(
        self,
        output_file: str,
        company_results: List[LinkedInCompanyResult],
        profile_results: List[ProfileSearchResult],
    ) -> None:
        """Save results to JSON file for debugging."""
        output = {
            'timestamp': datetime.utcnow().isoformat(),
            'company_results': [
                {
                    'company_name': r.company_name,
                    'domain': r.domain,
                    'linkedin_url': r.linkedin_url,
                    'employee_count': r.employee_count,
                    'employees_found': len(r.employees),
                    'atl_employees': len(r.atl_employees),
                    'error': r.error,
                }
                for r in company_results
            ],
            'profile_results': [
                {
                    'contact_name': r.contact_name,
                    'company_name': r.company_name,
                    'linkedin_url': r.linkedin_url,
                    'confidence': r.confidence,
                    'error': r.error,
                }
                for r in profile_results
            ],
        }

        with open(output_file, 'w') as f:
            json.dump(output, f, indent=2)

        logger.info(f"Results saved to {output_file}")

    def _log_summary(self, stats: Dict[str, Any]) -> None:
        """Log pipeline summary."""
        duration_min = stats['duration_seconds'] / 60

        logger.info("=" * 60)
        logger.info("LINKEDIN ENRICHMENT PIPELINE SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Leads fetched:       {stats['leads_fetched']}")
        logger.info(f"Companies scraped:   {stats['companies_scraped']}")
        logger.info(f"Company errors:      {stats['company_errors']}")
        logger.info(f"ATL employees found: {stats['atl_employees_found']}")
        logger.info(f"Profiles searched:   {stats['profiles_searched']}")
        logger.info(f"Profiles found:      {stats['profiles_found']}")
        logger.info(f"Supabase synced:     {stats['supabase_synced']}")
        logger.info(f"Duration:            {duration_min:.1f} minutes")
        logger.info("=" * 60)

    async def _cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up pipeline resources...")

        if self._company_scraper:
            await self._company_scraper.cleanup()

        # Close shared session pool
        await close_session_pool()

        logger.info("Cleanup complete")


async def main():
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description='LinkedIn Enrichment Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test with 10 companies
    python run_linkedin_enrichment.py --limit 10

    # Enrich PLATINUM tier leads only
    python run_linkedin_enrichment.py --tier PLATINUM

    # Dry run (no Supabase writes)
    python run_linkedin_enrichment.py --limit 5 --dry-run

    # Save results to JSON
    python run_linkedin_enrichment.py --limit 10 --output results.json
        """
    )

    parser.add_argument(
        '--limit', '-l',
        type=int,
        help='Max companies to enrich (default: 10 for safety)'
    )
    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Enrich all companies without LinkedIn data (USE WITH CAUTION)'
    )
    parser.add_argument(
        '--tier', '-t',
        choices=['PLATINUM', 'GOLD', 'SILVER', 'BRONZE'],
        help='Filter by ICP tier'
    )
    parser.add_argument(
        '--dry-run', '-n',
        action='store_true',
        help='Run without writing to Supabase'
    )
    parser.add_argument(
        '--output', '-o',
        type=str,
        help='Save results to JSON file'
    )
    parser.add_argument(
        '--workers', '-w',
        type=int,
        default=3,
        help='Max concurrent browser sessions (default: 3)'
    )
    parser.add_argument(
        '--no-company-scrape',
        action='store_true',
        help='Skip company page scraping (profiles only)'
    )
    parser.add_argument(
        '--no-profile-search',
        action='store_true',
        help='Skip profile searching (company scraping only)'
    )

    args = parser.parse_args()

    # Safety check: require explicit --all or --limit
    if not args.all and not args.limit:
        args.limit = 10  # Default to 10 for safety
        logger.warning(f"No limit specified, defaulting to {args.limit} companies")

    # Initialize pipeline
    pipeline = LinkedInEnrichmentPipeline(
        max_workers=args.workers,
        company_scrape_enabled=not args.no_company_scrape,
        profile_search_enabled=not args.no_profile_search,
        dry_run=args.dry_run,
    )

    # Run pipeline
    limit = None if args.all else args.limit
    stats = await pipeline.run(
        limit=limit,
        icp_tier=args.tier,
        output_file=args.output,
    )

    # Exit with error if no leads enriched
    if stats['leads_fetched'] == 0:
        logger.warning("No leads found to enrich")
        sys.exit(0)

    if stats['companies_scraped'] == 0 and stats['profiles_found'] == 0:
        logger.error("Pipeline completed but no data enriched")
        sys.exit(1)

    logger.info("✅ LinkedIn enrichment pipeline complete!")


if __name__ == '__main__':
    asyncio.run(main())
