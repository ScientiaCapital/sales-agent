"""
OEM Taxonomy Configuration for MEP+E Scoring

Defines 6-category OEM tier lists based on dealer-scraper-mvp patterns
and BuildOps marquee client analysis (Crete United, Haynes Mechanical, etc.)

Categories:
- HVAC/Mechanical: Heat pumps, air conditioning, heating systems
- Solar: Photovoltaic panels and inverters
- Battery: Energy storage systems
- Generator: Backup power and standby generators
- Smart Panel: Load management and electrical distribution
- IoT: Smart home and building automation systems

Tier Scoring:
- Tier 1: 3 points (Premium brands, high sophistication)
- Tier 2: 1 point (Mid-market brands, solid quality)
"""

from typing import Dict, List

# ============================================================================
# OEM Taxonomy: 6 Categories for MEP+E Contractor Scoring
# ============================================================================

OEM_TAXONOMY: Dict[str, Dict[str, List[str]]] = {
    # Category 1: HVAC/Mechanical OEMs
    "hvac": {
        "tier1": [
            "Daikin",
            "Mitsubishi Electric",
            "Carrier",
            "Trane",
            "Lennox",
            "Bosch",
            "LG",
        ],
        "tier2": [
            "Rheem",
            "Goodman",
            "York",
            "Ruud",
            "American Standard",
            "Bryant",
            "Payne",
            "Amana",
        ],
    },
    # Category 2: Solar OEMs
    "solar": {
        "tier1": [
            "Tesla Solar",
            "Tesla",  # Alias
            "SunPower",
            "Panasonic",
            "LG Solar",
            "REC Solar",
            "Canadian Solar",
            "Q CELLS",
            "SolarEdge",  # Inverters but often paired with panels
        ],
        "tier2": [
            "Trina Solar",
            "JA Solar",
            "Jinko Solar",
            "JinkoSolar",  # Alias
            "LONGi Solar",
            "Silfab Solar",
            "Axitec",
            "Mission Solar",
        ],
    },
    # Category 3: Battery/Energy Storage OEMs
    "battery": {
        "tier1": [
            "Tesla Powerwall",
            "Tesla",  # Alias
            "Enphase IQ Battery",
            "Enphase",  # Alias
            "LG Chem RESU",
            "LG Chem",  # Alias
            "sonnenBatterie",
            "Sonnen",  # Alias
            "Generac PWRcell",
        ],
        "tier2": [
            "SimpliPhi",
            "BYD Battery-Box",
            "BYD",  # Alias
            "Pika Energy Harbor",
            "Pika",  # Alias
            "Electriq PowerPod",
            "Electriq",  # Alias
        ],
    },
    # Category 4: Generator/Backup Power OEMs
    "generator": {
        "tier1": [
            "Generac",
            "Kohler",
            "Cummins",
            "Briggs & Stratton",
            "Briggs and Stratton",  # Alias
            "CAT",
            "Caterpillar",  # Alias
        ],
        "tier2": [
            "Honda",
            "Champion",
            "Westinghouse",
            "Duromax",
            "Firman",
            "Predator",
        ],
    },
    # Category 5: Smart Panel OEMs (NEW - from user request)
    "smart_panel": {
        "tier1": [
            "Span Panel",
            "Span",  # Alias
            "Leviton Load Center",
            "Leviton",  # Alias
            "Schneider Electric Square D",
            "Schneider Electric",  # Alias
            "Square D",  # Alias
            "Eaton",
            "Lumin",
        ],
        "tier2": [
            "Emporia Vue",
            "Emporia",  # Alias
            "Sense",
            "Neurio",
        ],
    },
    # Category 6: IoT/Home Automation OEMs (NEW - from user request)
    "iot": {
        "tier1": [
            "Ecobee Pro",
            "Nest Pro",
            "Honeywell Prestige",
            "Carrier Infinity",
            "Control4",
            "Crestron",
            "Lutron",
        ],
        "tier2": [
            "Nest",
            "Ecobee",
            "Honeywell Home",
            "Ring",
            "SimpliSafe",
            "August",
            "Arlo",
        ],
    },
}

# Tier point values for MEP+E scoring
TIER_POINTS: Dict[str, int] = {
    "tier1": 3,  # Premium brands (high sophistication)
    "tier2": 1,  # Mid-market brands (solid quality)
}

# ============================================================================
# Helper Functions for OEM Taxonomy Lookup
# ============================================================================


