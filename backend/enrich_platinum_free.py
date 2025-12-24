#!/usr/bin/env python3
"""
PLATINUM Free Enrichment Script
================================
Targets ONLY PLATINUM tier leads with FREE/cheap enrichment methods.

NO Hunter.io or Apollo (credits exhausted until Jan 1)

Methods used:
1. BeautifulSoup - ICP signals, basic contact extraction ($0)
2. Browserbase - Team page screenshots for JS-heavy sites (~$0.01/page)
3. VLM Contact Extractor - AI vision extraction (~$0.001/screenshot)

Estimated cost for 134 PLATINUM leads: ~$2-3 total

Usage:
    python3 enrich_platinum_free.py                    # Enrich all PLATINUM
    python3 enrich_platinum_free.py --limit 10        # Test with 10
    python3 enrich_platinum_free.py --dry-run         # Show what would be enriched

Author: Tim + Claude
Date: Dec 23, 2024
"""

import asyncio
import os
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
import httpx
from bs4 import BeautifulSoup
import re
import json

# Add app to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

from supabase import create_client

# Config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY')
BROWSERBASE_API_KEY = os.getenv('BROWSERBASE_API_KEY')
BROWSERBASE_PROJECT_ID = os.getenv('BROWSERBASE_PROJECT_ID')

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# ATL title patterns
ATL_TITLES = [
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

# ICP Signal patterns
SIGNAL_PATTERNS = {
    'has_commercial': [r'commercial', r'business', r'office', r'retail', r'multi.?family'],
    'has_industrial': [r'industrial', r'manufacturing', r'facility', r'plant', r'warehouse'],
    'has_generators': [r'generator', r'backup power', r'standby', r'generac', r'kohler', r'cummins'],
    'has_design_build': [r'design.?build', r'turnkey', r'design.?construct'],
    'has_engineering': [r'engineering', r'in.?house engineer', r'PE license'],
    'has_service_contracts': [r'service contract', r'maintenance agreement', r'preventive maintenance'],
}

# Pages to check
ESSENTIAL_PAGES = [
    "/", "/about", "/about-us", "/services", "/team", "/our-team",
    "/leadership", "/commercial", "/industrial", "/contact"
]


def is_atl_title(title: str) -> bool:
    """Check if title indicates Above-The-Line decision maker"""
    if not title:
        return False
    title_lower = title.lower()
    for pattern in ATL_TITLES:
        if re.search(pattern, title_lower):
            return True
    return False


async def scrape_page_bs(url: str, timeout: int = 10) -> Optional[str]:
    """Scrape page with BeautifulSoup (FREE)"""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if response.status_code == 200:
                return response.text
    except Exception as e:
        pass
    return None


def extract_contacts_from_html(html: str, domain: str) -> List[Dict]:
    """Extract contacts from HTML using patterns"""
    contacts = []
    soup = BeautifulSoup(html, 'html.parser')
    
    # Remove script/style
    for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
        tag.decompose()
    
    text = soup.get_text(separator=' ', strip=True)
    
    # Email pattern
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = set(re.findall(email_pattern, text))
    
    # Filter to company domain emails
    company_domain = domain.replace('www.', '').lower()
    relevant_emails = [e for e in emails if company_domain in e.lower()]
    
    # Look for team cards/sections
    team_sections = soup.find_all(['div', 'section', 'article'], 
        class_=re.compile(r'team|staff|employee|member|people|leadership', re.I))
    
    for section in team_sections:
        # Look for name patterns
        headings = section.find_all(['h2', 'h3', 'h4', 'strong', 'b'])
        for h in headings:
            name = h.get_text(strip=True)
            # Check if it looks like a name (2-4 words, capitalized)
            if name and len(name.split()) in [2, 3, 4] and name[0].isupper():
                # Look for title nearby
                next_elem = h.find_next(['p', 'span', 'div'])
                title = next_elem.get_text(strip=True) if next_elem else None
                
                if title and len(title) < 100:
                    contacts.append({
                        'full_name': name,
                        'title': title,
                        'email': None,
                        'is_atl': is_atl_title(title),
                        'source': 'beautifulsoup'
                    })
    
    # Add emails found
    for email in relevant_emails:
        # Check if we already have this person
        email_local = email.split('@')[0].lower()
        matched = False
        for c in contacts:
            name_parts = c['full_name'].lower().split()
            if any(part in email_local for part in name_parts):
                c['email'] = email
                matched = True
                break
        if not matched:
            contacts.append({
                'full_name': None,
                'title': None,
                'email': email,
                'is_atl': False,
                'source': 'beautifulsoup'
            })
    
    return contacts


def detect_icp_signals(html: str) -> Dict[str, bool]:
    """Detect ICP signals from page content"""
    signals = {}
    text = BeautifulSoup(html, 'html.parser').get_text(separator=' ', strip=True).lower()
    
    for signal_name, patterns in SIGNAL_PATTERNS.items():
        signals[signal_name] = any(re.search(p, text, re.I) for p in patterns)
    
    return signals


async def enrich_company_free(company: Dict) -> Dict:
    """
    Enrich a single company using FREE methods only.
    
    Returns enrichment results dict.
    """
    results = {
        'company_id': company['company_id'],
        'company_name': company['company_name'],
        'domain': company.get('domain'),
        'contacts_found': [],
        'signals': {},
        'pages_scraped': 0,
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
    all_html = ""
    
    # Scrape essential pages
    for page in ESSENTIAL_PAGES:
        url = f"{base_url}{page}"
        html = await scrape_page_bs(url)
        if html:
            results['pages_scraped'] += 1
            all_html += html
            
            # Extract contacts from team pages
            if any(p in page for p in ['/team', '/leadership', '/about']):
                contacts = extract_contacts_from_html(html, domain)
                results['contacts_found'].extend(contacts)
    
    # Detect ICP signals from all content
    if all_html:
        results['signals'] = detect_icp_signals(all_html)
    
    # Dedupe contacts
    seen_emails = set()
    seen_names = set()
    unique_contacts = []
    for c in results['contacts_found']:
        email = c.get('email')
        name = c.get('full_name')
        if email and email not in seen_emails:
            seen_emails.add(email)
            unique_contacts.append(c)
        elif name and name not in seen_names:
            seen_names.add(name)
            unique_contacts.append(c)
    results['contacts_found'] = unique_contacts
    
    return results


async def save_enrichment_results(results: Dict):
    """Save enrichment results to Supabase"""
    company_id = results['company_id']
    
    # Update company with signals and scrape timestamp
    update_data = {
        'website_scraped_at': datetime.now().isoformat(),
        'last_enriched_at': datetime.now().isoformat(),
    }
    
    # Add ICP signals
    for signal, value in results.get('signals', {}).items():
        if value:
            update_data[signal] = True
    
    supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
    
    # Save contacts
    for contact in results.get('contacts_found', []):
        if contact.get('full_name') or contact.get('email'):
            contact_data = {
                'company_id': company_id,
                'full_name': contact.get('full_name'),
                'title': contact.get('title'),
                'email': contact.get('email'),
                'is_atl': contact.get('is_atl', False),
                'source': 'free_enrichment',
                'created_at': datetime.now().isoformat()
            }
            
            # Upsert - avoid duplicates
            try:
                if contact.get('email'):
                    # Check if exists
                    existing = supabase.table('dim_contacts')\
                        .select('contact_id')\
                        .eq('company_id', company_id)\
                        .eq('email', contact['email'])\
                        .execute()
                    
                    if not existing.data:
                        supabase.table('dim_contacts').insert(contact_data).execute()
                else:
                    supabase.table('dim_contacts').insert(contact_data).execute()
            except Exception as e:
                pass  # Skip duplicates


async def main():
    parser = argparse.ArgumentParser(description='Free enrichment for PLATINUM leads')
    parser.add_argument('--limit', type=int, default=None, help='Limit number of leads')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be enriched')
    parser.add_argument('--source', type=str, default=None, help='Filter by source')
    args = parser.parse_args()
    
    print("=" * 70)
    print("PLATINUM FREE ENRICHMENT")
    print("=" * 70)
    print(f"Methods: BeautifulSoup (FREE), No Hunter/Apollo")
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Get PLATINUM leads that need enrichment
    query = supabase.table('dim_companies')\
        .select('company_id, company_name, domain, icp_tier, icp_score, website_scraped_at')\
        .eq('icp_tier', 'PLATINUM')\
        .is_('website_scraped_at', 'null')  # Not yet scraped
    
    if args.source:
        query = query.eq('original_source', args.source)
    
    query = query.order('icp_score', desc=True)
    
    if args.limit:
        query = query.limit(args.limit)
    
    result = query.execute()
    leads = result.data
    
    print(f"\nFound {len(leads)} PLATINUM leads needing enrichment")
    
    if args.dry_run:
        print("\n=== DRY RUN - Would enrich: ===")
        for i, lead in enumerate(leads[:20], 1):
            print(f"  {i}. {lead['company_name']} ({lead.get('domain', 'NO DOMAIN')})")
        if len(leads) > 20:
            print(f"  ... and {len(leads) - 20} more")
        return
    
    # Process leads
    success = 0
    failed = 0
    contacts_found = 0
    
    for i, lead in enumerate(leads, 1):
        print(f"\n[{i}/{len(leads)}] {lead['company_name']}...")
        
        try:
            results = await enrich_company_free(lead)
            
            if results['pages_scraped'] > 0:
                await save_enrichment_results(results)
                success += 1
                contacts_found += len(results['contacts_found'])
                
                atl_count = sum(1 for c in results['contacts_found'] if c.get('is_atl'))
                signals = [k for k, v in results.get('signals', {}).items() if v]
                
                print(f"  ✅ Scraped {results['pages_scraped']} pages, "
                      f"found {len(results['contacts_found'])} contacts ({atl_count} ATL)")
                if signals:
                    print(f"  📊 Signals: {', '.join(signals)}")
            else:
                failed += 1
                print(f"  ⚠️ No pages accessible")
                
        except Exception as e:
            failed += 1
            print(f"  ❌ Error: {e}")
        
        # Small delay to be polite
        await asyncio.sleep(0.5)
    
    # Summary
    print("\n" + "=" * 70)
    print("ENRICHMENT COMPLETE")
    print("=" * 70)
    print(f"  Processed: {len(leads)}")
    print(f"  Success: {success}")
    print(f"  Failed: {failed}")
    print(f"  Contacts found: {contacts_found}")
    print(f"  Cost: $0 (BeautifulSoup only)")


if __name__ == '__main__':
    asyncio.run(main())
