"""
Shared Scraper Patterns - Used by Both BeautifulSoup and Browserbase Scrapers

This module centralizes all patterns, rules, and title classification logic
so that both FREE (BeautifulSoup) and Premium (Browserbase) scrapers stay in sync.

IMPORTANT: When updating patterns here, both scrapers automatically get the changes.
"""

import re
from typing import List, Dict, Set

# =============================================================================
# TEAM PAGE URL PATTERNS
# =============================================================================
# Common patterns for team/about/leadership pages on company websites.
# Order matters - more common patterns first for efficiency.

TEAM_PAGE_PATTERNS = [
    # Primary about/team pages
    "/about",
    "/about-us",
    "/about-us/",
    "/about/",
    "/team",
    "/our-team",
    "/our-team/",
    "/meet-the-team",
    "/meet-our-team",
    "/the-team",
    # Leadership/management
    "/leadership",
    "/leadership/",
    "/our-leadership",
    "/management",
    "/management-team",
    "/executives",
    "/executive-team",
    "/senior-leadership",
    # Company info
    "/company",
    "/company/",
    "/company/team",
    "/company/about",
    "/company/leadership",
    "/who-we-are",
    "/our-story",
    "/our-company",
    # People/staff
    "/people",
    "/our-people",
    "/staff",
    "/our-staff",
    "/employees",
    # Contact/services (sometimes has owner info)
    "/contact",
    "/contact-us",
    "/contact/",
    # Nested paths
    "/about/team",
    "/about/leadership",
    "/about/our-team",
    "/about/management",
    "/about/people",
    # Industry-specific
    "/meet-us",
    "/founders",
    "/owners",
    "/principals",
    "/partners",
    "/board",
    "/board-of-directors",
]

# =============================================================================
# ATL vs BTL Title Classification
# =============================================================================
# ATL (Above The Line) = Decision makers who can sign contracts/approve deals
# BTL (Below The Line) = Implementers who execute but don't have signing authority
#
# Key insight: In construction/trades, "Owner" and "President" are gold.
# VP+ titles are decision makers. Director depends on context.
# =============================================================================

# ATL (Above The Line) - DECISION MAKERS - these are your sales targets
ATL_TITLE_PATTERNS = [
    # C-Suite (always ATL)
    r"\b(CEO|Chief\s+Executive\s+Officer)\b",
    r"\b(CFO|Chief\s+Financial\s+Officer)\b",
    r"\b(COO|Chief\s+Operating\s+Officer)\b",
    r"\b(CTO|Chief\s+Technology\s+Officer)\b",
    r"\b(CMO|Chief\s+Marketing\s+Officer)\b",
    r"\b(CRO|Chief\s+Revenue\s+Officer)\b",
    r"\b(CSO|Chief\s+Sales\s+Officer|Chief\s+Strategy\s+Officer)\b",
    r"\b(CPO|Chief\s+Product\s+Officer|Chief\s+People\s+Officer)\b",
    r"\b(CHRO|Chief\s+Human\s+Resources\s+Officer)\b",
    r"\b(CIO|Chief\s+Information\s+Officer)\b",
    r"\b(CLO|Chief\s+Legal\s+Officer)\b",
    r"\b(Chief\s+\w+\s+Officer)\b",  # Catch-all for any Chief X Officer

    # Ownership & Founders (GOLD for construction/trades)
    r"\b(Owner|Co-Owner)\b",
    r"\b(Founder|Co-Founder)\b",
    r"\b(Partner|Managing\s+Partner|General\s+Partner)\b",
    r"\b(Principal)\b",
    r"\b(Proprietor)\b",

    # President-level (decision makers)
    r"\b(President)\b",
    r"\b(Vice\s+President|VP)\b",
    r"\b(SVP|Senior\s+Vice\s+President)\b",
    r"\b(EVP|Executive\s+Vice\s+President)\b",
    r"\b(AVP|Assistant\s+Vice\s+President)\b",

    # Director-level (usually decision makers)
    r"\b(Managing\s+Director)\b",
    r"\b(General\s+Manager|GM)\b",
    r"\b(Executive\s+Director)\b",
    r"\b(Director\s+of\s+\w+)\b",  # Director of Operations, Director of Sales, etc.
    r"\b(Regional\s+Director)\b",
    r"\b(Director)\b",  # Catch-all for director titles

    # Board-level
    r"\b(Chairman|Chairwoman|Chair)\b",
    r"\b(Board\s+Member)\b",
]

