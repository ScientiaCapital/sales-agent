"""
Close CRM Deduplication Service

Prevents duplicate leads by querying Close CRM API BEFORE creating new leads.

Two-stage matching:
1. **Company-level**: Fuzzy match company name in Close CRM
2. **Contact-level**: If company found, check if contact already exists

This ensures we never create duplicate companies OR duplicate contacts within a company.

Usage:
    ```python
    from app.services.crm.close_deduplication import CloseDeduplicationService

    dedup = CloseDeduplicationService(api_key=os.getenv("CLOSE_API_KEY"))

    result = await dedup.check_duplicate(
        company_name="Acme Corporation",
        email="john@acme.com"
    )

    if result.is_duplicate:
        print(f"Found existing lead: {result.matched_lead_id}")
        print(f"Company match: {result.company_confidence}%")
        print(f"Contact match: {result.contact_confidence}%")
    ```
"""

import httpx
import base64
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.core.logging import setup_logging
from app.services.crm.base import CRMAuthenticationError, CRMNetworkError

logger = setup_logging(__name__)


# ========== Data Models ==========

@dataclass
class CloseLead:
    """Represents a lead from Close CRM"""
    lead_id: str
    company_name: str
    contacts: List[Dict[str, Any]]  # List of contacts in this lead
    status: str
    url: str


@dataclass
class DuplicationCheckResult:
    """Result of Close CRM duplication check"""
    is_duplicate: bool

    # Company-level matching
    company_match_found: bool
    company_confidence: float  # 0-100, fuzzy match score
    matched_lead_id: Optional[str] = None
    matched_company_name: Optional[str] = None

    # Contact-level matching
    contact_match_found: bool = False
    contact_confidence: float = 0.0
    matched_contact_id: Optional[str] = None
    matched_contact_email: Optional[str] = None

    # Recommendation
    recommendation: str = ""  # "create_new", "add_contact_to_existing", "skip_duplicate"


# ========== Close CRM Deduplication Service ==========

