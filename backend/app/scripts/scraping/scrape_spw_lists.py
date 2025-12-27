#!/usr/bin/env python3
"""
Solar Power World Top Contractors Scraper
==========================================

Scrapes Solar Power World's ranked contractor lists to build lead pipeline.

Lists supported:
- 2025 Top Solar Contractors
- 2025 Top Solar EPCs
- 2025 Top Solar Installers
- 2025 Top Solar Electrical Subcontractors
- 2025 Top Solar Installation Subcontractors
- 2025 Top Solar Storage Installers
- 2025 Top Commercial Solar Contractors

Usage:
    cd backend
    python scrape_spw_lists.py --test           # Test with 1 list, 5 companies
    python scrape_spw_lists.py --list-url URL   # Scrape specific list
    python scrape_spw_lists.py --all            # Scrape all lists
    python scrape_spw_lists.py --all --limit 50 # Limit per list
"""

import argparse
import asyncio
import os
import sys
import time
import re
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

try:
    from bs4 import BeautifulSoup
    import httpx
except ImportError:
    print("ERROR: pip install beautifulsoup4 httpx")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("ERROR: pip install supabase")
    sys.exit(1)

# Browserbase for JS-heavy pages
BROWSERBASE_API_KEY = os.getenv('BROWSERBASE_API_KEY')
BROWSERBASE_PROJECT_ID = os.getenv('BROWSERBASE_PROJECT_ID')

# Supabase
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

# Solar Power World list URLs
SPW_LISTS = [
    {
        'url': 'https://www.solarpowerworldonline.com/2025-top-solar-contractors/',
        'name': '2025 Top Solar Contractors',
        'category': 'solar_contractor'
    },
    {
        'url': 'https://www.solarpowerworldonline.com/2025-top-solar-epcs/',
        'name': '2025 Top Solar EPCs',
        'category': 'solar_epc'
    },
    {
        'url': 'https://www.solarpowerworldonline.com/2025-top-solar-installers/',
        'name': '2025 Top Solar Installers',
        'category': 'solar_installer'
    },
    {
        'url': 'https://www.solarpowerworldonline.com/2025-top-solar-electrical-subcontractors/',
        'name': '2025 Top Solar Electrical Subcontractors',
        'category': 'solar_electrical_sub'
    },
    {
        'url': 'https://www.solarpowerworldonline.com/2025-top-solar-installation-subcontractors/',
        'name': '2025 Top Solar Installation Subcontractors',
        'category': 'solar_install_sub'
    },
    {
        'url': 'https://www.solarpowerworldonline.com/2025-top-solar-storage-installers/',
        'name': '2025 Top Solar Storage Installers',
        'category': 'solar_storage'
    },
    {
        'url': 'https://www.solarpowerworldonline.com/2025-top-commercial-solar-contractors/',
        'name': '2025 Top Commercial Solar Contractors',
        'category': 'commercial_solar'
    },
]

# Headers for requests
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def get_supabase():
    """Get Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


def normalize_company_name(name: str) -> str:
    """Normalize company name for deduplication."""
    import re
    name = name.lower().strip()
    # Remove common suffixes
    for suffix in [' llc', ' inc', ' corp', ' co', ' ltd', ' company', ' solar', ' energy']:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
    # Remove special chars
    name = re.sub(r'[^a-z0-9]', '', name)
    return name


async def fetch_page_content(url: str) -> str:
    """Fetch page content using httpx."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=HEADERS, follow_redirects=True)
        response.raise_for_status()
        return response.text


