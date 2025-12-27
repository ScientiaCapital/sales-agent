#!/usr/bin/env python3
"""
VLM Batch Enrichment Script
============================
Uses Vision Language Models via OpenRouter to extract contacts + ICP signals
from website screenshots.

Targets: PLATINUM, GOLD, SILVER tier leads
Cost: ~$0.001 per screenshot via OpenRouter

Methods:
1. Browserbase - Takes screenshots of team/about pages
2. VLM (InternVL/Qwen) - Extracts contacts + signals from screenshots

Usage:
    python3 enrich_vlm_batch.py --tier PLATINUM          # PLATINUM only
    python3 enrich_vlm_batch.py --tier PLATINUM,GOLD    # P + G
    python3 enrich_vlm_batch.py --all                    # All P/G/S
    python3 enrich_vlm_batch.py --limit 10 --tier PLATINUM  # Test 10

Author: Tim + Claude
Date: Dec 23, 2024
"""

import asyncio
import os
import sys
import argparse
import json
import base64
import re
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx

sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from supabase import create_client

# Import existing services
from app.services.browserbase_team_scraper import BrowserbaseTeamScraper

# Config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# VLM Config
VLM_MODEL = "qwen/qwen2.5-vl-72b-instruct"  # Best price/performance
VLM_FALLBACK = "opengvlab/internvl3-14b"

# Pages to screenshot
TEAM_PAGES = ["/team", "/our-team", "/about", "/about-us", "/leadership", "/staff"]

# ATL title patterns
ATL_PATTERNS = [
    r'\b(ceo|chief executive)\b',
    r'\b(president)\b',
    r'\b(owner|co-owner)\b',
    r'\b(founder|co-founder)\b',
    r'\b(partner|managing partner)\b',
    r'\b(principal)\b',
    r'\bvp\b|\bvice president\b',
    r'\bdirector\b',
    r'\b(gm|general manager)\b',
]

# VLM Prompt
VLM_PROMPT = """Analyze this screenshot of a business website.

YOUR TASK: Extract ALL people visible on this page and detect business signals.

FOR EACH PERSON FOUND:
- name: Full name exactly as shown
- title: Job title if visible
- email: Email if visible  
- is_atl: true if title suggests decision-maker (CEO, Owner, President, VP, Director, Partner, Founder)

ALSO DETECT THESE BUSINESS SIGNALS (true/false):
- has_commercial: Commercial services mentioned
- has_industrial: Industrial/manufacturing services
- has_generators: Generator/backup power services
- has_design_build: Design-build capabilities
- has_engineering: In-house engineering
- has_medical_specialization: Healthcare/medical gas
- has_building_automation: BMS/controls
- has_awards: Awards or certifications visible
- has_emergency_service: 24/7 or emergency service
- has_oem_partnerships: Dealer/partner badges (Carrier, Generac, etc)

OUTPUT ONLY THIS JSON:
{
  "contacts": [
    {"name": "John Smith", "title": "CEO", "email": null, "is_atl": true}
  ],
  "signals": {
    "has_commercial": false,
    "has_industrial": false,
    "has_generators": false,
    "has_design_build": false,
    "has_engineering": false,
    "has_medical_specialization": false,
    "has_building_automation": false,
    "has_awards": false,
    "has_emergency_service": false,
    "has_oem_partnerships": false
  }
}

If no people visible, return empty contacts array. Always return signals."""


def is_atl_title(title: str) -> bool:
    """Check if title indicates decision maker"""
    if not title:
        return False
    title_lower = title.lower()
    for pattern in ATL_PATTERNS:
        if re.search(pattern, title_lower):
            return True
    return False


