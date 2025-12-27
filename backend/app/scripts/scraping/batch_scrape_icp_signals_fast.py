#!/usr/bin/env python3
"""
FAST Batch ICP Signal Scraper
==============================
Speed-optimized version that checks only essential pages.

Uses:
- BeautifulSoup: Fast ICP signal detection (keywords)
- Browserbase: High-quality contact extraction (JavaScript rendering)

Usage:
    python3 batch_scrape_icp_signals_fast.py              # Start batch 0
    python3 batch_scrape_icp_signals_fast.py --batch 5    # Resume from batch 5
    python3 batch_scrape_icp_signals_fast.py --auto       # Run all batches non-stop

Author: Claude + Tim
Date: Dec 22, 2025
"""
import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client
import argparse
import httpx
from bs4 import BeautifulSoup
import re

# Add app to path for imports
sys.path.insert(0, str(Path(__file__).parent))

load_dotenv(Path(__file__).parent.parent / '.env')

# Import Browserbase team scraper
from app.services.browserbase_team_scraper import BrowserbaseTeamScraper

# Config
BATCH_SIZE = 25
DELAY_BETWEEN_COMPANIES = 1  # Faster delay (1 sec instead of 2)
TIMEOUT_PER_COMPANY = 30     # Max 30 seconds per company

# Connect to Supabase
supabase = create_client(os.getenv('SUPABASE_URL'), os.getenv('SUPABASE_SERVICE_KEY'))

# COMPREHENSIVE page list - check all common variants (20 pages)
ESSENTIAL_PAGES = [
    # Core pages (always check)
    "/",                      # Homepage
    "/about",                 # About us
    "/about-us",              # About variant

    # Services pages (multiple variants)
    "/services",              # Services
    "/service-division",      # Services variant (Gibson, etc.)
    "/what-we-do",            # Services variant
    "/capabilities",          # Capabilities

    # High-value signals
    "/commercial",            # Commercial
    "/commercial-services",   # Commercial variant
    "/industrial",            # Industrial (HIGH VALUE)
    "/design-build",          # Design-build (HIGH VALUE)

    # Other signals
    "/generators",            # Generators
    "/awards",                # Awards

    # Team/people pages (for contact extraction)
    "/team",                  # Team
    "/our-team",              # Our team
    "/leadership",            # Leadership
    "/management",            # Management
    "/meet-the-team",         # Meet the team
]

# =============================================================================
# SIGNAL DETECTION PATTERNS (70 signals - 7 categories)
# Coperniq ICP: MEP, Multi-Trade, Self-Performing, Asset-Centric, $5-50M, 25-200+
# =============================================================================

