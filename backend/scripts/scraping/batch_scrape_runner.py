#!/usr/bin/env python3
"""
Batch Deep Scrape Runner with Supabase Sync
============================================

Scrapes companies 5 at a time (sequentially), syncs to Supabase,
then prompts you to continue or quit.

Usage:
    python batch_scrape_runner.py              # Start from company 0
    python batch_scrape_runner.py --start 100  # Resume from company 100
    python batch_scrape_runner.py --batch 10   # 10 companies per batch
    python batch_scrape_runner.py --auto       # No prompts, run all

Progress is saved to BATCH_PROGRESS.json for easy resuming.
"""

import asyncio
import json
import os
import re
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any

# Load environment
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

import pandas as pd
import httpx

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("ERROR: supabase not installed. Run: pip install supabase")
    sys.exit(1)

# Browserbase config
BROWSERBASE_API_KEY = os.getenv('BROWSERBASE_API_KEY')
BROWSERBASE_PROJECT_ID = os.getenv('BROWSERBASE_PROJECT_ID')

# Supabase config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

# Directories
INPUT_DIR = Path('data/final_enrichment_output')
OUTPUT_DIR = Path('data/final_enrichment_output')
PROGRESS_FILE = OUTPUT_DIR / 'BATCH_PROGRESS.json'


@dataclass
class ScrapeResult:
    """Result from scraping one company."""
    company_name: str
    domain: str
    normalized_name: str = ""  # Pre-computed from input file
    success: bool = False

    # Data
    phones: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    atl_contacts: List[Dict] = field(default_factory=list)
    pages_scraped: List[str] = field(default_factory=list)
    linkedin_url: str = ""
    linkedin_employees: int = 0

    # Address
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""

    # ICP signals
    trades_detected: List[str] = field(default_factory=list)
    is_multi_trade: bool = False
    family_owned: bool = False
    years_in_business: int = 0

    # Meta
    duration_seconds: float = 0
    error: str = ""


def get_supabase():
    """Create Supabase client."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


async def create_session() -> tuple:
    """Create Browserbase session."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.browserbase.com/v1/sessions",
            headers={
                "x-bb-api-key": BROWSERBASE_API_KEY,
                "Content-Type": "application/json"
            },
            json={"projectId": BROWSERBASE_PROJECT_ID}
        )
        response.raise_for_status()
        data = response.json()
        return data["id"], data.get("connectUrl")


async def close_session(session_id: str):
    """Close Browserbase session."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.browserbase.com/v1/sessions/{session_id}/stop",
                headers={"x-bb-api-key": BROWSERBASE_API_KEY}
            )
    except (httpx.HTTPError, httpx.TimeoutException):
        pass  # Session cleanup is best-effort


def extract_phones(content: str) -> List[str]:
    """Extract phone numbers."""
    patterns = [
        r'\(\d{3}\)\s*\d{3}[-.\s]\d{4}',
        r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',
    ]
    phones = set()
    for pattern in patterns:
        for match in re.findall(pattern, content):
            digits = re.sub(r'\D', '', match)
            if len(digits) == 10 and digits[:3] not in ['000', '111', '555', '800', '888']:
                phones.add(match.strip())
    return list(phones)


def extract_emails(content: str) -> List[str]:
    """Extract emails."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = set()
    for email in re.findall(pattern, content):
        if not any(x in email.lower() for x in ['example.com', 'domain.com', 'noreply']):
            emails.add(email.lower())
    return list(emails)


def extract_atl(content: str) -> List[Dict]:
    """Extract ATL contacts from text patterns."""
    patterns = [
        (r'[Ff]ounded\s+(?:in\s+\d{4}\s+)?by\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', 'Founder'),
        (r'[Oo]wner[:\s-]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', 'Owner'),
        (r'[Pp]resident[:\s-]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', 'President'),
        (r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),\s*(?:[Oo]wner|[Ff]ounder)', 'Owner/Founder'),
    ]

    contacts = []
    seen = set()

    for pattern, title in patterns:
        for match in re.findall(pattern, content):
            name = match.strip()
            if name and 5 <= len(name) <= 40 and name.lower() not in seen:
                words = name.split()
                if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if len(w) > 1):
                    contacts.append({'name': name, 'title': title, 'email': '', 'extraction_method': 'text_pattern'})
                    seen.add(name.lower())

    return contacts


def extract_address(content: str) -> Dict:
    """Extract address from content."""
    states = r'(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)'
    pattern = rf'(\d+[^,\n]+),?\s*([A-Za-z\s]+),?\s*{states}\s*(\d{{5}}(?:-\d{{4}})?)'
    match = re.search(pattern, content)
    if match:
        return {
            'address': match.group(1).strip(),
            'city': match.group(2).strip(),
            'state': match.group(3),
            'zip_code': match.group(4)
        }
    return {}