def get_oem_category(oem_name: str) -> str | None:
    """
    Lookup OEM category by name (case-insensitive fuzzy matching).

    Args:
        oem_name: OEM brand name (e.g., "Generac", "Tesla", "Enphase")

    Returns:
        Category name ("hvac", "solar", "battery", etc.) or None if not found

    Examples:
        >>> get_oem_category("Generac")
        'generator'
        >>> get_oem_category("Tesla Powerwall")
        'battery'
        >>> get_oem_category("tesla")  # Case insensitive
        'solar'
    """
    oem_lower = oem_name.lower().strip()

    for category, tiers in OEM_TAXONOMY.items():
        for tier_name, brands in tiers.items():
            for brand in brands:
                if brand.lower() in oem_lower or oem_lower in brand.lower():
                    return category

    return None


def get_oem_tier(oem_name: str) -> str | None:
    """
    Lookup OEM tier by name (case-insensitive fuzzy matching).

    Args:
        oem_name: OEM brand name

    Returns:
        Tier name ("tier1" or "tier2") or None if not found

    Examples:
        >>> get_oem_tier("SunPower")
        'tier1'
        >>> get_oem_tier("Trina Solar")
        'tier2'
    """
    oem_lower = oem_name.lower().strip()

    for category, tiers in OEM_TAXONOMY.items():
        for tier_name, brands in tiers.items():
            for brand in brands:
                if brand.lower() in oem_lower or oem_lower in brand.lower():
                    return tier_name

    return None


def get_oem_tier_points(oem_name: str) -> int:
    """
    Get point value for OEM based on tier classification.

    Args:
        oem_name: OEM brand name

    Returns:
        Point value (3 for tier1, 1 for tier2, 0 if not found)

    Examples:
        >>> get_oem_tier_points("Tesla")
        3
        >>> get_oem_tier_points("Jinko Solar")
        1
        >>> get_oem_tier_points("Unknown Brand")
        0
    """
    tier = get_oem_tier(oem_name)
    if tier:
        return TIER_POINTS.get(tier, 0)
    return 0


def categorize_oems(oems_list: List[str]) -> Dict[str, List[str]]:
    """
    Categorize a list of OEM names into 6 categories.

    Args:
        oems_list: List of OEM brand names

    Returns:
        Dictionary with category keys and lists of OEMs

    Examples:
        >>> categorize_oems(["Generac", "Tesla", "Enphase", "Daikin"])
        {
            'hvac': ['Daikin'],
            'solar': ['Tesla'],
            'battery': ['Tesla', 'Enphase'],
            'generator': ['Generac'],
            'smart_panel': [],
            'iot': []
        }
    """
    categorized: Dict[str, List[str]] = {
        "hvac": [],
        "solar": [],
        "battery": [],
        "generator": [],
        "smart_panel": [],
        "iot": [],
    }

    for oem in oems_list:
        category = get_oem_category(oem)
        if category and oem not in categorized[category]:
            categorized[category].append(oem)

    return categorized


def count_oems_by_category(oems_list: List[str]) -> Dict[str, int]:
    """
    Count OEMs in each category.

    Args:
        oems_list: List of OEM brand names

    Returns:
        Dictionary with category keys and count values

    Examples:
        >>> count_oems_by_category(["Generac", "Tesla", "Enphase", "Daikin"])
        {
            'hvac': 1,
            'solar': 1,
            'battery': 2,
            'generator': 1,
            'smart_panel': 0,
            'iot': 0
        }
    """
    categorized = categorize_oems(oems_list)
    return {category: len(oems) for category, oems in categorized.items()}


# ============================================================================
# ZIP Code Targeting Configuration (from dealer-scraper-mvp)
# ============================================================================

# Total: ~404 ZIP codes for national coverage
# - 179 wealthy ZIP codes (all 50 states)
# - ~150 major metro ZIP codes (2-3 per state)
# - 75 SREC state ZIP codes (15 states × 5 each)

# Note: Full ZIP list should be imported from dealer-scraper-mvp repo
# This is just the structure for reference
ZIP_TARGETING = {
    "wealthy_zips": 179,  # Affluent areas, $150K+ median income
    "major_metro_zips": 150,  # 2-3 per state for all 50 states
    "srec_state_zips": 75,  # CA, TX, PA, MA, NJ, FL, NY, OH, MD, DC, DE, NH, RI, CT, IL
    "total_zips": 404,
}
