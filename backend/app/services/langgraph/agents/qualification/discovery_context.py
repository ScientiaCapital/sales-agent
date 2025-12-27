"""Discovery context: Shared state for contact discovery stages."""
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field


@dataclass
class DiscoveryContext:
    """Context for contact discovery across stages."""
    company_name: str
    company_website: Optional[str] = None
    company_phone: Optional[str] = None
    industry: Optional[str] = None
    lead_id: Optional[int] = None

    # Accumulated state
    all_contacts: List[Dict[str, Any]] = field(default_factory=list)
    seen_emails: set = field(default_factory=set)
    atl_contacts: List[Dict[str, Any]] = field(default_factory=list)
    btl_contacts: List[Dict[str, Any]] = field(default_factory=list)
    primary_email: Optional[str] = None
    extraction_method: str = "none"
    discovery_cost: float = 0.0
    notes: str = ""


__all__ = ["DiscoveryContext"]