SIGNAL_PATTERNS = {
    # =========================================================================
    # CATEGORY 1: SERVICE OFFERING (10)
    # =========================================================================
    'has_commercial': [
        r'commercial', r'business', r'office', r'retail', r'multi.?family',
        r'commercial projects', r'commercial clients'
    ],
    'has_industrial': [
        r'industrial', r'manufacturing', r'facility', r'plant', r'warehouse',
        r'industrial projects', r'process piping', r'heavy\s+industrial'
    ],
    'has_residential': [
        r'residential', r'home', r'homeowner', r'house', r'single.?family'
    ],
    'has_solar_commercial': [
        r'commercial solar', r'c\s*&\s*i', r'ground mount', r'carport solar',
        r'utility.?scale', r'solar farm'
    ],
    'has_solar_residential': [
        r'residential solar', r'rooftop solar', r'home solar', r'solar panel'
    ],
    'has_battery_storage': [
        r'battery', r'storage', r'powerwall', r'backup', r'ESS', r'energy storage',
        r'tesla battery', r'enphase battery', r'backup power'
    ],
    'has_ev_charging': [
        r'ev\s+charg', r'electric vehicle', r'charging station', r'EVSE',
        r'chargepoint', r'tesla charger', r'level 2 charger'
    ],
    'has_generators': [
        r'generator', r'backup power', r'standby power', r'emergency power',
        r'generac', r'kohler', r'cummins'
    ],
    'has_emergency_service': [
        r'24/7', r'24 hour', r'emergency', r'always available',
        r'emergency service', r'on.?call'
    ],
    'has_maintenance_plans': [
        r'maintenance plan', r'service plan', r'preventive maintenance',
        r'maintenance agreement', r'annual maintenance'
    ],

    # =========================================================================
    # CATEGORY 2: CAPABILITY (10)
    # =========================================================================
    'has_design_build': [
        r'design.build', r'design/build', r'design & build', r'design-build',
        r'turnkey', r'design.construct', r'full.?service'
    ],
    'has_engineering': [
        r'engineering', r'engineer', r'CAD', r'design engineer', r'PE license',
        r'in.?house engineering', r'engineering team', r'mechanical engineer'
    ],
    'has_building_automation': [
        r'building automation', r'BAS', r'controls', r'automation system',
        r'HVAC controls', r'building controls', r'smart building', r'BMS'
    ],
    'has_medical_specialization': [
        r'medical gas', r'healthcare', r'hospital', r'clinic', r'med.?gas',
        r'healthcare facilities', r'medical facilities'
    ],
    'has_multi_location': [
        r'locations', r'offices', r'branches', r'serving.*multiple',
        r'nationwide', r'regional offices', r'\d+\s+locations'
    ],
    'has_large_service_area': [
        r'serving.*county', r'statewide', r'tri.?state', r'multiple states',
        r'regional', r'metro area'
    ],
    'has_project_management': [
        r'project manag', r'PM team', r'construction management',
        r'project coordinator', r'job superintendent'
    ],
    'has_permitting_services': [
        r'permitting', r'permit', r'code compliance', r'inspection',
        r'building department', r'AHJ'
    ],
    'has_monitoring': [
        r'monitoring', r'remote monitoring', r'solar monitoring',
        r'system monitoring', r'performance monitoring'
    ],
    'has_utility_scale': [
        r'utility.?scale', r'utility project', r'large.?scale',
        r'megawatt', r'MW', r'grid.?scale'
    ],

    # =========================================================================
    # CATEGORY 3: CREDIBILITY (10)
    # =========================================================================
    'has_awards': [
        r'award', r'recognition', r'certified', r'accredited', r'abc\s+award',
        r'safety award', r'excellence award', r'best of'
    ],
    'has_certifications': [
        r'NABCEP', r'OSHA', r'certified', r'accredited', r'NATE',
        r'EPA certified', r'master electrician'
    ],
    'has_licensed': [
        r'licensed', r'license\s*#', r'contractor license', r'state license',
        r'fully licensed'
    ],
    'has_bonded_insured': [
        r'bonded', r'insured', r'liability insurance', r'workers comp',
        r'fully insured', r'bonded & insured'
    ],
    'has_nabcep': [
        r'NABCEP', r'north american board', r'certified solar'
    ],
    'has_reviews_visible': [
        r'reviews', r'testimonials', r'google reviews', r'yelp',
        r'5\s*star', r'4\.9\s*star', r'customer reviews'
    ],
    'has_project_gallery': [
        r'gallery', r'portfolio', r'our work', r'projects', r'case studies',
        r'project photos', r'completed projects'
    ],
    'has_case_studies': [
        r'case stud', r'success stor', r'project spotlight', r'featured project'
    ],
    'has_testimonials': [
        r'testimonial', r'customer stories', r'what our customers say',
        r'client feedback', r'customer reviews'
    ],
    'has_bbb_rating': [
        r'BBB', r'better business bureau', r'A\+\s*rating', r'accredited business'
    ],

    # =========================================================================
    # CATEGORY 4: PARTNERSHIP (10)
    # =========================================================================
    'has_oem_partnerships': [
        r'authorized dealer', r'certified installer', r'factory.?authorized',
        r'preferred contractor', r'partner', r'elite dealer'
    ],
    'has_enphase': [r'enphase', r'iq\s*\d', r'microinverter'],
    'has_solaredge': [r'solaredge', r'solar edge', r'power optimizer'],
    'has_tesla': [r'tesla', r'powerwall', r'tesla certified'],
    'has_lg_panels': [r'\blg\b', r'lg solar', r'lg neon', r'lg chem'],
    'has_generac': [r'generac', r'generac dealer', r'pwrcell'],
    'has_sunpower': [r'sunpower', r'sun power', r'maxeon'],
    'has_financing_partners': [
        r'mosaic', r'sunlight financial', r'goodleap', r'sunnova',
        r'financing partner', r'lending partner'
    ],
    'has_utility_partners': [
        r'utility partner', r'rebate partner', r'net metering',
        r'utility program', r'SREC'
    ],
    'has_manufacturer_certified': [
        r'manufacturer certified', r'factory trained', r'OEM certified',
        r'authorized service'
    ],

    # =========================================================================
    # CATEGORY 5: GROWTH (5)
    # =========================================================================
    'is_hiring': [
        r'hiring', r'careers', r'job opening', r'join our team',
        r'now hiring', r'employment', r'job opportunities'
    ],
    'has_funding': [
        r'funding', r'investment', r'venture', r'series [a-z]',
        r'raised.*million', r'backed by'
    ],
    'has_expansion_news': [
        r'expansion', r'new location', r'opening soon', r'grand opening',
        r'new office', r'expanding'
    ],
    'has_inc_5000': [
        r'inc\s*\.?\s*5000', r'inc 500', r'fastest growing', r'top 100'
    ],
    'has_recent_projects': [
        r'recent project', r'latest project', r'completed.*2024',
        r'completed.*2025', r'current project'
    ],

    # =========================================================================
    # CATEGORY 6: FINANCING (5)
    # =========================================================================
    'has_financing': [
        r'financing', r'payment plan', r'0%.*financing', r'finance options',
        r'flexible payment', r'financing available'
    ],
    'has_ppa': [
        r'\bPPA\b', r'power purchase agreement', r'solar lease',
        r'\$0 down solar', r'no money down'
    ],
    'has_lease_options': [
        r'lease', r'leasing', r'solar lease', r'equipment lease'
    ],
    'has_loan_programs': [
        r'loan', r'solar loan', r'home improvement loan', r'low interest'
    ],
    'has_rebate_assistance': [
        r'rebate', r'incentive', r'tax credit', r'ITC', r'federal tax credit',
        r'state rebate', r'utility rebate'
    ],

    # =========================================================================
    # CATEGORY 7: COPERNIQ IDEAL ICP (20) - THE MONEY SIGNALS
    # MEP, Multi-Trade, Self-Performing, Asset-Centric, $5-50M, 25-200+
    # =========================================================================

    # MEP Trade Indicators
    'has_electrical_trade': [
        r'electrical contractor', r'electrician', r'electrical service',
        r'wiring', r'panel', r'circuit', r'electrical work'
    ],
    'has_mechanical_trade': [
        r'mechanical contractor', r'mechanical service', r'piping',
        r'ductwork', r'mechanical system', r'process piping'
    ],
    'has_plumbing_trade': [
        r'plumbing', r'plumber', r'piping', r'water heater', r'drain',
        r'fixture', r'plumbing service'
    ],
    'has_hvac_trade': [
        r'\bhvac\b', r'heating', r'cooling', r'air conditioning',
        r'ventilation', r'furnace', r'heat pump', r'hvac service'
    ],
    'has_fire_protection': [
        r'fire protection', r'sprinkler', r'fire alarm', r'fire suppression',
        r'fire safety', r'fire sprinkler'
    ],
    'is_mep_contractor': [
        r'\bMEP\b', r'mechanical electrical plumbing', r'full MEP',
        r'MEP service', r'M/E/P', r'mep contractor'
    ],

    # Multi-Trade / Multi-License
    'is_multi_trade': [
        r'multiple trades', r'full.?service', r'one.?stop', r'comprehensive',
        r'electrical and mechanical', r'electrical and plumbing',
        r'hvac and electrical', r'plumbing and electrical'
    ],
    'is_multi_license': [
        r'multiple license', r'licensed in', r'license\s*#.*license\s*#',
        r'C-10.*C-46', r'A.*B\s+license', r'contractor license'
    ],

    # Self-Performing (NOT just GC who subs out)
    'is_self_performing': [
        r'self.?performing', r'in.?house team', r'own technician',
        r'we perform', r'our crews do', r'our team performs'
    ],
    'has_own_crews': [
        r'our team', r'our technician', r'our electrician', r'in.?house crew',
        r'field crew', r'our installer'
    ],
    'has_in_house_technicians': [
        r'in.?house', r'on.?staff', r'employed technician', r'W-2 employee',
        r'not subcontractor', r'full.?time technician'
    ],
    'has_apprenticeship': [
        r'apprentice', r'apprenticeship', r'training program', r'IBEW',
        r'union', r'journeyman'
    ],

    # Asset-Centric
    'is_asset_centric': [
        r'equipment', r'fleet', r'tools', r'vehicle', r'asset',
        r'inventory', r'warehouse'
    ],
    'has_fleet': [
        r'fleet', r'truck', r'van', r'vehicle', r'service vehicle',
        r'fully stocked', r'mobile workshop'
    ],
    'has_warehouse': [
        r'warehouse', r'inventory', r'parts', r'material', r'stock',
        r'supply', r'distribution center'
    ],
    'has_equipment_yard': [
        r'equipment yard', r'staging', r'heavy equipment', r'material storage',
        r'laydown yard'
    ],

    # Legacy signals (keep for backwards compatibility)
    'has_specials': [
        r'special', r'promotion', r'discount', r'coupon', r'limited.?time',
        r'save \$', r'\$\d+\s+off'
    ],
    'has_membership': [
        r'membership', r'maintenance plan', r'service plan', r'club',
        r'maintenance agreement', r'service agreement', r'preventive maintenance'
    ],
}


