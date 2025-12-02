#!/usr/bin/env python3
"""
Multi-Source Company Enrichment with Phone Verification
========================================================
Enriches companies from multiple free sources, accumulating and verifying
phone numbers across sources. Each phone found is tracked with its source
for SDR audit trail.

Sources (in order):
1. Company Website - homepage, contact page, footer
2. Google Business Profile - verified business info
3. BBB (Better Business Bureau) - accreditation, rating
4. Yelp - reviews, phone, rating
5. Facebook Business - page info
6. LinkedIn Company - leadership team, employee names

Phone Verification Logic:
- First phone found = "unverified"
- Same phone from 2nd source = "verified"
- Different phone = add to list with source
- SDR gets ALL phone numbers to try

Rate Limits:
- 1 second delay between requests per source
- 3 second delay between sources for same company
- Respectful scraping with proper User-Agent

Usage:
    python enrich_multi_source.py --test 10       # Test on 10 companies
    python enrich_multi_source.py --batch 1       # Process batch 1 (0-500)
    python enrich_multi_source.py --company "ABC Heating"  # Single company
"""

import asyncio
import pandas as pd
import logging
import re
import os
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from urllib.parse import quote_plus, urljoin
import argparse
from dataclasses import dataclass, field, asdict
from dotenv import load_dotenv
import httpx
from bs4 import BeautifulSoup

# Load environment
load_dotenv(Path(__file__).parent.parent / '.env')

# Configuration
OUTPUT_DIR = Path("data/final_enrichment_output")
LOG_DIR = OUTPUT_DIR / "logs"
BATCH_SIZE = 500
REQUEST_TIMEOUT = 15

# Ensure directories exist
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Setup logging - both console and file
def setup_logging(batch_name: str = "enrichment"):
    """Setup logging to both console and file."""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = LOG_DIR / f"enrichment_{batch_name}_{timestamp}.log"

    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers = []

    # Create formatters
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)

    # File handler
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)  # Capture everything in file
    file_handler.setFormatter(formatter)

    # Configure root logger
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    return log_file

logger = logging.getLogger(__name__)

# User agent for respectful scraping
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Phone regex patterns
PHONE_PATTERNS = [
    r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}',  # (123) 456-7890 or 123-456-7890
    r'\d{3}[-.\s]\d{3}[-.\s]\d{4}',            # 123-456-7890
    r'\+1[-.\s]?\d{3}[-.\s]?\d{3}[-.\s]?\d{4}', # +1 123-456-7890
]


@dataclass
class PhoneRecord:
    """Represents a phone number with its source and verification status."""
    number: str  # Normalized 10-digit number
    display: str  # Original format for display
    source: str  # Where we found it (website, google, bbb, yelp, etc.)
    source_url: str  # URL where found
    verified: bool = False  # True if found from 2+ sources
    verification_sources: List[str] = field(default_factory=list)


@dataclass
class CompanyEnrichment:
    """Accumulated enrichment data for a company."""
    company_name: str
    domain: str

    # Phone accumulation
    phones: List[PhoneRecord] = field(default_factory=list)
    primary_phone: str = ""  # Most verified phone
    phone_count: int = 0
    verified_phone_count: int = 0

    # Source verification flags
    website_verified: bool = False
    google_verified: bool = False
    bbb_verified: bool = False
    bbb_accredited: bool = False
    bbb_rating: str = ""
    yelp_verified: bool = False
    yelp_rating: float = 0.0
    yelp_review_count: int = 0
    facebook_verified: bool = False
    linkedin_verified: bool = False
    linkedin_company_url: str = ""
    linkedin_employee_count: str = ""

    # Additional data
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    hours: str = ""

    # ATL contacts found
    contacts: List[Dict] = field(default_factory=list)

    # Audit trail
    sources_checked: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    enrichment_timestamp: str = ""

    def add_phone(self, number: str, display: str, source: str, source_url: str) -> bool:
        """
        Add a phone number, verifying against existing numbers.

        Returns True if this was a new phone, False if it verified an existing one.
        """
        normalized = normalize_phone(number)
        if not normalized or len(normalized) != 10:
            return False

        # Check if we already have this phone
        for phone in self.phones:
            if phone.number == normalized:
                # Same phone - mark as verified!
                if not phone.verified:
                    phone.verified = True
                    phone.verification_sources.append(source)
                    self.verified_phone_count += 1
                    logger.info(f"  📞 VERIFIED: {display} (also found on {source})")
                elif source not in phone.verification_sources:
                    phone.verification_sources.append(source)
                return False

        # New phone number
        self.phones.append(PhoneRecord(
            number=normalized,
            display=display,
            source=source,
            source_url=source_url,
            verified=False,
            verification_sources=[source]
        ))
        self.phone_count += 1
        logger.info(f"  📞 NEW: {display} (from {source})")
        return True

    def get_all_phones_for_sdr(self) -> List[Dict]:
        """Get all phones formatted for SDR calling list."""
        result = []
        # Verified phones first
        for phone in sorted(self.phones, key=lambda p: (not p.verified, p.source)):
            result.append({
                'phone': phone.display,
                'normalized': phone.number,
                'verified': phone.verified,
                'source': phone.source,
                'verification_count': len(phone.verification_sources),
                'all_sources': ', '.join(phone.verification_sources)
            })
        return result

    def set_primary_phone(self):
        """Set the primary phone (most verified, or first found)."""
        if not self.phones:
            return

        # Prefer verified phones
        verified = [p for p in self.phones if p.verified]
        if verified:
            # Most verification sources wins
            best = max(verified, key=lambda p: len(p.verification_sources))
            self.primary_phone = best.display
        else:
            # First phone found
            self.primary_phone = self.phones[0].display


