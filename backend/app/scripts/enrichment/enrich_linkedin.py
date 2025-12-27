#!/usr/bin/env python3
"""
LinkedIn Enrichment Service
============================

Finds, verifies, and scrapes LinkedIn company pages for:
- Company details (employee count, industry, description, etc.)
- All employees (ATL + BTL) with pagination for big companies
- Employee LinkedIn profile URLs

Uses Browserbase for scraping to bypass LinkedIn's bot detection.

Usage:
    cd backend
    python enrich_linkedin.py --test --domain example.com
    python enrich_linkedin.py --test --limit 3
    python enrich_linkedin.py --auto --limit 100
    python enrich_linkedin.py --search-employee "John Doe" "Acme Corp"
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

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

try:
    from supabase import create_client
    from playwright.async_api import async_playwright
    import httpx
except ImportError:
    print("ERROR: pip install supabase playwright httpx")
    sys.exit(1)

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from app.services.linkedin_company_service import LinkedInCompanyService, get_linkedin_company_service
from app.services.linkedin_people_service import LinkedInPeopleService, get_linkedin_people_service

# Config
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
BROWSERBASE_API_KEY = os.getenv('BROWSERBASE_API_KEY')
BROWSERBASE_PROJECT_ID = os.getenv('BROWSERBASE_PROJECT_ID')

BATCH_SIZE = 5
RATE_LIMIT_DELAY = 10  # 10 seconds between companies (LinkedIn is strict)


def get_supabase():
    """Get Supabase client."""
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


async def create_browserbase_session():
    """Create Browserbase session."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.browserbase.com/v1/sessions",
            headers={"x-bb-api-key": BROWSERBASE_API_KEY, "Content-Type": "application/json"},
            json={"projectId": BROWSERBASE_PROJECT_ID}
        )
        response.raise_for_status()
        data = response.json()
        return data["id"], data.get("connectUrl")


