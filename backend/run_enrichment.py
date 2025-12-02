#!/usr/bin/env python3
"""
Simple Enrichment Runner - 5 at a time from Supabase
====================================================

Pulls unenriched companies directly from Supabase, scrapes 5,
syncs back, then waits for you to continue.

Usage:
    cd backend
    source ../venv/bin/activate
    python run_enrichment.py

Controls:
    - Press Enter to run next batch of 5
    - Type 'q' to quit
    - Progress auto-saves to Supabase
    - Failed companies logged to FAILED_ENRICHMENT.csv
"""

import asyncio
import csv
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / '.env', override=True)

import httpx

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("ERROR: pip install playwright && playwright install chromium")
    sys.exit(1)

try:
    from supabase import create_client
except ImportError:
    print("ERROR: pip install supabase")
    sys.exit(1)

# Config
BROWSERBASE_API_KEY = os.getenv('BROWSERBASE_API_KEY')
BROWSERBASE_PROJECT_ID = os.getenv('BROWSERBASE_PROJECT_ID')
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')

BATCH_SIZE = 5
OUTPUT_DIR = Path(__file__).parent / 'data' / 'final_enrichment_output'
FAILED_FILE = OUTPUT_DIR / 'FAILED_ENRICHMENT.csv'


def log_failed_company(company_name, domain, error, company_id):
    """Append failed company to CSV for later troubleshooting."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    file_exists = FAILED_FILE.exists()

    with open(FAILED_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['timestamp', 'company_id', 'company_name', 'domain', 'error'])
        writer.writerow([
            datetime.now().isoformat(),
            company_id,
            company_name,
            domain,
            error
        ])


def get_supabase():
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)


async def create_session():
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            "https://api.browserbase.com/v1/sessions",
            headers={"x-bb-api-key": BROWSERBASE_API_KEY, "Content-Type": "application/json"},
            json={"projectId": BROWSERBASE_PROJECT_ID}
        )
        response.raise_for_status()
        data = response.json()
        return data["id"], data.get("connectUrl")


async def close_session(session_id):
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            await client.post(
                f"https://api.browserbase.com/v1/sessions/{session_id}/stop",
                headers={"x-bb-api-key": BROWSERBASE_API_KEY}
            )
    except:
        pass


def extract_phones(content):
    patterns = [r'\(\d{3}\)\s*\d{3}[-.\s]\d{4}', r'\d{3}[-.\s]\d{3}[-.\s]\d{4}']
    phones = set()
    for pattern in patterns:
        for match in re.findall(pattern, content):
            digits = re.sub(r'\D', '', match)
            if len(digits) == 10 and digits[:3] not in ['000', '111', '555', '800', '888']:
                phones.add(match.strip())
    return list(phones)


def extract_emails(content):
    pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = set()
    for email in re.findall(pattern, content):
        if not any(x in email.lower() for x in ['example.com', 'domain.com', 'noreply']):
            emails.add(email.lower())
    return list(emails)


# ATL titles (executives, owners, decision makers - high priority)
ATL_TITLES = [
    'owner', 'co-owner', 'founder', 'co-founder', 'president', 'ceo', 'chief executive',
    'general manager', 'gm', 'director', 'vp', 'vice president', 'partner',
    'principal', 'managing', 'office manager', 'operations manager'
]

# BTL titles (technicians, installers, staff - still valuable contacts)
BTL_TITLES = [
    'technician', 'tech', 'installer', 'installation', 'service', 'hvac tech',
    'plumber', 'electrician', 'apprentice', 'helper', 'assistant',
    'dispatcher', 'coordinator', 'scheduler', 'admin', 'administrator',
    'permits', 'compliance', 'sales', 'estimator', 'supervisor', 'foreman',
    'lead', 'senior', 'junior', 'specialist', 'representative', 'rep'
]

# All titles combined for detection
ALL_TITLES = ATL_TITLES + BTL_TITLES

# Team page paths to check (prioritized - best/most common first)
# Both with and without trailing slashes
TEAM_PAGE_PATHS = [
    # High priority - most likely to have team info
    '/meet-the-team', '/meet-the-team/',
    '/team', '/team/',
    '/our-team', '/our-team/',
    '/about-us', '/about-us/',
    '/about', '/about/',
    '/staff', '/staff/',
    # Medium priority
    '/meet-our-team', '/meet-our-team/',
    '/leadership', '/leadership/',
    '/management', '/management/',
    '/people', '/people/',
    '/the-team', '/the-team/',
    '/our-staff', '/our-staff/',
    # Lower priority
    '/who-we-are', '/who-we-are/',
    '/company', '/company/',
    '/about/team', '/about/team/',
    '/aboutus', '/ourteam', '/meettheteam', '/ourstaff'
]

# Services that indicate good ICP fit for Coperniq
# HIGH VALUE: generators, commercial, maintenance = larger operations
ICP_SERVICES = [
    # GOLD signals (larger operations)
    'generator', 'generators', 'standby generator', 'backup generator',
    'commercial', 'commercial hvac', 'commercial refrigeration',
    'maintenance', 'maintenance plan', 'maintenance agreement', 'service agreement',
    'preventative maintenance', 'preventive maintenance',
    # Standard HVAC
    'ac repair', 'air conditioning', 'hvac', 'heating', 'cooling',
    'ductwork', 'furnace', 'heat pump', 'mini split', 'ductless',
    # Multi-trade (bigger companies)
    'plumbing', 'electrical', 'refrigeration',
    # Residential indicators
    'residential', 'home comfort'
]

# HVAC brands - indicates established contractor with brand partnerships
HVAC_BRANDS = [
    # Premium HVAC brands
    'Carrier', 'Trane', 'Lennox', 'Bryant', 'Rheem', 'Ruud', 'Goodman', 'Daikin',
    'American Standard', 'York', 'Amana', 'Mitsubishi', 'Fujitsu', 'LG', 'Samsung',
    'Bosch', 'Honeywell', 'Nest', 'Ecobee', 'Aprilaire', 'Coleman', 'Heil',
    'Payne', 'Comfortmaker', 'Tempstar', 'Day & Night', 'Arcoaire', 'Keeprite',
    # Generator brands (HIGH VALUE - indicates larger operation)
    'Generac', 'Kohler', 'Cummins', 'Briggs & Stratton', 'Champion',
    # Water heater brands
    'Navien', 'Rinnai', 'Noritz', 'Takagi', 'Bradford White', 'A.O. Smith'
]

# Service area page paths to check (with trailing slash variants)
SERVICE_AREA_PATHS = [
    '/service-area', '/service-area/',
    '/service-areas', '/service-areas/',
    '/areas-served', '/areas-served/',
    '/areas-we-serve', '/areas-we-serve/',
    '/locations', '/locations/',
    '/coverage', '/coverage/',
    '/service-locations', '/service-locations/',
    '/where-we-serve', '/where-we-serve/',
    '/cities-served', '/cities-served/',
    '/our-service-area', '/our-service-area/'
]


def is_atl_title(title):
    """Check if a title is ATL (decision maker) or BTL."""
    title_lower = title.lower()
    for atl in ATL_TITLES:
        if atl in title_lower:
            return True
    return False


def extract_contacts(content):
    """Extract ALL contacts (ATL + BTL) using multiple methods."""
    contacts = []
    seen = set()

    # Method 1: Text patterns like "Founded by X", "Owner: X"
    text_patterns = [
        (r'[Ff]ounded\s+(?:in\s+\d{4}\s+)?by\s+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', 'Founder'),
        (r'[Oo]wner[:\s-]+([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)', 'Owner'),
        (r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),\s*(?:[Oo]wner|[Ff]ounder|CEO|President)', 'Owner/Founder'),
        (r'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s*[-–]\s*(?:[Oo]wner|[Ff]ounder|CEO|President)', 'Owner/Founder'),
    ]

    for pattern, title in text_patterns:
        for match in re.findall(pattern, content):
            name = match.strip()
            if name and 5 <= len(name) <= 40 and name.lower() not in seen:
                words = name.split()
                if 2 <= len(words) <= 4:
                    contacts.append({'name': name, 'title': title, 'is_atl': True})
                    seen.add(name.lower())

    # Method 2: Look for "Name - Title" or "Name, Title" patterns with ALL titles
    for title_keyword in ALL_TITLES:
        is_atl = title_keyword in ATL_TITLES

        # Pattern: "John Smith - Owner" or "John Smith, General Manager"
        pattern = rf'([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)\s*[-–,]\s*{title_keyword}'
        for match in re.findall(pattern, content, re.IGNORECASE):
            name = match.strip()
            if name and 5 <= len(name) <= 40 and name.lower() not in seen:
                words = name.split()
                if 2 <= len(words) <= 4:
                    contacts.append({'name': name, 'title': title_keyword.title(), 'is_atl': is_atl})
                    seen.add(name.lower())

        # Pattern: "Owner: John Smith" or "General Manager - John Smith"
        pattern = rf'{title_keyword}\s*[-–:]\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+)'
        for match in re.findall(pattern, content, re.IGNORECASE):
            name = match.strip()
            if name and 5 <= len(name) <= 40 and name.lower() not in seen:
                words = name.split()
                if 2 <= len(words) <= 4:
                    contacts.append({'name': name, 'title': title_keyword.title(), 'is_atl': is_atl})
                    seen.add(name.lower())

    # Method 3: Look for Name on one line, Title within next few lines (team page cards)
    lines = [l.strip() for l in content.split('\n')]

    for i in range(len(lines)):
        current_line = lines[i]
        if not current_line:
            continue

        # Look ahead up to 3 lines for a title (to handle empty lines between name and title)
        title_found = None
        is_atl = False
        for offset in range(1, 4):
            if i + offset >= len(lines):
                break
            check_line = lines[i + offset].lower()
            if not check_line:
                continue

            # Check if this line is ANY title (ATL or BTL)
            for title_keyword in ALL_TITLES:
                if title_keyword in check_line and len(check_line) < 50:
                    title_found = lines[i + offset].strip().title()
                    is_atl = title_keyword in ATL_TITLES
                    break

            # Also check for exact title matches
            exact_atl = ['owner', 'owners', 'founder', 'founders', 'co-owner', 'co-founder',
                         'president', 'ceo', 'general manager', 'office manager']
            exact_btl = ['installation', 'technician', 'service technician', 'installer',
                         'permits and compliance', 'permits', 'compliance']

            for exact in exact_atl:
                if check_line == exact or check_line.rstrip('s') == exact.rstrip('s'):
                    title_found = check_line.title()
                    is_atl = True
                    break

            if not title_found:
                for exact in exact_btl:
                    if check_line == exact or exact in check_line:
                        title_found = check_line.title()
                        is_atl = False
                        break

            if title_found:
                break

        if title_found:
            # Check if current line looks like a name (2-5 capitalized words)
            words = current_line.split()
            if 2 <= len(words) <= 5 and 5 <= len(current_line) <= 40:
                # Check if words are capitalized (name pattern)
                if all(w[0].isupper() for w in words if w and len(w) > 0 and w[0].isalpha()):
                    # Exclude common non-name words and menu/service terms
                    skip_words = {
                        # Navigation/menu
                        'the', 'our', 'meet', 'about', 'company', 'team', 'staff',
                        'contact', 'home', 'services', 'phone', 'email', 'address',
                        'schedule', 'now', 'call', 'today', 'free', 'quote', 'estimate',
                        'learn', 'more', 'view', 'all', 'read', 'get', 'request', 'from',
                        # Industry/business terms
                        'heating', 'cooling', 'hvac', 'air', 'conditioning',
                        'residential', 'commercial', 'emergency', 'repair', 'installation',
                        'installations', 'repairs', 'maintenance', 'preventative', 'routine',
                        'service', 'agreement', 'agreements', 'area', 'areas',
                        'inquiry', 'about', 'new', 'existing', 'customer', 'customers',
                        # Common false positives
                        'financing', 'available', 'indoor', 'outdoor', 'quality', 'comfort',
                        'plumbing', 'electrical', 'products', 'systems', 'solutions',
                        'awards', 'recognition', 'promised', 'spring', 'valley', 'city',
                        'rating', 'ratings', 'reviews', 'review', 'google', 'yelp',
                        'privacy', 'policy', 'terms', 'conditions', 'copyright',
                        # More false positives from McAllister pattern
                        'full', 'by', 'a', 'an', 'is', 'are', 'was', 'were', 'be',
                        'membership', 'plan', 'plans', 'club', 'program', 'programs'
                    }
                    # Skip if any word is in skip list OR line contains '*' (form fields)
                    if not any(w.lower() in skip_words for w in words) and '*' not in current_line:
                        # Additional validation: first word should look like a first name (3-15 chars)
                        first_word = words[0]
                        if 3 <= len(first_word) <= 15 and first_word.isalpha():
                            # Last word should also be name-like (2-20 chars, alphabetic)
                            last_word = words[-1]
                            if 2 <= len(last_word) <= 20 and last_word.replace("'", "").isalpha():
                                name = current_line
                                if name.lower() not in seen:
                                    contacts.append({'name': name, 'title': title_found, 'is_atl': is_atl})
                                    seen.add(name.lower())

    return contacts


# Keep extract_atl as alias for backwards compatibility
def extract_atl(content):
    """Extract contacts - returns all contacts with is_atl flag."""
    return extract_contacts(content)


def extract_services(content):
    """Extract services offered that indicate ICP fit."""
    content_lower = content.lower()
    found_services = []
    for service in ICP_SERVICES:
        if service in content_lower:
            found_services.append(service)
    return found_services


def extract_brands(content):
    """Extract HVAC brands mentioned - indicates established contractor.

    More brands = likely larger operation with multiple partnerships.
    Premium brands (Carrier, Trane, Lennox) = quality-focused contractor.
    """
    content_lower = content.lower()
    found_brands = []
    for brand in HVAC_BRANDS:
        if brand.lower() in content_lower:
            found_brands.append(brand)
    return found_brands


def extract_owner_quote(content):
    """Extract quotes attributed to owner/founder/CEO.

    Patterns:
    - "quote text" - Name, Owner
    - "quote text" - Name Lastname, Founder
    - - Name, Owner (just the attribution without quote)
    """
    quotes = []

    # Pattern 1: Look for "- Name, Owner" or "– Name, Founder" etc.
    owner_pattern = r'[-–—]\s*([A-Z][a-z]+(?:\s+[A-Z]\.?)?\s+[A-Z][a-z]+),?\s+(Owner|Founder|Co-[Ff]ounder|CEO|President|Partner)'
    matches = re.findall(owner_pattern, content)
    for name, title in matches:
        quotes.append({'name': name.strip(), 'title': title})

    # Pattern 2: Look for "A Message From Our Owner" style sections
    message_pattern = r'(?:message from|letter from|note from|word from)\s+(?:our\s+)?(?:the\s+)?(owner|founder|ceo|president)'
    if re.search(message_pattern, content.lower()):
        # There's an owner message section - look for the name nearby
        pass  # The first pattern should catch the attribution

    return quotes


def extract_maintenance_plans(content):
    """Extract maintenance plan/membership names - BDR gold for openers.

    Common patterns:
    - "Comfort Club"
    - "Priority Service Agreement"
    - "Home Protection Plan"
    - "VIP Membership"
    - "Service Partner Program"
    """
    plans = []
    content_lower = content.lower()

    # Keywords that indicate a maintenance plan section
    plan_keywords = [
        'comfort club', 'service club', 'priority club', 'vip club',
        'maintenance plan', 'maintenance agreement', 'service agreement',
        'service plan', 'protection plan', 'home protection',
        'membership', 'priority member', 'preferred customer',
        'service partner', 'comfort agreement', 'priority service',
        'maintenance membership', 'annual plan', 'yearly plan'
    ]

    for keyword in plan_keywords:
        if keyword in content_lower:
            # Try to find the full branded name (capitalized version)
            # Look for the keyword in original content with surrounding context
            pattern = rf'([A-Z][A-Za-z\s&\']+)?({re.escape(keyword)})([A-Za-z\s&\']+)?'
            matches = re.findall(pattern, content, re.IGNORECASE)
            for match in matches:
                # Combine the parts
                full_name = ''.join(match).strip()
                if full_name and len(full_name) <= 50:
                    # Clean up and add
                    plans.append(full_name.title())

            # If no fancy name found, just add the keyword
            if not any(keyword.lower() in p.lower() for p in plans):
                plans.append(keyword.title())

    # Deduplicate
    seen = set()
    unique_plans = []
    for p in plans:
        p_lower = p.lower()
        if p_lower not in seen:
            seen.add(p_lower)
            unique_plans.append(p)

    return unique_plans[:5]  # Return top 5 to avoid noise


def extract_service_areas(content):
    """Extract service areas/cities from content.

    Looks for patterns like:
    - "Service Areas" sections with city lists
    - "We serve X, Y, Z" patterns
    - Bulleted/listed cities near "areas" or "locations" keywords

    Returns list of city names found.
    """
    areas = set()
    lines = content.split('\n')

    # Track if we're in a "service area" section
    in_service_section = False
    service_section_lines = 0

    # Filter out non-city words that appear in service sections
    skip_words = {
        # Navigation
        'home', 'about', 'contact', 'services', 'team', 'blog', 'news',
        'call', 'today', 'now', 'free', 'estimate', 'quote', 'schedule',
        # Industry terms (NOT cities!)
        'heating', 'cooling', 'hvac', 'air', 'conditioning', 'repair',
        'service', 'areas', 'we', 'serve', 'our', 'the', 'and', 'or',
        'residential', 'commercial', 'emergency', 'maintenance', 'installation',
        'plumbing', 'electrical', 'generator', 'generators', 'furnace',
        'ductless', 'mini', 'split', 'heat', 'pump', 'water', 'heater',
        # Common false positive phrases
        'air conditioning', 'full service', 'service agreement', 'new jersey',
        'south jersey', 'north jersey', 'central jersey',
        # Brand names (not cities)
        'carrier', 'trane', 'lennox', 'bryant', 'rheem', 'goodman', 'daikin',
        'generac', 'kohler', 'american', 'standard', 'york', 'amana',
        # Common words that get capitalized
        'county', 'township', 'borough', 'city', 'town', 'village',
        'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'
    }

    for i, line in enumerate(lines):
        line_clean = line.strip()
        line_lower = line_clean.lower()

        # Check if this line starts a service area section
        if any(phrase in line_lower for phrase in [
            'service area', 'areas served', 'areas we serve', 'we serve',
            'service locations', 'cities served', 'locations we serve',
            'proudly serving', 'serving the following'
        ]):
            in_service_section = True
            service_section_lines = 0
            continue

        # If in service section, look for city names (capitalized words)
        if in_service_section:
            service_section_lines += 1
            # Stop after 30 lines to avoid grabbing unrelated content
            if service_section_lines > 30:
                in_service_section = False
                continue

            # Look for capitalized words that could be cities
            # Pattern: "City Name" or "City-Name"
            words = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?(?:\s+[A-Z][a-z]+)?', line_clean)
            for word in words:
                word_lower = word.lower()
                # Skip if it's a common non-city word (check full phrase and individual words)
                if word_lower in skip_words:
                    continue
                # Also check if any word in the phrase is a skip word
                if any(w in skip_words for w in word_lower.split()):
                    continue
                # Skip very short or very long
                if len(word) < 3 or len(word) > 30:
                    continue
                # Skip if contains numbers
                if any(c.isdigit() for c in word):
                    continue
                areas.add(word)

        # Also look for inline patterns like "serving Alhambra, Pasadena, and Arcadia"
        serving_match = re.search(
            r'(?:serving|serve|service)\s+(?:in\s+)?(.+?)(?:\.|$)',
            line_lower
        )
        if serving_match:
            # Extract capitalized words from the match
            match_text = line_clean[serving_match.start():serving_match.end()]
            cities = re.findall(r'[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?', match_text)
            for city in cities:
                city_lower = city.lower()
                # Skip if any word in the phrase is a skip word
                if city_lower in skip_words or any(w in skip_words for w in city_lower.split()):
                    continue
                if 3 <= len(city) <= 25:
                    areas.add(city)

    return sorted(list(areas))


async def find_team_links(page):
    """Find team/about page links in navigation."""
    team_keywords = ['team', 'about', 'staff', 'leadership', 'people', 'management', 'who we are', 'meet']
    found_links = set()

    try:
        # Get all links from the page
        links = await page.eval_on_selector_all('a[href]', '''
            elements => elements.map(el => ({
                href: el.href,
                text: el.innerText.toLowerCase().trim()
            }))
        ''')

        for link in links:
            href = link.get('href', '')
            text = link.get('text', '')

            # Check if link text or href contains team keywords
            for keyword in team_keywords:
                if keyword in text or keyword in href.lower():
                    # Only add internal links
                    if href and not href.startswith('mailto:') and not href.startswith('tel:'):
                        found_links.add(href)
                        break
    except:
        pass

    return list(found_links)


async def scrape_one(company_id, company_name, domain):
    """Scrape one company, return dict of results."""
    result = {
        'company_id': company_id,
        'success': False,
        'phones': [],
        'emails': [],
        'atl_contacts': [],
        'services': [],
        'brands': [],
        'service_areas': [],
        'maintenance_plans': [],  # BDR gold - plan names for openers
        'pages_checked': [],
        'error': '',
        'duration': 0
    }
    start = time.time()
    session_id = None

    try:
        session_id, connect_url = await create_session()

        playwright = await async_playwright().start()
        browser = await playwright.chromium.connect_over_cdp(connect_url)
        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()

        base_url = f"https://{domain}"
        discovered_links = []

        # Landing page
        try:
            response = await asyncio.wait_for(
                page.goto(base_url, wait_until="domcontentloaded"),
                timeout=15.0
            )
            if response and response.status < 400:
                result['pages_checked'].append(base_url)
                content = await page.content()
                result['phones'] = extract_phones(content)
                result['emails'] = extract_emails(content)
                text = await page.inner_text('body')
                result['atl_contacts'] = extract_atl(text)
                result['services'] = extract_services(text)
                result['brands'] = extract_brands(text)
                result['service_areas'] = extract_service_areas(text)
                result['maintenance_plans'] = extract_maintenance_plans(text)

                # Discover team links from navigation
                discovered_links = await find_team_links(page)
        except asyncio.TimeoutError:
            result['error'] = 'Landing timeout'
        except Exception as e:
            result['error'] = str(e)[:50]

        # Build list of pages to check in priority order (team pages first)
        pages_to_check = []
        seen_urls = set()

        # Add static team page paths (in priority order)
        for path in TEAM_PAGE_PATHS:
            url = f"{base_url}{path}"
            if url not in seen_urls:
                pages_to_check.append(url)
                seen_urls.add(url)

        # Add discovered links from navigation (might find team links)
        for link in discovered_links:
            if domain in link and link not in seen_urls:
                pages_to_check.append(link)
                seen_urls.add(link)

        # Add service area page paths (lower priority)
        for path in SERVICE_AREA_PATHS:
            url = f"{base_url}{path}"
            if url not in seen_urls:
                pages_to_check.append(url)
                seen_urls.add(url)

        # Remove landing page (already checked)
        pages_to_check = [p for p in pages_to_check if p not in [base_url, f"{base_url}/"]]

        # Check each page (limit to first 15 to balance coverage vs. time)
        checked_count = 0
        for page_url in pages_to_check[:15]:
            try:
                response = await asyncio.wait_for(
                    page.goto(page_url, wait_until="domcontentloaded"),
                    timeout=8.0
                )
                if response and response.status < 400:
                    result['pages_checked'].append(page_url)
                    checked_count += 1
                    text = await page.inner_text('body')

                    # Extract ATL contacts
                    new_atl = extract_atl(text)
                    existing = {c['name'].lower() for c in result['atl_contacts']}
                    for c in new_atl:
                        if c['name'].lower() not in existing:
                            result['atl_contacts'].append(c)

                    # Extract additional services
                    new_services = extract_services(text)
                    for s in new_services:
                        if s not in result['services']:
                            result['services'].append(s)

                    # Extract service areas
                    new_areas = extract_service_areas(text)
                    for area in new_areas:
                        if area not in result['service_areas']:
                            result['service_areas'].append(area)

                    # Extract brands
                    new_brands = extract_brands(text)
                    for brand in new_brands:
                        if brand not in result['brands']:
                            result['brands'].append(brand)

                    # Extract maintenance plans
                    new_plans = extract_maintenance_plans(text)
                    for plan in new_plans:
                        if plan not in result['maintenance_plans']:
                            result['maintenance_plans'].append(plan)

                    # Extract additional phones/emails
                    content = await page.content()
                    for phone in extract_phones(content):
                        if phone not in result['phones']:
                            result['phones'].append(phone)
                    for email in extract_emails(content):
                        if email not in result['emails']:
                            result['emails'].append(email)

                await asyncio.sleep(0.3)
            except:
                pass

        await browser.close()
        await playwright.stop()
        result['success'] = True

    except Exception as e:
        result['error'] = str(e)[:100]

    finally:
        if session_id:
            await close_session(session_id)
        result['duration'] = time.time() - start

    return result


def sync_to_supabase(supabase, results):
    """Sync results back to Supabase."""
    companies_updated = 0
    contacts_added = 0

    for r in results:
        if not r['success']:
            continue

        company_id = r['company_id']

        # Update company with service_areas if found
        update_data = {'last_enriched_at': datetime.now().isoformat()}
        if r.get('service_areas'):
            # Store service areas as JSON array in a dedicated column if it exists
            # Otherwise just track in the enrichment metadata
            update_data['service_areas'] = r['service_areas']
        try:
            supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
            companies_updated += 1
        except Exception as e:
            # If service_areas column doesn't exist, try without it
            if 'service_areas' in update_data:
                del update_data['service_areas']
                try:
                    supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()
                    companies_updated += 1
                except Exception as e2:
                    print(f"    Update error: {e2}")
            else:
                print(f"    Update error: {e}")

        # Add ALL contacts (ATL + BTL) with proper is_atl flag
        for contact in r['atl_contacts']:
            # Skip contacts with invalid names (too long, contains bad chars)
            name = contact['name'].strip()
            if len(name) > 60 or '-' in name or '\n' in name:
                continue  # Skip garbage contacts like "agreements Full - Service"

            name_parts = name.split()
            # Truncate to fit DB columns (varchar 255)
            contact_data = {
                'company_id': company_id,
                'full_name': name[:100],  # Truncate to safe length
                'first_name': (name_parts[0] if name_parts else '')[:50],
                'last_name': (' '.join(name_parts[1:]) if len(name_parts) > 1 else '')[:50],
                'title': contact['title'][:100],  # Truncate title too
                'is_atl': contact.get('is_atl', True),  # Use actual flag from extraction
                'source': 'enrichment_runner'
            }
            try:
                existing = supabase.table('dim_contacts').select('contact_id').eq('company_id', company_id).eq('full_name', name[:100]).execute()
                if not existing.data:
                    supabase.table('dim_contacts').insert(contact_data).execute()
                    contacts_added += 1
            except Exception as e:
                print(f"    Contact error: {e}")

    return companies_updated, contacts_added


def get_unenriched_batch(supabase, batch_size):
    """Get next batch of unenriched companies with domains."""
    result = supabase.table('dim_companies')\
        .select('company_id, company_name, domain')\
        .not_.is_('domain', 'null')\
        .is_('last_enriched_at', 'null')\
        .limit(batch_size)\
        .execute()
    return result.data


async def run_batch(supabase, companies):
    """Run one batch."""
    results = []
    failed_count = 0

    for i, company in enumerate(companies, 1):
        company_id = company['company_id']
        name = company['company_name']
        domain = company['domain']

        print(f"  [{i}/{len(companies)}] {name} ({domain})...", end=" ", flush=True)

        r = await scrape_one(company_id, name, domain)
        # Store company info in result for failed logging
        r['company_name'] = name
        r['domain'] = domain
        results.append(r)

        if r['success']:
            contacts = r['atl_contacts']
            atl_count = sum(1 for c in contacts if c.get('is_atl', True))
            btl_count = len(contacts) - atl_count
            phones = len(r['phones'])
            services = len(r.get('services', []))
            areas = len(r.get('service_areas', []))
            brands = len(r.get('brands', []))
            plans = len(r.get('maintenance_plans', []))
            pages = len(r.get('pages_checked', []))
            # Show maintenance plan names if found (BDR gold!)
            plan_info = ""
            if r.get('maintenance_plans'):
                plan_info = f" 🎯{r['maintenance_plans'][0][:20]}"
            print(f"OK {r['duration']:.0f}s ({atl_count} ATL, {btl_count} BTL, {phones} ph, {services} svc, {areas} areas, {brands} brands{plan_info})")
        else:
            print(f"FAIL: {r['error']}")
            # Log to failed companies CSV
            log_failed_company(name, domain, r['error'], company_id)
            failed_count += 1

    if failed_count > 0:
        print(f"  📝 {failed_count} failed companies logged to {FAILED_FILE.name}")

    return results


async def main():
    # Validate
    if not all([BROWSERBASE_API_KEY, BROWSERBASE_PROJECT_ID, SUPABASE_URL, SUPABASE_SERVICE_KEY]):
        print("ERROR: Missing environment variables")
        sys.exit(1)

    supabase = get_supabase()

    # Get stats
    total = supabase.table('dim_companies').select('company_id', count='exact').not_.is_('domain', 'null').is_('last_enriched_at', 'null').execute()
    print(f"\n{'='*60}")
    print(f"ENRICHMENT RUNNER")
    print(f"{'='*60}")
    print(f"Companies needing enrichment: {total.count}")
    print(f"Batch size: {BATCH_SIZE}")
    print(f"Estimated batches: {(total.count + BATCH_SIZE - 1) // BATCH_SIZE}")
    print(f"\nPress Enter to start, 'q' to quit")

    batch_num = 0
    total_enriched = 0
    total_atl = 0

    while True:
        # Get next batch
        companies = get_unenriched_batch(supabase, BATCH_SIZE)

        if not companies:
            print("\n ALL COMPANIES ENRICHED!")
            break

        batch_num += 1
        remaining = total.count - total_enriched
        print(f"\n{'='*60}")
        print(f"BATCH {batch_num} ({remaining} remaining)")
        print(f"{'='*60}")

        # Run batch
        results = await run_batch(supabase, companies)

        # Sync
        print("\n  Syncing to Supabase...", end=" ")
        updated, contacts = sync_to_supabase(supabase, results)
        print(f"{updated} companies, {contacts} contacts")

        total_enriched += updated
        total_atl += contacts

        # Stats
        successful = sum(1 for r in results if r['success'])
        failed = len(results) - successful
        if failed > 0:
            print(f"  {failed} failed (will retry later)")

        print(f"\n  Session total: {total_enriched} enriched, {total_atl} ATL found")

        # Prompt
        response = input("\nPress Enter for next batch, 'q' to quit: ")
        if response.lower() == 'q':
            break

    print(f"\n{'='*60}")
    print("SESSION COMPLETE")
    print(f"{'='*60}")
    print(f"Companies enriched: {total_enriched}")
    print(f"ATL contacts found: {total_atl}")
    if FAILED_FILE.exists():
        print(f"\n⚠️  Failed companies logged to: {FAILED_FILE}")
        print("   Review and retry these later")


if __name__ == '__main__':
    asyncio.run(main())
