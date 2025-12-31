"""
Accounts API - FastAPI router for account-based sales operations.

Endpoints:
- GET /api/v1/accounts/ - List accounts with pagination
- POST /api/v1/accounts/ - Create account (auto-group by domain)
- GET /api/v1/accounts/{id} - Get account with rollup metrics
- GET /api/v1/accounts/{id}/contacts - All contacts at account
- GET /api/v1/accounts/{id}/stakeholder-map - Decision maker analysis
- POST /api/v1/accounts/{id}/sequences - Multi-contact sequence
- POST /api/v1/accounts/group-by-domain - Auto-group companies
- PATCH /api/v1/accounts/{id}/stage - Update pipeline stage
"""
import logging
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import get_db
from app.models.account import Account, AccountStage
from app.services.account_service import AccountService
from app.core.pagination import (
    PaginationParams,
    PaginatedResponse,
    PaginationMeta,
    paginate_query_async,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/accounts", tags=["accounts"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class CreateAccountRequest(BaseModel):
    """Request to create a new account."""
    name: str = Field(min_length=1, max_length=255)
    domain: Optional[str] = Field(None, max_length=255)
    industry: Optional[str] = Field(None, max_length=100)
    employee_count: Optional[int] = Field(None, ge=0)


class AccountResponse(BaseModel):
    """Account response schema."""
    id: str
    name: str
    domain: Optional[str]
    industry: Optional[str]
    employee_count: Optional[int]
    total_contacts: int
    engaged_contacts: int
    total_activities: int
    stakeholder_score: Optional[float]
    engagement_rate: float
    account_stage: str
    deal_value: Optional[float]
    probability: Optional[float]
    weighted_deal_value: Optional[float]
    created_at: str
    updated_at: Optional[str]

    class Config:
        from_attributes = True


class ContactResponse(BaseModel):
    """Contact response for account endpoints."""
    id: str
    name: Optional[str]
    email: Optional[str]
    title: Optional[str]
    phone: Optional[str]
    linkedin_url: Optional[str]
    is_atl: bool
    confidence: Optional[float]
    company_name: Optional[str]
    company_id: Optional[str]


class AccountContactsResponse(BaseModel):
    """Response for account contacts endpoint."""
    account: AccountResponse
    contacts: List[ContactResponse]
    contact_count: int
    atl_count: int


class StakeholderStats(BaseModel):
    """Statistics for a stakeholder group."""
    total: int
    engaged: int
    replied: int
    engagement_rate: float


class StakeholderGroup(BaseModel):
    """Stakeholder group with contacts and stats."""
    contacts: List[dict]
    stats: StakeholderStats


class StakeholderMapResponse(BaseModel):
    """Response for stakeholder map endpoint."""
    account_id: str
    atl: StakeholderGroup
    non_atl: StakeholderGroup
    stakeholder_score: Optional[float]


class UpdateStageRequest(BaseModel):
    """Request to update account stage."""
    stage: AccountStage
    deal_value: Optional[float] = None
    probability: Optional[float] = Field(None, ge=0, le=1)


class GroupByDomainRequest(BaseModel):
    """Request for domain grouping operation."""
    dry_run: bool = Field(default=True, description="Preview without making changes")


class GroupByDomainResponse(BaseModel):
    """Response for domain grouping operation."""
    dry_run: bool
    accounts_created: Optional[int] = None
    companies_grouped: Optional[int] = None
    domains_processed: Optional[int] = None
    domains_found: Optional[int] = None
    companies_to_group: Optional[int] = None
    domain_breakdown: Optional[dict] = None
    errors: Optional[List[dict]] = None


class CreateSequenceRequest(BaseModel):
    """Request to create multi-contact sequence."""
    sequence_id: str = Field(min_length=1, max_length=50)
    contact_ids: Optional[List[str]] = None
    include_atl_only: bool = Field(default=False)
    mailbox_id: int


class SequenceCreationResponse(BaseModel):
    """Response for sequence creation."""
    account_id: str
    sequence_id: str
    entries_created: int
    contacts_enrolled: List[str]


class RollupMetricsResponse(BaseModel):
    """Response for rollup metrics update."""
    account_id: str
    total_contacts: int
    engaged_contacts: int
    total_activities: int
    stakeholder_score: Optional[float]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.get("/", response_model=PaginatedResponse[AccountResponse])
async def list_accounts(
    stage: Optional[AccountStage] = Query(None, description="Filter by stage"),
    industry: Optional[str] = Query(None, description="Filter by industry"),
    min_contacts: Optional[int] = Query(None, ge=0, description="Min contacts"),
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """
    List accounts with pagination and filtering.

    Supports filtering by:
    - stage: Pipeline stage
    - industry: Industry classification
    - min_contacts: Minimum contact count
    """
    try:
        query = select(Account)

        # Apply filters
        if stage:
            query = query.where(Account.account_stage == stage.value)
        if industry:
            query = query.where(Account.industry == industry)
        if min_contacts:
            query = query.where(Account.total_contacts >= min_contacts)

        query = query.order_by(Account.created_at.desc())

        # Paginate
        pagination = PaginationParams(limit=limit, offset=offset)
        items, meta = await paginate_query_async(query, pagination, db)

        # Convert to response models
        account_responses = [
            AccountResponse(
                id=str(acc.id),
                name=acc.name,
                domain=acc.domain,
                industry=acc.industry,
                employee_count=acc.employee_count,
                total_contacts=acc.total_contacts,
                engaged_contacts=acc.engaged_contacts,
                total_activities=acc.total_activities,
                stakeholder_score=acc.stakeholder_score,
                engagement_rate=acc.engagement_rate,
                account_stage=acc.account_stage,
                deal_value=float(acc.deal_value) if acc.deal_value else None,
                probability=acc.probability,
                weighted_deal_value=acc.weighted_deal_value,
                created_at=acc.created_at.isoformat(),
                updated_at=acc.updated_at.isoformat() if acc.updated_at else None,
            )
            for acc in items
        ]

        return PaginatedResponse(items=account_responses, pagination=meta)

    except Exception as e:
        logger.error(f"Failed to list accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    request: CreateAccountRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create a new account.

    If domain is provided, will check for existing account with same domain
    and return it instead of creating a duplicate.
    """
    try:
        service = AccountService(db)
        account = await service.create_account(
            name=request.name,
            domain=request.domain,
            industry=request.industry,
            employee_count=request.employee_count,
        )

        return AccountResponse(
            id=str(account.id),
            name=account.name,
            domain=account.domain,
            industry=account.industry,
            employee_count=account.employee_count,
            total_contacts=account.total_contacts,
            engaged_contacts=account.engaged_contacts,
            total_activities=account.total_activities,
            stakeholder_score=account.stakeholder_score,
            engagement_rate=account.engagement_rate,
            account_stage=account.account_stage,
            deal_value=float(account.deal_value) if account.deal_value else None,
            probability=account.probability,
            weighted_deal_value=account.weighted_deal_value,
            created_at=account.created_at.isoformat(),
            updated_at=account.updated_at.isoformat() if account.updated_at else None,
        )

    except Exception as e:
        logger.error(f"Failed to create account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get account by ID with current rollup metrics."""
    try:
        service = AccountService(db)
        account = await service.get_account_by_id(account_id)

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        return AccountResponse(
            id=str(account.id),
            name=account.name,
            domain=account.domain,
            industry=account.industry,
            employee_count=account.employee_count,
            total_contacts=account.total_contacts,
            engaged_contacts=account.engaged_contacts,
            total_activities=account.total_activities,
            stakeholder_score=account.stakeholder_score,
            engagement_rate=account.engagement_rate,
            account_stage=account.account_stage,
            deal_value=float(account.deal_value) if account.deal_value else None,
            probability=account.probability,
            weighted_deal_value=account.weighted_deal_value,
            created_at=account.created_at.isoformat(),
            updated_at=account.updated_at.isoformat() if account.updated_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get account: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}/contacts", response_model=AccountContactsResponse)
async def get_account_contacts(
    account_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get all contacts associated with an account."""
    try:
        service = AccountService(db)
        result = await service.get_account_with_contacts(account_id)

        if not result:
            raise HTTPException(status_code=404, detail="Account not found")

        return AccountContactsResponse(
            account=AccountResponse(**result["account"]),
            contacts=[ContactResponse(**c) for c in result["contacts"]],
            contact_count=result["contact_count"],
            atl_count=result["atl_count"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get account contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{account_id}/stakeholder-map", response_model=StakeholderMapResponse)
async def get_stakeholder_map(
    account_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """
    Get stakeholder breakdown for account.

    Returns ATL (decision makers) vs non-ATL contacts with engagement status.
    Useful for account-based selling strategy.
    """
    try:
        service = AccountService(db)
        result = await service.get_stakeholder_map(account_id)

        if not result:
            raise HTTPException(status_code=404, detail="Account not found")

        return StakeholderMapResponse(
            account_id=result["account_id"],
            atl=StakeholderGroup(
                contacts=result["atl"]["contacts"],
                stats=StakeholderStats(**result["atl"]["stats"]),
            ),
            non_atl=StakeholderGroup(
                contacts=result["non_atl"]["contacts"],
                stats=StakeholderStats(**result["non_atl"]["stats"]),
            ),
            stakeholder_score=result["stakeholder_score"],
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get stakeholder map: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/sequences", response_model=SequenceCreationResponse)
async def create_account_sequence(
    account_id: UUID,
    request: CreateSequenceRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Create sequence entries for multiple contacts at an account.

    Creates sequence entries for all contacts (or ATL-only if specified).
    This is the primary method for account-based multi-stakeholder engagement.
    """
    try:
        from app.services.sequences.engine import SequenceEngine
        from app.models.sequence_entry import SequenceEntry
        from app.models.sequence import Sequence

        service = AccountService(db)
        account_data = await service.get_account_with_contacts(account_id)

        if not account_data:
            raise HTTPException(status_code=404, detail="Account not found")

        # Get sequence
        seq_query = select(Sequence).where(
            Sequence.sequence_id == request.sequence_id
        )
        result = await db.execute(seq_query)
        sequence = result.scalar_one_or_none()

        if not sequence:
            raise HTTPException(
                status_code=404,
                detail=f"Sequence '{request.sequence_id}' not found"
            )

        # Filter contacts
        contacts = account_data["contacts"]
        if request.contact_ids:
            contacts = [c for c in contacts if str(c["id"]) in request.contact_ids]
        elif request.include_atl_only:
            contacts = [c for c in contacts if c.get("is_atl")]

        if not contacts:
            raise HTTPException(
                status_code=400,
                detail="No eligible contacts found for sequence"
            )

        # Create sequence entries for each contact
        engine = SequenceEngine(db)
        enrolled = []

        for contact in contacts:
            try:
                result = await engine.enroll_prospect(
                    prospect_email=contact["email"],
                    sequence_id=request.sequence_id,
                    mailbox_id=request.mailbox_id,
                    company_name=contact.get("company_name"),
                    first_name=contact.get("name", "").split()[0] if contact.get("name") else None,
                )
                if result.get("success"):
                    enrolled.append(contact["email"])
            except Exception as e:
                logger.warning(f"Failed to enroll {contact['email']}: {e}")

        # Update account to link to sequence
        account = await service.get_account_by_id(account_id)
        if hasattr(sequence, 'account_id'):
            sequence.account_id = account_id
            await db.commit()

        return SequenceCreationResponse(
            account_id=str(account_id),
            sequence_id=request.sequence_id,
            entries_created=len(enrolled),
            contacts_enrolled=enrolled,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to create account sequence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/group-by-domain", response_model=GroupByDomainResponse)
async def group_companies_by_domain(
    request: GroupByDomainRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Auto-group companies by domain into accounts.

    Use dry_run=true to preview what would be created without making changes.
    """
    try:
        service = AccountService(db)
        result = await service.group_by_domain(dry_run=request.dry_run)
        return GroupByDomainResponse(**result)

    except Exception as e:
        logger.error(f"Failed to group by domain: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{account_id}/stage", response_model=AccountResponse)
async def update_account_stage(
    account_id: UUID,
    request: UpdateStageRequest,
    db: AsyncSession = Depends(get_db)
):
    """Update account pipeline stage and deal details."""
    try:
        service = AccountService(db)
        account = await service.get_account_by_id(account_id)

        if not account:
            raise HTTPException(status_code=404, detail="Account not found")

        account.account_stage = request.stage.value
        if request.deal_value is not None:
            account.deal_value = request.deal_value
        if request.probability is not None:
            account.probability = request.probability

        await db.commit()
        await db.refresh(account)

        return AccountResponse(
            id=str(account.id),
            name=account.name,
            domain=account.domain,
            industry=account.industry,
            employee_count=account.employee_count,
            total_contacts=account.total_contacts,
            engaged_contacts=account.engaged_contacts,
            total_activities=account.total_activities,
            stakeholder_score=account.stakeholder_score,
            engagement_rate=account.engagement_rate,
            account_stage=account.account_stage,
            deal_value=float(account.deal_value) if account.deal_value else None,
            probability=account.probability,
            weighted_deal_value=account.weighted_deal_value,
            created_at=account.created_at.isoformat(),
            updated_at=account.updated_at.isoformat() if account.updated_at else None,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update account stage: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{account_id}/refresh-metrics", response_model=RollupMetricsResponse)
async def refresh_account_metrics(
    account_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Recalculate rollup metrics for an account."""
    try:
        service = AccountService(db)
        result = await service.update_rollup_metrics(account_id)
        return RollupMetricsResponse(**result)

    except Exception as e:
        logger.error(f"Failed to refresh metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