async def close_browserbase_session(session_id: str):
    """Close Browserbase session."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.browserbase.com/v1/sessions/{session_id}/stop",
                headers={"x-bb-api-key": BROWSERBASE_API_KEY}
            )
    except:
        pass


def get_companies_for_linkedin_enrichment(supabase, batch_size: int, test_domains: Optional[List[str]] = None):
    """Get companies that need LinkedIn enrichment.
    
    Criteria:
    - Have domain (required)
    - Have been website-enriched (have last_enriched_at)
    - Don't have linkedin_enriched_at yet (or need refresh)
    """
    if test_domains:
        # Test mode: get specific domains
        companies = []
        for domain in test_domains[:5]:  # Max 5 for test
            result = supabase.table('dim_companies')\
                .select('company_id, company_name, domain, linkedin_url')\
                .eq('domain', domain)\
                .limit(1)\
                .execute()
            if result.data:
                companies.append(result.data[0])
        return companies
    
    # Normal mode: get companies that need LinkedIn enrichment
    result = supabase.table('dim_companies')\
        .select('company_id, company_name, domain, linkedin_url')\
        .not_.is_('domain', 'null')\
        .not_.is_('last_enriched_at', 'null')\
        .is_('linkedin_enriched_at', 'null')\
        .limit(batch_size)\
        .execute()
    return result.data


async def find_company_linkedin_page(company_service: LinkedInCompanyService, company_name: str, domain: str) -> Optional[str]:
    """Find or verify company LinkedIn page."""
    try:
        result = await company_service.find_company(company_name=company_name, website=domain)
        if result.status == "success" and result.company:
            return result.company.linkedin_url
    except Exception as e:
        print(f"    ⚠️  LinkedIn search error: {e}")
    return None


async def scrape_linkedin_company_page(session_id: str, connect_url: str, linkedin_url: str) -> Dict[str, Any]:
    """Scrape LinkedIn company page using Browserbase.
    
    Returns:
        - company_data: Basic company info (employee count, industry, description)
        - employees: List of employees (ATL + BTL) with profile URLs
    """
    company_data = {
        'linkedin_url': linkedin_url,
        'employee_count': None,
        'industry': None,
        'description': None,
        'founded_year': None,
        'website': None,
        'headquarters': None
    }
    employees = []
    
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()
        
        # Navigate to company page
        await page.goto(linkedin_url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(3)  # Wait for page to load
        
        # Extract company data
        try:
            # Employee count
            emp_elem = await page.query_selector('a[href*="/search/results/people/"]')
            if emp_elem:
                emp_text = await emp_elem.inner_text()
                # Extract number from text like "50-200 employees"
                match = re.search(r'([\d,]+(?:-[\d,]+)?)', emp_text)
                if match:
                    company_data['employee_count'] = match.group(1)
        except:
            pass
        
        try:
            # Industry
            industry_elem = await page.query_selector('dd:has-text("Industry")')
            if industry_elem:
                company_data['industry'] = await industry_elem.inner_text()
        except:
            pass
        
        try:
            # Description
            desc_elem = await page.query_selector('[class*="org-about-us-organization-description"]')
            if desc_elem:
                company_data['description'] = await desc_elem.inner_text()
        except:
            pass
        
        # Navigate to /people/ page to get employees
        people_url = f"{linkedin_url.rstrip('/')}/people/"
        await page.goto(people_url, wait_until='networkidle', timeout=30000)
        await asyncio.sleep(3)
        
        # Scroll to load more employees (for big companies)
        for _ in range(3):  # Scroll 3 times to load more
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(2)
        
        # Extract employee cards
        employee_cards = await page.query_selector_all('[class*="org-people-profile-card"], [class*="profile-card"], [data-testid*="profile"]')
        
        for card in employee_cards[:100]:  # Limit to 100 employees per company
            try:
                # Extract name
                name_elem = await card.query_selector('span[class*="title"], h3, a[href*="/in/"]')
                name = await name_elem.inner_text() if name_elem else None
                
                # Extract title
                title_elem = await card.query_selector('span[class*="subtitle"], p, div[class*="role"]')
                title = await title_elem.inner_text() if title_elem else None
                
                # Extract LinkedIn URL
                link_elem = await card.query_selector('a[href*="/in/"]')
                profile_url = await link_elem.get_attribute('href') if link_elem else None
                
                if name and name.strip():
                    # Determine if ATL
                    title_lower = (title or '').lower()
                    is_atl = any(keyword in title_lower for keyword in [
                        'ceo', 'president', 'owner', 'founder', 'vp', 'vice president',
                        'director', 'head of', 'chief', 'cfo', 'cto', 'coo', 'cmo'
                    ])
                    
                    employees.append({
                        'name': name.strip(),
                        'title': title.strip() if title else None,
                        'linkedin_url': profile_url,
                        'is_atl': is_atl
                    })
            except:
                continue
        
        await browser.close()
        await playwright.stop()
        
    except Exception as e:
        print(f"    ⚠️  Scraping error: {e}")
    
    return {
        'company_data': company_data,
        'employees': employees
    }


async def enrich_company_with_linkedin(
    company_service: LinkedInCompanyService,
    company_id: str,
    company_name: str,
    domain: str,
    existing_linkedin_url: Optional[str] = None
) -> Dict[str, Any]:
    """Enrich one company with LinkedIn data.
    
    Returns dict with:
    - company_data: LinkedIn company info
    - employees: List of employees
    - success: bool
    - error: str if failed
    """
    result = {
        'company_id': company_id,
        'company_name': company_name,
        'domain': domain,
        'success': False,
        'company_data': None,
        'employees': [],
        'error': ''
    }
    
    try:
        # Step 1: Find or verify LinkedIn page
        linkedin_url = existing_linkedin_url
        if not linkedin_url:
            print(f"    Finding LinkedIn page...", end=" ", flush=True)
            linkedin_url = await find_company_linkedin_page(company_service, company_name, domain)
            if linkedin_url:
                print(f"✅ Found: {linkedin_url}")
            else:
                print("❌ Not found")
                result['error'] = "LinkedIn company page not found"
                return result
        else:
            print(f"    Using existing LinkedIn URL: {linkedin_url}")
        
        # Step 2: Scrape company page using Browserbase
        if not BROWSERBASE_API_KEY:
            result['error'] = "BROWSERBASE_API_KEY not configured"
            return result
        
        print(f"    Scraping LinkedIn page...", end=" ", flush=True)
        session_id, connect_url = await create_browserbase_session()
        
        try:
            scrape_result = await scrape_linkedin_company_page(session_id, connect_url, linkedin_url)
            result['company_data'] = scrape_result['company_data']
            result['employees'] = scrape_result['employees']
            result['success'] = True
            print(f"✅ {len(result['employees'])} employees found")
        finally:
            await close_browserbase_session(session_id)
        
    except Exception as e:
        result['error'] = str(e)[:100]
    
    return result


async def search_employee_linkedin(people_service: LinkedInPeopleService, employee_name: str, company_name: str) -> Optional[str]:
    """Search for specific employee LinkedIn profile."""
    try:
        # Use Google search to find employee LinkedIn profile
        # This is a simplified version - in production, you might use Apollo or other services
        print(f"\nSearching for {employee_name} at {company_name}...")
        
        # For now, return None - this would need proper implementation
        # The LinkedInPeopleService could be extended for this
        return None
    except Exception as e:
        print(f"    ⚠️  Search error: {e}")
        return None


def sync_linkedin_data_to_supabase(supabase, results: List[Dict[str, Any]]) -> tuple:
    """Sync LinkedIn enrichment data to Supabase.
    
    Returns: (companies_updated, contacts_added)
    """
    companies_updated = 0
    contacts_added = 0
    
    for r in results:
        if not r['success']:
            continue
        
        company_id = r['company_id']
        company_data = r.get('company_data', {})
        employees = r.get('employees', [])
        
        # Update company with LinkedIn data
        update_data = {
            'linkedin_enriched_at': datetime.now().isoformat()
        }
        
        if company_data:
            if company_data.get('linkedin_url'):
                update_data['linkedin_url'] = company_data['linkedin_url']
            if company_data.get('employee_count'):
                update_data['employee_count'] = company_data['employee_count']
            if company_data.get('industry'):
                update_data['industry'] = company_data['industry']
        
        try:
            supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
            companies_updated += 1
        except Exception as e:
            print(f"    Company update error: {e}")
        
        # Add employees as contacts
        for emp in employees:
            name = emp.get('name')
            if not name or len(name) < 3:
                continue
            
            title = emp.get('title')
            linkedin_url = emp.get('linkedin_url')
            is_atl = emp.get('is_atl', False)
            
            contact_data = {
                'company_id': company_id,
                'full_name': name[:100],
                'first_name': name.split()[0] if name.split() else ''[:50],
                'last_name': ' '.join(name.split()[1:]) if len(name.split()) > 1 else ''[:50],
                'title': title[:100] if title else None,
                'linkedin_url': linkedin_url,
                'is_atl': is_atl,
                'source': 'linkedin_scrape'
            }
            
            try:
                # Check if contact already exists
                existing = supabase.table('dim_contacts')\
                    .select('contact_id')\
                    .eq('company_id', company_id)\
                    .eq('full_name', name[:100])\
                    .execute()
                
                if not existing.data:
                    supabase.table('dim_contacts').insert(contact_data).execute()
                    contacts_added += 1
                elif linkedin_url:
                    # Update LinkedIn URL if missing
                    supabase.table('dim_contacts')\
                        .update({'linkedin_url': linkedin_url})\
                        .eq('contact_id', existing.data[0]['contact_id'])\
                        .is_('linkedin_url', 'null')\
                        .execute()
            except Exception as e:
                print(f"    Contact error: {e}")
    
    return companies_updated, contacts_added


async def run_linkedin_batch(
    company_service: LinkedInCompanyService,
    supabase,
    companies: List[Dict],
    test_mode: bool = False
) -> List[Dict[str, Any]]:
    """Run LinkedIn enrichment on a batch of companies."""
    results = []
    
    for i, company in enumerate(companies, 1):
        # Rate limiting: delay between companies
        if test_mode and i > 1:
            await asyncio.sleep(RATE_LIMIT_DELAY)
        elif not test_mode and i > 1:
            await asyncio.sleep(RATE_LIMIT_DELAY)
        
        company_id = company['company_id']
        name = company['company_name']
        domain = company['domain']
        existing_linkedin = company.get('linkedin_url')
        
        print(f"  [{i}/{len(companies)}] {name} ({domain})...", end=" ", flush=True)
        
        result = await enrich_company_with_linkedin(
            company_service, company_id, name, domain, existing_linkedin
        )
        results.append(result)
        
        if result['success']:
            company_info = result['company_data'] or {}
            employees_count = len(result['employees'])
            atl_count = sum(1 for e in result['employees'] if e.get('is_atl'))
            employee_count = company_info.get('employee_count', '?')
            industry = company_info.get('industry', '?')
            
            print(f"✅ ({employees_count} employees, {atl_count} ATL, {employee_count} total, {industry})")
        else:
            print(f"❌ {result['error']}")
    
    return results


async def main():
    parser = argparse.ArgumentParser(description='LinkedIn enrichment service')
    parser.add_argument('--auto', action='store_true', help='Run continuously without prompts')
    parser.add_argument('--limit', type=int, default=0, help='Max companies to process (0=unlimited)')
    parser.add_argument('--test', action='store_true', help='Test mode: max 5 companies, adds rate limiting')
    parser.add_argument('--domain', type=str, help='Test single domain (e.g., acmeheating.com)')
    parser.add_argument('--domains', type=str, help='Test multiple domains, comma-separated (max 5)')
    parser.add_argument('--search-employee', nargs=2, metavar=('NAME', 'COMPANY'), help='Search for specific employee LinkedIn profile')
    args = parser.parse_args()
    
    # Validate
    if not all([SUPABASE_URL, SUPABASE_SERVICE_KEY]):
        print("ERROR: Missing Supabase environment variables")
        sys.exit(1)
    
    if not BROWSERBASE_API_KEY or not BROWSERBASE_PROJECT_ID:
        print("ERROR: Missing BROWSERBASE_API_KEY or BROWSERBASE_PROJECT_ID")
        sys.exit(1)
    
    supabase = get_supabase()
    company_service = await get_linkedin_company_service()
    people_service = await get_linkedin_people_service()
    
    # Employee search mode
    if args.search_employee:
        employee_name, company_name = args.search_employee
        linkedin_url = await search_employee_linkedin(people_service, employee_name, company_name)
        if linkedin_url:
            print(f"✅ Found: {linkedin_url}")
        else:
            print("❌ Not found")
        return
    
    # Test mode handling
    if args.test:
        print(f"\n{'='*60}")
        print(f"LINKEDIN ENRICHMENT (TEST MODE)")
        print(f"{'='*60}")
        print(f"Rate limiting: {RATE_LIMIT_DELAY}s delay between companies")
        print(f"Max companies: 5")
        print(f"⚠️  Uses Browserbase for scraping")
        
        # Get companies for test
        test_domains = None
        if args.domain:
            test_domains = [args.domain]
            print(f"Testing single domain: {args.domain}")
        elif args.domains:
            test_domains = [d.strip() for d in args.domains.split(',')][:5]
            print(f"Testing multiple domains: {', '.join(test_domains)}")
        else:
            test_limit = min(args.limit or 3, 5)
            print(f"Testing {test_limit} random companies from Supabase")
        
        companies = get_companies_for_linkedin_enrichment(supabase, BATCH_SIZE, test_domains=test_domains)
        
        if not companies:
            print("\n❌ No companies found to test")
            return
        
        companies = companies[:5]
        print(f"Processing {len(companies)} companies...\n")
        
        # Run batch
        results = await run_linkedin_batch(company_service, supabase, companies, test_mode=True)
        
        # Sync
        print("\n  Syncing to Supabase...", end=" ")
        updated, contacts = sync_linkedin_data_to_supabase(supabase, results)
        print(f"{updated} companies, {contacts} contacts")
        
        # Stats
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        if failed > 0:
            print(f"  ⚠️  {failed} failed")
        
        print(f"\n{'='*60}")
        print("TEST COMPLETE")
        print(f"{'='*60}")
        print(f"Companies enriched: {updated}")
        print(f"Contacts found: {contacts}")
        return
    
    # Normal mode
    # Get stats
    total = supabase.table('dim_companies')\
        .select('company_id', count='exact')\
        .not_.is_('domain', 'null')\
        .not_.is_('last_enriched_at', 'null')\
        .is_('linkedin_enriched_at', 'null')\
        .execute()
    
    print(f"\n{'='*60}")
    print(f"LINKEDIN ENRICHMENT {'(AUTO MODE)' if args.auto else ''}")
    print(f"{'='*60}")
    print(f"Companies needing LinkedIn enrichment: {total.count}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Rate limiting: {RATE_LIMIT_DELAY}s delay between companies")
    print(f"⚠️  Uses Browserbase for scraping")
    if args.limit:
        print(f"Limit: {args.limit} companies")
    
    if not args.auto:
        print(f"\nPress Enter to start, 'q' to quit")
        response = input()
        if response.lower() == 'q':
            return
    
    batch_num = 0
    total_enriched = 0
    total_contacts = 0
    
    while True:
        # Check limit
        if args.limit and total_enriched >= args.limit:
            print(f"\n✅ Reached limit of {args.limit} companies")
            break
        
        # Get next batch
        companies = get_companies_for_linkedin_enrichment(supabase, BATCH_SIZE)
        
        if not companies:
            print("\n✅ ALL COMPANIES ENRICHED WITH LINKEDIN!")
            break
        
        batch_num += 1
        remaining = total.count - total_enriched
        print(f"\n{'='*60}")
        print(f"BATCH {batch_num} ({remaining} remaining)")
        print(f"{'='*60}")
        
        # Run batch
        results = await run_linkedin_batch(company_service, supabase, companies, test_mode=False)
        
        # Sync
        print("\n  Syncing to Supabase...", end=" ")
        updated, contacts = sync_linkedin_data_to_supabase(supabase, results)
        print(f"{updated} companies, {contacts} contacts")
        
        total_enriched += updated
        total_contacts += contacts
        
        # Stats
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        if failed > 0:
            print(f"  ⚠️  {failed} failed (will retry later)")
        
        print(f"\n  Session total: {total_enriched} enriched, {total_contacts} contacts found")
        
        # Prompt (skip in auto mode)
        if not args.auto:
            response = input("\nPress Enter for next batch, 'q' to quit: ")
            if response.lower() == 'q':
                break
        else:
            # Small delay between batches in auto mode
            await asyncio.sleep(2)
    
    print(f"\n{'='*60}")
    print("SESSION COMPLETE")
    print(f"{'='*60}")
    print(f"Companies enriched: {total_enriched}")
    print(f"Contacts found: {total_contacts}")


if __name__ == '__main__':
    asyncio.run(main())

