#!/usr/bin/env python3
"""
Sync LinkedIn Scraping Results to Supabase
===========================================

Syncs LinkedIn company and profile scraping results to Supabase:
1. Updates dim_companies with LinkedIn company URLs and employee counts
2. Creates new contacts in dim_contacts from LinkedIn /people/ page scraping
3. Updates existing contacts with LinkedIn profile URLs from profile searches

Tables Updated:
- dim_companies: linkedin_url, linkedin_employee_count
- dim_contacts: linkedin_url, source='linkedin_company_scrape'

Usage:
    # After running LinkedIn enrichment pipeline
    python sync_linkedin_to_supabase.py --company-results results.json
    python sync_linkedin_to_supabase.py --profile-results profiles.json
    python sync_linkedin_to_supabase.py --all results.json profiles.json
"""

import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Optional, Any

from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

# Supabase connection
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY') or os.getenv('SUPABASE_ANON_KEY')

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class LinkedInSupabaseSync:
    """
    Sync LinkedIn scraping results to Supabase star schema.

    Follows the check-then-insert/update pattern used throughout the project.
    """

    def __init__(self):
        """Initialize Supabase client."""
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in .env")

        from supabase import create_client
        self.supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        logger.info("Supabase client initialized")

    async def sync_company_results(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Sync LinkedIn company scraping results to Supabase.

        Updates dim_companies with:
        - linkedin_url: Company LinkedIn page URL
        - linkedin_employee_count: Employee count from LinkedIn

        Creates new contacts in dim_contacts from discovered employees.

        Args:
            results: List of LinkedInCompanyResult dicts (from parallel_linkedin_company_scraper.py)

        Returns:
            Stats dict with companies_updated, contacts_created, contacts_skipped
        """
        stats = {
            "companies_updated": 0,
            "contacts_created": 0,
            "contacts_updated": 0,
            "contacts_skipped": 0,
            "errors": 0
        }

        # Get existing companies by normalized name
        logger.info("Fetching existing companies from Supabase...")
        existing_companies = self.supabase.table('dim_companies').select(
            'company_id, normalized_name, linkedin_url'
        ).execute()
        company_map = {
            r['normalized_name']: r for r in existing_companies.data
        }
        logger.info(f"Found {len(company_map)} existing companies")

        # Get existing contacts by email (for dedup)
        logger.info("Fetching existing contacts from Supabase...")
        existing_contacts = self.supabase.table('dim_contacts').select(
            'contact_id, email, full_name, linkedin_url, company_id'
        ).execute()
        # Map by lowercase email and by full_name for matching
        contact_by_email = {
            r['email'].lower(): r for r in existing_contacts.data if r.get('email')
        }
        contact_by_name = {}
        for r in existing_contacts.data:
            if r.get('full_name'):
                key = r['full_name'].lower().strip()
                if key not in contact_by_name:
                    contact_by_name[key] = []
                contact_by_name[key].append(r)
        logger.info(f"Found {len(contact_by_email)} contacts by email, {len(contact_by_name)} by name")

        for result in results:
            try:
                company_name = result.get('company_name', '')
                normalized = company_name.lower().strip()

                if normalized not in company_map:
                    logger.warning(f"Company not found in Supabase: {company_name}")
                    stats["errors"] += 1
                    continue

                company_data = company_map[normalized]
                company_id = company_data['company_id']

                # Update company with LinkedIn info
                linkedin_url = result.get('linkedin_url')
                employee_count = result.get('employee_count')

                if linkedin_url:
                    update_data = {
                        'linkedin_url': linkedin_url,
                        'updated_at': datetime.now(timezone.utc).isoformat()
                    }
                    if employee_count:
                        update_data['linkedin_employee_count'] = employee_count

                    self.supabase.table('dim_companies').update(
                        update_data
                    ).eq('company_id', company_id).execute()
                    stats["companies_updated"] += 1
                    logger.info(f"[{company_name}] Updated company with LinkedIn URL")

                # Create contacts from discovered employees
                employees = result.get('employees', [])
                for emp in employees:
                    emp_name = emp.get('name', '').strip()
                    emp_title = emp.get('title', '')
                    emp_linkedin = emp.get('profile_url')
                    is_atl = emp.get('is_atl', False)

                    if not emp_name:
                        continue

                    # Check if contact exists by name within THIS company
                    name_key = emp_name.lower().strip()
                    existing_contact = None

                    if name_key in contact_by_name:
                        # Only match if contact belongs to the SAME company
                        for c in contact_by_name[name_key]:
                            if c.get('company_id') == company_id:
                                existing_contact = c
                                break

                    if existing_contact:
                        # Update existing contact with LinkedIn URL if not set
                        if emp_linkedin and not existing_contact.get('linkedin_url'):
                            self.supabase.table('dim_contacts').update({
                                'linkedin_url': emp_linkedin,
                                'updated_at': datetime.now(timezone.utc).isoformat()
                            }).eq('contact_id', existing_contact['contact_id']).execute()
                            stats["contacts_updated"] += 1
                            logger.info(f"[{company_name}] Updated {emp_name} with LinkedIn URL")
                        else:
                            stats["contacts_skipped"] += 1
                    else:
                        # Create new contact
                        new_contact = {
                            'company_id': company_id,
                            'full_name': emp_name,
                            'title': emp_title,
                            'linkedin_url': emp_linkedin,
                            'is_atl': is_atl,
                            'source': 'linkedin_company_scrape',
                            'confidence': 70,  # Lower than Hunter.io verified
                            'created_at': datetime.now(timezone.utc).isoformat(),
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        }

                        try:
                            result = self.supabase.table('dim_contacts').insert(new_contact).execute()
                            stats["contacts_created"] += 1
                            logger.info(f"[{company_name}] Created contact: {emp_name} ({emp_title})")

                            # Add to dedup map with actual contact_id from DB
                            if result.data and len(result.data) > 0:
                                inserted_contact = result.data[0]
                                contact_by_name.setdefault(name_key, []).append(inserted_contact)
                            else:
                                # Fallback: use the new_contact dict (without DB-generated ID)
                                contact_by_name.setdefault(name_key, []).append(new_contact)
                        except Exception as e:
                            if 'duplicate' in str(e).lower():
                                stats["contacts_skipped"] += 1
                            else:
                                logger.error(f"Error creating contact {emp_name}: {e}")
                                stats["errors"] += 1

            except Exception as e:
                logger.error(f"Error processing company {result.get('company_name')}: {e}")
                stats["errors"] += 1

        logger.info(f"Company sync complete: {stats}")
        return stats

    async def sync_profile_results(
        self,
        results: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Sync LinkedIn profile search results to Supabase.

        Updates existing contacts in dim_contacts with discovered LinkedIn profile URLs.
        Only updates if confidence >= 0.3 and contact exists.

        Args:
            results: List of ProfileSearchResult dicts (from parallel_linkedin_profile_scraper.py)

        Returns:
            Stats dict with contacts_updated, skipped, errors
        """
        stats = {
            "contacts_updated": 0,
            "contacts_skipped": 0,
            "low_confidence_skipped": 0,
            "not_found": 0,
            "errors": 0
        }

        for result in results:
            try:
                contact_id = result.get('contact_id')
                linkedin_url = result.get('linkedin_url')
                confidence = result.get('confidence', 0)
                contact_name = result.get('contact_name', 'Unknown')

                # Skip low confidence matches
                if confidence < 0.3:
                    stats["low_confidence_skipped"] += 1
                    continue

                # Skip if no LinkedIn URL found
                if not linkedin_url:
                    stats["contacts_skipped"] += 1
                    continue

                # Update contact with LinkedIn URL
                if contact_id:
                    try:
                        self.supabase.table('dim_contacts').update({
                            'linkedin_url': linkedin_url,
                            'updated_at': datetime.now(timezone.utc).isoformat()
                        }).eq('contact_id', contact_id).execute()
                        stats["contacts_updated"] += 1
                        logger.info(f"Updated {contact_name} with LinkedIn URL (confidence: {confidence:.2f})")
                    except Exception as e:
                        if 'not found' in str(e).lower() or 'no rows' in str(e).lower():
                            stats["not_found"] += 1
                            logger.warning(f"Contact not found: {contact_id}")
                        else:
                            raise
                else:
                    stats["not_found"] += 1

            except Exception as e:
                logger.error(f"Error updating contact: {e}")
                stats["errors"] += 1

        logger.info(f"Profile sync complete: {stats}")
        return stats

    async def sync_all(
        self,
        company_results: List[Dict[str, Any]],
        profile_results: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, int]]:
        """
        Sync both company and profile results to Supabase.

        Args:
            company_results: List of LinkedInCompanyResult dicts
            profile_results: List of ProfileSearchResult dicts

        Returns:
            Combined stats from both sync operations
        """
        company_stats = await self.sync_company_results(company_results)
        profile_stats = await self.sync_profile_results(profile_results)

        return {
            "company_sync": company_stats,
            "profile_sync": profile_stats
        }


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description='Sync LinkedIn scraping results to Supabase'
    )
    parser.add_argument(
        '--company-results',
        type=str,
        help='Path to company results JSON file'
    )
    parser.add_argument(
        '--profile-results',
        type=str,
        help='Path to profile results JSON file'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print what would be synced without actually syncing'
    )

    args = parser.parse_args()

    if not args.company_results and not args.profile_results:
        parser.print_help()
        print("\nError: Provide at least one of --company-results or --profile-results")
        sys.exit(1)

    try:
        syncer = LinkedInSupabaseSync()
    except ValueError as e:
        logger.error(f"Failed to initialize Supabase client: {e}")
        sys.exit(1)

    # Load and sync company results
    if args.company_results:
        logger.info(f"Loading company results from {args.company_results}")
        try:
            with open(args.company_results, 'r') as f:
                company_data = json.load(f)
        except FileNotFoundError:
            logger.error(f"Company results file not found: {args.company_results}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in company results file: {e}")
            sys.exit(1)

        if args.dry_run:
            logger.info(f"[DRY RUN] Would sync {len(company_data)} company results")
        else:
            stats = await syncer.sync_company_results(company_data)
            logger.info(f"Company sync stats: {stats}")

    # Load and sync profile results
    if args.profile_results:
        logger.info(f"Loading profile results from {args.profile_results}")
        try:
            with open(args.profile_results, 'r') as f:
                profile_data = json.load(f)
        except FileNotFoundError:
            logger.error(f"Profile results file not found: {args.profile_results}")
            sys.exit(1)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in profile results file: {e}")
            sys.exit(1)

        if args.dry_run:
            logger.info(f"[DRY RUN] Would sync {len(profile_data)} profile results")
        else:
            stats = await syncer.sync_profile_results(profile_data)
            logger.info(f"Profile sync stats: {stats}")

    logger.info("✅ LinkedIn sync complete!")


if __name__ == '__main__':
    asyncio.run(main())