async def call_vlm(image_base64: str, model: str = VLM_MODEL) -> Optional[Dict]:
    """Call OpenRouter VLM API with image"""
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://scientia.capital",
                    "X-Title": "Sales-Agent-VLM"
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "user",
                            "content": [
                                {"type": "text", "text": VLM_PROMPT},
                                {
                                    "type": "image_url",
                                    "image_url": {
                                        "url": f"data:image/png;base64,{image_base64}"
                                    }
                                }
                            ]
                        }
                    ],
                    "max_tokens": 2000,
                    "temperature": 0.1
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data['choices'][0]['message']['content']
                
                # Parse JSON from response
                try:
                    # Handle markdown code blocks
                    if "```json" in content:
                        json_start = content.index("```json") + 7
                        json_end = content.index("```", json_start)
                        content = content[json_start:json_end].strip()
                    elif "```" in content:
                        json_start = content.index("```") + 3
                        json_end = content.index("```", json_start)
                        content = content[json_start:json_end].strip()
                    
                    return json.loads(content)
                except (json.JSONDecodeError, ValueError):
                    # Try to find JSON in response
                    json_match = re.search(r'\{[\s\S]*\}', content)
                    if json_match:
                        return json.loads(json_match.group())
                    return None
            else:
                print(f"    VLM API error: {response.status_code}")
                return None
                
    except Exception as e:
        print(f"    VLM error: {e}")
        return None


async def take_screenshot(url: str, scraper: BrowserbaseTeamScraper) -> Optional[str]:
    """Take screenshot using Browserbase and return base64"""
    try:
        # Use browserbase to get screenshot
        result = await scraper.scrape_single_url(url)
        
        if result and result.get('screenshot_path'):
            screenshot_path = Path(result['screenshot_path'])
            if screenshot_path.exists():
                with open(screenshot_path, 'rb') as f:
                    return base64.b64encode(f.read()).decode('utf-8')
        
        return None
    except Exception as e:
        print(f"    Screenshot error: {e}")
        return None


async def enrich_company_vlm(company: Dict, scraper: BrowserbaseTeamScraper) -> Dict:
    """Enrich a company using VLM extraction"""
    results = {
        'company_id': company['company_id'],
        'company_name': company['company_name'],
        'contacts': [],
        'signals': {},
        'screenshots_taken': 0,
        'errors': []
    }
    
    domain = company.get('domain')
    if not domain:
        results['errors'].append('No domain')
        return results
    
    # Normalize domain
    if not domain.startswith('http'):
        domain = f'https://{domain}'
    base_url = domain.rstrip('/')
    
    # Try team pages
    for page in TEAM_PAGES:
        url = f"{base_url}{page}"
        
        try:
            # Take screenshot
            screenshot_b64 = await take_screenshot(url, scraper)
            
            if screenshot_b64:
                results['screenshots_taken'] += 1
                
                # Call VLM
                vlm_result = await call_vlm(screenshot_b64)
                
                if vlm_result:
                    # Merge contacts
                    for contact in vlm_result.get('contacts', []):
                        # Ensure is_atl is set correctly
                        if not contact.get('is_atl'):
                            contact['is_atl'] = is_atl_title(contact.get('title', ''))
                        contact['source'] = 'vlm_extraction'
                        results['contacts'].append(contact)
                    
                    # Merge signals (any true wins)
                    for signal, value in vlm_result.get('signals', {}).items():
                        if value:
                            results['signals'][signal] = True
                
                # Found a working team page, can break
                if results['contacts']:
                    break
                    
        except Exception as e:
            results['errors'].append(f"{page}: {e}")
        
        await asyncio.sleep(0.5)  # Rate limit
    
    # Dedupe contacts by name
    seen_names = set()
    unique_contacts = []
    for c in results['contacts']:
        name = c.get('name', '').lower()
        if name and name not in seen_names:
            seen_names.add(name)
            unique_contacts.append(c)
    results['contacts'] = unique_contacts
    
    return results


async def save_vlm_results(results: Dict):
    """Save VLM enrichment results to Supabase"""
    company_id = results['company_id']
    
    # Update company with signals
    update_data = {
        'website_scraped_at': datetime.now().isoformat(),
        'ai_enriched_at': datetime.now().isoformat(),
    }
    
    # Add signals
    for signal, value in results.get('signals', {}).items():
        if signal.startswith('has_') and value:
            update_data[signal] = True
    
    supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
    
    # Save contacts
    for contact in results.get('contacts', []):
        if contact.get('name'):
            contact_data = {
                'company_id': company_id,
                'full_name': contact.get('name'),
                'title': contact.get('title'),
                'email': contact.get('email'),
                'is_atl': contact.get('is_atl', False),
                'source': 'vlm_extraction',
                'created_at': datetime.now().isoformat()
            }
            
            try:
                # Check for duplicates
                existing = supabase.table('dim_contacts')\
                    .select('contact_id')\
                    .eq('company_id', company_id)\
                    .ilike('full_name', contact.get('name', ''))\
                    .execute()
                
                if not existing.data:
                    supabase.table('dim_contacts').insert(contact_data).execute()
            except Exception as e:
                pass