def extract_contacts(text: str) -> list:
    """
    Extract contact names from text.
    Looks for capitalized names (2-3 words) that look like real people.
    """
    # Find all potential names (2-3 capitalized words)
    name_pattern = r'\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b'
    potential_names = re.findall(name_pattern, text)

    # EXTENSIVE stopword list - filter out garbage
    stopwords = {
        # Common words
        'The', 'Our', 'About', 'Contact', 'Services', 'Home', 'Team', 'And', 'With', 'From',
        'When', 'This', 'That', 'More', 'All', 'New', 'Get', 'Learn', 'Read', 'Click', 'View',
        'Soon', 'Coming', 'Copyright', 'Reserved', 'Rights', 'Privacy', 'Policy', 'Terms',

        # Directions & locations
        'North', 'South', 'East', 'West', 'United States', 'North Florida', 'South Florida',
        'New York', 'New Jersey', 'New Hampshire', 'New Mexico', 'North Carolina', 'South Carolina',
        'North Dakota', 'South Dakota', 'West Virginia', 'Rhode Island', 'Puerto Rico',

        # Address components
        'Street Address', 'City', 'State', 'Zip', 'Code', 'Panther Ln', 'Suite', 'Address Line',

        # Business terms
        'Home Services', 'Commercial Roofing', 'Residential Roofing', 'Insurance Process',
        'Free Estimate', 'Read Reviews', 'Request Your', 'Contact Us', 'About Us', 'Learn More',
        'Emergency Repair', 'Roof Types', 'Additional Services', 'Special Offer', 'Get Started',
        'Click Here', 'Sign Up', 'Call Now', 'Schedule Now', 'Book Now', 'Learn How',

        # Building/construction terms
        'Asphalt Shingle', 'Roof Repair', 'Emergency Tarping', 'General Contractor',
        'Building Automation', 'Design Build', 'Roofing Contractor', 'Heating Cooling',

        # Generic phrases
        'Your Name', 'First Name', 'Last Name', 'Email Address', 'Phone Number',
        'Corporate Office', 'Corporate Phone', 'Armed Forces', 'Select An',
        'Refer A', 'Message Us', 'Follow Us', 'Join Us',

        # US states (abbreviated forms often show up)
        'Florida', 'Georgia', 'Alabama', 'Alaska', 'Arizona', 'Arkansas', 'California', 'Colorado',
        'Connecticut', 'Delaware', 'Hawaii', 'Idaho', 'Illinois', 'Indiana', 'Iowa', 'Kansas',
        'Kentucky', 'Louisiana', 'Maine', 'Maryland', 'Massachusetts', 'Michigan', 'Minnesota',
        'Mississippi', 'Missouri', 'Montana', 'Nebraska', 'Nevada', 'Ohio', 'Oklahoma', 'Oregon',
        'Pennsylvania', 'Tennessee', 'Texas', 'Vermont', 'Virginia', 'Washington', 'Wisconsin', 'Wyoming',

        # Common company suffixes
        'Inc', 'Llc', 'Corp', 'Corporation', 'Company', 'Group', 'Associates', 'Partners',
    }

    # Filter out stopwords and obvious non-names
    filtered = []
    for name in potential_names:
        # Skip if in stopwords
        if name in stopwords:
            continue

        # Skip if too short
        if len(name) <= 3:
            continue

        # Skip if contains common non-name patterns
        if any(word in name for word in ['Roof', 'Roofing', 'Service', 'Services', 'Construction',
                                          'Heating', 'Cooling', 'Plumbing', 'Electric', 'Solar',
                                          'Building', 'Phone', 'Fax', 'Email', 'Office', 'Coast',
                                          'Island', 'County', 'City', 'Street', 'Avenue', 'Drive',
                                          'Suite', 'Floor', 'Building', 'Center', 'Plaza',
                                          'Coming', 'Soon', 'Copyright', 'Reserved', 'Rights',
                                          'Privacy', 'Policy', 'Terms', 'Conditions', 'Website']):
            continue

        # Skip if all parts are too short (like "Jo Ann")
        parts = name.split()
        if all(len(part) <= 2 for part in parts):
            continue

        filtered.append(name)

    # Remove duplicates, keep unique names
    unique_names = list(set(filtered))

    # Return as contact list (accepting names mentioned even just 1 time)
    contacts = [{"name": name, "title": ""} for name in unique_names]

    return contacts[:15]  # Max 15 contacts per company


