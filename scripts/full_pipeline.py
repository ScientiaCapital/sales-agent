#!/usr/bin/env python3
"""
Complete Pipeline: Import CSV → Discover ATL Contacts → Enrich

This script:
1. Imports CSV companies
2. Discovers ATL contacts via LinkedIn (for companies without emails)
3. Enriches contacts with Apollo (for companies with emails)
4. Updates lead records with discovered contacts

Usage:
    python3 scripts/full_pipeline.py [--skip-import] [--limit N]

Examples:
    # Full pipeline (import + discover + enrich)
    python3 scripts/full_pipeline.py

    # Skip import, just discover and enrich
    python3 scripts/full_pipeline.py --skip-import

    # Process only first 10 companies
    python3 scripts/full_pipeline.py --limit 10
"""
import asyncio
import sys
import os
import argparse
import requests
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add backend to path
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.models.database import SessionLocal
from app.models.lead import Lead
from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
from app.services.linkedin_scraper import LinkedInScraper
from app.services.apollo import ApolloService
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class FullPipelineService:
    """Complete pipeline for importing and enriching companies"""
    
    def __init__(self, db: Session):
        self.db = db
        self.enrichment_agent = EnrichmentAgent()
        self.linkedin_scraper = LinkedInScraper()
        self.apollo_service = ApolloService()
        self.stats = {
            'imported': 0,
            'linkedin_discovered': 0,
            'apollo_enriched': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': datetime.now()
        }
    
    def import_csv(self, csv_file: str) -> bool:
        """Import CSV via API"""
        print(f"\n📤 Importing CSV: {csv_file}")
        
        if not Path(csv_file).exists():
            print(f"❌ CSV file not found: {csv_file}")
            return False
        
        try:
            url = "http://localhost:8001/api/leads/import/csv"
            with open(csv_file, 'rb') as f:
                files = {'file': (Path(csv_file).name, f, 'text/csv')}
                response = requests.post(url, files=files, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                self.stats['imported'] = result['imported_count']
                print(f"✅ Imported {result['imported_count']}/{result['total_leads']} companies")
                print(f"   Duration: {result['duration_ms']}ms")
                return True
            else:
                print(f"❌ Import failed: {response.status_code}")
                print(response.text[:200])
                return False
                
        except requests.exceptions.ConnectionError:
            print(f"❌ Server not running at http://localhost:8001")
            print(f"   Start server: python3 start_server.py")
            return False
        except Exception as e:
            print(f"❌ Import error: {e}")
            return False
    
    def extract_domain(self, website: Optional[str], notes: Optional[str]) -> Optional[str]:
        """Extract domain from website URL or notes"""
        if website:
            domain = website.replace('https://', '').replace('http://', '').replace('www.', '')
            domain = domain.split('/')[0].split('?')[0].strip()
            if domain:
                return domain
        
        if notes:
            for line in notes.split('|'):
                if 'Domain:' in line:
                    domain = line.split('Domain:')[1].strip()
                    if domain:
                        return domain.split()[0]
        
        return None
    
    def find_linkedin_url(self, company_name: str, website: Optional[str]) -> Optional[str]:
        """Try to construct LinkedIn URL from company name"""
        # Simplified - in production, would use search API
        # For now, return None and let user provide URLs
        return None
    
    async def discover_atl_contacts_for_lead(self, lead: Lead) -> Dict[str, Any]:
        """Discover ATL contacts for a lead via LinkedIn"""
        # Check if we have LinkedIn info
        linkedin_url = None
        
        # Try to find LinkedIn URL from additional_data or notes
        if lead.additional_data and lead.additional_data.get('linkedin_url'):
            linkedin_url = lead.additional_data['linkedin_url']
        
        # If no LinkedIn URL, try to construct from company name
        if not linkedin_url:
            linkedin_url = self.find_linkedin_url(lead.company_name, lead.company_website)
        
        if not linkedin_url:
            return {
                'status': 'skipped',
                'reason': 'No LinkedIn URL found',
                'lead_id': lead.id,
                'company': lead.company_name
            }
        
        try:
            # Use LinkedIn scraper to discover ATL contacts
            result = self.linkedin_scraper.discover_atl_contacts(
                company_linkedin_url=linkedin_url,
                include_titles=None  # Use defaults: CEO, VP, Director, etc.
            )
            
            contacts = result.get('contacts', [])
            
            if contacts:
                # Store discovered contacts in lead
                if not lead.additional_data:
                    lead.additional_data = {}
                
                lead.additional_data['atl_contacts'] = contacts
                lead.additional_data['atl_discovered_at'] = datetime.now().isoformat()
                
                # Update contact info from first ATL contact (highest priority)
                if contacts and contacts[0].get('name'):
                    lead.contact_name = contacts[0]['name']
                    lead.contact_title = contacts[0].get('title', '')
                    lead.contact_phone = contacts[0].get('phone', '')
                    # LinkedIn URL as proxy identifier
                    if contacts[0].get('profile_url'):
                        if not lead.additional_data.get('linkedin_urls'):
                            lead.additional_data['linkedin_urls'] = []
                        lead.additional_data['linkedin_urls'].append(contacts[0]['profile_url'])
                
                self.db.commit()
                
                return {
                    'status': 'success',
                    'lead_id': lead.id,
                    'company': lead.company_name,
                    'contacts_found': len(contacts),
                    'top_contact': contacts[0].get('name') if contacts else None
                }
            else:
                return {
                    'status': 'no_contacts',
                    'lead_id': lead.id,
                    'company': lead.company_name
                }
                
        except Exception as e:
            logger.error(f"ATL discovery failed for lead {lead.id}: {e}")
            self.db.rollback()
            return {
                'status': 'error',
                'lead_id': lead.id,
                'company': lead.company_name,
                'error': str(e)
            }
    
    async def enrich_lead_with_email(self, lead: Lead) -> Dict[str, Any]:
        """Enrich a lead that has an email"""
        try:
            result = await self.enrichment_agent.enrich(
                email=lead.contact_email,
                lead_id=lead.id
            )
            
            if result.enriched_data:
                enriched = result.enriched_data
                
                # Update contact info
                if enriched.get('first_name') or enriched.get('last_name'):
                    name_parts = []
                    if enriched.get('first_name'):
                        name_parts.append(enriched['first_name'])
                    if enriched.get('last_name'):
                        name_parts.append(enriched['last_name'])
                    if name_parts:
                        lead.contact_name = ' '.join(name_parts)
                
                if enriched.get('title'):
                    lead.contact_title = enriched['title']
                
                if enriched.get('phone'):
                    lead.contact_phone = enriched.get('phone')
                
                # Store enrichment metadata
                if not lead.additional_data:
                    lead.additional_data = {}
                
                lead.additional_data['enrichment'] = {
                    'sources': result.sources,
                    'confidence': result.confidence_score,
                    'completeness': result.completeness_score,
                    'enriched_at': datetime.now().isoformat()
                }
                
                self.db.commit()
                
                return {
                    'status': 'success',
                    'lead_id': lead.id,
                    'company': lead.company_name,
                    'confidence': result.confidence_score
                }
            else:
                return {
                    'status': 'no_data',
                    'lead_id': lead.id,
                    'company': lead.company_name
                }
                
        except Exception as e:
            logger.error(f"Enrichment failed for lead {lead.id}: {e}")
            self.db.rollback()
            return {
                'status': 'error',
                'lead_id': lead.id,
                'company': lead.company_name,
                'error': str(e)
            }
    
    async def run_pipeline(
        self,
        csv_file: Optional[str] = None,
        skip_import: bool = False,
        limit: int = 0
    ) -> Dict[str, Any]:
        """Run the complete pipeline"""
        
        # Step 1: Import CSV
        if not skip_import and csv_file:
            if not self.import_csv(csv_file):
                return {'status': 'import_failed'}
        elif skip_import:
            print("\n⏭️  Skipping CSV import")
        
        # Step 2: Get leads needing processing
        print(f"\n🔍 Finding leads to process...")
        
        # Leads with emails (enrich with Apollo)
        leads_with_emails = self.db.query(Lead).filter(
            and_(
                Lead.contact_email.isnot(None),
                Lead.contact_email != '',
                Lead.contact_name.is_(None)  # Not yet enriched
            )
        )
        
        # Leads without emails but with websites (discover via LinkedIn)
        leads_without_emails = self.db.query(Lead).filter(
            and_(
                or_(
                    Lead.contact_email.is_(None),
                    Lead.contact_email == ''
                ),
                Lead.company_website.isnot(None),
                Lead.company_website != ''
            )
        )
        
        if limit > 0:
            leads_with_emails = leads_with_emails.limit(limit)
            leads_without_emails = leads_without_emails.limit(limit)
        
        leads_with_emails = leads_with_emails.all()
        leads_without_emails = leads_without_emails.all()
        
        total = len(leads_with_emails) + len(leads_without_emails)
        
        if total == 0:
            print("✅ No leads need processing")
            return {'status': 'no_leads'}
        
        print(f"📊 Found {len(leads_with_emails)} leads with emails (Apollo enrichment)")
        print(f"📊 Found {len(leads_without_emails)} leads without emails (LinkedIn discovery)")
        
        # Step 3: Enrich leads with emails
        if leads_with_emails:
            print(f"\n🔵 Enriching {len(leads_with_emails)} leads with Apollo...")
            for lead in leads_with_emails[:10]:  # Process first 10
                result = await self.enrich_lead_with_email(lead)
                if result['status'] == 'success':
                    self.stats['apollo_enriched'] += 1
                elif result['status'] == 'error':
                    self.stats['failed'] += 1
                else:
                    self.stats['skipped'] += 1
        
        # Step 4: Discover ATL contacts for leads without emails
        if leads_without_emails:
            print(f"\n🔵 Discovering ATL contacts for {len(leads_without_emails)} companies via LinkedIn...")
            print("⚠️  Note: LinkedIn discovery requires LinkedIn company URLs")
            print("   You can add LinkedIn URLs to lead notes or additional_data")
            
            for lead in leads_without_emails[:5]:  # Process first 5
                result = await self.discover_atl_contacts_for_lead(lead)
                if result['status'] == 'success':
                    self.stats['linkedin_discovered'] += 1
                elif result['status'] == 'skipped':
                    self.stats['skipped'] += 1
                else:
                    self.stats['failed'] += 1
        
        # Print summary
        duration = (datetime.now() - self.stats['start_time']).total_seconds()
        
        print(f"\n{'='*60}")
        print(f"📊 Pipeline Summary")
        print(f"{'='*60}")
        print(f"✅ Imported:        {self.stats['imported']}")
        print(f"🔵 Apollo Enriched: {self.stats['apollo_enriched']}")
        print(f"🔵 LinkedIn ATL:    {self.stats['linkedin_discovered']}")
        print(f"⚠️  Skipped:         {self.stats['skipped']}")
        print(f"❌ Failed:           {self.stats['failed']}")
        print(f"⏱️  Duration:         {duration:.2f}s")
        print(f"{'='*60}\n")
        
        return {
            'status': 'complete',
            'stats': self.stats
        }


async def main():
    parser = argparse.ArgumentParser(description='Full pipeline: Import → Discover → Enrich')
    parser.add_argument(
        '--csv-file',
        default='companies_ready_to_import.csv',
        help='CSV file to import'
    )
    parser.add_argument(
        '--skip-import',
        action='store_true',
        help='Skip CSV import step'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=0,
        help='Limit number of leads to process (0 = all)'
    )
    
    args = parser.parse_args()
    
    # Check server
    try:
        response = requests.get("http://localhost:8001/api/health", timeout=2)
        if response.status_code != 200:
            print("❌ Server not healthy")
            sys.exit(1)
    except:
        print("❌ Server not running at http://localhost:8001")
        print("   Start server: python3 start_server.py")
        sys.exit(1)
    
    # Initialize database
    db = SessionLocal()
    
    try:
        service = FullPipelineService(db)
        result = await service.run_pipeline(
            csv_file=args.csv_file if not args.skip_import else None,
            skip_import=args.skip_import,
            limit=args.limit
        )
        
        if result['status'] == 'complete':
            print("✅ Pipeline completed successfully!")
        elif result['status'] == 'no_leads':
            print("ℹ️  No leads need processing")
        elif result['status'] == 'import_failed':
            print("❌ Pipeline failed at import step")
            sys.exit(1)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        db.close()
        await service.apollo_service.close()


if __name__ == "__main__":
    asyncio.run(main())

