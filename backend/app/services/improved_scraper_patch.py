"""
Improved Website Scraper - Fixes False Positives & Adds Missing Signals
========================================================================

FIXES:
1. Hiring: Only flag if /careers or /jobs page EXISTS (not 404)
2. Maintenance Plans: Detect "preventive maintenance", "service plans", "maintenance agreements"
3. Service Areas: Extract from /service-areas page
4. Generators: Detect generator sales/installation
5. Commercial: Detect commercial HVAC capability

Apply this patch to website_content_scraper.py
"""

# Add to IMPORTANT_PAGES list (after line 48):
IMPORTANT_PAGES_ENHANCED = [
    "/",           # Homepage
    "/about",      # About
    "/services",   # Services
    "/products",   # Products
    "/solutions",  # Solutions
    "/pricing",    # Pricing
    "/careers",    # Careers - VERIFY THIS EXISTS
    "/jobs",       # Jobs - alternate careers page
    "/contact",    # Contact
    "/team",       # Team
    "/customers",  # Customers
    "/case-studies",
    "/service-areas",  # NEW: Service areas
    "/commercial",     # NEW: Commercial services
    "/generators",     # NEW: Generator offerings
]

# Add new signal patterns (after line 67):
MAINTENANCE_PLAN_SIGNALS = [
    r"preventive\s+maintenance",
    r"preventative\s+maintenance",
    r"maintenance\s+(plan|agreement|contract|program)",
    r"service\s+(plan|agreement|contract)",
    r"annual\s+maintenance",
    r"planned\s+maintenance",
    r"(pm|ppm)\s+program",  # Preventive Maintenance Program
]

GENERATOR_SIGNALS = [
    r"generator\s+(sales|installation|service|repair)",
    r"standby\s+generator",
    r"backup\s+generator",
    r"home\s+generator",
    r"commercial\s+generator",
    r"whole[\s-]house\s+generator",
    r"generac|kohler|cummins",  # Major brands
]

COMMERCIAL_SIGNALS = [
    r"commercial\s+(hvac|plumbing|electrical)",
    r"commercial\s+services",
    r"business\s+services",
    r"industrial\s+(hvac|plumbing|electrical)",
    r"multi[\s-]family",
    r"property\s+management",
]


# IMPROVED _detect_hiring method (replace lines 317-323):
def _detect_hiring_improved(self, pages_scraped: list) -> bool:
    """
    Detect if company is hiring.

    FIXED: Only flag TRUE if /careers or /jobs page successfully loaded (not 404).
    This prevents false positives from homepage "we're hiring" text.
    """
    # Check if careers or jobs page was successfully scraped
    for page in pages_scraped:
        if page["path"] in ["/careers", "/jobs"]:
            return True  # Page exists and loaded successfully

    return False  # No careers/jobs page found


# NEW METHOD: Detect maintenance plans
def _detect_maintenance_plans(self, text: str) -> bool:
    """Detect if company offers maintenance plans/agreements."""
    text_lower = text.lower()
    for pattern in MAINTENANCE_PLAN_SIGNALS:
        if re.search(pattern, text_lower):
            return True
    return False


# NEW METHOD: Detect generators
def _detect_generators(self, text: str) -> bool:
    """Detect if company sells/installs generators."""
    text_lower = text.lower()
    for pattern in GENERATOR_SIGNALS:
        if re.search(pattern, text_lower):
            return True
    return False


# NEW METHOD: Detect commercial capability
def _detect_commercial(self, text: str) -> bool:
    """Detect if company serves commercial clients."""
    text_lower = text.lower()
    for pattern in COMMERCIAL_SIGNALS:
        if re.search(pattern, text_lower):
            return True
    return False


