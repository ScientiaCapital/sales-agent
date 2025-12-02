#!/usr/bin/env python3
"""
Single-Company Deep Scrape Debugger
====================================

Runs deep scrape on ONE company with verbose step-by-step output.
Use this to identify exactly where the scraper hangs.

Usage:
    python debug_single_scrape.py                    # Auto-pick first company
    python debug_single_scrape.py --index 5          # Pick 5th company (0-indexed)
    python debug_single_scrape.py --domain xyz.com   # Specific domain
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
from typing import List, Optional

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

# Browserbase config
BROWSERBASE_API_KEY = os.getenv('BROWSERBASE_API_KEY')
BROWSERBASE_PROJECT_ID = os.getenv('BROWSERBASE_PROJECT_ID')

# Input/Output directories
INPUT_DIR = Path('data/final_enrichment_output')
OUTPUT_DIR = Path('data/final_enrichment_output')


@dataclass
class DebugResult:
    """Debug scrape result with timing."""
    company_name: str
    domain: str
    success: bool = False

    # Timing (seconds)
    session_create_time: float = 0
    playwright_connect_time: float = 0
    landing_page_time: float = 0
    team_pages_time: float = 0
    linkedin_time: float = 0
    total_time: float = 0

    # Data found
    phones: List[str] = field(default_factory=list)
    emails: List[str] = field(default_factory=list)
    atl_contacts: List[dict] = field(default_factory=list)
    pages_scraped: List[str] = field(default_factory=list)
    linkedin_url: str = ""
    linkedin_employees: str = ""

    # Errors
    error_step: str = ""
    error_message: str = ""

    # Session info
    session_id: str = ""


def print_step(step: int, total: int, msg: str, status: str = ""):
    """Print a step with formatting."""
    prefix = f"[{step}/{total}]"
    if status == "ok":
        print(f"{prefix} {msg}")
        print(f"      OK")
    elif status == "error":
        print(f"{prefix} {msg}")
        print(f"      ERROR")
    elif status == "skip":
        print(f"{prefix} {msg}")
        print(f"      SKIPPED")
    else:
        print(f"{prefix} {msg}")


def print_detail(msg: str):
    """Print a detail line."""
    print(f"      {msg}")


async def create_session() -> tuple:
    """Create Browserbase session with timing."""
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
        connect_url = data.get("connectUrl")
        if not connect_url:
            raise ValueError("Browserbase did not return connectUrl")
        return session_id, connect_url


async def close_session(session_id: str):
    """Close Browserbase session."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.browserbase.com/v1/sessions/{session_id}/stop",
                headers={"x-bb-api-key": BROWSERBASE_API_KEY}
            )
    except Exception as e:
        print_detail(f"Session close warning: {e}")


def extract_phones(content: str) -> List[str]:
    """Extract phone numbers from HTML content."""
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
    """Extract emails from HTML content."""
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = set()
    for email in re.findall(pattern, content):
        if not any(x in email.lower() for x in ['example.com', 'domain.com', 'noreply']):
            emails.add(email.lower())
    return list(emails)


def extract_atl_from_text(content: str) -> List[dict]:
    """Extract ATL names from text patterns."""
    atl_patterns = [
        (r'[Ff]ounded\s+(?:in\s+\d{4}\s+)?by\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', 'Founder'),
        (r'[Oo]wner[:\s-]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', 'Owner'),
        (r'[Pp]resident[:\s-]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', 'President'),
        (r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),\s*(?:[Oo]wner|[Ff]ounder)', 'Owner/Founder'),
    ]

    contacts = []
    seen_names = set()

    for pattern, title in atl_patterns:
        for match in re.findall(pattern, content):
            name = match.strip()
            if name and 5 <= len(name) <= 40 and name.lower() not in seen_names:
                words = name.split()
                if 2 <= len(words) <= 4 and all(w[0].isupper() for w in words if len(w) > 1):
                    contacts.append({'name': name, 'title': title})
                    seen_names.add(name.lower())

    return contacts