async def fetch_with_browserbase(url: str) -> str:
    """Fetch page using Browserbase for JS-heavy pages."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: pip install playwright && playwright install chromium")
        return ""

    session_id = None

    # Create Browserbase session
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'https://api.browserbase.com/v1/sessions',
            headers={
                'x-bb-api-key': BROWSERBASE_API_KEY,
                'Content-Type': 'application/json'
            },
            json={'projectId': BROWSERBASE_PROJECT_ID}
        )
        session_data = response.json()
        session_id = session_data.get('id')
        connect_url = session_data.get('connectUrl')

    if not connect_url:
        print(f"  Failed to create Browserbase session")
        return ""

    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = await context.new_page()

        # Go to page with domcontentloaded (faster than networkidle)
        await page.goto(url, wait_until='domcontentloaded', timeout=30000)

        # Wait for table to appear
        try:
            await page.wait_for_selector('table', timeout=15000)
            await page.wait_for_timeout(3000)  # Extra time for table to populate
        except:
            print(f"  Table not found, waiting for any content...")
            await page.wait_for_timeout(5000)

        # Scroll to load any lazy content
        await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await page.wait_for_timeout(2000)

        content = await page.content()
        await browser.close()
        await playwright.stop()
        return content

    except Exception as e:
        print(f"  Browserbase error: {e}")
        return ""
    finally:
        # Close session
        if session_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f'https://api.browserbase.com/v1/sessions/{session_id}/stop',
                        headers={'x-bb-api-key': BROWSERBASE_API_KEY}
                    )
            except:
                pass


async def scrape_list_page(url: str, use_browserbase: bool = True) -> List[Dict[str, Any]]:
    """Scrape a Solar Power World list page.

    Returns list of companies with:
    - rank, company_name, company_url, hq_state, markets, service, kw_installed

    Note: SPW uses JS-rendered tables, so Browserbase is required.
    """
    print(f"  Fetching list page (Browserbase)...")

    # SPW pages are JS-heavy, always use Browserbase
    content = await fetch_with_browserbase(url)

    if not content:
        return []

    soup = BeautifulSoup(content, 'html.parser')
    companies = []

    # Find the table - SPW uses filter-table class
    table = (
        soup.find('table', class_='filter-table') or
        soup.find('table', class_='sortable') or
        soup.find('table', {'id': 'tablepress-1'}) or
        soup.find('table', class_='tablepress')
    )
    if not table:
        # Try finding any table with company data
        tables = soup.find_all('table')
        for t in tables:
            if t.find('a', href=lambda h: h and '/supplier/' in h):
                table = t
                break

    if not table:
        print(f"  Could not find company table")
        # Debug: print what we got
        all_tables = soup.find_all('table')
        print(f"  Found {len(all_tables)} tables total")
        if all_tables:
            for i, t in enumerate(all_tables[:3]):
                print(f"    Table {i}: {t.get('id', 'no-id')}, {t.get('class', 'no-class')}")
        return []

    # Parse table rows
    rows = table.find_all('tr')[1:]  # Skip header
    print(f"  Found {len(rows)} rows")

    for row in rows:
        cells = row.find_all(['td', 'th'])
        if len(cells) < 3:
            continue

        try:
            # Extract data from cells
            rank_text = cells[0].get_text(strip=True)
            rank = int(re.sub(r'[^\d]', '', rank_text)) if rank_text else 0

            # Company name and link
            company_cell = cells[1]
            company_link = company_cell.find('a')
            company_name = company_link.get_text(strip=True) if company_link else company_cell.get_text(strip=True)
            company_url = company_link.get('href') if company_link else None

            # State
            hq_state = cells[2].get_text(strip=True) if len(cells) > 2 else ''

            # Markets (may have multiple links)
            markets = []
            if len(cells) > 3:
                market_links = cells[3].find_all('a')
                if market_links:
                    markets = [m.get_text(strip=True) for m in market_links]
                else:
                    markets = [cells[3].get_text(strip=True)]

            # Service type
            service = cells[4].get_text(strip=True) if len(cells) > 4 else ''

            # kW installed
            kw_text = cells[5].get_text(strip=True) if len(cells) > 5 else '0'
            kw_installed = float(re.sub(r'[^\d.]', '', kw_text)) if kw_text else 0

            if company_name and company_name.lower() not in ['company', 'name', '']:
                companies.append({
                    'rank': rank,
                    'company_name': company_name,
                    'company_url': company_url,
                    'hq_state': hq_state,
                    'markets': markets,
                    'service': service,
                    'kw_installed': kw_installed,
                })

        except Exception as e:
            continue

    return companies


async def scrape_company_detail(company_url: str) -> Dict[str, Any]:
    """Scrape company detail page to get website/domain.

    Returns:
    - website: company website URL
    - domain: extracted domain
    - description: company description
    """
    result = {'website': None, 'domain': None, 'description': None}

    if not company_url:
        return result

    # Domains to exclude (tracking, social media, etc.)
    EXCLUDED_DOMAINS = {
        'solarpowerworldonline.com', 'facebook.com', 'linkedin.com', 'twitter.com',
        'instagram.com', 'youtube.com', 'gateway.on24.com', 'on24.com',
        'bit.ly', 'tinyurl.com', 'goo.gl', 't.co', 'ow.ly',
        'mailchimp.com', 'constantcontact.com', 'hubspot.com',
        'google.com', 'maps.google.com', 'yelp.com',
        'wtwhmedia.com', 'marketing.wtwhmedia.com',  # SPW tracking
        'addtoany.com', 'sharethis.com',  # Share buttons
        'soundcloud.com', 'spotify.com', 'apple.com',  # Media platforms
        'pinterest.com', 'tiktok.com', 'vimeo.com',
    }

    try:
        content = await fetch_page_content(company_url)
        soup = BeautifulSoup(content, 'html.parser')

        # Strategy 1: Find links where anchor text looks like a domain (e.g., "quantaservices.com")
        all_links = soup.find_all('a', href=lambda h: h and h.startswith('http'))

        for link in all_links:
            anchor_text = link.get_text(strip=True).lower()
            # If anchor text looks like a domain (contains .com, .net, etc.)
            if re.match(r'^[\w.-]+\.(com|net|org|co|io|energy|solar)$', anchor_text):
                href = link.get('href', '')
                domain = anchor_text.replace('www.', '')
                result['website'] = href
                result['domain'] = domain
                break

        # Strategy 2: Look for first external link that's not excluded
        if not result['domain']:
            for link in all_links:
                href = link.get('href', '')
                try:
                    parsed = urlparse(href)
                    domain = parsed.netloc.replace('www.', '').lower()

                    # Skip excluded domains
                    if any(excl in domain for excl in EXCLUDED_DOMAINS):
                        continue

                    # Skip if it's a file download
                    if any(ext in href.lower() for ext in ['.pdf', '.doc', '.xls', '.zip']):
                        continue

                    # Found a valid company website
                    result['website'] = href
                    result['domain'] = domain
                    break

                except:
                    continue

        # Get description
        desc_elem = soup.find('meta', {'name': 'description'}) or soup.find('p', class_='description')
        if desc_elem:
            result['description'] = desc_elem.get('content', '') or desc_elem.get_text(strip=True)

    except Exception as e:
        pass

    return result


async def scrape_spw_list(list_info: Dict, limit: int = 0, skip_details: bool = False) -> List[Dict[str, Any]]:
    """Scrape a complete Solar Power World list.

    Args:
        list_info: Dict with url, name, category
        limit: Max companies to scrape (0 = all)
        skip_details: Skip scraping company detail pages

    Returns:
        List of companies with full data
    """
    print(f"\n{'='*60}")
    print(f"Scraping: {list_info['name']}")
    print(f"{'='*60}")

    # Scrape list page
    companies = await scrape_list_page(list_info['url'])

    if not companies:
        print(f"  No companies found!")
        return []

    print(f"  Found {len(companies)} companies")

    if limit > 0:
        companies = companies[:limit]
        print(f"  Limited to {limit}")

    # Add category
    for c in companies:
        c['spw_category'] = list_info['category']
        c['spw_list'] = list_info['name']
        c['spw_url'] = list_info['url']

    # Scrape company details for websites
    if not skip_details:
        print(f"\n  Scraping company detail pages for websites...")
        for i, company in enumerate(companies):
            if company.get('company_url'):
                print(f"    [{i+1}/{len(companies)}] {company['company_name'][:40]}...", end=' ')
                details = await scrape_company_detail(company['company_url'])
                company.update(details)
                if details.get('domain'):
                    print(f"-> {details['domain']}")
                else:
                    print("(no website found)")
                await asyncio.sleep(0.5)  # Rate limit

    return companies


def save_to_supabase(supabase, companies: List[Dict], dry_run: bool = False) -> tuple:
    """Save companies to Supabase dim_companies.

    Returns: (inserted, updated, skipped)
    """
    inserted = 0
    updated = 0
    skipped = 0

    # Get existing companies by normalized name
    existing = supabase.table('dim_companies').select('company_id, normalized_name, domain').execute()
    existing_map = {r['normalized_name']: r for r in existing.data if r.get('normalized_name')}
    existing_domains = {r['domain'] for r in existing.data if r.get('domain')}

    for company in companies:
        normalized = normalize_company_name(company['company_name'])
        domain = company.get('domain')

        # Skip if already exists
        if normalized in existing_map:
            skipped += 1
            continue

        if domain and domain in existing_domains:
            skipped += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] Would insert: {company['company_name']} | {domain or 'no domain'}")
            inserted += 1
            continue

        # Prepare data
        data = {
            'company_name': company['company_name'],
            'normalized_name': normalized,
            'domain': domain,
            'website': company.get('website'),
            'state': company.get('hq_state'),
            'original_source': 'spw_' + company.get('spw_category', 'list'),
            'source_type': 'spw_scraper',
            'icp_score': min(100, 50 + (company.get('rank', 100) <= 50) * 20 + (company.get('kw_installed', 0) > 100000) * 10),
        }

        # Add SPW-specific data to a JSON field if needed
        # data['spw_data'] = {
        #     'rank': company.get('rank'),
        #     'kw_installed': company.get('kw_installed'),
        #     'markets': company.get('markets'),
        #     'service': company.get('service'),
        #     'list': company.get('spw_list'),
        # }

        try:
            supabase.table('dim_companies').insert(data).execute()
            inserted += 1
            print(f"  ✅ Inserted: {company['company_name'][:40]} | {domain or 'no domain'}")
        except Exception as e:
            print(f"  ❌ Error inserting {company['company_name']}: {e}")
            skipped += 1

    return inserted, updated, skipped


async def main():
    parser = argparse.ArgumentParser(description='Scrape Solar Power World top contractor lists')
    parser.add_argument('--test', action='store_true', help='Test mode: 1 list, 5 companies')
    parser.add_argument('--list-url', type=str, help='Scrape specific list URL')
    parser.add_argument('--all', action='store_true', help='Scrape all lists')
    parser.add_argument('--limit', type=int, default=0, help='Limit companies per list (0=all)')
    parser.add_argument('--skip-details', action='store_true', help='Skip company detail pages')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be inserted')
    args = parser.parse_args()

    if not any([args.test, args.list_url, args.all]):
        parser.print_help()
        return

    # Validate env vars
    if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY]):
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        sys.exit(1)

    supabase = get_supabase()
    all_companies = []

    if args.test:
        # Test mode: first list, 5 companies
        print("\n" + "="*60)
        print("TEST MODE: 1 list, 5 companies")
        print("="*60)
        companies = await scrape_spw_list(SPW_LISTS[0], limit=5)
        all_companies.extend(companies)

    elif args.list_url:
        # Specific URL
        list_info = {'url': args.list_url, 'name': 'Custom', 'category': 'custom'}
        # Try to match to known list
        for known in SPW_LISTS:
            if known['url'] == args.list_url:
                list_info = known
                break
        companies = await scrape_spw_list(list_info, limit=args.limit, skip_details=args.skip_details)
        all_companies.extend(companies)

    elif args.all:
        # All lists
        print("\n" + "="*60)
        print(f"SCRAPING ALL {len(SPW_LISTS)} LISTS")
        print("="*60)
        for list_info in SPW_LISTS:
            companies = await scrape_spw_list(list_info, limit=args.limit, skip_details=args.skip_details)
            all_companies.extend(companies)
            await asyncio.sleep(2)  # Rate limit between lists

    # Summary
    print(f"\n{'='*60}")
    print("SCRAPE COMPLETE")
    print(f"{'='*60}")
    print(f"Total companies scraped: {len(all_companies)}")

    with_domain = sum(1 for c in all_companies if c.get('domain'))
    print(f"With domain: {with_domain}")
    print(f"Without domain: {len(all_companies) - with_domain}")

    # Save to Supabase
    if all_companies:
        print(f"\n{'='*60}")
        print("SAVING TO SUPABASE")
        print(f"{'='*60}")
        inserted, updated, skipped = save_to_supabase(supabase, all_companies, dry_run=args.dry_run)
        print(f"\nResults:")
        print(f"  Inserted: {inserted}")
        print(f"  Skipped (duplicates): {skipped}")

        if args.dry_run:
            print(f"\n[DRY RUN] No changes made. Remove --dry-run to insert.")


if __name__ == '__main__':
    asyncio.run(main())