async def main():
    parser = argparse.ArgumentParser(description='VLM batch enrichment')
    parser.add_argument('--tier', type=str, default='PLATINUM', 
                        help='Tiers to process (comma-separated): PLATINUM,GOLD,SILVER')
    parser.add_argument('--all', action='store_true', help='Process all P/G/S tiers')
    parser.add_argument('--limit', type=int, default=None, help='Limit companies')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be processed')
    parser.add_argument('--source', type=str, default=None, help='Filter by source')
    args = parser.parse_args()
    
    # Determine tiers
    if args.all:
        tiers = ['PLATINUM', 'GOLD', 'SILVER']
    else:
        tiers = [t.strip().upper() for t in args.tier.split(',')]
    
    print("=" * 70)
    print("VLM BATCH ENRICHMENT")
    print("=" * 70)
    print(f"Tiers: {', '.join(tiers)}")
    print(f"Model: {VLM_MODEL}")
    print(f"Cost: ~$0.001/screenshot")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get leads needing enrichment
    all_leads = []
    for tier in tiers:
        query = supabase.table('dim_companies')\
            .select('company_id, company_name, domain, icp_tier, icp_score')\
            .eq('icp_tier', tier)\
            .is_('ai_enriched_at', 'null')\
            .not_.is_('domain', 'null')
        
        if args.source:
            query = query.eq('original_source', args.source)
        
        query = query.order('icp_score', desc=True)
        result = query.execute()
        all_leads.extend(result.data)
        print(f"  {tier}: {len(result.data)} leads")
    
    print(f"\nTotal to process: {len(all_leads)}")
    
    if args.limit:
        all_leads = all_leads[:args.limit]
        print(f"Limited to: {len(all_leads)}")
    
    # Cost estimate
    est_cost = len(all_leads) * 0.001
    print(f"Estimated cost: ${est_cost:.2f}")
    
    if args.dry_run:
        print("\n=== DRY RUN ===")
        for i, lead in enumerate(all_leads[:20], 1):
            print(f"  {i}. [{lead['icp_tier']}] {lead['company_name']} ({lead.get('domain')})")
        if len(all_leads) > 20:
            print(f"  ... and {len(all_leads) - 20} more")
        return
    
    # Confirm
    if len(all_leads) > 20 and not args.limit:
        confirm = input(f"\nProcess {len(all_leads)} leads for ~${est_cost:.2f}? (y/N): ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return
    
    # Initialize Browserbase scraper
    scraper = BrowserbaseTeamScraper()
    
    # Process leads
    success = 0
    failed = 0
    total_contacts = 0
    total_atl = 0
    
    for i, lead in enumerate(all_leads, 1):
        print(f"\n[{i}/{len(all_leads)}] [{lead['icp_tier']}] {lead['company_name']}...")
        
        try:
            results = await enrich_company_vlm(lead, scraper)
            
            if results['screenshots_taken'] > 0:
                await save_vlm_results(results)
                success += 1
                
                atl_count = sum(1 for c in results['contacts'] if c.get('is_atl'))
                total_contacts += len(results['contacts'])
                total_atl += atl_count
                
                signals = [k for k, v in results.get('signals', {}).items() if v]
                
                print(f"  ✅ {len(results['contacts'])} contacts ({atl_count} ATL)")
                if signals:
                    print(f"  📊 {', '.join(signals)}")
            else:
                failed += 1
                print(f"  ⚠️ No screenshots captured")
                
        except Exception as e:
            failed += 1
            print(f"  ❌ Error: {e}")
        
        # Rate limit
        await asyncio.sleep(1)
    
    # Summary
    print("\n" + "=" * 70)
    print("VLM ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"  Processed: {len(all_leads)}")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")
    print(f"  Contacts found: {total_contacts}")
    print(f"  ATL contacts: {total_atl}")
    print(f"  Estimated cost: ${success * 0.001:.2f}")


if __name__ == '__main__':
    asyncio.run(main())
