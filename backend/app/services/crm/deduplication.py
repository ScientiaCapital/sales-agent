"""
CRM Deduplication Engine

Multi-field matching algorithm to prevent duplicate/triplicate leads in Close CRM.
Uses email, domain, LinkedIn URL, company name fuzzy matching, and phone number
to calculate confidence scores for potential duplicates.

Features:
- Email exact match (100% confidence - primary key)
- Domain-based matching (@company.com → 80% confidence)
- LinkedIn URL exact match (95% confidence)
- Company name fuzzy matching via Levenshtein distance (60-90% confidence)
- Phone number normalization and matching (70% confidence)
- Aggregate confidence scoring with threshold (85% = duplicate alert)

Usage:
    ```python
    from app.services.crm.deduplication import DeduplicationEngine
    from app.models.database import SessionLocal

    db = SessionLocal()
    dedup = DeduplicationEngine(db)

    # Check for duplicates
    result = await dedup.find_duplicates(
        email="john@acme.com",
        company="Acme Corporation"
    )

    if result.is_duplicate:
        print(f"Duplicate found! Confidence: {result.confidence}%")
        print(f"Matched contacts: {result.matches}")
    ```
"""

import re
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.models.crm import CRMContact
from app.models.lead import Lead
from app.core.logging import setup_logging

logger = setup_logging(__name__)


# ========== Data Models ==========

@dataclass
class MatchDetails:
    """Details about a single field match"""
    field_name: str
    matched_value: str
    confidence: float  # 0-100
    match_type: str  # "exact", "fuzzy", "domain", "normalized"
    reason: str


@dataclass
class DuplicateMatch:
    """A potential duplicate contact with match details"""
    contact: CRMContact  # Matched contact from database
    confidence: float  # Overall confidence score (0-100)
    match_details: List[MatchDetails]  # Individual field matches

    def __repr__(self):
        return (
            f"DuplicateMatch(email={self.contact.email}, "
            f"company={self.contact.company}, confidence={self.confidence:.1f}%)"
        )


@dataclass
class DeduplicationResult:
    """Result of deduplication check"""
    is_duplicate: bool  # True if confidence >= threshold
    confidence: float  # Overall confidence score (0-100)
    matches: List[DuplicateMatch]  # All potential duplicates found
    threshold: float  # Threshold used (default 85%)
    checked_fields: List[str]  # Fields that were checked

    def get_best_match(self) -> Optional[DuplicateMatch]:
        """Get the highest confidence match"""
        if not self.matches:
            return None
        return max(self.matches, key=lambda m: m.confidence)


# ========== Deduplication Engine ==========

