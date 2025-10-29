#!/usr/bin/env python3
"""
Batch Enrichment Script for Companies

Enriches leads with Apollo.io contacts. Supports two modes:
1. Email-only: Enrich contacts that already have emails
2. Company search: Find contacts using company domain (requires Apollo People Search)

Usage:
    python3 scripts/batch_enrich_companies.py [--mode email_only|company_search] [--limit N]

Examples:
    # Enrich leads with existing emails
    python3 scripts/batch_enrich_companies.py --mode email_only

    # Find contacts via company domain (if available)
    python3 scripts/batch_enrich_companies.py --mode company_search --limit 10

    # Enrich all leads
    python3 scripts/batch_enrich_companies.py --mode email_only --limit 0
"""
import asyncio
import sys
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import argparse

# Add backend to path
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.models.database import SessionLocal
from app.models.lead import Lead
from app.services.langgraph.agents.enrichment_agent import EnrichmentAgent
from app.services.apollo import ApolloService
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class BatchEnrichmentService:
    """Service for batch enriching companies with Apollo contacts"""
    
    def __init__(self, db: Session):
        self.db = db
        self.enrichment_agent = EnrichmentAgent()
        self.apollo_service = ApolloService()
        self.stats = {
            'total': 0,
            'enriched': 0,
            'failed': 0,
            'skipped': 0,
            'start_time': datetime.now()
        }
    
    def extract_domain(self, website: Optional[str], notes: Optional[str]) -> Optional[str]:
        """Extract domain from website URL or notes"""
        if website:
            # Extract domain from URL
            domain = website.replace('https://', '').replace('http://', '').replace('www.', '')
            domain = domain.split('/')[0].split('?')[0].strip()
            if domain:
                return domain
        
        # Try to extract from notes (format: "Domain: example.com")
        if notes:
            for line in notes.split('|'):
                if 'Domain:' in line:
                    domain = line.split('Domain:')[1].strip()
                    if domain:
                        return domain.split()[0]  # Take first word
        
        return None
    
    async def get_leads_needing_enrichment(
        self, 
        mode: str = "email_only",
        limit: int = 0
    ) -> List[Lead]:
        """Get leads that need enrichment"""
        query = self.db.query(Lead)
        
        if mode == "email_only":
            # Leads with emails but no contact_name (need enrichment)
            query = query.filter(
                and_(
                    Lead.contact_email.isnot(None),
                    Lead.contact_email != '',
                    Lead.contact_name.is_(None)
                )
            )
        elif mode == "company_search":
            # Leads without emails but with website/domain
            query = query.filter(
                and_(
                    Lead.contact_email.is_(None),
                    Lead.company_website.isnot(None)
                )
            )
        else:
            raise ValueError(f"Invalid mode: {mode}")
        
        if limit > 0:
            query = query.limit(limit)
        
        return query.all()
    
    async def enrich_lead_with_email(self, lead: Lead) -> Dict[str, Any]:
        """Enrich a lead that has an email"""
        try:
            result = await self.enrichment_agent.enrich(
                email=lead.contact_email,
                lead_id=lead.id
            )
            
            # Update lead with enriched data
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
                
                # Store enrichment metadata in additional_data
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
            logger.error(f"Failed to enrich lead {lead.id}: {e}")
            self.db.rollback()
            return {
                'status': 'error',
                'lead_id': lead.id,
                'company': lead.company_name,
                'error': str(e)
            }
    
    async def enrich_lead_via_domain(self, lead: Lead) -> Dict[str, Any]:
        """Enrich a lead by finding contacts via company domain using Apollo search"""
        domain = self.extract_domain(lead.company_website, lead.notes)
        
        if not domain:
            return {
                'status': 'skipped',
                'lead_id': lead.id,
                'company': lead.company_name,
                'reason': 'No domain found'
            }
        
        try:
            # Search for ATL contacts at company domain
            # Target: CEO, COO, CFO, CTO, VP Finance, VP Operations
            atl_titles = ["CEO", "COO", "CFO", "CTO", "VP Finance", "VP Operations", 
                         "Vice President Finance", "Vice President Operations"]
            
            contacts = await self.apollo_service.search_company_contacts(
                domain=domain,
                job_titles=atl_titles,
                max_results=10
            )
            
            if contacts:
                # Update lead with found contacts
                if not lead.additional_data:
                    lead.additional_data = {}
                
                lead.additional_data['apollo_contacts'] = contacts
                lead.additional_data['apollo_search_at'] = datetime.now().isoformat()
                
                # Update lead with top contact info
                top_contact = contacts[0]
                if top_contact.get('email'):
                    lead.contact_email = top_contact['email']
                if top_contact.get('name'):
                    lead.contact_name = top_contact['name']
                if top_contact.get('title'):
                    lead.contact_title = top_contact['title']
                if top_contact.get('phone'):
                    lead.contact_phone = top_contact['phone']
                
                self.db.commit()
                
                return {
                    'status': 'contacts_found',
                    'lead_id': lead.id,
                    'company': lead.company_name,
                    'domain': domain,
                    'contacts_found': len(contacts),
                    'top_contact': top_contact.get('name')
                }
            else:
                # Fallback: Enrich company data even if no contacts found
                company_data = await self.apollo_service.enrich_company(domain)
            
            # Note: Apollo doesn't have a direct "find all contacts at company" API
            # This would require Apollo People Search API or manual search
            # For now, we'll enrich company data and note that contacts need manual discovery
            
            # Update lead with company enrichment
            if company_data:
                if company_data.get('name') and not lead.company_name:
                    lead.company_name = company_data['name']
                
                if company_data.get('industry') and not lead.industry:
                    lead.industry = company_data['industry']
                
                if company_data.get('employee_count'):
                    # Map employee count to company_size
                    emp_count = company_data['employee_count']
                    if emp_count < 10:
                        lead.company_size = "1-10"
                    elif emp_count < 50:
                        lead.company_size = "10-50"
                    elif emp_count < 200:
                        lead.company_size = "50-200"
                    elif emp_count < 500:
                        lead.company_size = "200-500"
                    else:
                        lead.company_size = "500+"
                
                    # Store company enrichment data
                    if not lead.additional_data:
                        lead.additional_data = {}
                    
                    lead.additional_data['company_enrichment'] = {
                        'domain': domain,
                        'enriched_at': datetime.now().isoformat(),
                        'apollo_data': company_data
                    }
                    
                    self.db.commit()
                    
                    return {
                        'status': 'company_enriched',
                        'lead_id': lead.id,
                        'company': lead.company_name,
                        'domain': domain,
                        'note': 'Company data enriched. No ATL contacts found via Apollo search.'
                    }
                
                return {
                    'status': 'no_contacts',
                    'lead_id': lead.id,
                    'company': lead.company_name,
                    'domain': domain,
                    'note': 'No contacts found at domain'
                }
            
        except Exception as e:
            logger.error(f"Failed to enrich company for lead {lead.id}: {e}")
            self.db.rollback()
            return {
                'status': 'error',
                'lead_id': lead.id,
                'company': lead.company_name,
                'error': str(e)
            }
    
    async def enrich_batch(
        self,
        mode: str = "email_only",
        limit: int = 0,
        max_concurrency: int = 5
    ) -> Dict[str, Any]:
        """Enrich a batch of leads"""
        print(f"\n🔍 Finding leads needing enrichment (mode: {mode})...")
        leads = await self.get_leads_needing_enrichment(mode=mode, limit=limit)
        
        if not leads:
            print(f"✅ No leads found needing enrichment")
            return {'status': 'no_leads'}
        
        self.stats['total'] = len(leads)
        print(f"📊 Found {len(leads)} leads to enrich\n")
        
        # Process in batches
        results = []
        semaphore = asyncio.Semaphore(max_concurrency)
        
        async def process_lead(lead: Lead):
            async with semaphore:
                if mode == "email_only":
                    return await self.enrich_lead_with_email(lead)
                else:
                    return await self.enrich_lead_via_domain(lead)
        
        # Process all leads
        tasks = [process_lead(lead) for lead in leads]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in results:
            if isinstance(result, Exception):
                self.stats['failed'] += 1
                logger.error(f"Enrichment exception: {result}")
            elif result['status'] == 'success':
                self.stats['enriched'] += 1
            elif result['status'] == 'skipped':
                self.stats['skipped'] += 1
            elif result['status'] == 'error':
                self.stats['failed'] += 1
            else:
                self.stats['enriched'] += 1  # company_enriched, no_data, etc.
        
        # Print summary
        duration = (datetime.now() - self.stats['start_time']).total_seconds()
        
        print(f"\n{'='*60}")
        print(f"📊 Enrichment Summary")
        print(f"{'='*60}")
        print(f"Total leads:     {self.stats['total']}")
        print(f"✅ Enriched:     {self.stats['enriched']}")
        print(f"⚠️  Skipped:      {self.stats['skipped']}")
        print(f"❌ Failed:        {self.stats['failed']}")
        print(f"⏱️  Duration:      {duration:.2f}s")
        print(f"{'='*60}\n")
        
        return {
            'status': 'complete',
            'stats': self.stats,
            'results': results
        }


async def main():
    parser = argparse.ArgumentParser(description='Batch enrich companies with Apollo contacts')
    parser.add_argument(
        '--mode',
        choices=['email_only', 'company_search'],
        default='email_only',
        help='Enrichment mode: email_only (enrich existing emails) or company_search (find contacts via domain)'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Limit number of leads to process (0 = all)'
    )
    parser.add_argument(
        '--concurrency',
        type=int,
        default=5,
        help='Max concurrent enrichments (default: 5)'
    )
    
    args = parser.parse_args()
    
    # Initialize database
    db = SessionLocal()
    
    try:
        service = BatchEnrichmentService(db)
        result = await service.enrich_batch(
            mode=args.mode,
            limit=args.limit,
            max_concurrency=args.concurrency
        )
        
        if result['status'] == 'complete':
            print("✅ Batch enrichment completed successfully!")
        elif result['status'] == 'no_leads':
            print("ℹ️  No leads need enrichment")
        
    except Exception as e:
        logger.error(f"Batch enrichment failed: {e}", exc_info=True)
        print(f"❌ Error: {e}")
        sys.exit(1)
    finally:
        db.close()
        await service.apollo_service.close()


if __name__ == "__main__":
    asyncio.run(main())