def detect_trades(text: str) -> List[str]:
    """Detect trades mentioned."""
    if not text:
        return []
    text_lower = text.lower()
    trade_keywords = {
        'hvac': ['hvac', 'heating', 'cooling', 'air conditioning'],
        'plumbing': ['plumbing', 'plumber', 'drain', 'sewer'],
        'electrical': ['electrical', 'electrician', 'wiring'],
        'roofing': ['roofing', 'roofer', 'shingle'],
        'solar': ['solar', 'renewable', 'photovoltaic'],
    }
    detected = []
    for trade, keywords in trade_keywords.items():
        if any(kw in text_lower for kw in keywords):
            detected.append(trade)
    return detected


async def scrape_company(company_name: str, domain: str, normalized_name: str = "") -> ScrapeResult:
    """Scrape one company."""
    result = ScrapeResult(company_name=company_name, domain=domain, normalized_name=normalized_name)
    start = time.time()
    session_id = None

    try:
        # Create session
        session_id, connect_url = await create_session()

        # Connect playwright
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()

        base_url = f"https://{domain}" if not domain.startswith('http') else domain

        # Scrape landing page
        try:
            response = await asyncio.wait_for(
                page.goto(base_url, wait_until="domcontentloaded"),
                timeout=15.0
            )
            if response and response.status < 400:
                result.pages_scraped.append(base_url)
                content = await page.content()
                result.phones = extract_phones(content)
                result.emails = extract_emails(content)

                text = await page.inner_text('body')
                result.atl_contacts = extract_atl(text)
                result.trades_detected = detect_trades(text)
                result.is_multi_trade = len(result.trades_detected) >= 2

                addr = extract_address(content)
                if addr:
                    result.address = addr.get('address', '')
                    result.city = addr.get('city', '')
                    result.state = addr.get('state', '')
                    result.zip_code = addr.get('zip_code', '')
        except asyncio.TimeoutError:
            result.error = "Landing page timeout"

        # Scrape team/about pages
        for path in ['/team', '/about', '/about-us', '/leadership']:
            try:
                full_url = f"{base_url}{path}"
                response = await asyncio.wait_for(
                    page.goto(full_url, wait_until="domcontentloaded"),
                    timeout=10.0
                )
                if response and response.status < 400:
                    result.pages_scraped.append(full_url)
                    text = await page.inner_text('body')
                    new_atl = extract_atl(text)
                    existing = {c['name'].lower() for c in result.atl_contacts}
                    for c in new_atl:
                        if c['name'].lower() not in existing:
                            result.atl_contacts.append(c)
                await asyncio.sleep(0.5)
            except (asyncio.TimeoutError, Exception) as e:
                pass  # Team page scraping is optional, continue

        # LinkedIn search
        try:
            search_query = f"site:linkedin.com/company {company_name}"
            google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            await asyncio.wait_for(
                page.goto(google_url, wait_until="domcontentloaded"),
                timeout=15.0
            )
            await asyncio.sleep(2)

            links = await page.query_selector_all('a[href*="linkedin.com/company"]')
            for link in links[:5]:
                href = await link.get_attribute('href')
                if href and 'linkedin.com/company/' in href:
                    match = re.search(r'(https?://[^/]*linkedin\.com/company/[a-zA-Z0-9_-]+)', href)
                    if match:
                        result.linkedin_url = match.group(1)
                        break
        except (asyncio.TimeoutError, Exception):
            pass  # LinkedIn search is optional, continue

        await browser.close()
        await playwright.stop()
        result.success = True

    except Exception as e:
        result.error = str(e)[:100]

    finally:
        if session_id:
            await close_session(session_id)
        result.duration_seconds = time.time() - start

    return result