# ATL keywords for simple string matching (lowercase)
ATL_TITLE_KEYWORDS = [
    # C-Suite
    "ceo", "chief executive officer", "chief executive",
    "cfo", "chief financial officer", "chief financial",
    "cto", "chief technology officer", "chief technology",
    "coo", "chief operating officer", "chief operating",
    "cmo", "chief marketing officer", "chief marketing",
    "cpo", "chief product officer", "chief people officer",
    "cro", "chief revenue officer", "chief risk officer",
    "cio", "chief information officer", "chief innovation officer",
    "cso", "chief strategy officer", "chief security officer",
    "chro", "chief human resources",
    # Ownership & Founders (GOLD for construction/trades)
    "owner", "co-owner",
    "founder", "co-founder",
    "partner", "managing partner", "general partner",
    "principal", "proprietor",
    # President-level
    "president",
    "vice president", "vp",
    "senior vice president", "svp",
    "executive vice president", "evp",
    "assistant vice president", "avp",
    # Director-level
    "managing director",
    "general manager", "gm",
    "director of",
    "director",
    # Board-level
    "chairman", "chairwoman", "chair",
    "board member",
    "executive director",
    # Other ATL
    "head of",
    "division head",
]

# BTL (Below The Line) - IMPLEMENTERS - not primary sales targets
BTL_TITLE_PATTERNS = [
    # Managers (execute, don't decide)
    r"\b(Project\s+Manager)\b",
    r"\b(Operations\s+Manager)\b",
    r"\b(Sales\s+Manager)\b",
    r"\b(Account\s+Manager)\b",
    r"\b(Office\s+Manager)\b",
    r"\b(Warehouse\s+Manager)\b",
    r"\b(Service\s+Manager)\b",
    r"\b(Manager)\b",

    # Supervisors & Leads
    r"\b(Supervisor)\b",
    r"\b(Foreman)\b",
    r"\b(Team\s+Lead|Lead)\b",
    r"\b(Crew\s+Lead)\b",

    # Technical/Field roles
    r"\b(Technician)\b",
    r"\b(Installer)\b",
    r"\b(Electrician|Master\s+Electrician)\b",
    r"\b(Engineer(?!ing\s+Director))\b",
    r"\b(Estimator)\b",

    # Support roles
    r"\b(Coordinator)\b",
    r"\b(Administrator)\b",
    r"\b(Assistant)\b",
    r"\b(Specialist)\b",
    r"\b(Analyst)\b",
    r"\b(Representative|Rep)\b",
]

# =============================================================================
# GARBAGE FILTER: Names that are NOT real people
# =============================================================================

GARBAGE_NAMES: Set[str] = {
    # Service/product categories
    "installation types", "battery storage", "industrial solar", "commercial solar",
    "residential solar", "solar panels", "solar energy", "solar power",
    "heating", "cooling", "plumbing", "electrical", "hvac", "roofing",
    "air conditioning", "water heater", "energy", "services",
    "ev charging", "ev chargers", "solar installation", "solar installer",
    "heat pump", "ductless", "mini split", "geothermal",
    # Placeholder names
    "john doe", "jane doe", "test user", "sample name", "your name",
    "first last", "name here", "full name",
    # Navigation/UI text
    "learn more", "read more", "click here", "view all", "see more",
    "schedule now", "call now", "get quote", "request quote", "contact us",
    "about us", "our team", "meet the team", "leadership", "management",
    "follow us", "follow us:",
    # Social media
    "facebook", "twitter", "linkedin", "instagram", "youtube", "tiktok",
}

# Patterns that indicate concatenated names (e.g., "JohnCEO", "MaryDirector")
CONCATENATED_PATTERNS = [
    r'\w+(CEO|CFO|CTO|COO|CMO|VP|Vice|Director|Manager|Owner|Founder|President|Customer|Advocate|Designer|Specialist|Crew|Lead|Installer|Technician|Roofing|Partner|Foreman)$',
]

# Additional garbage patterns
GARBAGE_NAME_PATTERNS = [
    r'roofing installer',
    r'shingle installer',
    r'metal roof installer',
    r'solar tech',
    r'comp shingle',
    r'plumbing & heating',
    r'solar technician',
]

# Title qualifiers that should NOT be stripped (they're part of the title)
TITLE_QUALIFIERS: Set[str] = {
    # Level prefixes
    'svp', 'evp', 'avp', 'vp', 'senior', 'junior', 'sr', 'jr', 'chief',
    'executive', 'managing', 'assistant', 'associate', 'deputy',
    # Department/area qualifiers
    'warehouse', 'operations', 'project', 'field', 'regional', 'national',
    'global', 'area', 'district', 'zone', 'commercial', 'residential',
    'sales', 'marketing', 'finance', 'hr', 'it', 'tech', 'engineering',
    'construction', 'maintenance', 'service', 'customer', 'business',
    'product', 'account', 'general', 'corporate', 'master', 'maine',
    'north', 'south', 'east', 'west', 'america', 'division',
}

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def is_atl_title(title: str) -> bool:
    """
    Check if a title is Above The Line (decision maker).

    Uses both regex patterns and keyword matching.
    """
    if not title:
        return False

    title_lower = title.lower().strip()

    # Check keywords first (faster)
    for keyword in ATL_TITLE_KEYWORDS:
        if keyword in title_lower:
            return True

    # Check regex patterns
    for pattern in ATL_TITLE_PATTERNS:
        if re.search(pattern, title, re.IGNORECASE):
            return True

    return False


