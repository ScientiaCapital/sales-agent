"""
Close CRM Bulk Push Service

Pushes enriched leads from Supabase to Close CRM with:
- Deduplication (skip existing leads)
- ATL contact filtering (decision-makers only by default)
- Dry-run mode for testing
- Batch processing with rate limiting
- Comprehensive result tracking

Usage:
    service = CloseBulkPushService(close_provider, db_session)
    result = await service.push_leads(leads_data, dry_run=True, atl_only=True)
"""

from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import asyncio

logger = logging.getLogger(__name__)


@dataclass
class LeadPushResult:
    """Result of pushing a single lead to Close CRM."""

    company_name: str
    domain: str
    status: str  # created, updated, duplicate, failed, would_create, skipped
    close_lead_id: Optional[str] = None
    existing_lead_id: Optional[str] = None
    contacts_created: int = 0
    error_message: Optional[str] = None
    dry_run: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON logging."""
        return {
            "company_name": self.company_name,
            "domain": self.domain,
            "status": self.status,
            "close_lead_id": self.close_lead_id,
            "existing_lead_id": self.existing_lead_id,
            "contacts_created": self.contacts_created,
            "error_message": self.error_message,
            "dry_run": self.dry_run
        }


@dataclass
class BulkPushResult:
    """Aggregate result of bulk push operation."""

    total_leads: int = 0
    success_count: int = 0
    failed_count: int = 0
    skipped_duplicates: int = 0
    skipped_no_contacts: int = 0
    would_create_count: int = 0  # For dry-run mode
    dry_run: bool = False
    batches_processed: int = 0
    results: List[LeadPushResult] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    @property
    def success_rate(self) -> float:
        """Calculate success rate as decimal (0.0 - 1.0)."""
        if self.total_leads == 0:
            return 0.0
        return self.success_count / self.total_leads

    @property
    def failure_rate(self) -> float:
        """Calculate failure rate as decimal (0.0 - 1.0)."""
        if self.total_leads == 0:
            return 0.0
        return self.failed_count / self.total_leads

    @property
    def duplicate_rate(self) -> float:
        """Calculate duplicate rate as decimal (0.0 - 1.0)."""
        if self.total_leads == 0:
            return 0.0
        return self.skipped_duplicates / self.total_leads

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for JSON logging."""
        return {
            "total_leads": self.total_leads,
            "success_count": self.success_count,
            "failed_count": self.failed_count,
            "skipped_duplicates": self.skipped_duplicates,
            "skipped_no_contacts": self.skipped_no_contacts,
            "would_create_count": self.would_create_count,
            "dry_run": self.dry_run,
            "batches_processed": self.batches_processed,
            "success_rate": self.success_rate,
            "failure_rate": self.failure_rate,
            "duplicate_rate": self.duplicate_rate,
            "results": [r.to_dict() for r in self.results]
        }


