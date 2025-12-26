#!/usr/bin/env python3
"""
FREE Batch Enrichment - BeautifulSoup only, no paid APIs
=========================================================

Processes companies in batches of 5, extracts:
- ICP signals (commercial, industrial, generators, etc.)
- Contact names and emails from team pages
- Company phone numbers

100% FREE - no Browserbase, Apollo, or Hunter costs.
"""

import asyncio
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv("/Users/tmk/tk_projects/sales-agent/.env", override=True)

from supabase import create_client

# Config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')
BATCH_SIZE = 5
MAX_BATCHES = 100  # 100 batches * 5 = 500 companies

# ICP Signal patterns
SIGNAL_PATTERNS = {
    'has_commercial': [r'commercial', r'business', r'office', r'retail'],
    'has_industrial': [r'industrial', r'manufacturing', r'facility', r'plant'],
    'has_generators': [r'generator', r'backup power', r'standby', r'generac', r'kohler'],
    'has_design_build': [r'design.?build', r'turnkey'],
    'has_engineering': [r'engineering', r'in.?house engineer'],
    'has_maintenance_plans': [r'maintenance agreement', r'service contract', r'preventive maintenance'],
    'has_hvac_trade': [r'\bhvac\b', r'heating', r'cooling', r'air conditioning'],
    'has_residential': [r'residential', r'home', r'homeowner'],
}

# ATL title patterns
ATL_TITLES = [
    r'\b(ceo|chief executive)\b', r'\b(president)\b', r'\b(owner|co-owner)\b',
    r'\b(founder|co-founder)\b', r'\b(partner)\b', r'\bvp\b|\bvice president\b',
    r'\bdirector\b', r'\b(gm|general manager)\b',
]

PAGES_TO_SCRAPE = ["/", "/about", "/about-us", "/services", "/team", "/our-team", "/contact"]


async def scrape_page(url: str, timeout: int = 10) -> str:
    """Scrape page HTML (FREE)"""
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            response = await client.get(url, headers={
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
            })
            if response.status_code == 200:
                return response.text
    except:
        pass
    return ""


def detect_signals(html: str) -> dict:
    """Detect ICP signals from page content"""
    signals = {}
    text = BeautifulSoup(html, 'html.parser').get_text(separator=' ', strip=True).lower()
    for signal_name, patterns in SIGNAL_PATTERNS.items():
        signals[signal_name] = any(re.search(p, text, re.I) for p in patterns)
    return signals


def is_atl_title(title: str) -> bool:
    """Check if title is ATL (decision maker)"""
    if not title:
        return False
    title_lower = title.lower()
    return any(re.search(pattern, title_lower) for pattern in ATL_TITLES)


# Garbage filtering
GARBAGE_NAMES = {
    'log in', 'login', 'sign up', 'signup', 'sign in', 'click here',
    'apply now', 'get started', 'read more', 'learn more', 'view all',
    'see all', 'show more', 'load more', 'submit', 'contact us', 'about us',
    'our team', 'our services', 'home', 'menu', 'search', 'close',
}
CITY_PREFIXES = {'los', 'las', 'san', 'santa', 'new', 'fort', 'palm', 'salt'}


def is_garbage_name(name: str) -> bool:
    """Check if name is garbage (not a real person name)"""
    if not name:
        return True
    name_lower = name.strip().lower()
    if len(name_lower) < 4:
        return True
    if name_lower in GARBAGE_NAMES:
        return True
    words = name_lower.split()
    if len(words) < 2:
        return True
    if len(words) >= 2 and words[0] in CITY_PREFIXES:
        return True
    if any(c.isdigit() for c in name_lower):
        return True
    if name_lower in ['none', 'null', 'undefined', 'n/a', 'na']:
        return True
    return False


