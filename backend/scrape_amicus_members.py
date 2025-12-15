#!/usr/bin/env python3
"""
Amicus Solar/O&M Member Directory Scraper
==========================================

Scrapes Amicus cooperative member directories to build lead pipeline.

Directories supported:
- Amicus O&M: https://www.amicusom.com/member/
- Amicus Solar: https://www.amicussolar.com/our-member-owners/

Usage:
    cd backend
    python scrape_amicus_members.py --test           # Test with 5 members
    python scrape_amicus_members.py --source om      # Scrape Amicus O&M only
    python scrape_amicus_members.py --source solar   # Scrape Amicus Solar only
    python scrape_amicus_members.py --all            # Scrape both directories
"""

import argparse
import asyncio
import os
import sys
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

# Amicus directories
AMICUS_SOURCES = {
    'om': {
        'base_url': 'https://www.amicusom.com/member/',
        'name': 'Amicus O&M Cooperative',
        'original_source': 'amicus_om',
        'pages': 6,  # Has pagination 1-6
    },
    'solar': {
        'base_url': 'https://www.amicussolar.com/our-member-owners/',
        'name': 'Amicus Solar Cooperative',
        'original_source': 'amicus_solar',
        'pages': 1,  # May have pagination
    },
}

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
    name = name.lower().strip()
    for suffix in [' llc', ' inc', ' corp', ' co', ' ltd', ' company', ' solar', ' energy']:
        if name.endswith(suffix):
            name = name[:-len(suffix)]
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

        await page.goto(url, wait_until='domcontentloaded', timeout=30000)
        await page.wait_for_timeout(3000)

        # Scroll to load lazy content
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
        if session_id:
            try:
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f'https://api.browserbase.com/v1/sessions/{session_id}/stop',
                        headers={'x-bb-api-key': BROWSERBASE_API_KEY}
                    )
            except:
                pass


async def scrape_amicus_om_page(url: str) -> List[Dict[str, Any]]:
    """Scrape Amicus O&M member page.

    Members are in cards with:
    - Company name (heading)
    - Website URL (link)
    - Description
    """
    print(f"  Fetching {url}...")

    try:
        content = await fetch_page_content(url)
    except:
        print(f"  HTTP failed, trying Browserbase...")
        content = await fetch_with_browserbase(url)

    if not content:
        return []

    soup = BeautifulSoup(content, 'html.parser')
    members = []

    # Find member cards - look for divs/articles with company info
    # Amicus O&M uses WordPress with member cards

    # Strategy 1: Look for links that point to company websites
    all_links = soup.find_all('a', href=lambda h: h and h.startswith('http'))

    seen_domains = set()
    for link in all_links:
        href = link.get('href', '')
        text = link.get_text(strip=True)

        # Skip internal links and social media
        if 'amicusom.com' in href or 'amicussolar.com' in href:
            continue
        if any(s in href for s in ['facebook.com', 'linkedin.com', 'twitter.com', 'instagram.com']):
            continue

        try:
            domain = urlparse(href).netloc.replace('www.', '').lower()
            if not domain or domain in seen_domains:
                continue

            # Try to find company name near the link
            parent = link.find_parent(['div', 'article', 'section', 'li'])
            company_name = None

            if parent:
                # Look for heading
                heading = parent.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                if heading:
                    company_name = heading.get_text(strip=True)

                # Or the link text itself might be the company name
                if not company_name and text and len(text) > 3 and not text.startswith('http'):
                    company_name = text

            # Use domain as fallback name
            if not company_name:
                company_name = domain.split('.')[0].title()

            # Skip if company name looks like garbage
            if len(company_name) < 3 or len(company_name) > 100:
                continue

            seen_domains.add(domain)
            members.append({
                'company_name': company_name,
                'website': href,
                'domain': domain,
            })

        except:
            continue

    return members


async def scrape_amicus_solar_page(url: str) -> List[Dict[str, Any]]:
    """Scrape Amicus Solar member page.

    This page is JS-heavy, needs Browserbase.
    """
    print(f"  Fetching {url} (Browserbase)...")

    content = await fetch_with_browserbase(url)

    if not content:
        return []

    soup = BeautifulSoup(content, 'html.parser')
    members = []

    # Similar extraction logic
    all_links = soup.find_all('a', href=lambda h: h and h.startswith('http'))

    seen_domains = set()
    for link in all_links:
        href = link.get('href', '')
        text = link.get_text(strip=True)

        if 'amicusom.com' in href or 'amicussolar.com' in href:
            continue
        if any(s in href for s in ['facebook.com', 'linkedin.com', 'twitter.com', 'instagram.com', 'youtube.com']):
            continue

        try:
            domain = urlparse(href).netloc.replace('www.', '').lower()
            if not domain or domain in seen_domains:
                continue
            if len(domain) < 4:
                continue

            parent = link.find_parent(['div', 'article', 'section', 'li'])
            company_name = None

            if parent:
                heading = parent.find(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])
                if heading:
                    company_name = heading.get_text(strip=True)

                if not company_name and text and len(text) > 3 and not text.startswith('http'):
                    company_name = text

            if not company_name:
                company_name = domain.split('.')[0].replace('-', ' ').title()

            if len(company_name) < 3 or len(company_name) > 100:
                continue

            seen_domains.add(domain)
            members.append({
                'company_name': company_name,
                'website': href,
                'domain': domain,
            })

        except:
            continue

    return members