def normalize_phone(phone: str) -> str:
    """Normalize phone to 10-digit format."""
    if not phone:
        return ""
    digits = re.sub(r'\D', '', phone)
    # Handle +1 prefix
    if len(digits) == 11 and digits.startswith('1'):
        digits = digits[1:]
    return digits if len(digits) == 10 else ""


def extract_phones_from_html(html: str, source: str, source_url: str) -> List[Tuple[str, str]]:
    """
    Extract all phone numbers from HTML content.

    Returns list of (normalized, display) tuples.
    """
    phones = []
    seen = set()

    # Method 1: tel: links (highest confidence)
    soup = BeautifulSoup(html, 'html.parser')
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        if href.startswith('tel:'):
            phone_text = href.replace('tel:', '').replace('+1', '').strip()
            normalized = normalize_phone(phone_text)
            if normalized and normalized not in seen:
                seen.add(normalized)
                # Get display text from link or href
                display = link.get_text(strip=True) or phone_text
                phones.append((normalized, display))

    # Method 2: Regex patterns in text
    text = soup.get_text()
    for pattern in PHONE_PATTERNS:
        matches = re.findall(pattern, text)
        for match in matches:
            normalized = normalize_phone(match)
            if normalized and normalized not in seen:
                seen.add(normalized)
                phones.append((normalized, match))

    return phones


async def fetch_page(client: httpx.AsyncClient, url: str) -> Optional[str]:
    """Fetch a page with proper headers and error handling."""
    try:
        response = await client.get(
            url,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
            timeout=REQUEST_TIMEOUT
        )
        if response.status_code == 200:
            return response.text
        else:
            logger.debug(f"HTTP {response.status_code} for {url}")
            return None
    except httpx.TimeoutException:
        logger.debug(f"Timeout fetching {url}")
        return None
    except Exception as e:
        logger.debug(f"Error fetching {url}: {e}")
        return None


async def enrich_from_website(
    client: httpx.AsyncClient,
    enrichment: CompanyEnrichment
) -> None:
    """
    Scrape company website for phones and contacts.

    Checks: homepage, /contact, /about, /team
    """
    if not enrichment.domain:
        return

    enrichment.sources_checked.append("website")
    base_url = f"https://{enrichment.domain}"

    # Pages to check
    pages_to_check = [
        ("", "homepage"),
        ("/contact", "contact"),
        ("/contact-us", "contact"),
        ("/about", "about"),
        ("/about-us", "about"),
        ("/team", "team"),
        ("/our-team", "team"),
    ]

    for path, page_type in pages_to_check:
        url = base_url + path
        html = await fetch_page(client, url)

        if html:
            enrichment.website_verified = True
            phones = extract_phones_from_html(html, f"website_{page_type}", url)

            for normalized, display in phones:
                enrichment.add_phone(normalized, display, f"website:{page_type}", url)

            # Extract contacts from team pages
            if page_type == "team":
                await extract_team_contacts(html, url, enrichment)

        # Small delay between page requests
        await asyncio.sleep(0.5)


async def extract_team_contacts(html: str, url: str, enrichment: CompanyEnrichment) -> None:
    """Extract ATL contacts from team/about pages."""
    soup = BeautifulSoup(html, 'html.parser')

    # Common ATL titles
    atl_patterns = [
        r'(?:ceo|chief executive)',
        r'(?:president)',
        r'(?:owner|founder|co-founder)',
        r'(?:vp|vice president)',
        r'(?:director)',
        r'(?:general manager)',
        r'(?:partner|principal)',
    ]

    # Look for team member cards/sections
    # Common patterns: div with class containing "team", "member", "staff"
    team_sections = soup.find_all(['div', 'section', 'article'],
                                   class_=re.compile(r'team|member|staff|leader|executive', re.I))

    for section in team_sections:
        # Look for name (usually in h2, h3, h4 or strong)
        name_elem = section.find(['h2', 'h3', 'h4', 'strong', 'span'],
                                  class_=re.compile(r'name|title', re.I))
        if not name_elem:
            name_elem = section.find(['h2', 'h3', 'h4'])

        # Look for title/position
        title_elem = section.find(['p', 'span', 'div'],
                                   class_=re.compile(r'title|position|role', re.I))

        if name_elem and title_elem:
            name = name_elem.get_text(strip=True)
            title = title_elem.get_text(strip=True)

            # Check if ATL
            title_lower = title.lower()
            is_atl = any(re.search(p, title_lower) for p in atl_patterns)

            if is_atl and name:
                # Look for email in same section
                email = None
                email_link = section.find('a', href=re.compile(r'mailto:', re.I))
                if email_link:
                    email = email_link.get('href', '').replace('mailto:', '').split('?')[0]

                # Look for phone in same section
                phone = None
                phone_link = section.find('a', href=re.compile(r'tel:', re.I))
                if phone_link:
                    phone = phone_link.get('href', '').replace('tel:', '')

                enrichment.contacts.append({
                    'name': name,
                    'title': title,
                    'email': email,
                    'phone': phone,
                    'source': 'website_team',
                    'source_url': url
                })
                logger.info(f"  👤 ATL Contact: {name} - {title}")


