"""
Free-First Enrichment Script

Exhausts FREE data sources before any paid API calls.
Designed for scenarios where Apollo credits are limited or exhausted.

Priority Order (cheapest first):
1. Website Discovery + Email Extraction ($0)
2. LinkedIn People Search ($0)
3. Hunter.io Domain Search ($0.01/domain - only if above fail)

Usage:
    python free_first_enrichment.py --csv input.csv --output enriched.csv
    python free_first_enrichment.py --company "ABC HVAC" --domain abchvac.com

Cost: ~$0.01-0.02/company (Hunter.io fallback only)
"""

import argparse
import asyncio
import csv
import logging
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Optional, Dict, Any
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.services.website_discovery import WebsiteDiscoveryService
from app.services.email_extractor import EmailExtractor
from app.services.linkedin_people_service import LinkedInPeopleService
from app.services.hunter_service import HunterService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# ATL Contact Classification
# =============================================================================

ATL_TITLES = [
    "ceo", "chief executive", "president", "owner", "founder", "co-founder",
    "cto", "chief technology", "cfo", "chief financial", "coo", "chief operating",
    "vp", "vice president", "director", "head of", "manager", "partner", "principal",
    "managing director", "general manager"
]


def is_atl_contact(title: Optional[str]) -> bool:
    """Check if job title indicates an Above-The-Line decision maker."""
    if not title:
        return False
    title_lower = title.lower()
    return any(atl in title_lower for atl in ATL_TITLES)


# =============================================================================
# Data Models
# =============================================================================

@dataclass
class EnrichedContact:
    """Contact discovered through enrichment."""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    title: Optional[str] = None
    linkedin_url: Optional[str] = None
    is_atl: bool = False
    confidence: int = 0
    source: str = ""  # "website", "linkedin", "hunter"

    def __hash__(self):
        """Hash by email (lowercase) for deduplication."""
        return hash(self.email.lower() if self.email else self.name.lower())

    def __eq__(self, other):
        if not isinstance(other, EnrichedContact):
            return False
        if self.email and other.email:
            return self.email.lower() == other.email.lower()
        return self.name.lower() == other.name.lower()


@dataclass
class EnrichmentResult:
    """Result of enriching a single company."""
    company_name: str
    domain: Optional[str] = None
    discovered_domain: bool = False
    contacts: List[EnrichedContact] = field(default_factory=list)
    atl_contacts_found: int = 0
    total_contacts_found: int = 0
    sources_used: List[str] = field(default_factory=list)
    hunter_cost: float = 0.0
    total_cost: float = 0.0
    error: Optional[str] = None

    def add_contact(self, contact: EnrichedContact):
        """Add contact with deduplication."""
        # Check for duplicates by email
        for existing in self.contacts:
            if existing == contact:
                # Update existing if new has higher confidence
                if contact.confidence > existing.confidence:
                    existing.confidence = contact.confidence
                    if contact.email and not existing.email:
                        existing.email = contact.email
                    if contact.phone and not existing.phone:
                        existing.phone = contact.phone
                return

        self.contacts.append(contact)
        self.total_contacts_found += 1
        if contact.is_atl:
            self.atl_contacts_found += 1


# =============================================================================
# Free-First Enrichment Engine
# =============================================================================

