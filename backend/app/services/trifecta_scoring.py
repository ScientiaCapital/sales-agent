"""
Trifecta Scoring Service

Centralized scoring algorithm to identify high-value "UNICORN" contractors.
Scores contractors based on Solar + Generator + Battery capabilities, OEM breadth,
trade diversity, geographic reach, and contact quality.

Author: Scientia Capital
Created: Dec 8, 2025
"""

from typing import List, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import re


# ============================================================================
# OEM CATEGORY DEFINITIONS
# ============================================================================

SOLAR_OEMS = [
    "Enphase", "SolarEdge", "SMA", "Tesla Solar", "Fronius",
    "Sungrow", "GoodWe", "Growatt", "Huawei", "Canadian Solar",
    "Sunpower", "REC Solar", "Q Cells", "JA Solar", "Jinko Solar",
    "Panasonic Solar", "LG Solar", "Trina Solar"
]

GENERATOR_OEMS = [
    "Generac", "Kohler", "Cummins", "Briggs & Stratton", "Briggs and Stratton",
    "Champion", "Caterpillar", "Honda", "Westinghouse",
    "Onan", "Yanmar", "Perkins", "MTU", "Detroit Diesel"
]

BATTERY_OEMS = [
    "Tesla Powerwall", "Tesla Megapack", "Generac PWRcell", "Enphase IQ",
    "LG Chem", "Sonnen", "SimpliPhi", "BYD", "Panasonic",
    "Samsung SDI", "Fortress Power", "StorEdge", "Pika Energy",
    "Blue Planet Energy", "Electriq Power"
]

HVAC_PREMIUM_OEMS = [
    "Carrier", "Trane", "Lennox", "Daikin", "Mitsubishi",
    "Fujitsu", "LG VRF", "LG Multi V", "York", "Bryant",
    "Rheem", "Ruud", "American Standard", "Bosch"
]

# All OEM sets for quick lookup
ALL_SOLAR_OEMS = {oem.lower() for oem in SOLAR_OEMS}
ALL_GENERATOR_OEMS = {oem.lower() for oem in GENERATOR_OEMS}
ALL_BATTERY_OEMS = {oem.lower() for oem in BATTERY_OEMS}
ALL_HVAC_PREMIUM_OEMS = {oem.lower() for oem in HVAC_PREMIUM_OEMS}


# ============================================================================
# TRADE CATEGORIES
# ============================================================================

TRADE_CATEGORIES = {
    "solar": ["solar", "photovoltaic", "pv", "solar panel", "solar installation"],
    "generator": ["generator", "standby generator", "backup generator", "emergency power"],
    "battery": ["battery storage", "energy storage", "battery backup", "ess"],
    "hvac": ["hvac", "heating", "cooling", "air conditioning", "furnace", "heat pump"],
    "electrical": ["electrical", "electrician", "electric", "wiring"],
    "plumbing": ["plumbing", "plumber", "pipe", "water heater"],
    "ev_charging": ["ev charger", "ev charging", "electric vehicle charging", "chargepoint"],
    "roofing": ["roofing", "roof", "roofer"],
    "insulation": ["insulation", "weatherization"],
    "water_treatment": ["water treatment", "water filtration", "water softener"],
}


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class TrifectaScore(BaseModel):
    """Trifecta scoring result"""
    total: int = Field(..., description="Total score (0-100)")
    signals: List[str] = Field(default_factory=list, description="Scoring signals/reasons")
    trade_diversity_pts: int = Field(0, description="Points from trade diversity (max 25)")
    energy_trifecta_pts: int = Field(0, description="Points from energy trifecta (max 25)")
    oem_breadth_pts: int = Field(0, description="Points from OEM breadth (max 20)")
    geographic_pts: int = Field(0, description="Points from geographic reach (max 15)")
    contact_quality_pts: int = Field(0, description="Points from contact quality (max 15)")
    has_solar: bool = Field(False, description="Has solar capability")
    has_generator: bool = Field(False, description="Has generator capability")
    has_battery: bool = Field(False, description="Has battery capability")
    is_unicorn: bool = Field(False, description="Full trifecta (Solar + Generator + Battery)")
    is_partial_trifecta: bool = Field(False, description="2 of 3 energy categories")
    tier: str = Field("LEAD", description="UNICORN, PLATINUM, GOLD, SILVER, BRONZE, LEAD")
    oem_categories: Dict[str, List[str]] = Field(default_factory=dict, description="OEMs by category")
    trades_detected: List[str] = Field(default_factory=list, description="Trades detected")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_text(text: str) -> str:
    """Normalize text for matching"""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text.lower().strip())


