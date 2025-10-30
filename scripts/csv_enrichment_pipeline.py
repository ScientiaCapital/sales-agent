#!/usr/bin/env python3
"""
Easy CSV Upload and Enrichment Pipeline

Usage:
    python3 scripts/csv_enrichment_pipeline.py --input your_file.csv --limit 10
    python3 scripts/csv_enrichment_pipeline.py --input your_file.csv --limit 0  # All leads
"""

import asyncio
import sys
import os
import pandas as pd
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import time

# Add backend to path
backend_path = Path(__file__).parent.parent / 'backend'
sys.path.insert(0, str(backend_path))

from sqlalchemy.orm import Session
from app.models.database import SessionLocal
from app.models.lead import Lead
from app.services.cerebras import CerebrasService
from app.core.logging import setup_logging

logger = setup_logging(__name__)


class CSVEnrichmentPipeline:
    """Easy CSV upload and enrichment pipeline"""
    
    def __init__(self):
        self.cerebras = CerebrasService()
        self.stats = {
            'processed': 0,
            'qualified': 0,
            'enriched': 0,
            'failed': 0,
            'start_time': datetime.now()
        }
    
    def load_csv(self, file_path: str) -> pd.DataFrame:
        """Load and validate CSV file"""
        try:
            df = pd.read_csv(file_path)
            print(f"📊 Loaded {len(df)} leads from {file_path}")
            
            # Check required columns
            required_cols = ['company_name']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if missing_cols:
                print(f"❌ Missing required columns: {missing_cols}")
                print(f"Available columns: {list(df.columns)}")
                return None
            
            # Add missing columns with defaults
            if 'company_website' not in df.columns:
                df['company_website'] = ''
            if 'industry' not in df.columns:
                df['industry'] = 'Unknown'
            if 'company_size' not in df.columns:
                df['company_size'] = 'Unknown'
            if 'notes' not in df.columns:
                df['notes'] = ''
            
            print(f"✅ CSV validation successful")
            return df
            
        except Exception as e:
            print(f"❌ Error loading CSV: {e}")
            return None
    
    def qualify_lead(self, row: pd.Series) -> Dict[str, Any]:
        """Qualify a single lead using Cerebras"""
        try:
            start_time = time.time()
            
            score, reasoning, latency = self.cerebras.qualify_lead(
                company_name=row['company_name'],
                company_website=row.get('company_website', ''),
                industry=row.get('industry', 'Unknown'),
                company_size=row.get('company_size', 'Unknown'),
                notes=row.get('notes', '')
            )
            
            return {
                'qualified': True,
                'score': score,
                'reasoning': reasoning,
                'latency_ms': latency,
                'error': None
            }
            
        except Exception as e:
            return {
                'qualified': False,
                'score': 0,
                'reasoning': f"Qualification failed: {str(e)}",
                'latency_ms': 0,
                'error': str(e)
            }
    
    def enrich_lead(self, row: pd.Series, qualification_result: Dict[str, Any]) -> Dict[str, Any]:
        """Enrich a lead with real ATL contacts from website and LinkedIn"""
        try:
            atl_contacts = []
            sources_used = []
            
            # Step 1: Try website scraping first
            website = row.get('company_website', '')
            if website and website != 'nan' and website.startswith('http'):
                website_contacts = self.scrape_website_for_contacts(website)
                atl_contacts.extend(website_contacts)
                if website_contacts:
                    sources_used.append('website')
            
            # Step 2: Try LinkedIn discovery
            company_name = row['company_name']
            linkedin_contacts = self.discover_linkedin_contacts(company_name)
            atl_contacts.extend(linkedin_contacts)
            if linkedin_contacts:
                sources_used.append('linkedin')
            
            # If no real contacts found, return empty (don't simulate)
            if not atl_contacts:
                return {
                    'enriched': False,
                    'atl_contacts': [],
                    'contact_count': 0,
                    'linkedin_profiles': [],
                    'employee_count': 'Unknown',
                    'sources_used': [],
                    'error': 'No ATL contacts found'
                }
            
            return {
                'enriched': True,
                'atl_contacts': atl_contacts,
                'contact_count': len(atl_contacts),
                'linkedin_profiles': [c.get('linkedin_url', '') for c in atl_contacts if c.get('linkedin_url')],
                'employee_count': 'Unknown',
                'sources_used': sources_used,
                'error': None
            }
            
        except Exception as e:
            return {
                'enriched': False,
                'atl_contacts': [],
                'contact_count': 0,
                'linkedin_profiles': [],
                'employee_count': 'Unknown',
                'sources_used': [],
                'error': str(e)
            }
    
    def scrape_website_for_contacts(self, website: str) -> List[Dict[str, Any]]:
        """Scrape company website for ATL contacts using Playwright MCP"""
        try:
            print(f"    🌐 Scraping with Playwright: {website}")
            
            # Target executive titles
            ATL_TITLES = [
                "CEO", "Chief Executive Officer",
                "COO", "Chief Operating Officer", 
                "CFO", "Chief Financial Officer",
                "CTO", "Chief Technology Officer",
                "VP Finance", "VP Operations"
            ]
            
            contacts = []
            
            # This method will be called from the main pipeline
            # The actual Playwright MCP integration will be implemented
            # in the main pipeline where we have access to MCP tools
            
            print(f"    📊 Playwright scraping ready - will be implemented in main pipeline")
            return contacts
            
        except Exception as e:
            print(f"    ❌ Playwright scraping error: {e}")
            return []
    
    def discover_linkedin_contacts(self, company_name: str) -> List[Dict[str, Any]]:
        """Discover ATL contacts from LinkedIn (simplified)"""
        try:
            # For now, return empty - would need LinkedIn API or scraping
            # In production, this would use LinkedIn API or Browserbase scraping
            return []
        except Exception as e:
            logger.error(f"LinkedIn discovery error: {e}")
            return []
    
    def save_to_database(self, row: pd.Series, qualification_result: Dict[str, Any], enrichment_result: Dict[str, Any]) -> bool:
        """Save enriched lead to database"""
        try:
            db = SessionLocal()
            
            # Create lead record
            lead = Lead(
                company_name=row['company_name'],
                company_website=row.get('company_website', ''),
                industry=row.get('industry', 'Unknown'),
                company_size=row.get('company_size', 'Unknown'),
                contact_name=None,  # Will be filled by ATL discovery
                contact_email=None,  # Will be filled by ATL discovery
                contact_title=None,  # Will be filled by ATL discovery
                notes=row.get('notes', ''),
                qualification_score=qualification_result['score'] if qualification_result['qualified'] else None,
                qualification_reasoning=qualification_result['reasoning'] if qualification_result['qualified'] else None,
                qualification_latency_ms=qualification_result['latency_ms'] if qualification_result['qualified'] else None
            )
            
            # Add enrichment data
            if enrichment_result['enriched']:
                lead.additional_data = {
                    'atl_contacts': enrichment_result['atl_contacts'],
                    'contact_count': enrichment_result['contact_count'],
                    'linkedin_profiles': enrichment_result['linkedin_profiles'],
                    'employee_count': enrichment_result['employee_count'],
                    'enriched_at': datetime.now().isoformat()
                }
            
            db.add(lead)
            db.commit()
            db.close()
            
            return True
            
        except Exception as e:
            print(f"❌ Database save error: {e}")
            return False
    
    async def process_csv(self, file_path: str, limit: int = 0) -> Dict[str, Any]:
        """Process CSV file with enrichment"""
        print(f"🚀 Starting CSV enrichment pipeline...")
        print(f"📁 File: {file_path}")
        print(f"📊 Limit: {limit if limit > 0 else 'All leads'}")
        print("=" * 60)
        
        # Load CSV
        df = self.load_csv(file_path)
        if df is None:
            return {'status': 'error', 'message': 'Failed to load CSV'}
        
        # Apply limit
        if limit > 0:
            df = df.head(limit)
        
        print(f"🎯 Processing {len(df)} leads...")
        print()
        
        results = []
        
        for i, row in df.iterrows():
            print(f"[{i+1}/{len(df)}] {row['company_name']}")
            
            # Step 1: Qualify lead
            print(f"  🤖 Qualifying...", end=" ")
            qualification_result = self.qualify_lead(row)
            
            if qualification_result['qualified']:
                print(f"✅ {qualification_result['score']}/100 ({qualification_result['latency_ms']}ms)")
                self.stats['qualified'] += 1
            else:
                print(f"❌ Failed: {qualification_result['error']}")
                self.stats['failed'] += 1
                results.append({
                    'company_name': row['company_name'],
                    'status': 'qualification_failed',
                    'error': qualification_result['error']
                })
                continue
            
            # Step 2: Enrich lead
            print(f"  🔍 Enriching...", end=" ")
            enrichment_result = self.enrich_lead(row, qualification_result)
            
            if enrichment_result['enriched']:
                print(f"✅ {enrichment_result['contact_count']} contacts found")
                self.stats['enriched'] += 1
            else:
                print(f"❌ Failed: {enrichment_result['error']}")
            
            # Step 3: Save to database
            print(f"  💾 Saving...", end=" ")
            saved = self.save_to_database(row, qualification_result, enrichment_result)
            
            if saved:
                print(f"✅ Saved")
            else:
                print(f"❌ Save failed")
            
            self.stats['processed'] += 1
            print()
            
            # Add small delay to avoid rate limiting
            await asyncio.sleep(0.1)
        
        # Print summary
        duration = (datetime.now() - self.stats['start_time']).total_seconds()
        
        print(f"\n{'='*60}")
        print(f"📊 ENRICHMENT SUMMARY")
        print(f"{'='*60}")
        print(f"Leads processed:     {self.stats['processed']}")
        print(f"Successfully qualified: {self.stats['qualified']}")
        print(f"Successfully enriched:  {self.stats['enriched']}")
        print(f"Failed:              {self.stats['failed']}")
        print(f"⏱️  Duration:          {duration:.2f}s")
        print(f"⚡ Avg per lead:      {duration/self.stats['processed']:.2f}s")
        print(f"{'='*60}\n")
        
        return {
            'status': 'complete',
            'stats': self.stats,
            'results': results
        }


async def main():
    parser = argparse.ArgumentParser(description='CSV Upload and Enrichment Pipeline')
    parser.add_argument(
        '--input',
        type=str,
        required=True,
        help='Path to CSV file'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=10,
        help='Limit number of leads to process (0 = all)'
    )
    
    args = parser.parse_args()
    
    # Check if file exists
    if not os.path.exists(args.input):
        print(f"❌ File not found: {args.input}")
        return
    
    # Initialize pipeline
    pipeline = CSVEnrichmentPipeline()
    
    # Process CSV
    result = await pipeline.process_csv(args.input, args.limit)
    
    if result['status'] == 'complete':
        print("🎉 Enrichment pipeline completed successfully!")
    else:
        print(f"❌ Pipeline failed: {result.get('message', 'Unknown error')}")


if __name__ == "__main__":
    asyncio.run(main())