class CloseDeduplicationService:
    """
    Prevents duplicates by checking Close CRM API before lead creation.

    Matching Strategy:
    1. Search Close CRM for company name (fuzzy matching)
    2. If company found (>= 85% match), check contacts in that lead
    3. If contact email matches, it's a duplicate
    4. If contact doesn't exist, recommend adding to existing lead
    """

    BASE_URL = "https://api.close.com/api/v1"

    # Thresholds
    COMPANY_FUZZY_MATCH_THRESHOLD = 85.0  # 85% similarity = same company
    EMAIL_EXACT_MATCH_REQUIRED = True  # Email must match exactly

    def __init__(self, api_key: str):
        """
        Initialize Close CRM deduplication service.

        Args:
            api_key: Close CRM API key (format: api_xxx...)
        """
        if not api_key:
            raise CRMAuthenticationError("Close API key is required")

        self.api_key = api_key

        # Create Basic auth header
        auth_string = f"{api_key}:"
        auth_bytes = auth_string.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        self.auth_header = f"Basic {auth_b64}"

    async def check_duplicate(
        self,
        company_name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None
    ) -> DuplicationCheckResult:
        """
        Check if lead/contact already exists in Close CRM.

        Args:
            company_name: Company name to check
            email: Contact email (optional but recommended)
            phone: Contact phone (optional)

        Returns:
            DuplicationCheckResult with match details and recommendation
        """
        logger.info(f"Checking Close CRM for duplicates: company={company_name}, email={email}")

        # Step 1: Search for company in Close CRM
        company_matches = await self._search_companies(company_name)

        if not company_matches:
            # No company found - safe to create new lead
            return DuplicationCheckResult(
                is_duplicate=False,
                company_match_found=False,
                company_confidence=0.0,
                contact_match_found=False,
                recommendation="create_new"
            )

        # Step 2: Find best company match with fuzzy matching
        best_match = self._find_best_company_match(company_name, company_matches)

        if not best_match or best_match.confidence < self.COMPANY_FUZZY_MATCH_THRESHOLD:
            # Company match too weak - safe to create new lead
            return DuplicationCheckResult(
                is_duplicate=False,
                company_match_found=False,
                company_confidence=best_match.confidence if best_match else 0.0,
                contact_match_found=False,
                recommendation="create_new"
            )

        # Step 3: Company found! Check if contact already exists
        logger.info(
            f"Company match found: '{best_match.lead.company_name}' "
            f"(confidence: {best_match.confidence:.1f}%, lead_id: {best_match.lead.lead_id})"
        )

        if email:
            contact_match = self._find_contact_in_lead(email, best_match.lead)

            if contact_match:
                # Duplicate contact found!
                return DuplicationCheckResult(
                    is_duplicate=True,
                    company_match_found=True,
                    company_confidence=best_match.confidence,
                    matched_lead_id=best_match.lead.lead_id,
                    matched_company_name=best_match.lead.company_name,
                    contact_match_found=True,
                    contact_confidence=100.0,  # Exact email match
                    matched_contact_id=contact_match["id"],
                    matched_contact_email=email,
                    recommendation="skip_duplicate"
                )
            else:
                # Company exists but contact is new - add to existing lead
                return DuplicationCheckResult(
                    is_duplicate=False,
                    company_match_found=True,
                    company_confidence=best_match.confidence,
                    matched_lead_id=best_match.lead.lead_id,
                    matched_company_name=best_match.lead.company_name,
                    contact_match_found=False,
                    recommendation="add_contact_to_existing"
                )
        else:
            # No email provided - can't check contact level
            logger.warning(f"No email provided - can't verify contact uniqueness for {company_name}")
            return DuplicationCheckResult(
                is_duplicate=False,
                company_match_found=True,
                company_confidence=best_match.confidence,
                matched_lead_id=best_match.lead.lead_id,
                matched_company_name=best_match.lead.company_name,
                contact_match_found=False,
                recommendation="add_contact_to_existing"  # Assume contact is new
            )

    async def _search_companies(self, company_name: str) -> List[CloseLead]:
        """
        Search Close CRM for leads matching company name using Advanced Filtering API.

        Uses the modern /api/v1/data/search/ endpoint (NOT deprecated query parameter).

        Args:
            company_name: Company name to search

        Returns:
            List of CloseLead objects from Close CRM
        """
        try:
            async with httpx.AsyncClient() as client:
                # Use Advanced Filtering API (modern, NOT deprecated)
                # https://developer.close.com/resources/advanced-filtering
                search_payload = {
                    "query": {
                        "type": "and",
                        "queries": [
                            {
                                "type": "object_type",
                                "object_type": "lead"
                            },
                            {
                                "type": "field_condition",
                                "field": {
                                    "type": "regular_field",
                                    "object_type": "lead",
                                    "field_name": "name"  # Lead/company name field
                                },
                                "condition": {
                                    "type": "text",
                                    "mode": "full_words",  # Searches all words anywhere in company name
                                    "value": company_name
                                }
                            }
                        ]
                    },
                    "results_limit": 20  # Get up to 20 matches for fuzzy comparison
                }

                response = await client.post(
                    f"{self.BASE_URL}/data/search/",
                    headers={
                        "Authorization": self.auth_header,
                        "Content-Type": "application/json"
                    },
                    json=search_payload,
                    timeout=10.0
                )

                if response.status_code == 401:
                    raise CRMAuthenticationError("Invalid Close API key")

                if response.status_code >= 400:
                    logger.error(f"Close API error: {response.status_code} - {response.text}")
                    return []

                data = response.json()
                search_results = data.get("data", [])

                logger.info(f"Found {len(search_results)} potential matches in Close CRM for '{company_name}'")

                # Now fetch full lead details for each result (search returns minimal data)
                leads = []
                for result in search_results:
                    lead_id = result.get("id")
                    if not lead_id:
                        continue

                    # Fetch full lead details including contacts
                    lead_detail = await self._get_lead_details(client, lead_id)
                    if lead_detail:
                        leads.append(lead_detail)

                return leads

        except httpx.HTTPError as e:
            logger.error(f"Network error searching Close CRM: {e}")
            raise CRMNetworkError(f"Failed to search Close CRM: {e}")

    async def _get_lead_details(self, client: httpx.AsyncClient, lead_id: str) -> Optional[CloseLead]:
        """
        Fetch full lead details including contacts.

        Args:
            client: httpx client instance
            lead_id: Lead ID to fetch

        Returns:
            CloseLead object with full details, or None if fetch fails
        """
        try:
            response = await client.get(
                f"{self.BASE_URL}/lead/{lead_id}/",
                headers={
                    "Authorization": self.auth_header,
                    "Content-Type": "application/json"
                },
                timeout=5.0
            )

            if response.status_code != 200:
                logger.warning(f"Failed to fetch lead {lead_id}: {response.status_code}")
                return None

            lead_data = response.json()

            return CloseLead(
                lead_id=lead_data.get("id"),
                company_name=lead_data.get("name", ""),
                contacts=lead_data.get("contacts", []),
                status=lead_data.get("status_label", ""),
                url=lead_data.get("url", "")
            )

        except Exception as e:
            logger.error(f"Error fetching lead {lead_id}: {e}")
            return None

    def _find_best_company_match(
        self,
        query_company: str,
        candidates: List[CloseLead]
    ) -> Optional['CompanyMatch']:
        """
        Find best fuzzy match for company name.

        Uses SequenceMatcher for fuzzy string matching.

        Args:
            query_company: Company name to match
            candidates: List of candidate leads from Close CRM

        Returns:
            CompanyMatch with highest confidence, or None
        """
        if not candidates:
            return None

        best_match = None
        best_confidence = 0.0

        # Normalize query for comparison
        query_normalized = self._normalize_company_name(query_company)

        for candidate in candidates:
            candidate_normalized = self._normalize_company_name(candidate.company_name)

            # Calculate similarity using SequenceMatcher
            similarity = SequenceMatcher(None, query_normalized, candidate_normalized).ratio()
            confidence = similarity * 100.0  # Convert to percentage

            if confidence > best_confidence:
                best_confidence = confidence
                best_match = CompanyMatch(
                    lead=candidate,
                    confidence=confidence
                )

        return best_match

    def _normalize_company_name(self, company_name: str) -> str:
        """
        Normalize company name for fuzzy matching.

        Removes common suffixes, converts to lowercase, strips whitespace.

        Args:
            company_name: Raw company name

        Returns:
            Normalized company name
        """
        # Convert to lowercase
        normalized = company_name.lower()

        # Remove common company suffixes
        suffixes = [
            " inc", " inc.", " incorporated",
            " llc", " ltd", " ltd.",
            " corp", " corp.", " corporation",
            " co", " co.", " company",
            " plc", " limited", " ag", " gmbh"
        ]

        for suffix in suffixes:
            if normalized.endswith(suffix):
                normalized = normalized[:-len(suffix)]

        # Strip whitespace and punctuation
        normalized = normalized.strip().strip(".,;")

        return normalized

    def _find_contact_in_lead(
        self,
        email: str,
        lead: CloseLead
    ) -> Optional[Dict[str, Any]]:
        """
        Check if contact with given email exists in lead.

        Args:
            email: Email address to search for
            lead: CloseLead containing contacts

        Returns:
            Contact data if found, None otherwise
        """
        email_lower = email.lower()

        for contact in lead.contacts:
            # Check all emails for this contact
            contact_emails = contact.get("emails", [])
            for email_data in contact_emails:
                if email_data.get("email", "").lower() == email_lower:
                    logger.info(
                        f"Contact match found: {email} in lead {lead.lead_id} "
                        f"(contact_id: {contact.get('id')})"
                    )
                    return contact

        return None


@dataclass
class CompanyMatch:
    """Represents a fuzzy company name match"""
    lead: CloseLead
    confidence: float  # 0-100
