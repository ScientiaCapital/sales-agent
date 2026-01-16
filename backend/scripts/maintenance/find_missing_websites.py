#!/usr/bin/env python3
"""
Find Missing Websites via Google Search
========================================
Before excluding companies with no website, try to find their websites
using Google search. This recovers good leads that just had bad data.

Usage:
    python3 find_missing_websites.py              # Process 50 companies
    python3 find_missing_websites.py --limit 100  # Process 100 companies
    python3 find_missing_websites.py --dry-run    # Preview only, no updates

Author: Claude + Tim
Date: Dec 24, 2025
"""
import asyncio
import os
import sys
import re
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import urlparse

from dotenv import load_dotenv
from supabase import create_client
import httpx
from bs4 import BeautifulSoup

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

# Supabase connection
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# Google search via SerpAPI or fallback to DuckDuckGo HTML
SERPAPI_KEY = os.getenv('SERPAPI_KEY')  # Optional - faster/more reliable

# Rate limiting
DELAY_BETWEEN_SEARCHES = 3.0  # Be nice to search engines


def extract_domain(url: str) -> str:
    """Extract clean domain from URL."""
    if not url:
        return None
    try:
        parsed = urlparse(url if url.startswith('http') else f'https://{url}')
        domain = parsed.netloc or parsed.path.split('/')[0]
        # Remove www prefix
        if domain.startswith('www.'):
            domain = domain[4:]
        return domain.lower() if domain else None
    except:
        return None


async def search_duckduckgo(query: str) -> list[dict]:
    """
    Search DuckDuckGo HTML (no API key needed).
    Returns list of {title, url, snippet}.
    """
    search_url = f"https://html.duckduckgo.com/html/?q={query}"

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.get(
                search_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                },
                follow_redirects=True
            )

            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, 'html.parser')
            results = []

            # DuckDuckGo HTML results
            for result in soup.select('.result'):
                title_elem = result.select_one('.result__title')
                link_elem = result.select_one('.result__url')
                snippet_elem = result.select_one('.result__snippet')

                if title_elem and link_elem:
                    # Extract actual URL from DuckDuckGo redirect
                    href = title_elem.find('a')
                    if href and href.get('href'):
                        url = href.get('href')
                        # DuckDuckGo wraps URLs - extract the actual one
                        if 'uddg=' in url:
                            import urllib.parse
                            parsed = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
                            url = parsed.get('uddg', [url])[0]

                        results.append({
                            'title': title_elem.get_text(strip=True),
                            'url': url,
                            'snippet': snippet_elem.get_text(strip=True) if snippet_elem else ''
                        })

            return results[:5]  # Top 5 results

        except Exception as e:
            print(f"    Search error: {e}")
            return []


def is_likely_company_website(url: str, company_name: str) -> tuple[bool, int]:
    """
    Check if URL is likely the company's actual website.
    Returns (is_likely, confidence_score).
    """
    if not url:
        return False, 0

    url_lower = url.lower()
    name_lower = company_name.lower()

    # Skip aggregator/directory sites
    skip_domains = [
        'facebook.com', 'linkedin.com', 'twitter.com', 'instagram.com',
        'yelp.com', 'yellowpages.com', 'bbb.org', 'angieslist.com',
        'homeadvisor.com', 'thumbtack.com', 'houzz.com', 'google.com',
        'mapquest.com', 'manta.com', 'dnb.com', 'zoominfo.com',
        'indeed.com', 'glassdoor.com', 'crunchbase.com',
        'wikipedia.org', 'bloomberg.com', 'reuters.com'
    ]

    for skip in skip_domains:
        if skip in url_lower:
            return False, 0

    # Extract domain
    domain = extract_domain(url)
    if not domain:
        return False, 0

    # Check if company name words appear in domain
    name_words = re.findall(r'\w+', name_lower)
    name_words = [w for w in name_words if len(w) > 2 and w not in
                  {'the', 'and', 'inc', 'llc', 'corp', 'ltd', 'company', 'co', 'services', 'service'}]

    confidence = 0

    # Check domain match
    for word in name_words[:3]:  # First 3 significant words
        if word in domain:
            confidence += 30

    # Bonus for .com
    if domain.endswith('.com'):
        confidence += 10

    # Bonus for short domain (likely primary site)
    if len(domain) < 25:
        confidence += 10

    return confidence >= 30, confidence