async def enrich_from_google(
    client: httpx.AsyncClient,
    enrichment: CompanyEnrichment
) -> None:
    """
    Search Google for business info.

    Note: This is a simple search scrape - for production, use Google Places API.
    """
    enrichment.sources_checked.append("google_search")

    # Build search query
    query = f"{enrichment.company_name} {enrichment.domain} phone"
    search_url = f"https://www.google.com/search?q={quote_plus(query)}"

    html = await fetch_page(client, search_url)
    if not html:
        return

    # Extract phones from search results
    phones = extract_phones_from_html(html, "google_search", search_url)
    for normalized, display in phones[:3]:  # Limit to first 3 from search
        enrichment.add_phone(normalized, display, "google:search", search_url)

    # Check for Knowledge Panel indicators
    if 'data-attrid="kc:/local' in html or 'class="LrzXr"' in html:
        enrichment.google_verified = True


async def enrich_from_bbb(
    client: httpx.AsyncClient,
    enrichment: CompanyEnrichment
) -> None:
    """
    Check BBB (Better Business Bureau) for business verification.
    """
    enrichment.sources_checked.append("bbb")

    # BBB search URL
    query = f"{enrichment.company_name}"
    if enrichment.state:
        query += f" {enrichment.state}"

    search_url = f"https://www.bbb.org/search?find_text={quote_plus(query)}"

    html = await fetch_page(client, search_url)
    if not html:
        return

    soup = BeautifulSoup(html, 'html.parser')

    # Look for business listing
    listing = soup.find('a', class_=re.compile(r'business-card', re.I))
    if listing:
        enrichment.bbb_verified = True

        # Check for accreditation
        accredited = soup.find(text=re.compile(r'BBB Accredited', re.I))
        if accredited:
            enrichment.bbb_accredited = True

        # Extract rating
        rating_elem = soup.find(class_=re.compile(r'rating', re.I))
        if rating_elem:
            rating_text = rating_elem.get_text(strip=True)
            if rating_text and rating_text[0] in 'ABCDF':
                enrichment.bbb_rating = rating_text[0]

        # Extract phone from listing
        phones = extract_phones_from_html(str(listing), "bbb", search_url)
        for normalized, display in phones[:1]:
            enrichment.add_phone(normalized, display, "bbb:listing", search_url)


async def enrich_from_yelp(
    client: httpx.AsyncClient,
    enrichment: CompanyEnrichment
) -> None:
    """
    Check Yelp for business info and reviews.
    """
    enrichment.sources_checked.append("yelp")

    # Yelp search URL
    query = f"{enrichment.company_name}"
    location = enrichment.city or enrichment.state or ""

    search_url = f"https://www.yelp.com/search?find_desc={quote_plus(query)}&find_loc={quote_plus(location)}"

    html = await fetch_page(client, search_url)
    if not html:
        return

    soup = BeautifulSoup(html, 'html.parser')

    # Look for business listing
    listing = soup.find('div', {'data-testid': 'serp-ia-card'})
    if not listing:
        listing = soup.find('div', class_=re.compile(r'businessName', re.I))

    if listing:
        enrichment.yelp_verified = True

        # Extract rating
        rating_elem = soup.find('div', {'aria-label': re.compile(r'\d+\.?\d* star rating', re.I)})
        if rating_elem:
            try:
                rating_text = rating_elem.get('aria-label', '')
                rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                if rating_match:
                    enrichment.yelp_rating = float(rating_match.group(1))
            except:
                pass

        # Extract review count
        review_elem = soup.find(text=re.compile(r'\d+\s*reviews?', re.I))
        if review_elem:
            try:
                count_match = re.search(r'(\d+)', str(review_elem))
                if count_match:
                    enrichment.yelp_review_count = int(count_match.group(1))
            except:
                pass

        # Extract phone
        phones = extract_phones_from_html(html, "yelp", search_url)
        for normalized, display in phones[:1]:
            enrichment.add_phone(normalized, display, "yelp:listing", search_url)