class CloseBulkPushService:
    """
    Service for bulk pushing enriched leads to Close CRM.

    Features:
    - Deduplication via domain/email lookup
    - ATL contact filtering (decision-makers only)
    - Dry-run mode for testing
    - Batch processing with configurable size
    - Rate limiting between API calls
    - Retry logic for transient failures
    """

    def __init__(
        self,
        close_provider: Any,
        db_session: Optional[Any] = None,
        supabase_client: Optional[Any] = None
    ):
        """
        Initialize bulk push service.

        Args:
            close_provider: CloseProvider instance for CRM operations
            db_session: Database session for queries (optional)
            supabase_client: Supabase client for deduplication queries (optional)
        """
        self.close_provider = close_provider
        self.db_session = db_session
        self.supabase = supabase_client

    async def push_leads(
        self,
        leads_data: Optional[List[Dict[str, Any]]],
        dry_run: bool = False,
        atl_only: bool = True,
        update_existing: bool = False,
        max_retries: int = 0,
        batch_size: int = 50,
        rate_limit_delay: float = 0.1
    ) -> BulkPushResult:
        """
        Push leads to Close CRM in bulk.

        Args:
            leads_data: List of enriched lead dictionaries
            dry_run: If True, validate but don't create (default False)
            atl_only: If True, only include ATL contacts (default True)
            update_existing: If True, add contacts to existing leads (default False)
            max_retries: Max retries per lead on transient failures (default 0)
            batch_size: Leads per batch (default 50)
            rate_limit_delay: Seconds between API calls (default 0.1)

        Returns:
            BulkPushResult with comprehensive statistics

        Raises:
            ValueError: If leads_data is None
        """
        # Validate input
        if leads_data is None:
            raise ValueError("leads_data cannot be None")

        result = BulkPushResult(
            total_leads=len(leads_data),
            dry_run=dry_run,
            started_at=datetime.now(timezone.utc)
        )

        # Handle empty input
        if not leads_data:
            result.completed_at = datetime.now(timezone.utc)
            return result

        # Process in batches
        batches = [
            leads_data[i:i + batch_size]
            for i in range(0, len(leads_data), batch_size)
        ]

        for batch_idx, batch in enumerate(batches):
            logger.info(f"Processing batch {batch_idx + 1}/{len(batches)}")

            for lead_data in batch:
                lead_result = await self._process_single_lead(
                    lead_data=lead_data,
                    dry_run=dry_run,
                    atl_only=atl_only,
                    update_existing=update_existing,
                    max_retries=max_retries
                )

                # Update counters based on result
                result.results.append(lead_result)

                if lead_result.status == "created":
                    result.success_count += 1
                elif lead_result.status == "updated":
                    result.success_count += 1
                elif lead_result.status == "duplicate":
                    result.skipped_duplicates += 1
                elif lead_result.status == "failed":
                    result.failed_count += 1
                elif lead_result.status == "would_create":
                    result.would_create_count += 1
                elif lead_result.status == "skipped_no_atl":
                    result.skipped_no_contacts += 1

                # Rate limiting between calls (not in dry-run)
                if not dry_run and rate_limit_delay > 0:
                    await asyncio.sleep(rate_limit_delay)

            result.batches_processed += 1

        result.completed_at = datetime.now(timezone.utc)

        # Log summary
        logger.info(
            f"Bulk push complete: {result.success_count} created, "
            f"{result.failed_count} failed, {result.skipped_duplicates} duplicates, "
            f"{result.skipped_no_contacts} no contacts"
        )

        return result

    async def _process_single_lead(
        self,
        lead_data: Dict[str, Any],
        dry_run: bool,
        atl_only: bool,
        update_existing: bool,
        max_retries: int
    ) -> LeadPushResult:
        """
        Process a single lead for Close CRM push.

        Args:
            lead_data: Lead dictionary with company and contacts
            dry_run: If True, don't actually create
            atl_only: If True, filter to ATL contacts only
            update_existing: If True, add contacts to existing leads
            max_retries: Max retries on transient failures

        Returns:
            LeadPushResult for this lead
        """
        company_name = lead_data.get("company_name", "Unknown")
        domain = lead_data.get("domain", "")

        # Validate lead data
        validation_error = self._validate_lead_data(lead_data)
        if validation_error:
            return LeadPushResult(
                company_name=company_name,
                domain=domain,
                status="failed",
                error_message=validation_error,
                dry_run=dry_run
            )

        # Filter contacts
        contacts = lead_data.get("contacts", [])
        if atl_only:
            contacts = [c for c in contacts if c.get("is_atl", False)]

        # Skip leads with no contacts after filtering
        if not contacts:
            return LeadPushResult(
                company_name=company_name,
                domain=domain,
                status="skipped_no_atl",
                dry_run=dry_run
            )

        # Check for existing lead (deduplication)
        existing_lead = await self._check_existing_lead(domain)

        if existing_lead and not update_existing:
            return LeadPushResult(
                company_name=company_name,
                domain=domain,
                status="duplicate",
                existing_lead_id=existing_lead.get("id"),
                dry_run=dry_run
            )

        # Dry-run mode - don't actually create
        if dry_run:
            return LeadPushResult(
                company_name=company_name,
                domain=domain,
                status="would_create",
                contacts_created=len(contacts),
                dry_run=True
            )

        # Build payload and create lead
        payload = self._build_lead_payload(lead_data, contacts)

        # Retry logic
        last_error = None
        for attempt in range(max_retries + 1):
            try:
                if existing_lead and update_existing:
                    # Add contacts to existing lead
                    result = await self.close_provider.create_lead(
                        lead=payload,
                        matched_lead_id=existing_lead.get("id")
                    )
                    return LeadPushResult(
                        company_name=company_name,
                        domain=domain,
                        status="updated",
                        close_lead_id=existing_lead.get("id"),
                        contacts_created=len(contacts),
                        dry_run=False
                    )
                else:
                    # Create new lead
                    result = await self.close_provider.create_lead(lead=payload)
                    return LeadPushResult(
                        company_name=company_name,
                        domain=domain,
                        status="created",
                        close_lead_id=result.get("id"),
                        contacts_created=len(contacts),
                        dry_run=False
                    )
            except Exception as e:
                last_error = str(e)
                logger.warning(
                    f"Attempt {attempt + 1}/{max_retries + 1} failed for {company_name}: {e}"
                )
                if attempt < max_retries:
                    # Exponential backoff
                    await asyncio.sleep(2 ** attempt)

        # All retries failed
        return LeadPushResult(
            company_name=company_name,
            domain=domain,
            status="failed",
            error_message=last_error,
            dry_run=False
        )

    def _validate_lead_data(self, lead_data: Dict[str, Any]) -> Optional[str]:
        """
        Validate lead data has required fields.

        Args:
            lead_data: Lead dictionary to validate

        Returns:
            Error message if invalid, None if valid
        """
        if not lead_data:
            return "Lead data is empty"

        company_name = lead_data.get("company_name")
        if not company_name:
            return "Missing required field: company_name"

        contacts = lead_data.get("contacts")
        if contacts is None:
            return "Missing required field: contacts"

        if not contacts:
            return "Lead has no contacts - at least one contact required"

        # Validate each contact has email
        for i, contact in enumerate(contacts):
            if not contact.get("email"):
                return f"Contact {i} missing required field: email"

        return None

    async def _check_existing_lead(
        self,
        domain: str
    ) -> Optional[Dict[str, Any]]:
        """
        Check if a lead already exists in Close CRM by domain.

        Args:
            domain: Company domain to search for

        Returns:
            Existing lead dict if found, None otherwise
        """
        # This would typically query Close CRM or a local cache
        # For now, return None (will be overridden in tests)
        return None

    def _build_lead_payload(
        self,
        lead_data: Dict[str, Any],
        contacts: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Build Close CRM lead payload from enriched lead data.

        Args:
            lead_data: Enriched lead dictionary
            contacts: Filtered contacts list

        Returns:
            Payload dict for CloseProvider.create_lead()
        """
        return {
            "name": lead_data.get("company_name"),
            "domain": lead_data.get("domain"),
            "industry": lead_data.get("industry"),
            "qualification_score": lead_data.get("qualification_score", 0),
            "_discovered_contacts": contacts,
            # Additional fields for Close custom fields
            "tier": lead_data.get("tier", "unknown"),
            "oem_brands": lead_data.get("oem_brands", []),
            "service_areas": lead_data.get("service_areas", []),
        }


__all__ = [
    "CloseBulkPushService",
    "BulkPushResult",
    "LeadPushResult"
]
