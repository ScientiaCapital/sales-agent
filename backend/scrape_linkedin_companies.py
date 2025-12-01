#!/usr/bin/env python3
"""
LinkedIn Company Page Scraper (Browserbase + Playwright)
=========================================================

Properly scrapes LinkedIn company pages to find:
1. Company page existence and URL
2. Employee count (visible on company page)
3. Employee list with names and titles (publicly visible)
4. ATL contacts (CEO, Owner, VP, etc.)

Uses Browserbase for browser automation to bypass LinkedIn's scraping blocks.

Usage:
    python scrape_linkedin_companies.py --test 5       # Test with 5 companies
    python scrape_linkedin_companies.py --all          # All 1,000 enriched leads
    python scrape_linkedin_companies.py --resume       # Resume from progress
    python scrape_linkedin_companies.py --top 500      # Top 500 by ICP score

Rate Limits (Browserbase):
- Free tier: 1 concurrent, 5/min
- Your config: 25 concurrent, ~25/min
- LinkedIn: Be gentle - 3-5s between requests

Estimated Time: 1,000 companies @ 5s each = ~83 minutes with 25 concurrent
"""

import asyncio
import pandas as pd
import logging
import sys
import os
import json
import re
from pathlib import Path
from datetime import datetime
import argparse
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

# Load environment variables
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env')

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

# Setup logging
log_dir = Path('logs')
log_dir.mkdir(exist_ok=True)
log_file = log_dir / f"linkedin_company_scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(log_file)
    ]
)
logger = logging.getLogger(__name__)

# Browserbase config
BROWSERBASE_API_KEY = os.getenv('BROWSERBASE_API_KEY')
BROWSERBASE_PROJECT_ID = os.getenv('BROWSERBASE_PROJECT_ID')
MAX_CONCURRENT = int(os.getenv('BROWSERBASE_MAX_CONCURRENT', '10'))  # Be conservative
MIN_DELAY = float(os.getenv('BROWSERBASE_MIN_DELAY', '3.0'))  # LinkedIn needs slower pace

# Paths
INPUT_DIR = Path('data/final_enrichment_output')
OUTPUT_DIR = Path('data/final_enrichment_output')


@dataclass
class LinkedInCompanyData:
    """Data extracted from LinkedIn company page."""
    company_name: str
    domain: str
    linkedin_url: str = ""
    linkedin_found: bool = False
    employee_count: str = ""
    employee_count_numeric: int = 0
    employees_visible: List[Dict[str, str]] = field(default_factory=list)
    atl_contacts: List[Dict[str, str]] = field(default_factory=list)
    atl_count: int = 0
    scrape_error: str = ""
    scrape_timestamp: str = ""


# ATL title keywords
ATL_TITLES = [
    'ceo', 'chief executive', 'president', 'owner', 'founder', 'co-founder',
    'cto', 'chief technology', 'cfo', 'chief financial', 'coo', 'chief operating',
    'vp', 'vice president', 'svp', 'evp', 'director', 'head of',
    'general manager', 'partner', 'principal', 'managing'
]


def is_atl(title: str) -> bool:
    """Check if title is Above The Line (decision maker)."""
    if not title:
        return False
    title_lower = title.lower()
    return any(t in title_lower for t in ATL_TITLES)


async def create_browserbase_session() -> tuple:
    """Create a Browserbase browser session."""
    import httpx

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
        session_id = data["id"]
        connect_url = data.get("connectUrl", f"wss://connect.browserbase.com?sessionId={session_id}&apiKey={BROWSERBASE_API_KEY}")
        return session_id, connect_url