async def enrich_from_facebook(
    client: httpx.AsyncClient,
    enrichment: CompanyEnrichment
) -> None:
    """
    Search for Facebook business page.
    """
    enrichment.sources_checked.append("facebook")

    # Search via Google (Facebook search is harder to scrape)
    query = f"site:facebook.com {enrichment.company_name}"
    search_url = f"https://www.google.com/search?q={quote_plus(query)}"

    html = await fetch_page(client, search_url)
    if not html:
        return

    # Look for Facebook page link
    if 'facebook.com' in html.lower():
        enrichment.facebook_verified = True

        # Extract any phones from search snippet
        phones = extract_phones_from_html(html, "facebook_search", search_url)
        for normalized, display in phones[:1]:
            enrichment.add_phone(normalized, display, "facebook:search", search_url)


async def enrich_from_linkedin(
    client: httpx.AsyncClient,
    enrichment: CompanyEnrichment
) -> None:
    """
    Search for LinkedIn company page and extract leadership info.

    Strategy:
    1. Google search for LinkedIn company page
    2. Try to extract company URL from search results
    3. Search for company + "CEO" / "owner" / "founder" to find key people
    4. Extract names from search results (avoiding direct LinkedIn scraping)

    Note: Direct LinkedIn scraping is rate-limited/blocked. We use Google
    to find publicly visible LinkedIn data in search snippets.
    """
    enrichment.sources_checked.append("linkedin")

    # =====================================================================
    # STEP 1: Find LinkedIn Company Page
    # =====================================================================
    company_query = f"site:linkedin.com/company {enrichment.company_name}"
    search_url = f"https://www.google.com/search?q={quote_plus(company_query)}"

    html = await fetch_page(client, search_url)
    if not html:
        return

    soup = BeautifulSoup(html, 'html.parser')

    # Look for LinkedIn company URL in search results
    linkedin_url = None
    for link in soup.find_all('a', href=True):
        href = link.get('href', '')
        # Google wraps URLs, look for linkedin.com/company in the text or data
        if 'linkedin.com/company' in href.lower():
            linkedin_url = href
            break

    # Also check cite elements (Google shows URL there)
    if not linkedin_url:
        for cite in soup.find_all('cite'):
            cite_text = cite.get_text()
            if 'linkedin.com/company' in cite_text.lower():
                # Extract just the LinkedIn URL
                match = re.search(r'linkedin\.com/company/[a-zA-Z0-9-]+', cite_text)
                if match:
                    linkedin_url = f"https://www.{match.group()}"
                    break

    if linkedin_url or 'linkedin.com' in html.lower():
        enrichment.linkedin_verified = True
        if linkedin_url:
            enrichment.linkedin_company_url = linkedin_url
            logger.info(f"  🔗 LinkedIn company page found")

    # Extract employee count from search snippet if visible
    # Common patterns: "1,001-5,000 employees" or "51-200 employees"
    employee_match = re.search(r'(\d[\d,]*[-–]\d[\d,]*)\s*employees?', html, re.I)
    if employee_match:
        enrichment.linkedin_employee_count = employee_match.group(1)
        logger.info(f"  👥 LinkedIn employee count: {enrichment.linkedin_employee_count}")

    await asyncio.sleep(5)  # Longer delay to avoid Google rate limits

    # =====================================================================
    # STEP 2: Search for Key People (ATL contacts)
    # =====================================================================
    # Search patterns for finding executives
    atl_search_patterns = [
        ("CEO", ["ceo", "chief executive"]),
        ("Owner", ["owner", "founder"]),
        ("President", ["president"]),
        ("VP", ["vp", "vice president"]),
    ]

    for title_label, title_keywords in atl_search_patterns:
        # Search Google for: site:linkedin.com "company name" CEO
        people_query = f'site:linkedin.com/in "{enrichment.company_name}" {title_label}'
        people_url = f"https://www.google.com/search?q={quote_plus(people_query)}"

        html = await fetch_page(client, people_url)
        if not html:
            continue

        soup = BeautifulSoup(html, 'html.parser')

        # Look for LinkedIn profile snippets
        # Google shows name in <h3> and title in snippet
        for result in soup.find_all('div', class_=['g', 'tF2Cxc', 'yuRUbf']):
            # Try to find name from title/h3
            name_elem = result.find(['h3'])
            if not name_elem:
                continue

            name_text = name_elem.get_text(strip=True)

            # LinkedIn titles typically: "John Smith - CEO - Company | LinkedIn"
            # or "John Smith | LinkedIn"
            if 'linkedin' in name_text.lower():
                # Extract name (before " - " or " | ")
                name_parts = re.split(r'\s*[-|–]\s*', name_text)
                if name_parts:
                    person_name = name_parts[0].strip()

                    # Validate it looks like a name (2+ words, not too long)
                    if ' ' in person_name and len(person_name) < 50:
                        # Check snippet for title confirmation
                        snippet = result.find('span', class_=['st', 'aCOpRe'])
                        snippet_text = snippet.get_text() if snippet else ""

                        # Confirm this is an ATL role
                        is_atl = any(kw in name_text.lower() or kw in snippet_text.lower()
                                    for kw in title_keywords)

                        if is_atl:
                            # Extract title from the result
                            extracted_title = ""
                            for kw in title_keywords:
                                if kw in name_text.lower():
                                    extracted_title = title_label
                                    break
                                elif kw in snippet_text.lower():
                                    extracted_title = title_label
                                    break

                            # Check if we already have this contact
                            existing_names = [c['name'].lower() for c in enrichment.contacts]
                            if person_name.lower() not in existing_names:
                                enrichment.contacts.append({
                                    'name': person_name,
                                    'title': extracted_title or title_label,
                                    'email': None,
                                    'phone': None,
                                    'source': 'linkedin:google_search',
                                    'source_url': people_url
                                })
                                logger.info(f"  👤 LinkedIn ATL: {person_name} - {extracted_title or title_label}")

        # Rate limit between searches - longer delay for Google
        await asyncio.sleep(3)

        # Stop after finding 2 contacts to avoid too many requests
        if len(enrichment.contacts) >= 2:
            break


