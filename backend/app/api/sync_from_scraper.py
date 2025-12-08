"""
Dealer Scraper Sync API

FastAPI endpoint for receiving batches of scraped contractors and contacts
from dealer-scraper-mvp's Celery push task.

Features:
- Batch contractor import with deduplication
- Contact import linked to companies
- Automatic source tracking (generac, enphase, etc.)
- OEM brand merging for existing companies
- Audit logging for all imports
- Sync status tracking

Endpoints:
- POST /contractors - Receive batch of scraped contractors
- POST /contacts - Receive batch of scraped contacts
- GET /status - Check sync status and last sync time
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator

from app.services.langgraph.tools.supabase_tools import get_supabase
from app.core.logging import setup_logging

logger = setup_logging(__name__)

router = APIRouter(prefix="/scraper", tags=["dealer-scraper"])


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class ScrapedContractor(BaseModel):
    """Contractor data from dealer-scraper-mvp."""

    company_name: str = Field(..., description="Company name as scraped")
    normalized_name: str = Field(..., description="Normalized name for deduplication")
    phone: Optional[str] = Field(None, description="Company phone number")
    email: Optional[str] = Field(None, description="Company email address")
    domain: Optional[str] = Field(None, description="Company website domain")
    state: str = Field(..., description="State abbreviation (e.g., TX, CA)")
    city: Optional[str] = Field(None, description="City name")
    address: Optional[str] = Field(None, description="Full address")
    zip_code: Optional[str] = Field(None, description="ZIP code")
    oem_brands: List[str] = Field(default_factory=list, description="List of OEM brands sold/installed")
    source_scraper: str = Field(..., description="Scraper source (generac, enphase, carrier, etc.)")
    certifications: List[str] = Field(default_factory=list, description="Certifications (NATE, etc.)")
    service_areas: List[str] = Field(default_factory=list, description="Cities/regions served")

    @field_validator('normalized_name', 'state', 'source_scraper')
    @classmethod
    def lowercase_fields(cls, v):
        """Ensure certain fields are lowercase."""
        return v.lower() if v else v

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "ABC HVAC & Plumbing",
                "normalized_name": "abc hvac plumbing",
                "phone": "5551234567",
                "email": "info@abchvac.com",
                "domain": "abchvac.com",
                "state": "tx",
                "city": "Austin",
                "oem_brands": ["Carrier", "Trane", "Lennox"],
                "source_scraper": "carrier",
                "certifications": ["NATE", "EPA Certified"],
                "service_areas": ["Austin", "Round Rock", "Cedar Park"]
            }
        }


class ScrapedContact(BaseModel):
    """Contact data from dealer-scraper-mvp."""

    company_name: str = Field(..., description="Company name (must match ScrapedContractor.company_name)")
    normalized_company_name: str = Field(..., description="Normalized company name for linking")
    full_name: str = Field(..., description="Contact full name")
    email: Optional[str] = Field(None, description="Contact email")
    phone: Optional[str] = Field(None, description="Contact direct phone")
    title: Optional[str] = Field(None, description="Job title")
    is_decision_maker: bool = Field(default=False, description="Is this an ATL decision maker?")
    source_scraper: str = Field(..., description="Scraper source (generac, enphase, etc.)")

    @field_validator('normalized_company_name', 'source_scraper')
    @classmethod
    def lowercase_fields(cls, v):
        """Ensure certain fields are lowercase."""
        return v.lower() if v else v

    class Config:
        json_schema_extra = {
            "example": {
                "company_name": "ABC HVAC & Plumbing",
                "normalized_company_name": "abc hvac plumbing",
                "full_name": "John Smith",
                "email": "john@abchvac.com",
                "phone": "5551234568",
                "title": "Owner",
                "is_decision_maker": True,
                "source_scraper": "carrier"
            }
        }


class ContractorBatchRequest(BaseModel):
    """Batch request for importing contractors."""

    contractors: List[ScrapedContractor] = Field(..., description="List of contractors to import")
    batch_id: Optional[str] = Field(None, description="Optional batch ID for tracking")
    source_scraper: str = Field(..., description="Scraper source (overrides individual records if needed)")

    class Config:
        json_schema_extra = {
            "example": {
                "contractors": [
                    {
                        "company_name": "ABC HVAC",
                        "normalized_name": "abc hvac",
                        "domain": "abchvac.com",
                        "state": "tx",
                        "oem_brands": ["Carrier"],
                        "source_scraper": "carrier"
                    }
                ],
                "batch_id": "carrier_batch_20251208",
                "source_scraper": "carrier"
            }
        }


class ContactBatchRequest(BaseModel):
    """Batch request for importing contacts."""

    contacts: List[ScrapedContact] = Field(..., description="List of contacts to import")
    batch_id: Optional[str] = Field(None, description="Optional batch ID for tracking")
    source_scraper: str = Field(..., description="Scraper source (overrides individual records if needed)")

    class Config:
        json_schema_extra = {
            "example": {
                "contacts": [
                    {
                        "company_name": "ABC HVAC",
                        "normalized_company_name": "abc hvac",
                        "full_name": "John Smith",
                        "email": "john@abchvac.com",
                        "title": "Owner",
                        "is_decision_maker": True,
                        "source_scraper": "carrier"
                    }
                ],
                "batch_id": "carrier_contacts_20251208",
                "source_scraper": "carrier"
            }
        }


class SyncStatusResponse(BaseModel):
    """Sync status response."""

    last_sync_at: Optional[str] = Field(None, description="Last sync timestamp")
    total_contractors_synced: int = Field(0, description="Total contractors synced (all time)")
    total_contacts_synced: int = Field(0, description="Total contacts synced (all time)")
    last_batch_id: Optional[str] = Field(None, description="Last batch ID processed")
    last_source_scraper: Optional[str] = Field(None, description="Last scraper source")


class ContractorSyncResponse(BaseModel):
    """Response for contractor batch sync."""

    status: str = Field(..., description="Success/error status")
    batch_id: Optional[str] = Field(None, description="Batch ID if provided")
    source_scraper: str = Field(..., description="Scraper source")
    total_received: int = Field(..., description="Total contractors in batch")
    inserted: int = Field(0, description="New contractors inserted")
    updated: int = Field(0, description="Existing contractors updated")
    skipped: int = Field(0, description="Contractors skipped")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Error details")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


class ContactSyncResponse(BaseModel):
    """Response for contact batch sync."""

    status: str = Field(..., description="Success/error status")
    batch_id: Optional[str] = Field(None, description="Batch ID if provided")
    source_scraper: str = Field(..., description="Scraper source")
    total_received: int = Field(..., description="Total contacts in batch")
    inserted: int = Field(0, description="New contacts inserted")
    updated: int = Field(0, description="Existing contacts updated")
    skipped: int = Field(0, description="Contacts skipped (no matching company)")
    errors: List[Dict[str, Any]] = Field(default_factory=list, description="Error details")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def normalize_phone(phone: Optional[str]) -> Optional[str]:
    """Normalize phone number to 10 digits."""
    if not phone:
        return None
    digits = ''.join(c for c in phone if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else None


def merge_oem_brands(existing: Optional[List[str]], new: List[str]) -> List[str]:
    """Merge OEM brands, removing duplicates."""
    if not existing:
        existing = []
    # Case-insensitive merge
    existing_lower = {b.lower(): b for b in existing}
    for brand in new:
        if brand.lower() not in existing_lower:
            existing_lower[brand.lower()] = brand
    return list(existing_lower.values())


def merge_service_areas(existing: Optional[List[str]], new: List[str]) -> List[str]:
    """Merge service areas, removing duplicates."""
    if not existing:
        existing = []
    # Case-insensitive merge
    existing_lower = {a.lower(): a for a in existing}
    for area in new:
        if area.lower() not in existing_lower:
            existing_lower[area.lower()] = area
    return list(existing_lower.values())


def log_to_audit(
    supabase,
    company_name: str,
    event_type: str,
    decision_data: dict,
    session_id: str = "dealer_scraper_sync"
) -> None:
    """Log import event to lead_audit_log table."""
    try:
        audit_entry = {
            "company_name": company_name,
            "session_id": session_id,
            "event_type": event_type,
            "stage": "import",
            "decision_data": decision_data,
            "created_by": "dealer_scraper_api",
            "created_at": datetime.now().isoformat()
        }
        supabase.table('lead_audit_log').insert(audit_entry).execute()
    except Exception as e:
        logger.warning(f"Failed to log audit entry for {company_name}: {e}")


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/contractors", response_model=ContractorSyncResponse)
async def sync_contractors(request: ContractorBatchRequest):
    """
    Receive batch of scraped contractors from dealer-scraper-mvp.

    Business Logic:
    1. Check if contractor exists by normalized_name OR phone OR domain
    2. If exists: Merge OEM brands and update other fields
    3. If new: Insert with source='dealer_scraper'
    4. Log all imports to lead_audit_log
    5. Return counts: inserted, updated, skipped

    Deduplication Strategy:
    - Match on normalized_name (primary)
    - Match on phone (if normalized_name doesn't match)
    - Match on domain (if phone doesn't match)

    Args:
        request: Batch of contractors with metadata

    Returns:
        Sync result with counts and errors
    """
    try:
        supabase = get_supabase()

        total_received = len(request.contractors)
        inserted = 0
        updated = 0
        skipped = 0
        errors = []

        # Get existing companies for deduplication (batch query)
        existing_result = supabase.table('dim_companies').select(
            'company_id, normalized_name, phone, domain, oem_brands, service_areas, certifications'
        ).execute()

        # Build lookup maps
        existing_by_norm_name = {}
        existing_by_phone = {}
        existing_by_domain = {}

        for company in existing_result.data:
            norm_name = company.get('normalized_name', '').lower()
            phone = normalize_phone(company.get('phone'))
            domain = company.get('domain', '').lower()

            if norm_name:
                existing_by_norm_name[norm_name] = company
            if phone:
                existing_by_phone[phone] = company
            if domain:
                existing_by_domain[domain] = company

        logger.info(f"Processing {total_received} contractors from {request.source_scraper}")

        # Process each contractor
        for contractor in request.contractors:
            try:
                # Normalize data
                norm_name = contractor.normalized_name.lower()
                norm_phone = normalize_phone(contractor.phone)
                norm_domain = contractor.domain.lower() if contractor.domain else None

                # Check if exists (3-way dedup)
                existing_company = None
                match_reason = None

                if norm_name and norm_name in existing_by_norm_name:
                    existing_company = existing_by_norm_name[norm_name]
                    match_reason = "normalized_name"
                elif norm_phone and norm_phone in existing_by_phone:
                    existing_company = existing_by_phone[norm_phone]
                    match_reason = "phone"
                elif norm_domain and norm_domain in existing_by_domain:
                    existing_company = existing_by_domain[norm_domain]
                    match_reason = "domain"

                if existing_company:
                    # UPDATE existing company
                    company_id = existing_company['company_id']

                    # Merge OEM brands and service areas
                    merged_oem = merge_oem_brands(
                        existing_company.get('oem_brands', []),
                        contractor.oem_brands
                    )
                    merged_areas = merge_service_areas(
                        existing_company.get('service_areas', []),
                        contractor.service_areas
                    )
                    merged_certs = list(set(
                        existing_company.get('certifications', []) + contractor.certifications
                    ))

                    update_data = {
                        'oem_brands': merged_oem,
                        'service_areas': merged_areas,
                        'certifications': merged_certs,
                        'source_scraper': request.source_scraper,
                        'last_enriched_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    }

                    # Update fields if they were empty before
                    if not existing_company.get('phone') and contractor.phone:
                        update_data['phone'] = contractor.phone
                    if not existing_company.get('domain') and contractor.domain:
                        update_data['domain'] = contractor.domain
                    if not existing_company.get('city') and contractor.city:
                        update_data['city'] = contractor.city
                    if contractor.address:
                        update_data['address'] = contractor.address
                    if contractor.zip_code:
                        update_data['zip_code'] = contractor.zip_code

                    supabase.table('dim_companies').update(update_data).eq('company_id', company_id).execute()

                    log_to_audit(
                        supabase,
                        contractor.company_name,
                        "updated",
                        {
                            "reason": f"Matched on {match_reason}",
                            "source_scraper": request.source_scraper,
                            "oem_brands_added": len(merged_oem) - len(existing_company.get('oem_brands', []))
                        },
                        session_id=request.batch_id or "dealer_scraper_sync"
                    )

                    updated += 1

                else:
                    # INSERT new company
                    import uuid

                    insert_data = {
                        'company_id': str(uuid.uuid4()),
                        'company_name': contractor.company_name,
                        'normalized_name': contractor.normalized_name,
                        'phone': contractor.phone,
                        'email': contractor.email,
                        'domain': contractor.domain,
                        'state': contractor.state,
                        'city': contractor.city,
                        'address': contractor.address,
                        'zip_code': contractor.zip_code,
                        'oem_brands': contractor.oem_brands,
                        'service_areas': contractor.service_areas,
                        'certifications': contractor.certifications,
                        'source': 'dealer_scraper',
                        'source_scraper': request.source_scraper,
                        'last_enriched_at': datetime.now().isoformat(),
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    }

                    supabase.table('dim_companies').insert(insert_data).execute()

                    log_to_audit(
                        supabase,
                        contractor.company_name,
                        "inserted",
                        {
                            "source_scraper": request.source_scraper,
                            "oem_brands": contractor.oem_brands,
                            "has_domain": bool(contractor.domain)
                        },
                        session_id=request.batch_id or "dealer_scraper_sync"
                    )

                    inserted += 1

            except Exception as e:
                logger.error(f"Error processing contractor {contractor.company_name}: {e}")
                errors.append({
                    "company_name": contractor.company_name,
                    "error": str(e)
                })
                skipped += 1

        logger.info(f"Contractor sync complete: {inserted} inserted, {updated} updated, {skipped} skipped")

        return ContractorSyncResponse(
            status="success" if not errors else "partial_success",
            batch_id=request.batch_id,
            source_scraper=request.source_scraper,
            total_received=total_received,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            errors=errors
        )

    except Exception as e:
        logger.error(f"Error syncing contractors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync contractors: {str(e)}")


@router.post("/contacts", response_model=ContactSyncResponse)
async def sync_contacts(request: ContactBatchRequest):
    """
    Receive batch of scraped contacts from dealer-scraper-mvp.

    Business Logic:
    1. Find matching company by normalized_company_name
    2. If no company match, skip contact (can't orphan)
    3. Check if contact exists by email or phone
    4. If exists: Update title and other fields
    5. If new: Insert linked to company_id
    6. Log all imports to lead_audit_log

    Args:
        request: Batch of contacts with metadata

    Returns:
        Sync result with counts and errors
    """
    try:
        supabase = get_supabase()

        total_received = len(request.contacts)
        inserted = 0
        updated = 0
        skipped = 0
        errors = []

        # Get existing companies for linking
        existing_companies = supabase.table('dim_companies').select(
            'company_id, normalized_name'
        ).execute()

        company_id_map = {
            c['normalized_name'].lower(): c['company_id']
            for c in existing_companies.data
            if c.get('normalized_name')
        }

        # Get existing contacts for deduplication
        existing_contacts = supabase.table('dim_contacts').select(
            'contact_id, company_id, email, phone, full_name'
        ).execute()

        # Build lookup map by (company_id, email) and (company_id, phone)
        existing_by_email = {}
        existing_by_phone = {}

        for contact in existing_contacts.data:
            company_id = contact.get('company_id')
            email = contact.get('email', '').lower()
            phone = normalize_phone(contact.get('phone'))

            if company_id and email:
                existing_by_email[(company_id, email)] = contact
            if company_id and phone:
                existing_by_phone[(company_id, phone)] = contact

        logger.info(f"Processing {total_received} contacts from {request.source_scraper}")

        # Process each contact
        for contact in request.contacts:
            try:
                # Find matching company
                norm_company = contact.normalized_company_name.lower()
                company_id = company_id_map.get(norm_company)

                if not company_id:
                    logger.warning(f"No company found for contact {contact.full_name} (company: {contact.company_name})")
                    errors.append({
                        "contact_name": contact.full_name,
                        "company_name": contact.company_name,
                        "error": "No matching company found"
                    })
                    skipped += 1
                    continue

                # Check if contact exists
                norm_email = contact.email.lower() if contact.email else None
                norm_phone = normalize_phone(contact.phone)

                existing_contact = None
                match_reason = None  # noqa: F841 - prepared for logging

                if norm_email and (company_id, norm_email) in existing_by_email:
                    existing_contact = existing_by_email[(company_id, norm_email)]
                    match_reason = "email"
                elif norm_phone and (company_id, norm_phone) in existing_by_phone:
                    existing_contact = existing_by_phone[(company_id, norm_phone)]
                    match_reason = "phone"

                if existing_contact:
                    # UPDATE existing contact
                    contact_id = existing_contact['contact_id']

                    update_data = {
                        'title': contact.title,
                        'is_decision_maker': contact.is_decision_maker,
                        'source_scraper': request.source_scraper,
                        'updated_at': datetime.now().isoformat()
                    }

                    # Update fields if they were empty before
                    if not existing_contact.get('phone') and contact.phone:
                        update_data['phone'] = contact.phone
                    if not existing_contact.get('email') and contact.email:
                        update_data['email'] = contact.email

                    supabase.table('dim_contacts').update(update_data).eq('contact_id', contact_id).execute()

                    updated += 1

                else:
                    # INSERT new contact
                    import uuid

                    insert_data = {
                        'contact_id': str(uuid.uuid4()),
                        'company_id': company_id,
                        'full_name': contact.full_name,
                        'email': contact.email,
                        'phone': contact.phone,
                        'title': contact.title,
                        'is_decision_maker': contact.is_decision_maker,
                        'source': 'dealer_scraper',
                        'source_scraper': request.source_scraper,
                        'created_at': datetime.now().isoformat(),
                        'updated_at': datetime.now().isoformat()
                    }

                    supabase.table('dim_contacts').insert(insert_data).execute()

                    inserted += 1

            except Exception as e:
                logger.error(f"Error processing contact {contact.full_name}: {e}")
                errors.append({
                    "contact_name": contact.full_name,
                    "company_name": contact.company_name,
                    "error": str(e)
                })
                skipped += 1

        logger.info(f"Contact sync complete: {inserted} inserted, {updated} updated, {skipped} skipped")

        return ContactSyncResponse(
            status="success" if not errors else "partial_success",
            batch_id=request.batch_id,
            source_scraper=request.source_scraper,
            total_received=total_received,
            inserted=inserted,
            updated=updated,
            skipped=skipped,
            errors=errors
        )

    except Exception as e:
        logger.error(f"Error syncing contacts: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to sync contacts: {str(e)}")


@router.get("/status", response_model=SyncStatusResponse)
async def get_sync_status():
    """
    Get sync status and last sync information.

    Returns:
        Last sync timestamp, total counts, and batch info
    """
    try:
        supabase = get_supabase()

        # Query audit log for last sync
        audit_result = supabase.table('lead_audit_log').select(
            'created_at, session_id, decision_data'
        ).eq(
            'created_by', 'dealer_scraper_api'
        ).order('created_at', desc=True).limit(1).execute()

        last_sync_at = None
        last_batch_id = None
        last_source_scraper = None

        if audit_result.data:
            last_entry = audit_result.data[0]
            last_sync_at = last_entry.get('created_at')
            last_batch_id = last_entry.get('session_id')
            decision_data = last_entry.get('decision_data', {})
            last_source_scraper = decision_data.get('source_scraper')

        # Count total contractors from dealer_scraper
        contractors_result = supabase.table('dim_companies').select(
            'company_id', count='exact'
        ).eq('source', 'dealer_scraper').execute()

        total_contractors = contractors_result.count or 0

        # Count total contacts from dealer_scraper
        contacts_result = supabase.table('dim_contacts').select(
            'contact_id', count='exact'
        ).eq('source', 'dealer_scraper').execute()

        total_contacts = contacts_result.count or 0

        return SyncStatusResponse(
            last_sync_at=last_sync_at,
            total_contractors_synced=total_contractors,
            total_contacts_synced=total_contacts,
            last_batch_id=last_batch_id,
            last_source_scraper=last_source_scraper
        )

    except Exception as e:
        logger.error(f"Error getting sync status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get sync status: {str(e)}")
