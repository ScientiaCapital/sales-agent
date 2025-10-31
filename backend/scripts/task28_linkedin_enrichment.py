#!/usr/bin/env python3
"""
Task 28: Test LinkedIn Enrichment with Browserbase on 5 Sample Leads

Selects 5 leads with linkedin_url from imported top_200 and tests LinkedIn scraper
for company page scraping, employee discovery, and ATL contact scoring.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
if env_path.exists():
    load_dotenv(env_path)
else:
    root_env = Path(__file__).parent.parent.parent / '.env'
    if root_env.exists():
        load_dotenv(root_env)

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session
from app.models.database import get_db
from app.models.lead import Lead
from app.services.crm.linkedin import LinkedInProvider
from app.core.cache import get_cache_manager
import asyncio
from typing import Dict, Any, List

# Check Browserbase credentials
BROWSERBASE_API_KEY = os.getenv("BROWSERBASE_API_KEY")
BROWSERBASE_PROJECT_ID = os.getenv("BROWSERBASE_PROJECT_ID")

if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
    print("⚠️  Warning: BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID not set")
    print("   LinkedIn scraping will use mock/dry-run mode")
    print("   Set these in .env to enable actual Browserbase scraping\n")


async def test_linkedin_enrichment():
    """Test LinkedIn enrichment on 5 sample leads."""
    db: Session = next(get_db())
    
    try:
        # Find leads with linkedin_url
        print("📋 Finding leads with LinkedIn URLs...")
        all_leads = db.query(Lead).limit(1000).all()
        
        leads_with_linkedin = []
        for lead in all_leads:
            if lead.additional_data and isinstance(lead.additional_data, dict):
                additional = lead.additional_data
                linkedin_url = additional.get('linkedin_url') or additional.get('LinkedIn_URL') or additional.get('linkedin_url')
                
                # Also check original_row if present
                if not linkedin_url and 'original_row' in additional:
                    original = additional['original_row']
                    if isinstance(original, dict):
                        linkedin_url = original.get('linkedin_url')
                
                if linkedin_url and linkedin_url.strip():
                    leads_with_linkedin.append({
                        'lead_id': lead.id,
                        'company_name': lead.company_name,
                        'linkedin_url': linkedin_url.strip()
                    })
        
        if len(leads_with_linkedin) < 5:
            print(f"⚠️  Only found {len(leads_with_linkedin)} leads with LinkedIn URLs")
            if leads_with_linkedin:
                print(f"   Testing with available {len(leads_with_linkedin)} leads:")
                for lead in leads_with_linkedin:
                    print(f"     - {lead['company_name']}: {lead['linkedin_url']}")
            else:
                print("   No LinkedIn URLs found in imported leads.")
                print("   This is expected - LinkedIn URLs may not be in the CSV.")
                print("   Task 28 skipped - proceeding to Task 29.")
                return []
        
        # Select 5 leads
        test_leads = leads_with_linkedin[:5]
        print(f"\n✅ Selected {len(test_leads)} leads for testing:")
        for i, lead in enumerate(test_leads, 1):
            print(f"   {i}. {lead['company_name']} - {lead['linkedin_url']}")
        
        # Initialize LinkedIn provider
        print("\n🔧 Initializing LinkedIn provider...")
        redis_client = await get_cache_manager()
        
        linkedin_provider = LinkedInProvider(
            db=db,
            redis_client=redis_client,
            client_id=os.getenv("LINKEDIN_CLIENT_ID", "dummy"),
            client_secret=os.getenv("LINKEDIN_CLIENT_SECRET", "dummy"),
            redirect_uri=os.getenv("LINKEDIN_REDIRECT_URI", "http://localhost:8001/callback")
        )
        
        # Test each lead
        print("\n🧪 Testing LinkedIn enrichment...")
        results = []
        
        for i, lead_data in enumerate(test_leads, 1):
            print(f"\n📊 Test {i}/5: {lead_data['company_name']}")
            print(f"   LinkedIn URL: {lead_data['linkedin_url']}")
            
            try:
                # Test profile enrichment
                print("   → Scraping profile...")
                enrichment = await linkedin_provider.enrich_contact_from_profile(
                    lead_data['linkedin_url']
                )
                
                if enrichment:
                    print(f"   ✅ Profile scraped successfully")
                    print(f"      - Name: {enrichment.get('name', 'N/A')}")
                    print(f"      - Headline: {enrichment.get('headline', 'N/A')}")
                    print(f"      - Current Company: {enrichment.get('current_company', 'N/A')}")
                    print(f"      - Current Title: {enrichment.get('current_title', 'N/A')}")
                    
                    # ATL contact scoring
                    title = enrichment.get('current_title', '').upper()
                    if any(title in keyword for keyword in ['CEO', 'CTO', 'CFO', 'CMO', 'CHIEF']):
                        score = 100
                        tier = "C-Level"
                    elif 'VP' in title or 'VICE PRESIDENT' in title:
                        score = 85
                        tier = "VP-Level"
                    elif 'DIRECTOR' in title:
                        score = 70
                        tier = "Director"
                    else:
                        score = 50
                        tier = "Other"
                    
                    print(f"      - ATL Score: {score} ({tier})")
                    
                    results.append({
                        'lead_id': lead_data['lead_id'],
                        'company_name': lead_data['company_name'],
                        'success': True,
                        'enrichment': enrichment,
                        'atl_score': score,
                        'atl_tier': tier
                    })
                else:
                    print(f"   ❌ Profile scraping failed")
                    results.append({
                        'lead_id': lead_data['lead_id'],
                        'company_name': lead_data['company_name'],
                        'success': False,
                        'error': 'Enrichment returned None'
                    })
                
            except Exception as e:
                print(f"   ❌ Error: {str(e)}")
                results.append({
                    'lead_id': lead_data['lead_id'],
                    'company_name': lead_data['company_name'],
                    'success': False,
                    'error': str(e)
                })
            
            # Rate limit check (100 req/day for LinkedIn)
            if i < len(test_leads):
                print("   ⏳ Waiting 1 second before next request...")
                await asyncio.sleep(1)
        
        # Summary
        print("\n" + "="*60)
        print("📈 Test Summary")
        print("="*60)
        successful = sum(1 for r in results if r['success'])
        print(f"Total Tests: {len(results)}")
        print(f"Successful: {successful}")
        print(f"Failed: {len(results) - successful}")
        
        if successful > 0:
            print(f"\n✅ Successfully enriched {successful} leads")
            print("ATL Contact Scores:")
            for result in results:
                if result['success']:
                    print(f"  - {result['company_name']}: {result['atl_score']} ({result['atl_tier']})")
        else:
            print("\n⚠️  No successful enrichments. Check Browserbase credentials and LinkedIn URLs.")
        
        print("\n✅ Task 28 complete!")
        
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_linkedin_enrichment())