async def enrich_company(
    client: httpx.AsyncClient,
    company_name: str,
    domain: str,
    city: str = "",
    state: str = ""
) -> CompanyEnrichment:
    """
    Run full multi-source enrichment on a company.
    """
    enrichment = CompanyEnrichment(
        company_name=company_name,
        domain=domain,
        city=city,
        state=state,
        enrichment_timestamp=datetime.now().isoformat()
    )

    logger.info(f"\n{'='*60}")
    logger.info(f"Enriching: {company_name}")
    logger.info(f"Domain: {domain}")
    logger.info(f"{'='*60}")

    # Run enrichment from each source (with delays between sources)
    # NOTE: Longer delays (5s) for Google-based searches to avoid rate limits
    try:
        # 1. Website (primary source) - no Google, fast
        await enrich_from_website(client, enrichment)
        await asyncio.sleep(1)

        # 2. Google search - USES GOOGLE, need longer delay
        await enrich_from_google(client, enrichment)
        await asyncio.sleep(5)  # Longer delay to avoid Google rate limits

        # 3. BBB - direct site, no Google
        await enrich_from_bbb(client, enrichment)
        await asyncio.sleep(2)

        # 4. Yelp - direct site, no Google
        await enrich_from_yelp(client, enrichment)
        await asyncio.sleep(2)

        # 5. Facebook - USES GOOGLE search
        await enrich_from_facebook(client, enrichment)
        await asyncio.sleep(5)  # Longer delay to avoid Google rate limits

        # 6. LinkedIn - USES GOOGLE search (multiple queries)
        await enrich_from_linkedin(client, enrichment)

    except Exception as e:
        enrichment.errors.append(str(e))
        logger.error(f"Error enriching {company_name}: {e}")

    # Set primary phone
    enrichment.set_primary_phone()

    # Summary
    logger.info(f"\n📊 Summary for {company_name}:")
    logger.info(f"   Total phones: {enrichment.phone_count}")
    logger.info(f"   Verified phones: {enrichment.verified_phone_count}")
    logger.info(f"   ATL contacts: {len(enrichment.contacts)}")
    logger.info(f"   Sources verified: website={enrichment.website_verified}, google={enrichment.google_verified}, bbb={enrichment.bbb_verified}, yelp={enrichment.yelp_verified}, linkedin={enrichment.linkedin_verified}")

    return enrichment


def enrichment_to_row(enrichment: CompanyEnrichment) -> Dict:
    """Convert enrichment to flat dict for CSV/DataFrame."""
    # Get all phones for SDR
    all_phones = enrichment.get_all_phones_for_sdr()

    # Format phones as columns
    phone_cols = {}
    for i, phone in enumerate(all_phones[:5], 1):  # Max 5 phones
        phone_cols[f'phone_{i}'] = phone['phone']
        phone_cols[f'phone_{i}_verified'] = phone['verified']
        phone_cols[f'phone_{i}_sources'] = phone['all_sources']

    # Format contacts
    contact_cols = {}
    for i, contact in enumerate(enrichment.contacts[:3], 1):  # Max 3 contacts
        contact_cols[f'contact_{i}_name'] = contact.get('name', '')
        contact_cols[f'contact_{i}_title'] = contact.get('title', '')
        contact_cols[f'contact_{i}_email'] = contact.get('email', '')
        contact_cols[f'contact_{i}_phone'] = contact.get('phone', '')

    return {
        'company_name': enrichment.company_name,
        'domain': enrichment.domain,
        'primary_phone': enrichment.primary_phone,
        'phone_count': enrichment.phone_count,
        'verified_phone_count': enrichment.verified_phone_count,
        **phone_cols,
        **contact_cols,
        'website_verified': enrichment.website_verified,
        'google_verified': enrichment.google_verified,
        'bbb_verified': enrichment.bbb_verified,
        'bbb_accredited': enrichment.bbb_accredited,
        'bbb_rating': enrichment.bbb_rating,
        'yelp_verified': enrichment.yelp_verified,
        'yelp_rating': enrichment.yelp_rating,
        'yelp_review_count': enrichment.yelp_review_count,
        'facebook_verified': enrichment.facebook_verified,
        'linkedin_verified': enrichment.linkedin_verified,
        'linkedin_company_url': enrichment.linkedin_company_url,
        'linkedin_employee_count': enrichment.linkedin_employee_count,
        'city': enrichment.city,
        'state': enrichment.state,
        'sources_checked': ','.join(enrichment.sources_checked),
        'errors': '; '.join(enrichment.errors) if enrichment.errors else '',
        'enrichment_timestamp': enrichment.enrichment_timestamp,
        # JSON columns for detailed data
        'all_phones_json': json.dumps(enrichment.get_all_phones_for_sdr()),
        'contacts_json': json.dumps(enrichment.contacts),
    }