class DeduplicationEngine:
    """
    Multi-field deduplication engine for CRM contacts.

    Prevents duplicate/triplicate leads by matching across multiple fields
    with configurable confidence threshold.
    """

    # Confidence thresholds for duplicate detection
    DEFAULT_DUPLICATE_THRESHOLD = 85.0  # 85% confidence = duplicate

    # Individual field confidence scores
    EMAIL_EXACT_MATCH_CONFIDENCE = 100.0
    LINKEDIN_URL_EXACT_MATCH_CONFIDENCE = 95.0
    DOMAIN_MATCH_CONFIDENCE = 80.0
    PHONE_MATCH_CONFIDENCE = 70.0
    COMPANY_NAME_BASE_CONFIDENCE = 60.0  # Minimum for fuzzy match

    def __init__(
        self,
        db: Session,
        duplicate_threshold: float = DEFAULT_DUPLICATE_THRESHOLD
    ):
        """
        Initialize deduplication engine.

        Args:
            db: Database session for querying existing contacts
            duplicate_threshold: Confidence threshold for duplicate detection (default: 85%)
        """
        self.db = db
        self.duplicate_threshold = duplicate_threshold

    async def find_duplicates(
        self,
        email: Optional[str] = None,
        company: Optional[str] = None,
        linkedin_url: Optional[str] = None,
        phone: Optional[str] = None,
        company_website: Optional[str] = None
    ) -> DeduplicationResult:
        """
        Find potential duplicate contacts across multiple fields.

        Args:
            email: Email address to check
            company: Company name for fuzzy matching
            linkedin_url: LinkedIn profile URL
            phone: Phone number
            company_website: Company website for domain extraction

        Returns:
            DeduplicationResult with matches and confidence scores
        """
        checked_fields = []
        potential_matches: Dict[int, List[MatchDetails]] = {}  # contact_id -> [match_details]

        # 1. Email exact match (primary key)
        if email:
            checked_fields.append("email")
            matches = await self._match_by_email(email)
            for contact in matches:
                if contact.id not in potential_matches:
                    potential_matches[contact.id] = []
                potential_matches[contact.id].append(MatchDetails(
                    field_name="email",
                    matched_value=contact.email,
                    confidence=self.EMAIL_EXACT_MATCH_CONFIDENCE,
                    match_type="exact",
                    reason=f"Exact email match: {email}"
                ))

        # 2. Domain-based matching
        if email or company_website:
            checked_fields.append("domain")
            domain = self._extract_domain(email or company_website)
            if domain:
                matches = await self._match_by_domain(domain)
                for contact in matches:
                    if contact.id not in potential_matches:
                        potential_matches[contact.id] = []
                    potential_matches[contact.id].append(MatchDetails(
                        field_name="domain",
                        matched_value=contact.email or "",
                        confidence=self.DOMAIN_MATCH_CONFIDENCE,
                        match_type="domain",
                        reason=f"Same domain: @{domain}"
                    ))

        # 3. LinkedIn URL exact match
        if linkedin_url:
            checked_fields.append("linkedin_url")
            matches = await self._match_by_linkedin_url(linkedin_url)
            for contact in matches:
                if contact.id not in potential_matches:
                    potential_matches[contact.id] = []
                potential_matches[contact.id].append(MatchDetails(
                    field_name="linkedin_url",
                    matched_value=contact.linkedin_url or "",
                    confidence=self.LINKEDIN_URL_EXACT_MATCH_CONFIDENCE,
                    match_type="exact",
                    reason=f"Exact LinkedIn URL match: {linkedin_url}"
                ))

        # 4. Phone number normalized match
        if phone:
            checked_fields.append("phone")
            normalized_phone = self._normalize_phone(phone)
            if normalized_phone:
                matches = await self._match_by_phone(normalized_phone)
                for contact in matches:
                    if contact.id not in potential_matches:
                        potential_matches[contact.id] = []
                    potential_matches[contact.id].append(MatchDetails(
                        field_name="phone",
                        matched_value=contact.phone or "",
                        confidence=self.PHONE_MATCH_CONFIDENCE,
                        match_type="normalized",
                        reason=f"Phone number match: {normalized_phone}"
                    ))

        # 5. Company name fuzzy matching (slowest, run last)
        if company:
            checked_fields.append("company")
            matches = await self._match_by_company_fuzzy(company)
            for contact, similarity in matches:
                if contact.id not in potential_matches:
                    potential_matches[contact.id] = []
                # Scale confidence based on similarity (60% base + 30% * similarity)
                fuzzy_confidence = self.COMPANY_NAME_BASE_CONFIDENCE + (30.0 * similarity)
                potential_matches[contact.id].append(MatchDetails(
                    field_name="company",
                    matched_value=contact.company or "",
                    confidence=fuzzy_confidence,
                    match_type="fuzzy",
                    reason=f"Company name similarity: {similarity:.1%} ('{company}' vs '{contact.company}')"
                ))

        # Calculate aggregate confidence for each contact
        duplicate_matches = []
        for contact_id, match_details_list in potential_matches.items():
            # Get contact object
            contact = self.db.query(CRMContact).filter(CRMContact.id == contact_id).first()
            if not contact:
                continue

            # Calculate overall confidence (max of individual field confidences)
            # Use max instead of average to avoid diluting strong signals
            overall_confidence = max(detail.confidence for detail in match_details_list)

            duplicate_matches.append(DuplicateMatch(
                contact=contact,
                confidence=overall_confidence,
                match_details=match_details_list
            ))

        # Sort by confidence (highest first)
        duplicate_matches.sort(key=lambda m: m.confidence, reverse=True)

        # Determine if duplicate based on threshold
        is_duplicate = bool(duplicate_matches and duplicate_matches[0].confidence >= self.duplicate_threshold)

        # Get overall confidence (highest match or 0 if no matches)
        overall_confidence = duplicate_matches[0].confidence if duplicate_matches else 0.0

        logger.info(
            f"Deduplication check: {len(duplicate_matches)} potential matches found, "
            f"highest confidence: {overall_confidence:.1f}%, duplicate: {is_duplicate}"
        )

        return DeduplicationResult(
            is_duplicate=is_duplicate,
            confidence=overall_confidence,
            matches=duplicate_matches,
            threshold=self.duplicate_threshold,
            checked_fields=checked_fields
        )

    # ========== Field-Specific Matching Methods ==========

    async def _match_by_email(self, email: str) -> List[CRMContact]:
        """Find contacts with exact email match"""
        return self.db.query(CRMContact).filter(
            func.lower(CRMContact.email) == func.lower(email)
        ).all()

    async def _match_by_domain(self, domain: str) -> List[CRMContact]:
        """Find contacts with same email domain"""
        pattern = f"%@{domain}"
        return self.db.query(CRMContact).filter(
            CRMContact.email.ilike(pattern)
        ).all()

    async def _match_by_linkedin_url(self, linkedin_url: str) -> List[CRMContact]:
        """Find contacts with exact LinkedIn URL match"""
        # Normalize LinkedIn URLs (remove trailing slashes, convert to lowercase)
        normalized_url = linkedin_url.lower().rstrip('/')

        return self.db.query(CRMContact).filter(
            func.lower(func.rtrim(CRMContact.linkedin_url, '/')) == normalized_url
        ).all()

    async def _match_by_phone(self, normalized_phone: str) -> List[CRMContact]:
        """Find contacts with matching phone number (normalized)"""
        # Query contacts and filter in Python (phone normalization complex for SQL)
        all_contacts = self.db.query(CRMContact).filter(
            CRMContact.phone.isnot(None)
        ).all()

        matches = []
        for contact in all_contacts:
            if not contact.phone:
                continue
            
            contact_normalized = self._normalize_phone(contact.phone)
            
            # Direct match
            if contact_normalized == normalized_phone:
                matches.append(contact)
                continue
            
            # Handle US country code "1": try matching with/without it
            # Case 1: Contact has leading "1", query doesn't
            if contact_normalized.startswith('1') and len(contact_normalized) > len(normalized_phone):
                if contact_normalized[1:] == normalized_phone:
                    matches.append(contact)
                    continue
            
            # Case 2: Query has leading "1", contact doesn't
            if normalized_phone.startswith('1') and len(normalized_phone) > len(contact_normalized):
                if normalized_phone[1:] == contact_normalized:
                    matches.append(contact)
                    continue

        return matches

    async def _match_by_company_fuzzy(
        self,
        company_name: str,
        similarity_threshold: float = 0.7
    ) -> List[tuple[CRMContact, float]]:
        """
        Find contacts with similar company names using fuzzy matching.

        Returns:
            List of (contact, similarity_score) tuples
        """
        # Get all contacts with company names (limit to reasonable set for performance)
        contacts = self.db.query(CRMContact).filter(
            CRMContact.company.isnot(None)
        ).limit(1000).all()  # Limit for performance

        matches = []
        normalized_input = self._normalize_company_name(company_name)

        for contact in contacts:
            if not contact.company:
                continue

            normalized_contact = self._normalize_company_name(contact.company)
            similarity = self._calculate_levenshtein_similarity(normalized_input, normalized_contact)

            if similarity >= similarity_threshold:
                matches.append((contact, similarity))

        # Sort by similarity (highest first)
        matches.sort(key=lambda x: x[1], reverse=True)

        return matches

    # ========== Utility Methods ==========

    def _extract_domain(self, text: str) -> Optional[str]:
        """Extract domain from email or URL"""
        if not text:
            return None

        # Email: extract after @
        if '@' in text:
            return text.split('@')[-1].lower()

        # URL: extract domain
        match = re.search(r'(?:https?://)?(?:www\.)?([^/]+)', text)
        if match:
            return match.group(1).lower()

        return None

    def _normalize_phone(self, phone: str) -> str:
        """Normalize phone number to digits only"""
        if not phone:
            return ""
        # Remove all non-digit characters
        return re.sub(r'\D', '', phone)

    def _normalize_company_name(self, company: str) -> str:
        """Normalize company name for fuzzy matching"""
        if not company:
            return ""

        # Convert to lowercase
        normalized = company.lower()

        # Remove common suffixes using word boundaries
        suffixes = [
            'incorporated', 'corporation', 'technologies', 'technology',
            'solutions', 'enterprises', 'holdings', 'services',
            'limited', 'company', 'group', 'inc', 'corp', 'llc', 
            'ltd', 'co', 'tech'
        ]

        # Build regex pattern with word boundaries
        # Matches suffix at word boundary, optionally preceded by punctuation/space
        for suffix in suffixes:
            # Match: [space/comma/period][suffix][end/punctuation/space]
            pattern = rf'[\s,.]?\b{re.escape(suffix)}\b[\s,.]?'
            normalized = re.sub(pattern, ' ', normalized)

        # Remove punctuation except spaces
        normalized = re.sub(r'[^\w\s]', '', normalized)

        # Remove extra whitespace
        normalized = ' '.join(normalized.split())

        return normalized.strip()

    def _calculate_levenshtein_similarity(self, str1: str, str2: str) -> float:
        """
        Calculate similarity between two strings using Levenshtein distance.

        Returns:
            Similarity score between 0.0 and 1.0
        """
        if not str1 or not str2:
            return 0.0

        if str1 == str2:
            return 1.0

        # Calculate Levenshtein distance
        distance = self._levenshtein_distance(str1, str2)

        # Convert to similarity (0-1 scale)
        max_len = max(len(str1), len(str2))
        similarity = 1.0 - (distance / max_len)

        return max(0.0, similarity)  # Ensure non-negative

    def _levenshtein_distance(self, str1: str, str2: str) -> int:
        """Calculate Levenshtein distance between two strings"""
        if len(str1) < len(str2):
            return self._levenshtein_distance(str2, str1)

        if len(str2) == 0:
            return len(str1)

        previous_row = range(len(str2) + 1)
        for i, c1 in enumerate(str1):
            current_row = [i + 1]
            for j, c2 in enumerate(str2):
                # Cost of insertions, deletions, or substitutions
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row

        return previous_row[-1]


# ========== Factory Function ==========

def get_deduplication_engine(
    db: Session,
    threshold: float = DeduplicationEngine.DEFAULT_DUPLICATE_THRESHOLD
) -> DeduplicationEngine:
    """
    Factory function to create deduplication engine instance.

    Args:
        db: Database session
        threshold: Duplicate confidence threshold (default: 85%)

    Returns:
        Configured DeduplicationEngine instance
    """
    return DeduplicationEngine(db=db, duplicate_threshold=threshold)