async def fast_scrape(website: str) -> dict:
    """
    Fast scraper - checks essential pages with timeout, extracts signals + contacts
    """
    if not website.startswith('http'):
        website = f'https://{website}'

    signals = {key: False for key in SIGNAL_PATTERNS.keys()}
    all_text = ""
    all_text_original = ""  # Keep original case for name extraction

    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(10.0),  # 10 sec per page
            follow_redirects=True,
            max_redirects=5,  # Prevent infinite redirect loops
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        ) as client:

            for page_path in ESSENTIAL_PAGES:
                url = f"{website}{page_path}" if page_path != "/" else website

                try:
                    response = await client.get(url)

                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')

                        # Remove scripts/styles
                        for tag in soup(['script', 'style', 'meta', 'link']):
                            tag.decompose()

                        text = soup.get_text(separator=' ', strip=True)
                        all_text += " " + text.lower()
                        all_text_original += " " + text  # Keep original case

                except (httpx.HTTPError, Exception):
                    # Skip failed pages silently
                    continue

            # Detect signals from combined text
            for signal_name, patterns in SIGNAL_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, all_text, re.IGNORECASE):
                        signals[signal_name] = True
                        break

            # Extract contacts from original case text
            contacts = extract_contacts(all_text_original)

            return {"signals": signals, "contacts": contacts, "error": None}

    except Exception as e:
        return {"signals": signals, "contacts": [], "error": str(e)}