class FreeFirstEnrichment:
    """
    Enrichment engine that prioritizes FREE sources.

    Strategy:
    1. Website Discovery - Find company website from name ($0)
    2. Email Extraction - Scrape emails from website ($0)
    3. LinkedIn Search - Find ATL contacts via Google ($0)
    4. Hunter.io Fallback - Only if no ATL found ($0.01/domain)
    """

    def __init__(self, use_hunter_fallback: bool = True):
        """
        Initialize enrichment engine.

        Args:
            use_hunter_fallback: Whether to use Hunter.io if free sources fail
        """
        self.use_hunter_fallback = use_hunter_fallback

        # Initialize services
        self.website_discovery = WebsiteDiscoveryService()
        self.email_extractor = EmailExtractor()
        self.linkedin_service = LinkedInPeopleService()
        self.hunter_service = HunterService()

        # Statistics
        self.stats = {
            "companies_processed": 0,
            "companies_with_atl": 0,
            "total_contacts": 0,
            "total_atl_contacts": 0,
            "hunter_calls": 0,
            "total_cost": 0.0,
            "sources": {
                "website": 0,
                "linkedin": 0,
                "hunter": 0
            }
        }

    async def enrich_company(
        self,
        company_name: str,
        domain: Optional[str] = None,
        industry: str = "",
        city: str = "",
        state: str = ""
    ) -> EnrichmentResult:
        """
        Enrich a single company using free-first strategy.

        Args:
            company_name: Company name
            domain: Known domain (optional - will discover if missing)
            industry: Industry type (helps website discovery)
            city: City (for geo-targeting)
            state: State (for geo-targeting)

        Returns:
            EnrichmentResult with discovered contacts
        """
        result = EnrichmentResult(company_name=company_name, domain=domain)

        try:
            logger.info(f"🔍 Enriching: {company_name}")

            # =================================================================
            # Step 1: Website Discovery ($0)
            # =================================================================
            if not domain:
                logger.info(f"  → Discovering website for {company_name}...")
                discovered = await self.website_discovery.discover_website(
                    company_name=company_name,
                    industry=industry,
                    city=city,
                    state=state
                )
                if discovered:
                    # Extract domain from URL
                    domain = discovered.replace("https://", "").replace("http://", "")
                    domain = domain.replace("www.", "").rstrip("/").split("/")[0]
                    result.domain = domain
                    result.discovered_domain = True
                    logger.info(f"  ✅ Found website: {domain}")
                else:
                    logger.info(f"  ⚠️ No website found for {company_name}")
            else:
                result.domain = domain

            # =================================================================
            # Step 2: Email Extraction from Website ($0)
            # =================================================================
            if domain:
                logger.info(f"  → Extracting emails from {domain}...")
                try:
                    raw_emails = await self.email_extractor.extract_emails(domain)

                    # Filter out false positives
                    emails = [e for e in raw_emails if self._is_valid_email(e)]

                    for email in emails:
                        # Infer name from email (firstname.lastname@)
                        name = self._infer_name_from_email(email)

                        contact = EnrichedContact(
                            name=name,
                            email=email,
                            is_atl=False,  # Can't determine from email alone
                            confidence=60,  # Lower confidence - no title info
                            source="website"
                        )
                        result.add_contact(contact)
                        self.stats["sources"]["website"] += 1

                    if emails:
                        result.sources_used.append("website")
                        logger.info(f"  ✅ Found {len(emails)} emails from website")

                except Exception as e:
                    logger.warning(f"  ⚠️ Email extraction failed: {e}")

            # =================================================================
            # Step 3: LinkedIn People Search ($0)
            # =================================================================
            logger.info(f"  → Searching LinkedIn for ATL contacts...")
            try:
                linkedin_url = f"https://linkedin.com/company/{self._slugify(company_name)}"
                linkedin_result = await self.linkedin_service.find_atl_contacts(
                    company_linkedin_url=linkedin_url,
                    company_name=company_name,
                    limit=5
                )

                for person in linkedin_result.people:
                    contact = EnrichedContact(
                        name=person.name,
                        linkedin_url=person.linkedin_url,
                        title=person.title,
                        is_atl=True,  # Pre-filtered for ATL
                        confidence=70,  # No email, but have name/title
                        source="linkedin"
                    )
                    result.add_contact(contact)
                    self.stats["sources"]["linkedin"] += 1

                if linkedin_result.people:
                    result.sources_used.append("linkedin")
                    logger.info(f"  ✅ Found {len(linkedin_result.people)} LinkedIn profiles")

            except Exception as e:
                logger.warning(f"  ⚠️ LinkedIn search failed: {e}")

            # =================================================================
            # Step 4: Hunter.io Fallback ($0.01/domain)
            # =================================================================
            # Only use Hunter if:
            # - Fallback is enabled
            # - We have a domain
            # - No ATL contacts found yet
            atl_found = any(c.is_atl for c in result.contacts)

            if self.use_hunter_fallback and domain and not atl_found:
                logger.info(f"  → Hunter.io fallback (no ATL found)...")
                try:
                    hunter_contacts = await self.hunter_service.domain_search(
                        domain=domain,
                        limit=10,
                        atl_only=True
                    )

                    if hunter_contacts:
                        for hc in hunter_contacts:
                            contact = EnrichedContact(
                                name=f"{hc.get('first_name', '')} {hc.get('last_name', '')}".strip(),
                                email=hc.get("email"),
                                phone=hc.get("phone"),
                                title=hc.get("position"),
                                linkedin_url=hc.get("linkedin"),
                                is_atl=hc.get("is_atl", False),
                                confidence=hc.get("confidence", 80),
                                source="hunter"
                            )
                            result.add_contact(contact)
                            self.stats["sources"]["hunter"] += 1

                        result.sources_used.append("hunter")
                        result.hunter_cost = 0.01
                        result.total_cost = 0.01
                        self.stats["hunter_calls"] += 1
                        self.stats["total_cost"] += 0.01
                        logger.info(f"  ✅ Found {len(hunter_contacts)} contacts via Hunter.io ($0.01)")
                    else:
                        logger.info(f"  ⚠️ No Hunter.io results")

                except Exception as e:
                    logger.warning(f"  ⚠️ Hunter.io search failed: {e}")

            # =================================================================
            # Update Statistics
            # =================================================================
            self.stats["companies_processed"] += 1
            self.stats["total_contacts"] += result.total_contacts_found
            self.stats["total_atl_contacts"] += result.atl_contacts_found

            if result.atl_contacts_found > 0:
                self.stats["companies_with_atl"] += 1

            logger.info(
                f"  📊 Result: {result.total_contacts_found} contacts "
                f"({result.atl_contacts_found} ATL) | Cost: ${result.total_cost:.2f}"
            )

        except Exception as e:
            result.error = str(e)
            logger.error(f"  ❌ Enrichment failed: {e}")

        return result

    async def enrich_batch(
        self,
        companies: List[Dict[str, Any]],
        concurrency: int = 3
    ) -> List[EnrichmentResult]:
        """
        Enrich multiple companies with controlled concurrency.

        Args:
            companies: List of dicts with company_name, domain, etc.
            concurrency: Max concurrent enrichments

        Returns:
            List of EnrichmentResults
        """
        results = []
        semaphore = asyncio.Semaphore(concurrency)

        async def enrich_with_semaphore(company: Dict) -> EnrichmentResult:
            async with semaphore:
                # Handle various column name formats from different sources
                company_name = (
                    company.get("company_name") or
                    company.get("business_name") or
                    company.get("name") or
                    ""
                )
                domain = (
                    company.get("domain") or
                    company.get("website") or
                    ""
                )
                return await self.enrich_company(
                    company_name=company_name,
                    domain=domain,
                    industry=company.get("industry", ""),
                    city=company.get("city", ""),
                    state=company.get("state", "")
                )

        # Create tasks
        tasks = [enrich_with_semaphore(c) for c in companies]

        # Execute with progress
        logger.info(f"Starting batch enrichment of {len(companies)} companies...")

        for i, task in enumerate(asyncio.as_completed(tasks), 1):
            result = await task
            results.append(result)
            if i % 10 == 0:
                logger.info(f"Progress: {i}/{len(companies)} companies processed")

        return results

    def print_summary(self):
        """Print enrichment statistics summary."""
        print("\n" + "=" * 60)
        print("FREE-FIRST ENRICHMENT SUMMARY")
        print("=" * 60)
        print(f"Companies Processed: {self.stats['companies_processed']}")
        print(f"Companies with ATL:  {self.stats['companies_with_atl']} "
              f"({self._pct(self.stats['companies_with_atl'], self.stats['companies_processed'])}%)")
        print(f"Total Contacts:      {self.stats['total_contacts']}")
        print(f"ATL Contacts:        {self.stats['total_atl_contacts']}")
        print("-" * 60)
        print("Source Breakdown:")
        print(f"  Website Scraping:  {self.stats['sources']['website']} contacts ($0)")
        print(f"  LinkedIn Search:   {self.stats['sources']['linkedin']} contacts ($0)")
        print(f"  Hunter.io:         {self.stats['sources']['hunter']} contacts "
              f"(${self.stats['total_cost']:.2f})")
        print("-" * 60)
        print(f"Total Cost:          ${self.stats['total_cost']:.2f}")
        print(f"Hunter.io Calls:     {self.stats['hunter_calls']}")
        print("=" * 60 + "\n")

    def _is_valid_email(self, email: str) -> bool:
        """
        Filter out false positive emails (images, templates, known junk).

        Returns False for:
        - Image file patterns (logo@2x.png, icon.jpg)
        - Template/placeholder domains (godaddy.com, squarespace.com)
        - Common web framework emails
        """
        email_lower = email.lower()

        # Skip image file patterns (common false positive from regex)
        if any(ext in email_lower for ext in ['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp']):
            return False

        # Skip template/placeholder domains
        junk_domains = [
            'godaddy.com', 'squarespace.com', 'wix.com', 'weebly.com',
            'wordpress.com', 'latofonts.com', 'placeholder.com', 'example.com',
            'sentry.io', 'googletagmanager.com', 'facebook.com', 'twitter.com'
        ]
        domain = email_lower.split('@')[-1] if '@' in email_lower else ''
        if any(junk in domain for junk in junk_domains):
            return False

        # Skip generic/system emails
        generic_prefixes = [
            'noreply', 'no-reply', 'donotreply', 'mailer-daemon', 'postmaster',
            'webmaster', 'admin', 'root', 'localhost', 'test', 'demo'
        ]
        local_part = email_lower.split('@')[0] if '@' in email_lower else ''
        if any(local_part.startswith(prefix) for prefix in generic_prefixes):
            return False

        return True

    def _infer_name_from_email(self, email: str) -> str:
        """Infer name from email address (john.smith@ -> John Smith)."""
        local_part = email.split("@")[0]
        # Replace common separators with space
        name = local_part.replace(".", " ").replace("_", " ").replace("-", " ")
        # Title case
        return name.title()

    def _slugify(self, name: str) -> str:
        """Convert company name to URL slug."""
        import re
        slug = name.lower()
        slug = re.sub(r'[^a-z0-9\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        return slug.strip('-')

    def _pct(self, a: int, b: int) -> str:
        """Calculate percentage safely."""
        if b == 0:
            return "0"
        return f"{(a / b) * 100:.1f}"

    async def close(self):
        """Clean up resources."""
        await self.email_extractor.close()


# =============================================================================
# CSV Processing
# =============================================================================

def load_csv(filepath: str) -> List[Dict[str, Any]]:
    """Load companies from CSV file."""
    companies = []
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            companies.append(dict(row))
    return companies


def save_results_csv(results: List[EnrichmentResult], output_path: str):
    """Save enrichment results to CSV."""
    rows = []

    for result in results:
        if not result.contacts:
            # Company with no contacts found
            rows.append({
                "company_name": result.company_name,
                "domain": result.domain or "",
                "contact_name": "",
                "contact_email": "",
                "contact_phone": "",
                "contact_title": "",
                "linkedin_url": "",
                "is_atl": "",
                "confidence": "",
                "source": "",
                "sources_used": ",".join(result.sources_used),
                "cost": f"{result.total_cost:.2f}",
                "error": result.error or ""
            })
        else:
            for contact in result.contacts:
                rows.append({
                    "company_name": result.company_name,
                    "domain": result.domain or "",
                    "contact_name": contact.name,
                    "contact_email": contact.email or "",
                    "contact_phone": contact.phone or "",
                    "contact_title": contact.title or "",
                    "linkedin_url": contact.linkedin_url or "",
                    "is_atl": "Yes" if contact.is_atl else "No",
                    "confidence": str(contact.confidence),
                    "source": contact.source,
                    "sources_used": ",".join(result.sources_used),
                    "cost": f"{result.total_cost:.2f}",
                    "error": result.error or ""
                })

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            "company_name", "domain", "contact_name", "contact_email",
            "contact_phone", "contact_title", "linkedin_url", "is_atl",
            "confidence", "source", "sources_used", "cost", "error"
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    logger.info(f"Results saved to: {output_path}")


# =============================================================================
# CLI Interface
# =============================================================================

async def main():
    parser = argparse.ArgumentParser(
        description="Free-First Lead Enrichment - Exhaust FREE sources before paid APIs"
    )

    # Input options (mutually exclusive)
    input_group = parser.add_mutually_exclusive_group(required=True)
    input_group.add_argument(
        "--csv",
        help="Input CSV file with companies"
    )
    input_group.add_argument(
        "--company",
        help="Single company name to enrich"
    )

    # Additional options
    parser.add_argument(
        "--domain",
        help="Known domain (with --company)"
    )
    parser.add_argument(
        "--output", "-o",
        help="Output CSV file (default: enriched_TIMESTAMP.csv)"
    )
    parser.add_argument(
        "--no-hunter",
        action="store_true",
        help="Disable Hunter.io fallback (100% free)"
    )
    parser.add_argument(
        "--concurrency", "-c",
        type=int,
        default=3,
        help="Concurrent enrichments (default: 3)"
    )

    args = parser.parse_args()

    # Initialize engine
    engine = FreeFirstEnrichment(use_hunter_fallback=not args.no_hunter)

    try:
        if args.company:
            # Single company mode
            result = await engine.enrich_company(
                company_name=args.company,
                domain=args.domain
            )

            print("\n" + "=" * 60)
            print(f"ENRICHMENT RESULT: {result.company_name}")
            print("=" * 60)
            print(f"Domain: {result.domain or 'Not found'}")
            print(f"Sources Used: {', '.join(result.sources_used) or 'None'}")
            print(f"Cost: ${result.total_cost:.2f}")
            print("-" * 60)

            if result.contacts:
                print(f"Contacts Found: {result.total_contacts_found}")
                print()
                for i, contact in enumerate(result.contacts, 1):
                    print(f"  {i}. {contact.name}")
                    if contact.email:
                        print(f"     Email: {contact.email}")
                    if contact.phone:
                        print(f"     Phone: {contact.phone}")
                    if contact.title:
                        print(f"     Title: {contact.title}")
                    if contact.linkedin_url:
                        print(f"     LinkedIn: {contact.linkedin_url}")
                    print(f"     ATL: {'Yes' if contact.is_atl else 'No'} | "
                          f"Confidence: {contact.confidence}% | Source: {contact.source}")
                    print()
            else:
                print("No contacts found.")

            if result.error:
                print(f"Error: {result.error}")

        else:
            # Batch mode
            companies = load_csv(args.csv)
            logger.info(f"Loaded {len(companies)} companies from {args.csv}")

            results = await engine.enrich_batch(
                companies=companies,
                concurrency=args.concurrency
            )

            # Generate output filename
            if args.output:
                output_path = args.output
            else:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = f"enriched_{timestamp}.csv"

            save_results_csv(results, output_path)
            engine.print_summary()

    finally:
        await engine.close()


if __name__ == "__main__":
    asyncio.run(main())
