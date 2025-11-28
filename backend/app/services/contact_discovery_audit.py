"""
Contact Discovery Audit Service - Comprehensive logging for ATL/BTL contact discovery

Provides visibility into:
1. Every discovery method attempted (Hunter.io, Apollo, LinkedIn, Scraping)
2. Success/failure of each method with reasons
3. ATL vs BTL contact separation
4. Total contacts discovered per source
5. Fallback chain execution

Usage:
    audit = ContactDiscoveryAudit(company_name="ABC Corp")

    # Log each discovery attempt
    audit.log_attempt("hunter_io", success=True, contacts=3, atl=2, btl=1, latency_ms=850)
    audit.log_attempt("apollo", success=False, reason="API key not configured")
    audit.log_attempt("website_scrape", success=True, contacts=1, atl=0, btl=1, latency_ms=2100)

    # Get summary
    summary = audit.get_summary()
    # Returns detailed discovery audit with fallback chain visibility
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class DiscoveryMethod(str, Enum):
    """All available contact discovery methods"""
    # Qualification Stage
    WEBSITE_DISCOVERY = "website_discovery"  # Find company website
    HUNTER_DOMAIN_SEARCH = "hunter_domain_search"  # Hunter.io domain search
    APOLLO_DOMAIN_SEARCH = "apollo_domain_search"  # Apollo domain + enrichment
    APOLLO_PHONE_LOOKUP = "apollo_phone_lookup"  # Apollo phone-based search
    WEBSITE_EMAIL_SCRAPE = "website_email_scrape"  # EmailExtractor scraping
    REVIEW_SCRAPING = "review_scraping"  # Google, Yelp, BBB reputation

    # Enrichment Stage
    HUNTER_EMAIL_FINDER = "hunter_email_finder"  # Hunter.io specific person lookup
    WEBSITE_TEAM_SCRAPE = "website_team_scrape"  # Team/about page scraping
    LINKEDIN_PROFILE = "linkedin_profile"  # LinkedIn profile scraping
    BROWSERBASE_TEAM = "browserbase_team"  # Browserbase team page scraping

    # CRM Sources
    CLOSE_CRM_EXISTING = "close_crm_existing"  # Existing contacts in CRM


@dataclass
class DiscoveryAttempt:
    """Single discovery attempt record"""
    method: DiscoveryMethod
    success: bool
    contacts_found: int = 0
    atl_contacts: int = 0
    btl_contacts: int = 0
    latency_ms: int = 0
    cost_usd: float = 0.0
    reason: Optional[str] = None  # Failure reason or success details
    contacts_data: List[Dict[str, Any]] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class ContactDiscoveryAudit:
    """
    Comprehensive contact discovery audit trail.

    Tracks every discovery attempt for a company, providing
    full visibility into the ATL→BTL fallback chain.
    """
    company_name: str
    company_website: Optional[str] = None
    attempts: List[DiscoveryAttempt] = field(default_factory=list)

    # Aggregated results
    all_contacts: List[Dict[str, Any]] = field(default_factory=list)
    seen_emails: set = field(default_factory=set)

    # Session tracking
    session_id: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.utcnow)

    def log_attempt(
        self,
        method: DiscoveryMethod | str,
        success: bool,
        contacts: int = 0,
        atl: int = 0,
        btl: int = 0,
        latency_ms: int = 0,
        cost_usd: float = 0.0,
        reason: Optional[str] = None,
        contacts_data: Optional[List[Dict]] = None
    ) -> None:
        """
        Log a single discovery attempt.

        Args:
            method: Discovery method used
            success: Whether the method succeeded
            contacts: Total contacts found
            atl: Above-the-line (decision makers) count
            btl: Below-the-line (non-decision makers) count
            latency_ms: Time taken in milliseconds
            cost_usd: Cost in USD (e.g., 0.01 for Hunter.io)
            reason: Success details or failure reason
            contacts_data: Raw contact data for merging
        """
        # Convert string to enum if needed
        if isinstance(method, str):
            try:
                method = DiscoveryMethod(method)
            except ValueError:
                logger.warning(f"Unknown discovery method: {method}")
                # Use string value anyway for flexibility

        attempt = DiscoveryAttempt(
            method=method,
            success=success,
            contacts_found=contacts,
            atl_contacts=atl,
            btl_contacts=btl,
            latency_ms=latency_ms,
            cost_usd=cost_usd,
            reason=reason,
            contacts_data=contacts_data or []
        )

        self.attempts.append(attempt)

        # Log immediately for visibility
        status_icon = "✅" if success else "❌"
        if success and contacts > 0:
            logger.info(
                f"{status_icon} [{method.value if hasattr(method, 'value') else method}] "
                f"{self.company_name}: Found {contacts} contacts ({atl} ATL, {btl} BTL) "
                f"in {latency_ms}ms, cost=${cost_usd:.4f}"
            )
        elif success:
            logger.info(
                f"{status_icon} [{method.value if hasattr(method, 'value') else method}] "
                f"{self.company_name}: No contacts found ({reason or 'empty result'})"
            )
        else:
            logger.warning(
                f"{status_icon} [{method.value if hasattr(method, 'value') else method}] "
                f"{self.company_name}: Failed - {reason or 'unknown error'}"
            )

        # Merge contacts if provided
        if contacts_data:
            self._merge_contacts(contacts_data, str(method.value if hasattr(method, 'value') else method))

    def _merge_contacts(self, contacts: List[Dict], source: str) -> int:
        """
        Merge new contacts into all_contacts, deduping by email.

        Returns:
            Number of new contacts added (not duplicates)
        """
        new_count = 0
        for contact in contacts:
            email = contact.get('email', '').lower().strip()
            if email and email not in self.seen_emails:
                # Tag with source if not already tagged
                if 'source' not in contact:
                    contact['source'] = source
                self.all_contacts.append(contact)
                self.seen_emails.add(email)
                new_count += 1
            elif email and email in self.seen_emails:
                # Cross-verification: update existing with new source
                for existing in self.all_contacts:
                    if existing.get('email', '').lower() == email:
                        existing_sources = existing.get('verified_by', existing.get('source', ''))
                        if source not in existing_sources:
                            existing['verified_by'] = f"{existing_sources}+{source}"
                            logger.debug(f"Cross-verified {email}: {existing['verified_by']}")
                        break

        return new_count

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive discovery summary.

        Returns structured audit data suitable for:
        - Qualification notes (human-readable)
        - Lead audit log (structured storage)
        - Pipeline monitoring (aggregated metrics)
        """
        # Calculate totals
        total_attempts = len(self.attempts)
        successful_attempts = sum(1 for a in self.attempts if a.success)
        failed_attempts = sum(1 for a in self.attempts if not a.success)

        total_contacts = len(self.all_contacts)
        atl_contacts = [c for c in self.all_contacts if c.get('is_atl', False)]
        btl_contacts = [c for c in self.all_contacts if not c.get('is_atl', False)]

        total_latency = sum(a.latency_ms for a in self.attempts)
        total_cost = sum(a.cost_usd for a in self.attempts)

        # Build method breakdown
        method_results = {}
        for attempt in self.attempts:
            method_key = attempt.method.value if hasattr(attempt.method, 'value') else str(attempt.method)
            method_results[method_key] = {
                "success": attempt.success,
                "contacts_found": attempt.contacts_found,
                "atl": attempt.atl_contacts,
                "btl": attempt.btl_contacts,
                "latency_ms": attempt.latency_ms,
                "cost_usd": attempt.cost_usd,
                "reason": attempt.reason
            }

        # Determine primary ATL contact
        primary_contact = None
        if atl_contacts:
            primary_contact = atl_contacts[0]
        elif btl_contacts:
            primary_contact = btl_contacts[0]

        return {
            "company_name": self.company_name,
            "company_website": self.company_website,
            "session_id": self.session_id,

            # Aggregated results
            "total_contacts": total_contacts,
            "atl_contacts": len(atl_contacts),
            "btl_contacts": len(btl_contacts),
            "primary_contact": primary_contact,

            # Method breakdown
            "discovery_attempts": total_attempts,
            "successful_methods": successful_attempts,
            "failed_methods": failed_attempts,
            "method_results": method_results,

            # Performance
            "total_latency_ms": total_latency,
            "total_cost_usd": total_cost,

            # Raw data
            "all_contacts": self.all_contacts,
            "atl_list": atl_contacts,
            "btl_list": btl_contacts,

            # Timestamps
            "start_time": self.start_time.isoformat(),
            "end_time": datetime.utcnow().isoformat()
        }

    def get_qualification_notes(self) -> str:
        """
        Generate human-readable notes for qualification stage.

        Returns string suitable for `notes` field in qualification result.
        """
        summary = self.get_summary()

        lines = [
            "",
            "=" * 50,
            "CONTACT DISCOVERY AUDIT",
            "=" * 50,
            f"Company: {self.company_name}",
            f"Website: {self.company_website or 'Not provided'}",
            ""
        ]

        # Discovery chain
        lines.append("DISCOVERY METHODS ATTEMPTED:")
        for attempt in self.attempts:
            method_name = attempt.method.value if hasattr(attempt.method, 'value') else str(attempt.method)
            if attempt.success and attempt.contacts_found > 0:
                lines.append(f"  ✅ {method_name}: {attempt.contacts_found} contacts ({attempt.atl_contacts} ATL, {attempt.btl_contacts} BTL)")
            elif attempt.success:
                lines.append(f"  ⚪ {method_name}: No contacts ({attempt.reason or 'empty'})")
            else:
                lines.append(f"  ❌ {method_name}: FAILED - {attempt.reason or 'error'}")

        lines.append("")

        # Summary
        lines.append(f"TOTAL: {summary['total_contacts']} contacts ({summary['atl_contacts']} ATL, {summary['btl_contacts']} BTL)")
        lines.append(f"COST: ${summary['total_cost_usd']:.4f}")
        lines.append(f"LATENCY: {summary['total_latency_ms']}ms")

        # ATL contacts detail
        if summary['atl_list']:
            lines.append("")
            lines.append("ATL CONTACTS (Decision Makers):")
            for i, contact in enumerate(summary['atl_list'][:5], 1):
                name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
                title = contact.get('position', contact.get('title', 'Unknown'))
                email = contact.get('email', 'No email')
                source = contact.get('verified_by', contact.get('source', 'unknown'))
                lines.append(f"  {i}. {name} ({title})")
                lines.append(f"     📧 {email} [{source}]")
            if len(summary['atl_list']) > 5:
                lines.append(f"  ... and {len(summary['atl_list']) - 5} more ATL contacts")

        # BTL contacts summary
        if summary['btl_list']:
            lines.append("")
            lines.append(f"BTL CONTACTS (Champions): {len(summary['btl_list'])} found")
            for contact in summary['btl_list'][:3]:
                name = f"{contact.get('first_name', '')} {contact.get('last_name', '')}".strip()
                title = contact.get('position', contact.get('title', 'Unknown'))
                lines.append(f"  • {name} ({title})")

        lines.append("")
        lines.append("=" * 50)

        return "\n".join(lines)

    def log_disabled_method(self, method: DiscoveryMethod | str, reason: str) -> None:
        """
        Log that a discovery method is disabled (not a failure, just not available).

        This provides visibility that the method EXISTS but is currently disabled.
        """
        self.log_attempt(
            method=method,
            success=False,
            reason=f"DISABLED: {reason}"
        )


# Singleton factory function
_audit_instances: Dict[str, ContactDiscoveryAudit] = {}


def get_discovery_audit(
    company_name: str,
    company_website: Optional[str] = None,
    session_id: Optional[str] = None,
    create_new: bool = False
) -> ContactDiscoveryAudit:
    """
    Get or create a discovery audit instance for a company.

    Args:
        company_name: Company being processed
        company_website: Company website (optional)
        session_id: Pipeline session ID for tracking
        create_new: Force create new audit (for new pipeline runs)

    Returns:
        ContactDiscoveryAudit instance
    """
    key = f"{company_name}:{session_id or 'default'}"

    if create_new or key not in _audit_instances:
        _audit_instances[key] = ContactDiscoveryAudit(
            company_name=company_name,
            company_website=company_website,
            session_id=session_id
        )

    return _audit_instances[key]


def clear_audit_cache():
    """Clear all cached audit instances (for testing)."""
    global _audit_instances
    _audit_instances = {}