def sync_to_supabase(results: List[ScrapeResult]) -> tuple:
    """Sync results to Supabase. Returns (companies_updated, contacts_added).

    Actual dim_companies columns: city, state, zip, street, phone, last_enriched_at, trade_count
    Actual dim_contacts columns: company_id, full_name, title, email, phone, is_atl, source
    """
    supabase = get_supabase()
    if not supabase:
        print("  Supabase not configured - skipping sync")
        return 0, 0

    # Normalize function - matches Supabase's normalized_name format (keeps inc, llc, etc)
    def normalize_name(name):
        if not name:
            return None
        n = str(name).lower().strip()
        # Replace special chars with space, but keep alphanumeric, spaces, and hyphens
        n = re.sub(r'[^\w\s-]', ' ', n)
        # Collapse multiple spaces
        return re.sub(r'\s+', ' ', n).strip()

    # Get existing companies (paginate to get all - Supabase default limit is 1000)
    try:
        all_companies = []
        offset = 0
        batch_size = 1000
        while True:
            result = supabase.table('dim_companies').select('company_id, normalized_name').range(offset, offset + batch_size - 1).execute()
            all_companies.extend(result.data)
            if len(result.data) < batch_size:
                break
            offset += batch_size
        name_to_id = {r['normalized_name']: r['company_id'] for r in all_companies if r['normalized_name']}
        print(f"  Loaded {len(name_to_id)} companies from Supabase")
    except Exception as e:
        print(f"  Failed to fetch companies: {e}")
        return 0, 0

    companies_updated = 0
    contacts_added = 0

    for r in results:
        if not r.success:
            continue

        # Use pre-computed normalized_name if available, otherwise compute it
        norm_name = r.normalized_name if r.normalized_name else normalize_name(r.company_name)
        company_id = name_to_id.get(norm_name)

        if not company_id:
            print(f"  Company not found in Supabase: {r.company_name} (normalized: {norm_name})")
            continue

        # Update company - only use columns that exist in schema
        update_data = {
            'last_enriched_at': datetime.now().isoformat()
        }
        # Address fields (these exist in schema)
        if r.city:
            update_data['city'] = r.city
        if r.state:
            update_data['state'] = r.state
        if r.zip_code:
            update_data['zip'] = r.zip_code
        if r.address:
            update_data['street'] = r.address
        # Trade count (exists in schema)
        if r.trades_detected:
            update_data['trade_count'] = len(r.trades_detected)

        try:
            supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
            companies_updated += 1
        except Exception as e:
            print(f"  Failed to update {r.company_name}: {e}")

        # Add ATL contacts - use correct column names from schema
        for atl in r.atl_contacts:
            if not atl.get('name'):
                continue

            # Parse first/last name
            name_parts = atl['name'].split()
            first_name = name_parts[0] if name_parts else ''
            last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ''

            contact_data = {
                'company_id': company_id,
                'full_name': atl['name'],
                'first_name': first_name,
                'last_name': last_name,
                'title': atl.get('title', ''),
                'email': atl.get('email') or None,  # NULL if empty
                'is_atl': True,
                'source': 'batch_scrape_runner',
                'seniority': 'executive' if atl.get('title', '').lower() in ['owner', 'founder', 'ceo', 'president'] else 'director'
            }
            try:
                # Check if exists by full_name
                existing_contact = supabase.table('dim_contacts').select('contact_id').eq('company_id', company_id).eq('full_name', atl['name']).execute()
                if existing_contact.data:
                    supabase.table('dim_contacts').update(contact_data).eq('contact_id', existing_contact.data[0]['contact_id']).execute()
                else:
                    supabase.table('dim_contacts').insert(contact_data).execute()
                    contacts_added += 1
            except Exception as e:
                print(f"  Failed to add contact {atl['name']}: {e}")

    return companies_updated, contacts_added


def save_progress(start_index: int, completed: int, total: int):
    """Save progress to file."""
    progress = {
        'last_completed_index': start_index + completed - 1,
        'next_start_index': start_index + completed,
        'total_companies': total,
        'completed_companies': start_index + completed,
        'remaining': total - (start_index + completed),
        'timestamp': datetime.now().isoformat()
    }
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)