def detect_oem_categories(oem_brands: List[str]) -> Dict[str, List[str]]:
    """
    Detect which OEM categories are present

    Args:
        oem_brands: List of OEM brand names

    Returns:
        Dict with categories as keys and matched OEMs as values
    """
    categories = {
        "solar": [],
        "generator": [],
        "battery": [],
        "hvac_premium": []
    }

    if not oem_brands:
        return categories

    # Normalize OEM brands
    normalized_brands = {normalize_text(brand): brand for brand in oem_brands}

    for norm_brand, original_brand in normalized_brands.items():
        # Check solar
        for solar_oem in ALL_SOLAR_OEMS:
            if solar_oem in norm_brand or norm_brand in solar_oem:
                categories["solar"].append(original_brand)
                break

        # Check generator
        for gen_oem in ALL_GENERATOR_OEMS:
            if gen_oem in norm_brand or norm_brand in gen_oem:
                categories["generator"].append(original_brand)
                break

        # Check battery
        for battery_oem in ALL_BATTERY_OEMS:
            if battery_oem in norm_brand or norm_brand in battery_oem:
                categories["battery"].append(original_brand)
                break

        # Check HVAC premium
        for hvac_oem in ALL_HVAC_PREMIUM_OEMS:
            if hvac_oem in norm_brand or norm_brand in hvac_oem:
                categories["hvac_premium"].append(original_brand)
                break

    # Deduplicate
    for cat in categories:
        categories[cat] = list(set(categories[cat]))

    return categories


def count_trades(services_offered: List[str]) -> Dict[str, int]:
    """
    Count unique trades from services offered

    Args:
        services_offered: List of service strings

    Returns:
        Dict with trade names and count
    """
    if not services_offered:
        return {}

    detected_trades = set()
    normalized_services = [normalize_text(s) for s in services_offered]

    for trade_name, keywords in TRADE_CATEGORIES.items():
        for service in normalized_services:
            if any(keyword in service for keyword in keywords):
                detected_trades.add(trade_name)
                break

    return {trade: 1 for trade in detected_trades}


def is_premium_oem(oem_name: str) -> bool:
    """
    Check if OEM is premium tier

    Args:
        oem_name: OEM brand name

    Returns:
        True if premium tier
    """
    norm_name = normalize_text(oem_name)

    # Premium if in any of the premium categories
    premium_sets = [
        ALL_SOLAR_OEMS,
        ALL_GENERATOR_OEMS,
        ALL_BATTERY_OEMS,
        ALL_HVAC_PREMIUM_OEMS
    ]

    for premium_set in premium_sets:
        for premium_brand in premium_set:
            if premium_brand in norm_name or norm_name in premium_brand:
                return True

    return False


# ============================================================================
# MAIN SCORING FUNCTION
# ============================================================================

