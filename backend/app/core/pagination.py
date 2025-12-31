"""Reusable pagination utilities for API endpoints.

Provides standardized pagination schemas and helpers for consistent API responses.

Usage:
    from app.core.pagination import PaginationParams, PaginatedResponse, paginate_query

    @router.get("/items", response_model=PaginatedResponse[ItemSchema])
    async def list_items(pagination: PaginationParams = Depends()):
        query = select(Item)
        return await paginate_query(query, pagination, db)
"""

from typing import Generic, TypeVar, List, Optional, Any
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for pagination."""

    limit: int = Field(
        default=50,
        ge=1,
        le=1000,
        description="Maximum number of items to return (1-1000)"
    )
    offset: int = Field(
        default=0,
        ge=0,
        description="Number of items to skip"
    )
    cursor: Optional[str] = Field(
        default=None,
        description="Cursor for cursor-based pagination (base64 encoded)"
    )

    @classmethod
    def from_query(cls, limit: int = 50, offset: int = 0, cursor: str = None):
        """Create from query parameters."""
        return cls(limit=min(limit, 1000), offset=max(offset, 0), cursor=cursor)


class PaginationMeta(BaseModel):
    """Pagination metadata included in responses."""

    total: int = Field(description="Total number of items")
    limit: int = Field(description="Items per page")
    offset: int = Field(description="Current offset")
    has_more: bool = Field(description="Whether more items exist")
    next_cursor: Optional[str] = Field(default=None, description="Cursor for next page")


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated response wrapper."""

    items: List[T] = Field(description="List of items for current page")
    pagination: PaginationMeta = Field(description="Pagination metadata")

    class Config:
        arbitrary_types_allowed = True


def create_pagination_meta(
    total: int,
    limit: int,
    offset: int,
    next_cursor: str = None
) -> PaginationMeta:
    """Create pagination metadata."""
    return PaginationMeta(
        total=total,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total,
        next_cursor=next_cursor
    )


async def paginate_query_async(
    query,
    pagination: PaginationParams,
    db: AsyncSession,
    count_query=None
) -> tuple[List[Any], PaginationMeta]:
    """
    Execute paginated query with async session.

    Args:
        query: SQLAlchemy select query
        pagination: Pagination parameters
        db: Async database session
        count_query: Optional custom count query

    Returns:
        Tuple of (items, pagination_meta)
    """
    # Get total count
    if count_query is None:
        count_query = select(func.count()).select_from(query.subquery())

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Apply pagination
    paginated_query = query.offset(pagination.offset).limit(pagination.limit)
    result = await db.execute(paginated_query)
    items = result.scalars().all()

    meta = create_pagination_meta(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset
    )

    return list(items), meta


def paginate_query_sync(
    query,
    pagination: PaginationParams,
    db: Session,
    count_query=None
) -> tuple[List[Any], PaginationMeta]:
    """
    Execute paginated query with sync session.

    Args:
        query: SQLAlchemy select query
        pagination: Pagination parameters
        db: Sync database session
        count_query: Optional custom count query

    Returns:
        Tuple of (items, pagination_meta)
    """
    # Get total count
    if count_query is None:
        count_query = select(func.count()).select_from(query.subquery())

    total = db.execute(count_query).scalar() or 0

    # Apply pagination
    paginated_query = query.offset(pagination.offset).limit(pagination.limit)
    items = db.execute(paginated_query).scalars().all()

    meta = create_pagination_meta(
        total=total,
        limit=pagination.limit,
        offset=pagination.offset
    )

    return list(items), meta


def paginate_list(
    items: List[T],
    total: int,
    limit: int = 50,
    offset: int = 0
) -> PaginatedResponse[T]:
    """
    Create paginated response from an already-fetched list.

    Useful when pagination is done at the data layer (e.g., Supabase).

    Args:
        items: List of items for current page
        total: Total count of all items
        limit: Items per page
        offset: Current offset

    Returns:
        PaginatedResponse with items and metadata
    """
    return PaginatedResponse(
        items=items,
        pagination=create_pagination_meta(total, limit, offset)
    )