def load_progress() -> int:
    """Load progress from file. Returns next start index."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            progress = json.load(f)
            return progress.get('next_start_index', 0)
    return 0


def find_input_file() -> Path:
    """Find the input file."""
    patterns = [
        'TOP_1000_FOR_ENRICHMENT_*.csv',
        'ENRICHED_1000_ICP_COMPLETE_*.csv',
        'TOP_1000_UNIQUE_ICP_*.csv',
    ]
    for pattern in patterns:
        files = list(INPUT_DIR.glob(pattern))
        if files:
            return max(files, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError("No input file found")


async def run_batch(df: pd.DataFrame, start: int, batch_size: int, total: int) -> List[ScrapeResult]:
    """Run one batch of companies."""
    results = []
    end = min(start + batch_size, total)
    batch_num = (start // batch_size) + 1
    total_batches = (total + batch_size - 1) // batch_size

    print(f"\n{'='*60}")
    print(f"BATCH {batch_num}/{total_batches}: Companies {start}-{end-1}")
    print(f"{'='*60}")

    for i, idx in enumerate(range(start, end)):
        row = df.iloc[idx]
        company_name = row.get('company_name', 'Unknown')
        domain = row.get('domain', '')
        # Store normalized_name if available (from Supabase export)
        normalized_name = row.get('normalized_name', '')

        if not domain:
            print(f"[{i+1}/{batch_size}] {company_name}: No domain, skipping")
            continue

        print(f"[{i+1}/{batch_size}] {company_name} ({domain})...", end=" ", flush=True)

        result = await scrape_company(company_name, domain, normalized_name)
        results.append(result)

        if result.success:
            atl_count = len(result.atl_contacts)
            phone_count = len(result.phones)
            print(f"OK {result.duration_seconds:.0f}s ({atl_count} ATL, {phone_count} phones)")
        else:
            print(f"FAIL: {result.error}")

    return results


async def main():
    parser = argparse.ArgumentParser(description='Batch deep scrape with Supabase sync')
    parser.add_argument('--start', type=int, default=None, help='Start from company index (default: resume from progress)')
    parser.add_argument('--batch', type=int, default=5, help='Companies per batch (default: 5)')
    parser.add_argument('--input', type=str, help='Input CSV file')
    parser.add_argument('--auto', action='store_true', help='Run all batches without prompting')

    args = parser.parse_args()

    # Validate credentials
    if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
        print("ERROR: BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID required")
        sys.exit(1)

    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("WARNING: Supabase not configured - results will only be saved locally")

    # Load input
    input_file = Path(args.input) if args.input else find_input_file()
    print(f"Input: {input_file.name}")

    df = pd.read_csv(input_file)
    total = len(df)
    print(f"Total companies: {total}")

    # Determine start index
    if args.start is not None:
        start = args.start
    else:
        start = load_progress()
        if start > 0:
            print(f"Resuming from company {start} (loaded from progress file)")

    batch_size = args.batch
    total_batches = (total - start + batch_size - 1) // batch_size

    print(f"Batch size: {batch_size}")
    print(f"Remaining batches: {total_batches}")
    print(f"\n~{batch_size * 27}s per batch (~{batch_size * 27 / 60:.1f} minutes)")

    # Run batches
    current = start
    all_results = []

    while current < total:
        # Run batch
        results = await run_batch(df, current, batch_size, total)
        all_results.extend(results)

        # Sync to Supabase
        print(f"\nSyncing to Supabase...")
        companies_updated, contacts_added = sync_to_supabase(results)
        print(f"SUPABASE SYNC: {companies_updated} companies updated, {contacts_added} contacts added")

        # Save batch results to JSON
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        batch_file = OUTPUT_DIR / f"BATCH_{current}_{current + len(results) - 1}_{timestamp}.json"
        with open(batch_file, 'w') as f:
            json.dump([asdict(r) for r in results], f, indent=2, default=str)
        print(f"Saved: {batch_file.name}")

        # Save failed companies to CSV for audit/retry
        failed = [r for r in results if not r.success]
        if failed:
            failed_file = OUTPUT_DIR / 'FAILED_COMPANIES.csv'
            # Append to existing file
            failed_records = [{
                'company_name': r.company_name,
                'domain': r.domain,
                'error': r.error,
                'duration_seconds': r.duration_seconds,
                'timestamp': timestamp,
                'batch_start': current
            } for r in failed]
            failed_df = pd.DataFrame(failed_records)
            if failed_file.exists():
                failed_df.to_csv(failed_file, mode='a', header=False, index=False)
            else:
                failed_df.to_csv(failed_file, index=False)
            print(f"FAILED: {len(failed)} companies logged to FAILED_COMPANIES.csv")

        # Update progress
        current += len(results)
        save_progress(start, current - start, total)

        remaining = total - current
        if remaining <= 0:
            print(f"\n ALL {total} COMPANIES COMPLETE!")
            break

        # Prompt for next batch
        if not args.auto:
            print(f"\n{remaining} companies remaining ({(total - remaining)}/{total})")
            response = input(f"Press Enter for next batch ({current}-{min(current + batch_size - 1, total - 1)}) or 'q' to quit: ")
            if response.lower() == 'q':
                print(f"\nStopped at company {current}. Resume with: python batch_scrape_runner.py")
                break

    # Final summary
    successful = sum(1 for r in all_results if r.success)
    total_atl = sum(len(r.atl_contacts) for r in all_results)
    total_phones = sum(len(r.phones) for r in all_results)

    print(f"\n{'='*60}")
    print("SESSION SUMMARY")
    print(f"{'='*60}")
    print(f"Companies scraped: {len(all_results)}")
    print(f"Successful: {successful}")
    print(f"ATL contacts found: {total_atl}")
    print(f"Phones found: {total_phones}")
    print(f"Progress saved to: {PROGRESS_FILE}")


if __name__ == '__main__':
    asyncio.run(main())