def extract_contacts_from_html(html: str, domain: str) -> list:
    """Extract contacts from HTML"""
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

    # Look for team sections
    team_sections = soup.find_all(['div', 'section', 'article'],
        class_=re.compile(r'team|staff|employee|member|people|leadership', re.I))

    for section in team_sections:
        headings = section.find_all(['h2', 'h3', 'h4', 'strong', 'b'])
        for h in headings:
            name = h.get_text(strip=True)
            if name and len(name.split()) in [2, 3, 4] and name[0].isupper():
                # Garbage filter
                if is_garbage_name(name):
                    continue

                next_elem = h.find_next(['p', 'span', 'div'])
                title = next_elem.get_text(strip=True) if next_elem else None

                if title and len(title) < 100:
                    contacts.append({
                        'full_name': name,
                        'title': title,
                        'email': None,
                        'is_atl': is_atl_title(title),
                        'source': 'free_enrichment'
                    })

    # Add emails found
    for email in relevant_emails:
        email_local = email.split('@')[0].lower()
        matched = False
        for c in contacts:
            if c.get('full_name'):
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
                'source': 'free_enrichment'
            })

    return contacts


def extract_phones(text: str) -> list:
    """Extract phone numbers from text"""
    patterns = [r'\(\d{3}\)\s*\d{3}[-.\s]\d{4}', r'\d{3}[-.\s]\d{3}[-.\s]\d{4}']
    phones = set()
    for pattern in patterns:
        for match in re.findall(pattern, text):
            digits = re.sub(r'\D', '', match)
            if len(digits) == 10 and digits[:3] not in ['000', '111', '555', '800', '888']:
                phones.add(match.strip())
    return list(phones)[:3]


async def enrich_company(company: dict) -> dict:
    """Enrich a single company using FREE methods"""
    results = {
        'company_id': company['company_id'],
        'company_name': company['company_name'],
        'domain': company.get('domain'),
        'contacts': [],
        'signals': {},
        'phones': [],
        'pages_scraped': 0,
    }

    domain = company.get('domain')
    if not domain:
        return results

    if not domain.startswith('http'):
        domain = f'https://{domain}'

    base_url = domain.rstrip('/')
    all_html = ""

    for page in PAGES_TO_SCRAPE:
        url = f"{base_url}{page}"
        html = await scrape_page(url)
        if html:
            results['pages_scraped'] += 1
            all_html += html

            if any(p in page for p in ['/team', '/leadership', '/about']):
                contacts = extract_contacts_from_html(html, domain)
                results['contacts'].extend(contacts)

    if all_html:
        results['signals'] = detect_signals(all_html)
        text = BeautifulSoup(all_html, 'html.parser').get_text()
        results['phones'] = extract_phones(text)

    # Dedupe contacts
    seen = set()
    unique = []
    for c in results['contacts']:
        key = (c.get('full_name', ''), c.get('email', ''))
        if key not in seen and (c.get('full_name') or c.get('email')):
            seen.add(key)
            unique.append(c)
    results['contacts'] = unique

    return results


def save_results(supabase, results: dict):
    """Save enrichment results to Supabase"""
    company_id = results['company_id']

    # ALWAYS mark as enriched first (to prevent re-processing)
    try:
        supabase.table('dim_companies').update({
            'last_enriched_at': datetime.now().isoformat(),
        }).eq('company_id', company_id).execute()
    except Exception as e:
        print(f"    ⚠️ Enriched timestamp error: {e}")

    # Update company with signals
    update_data = {
        'website_scraped_at': datetime.now().isoformat(),
    }

    for signal, value in results.get('signals', {}).items():
        if value and signal in ['has_commercial', 'has_industrial', 'has_generators',
                                'has_design_build', 'has_engineering', 'has_maintenance_plans',
                                'has_hvac_trade', 'has_residential']:
            update_data[signal] = True

    # Skip main_phone - column doesn't exist in schema

    try:
        supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
    except Exception as e:
        print(f"    ⚠️ Update error: {e}")

    # Save contacts
    saved = 0
    for contact in results.get('contacts', []):
        if contact.get('full_name') or contact.get('email'):
            contact_data = {
                'contact_id': str(uuid4()),
                'company_id': company_id,
                'full_name': contact.get('full_name', ''),
                'title': contact.get('title', ''),
                'email': contact.get('email'),
                'is_atl': contact.get('is_atl', False),
                'source': 'free_enrichment',
            }

            try:
                # Check for existing
                if contact.get('email'):
                    existing = supabase.table('dim_contacts')\
                        .select('contact_id')\
                        .eq('company_id', company_id)\
                        .eq('email', contact['email'])\
                        .execute()
                    if existing.data:
                        continue

                supabase.table('dim_contacts').insert(contact_data).execute()
                saved += 1
            except:
                pass

    return saved