def deduplicate_companies(companies: List[Dict]) -> List[Dict]:
    """
    Deduplicate companies by normalized domain.
    Returns unique companies, preferring those with more data.
    """
    seen_domains = {}
    for company in companies:
        domain = (company.get('domain', '') or '').lower().strip()
        if not domain:
            continue

        # Clean domain - remove www, http, etc
        domain = domain.replace('https://', '').replace('http://', '').replace('www.', '').rstrip('/')

        if domain not in seen_domains:
            seen_domains[domain] = company
        else:
            # Keep the one with more data (name, city, state)
            existing = seen_domains[domain]
            existing_score = sum([
                bool(existing.get('name') or existing.get('company_name')),
                bool(existing.get('city')),
                bool(existing.get('state')),
            ])
            new_score = sum([
                bool(company.get('name') or company.get('company_name')),
                bool(company.get('city')),
                bool(company.get('state')),
            ])
            if new_score > existing_score:
                seen_domains[domain] = company

    return list(seen_domains.values())


async def sync_enrichment_to_supabase(results_df: pd.DataFrame) -> int:
    """
    Sync enrichment results back to Supabase dim_companies table.
    Updates existing records with new enrichment data.

    Returns count of updated records.
    """
    from supabase import create_client

    supabase = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_SERVICE_KEY')
    )

    updated_count = 0

    for _, row in results_df.iterrows():
        domain = row.get('domain', '')
        if not domain:
            continue

        # Build update payload
        update_data = {
            'enrichment_timestamp': row.get('enrichment_timestamp'),
            'enrichment_phone_count': int(row.get('phone_count', 0)),
            'enrichment_verified_phones': int(row.get('verified_phone_count', 0)),
            'enrichment_primary_phone': row.get('primary_phone', ''),
            'enrichment_website_verified': bool(row.get('website_verified', False)),
            'enrichment_linkedin_verified': bool(row.get('linkedin_verified', False)),
            'enrichment_bbb_verified': bool(row.get('bbb_verified', False)),
            'enrichment_bbb_rating': row.get('bbb_rating', ''),
            'enrichment_atl_count': sum([
                1 for i in range(1, 4)
                if row.get(f'contact_{i}_name') and str(row.get(f'contact_{i}_name')).strip()
            ]),
        }

        # Add first ATL contact if found
        if row.get('contact_1_name') and str(row.get('contact_1_name')).strip():
            update_data['enrichment_atl_name'] = row.get('contact_1_name', '')
            update_data['enrichment_atl_title'] = row.get('contact_1_title', '')

        # Update by domain
        try:
            result = supabase.table('dim_companies').update(update_data).eq('domain', domain).execute()
            if result.data:
                updated_count += 1
        except Exception as e:
            logger.debug(f"Supabase update error for {domain}: {e}")

    logger.info(f"📤 Synced {updated_count} records to Supabase")
    return updated_count