def is_garbage_name(name: str) -> bool:
    """Check if a name is garbage (not a real person)."""
    if not name:
        return True

    name_lower = name.lower().strip()

    # Check exact matches
    if name_lower in GARBAGE_NAMES:
        return True

    # Check patterns
    for pattern in GARBAGE_NAME_PATTERNS:
        if re.search(pattern, name_lower):
            return True

    # Check concatenated patterns
    for pattern in CONCATENATED_PATTERNS:
        if re.search(pattern, name):
            return True

    # Name too short
    if len(name_lower) < 3:
        return True

    # Name too long (probably scraped paragraph)
    if len(name) > 50:
        return True

    return False


def clean_title(title: str) -> str:
    """
    Clean up a title - strip READ BIO, pipe separators, merged names.

    Examples:
        "CO-FOUNDER | READ BIO" -> "CO-FOUNDER"
        "Jason BoyceVice President" -> "Vice President"
        "EVP & General Manager" -> "EVP & General Manager" (preserved)
    """
    if not title:
        return title

    # Strip "READ BIO" and similar suffixes
    title = re.sub(r'\s*\|\s*READ\s*BIO\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*-\s*READ\s*BIO\s*$', '', title, flags=re.IGNORECASE)
    title = re.sub(r'\s*READ\s*BIO\s*$', '', title, flags=re.IGNORECASE)

    # Strip "View Profile", "Learn More" etc.
    title = re.sub(r'\s*\|\s*(?:VIEW|LEARN|READ)\s*(?:PROFILE|MORE|BIO)\s*$', '', title, flags=re.IGNORECASE)

    # Strip trailing pipes and dashes
    title = re.sub(r'\s*[\|\-]\s*$', '', title)

    # Only strip ACTUAL person names concatenated to titles
    # Pattern: PersonName + TitleKeyword (without space)
    role_keywords = ['Vice', 'President', 'CEO', 'CFO', 'CTO', 'COO', 'CMO',
                     'Owner', 'Founder', 'Director', 'Partner']

    for keyword in role_keywords:
        match = re.match(rf'^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)({keyword}.*)$', title)
        if match:
            potential_name = match.group(1).strip()
            role_part = match.group(2).strip()

            # Verify the potential name is NOT a title qualifier
            name_words = potential_name.lower().split()
            if not any(w in TITLE_QUALIFIERS for w in name_words):
                # This looks like a person name prepended to a title
                title = role_part
                break

    return title.strip()


def split_concatenated_name(full_name: str) -> tuple:
    """
    Split concatenated names like "Becky BrandborgOwner/ Partner".

    Returns:
        (fixed_name, extracted_title) or (original_name, "") if no fix needed
    """
    if not full_name:
        return full_name, ""

    # Title patterns to detect in concatenated names
    title_patterns = [
        # Compound titles
        r'(Owner/?.*Partner)',
        r'(President\s*&?\s*Owner)',
        # Executive titles
        r'(CEO|CFO|CTO|COO|CMO|CPO|CRO|CHRO)',
        r'(Co-?[Ff]ounder.*)',
        r'(Founder.*)',
        r'(President.*)',
        r'(Vice\s*President.*)',
        r'(Director.*)',
        r'(VP.*)',
        r'(General\s*Manager.*)',
        r'(GM)',
        # Operational roles (crews, teams)
        r'(Tear\s*Off\s*(?:Crew|Lead).*)',
        r'((?:Crew|Team)\s*(?:Lead|Leader|Member).*)',
        r'(Office\s*(?:Administrator|Manager|Assistant).*)',
        r'(Project\s*Manager.*)',
        r'(Account(?:s)?\s*Manager.*)',
        r'(Sales\s*(?:Manager|Rep|Representative).*)',
        r'(Service\s*Manager.*)',
        r'(Operations\s*Manager.*)',
        # Generic roles
        r'(Manager.*)',
        r'(Partner)',
        r'(Owner)',
        r'(Foreman.*)',
        r'(Supervisor.*)',
        r'(Technician.*)',
        r'(Installer.*)',
        r'(Estimator.*)',
        r'(Auditor.*)',
        r'(Customer\s*(?:Advocate|Service).*)',
        r'(Administrator.*)',
    ]

    # Try each title pattern
    for pattern in title_patterns:
        match = re.search(r'([A-Za-z]+)(' + pattern[1:-1] + r'.*)$', full_name)
        if match:
            before_title = full_name[:match.start(2)]
            title_part = match.group(2)

            # Clean up the name
            if before_title and before_title[-1].islower():
                words = before_title.split()
                if words:
                    last_word = words[-1]
                    for i, char in enumerate(last_word):
                        if char.isupper() and i > 0:
                            fixed_last_word = last_word[:i] + " " + last_word[i:]
                            words[-1] = fixed_last_word
                            before_title = " ".join(words)
                            break

            title_part = clean_title(title_part)
            return before_title.strip(), title_part.strip()

    return full_name, ""