async def save_contacts(company_id: str, contacts: list):
    """Save extracted contacts to dim_contacts"""
    if not contacts:
        return 0

    saved = 0
    for contact in contacts:
        name = contact.get("name", "").strip()
        if not name or len(name) < 3:
            continue

        # Parse first/last name
        name_parts = name.split()
        first_name = name_parts[0] if name_parts else ""
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        # Check if contact already exists (case-insensitive)
        try:
            existing = supabase.table("dim_contacts") \
                .select("contact_id") \
                .eq("company_id", company_id) \
                .ilike("full_name", name) \
                .limit(1) \
                .execute()

            if existing.data:
                continue  # Skip existing contact

            contact_data = {
                "company_id": company_id,
                "full_name": name,
                "first_name": first_name,
                "last_name": last_name,
                "title": contact.get("title", ""),
                "is_atl": True,  # Assume ATL (mentioned on website)
                "source": "website_scraper_fast",
                "confidence": 60,  # Medium-low confidence (no title)
            }

            # Insert (not upsert - we already checked for duplicates)
            supabase.table("dim_contacts").insert(contact_data).execute()
            saved += 1
        except Exception:
            pass  # Ignore errors

    return saved


async def scrape_and_save(company: dict):
    """Scrape company website and save ICP signals + contacts"""
    company_id = company["company_id"]
    company_name = company["company_name"]
    website = company.get("website") or company.get("domain")

    if not website:
        print(f"⏭️  {company_name[:40]:<40} No website")
        return {"status": "skipped", "reason": "no_website"}

    print(f"🔍 {company_name[:40]:<40} ", end='', flush=True)

    try:
        # Fast scrape with timeout
        result = await asyncio.wait_for(
            fast_scrape(website),
            timeout=TIMEOUT_PER_COMPANY
        )

        if result.get('error'):
            print(f"❌ {result['error'][:20]}")
            return {"status": "failed"}

        signals = result.get("signals", {})
        contacts = result.get("contacts", [])

        # Count trades for trade_count
        trade_signals = ['has_electrical_trade', 'has_mechanical_trade', 'has_plumbing_trade',
                         'has_hvac_trade', 'has_fire_protection']
        trade_count = sum(1 for t in trade_signals if signals.get(t, False))

        # Count OEMs for oem_count
        oem_signals = ['has_enphase', 'has_solaredge', 'has_tesla', 'has_lg_panels',
                       'has_generac', 'has_sunpower']
        oem_count = sum(1 for o in oem_signals if signals.get(o, False))

        # Derive composite signals
        is_multi_trade = trade_count >= 2 or signals.get('is_multi_trade', False)
        is_multi_oem = oem_count >= 2 or signals.get('has_oem_partnerships', False)

        # Build update_data with ALL 70 signals
        update_data = {
            # === CATEGORY 1: SERVICE OFFERING (10) ===
            'has_commercial': signals.get('has_commercial', False),
            'has_industrial': signals.get('has_industrial', False),
            'has_residential': signals.get('has_residential', False),
            'has_solar_commercial': signals.get('has_solar_commercial', False),
            'has_solar_residential': signals.get('has_solar_residential', False),
            'has_battery_storage': signals.get('has_battery_storage', False),
            'has_ev_charging': signals.get('has_ev_charging', False),
            'has_generators': signals.get('has_generators', False),
            'has_emergency_service': signals.get('has_emergency_service', False),
            'has_maintenance_plans': signals.get('has_maintenance_plans', False),

            # === CATEGORY 2: CAPABILITY (10) ===
            'has_design_build': signals.get('has_design_build', False),
            'has_engineering': signals.get('has_engineering', False),
            'has_building_automation': signals.get('has_building_automation', False),
            'has_medical_specialization': signals.get('has_medical_specialization', False),
            'has_multi_location': signals.get('has_multi_location', False),
            'has_large_service_area': signals.get('has_large_service_area', False),
            'has_project_management': signals.get('has_project_management', False),
            'has_permitting_services': signals.get('has_permitting_services', False),
            'has_monitoring': signals.get('has_monitoring', False),
            'has_utility_scale': signals.get('has_utility_scale', False),

            # === CATEGORY 3: CREDIBILITY (10) ===
            'has_awards': signals.get('has_awards', False),
            'has_certifications': signals.get('has_certifications', False),
            'has_licensed': signals.get('has_licensed', False),
            'has_bonded_insured': signals.get('has_bonded_insured', False),
            'has_nabcep': signals.get('has_nabcep', False),
            'has_reviews_visible': signals.get('has_reviews_visible', False),
            'has_project_gallery': signals.get('has_project_gallery', False),
            'has_case_studies': signals.get('has_case_studies', False),
            'has_testimonials': signals.get('has_testimonials', False),
            'has_bbb_rating': signals.get('has_bbb_rating', False),

            # === CATEGORY 4: PARTNERSHIP (10) ===
            'has_oem_partnerships': signals.get('has_oem_partnerships', False),
            'has_enphase': signals.get('has_enphase', False),
            'has_solaredge': signals.get('has_solaredge', False),
            'has_tesla': signals.get('has_tesla', False),
            'has_lg_panels': signals.get('has_lg_panels', False),
            'has_generac': signals.get('has_generac', False),
            'has_sunpower': signals.get('has_sunpower', False),
            'has_financing_partners': signals.get('has_financing_partners', False),
            'has_utility_partners': signals.get('has_utility_partners', False),
            'has_manufacturer_certified': signals.get('has_manufacturer_certified', False),

            # === CATEGORY 5: GROWTH (5) ===
            'is_hiring': signals.get('is_hiring', False),
            'has_funding': signals.get('has_funding', False),
            'has_expansion_news': signals.get('has_expansion_news', False),
            'has_inc_5000': signals.get('has_inc_5000', False),
            'has_recent_projects': signals.get('has_recent_projects', False),

            # === CATEGORY 6: FINANCING (5) ===
            'has_financing': signals.get('has_financing', False),
            'has_ppa': signals.get('has_ppa', False),
            'has_lease_options': signals.get('has_lease_options', False),
            'has_loan_programs': signals.get('has_loan_programs', False),
            'has_rebate_assistance': signals.get('has_rebate_assistance', False),

            # === CATEGORY 7: COPERNIQ ICP (20) - THE MONEY SIGNALS ===
            # MEP Trades
            'has_electrical_trade': signals.get('has_electrical_trade', False),
            'has_mechanical_trade': signals.get('has_mechanical_trade', False),
            'has_plumbing_trade': signals.get('has_plumbing_trade', False),
            'has_hvac_trade': signals.get('has_hvac_trade', False),
            'has_fire_protection': signals.get('has_fire_protection', False),
            'is_mep_contractor': signals.get('is_mep_contractor', False),

            # Multi-Trade / Multi-License
            'is_multi_trade': is_multi_trade,
            'is_multi_license': signals.get('is_multi_license', False),
            'trade_count': trade_count,

            # Multi-OEM
            'is_multi_oem': is_multi_oem,
            'oem_count': oem_count,

            # Self-Performing
            'is_self_performing': signals.get('is_self_performing', False),
            'has_own_crews': signals.get('has_own_crews', False),
            'has_in_house_technicians': signals.get('has_in_house_technicians', False),
            'has_apprenticeship': signals.get('has_apprenticeship', False),

            # Asset-Centric
            'is_asset_centric': signals.get('is_asset_centric', False),
            'has_fleet': signals.get('has_fleet', False),
            'has_warehouse': signals.get('has_warehouse', False),
            'has_equipment_yard': signals.get('has_equipment_yard', False),

            # Legacy
            'has_specials': signals.get('has_specials', False),
            'has_membership': signals.get('has_membership', False),

            # Metadata
            'enrichment_status': 'free_enriched',
            'ai_enriched_at': datetime.now().isoformat(),
        }

        # Save signals to database
        supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()

        # Save contacts to database
        contacts_saved = await save_contacts(company_id, contacts)

        # Count signals (boolean only)
        signal_count = sum(1 for k, v in update_data.items()
                          if (k.startswith('has_') or k.startswith('is_')) and v == True)

        # Show key ICP signals
        icp_signals = []
        if is_multi_trade: icp_signals.append('multi-trade')
        if signals.get('is_mep_contractor'): icp_signals.append('MEP')
        if signals.get('is_self_performing'): icp_signals.append('self-perf')
        if signals.get('is_asset_centric'): icp_signals.append('asset')
        if signals.get('has_commercial'): icp_signals.append('comm')
        if signals.get('has_design_build'): icp_signals.append('D-B')

        signal_preview = ', '.join(icp_signals[:3]) if icp_signals else 'none'

        print(f"✅ {signal_count}/70 ({signal_preview}) +{contacts_saved}👤")

        return {"status": "success", "signals": signal_count, "contacts": contacts_saved}

    except asyncio.TimeoutError:
        print(f"⏱️  timeout (>{TIMEOUT_PER_COMPANY}s)")
        return {"status": "timeout"}
    except Exception as e:
        print(f"❌ {str(e)[:20]}")
        return {"status": "failed", "error": str(e)}