async def process_batch(
    companies: List[Dict],
    batch_name: str = "test",
    sync_to_supabase: bool = True
) -> pd.DataFrame:
    """
    Process a batch of companies through multi-source enrichment.

    Features:
    - Deduplication before processing
    - Progress saves every 50 companies
    - JSON backup of all data
    - CSV output for easy viewing
    - Log file capture
    - Optional Supabase sync
    """
    # Setup logging to file
    log_file = setup_logging(batch_name)
    logger.info(f"📝 Log file: {log_file}")

    # Deduplicate input
    original_count = len(companies)
    companies = deduplicate_companies(companies)
    deduped_count = len(companies)

    logger.info(f"\n{'#'*60}")
    logger.info(f"MULTI-SOURCE ENRICHMENT - {batch_name}")
    logger.info(f"{'#'*60}")
    logger.info(f"Input companies: {original_count}")
    logger.info(f"After deduplication: {deduped_count}")
    logger.info(f"Duplicates removed: {original_count - deduped_count}")

    results = []
    raw_enrichments = []  # Store full enrichment objects for JSON backup

    async with httpx.AsyncClient() as client:
        for idx, company in enumerate(companies, 1):
            logger.info(f"\n[{idx}/{deduped_count}] Processing...")

            enrichment = await enrich_company(
                client,
                company_name=company.get('name', company.get('company_name', '')),
                domain=company.get('domain', ''),
                city=company.get('city', ''),
                state=company.get('state', '')
            )

            row_data = enrichment_to_row(enrichment)
            results.append(row_data)

            # Store raw enrichment for JSON backup
            raw_enrichments.append({
                'company_name': enrichment.company_name,
                'domain': enrichment.domain,
                'phones': [asdict(p) for p in enrichment.phones],
                'contacts': enrichment.contacts,
                'website_verified': enrichment.website_verified,
                'google_verified': enrichment.google_verified,
                'bbb_verified': enrichment.bbb_verified,
                'bbb_accredited': enrichment.bbb_accredited,
                'bbb_rating': enrichment.bbb_rating,
                'yelp_verified': enrichment.yelp_verified,
                'yelp_rating': enrichment.yelp_rating,
                'yelp_review_count': enrichment.yelp_review_count,
                'facebook_verified': enrichment.facebook_verified,
                'linkedin_verified': enrichment.linkedin_verified,
                'linkedin_company_url': enrichment.linkedin_company_url,
                'linkedin_employee_count': enrichment.linkedin_employee_count,
                'sources_checked': enrichment.sources_checked,
                'errors': enrichment.errors,
                'enrichment_timestamp': enrichment.enrichment_timestamp,
            })

            # Progress save every 50 companies (both CSV and JSON)
            if idx % 50 == 0:
                temp_df = pd.DataFrame(results)
                temp_csv = OUTPUT_DIR / f"enrichment_progress_{batch_name}.csv"
                temp_df.to_csv(temp_csv, index=False)

                temp_json = OUTPUT_DIR / f"enrichment_progress_{batch_name}.json"
                with open(temp_json, 'w') as f:
                    json.dump(raw_enrichments, f, indent=2)

                logger.info(f"💾 Progress saved: {temp_csv} + {temp_json}")

            # Delay between companies
            await asyncio.sleep(2)

    # Create final DataFrame
    results_df = pd.DataFrame(results)

    # Final deduplication on output (by domain)
    if 'domain' in results_df.columns:
        before_dedup = len(results_df)
        results_df = results_df.drop_duplicates(subset=['domain'], keep='first')
        after_dedup = len(results_df)
        if before_dedup != after_dedup:
            logger.info(f"🧹 Final dedup removed {before_dedup - after_dedup} duplicates")

    # Save results - multiple formats
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 1. CSV output (easy to view/filter)
    csv_file = OUTPUT_DIR / f"multi_source_enriched_{batch_name}_{timestamp}.csv"
    results_df.to_csv(csv_file, index=False)
    logger.info(f"📊 CSV saved: {csv_file}")

    # 2. JSON backup (complete data, no loss)
    json_file = OUTPUT_DIR / f"multi_source_enriched_{batch_name}_{timestamp}.json"
    with open(json_file, 'w') as f:
        json.dump({
            'metadata': {
                'batch_name': batch_name,
                'timestamp': timestamp,
                'input_count': original_count,
                'deduped_count': deduped_count,
                'output_count': len(results_df),
                'log_file': str(log_file),
            },
            'enrichments': raw_enrichments
        }, f, indent=2)
    logger.info(f"📦 JSON backup: {json_file}")

    # 3. Cleanup progress files
    progress_csv = OUTPUT_DIR / f"enrichment_progress_{batch_name}.csv"
    progress_json = OUTPUT_DIR / f"enrichment_progress_{batch_name}.json"
    for f in [progress_csv, progress_json]:
        if f.exists():
            f.unlink()
            logger.info(f"🗑️ Cleaned up: {f.name}")

    # Summary stats
    logger.info(f"\n{'='*60}")
    logger.info(f"ENRICHMENT COMPLETE - {batch_name}")
    logger.info(f"{'='*60}")
    logger.info(f"Total companies: {len(results_df)}")
    logger.info(f"With phones: {(results_df['phone_count'] > 0).sum()}")
    logger.info(f"With verified phones: {(results_df['verified_phone_count'] > 0).sum()}")
    logger.info(f"Website verified: {results_df['website_verified'].sum()}")
    logger.info(f"Google verified: {results_df['google_verified'].sum()}")
    logger.info(f"BBB verified: {results_df['bbb_verified'].sum()}")
    logger.info(f"Yelp verified: {results_df['yelp_verified'].sum()}")
    logger.info(f"LinkedIn verified: {results_df['linkedin_verified'].sum()}")
    atl_count = (results_df['contact_1_name'].notna() & (results_df['contact_1_name'] != '')).sum() if 'contact_1_name' in results_df.columns else 0
    logger.info(f"ATL contacts found: {atl_count}")
    logger.info(f"\n📁 Output files:")
    logger.info(f"   CSV: {csv_file}")
    logger.info(f"   JSON: {json_file}")
    logger.info(f"   Log: {log_file}")

    # Sync to Supabase if enabled
    if sync_to_supabase:
        logger.info(f"\n🔄 Syncing to Supabase...")
        try:
            updated = await sync_enrichment_to_supabase(results_df)
            logger.info(f"✅ Supabase sync complete: {updated} records updated")
        except Exception as e:
            logger.error(f"❌ Supabase sync failed: {e}")

    return results_df