async def close_browserbase_session(session_id: str):
    """Close a Browserbase session."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.browserbase.com/v1/sessions/{session_id}/stop",
                headers={"x-bb-api-key": BROWSERBASE_API_KEY}
            )
    except Exception as e:
        logger.warning(f"Failed to close session {session_id}: {e}")


async def scrape_linkedin_company(company_name: str, domain: str, semaphore: asyncio.Semaphore) -> LinkedInCompanyData:
    """
    Scrape LinkedIn company page using Browserbase.

    Strategy:
    1. Search Google for "site:linkedin.com/company {company_name}"
    2. Navigate to LinkedIn company page
    3. Extract employee count and visible employees
    4. Identify ATL contacts
    """
    from playwright.async_api import async_playwright

    result = LinkedInCompanyData(
        company_name=company_name,
        domain=domain,
        scrape_timestamp=datetime.now().isoformat()
    )

    async with semaphore:
        session_id = None
        try:
            # Create Browserbase session
            session_id, connect_url = await create_browserbase_session()
            logger.info(f"[{company_name}] Browserbase session created")

            async with async_playwright() as p:
                # Connect to Browserbase
                browser = await p.chromium.connect_over_cdp(connect_url)
                context = browser.contexts[0] if browser.contexts else await browser.new_context()
                page = context.pages[0] if context.pages else await context.new_page()

                # Step 1: Search Google for LinkedIn company page
                search_query = f"site:linkedin.com/company {company_name}"
                google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

                logger.info(f"[{company_name}] Searching Google: {search_query}")
                await page.goto(google_url, wait_until="domcontentloaded", timeout=20000)
                await asyncio.sleep(2)  # Let results load

                # Find LinkedIn company URL in search results
                linkedin_url = None
                search_results = await page.query_selector_all('a[href*="linkedin.com/company"]')

                for result_link in search_results[:5]:
                    href = await result_link.get_attribute('href')
                    if href and 'linkedin.com/company/' in href:
                        # Extract clean LinkedIn URL
                        match = re.search(r'(https?://[^/]*linkedin\.com/company/[a-zA-Z0-9_-]+)', href)
                        if match:
                            linkedin_url = match.group(1)
                            break

                if not linkedin_url:
                    # Try cite elements
                    cites = await page.query_selector_all('cite')
                    for cite in cites:
                        text = await cite.inner_text()
                        if 'linkedin.com/company' in text.lower():
                            match = re.search(r'linkedin\.com/company/([a-zA-Z0-9_-]+)', text)
                            if match:
                                linkedin_url = f"https://www.linkedin.com/company/{match.group(1)}"
                                break

                if not linkedin_url:
                    result.scrape_error = "No LinkedIn company page found in Google results"
                    logger.info(f"[{company_name}] ❌ No LinkedIn page found")
                    await browser.close()
                    return result

                result.linkedin_url = linkedin_url
                result.linkedin_found = True
                logger.info(f"[{company_name}] ✅ Found LinkedIn: {linkedin_url}")

                # Step 2: Navigate to LinkedIn company page
                await asyncio.sleep(MIN_DELAY)  # Rate limit before LinkedIn

                try:
                    await page.goto(linkedin_url, wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(3)  # Let page render

                    # Check for auth wall
                    page_content = await page.content()
                    if 'authwall' in page_content.lower() or 'sign in' in page_content.lower()[:500]:
                        # Try adding /about to bypass
                        await page.goto(f"{linkedin_url}/about", wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(2)

                    # Step 3: Extract employee count
                    # LinkedIn shows "X employees" on company pages
                    employee_selectors = [
                        'a[href*="/people/"] span',
                        '[class*="employee"]',
                        'span:has-text("employees")',
                        'div:has-text("employees")'
                    ]

                    for selector in employee_selectors:
                        try:
                            elements = await page.query_selector_all(selector)
                            for elem in elements:
                                text = await elem.inner_text()
                                # Look for patterns like "51-200 employees" or "1,234 employees"
                                emp_match = re.search(r'([\d,]+(?:-[\d,]+)?)\s*employees?', text, re.IGNORECASE)
                                if emp_match:
                                    result.employee_count = emp_match.group(1)
                                    # Parse numeric value
                                    count_str = result.employee_count.split('-')[-1].replace(',', '')
                                    result.employee_count_numeric = int(count_str) if count_str.isdigit() else 0
                                    logger.info(f"[{company_name}] 👥 Employee count: {result.employee_count}")
                                    break
                        except:
                            continue
                        if result.employee_count:
                            break

                    # Step 4: Try to get employees list
                    # Navigate to /people/ page
                    people_url = f"{linkedin_url}/people/"
                    await asyncio.sleep(MIN_DELAY)

                    try:
                        await page.goto(people_url, wait_until="domcontentloaded", timeout=20000)
                        await asyncio.sleep(3)

                        # Extract visible employee cards
                        employee_cards = await page.query_selector_all('[class*="org-people-profile-card"]')

                        if not employee_cards:
                            # Try alternative selectors
                            employee_cards = await page.query_selector_all('[data-test*="profile"], [class*="profile-card"]')

                        for card in employee_cards[:20]:  # Limit to 20 employees
                            try:
                                # Extract name
                                name_elem = await card.query_selector('span[class*="title"], h3, a[href*="/in/"]')
                                name = await name_elem.inner_text() if name_elem else None

                                # Extract title
                                title_elem = await card.query_selector('span[class*="subtitle"], p, div[class*="role"]')
                                title = await title_elem.inner_text() if title_elem else None

                                if name and name.strip():
                                    employee = {
                                        'name': name.strip(),
                                        'title': title.strip() if title else '',
                                        'is_atl': is_atl(title) if title else False
                                    }
                                    result.employees_visible.append(employee)

                                    if employee['is_atl']:
                                        result.atl_contacts.append(employee)
                                        logger.info(f"[{company_name}] 👤 ATL: {name} - {title}")

                            except Exception as card_err:
                                continue

                        result.atl_count = len(result.atl_contacts)
                        logger.info(f"[{company_name}] Found {len(result.employees_visible)} employees, {result.atl_count} ATL")

                    except Exception as people_err:
                        logger.debug(f"[{company_name}] Could not access /people/ page: {people_err}")

                except Exception as nav_err:
                    result.scrape_error = f"Navigation error: {str(nav_err)[:100]}"
                    logger.warning(f"[{company_name}] LinkedIn navigation error: {nav_err}")

                await browser.close()

        except Exception as e:
            result.scrape_error = str(e)[:200]
            logger.error(f"[{company_name}] Scrape error: {e}")

        finally:
            if session_id:
                await close_browserbase_session(session_id)

        return result


async def run_linkedin_scrape(
    df: pd.DataFrame,
    max_concurrent: int = 10,
    progress_file: Optional[Path] = None
) -> List[LinkedInCompanyData]:
    """
    Run LinkedIn scraping on all companies in dataframe.
    """
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)

    # Load existing progress if resuming
    already_scraped = set()
    if progress_file and progress_file.exists():
        progress_df = pd.read_csv(progress_file)
        already_scraped = set(progress_df['domain'].dropna().str.lower())
        logger.info(f"Resuming: {len(already_scraped)} already scraped")

    # Create tasks
    tasks = []
    for _, row in df.iterrows():
        domain = str(row.get('domain', '')).lower().strip()
        if domain in already_scraped:
            continue

        company_name = row.get('company_name', '')
        tasks.append(scrape_linkedin_company(company_name, domain, semaphore))

    logger.info(f"Scraping {len(tasks)} companies (skipping {len(already_scraped)} already done)")

    # Process with progress tracking
    batch_size = 25
    for i in range(0, len(tasks), batch_size):
        batch = tasks[i:i + batch_size]
        batch_results = await asyncio.gather(*batch, return_exceptions=True)

        for result in batch_results:
            if isinstance(result, Exception):
                logger.error(f"Task exception: {result}")
            else:
                results.append(result)

        # Save progress
        if progress_file and results:
            save_results(results, progress_file.with_suffix('.progress.csv'))

        logger.info(f"Progress: {i + len(batch)}/{len(tasks)} ({(i + len(batch))/len(tasks)*100:.1f}%)")

        # Rate limit between batches
        if i + batch_size < len(tasks):
            await asyncio.sleep(5)

    return results


def save_results(results: List[LinkedInCompanyData], output_file: Path):
    """Save results to CSV and JSON."""
    records = []
    for r in results:
        record = {
            'company_name': r.company_name,
            'domain': r.domain,
            'linkedin_url': r.linkedin_url,
            'linkedin_found': r.linkedin_found,
            'employee_count': r.employee_count,
            'employee_count_numeric': r.employee_count_numeric,
            'atl_count': r.atl_count,
            'atl_contacts_json': json.dumps(r.atl_contacts),
            'employees_visible_count': len(r.employees_visible),
            'scrape_error': r.scrape_error,
            'scrape_timestamp': r.scrape_timestamp
        }

        # Add individual ATL contacts as columns
        for i, atl in enumerate(r.atl_contacts[:5], 1):
            record[f'atl_{i}_name'] = atl.get('name', '')
            record[f'atl_{i}_title'] = atl.get('title', '')

        records.append(record)

    df = pd.DataFrame(records)
    df.to_csv(output_file, index=False)

    # JSON backup
    json_file = output_file.with_suffix('.json')
    with open(json_file, 'w') as f:
        json.dump([asdict(r) for r in results], f, indent=2, default=str)


def find_latest_enriched_file() -> Path:
    """Find the most recent enriched leads file."""
    patterns = ['ENRICHED_1000_ICP_COMPLETE_*.csv', 'TOP_500_FOR_HUNTER_*.csv']
    for pattern in patterns:
        files = list(INPUT_DIR.glob(pattern))
        if files:
            return max(files, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError("No enriched leads file found")


async def main():
    parser = argparse.ArgumentParser(description='LinkedIn company page scraper using Browserbase')
    parser.add_argument('--test', type=int, help='Test with N companies')
    parser.add_argument('--top', type=int, help='Process top N by ICP score')
    parser.add_argument('--all', action='store_true', help='Process all companies')
    parser.add_argument('--resume', action='store_true', help='Resume from progress file')
    parser.add_argument('--input', type=str, help='Specific input file')
    parser.add_argument('--concurrent', type=int, default=10, help='Max concurrent scrapes')

    args = parser.parse_args()

    if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
        logger.error("BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID must be set!")
        return

    # Find input file
    if args.input:
        input_file = Path(args.input)
    else:
        input_file = find_latest_enriched_file()

    logger.info(f"{'='*60}")
    logger.info(f"LINKEDIN COMPANY SCRAPER (Browserbase)")
    logger.info(f"{'='*60}")
    logger.info(f"Input: {input_file}")
    logger.info(f"Max concurrent: {args.concurrent}")
    logger.info(f"Log: {log_file}")

    # Load data
    df = pd.read_csv(input_file)
    logger.info(f"Loaded {len(df)} companies")

    # Apply filters
    if args.test:
        df = df.head(args.test)
        logger.info(f"TEST MODE: {args.test} companies")
    elif args.top:
        # Sort by hunter_priority_score or icp_score if available
        if 'hunter_priority_score' in df.columns:
            df = df.nlargest(args.top, 'hunter_priority_score')
        df = df.head(args.top)
        logger.info(f"TOP {args.top} companies selected")

    # Progress file for resume
    timestamp = datetime.now().strftime('%Y%m%d')
    progress_file = OUTPUT_DIR / f"linkedin_scrape_progress_{timestamp}.csv"

    # Run scraping
    results = await run_linkedin_scrape(
        df,
        max_concurrent=args.concurrent,
        progress_file=progress_file if args.resume else None
    )

    if not results:
        logger.info("No new companies to scrape")
        return

    # Save final results
    output_file = OUTPUT_DIR / f"LINKEDIN_COMPANIES_{timestamp}.csv"
    save_results(results, output_file)

    # Summary
    linkedin_found = sum(1 for r in results if r.linkedin_found)
    with_employees = sum(1 for r in results if r.employee_count)
    with_atl = sum(1 for r in results if r.atl_count > 0)
    total_atl = sum(r.atl_count for r in results)

    logger.info(f"\n{'='*60}")
    logger.info(f"LINKEDIN SCRAPE COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"Total scraped: {len(results)}")
    logger.info(f"LinkedIn found: {linkedin_found} ({linkedin_found/len(results)*100:.1f}%)")
    logger.info(f"With employee count: {with_employees}")
    logger.info(f"With ATL contacts: {with_atl}")
    logger.info(f"Total ATL contacts: {total_atl}")
    logger.info(f"")
    logger.info(f"Output: {output_file}")
    logger.info(f"JSON: {output_file.with_suffix('.json')}")

    # Show top ATL contacts found
    if total_atl > 0:
        logger.info(f"\nTOP ATL CONTACTS FOUND:")
        for r in results:
            if r.atl_contacts:
                for atl in r.atl_contacts[:2]:
                    logger.info(f"  • {atl['name']} ({atl['title']}) @ {r.company_name}")


if __name__ == '__main__':
    asyncio.run(main())
