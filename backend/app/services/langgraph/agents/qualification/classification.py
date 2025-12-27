"""Classification utilities: ATL title detection and phone type classification."""
import re
from typing import Optional, List, Dict, Any

from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ATL keywords for decision-maker identification
ATL_KEYWORDS = [
    "ceo", "chief executive", "president", "owner", "founder", "co-founder",
    "cto", "chief technology", "cfo", "chief financial", "coo", "chief operating",
    "vp", "vice president", "svp", "senior vice president", "evp", "executive vice president",
    "director", "head of", "manager", "partner", "principal"
]


def is_atl_title(title: str) -> bool:
    """
    Check if job title indicates Above-The-Line (decision maker) position.

    Args:
        title: Job title string

    Returns:
        True if title matches ATL keywords
    """
    if not title:
        return False

    title_lower = title.lower()
    return any(keyword in title_lower for keyword in ATL_KEYWORDS)


def normalize_phone(phone: str) -> str:
    """Normalize phone number to last 10 digits for comparison."""
    if not phone:
        return ""
    return re.sub(r'\D', '', str(phone))[-10:]


def classify_phones(
    contacts: List[Dict[str, Any]],
    company_phone: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Classify phone numbers as direct_line vs main_office.

    Logic:
    1. If Hunter.io returns unique phone for contact → direct_line (highest value!)
    2. If all contacts share same phone → main_office (receptionist likely)
    3. If contact has no phone, fallback to company_phone → main_office

    Args:
        contacts: List of contact dicts with optional 'phone' field
        company_phone: Fallback company phone from CSV import

    Returns:
        Contacts with 'phone_type' and 'phone_source' fields added
    """
    if not contacts:
        return contacts

    # Collect all phones from contacts (from Hunter.io)
    hunter_phones = {}
    for c in contacts:
        phone = c.get('phone')
        if phone:
            normalized = normalize_phone(phone)
            if normalized:
                hunter_phones[normalized] = hunter_phones.get(normalized, 0) + 1

    # Determine if phones are shared (main_office) or unique (direct_line)
    unique_phones = set(hunter_phones.keys())

    for contact in contacts:
        hunter_phone = contact.get('phone')
        hunter_phone_normalized = normalize_phone(hunter_phone) if hunter_phone else ""

        if hunter_phone_normalized:
            # Hunter.io provided a phone - check if it's unique
            if hunter_phones.get(hunter_phone_normalized, 0) == 1 and len(unique_phones) > 1:
                # Unique phone among contacts = likely direct line
                contact['phone_type'] = 'direct_line'
                contact['phone_source'] = 'hunter_io'
            else:
                # Shared phone OR only phone found = main office
                contact['phone_type'] = 'main_office'
                contact['phone_source'] = 'hunter_io'
        elif company_phone:
            # No Hunter phone, fallback to company CSV phone
            contact['phone'] = company_phone
            contact['phone_type'] = 'main_office'
            contact['phone_source'] = 'company_csv'
        else:
            # No phone available at all
            contact['phone_type'] = None
            contact['phone_source'] = None

    # Log phone classification stats
    direct_count = sum(1 for c in contacts if c.get('phone_type') == 'direct_line')
    main_count = sum(1 for c in contacts if c.get('phone_type') == 'main_office')
    no_phone = sum(1 for c in contacts if not c.get('phone_type'))

    logger.info(
        f"Phone classification: {direct_count} direct_line, {main_count} main_office, "
        f"{no_phone} no_phone (total: {len(contacts)})"
    )

    return contacts


__all__ = ["is_atl_title", "classify_phones", "normalize_phone", "ATL_KEYWORDS"]