async def load_companies_from_supabase(limit: int = None, offset: int = 0) -> List[Dict]:
    """Load companies from Supabase."""
    from supabase import create_client

    supabase = create_client(
        os.getenv('SUPABASE_URL'),
        os.getenv('SUPABASE_SERVICE_KEY')
    )

    query = supabase.table('dim_companies').select(
        'company_name, normalized_name, domain, city, state'
    )

    if limit:
        query = query.range(offset, offset + limit - 1)

    result = query.execute()

    # Convert to list of dicts with expected keys
    companies = []
    for row in result.data:
        companies.append({
            'name': row.get('company_name', ''),
            'domain': row.get('domain', ''),
            'city': row.get('city', ''),
            'state': row.get('state', '')
        })

    logger.info(f"Loaded {len(companies)} companies from Supabase")
    return companies


async def main():
    parser = argparse.ArgumentParser(
        description='Multi-source company enrichment with phone verification',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python enrich_multi_source.py --test 10                    # Test on 10 companies
    python enrich_multi_source.py --batch 1                    # Process batch 1 (0-500)
    python enrich_multi_source.py --from-csv leads.csv         # Enrich from CSV
    python enrich_multi_source.py --from-csv leads.csv --no-sync  # Skip Supabase sync
    python enrich_multi_source.py --company "ABC Heating"      # Single company

Output files (all saved to data/final_enrichment_output/):
    - CSV: multi_source_enriched_<batch>_<timestamp>.csv
    - JSON: multi_source_enriched_<batch>_<timestamp>.json (full backup)
    - Log: logs/enrichment_<batch>_<timestamp>.log
        """
    )
    parser.add_argument('--test', type=int, help='Test on N companies from Supabase')
    parser.add_argument('--batch', type=int, help='Process batch N (500 companies each)')
    parser.add_argument('--company', type=str, help='Enrich single company by name')
    parser.add_argument('--from-csv', type=str, help='Load companies from CSV file')
    parser.add_argument('--no-sync', action='store_true', help='Skip Supabase sync after enrichment')
    parser.add_argument('--limit', type=int, help='Limit number of companies to process from CSV')
    parser.add_argument('--resume', type=str, help='Resume from existing progress CSV (skip already enriched domains)')

    args = parser.parse_args()
    sync_enabled = not args.no_sync

    if args.company:
        # Single company test (no sync for single company)
        setup_logging("single_company")
        async with httpx.AsyncClient() as client:
            # Simple domain guess
            domain_guess = args.company.lower().replace(' ', '').replace(',', '') + ".com"
            enrichment = await enrich_company(client, args.company, domain_guess)
            print(f"\nResult: {json.dumps(enrichment_to_row(enrichment), indent=2)}")

    elif args.test:
        # Test mode - load first N from Supabase
        companies = await load_companies_from_supabase(limit=args.test)
        await process_batch(companies, batch_name=f"test_{args.test}", sync_to_supabase=sync_enabled)

    elif args.batch:
        # Batch mode
        offset = (args.batch - 1) * BATCH_SIZE
        companies = await load_companies_from_supabase(limit=BATCH_SIZE, offset=offset)
        await process_batch(companies, batch_name=f"batch_{args.batch}", sync_to_supabase=sync_enabled)

    elif args.from_csv:
        # Load from CSV - handle different column names
        df = pd.read_csv(args.from_csv)

        # Apply limit if specified
        if args.limit:
            df = df.head(args.limit)

        # Resume: skip already enriched domains
        already_enriched = set()
        if args.resume and Path(args.resume).exists():
            resume_df = pd.read_csv(args.resume)
            already_enriched = set(resume_df['domain'].dropna().str.lower().str.strip())
            logger.info(f"📂 Resuming: found {len(already_enriched)} already enriched domains")

        # Normalize column names and filter out already enriched
        companies = []
        skipped = 0
        for _, row in df.iterrows():
            domain = str(row.get('domain', '')).lower().strip()
            if domain in already_enriched:
                skipped += 1
                continue
            companies.append({
                'name': row.get('company_name', row.get('name', '')),
                'domain': row.get('domain', ''),
                'city': row.get('city', ''),
                'state': row.get('state', '')
            })

        if skipped > 0:
            logger.info(f"⏭️ Skipped {skipped} already enriched leads")

        # Use filename as batch name
        batch_name = Path(args.from_csv).stem
        if args.limit:
            batch_name = f"{batch_name}_first{args.limit}"
        if args.resume:
            batch_name = f"{batch_name}_resumed"
        await process_batch(companies, batch_name=batch_name, sync_to_supabase=sync_enabled)

    else:
        parser.print_help()
        print("\n⚠️  Please specify --test N, --batch N, --company 'Name', or --from-csv file.csv")


if __name__ == "__main__":
    asyncio.run(main())