async def scrape_amicus_directory(source_key: str, limit: int = 0) -> List[Dict[str, Any]]:
    """Scrape an Amicus member directory.

    Args:
        source_key: 'om' or 'solar'
        limit: Max members to return (0 = all)

    Returns:
        List of member companies
    """
    source = AMICUS_SOURCES[source_key]
    print(f"\n{'='*60}")
    print(f"Scraping: {source['name']}")
    print(f"{'='*60}")

    all_members = []

    # Scrape each page
    for page_num in range(1, source['pages'] + 1):
        if page_num == 1:
            url = source['base_url']
        else:
            # Amicus O&M uses /member/page/2/ format
            url = f"{source['base_url']}page/{page_num}/"

        if source_key == 'om':
            members = await scrape_amicus_om_page(url)
        else:
            members = await scrape_amicus_solar_page(url)

        print(f"  Page {page_num}: Found {len(members)} members")

        # Add source info
        for m in members:
            m['original_source'] = source['original_source']
            m['source_name'] = source['name']

        all_members.extend(members)

        if page_num < source['pages']:
            await asyncio.sleep(1)  # Rate limit

    # Deduplicate by domain
    seen = set()
    unique = []
    for m in all_members:
        if m['domain'] not in seen:
            seen.add(m['domain'])
            unique.append(m)

    print(f"\n  Total unique members: {len(unique)}")

    if limit > 0:
        unique = unique[:limit]
        print(f"  Limited to: {limit}")

    return unique


def save_to_supabase(supabase, members: List[Dict], dry_run: bool = False) -> tuple:
    """Save members to Supabase dim_companies.

    Returns: (inserted, skipped)
    """
    inserted = 0
    skipped = 0

    # Get existing companies
    existing = supabase.table('dim_companies').select('company_id, normalized_name, domain').execute()
    existing_names = {r['normalized_name'] for r in existing.data if r.get('normalized_name')}
    existing_domains = {r['domain'] for r in existing.data if r.get('domain')}

    for member in members:
        normalized = normalize_company_name(member['company_name'])
        domain = member.get('domain')

        # Skip duplicates
        if normalized in existing_names:
            skipped += 1
            continue
        if domain and domain in existing_domains:
            skipped += 1
            continue

        if dry_run:
            print(f"  [DRY RUN] Would insert: {member['company_name']} | {domain} | {member['original_source']}")
            inserted += 1
            continue

        data = {
            'company_name': member['company_name'],
            'normalized_name': normalized,
            'domain': domain,
            'website': member.get('website'),
            'original_source': member['original_source'],
            'source_type': 'amicus_scraper',
            'icp_score': 60,  # Amicus members are quality contractors
        }

        try:
            supabase.table('dim_companies').insert(data).execute()
            inserted += 1
            print(f"  ✅ Inserted: {member['company_name'][:40]} | {domain} | {member['original_source']}")
            existing_names.add(normalized)
            existing_domains.add(domain)
        except Exception as e:
            print(f"  ❌ Error: {member['company_name']}: {e}")
            skipped += 1

    return inserted, skipped


async def main():
    parser = argparse.ArgumentParser(description='Scrape Amicus member directories')
    parser.add_argument('--test', action='store_true', help='Test mode: 5 members only')
    parser.add_argument('--source', type=str, choices=['om', 'solar'], help='Scrape specific directory')
    parser.add_argument('--all', action='store_true', help='Scrape both directories')
    parser.add_argument('--limit', type=int, default=0, help='Limit members (0=all)')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be inserted')
    args = parser.parse_args()

    if not any([args.test, args.source, args.all]):
        parser.print_help()
        return

    if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY]):
        print("ERROR: Missing SUPABASE_URL or SUPABASE_SERVICE_KEY")
        sys.exit(1)

    supabase = get_supabase()
    all_members = []

    if args.test:
        print("\n" + "="*60)
        print("TEST MODE: Amicus O&M, 5 members")
        print("="*60)
        members = await scrape_amicus_directory('om', limit=5)
        all_members.extend(members)

    elif args.source:
        members = await scrape_amicus_directory(args.source, limit=args.limit)
        all_members.extend(members)

    elif args.all:
        print("\n" + "="*60)
        print("SCRAPING BOTH AMICUS DIRECTORIES")
        print("="*60)
        for source_key in AMICUS_SOURCES:
            members = await scrape_amicus_directory(source_key, limit=args.limit)
            all_members.extend(members)
            await asyncio.sleep(2)

    # Summary
    print(f"\n{'='*60}")
    print("SCRAPE COMPLETE")
    print(f"{'='*60}")
    print(f"Total members scraped: {len(all_members)}")

    # Count by source
    by_source = {}
    for m in all_members:
        src = m.get('original_source', 'unknown')
        by_source[src] = by_source.get(src, 0) + 1

    print("\nBy source:")
    for src, count in by_source.items():
        print(f"  {src}: {count}")

    # Save to Supabase
    if all_members:
        print(f"\n{'='*60}")
        print("SAVING TO SUPABASE")
        print(f"{'='*60}")
        inserted, skipped = save_to_supabase(supabase, all_members, dry_run=args.dry_run)
        print(f"\nResults:")
        print(f"  Inserted: {inserted}")
        print(f"  Skipped (duplicates): {skipped}")

        if args.dry_run:
            print(f"\n[DRY RUN] No changes made. Remove --dry-run to insert.")


if __name__ == '__main__':
    asyncio.run(main())