def calculate_trifecta_score(
    company_name: str,
    oem_brands: Optional[List[str]] = None,
    services_offered: Optional[List[str]] = None,
    states_served: Optional[List[str]] = None,
    has_atl_contact: bool = False,
    has_email: bool = False,
    has_direct_phone: bool = False
) -> TrifectaScore:
    """
    Calculate trifecta score for a contractor

    Scoring breakdown (100 pts max):
    - Trade Diversity (25 pts): 5+ trades = 25, 3-4 = 18, 2 = 12, 1 = 5
    - Energy Trifecta (25 pts): Full = 25 + UNICORN, Partial = 18, Single = 8
    - OEM Breadth (20 pts): 6+ OEMs = 20, 3-5 = 12, 1-2 = 5
    - Geographic Reach (15 pts): 5+ states = 15, 2-4 = 10, 1 = 3
    - Contact Quality (15 pts): ATL+email+phone = 15, ATL+(email OR phone) = 10, ATL = 5

    Args:
        company_name: Company name
        oem_brands: List of OEM brands
        services_offered: List of services
        states_served: List of states
        has_atl_contact: Has ATL contact
        has_email: Has email
        has_direct_phone: Has direct phone

    Returns:
        TrifectaScore object with detailed scoring
    """
    oem_brands = oem_brands or []
    services_offered = services_offered or []
    states_served = states_served or []

    signals = []

    # Detect OEM categories
    oem_categories = detect_oem_categories(oem_brands)
    has_solar = len(oem_categories["solar"]) > 0
    has_generator = len(oem_categories["generator"]) > 0
    has_battery = len(oem_categories["battery"]) > 0

    # Detect trades
    trades = count_trades(services_offered)
    trades_detected = list(trades.keys())
    trade_count = len(trades_detected)

    # 1. TRADE DIVERSITY (25 pts)
    if trade_count >= 5:
        trade_diversity_pts = 25
        signals.append(f"5+ trades ({trade_count})")
    elif trade_count >= 3:
        trade_diversity_pts = 18
        signals.append(f"3-4 trades ({trade_count})")
    elif trade_count == 2:
        trade_diversity_pts = 12
        signals.append("2 trades")
    elif trade_count == 1:
        trade_diversity_pts = 5
        signals.append("1 trade")
    else:
        trade_diversity_pts = 0
        signals.append("No trades detected")

    # 2. ENERGY TRIFECTA (25 pts)
    trifecta_count = sum([has_solar, has_generator, has_battery])
    is_unicorn = trifecta_count == 3
    is_partial_trifecta = trifecta_count == 2

    if is_unicorn:
        energy_trifecta_pts = 25
        signals.append("🦄 UNICORN: Solar + Generator + Battery")
    elif is_partial_trifecta:
        energy_trifecta_pts = 18
        energy_types = []
        if has_solar:
            energy_types.append("Solar")
        if has_generator:
            energy_types.append("Generator")
        if has_battery:
            energy_types.append("Battery")
        signals.append(f"Partial Trifecta: {' + '.join(energy_types)}")
    elif trifecta_count == 1:
        energy_trifecta_pts = 8
        if has_solar:
            signals.append("Solar only")
        elif has_generator:
            signals.append("Generator only")
        elif has_battery:
            signals.append("Battery only")
    else:
        energy_trifecta_pts = 0
        signals.append("No energy trifecta")

    # 3. OEM BREADTH (20 pts)
    total_oems = len(oem_brands)
    if total_oems >= 6:
        oem_breadth_pts = 20
        signals.append(f"6+ OEMs ({total_oems})")
    elif total_oems >= 3:
        oem_breadth_pts = 12
        signals.append(f"3-5 OEMs ({total_oems})")
    elif total_oems >= 1:
        oem_breadth_pts = 5
        signals.append(f"1-2 OEMs ({total_oems})")
    else:
        oem_breadth_pts = 0
        signals.append("No OEMs detected")

    # 4. GEOGRAPHIC REACH (15 pts)
    state_count = len(states_served) if states_served else 0
    if state_count >= 5:
        geographic_pts = 15
        signals.append(f"5+ states ({state_count})")
    elif state_count >= 2:
        geographic_pts = 10
        signals.append(f"2-4 states ({state_count})")
    elif state_count == 1:
        geographic_pts = 3
        signals.append("1 state")
    else:
        geographic_pts = 0
        signals.append("No geographic data")

    # 5. CONTACT QUALITY (15 pts)
    if has_atl_contact and has_email and has_direct_phone:
        contact_quality_pts = 15
        signals.append("ATL + email + phone")
    elif has_atl_contact and (has_email or has_direct_phone):
        contact_quality_pts = 10
        if has_email:
            signals.append("ATL + email")
        else:
            signals.append("ATL + phone")
    elif has_atl_contact:
        contact_quality_pts = 5
        signals.append("ATL only")
    else:
        contact_quality_pts = 0
        signals.append("No ATL contact")

    # TOTAL SCORE
    total = (
        trade_diversity_pts +
        energy_trifecta_pts +
        oem_breadth_pts +
        geographic_pts +
        contact_quality_pts
    )

    # TIER ASSIGNMENT
    if is_unicorn:
        tier = "UNICORN"
    elif total >= 80:
        tier = "PLATINUM"
    elif total >= 65:
        tier = "GOLD"
    elif total >= 50:
        tier = "SILVER"
    elif total >= 35:
        tier = "BRONZE"
    else:
        tier = "LEAD"

    return TrifectaScore(
        total=total,
        signals=signals,
        trade_diversity_pts=trade_diversity_pts,
        energy_trifecta_pts=energy_trifecta_pts,
        oem_breadth_pts=oem_breadth_pts,
        geographic_pts=geographic_pts,
        contact_quality_pts=contact_quality_pts,
        has_solar=has_solar,
        has_generator=has_generator,
        has_battery=has_battery,
        is_unicorn=is_unicorn,
        is_partial_trifecta=is_partial_trifecta,
        tier=tier,
        oem_categories=oem_categories,
        trades_detected=trades_detected
    )


# ============================================================================
# BATCH SCORING
# ============================================================================

def score_contractors_batch(contractors: List[Dict]) -> List[TrifectaScore]:
    """
    Score a batch of contractors

    Args:
        contractors: List of contractor dicts with keys:
            - company_name (required)
            - oem_brands (optional list)
            - services_offered (optional list)
            - states_served (optional list)
            - has_atl_contact (optional bool)
            - has_email (optional bool)
            - has_direct_phone (optional bool)

    Returns:
        List of TrifectaScore objects
    """
    results = []

    for contractor in contractors:
        score = calculate_trifecta_score(
            company_name=contractor.get("company_name", "Unknown"),
            oem_brands=contractor.get("oem_brands"),
            services_offered=contractor.get("services_offered"),
            states_served=contractor.get("states_served"),
            has_atl_contact=contractor.get("has_atl_contact", False),
            has_email=contractor.get("has_email", False),
            has_direct_phone=contractor.get("has_direct_phone", False)
        )
        results.append(score)

    return results


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # Models
    "TrifectaScore",

    # Main functions
    "calculate_trifecta_score",
    "score_contractors_batch",

    # Helper functions
    "detect_oem_categories",
    "count_trades",
    "is_premium_oem",

    # Constants
    "SOLAR_OEMS",
    "GENERATOR_OEMS",
    "BATTERY_OEMS",
    "HVAC_PREMIUM_OEMS",
    "TRADE_CATEGORIES",
]