async def find_website_for_company(company_name: str, state: str = None) -> dict:
    """
    Search for a company's website.
    Returns {found: bool, website: str, domain: str, confidence: int, source: str}
    """
    # Build search query
    query_parts = [company_name]
    if state:
        query_parts.append(state)
    query_parts.append("official website")
    query = " ".join(query_parts)

    results = await search_duckduckgo(query)

    if not results:
        return {'found': False, 'reason': 'no_search_results'}

    # Find best match
    for result in results:
        url = result.get('url', '')
        is_likely, confidence = is_likely_company_website(url, company_name)

        if is_likely:
            domain = extract_domain(url)
            return {
                'found': True,
                'website': url,
                'domain': domain,
                'confidence': confidence,
                'source': 'duckduckgo',
                'title': result.get('title', '')
            }

    return {'found': False, 'reason': 'no_matching_website'}


async def process_companies(limit: int = 50, dry_run: bool = False):
    """Process companies with no website."""

    # Get companies with no website (prioritize by tier)
    result = supabase.table('dim_companies') \
        .select('company_id, company_name, state, icp_tier') \
        .is_('website', 'null') \
        .order('icp_tier') \
        .limit(limit) \
        .execute()

    companies = result.data

    print("\n" + "=" * 70)
    print(f"FIND MISSING WEBSITES - {'DRY RUN' if dry_run else 'LIVE'}")
    print("=" * 70)
    print(f"Companies to process: {len(companies)}")
    print(f"Delay between searches: {DELAY_BETWEEN_SEARCHES}s")
    print("=" * 70 + "\n")

    found_count = 0
    not_found_count = 0

    for i, company in enumerate(companies):
        company_id = company['company_id']
        company_name = company['company_name']
        state = company.get('state', '')

        print(f"[{i+1}/{len(companies)}] {company_name[:50]:<50} ", end='', flush=True)

        # Search for website
        result = await find_website_for_company(company_name, state)

        if result['found']:
            found_count += 1
            website = result['website']
            domain = result['domain']
            confidence = result['confidence']

            print(f"✅ {domain} (conf={confidence})")

            if not dry_run:
                # Update database
                supabase.table('dim_companies').update({
                    'website': website,
                    'domain': domain,
                    'enrichment_status': 'website_found',
                    'ai_enriched_at': datetime.now().isoformat(),
                }).eq('company_id', company_id).execute()
        else:
            not_found_count += 1
            reason = result.get('reason', 'unknown')
            print(f"❌ {reason}")

        # Rate limit
        if i < len(companies) - 1:
            await asyncio.sleep(DELAY_BETWEEN_SEARCHES)

    # Summary
    print("\n" + "-" * 70)
    print("SUMMARY")
    print("-" * 70)
    print(f"✅ Found websites: {found_count}")
    print(f"❌ Not found: {not_found_count}")
    print(f"📊 Success rate: {found_count / len(companies) * 100:.1f}%")

    if dry_run:
        print("\n⚠️  DRY RUN - No changes made. Run without --dry-run to update database.")
    else:
        print(f"\n✅ Updated {found_count} companies with new websites.")

    print("-" * 70 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="Find missing websites via Google search")
    parser.add_argument('--limit', type=int, default=50, help='Number of companies to process')
    parser.add_argument('--dry-run', action='store_true', help='Preview only, no updates')
    args = parser.parse_args()

    await process_companies(limit=args.limit, dry_run=args.dry_run)


if __name__ == "__main__":
    asyncio.run(main())