async def debug_scrape(company_name: str, domain: str) -> DebugResult:
    """Run debug scrape on single company with verbose output."""

    result = DebugResult(company_name=company_name, domain=domain)
    total_steps = 6
    overall_start = time.time()

    print("\n" + "=" * 60)
    print(f"DEBUG SCRAPE: {company_name}")
    print(f"Domain: {domain}")
    print("=" * 60 + "\n")

    session_id = None

    try:
        # Step 1: Create Browserbase session
        print_step(1, total_steps, "Creating Browserbase session...")
        step_start = time.time()

        try:
            session_id, connect_url = await create_session()
            result.session_id = session_id
            result.session_create_time = time.time() - step_start
            print_detail(f"Session: {session_id[:12]}...")
            print_detail(f"Took {result.session_create_time:.2f}s")
        except Exception as e:
            result.error_step = "session_create"
            result.error_message = str(e)
            print_detail(f"FAILED: {e}")
            return result

        # Step 2: Connect Playwright
        print_step(2, total_steps, "Connecting Playwright to browser...")
        step_start = time.time()

        try:
            playwright = await async_playwright().start()
            browser = await playwright.chromium.connect_over_cdp(connect_url)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = context.pages[0] if context.pages else await context.new_page()
            result.playwright_connect_time = time.time() - step_start
            print_detail(f"Connected ({result.playwright_connect_time:.2f}s)")
        except Exception as e:
            result.error_step = "playwright_connect"
            result.error_message = str(e)
            print_detail(f"FAILED: {e}")
            await close_session(session_id)
            return result

        base_url = f"https://{domain}" if not domain.startswith('http') else domain

        # Step 3: Navigate to landing page
        print_step(3, total_steps, f"Loading landing page: {base_url}")
        step_start = time.time()

        try:
            response = await asyncio.wait_for(
                page.goto(base_url, wait_until="domcontentloaded"),
                timeout=15.0
            )
            result.landing_page_time = time.time() - step_start

            if response and response.status < 400:
                result.pages_scraped.append(base_url)
                print_detail(f"Status: {response.status} ({result.landing_page_time:.2f}s)")

                # Extract from landing page
                content = await page.content()
                result.phones = extract_phones(content)
                result.emails = extract_emails(content)

                text_content = await page.inner_text('body')
                result.atl_contacts = extract_atl_from_text(text_content)

                print_detail(f"Found: {len(result.phones)} phones, {len(result.emails)} emails")
            else:
                print_detail(f"Status: {response.status if response else 'None'} (may be blocked)")
        except asyncio.TimeoutError:
            result.error_step = "landing_page"
            result.error_message = "Timeout after 15s"
            print_detail("TIMEOUT after 15s")
        except Exception as e:
            result.error_step = "landing_page"
            result.error_message = str(e)[:100]
            print_detail(f"Error: {e}")

        # Step 4: Try team/about pages
        print_step(4, total_steps, "Checking team/about pages...")
        step_start = time.time()

        team_pages = ['/team', '/about', '/about-us', '/leadership']
        pages_found = 0

        for path in team_pages:
            try:
                full_url = f"{base_url}{path}"
                response = await asyncio.wait_for(
                    page.goto(full_url, wait_until="domcontentloaded"),
                    timeout=10.0
                )
                if response and response.status < 400:
                    pages_found += 1
                    result.pages_scraped.append(full_url)

                    # Extract more ATL
                    text_content = await page.inner_text('body')
                    new_atl = extract_atl_from_text(text_content)
                    existing_names = {c['name'].lower() for c in result.atl_contacts}
                    for contact in new_atl:
                        if contact['name'].lower() not in existing_names:
                            result.atl_contacts.append(contact)

                    print_detail(f"{path}: Found ({len(new_atl)} ATL)")
                await asyncio.sleep(0.5)  # Small delay between pages
            except asyncio.TimeoutError:
                print_detail(f"{path}: Timeout")
            except Exception:
                pass  # Skip failed pages

        result.team_pages_time = time.time() - step_start
        print_detail(f"Scraped {pages_found} pages ({result.team_pages_time:.2f}s)")

        # Step 5: LinkedIn lookup
        print_step(5, total_steps, "Searching LinkedIn...")
        step_start = time.time()

        try:
            search_query = f"site:linkedin.com/company {company_name}"
            google_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

            await asyncio.wait_for(
                page.goto(google_url, wait_until="domcontentloaded"),
                timeout=15.0
            )
            await asyncio.sleep(2)  # Let Google render

            # Find LinkedIn URL
            links = await page.query_selector_all('a[href*="linkedin.com/company"]')
            for link in links[:5]:
                href = await link.get_attribute('href')
                if href and 'linkedin.com/company/' in href:
                    match = re.search(r'(https?://[^/]*linkedin\.com/company/[a-zA-Z0-9_-]+)', href)
                    if match:
                        result.linkedin_url = match.group(1)
                        print_detail(f"Found: {result.linkedin_url}")
                        break

            if not result.linkedin_url:
                print_detail("No LinkedIn company page found")

            result.linkedin_time = time.time() - step_start
            print_detail(f"Took {result.linkedin_time:.2f}s")

        except asyncio.TimeoutError:
            print_detail("Google search timeout")
            result.linkedin_time = time.time() - step_start
        except Exception as e:
            print_detail(f"LinkedIn error: {e}")
            result.linkedin_time = time.time() - step_start

        # Step 6: Cleanup
        print_step(6, total_steps, "Closing browser session...")

        try:
            await browser.close()
            await playwright.stop()
        except Exception:
            pass

        result.success = True

    except Exception as e:
        result.error_step = "unknown"
        result.error_message = str(e)
        print_detail(f"Unexpected error: {e}")

    finally:
        if session_id:
            await close_session(session_id)

        result.total_time = time.time() - overall_start

    # Summary
    print("\n" + "-" * 60)
    print("SUMMARY")
    print("-" * 60)
    print(f"Success: {'YES' if result.success else 'NO'}")
    print(f"Total time: {result.total_time:.2f}s")
    print(f"Pages scraped: {len(result.pages_scraped)}")
    print(f"Phones found: {len(result.phones)}")
    print(f"Emails found: {len(result.emails)}")
    print(f"ATL contacts: {len(result.atl_contacts)}")

    if result.atl_contacts:
        print("\nATL Contacts:")
        for c in result.atl_contacts:
            print(f"  - {c['name']} ({c['title']})")

    if result.linkedin_url:
        print(f"\nLinkedIn: {result.linkedin_url}")

    if result.error_step:
        print(f"\nFailed at: {result.error_step}")
        print(f"Error: {result.error_message}")

    return result