async def run_batch_enrichment():
    """Run batch enrichment - 100 batches of 5"""

    print("\n" + "="*70)
    print("🚀 FREE BATCH ENRICHMENT - 100 batches x 5 companies = 500 max")
    print("="*70)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("Method: BeautifulSoup (100% FREE)")
    print("="*70)

    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

    # Stats
    total_processed = 0
    total_success = 0
    total_contacts = 0
    batch_num = 0

    while batch_num < MAX_BATCHES:
        batch_num += 1

        # Get next batch of companies needing enrichment
        result = supabase.table('dim_companies')\
            .select('company_id, company_name, domain, icp_tier')\
            .not_.is_('domain', 'null')\
            .is_('last_enriched_at', 'null')\
            .order('icp_score', desc=True)\
            .limit(BATCH_SIZE)\
            .execute()

        companies = result.data
        if not companies:
            print(f"\n✅ No more companies to enrich!")
            break

        print(f"\n{'─'*60}")
        print(f"📦 BATCH {batch_num}/{MAX_BATCHES} - Processing {len(companies)} companies")
        print(f"{'─'*60}")

        # Update Supabase with phase status (create a simple status record)
        phase_status = f"Batch {batch_num}: Processing {len(companies)} companies"
        print(f"  📊 Phase: {phase_status}")

        for i, company in enumerate(companies, 1):
            company_name = company['company_name'][:35]
            domain = company.get('domain', 'N/A')
            tier = company.get('icp_tier', 'N/A')

            print(f"\n  [{i}/{len(companies)}] {company_name} ({domain}) [{tier}]")

            try:
                results = await enrich_company(company)
                total_processed += 1

                if results['pages_scraped'] > 0:
                    saved = save_results(supabase, results)
                    total_success += 1
                    total_contacts += saved

                    signals = [k.replace('has_', '') for k, v in results.get('signals', {}).items() if v]
                    atl = sum(1 for c in results['contacts'] if c.get('is_atl'))

                    print(f"      ✅ {results['pages_scraped']} pages | {len(results['contacts'])} contacts ({atl} ATL) | Saved: {saved}")
                    if signals:
                        print(f"      📊 Signals: {', '.join(signals[:5])}")
                else:
                    # Still mark as enriched to avoid re-processing
                    try:
                        supabase.table('dim_companies').update({
                            'last_enriched_at': datetime.now().isoformat(),
                        }).eq('company_id', results['company_id']).execute()
                    except:
                        pass
                    print(f"      ⚠️ No pages accessible")

            except Exception as e:
                print(f"      ❌ Error: {str(e)[:50]}")

            await asyncio.sleep(0.3)  # Polite delay

        # Batch summary
        print(f"\n  📈 Running totals: {total_processed} processed, {total_success} success, {total_contacts} contacts")

    # Final summary
    print("\n" + "="*70)
    print("📊 ENRICHMENT COMPLETE")
    print("="*70)
    print(f"  Batches completed: {batch_num}")
    print(f"  Companies processed: {total_processed}")
    print(f"  Successful scrapes: {total_success}")
    print(f"  Contacts saved: {total_contacts}")
    print(f"  Cost: $0.00 (BeautifulSoup FREE)")
    print(f"  Finished: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(run_batch_enrichment())