# NEW METHOD: Extract service areas
def _extract_service_areas(self, soup) -> list:
    """
    Extract service areas/locations from page.

    Looks for:
    - City names in lists
    - "Serving: City1, City2, City3"
    - State/city combinations
    """
    service_areas = []

    if not soup:
        return service_areas

    # Look for common patterns
    text = soup.get_text()

    # Pattern: "Serving: City1, City2, City3"
    serving_pattern = r"serving:?\s+([A-Z][a-z]+(?:,\s*[A-Z][a-z]+)*)"
    matches = re.findall(serving_pattern, text, re.IGNORECASE)
    for match in matches:
        cities = [c.strip() for c in match.split(',')]
        service_areas.extend(cities)

    # Look for list items that look like city names
    for li in soup.find_all('li'):
        li_text = li.get_text(strip=True)
        # Simple heuristic: 2-3 words, title case, no special chars
        if re.match(r'^[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2}$', li_text):
            if len(li_text) < 50:  # Not a long sentence
                service_areas.append(li_text)

    return list(set(service_areas))[:20]  # Dedupe, max 20


# UPDATED scrape_website method (replace result dict initialization):
result = {
    "url": base_url,
    "homepage_title": "",
    "homepage_description": "",
    "homepage_keywords": "",
    "homepage_text": "",
    "pages_scraped": [],
    "all_text": "",
    "services": [],
    "products": [],
    "value_proposition": "",
    "signals": {
        "is_hiring": False,           # FIXED: Now verifies page exists
        "has_funding": False,
        "has_maintenance_plan": False,  # NEW
        "has_generators": False,        # NEW
        "has_commercial": False,        # NEW
        "growth_indicators": [],
    },
    "service_areas": [],  # NEW
    "tech_stack": [],
    "social_links": {},
    "contact_info": {},
    "scraped_at": datetime.now().isoformat(),
    "error": None,
}


# UPDATED detection logic in scrape loop (replace lines 208-216):
# Detect signals
text = page_data.get("text", "")

# Don't detect hiring from text - will check page existence later
if self._detect_funding(text):
    result["signals"]["has_funding"] = True

# NEW: Detect maintenance plans
if self._detect_maintenance_plans(text):
    result["signals"]["has_maintenance_plan"] = True

# NEW: Detect generators
if self._detect_generators(text):
    result["signals"]["has_generators"] = True

# NEW: Detect commercial capability
if self._detect_commercial(text):
    result["signals"]["has_commercial"] = True

growth = self._detect_growth(text)
result["signals"]["growth_indicators"].extend(growth)

# NEW: Extract service areas from /service-areas page
if page_path == "/service-areas":
    areas = self._extract_service_areas(page_data.get("soup"))
    result["service_areas"].extend(areas)


# UPDATED hiring detection (add AFTER all pages scraped, around line 235):
# FIXED: Only flag hiring if careers/jobs page exists
result["signals"]["is_hiring"] = self._detect_hiring_improved(result["pages_scraped"])


"""
SUMMARY OF CHANGES:
===================

1. is_hiring: Now only TRUE if /careers or /jobs page loaded successfully
   - Prevents false positives from homepage "we're hiring!" text
   - ACTION AIR CON would now be FALSE (careers 404)

2. has_maintenance_plan: NEW signal detection
   - Detects "preventive maintenance", "service plans", etc.
   - ACTION AIR CON would be TRUE (they offer preventive maintenance)

3. service_areas: NEW field extraction
   - Scrapes /service-areas page
   - Extracts city names from lists
   - ACTION AIR CON would have their coverage cities

4. has_generators: NEW signal detection
   - Detects generator sales/installation
   - ACTION AIR CON would be TRUE (they sell generators)

5. has_commercial: NEW signal detection
   - Detects commercial HVAC capability
   - ACTION AIR CON would be TRUE (they offer commercial HVAC)


NEXT STEPS:
===========
1. Apply these changes to website_content_scraper.py
2. Re-run enrichment on the 50 companies
3. Verify ACTION AIR CON now has correct data
4. If accurate, run on remaining 150 ICP companies
"""