async def run_batch(batch_num: int, auto: bool = False, single: bool = False, max_batches: int = 0, batches_run: int = 0):
    """Run a single batch of 25 companies"""

    # Fetch all companies (ordered by name for consistent batching)
    all_companies = supabase.table('dim_companies') \
        .select('company_id, company_name, website, domain') \
        .order('company_name') \
        .execute()

    total_companies = len(all_companies.data)
    total_batches = (total_companies + BATCH_SIZE - 1) // BATCH_SIZE

    # Calculate batch range
    start_idx = batch_num * BATCH_SIZE
    end_idx = min(start_idx + BATCH_SIZE, total_companies)

    if start_idx >= total_companies:
        print(f"\n❌ Batch {batch_num} is out of range (only {total_batches} batches total)")
        return

    batch_companies = all_companies.data[start_idx:end_idx]

    print("\n" + "=" * 80)
    print(f"FAST BATCH {batch_num}/{total_batches - 1} ({len(batch_companies)} companies)")
    print(f"Companies {start_idx + 1}-{end_idx} of {total_companies}")
    print(f"Max time: {TIMEOUT_PER_COMPANY}s per company")
    print("=" * 80 + "\n")

    # Track results
    successful = 0
    failed = 0
    skipped = 0
    timeouts = 0

    start_time = datetime.now()

    # Process each company
    for i, company in enumerate(batch_companies):
        result = await scrape_and_save(company)

        if result["status"] == "success":
            successful += 1
        elif result["status"] == "skipped":
            skipped += 1
        elif result["status"] == "timeout":
            timeouts += 1
        else:
            failed += 1

        # Delay between companies (except last one)
        if i < len(batch_companies) - 1:
            await asyncio.sleep(DELAY_BETWEEN_COMPANIES)

    elapsed = (datetime.now() - start_time).total_seconds()

    # Batch summary
    print("\n" + "-" * 80)
    print(f"BATCH {batch_num} COMPLETE")
    print(f"✅ Success: {successful} | ⏱️  Timeout: {timeouts} | ❌ Failed: {failed} | ⏭️  Skipped: {skipped}")
    print(f"⏱️  Time: {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"📊 Avg: {elapsed/len(batch_companies):.1f}s per company")
    print("-" * 80 + "\n")

    # Estimate time remaining
    batches_remaining = total_batches - batch_num - 1
    est_time_remaining = (elapsed / 60) * batches_remaining

    if batches_remaining > 0:
        print(f"📈 Estimated time remaining: {est_time_remaining:.0f} minutes ({est_time_remaining/60:.1f} hours)")
        print(f"📊 Progress: {((batch_num + 1) / total_batches * 100):.1f}% complete")
        print()

    # Track batches completed
    batches_run += 1

    # Single batch mode - exit after one batch
    if single:
        print(f"\n✅ Single batch mode complete")
        print(f"\nTo continue, run: python3 batch_scrape_icp_signals_fast.py --batch {batch_num + 1}\n")
        return

    # Max batches limit reached
    if max_batches > 0 and batches_run >= max_batches:
        print(f"\n✅ Completed {batches_run} batches as requested")
        print(f"\nTo continue, run: python3 batch_scrape_icp_signals_fast.py --batch {batch_num + 1}\n")
        return

    # Next batch?
    if batch_num < total_batches - 1:
        if auto or max_batches > 0:
            print(f"🚀 Auto mode: Starting batch {batch_num + 1}...\n")
            await asyncio.sleep(2)
            await run_batch(batch_num + 1, auto=True, single=False, max_batches=max_batches, batches_run=batches_run)
        else:
            response = input(f"Continue to batch {batch_num + 1}? (Enter=yes, q=quit): ")
            if response.lower() != 'q':
                await run_batch(batch_num + 1, auto=False, single=False, max_batches=0, batches_run=0)
            else:
                print("\n✋ Stopped by user")
                print(f"\nTo resume, run: python3 batch_scrape_icp_signals_fast.py --batch {batch_num + 1}\n")
    else:
        print("\n" + "=" * 80)
        print("🎉 ALL BATCHES COMPLETE!")
        print(f"Total companies processed: {total_companies}")
        print("=" * 80 + "\n")


async def main():
    parser = argparse.ArgumentParser(description="FAST batch scrape ICP signals")
    parser.add_argument('--batch', type=int, default=0, help='Batch number to start from (default: 0)')
    parser.add_argument('--auto', action='store_true', help='Auto mode: run all batches non-stop')
    parser.add_argument('--single', action='store_true', help='Single batch mode: run one batch and exit')
    parser.add_argument('--count', type=int, default=0, help='Number of batches to run (0=unlimited)')
    args = parser.parse_args()

    print("\n" + "=" * 80)
    print("COPERNIQ ICP SIGNAL BATCH SCRAPER (70 signals)")
    print("=" * 80)
    print(f"Batch size: {BATCH_SIZE} companies")
    print(f"Timeout: {TIMEOUT_PER_COMPANY}s per company")
    print(f"Pages checked: {len(ESSENTIAL_PAGES)}")
    print(f"Signals: 70 (7 categories incl. MEP/Multi-Trade/Self-Performing)")
    mode = 'SINGLE BATCH' if args.single else ('AUTO (non-stop)' if args.auto else 'INTERACTIVE (batch-by-batch)')
    if args.count > 0:
        mode = f'AUTO ({args.count} batches)'
    print(f"Mode: {mode}")
    print("=" * 80)

    await run_batch(args.batch, auto=args.auto, single=args.single, max_batches=args.count)


if __name__ == "__main__":
    asyncio.run(main())