def find_latest_input() -> Path:
    """Find the latest enrichment input file."""
    patterns = [
        'TOP_1000_FOR_ENRICHMENT_*.csv',
        'ENRICHED_1000_ICP_COMPLETE_*.csv',
        'TOP_1000_UNIQUE_ICP_*.csv',
        'TOP_500_FOR_HUNTER_*.csv',
    ]
    for pattern in patterns:
        files = list(INPUT_DIR.glob(pattern))
        if files:
            return max(files, key=lambda p: p.stat().st_mtime)
    raise FileNotFoundError("No input file found in data/final_enrichment_output/")


async def main():
    parser = argparse.ArgumentParser(description='Debug single-company deep scrape')
    parser.add_argument('--index', type=int, default=0, help='Company index in input file (0-based)')
    parser.add_argument('--domain', type=str, help='Specific domain to scrape')
    parser.add_argument('--company', type=str, help='Company name (used with --domain)')
    parser.add_argument('--input', type=str, help='Specific input file')

    args = parser.parse_args()

    # Validate environment
    if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
        print("ERROR: BROWSERBASE_API_KEY and BROWSERBASE_PROJECT_ID must be set in .env")
        sys.exit(1)

    print("[DEBUG] Browserbase credentials found")

    # Get company to scrape
    if args.domain:
        company_name = args.company or args.domain
        domain = args.domain
        print(f"[DEBUG] Using specified domain: {domain}")
    else:
        # Load from input file
        if args.input:
            input_file = Path(args.input)
        else:
            input_file = find_latest_input()

        print(f"[DEBUG] Loading: {input_file.name}")
        df = pd.read_csv(input_file)

        if args.index >= len(df):
            print(f"ERROR: Index {args.index} out of range (file has {len(df)} companies)")
            sys.exit(1)

        row = df.iloc[args.index]
        company_name = row.get('company_name', 'Unknown')
        domain = row.get('domain', '')

        if not domain:
            print(f"ERROR: No domain for company at index {args.index}")
            sys.exit(1)

        print(f"[DEBUG] Selected: \"{company_name}\" ({domain})")

    # Run debug scrape
    result = await debug_scrape(company_name, domain)

    # Save JSON result
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    output_file = OUTPUT_DIR / f"DEBUG_SINGLE_{timestamp}.json"

    with open(output_file, 'w') as f:
        json.dump(asdict(result), f, indent=2, default=str)

    print(f"\nSaved: {output_file}")


if __name__ == '__main__':
    asyncio.run(main())
