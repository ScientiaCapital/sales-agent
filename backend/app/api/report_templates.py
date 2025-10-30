"""
Report Templates API Endpoints

Provides endpoints for creating, managing, and generating custom analytics reports
with flexible query configurations and SQL injection prevention.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

from app.models.database import get_db
from app.models.report_template import ReportTemplate
from app.services.analytics.query_builder import QueryBuilder, QueryResult, QueryValidationError


router = APIRouter(prefix="/report-templates", tags=["Report Templates"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class FilterClauseSchema(BaseModel):
    """Filter clause for query configuration"""
    column: str = Field(..., min_length=1)
    operator: str = Field(..., pattern="^(=|!=|>|>=|<|<=|in|not_in|like|ilike|is_null|is_not_null)$")
    value: Optional[Any] = None


class AggregationSchema(BaseModel):
    """Aggregation specification"""
    function: str = Field(..., pattern="^(count|sum|avg|min|max|count_distinct)$")
    column: str = Field(..., min_length=1)
    alias: Optional[str] = None


class OrderClauseSchema(BaseModel):
    """Order by clause"""
    column: str = Field(..., min_length=1)
    direction: str = Field(default="asc", pattern="^(asc|desc)$")


class QueryConfigSchema(BaseModel):
    """Query configuration for report generation"""
    table: str = Field(..., min_length=1)
    columns: List[str] = Field(..., min_items=1)
    filters: Optional[List[FilterClauseSchema]] = None
    aggregations: Optional[List[AggregationSchema]] = None
    group_by: Optional[List[str]] = None
    order_by: Optional[List[OrderClauseSchema]] = None
    limit: Optional[int] = Field(default=100, ge=1, le=10000)


class VisualizationConfigSchema(BaseModel):
    """Visualization configuration for frontend rendering"""
    chart_type: str = Field(..., pattern="^(bar|line|pie|doughnut|scatter|table)$")
    x_axis: Optional[str] = None
    y_axis: Optional[str] = None
    series: Optional[List[str]] = None


class ReportTemplateCreate(BaseModel):
    """Schema for creating a new report template"""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    report_type: str = Field(
        ...,
        pattern="^(lead_analysis|campaign_performance|cost_summary|ab_test_results|custom)$"
    )
    query_config: QueryConfigSchema
    visualization_config: Optional[VisualizationConfigSchema] = None
    filter_config: Optional[Dict[str, Any]] = None


class ReportTemplateUpdate(BaseModel):
    """Schema for updating a report template"""
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    description: Optional[str] = None
    query_config: Optional[QueryConfigSchema] = None
    visualization_config: Optional[VisualizationConfigSchema] = None
    filter_config: Optional[Dict[str, Any]] = None


class ReportTemplateResponse(BaseModel):
    """Schema for report template response"""
    id: int
    template_id: str
    name: str
    description: Optional[str]
    report_type: str
    query_config: Dict[str, Any]
    visualization_config: Optional[Dict[str, Any]]
    filter_config: Optional[Dict[str, Any]]
    is_system_template: bool
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    usage_count: int

    class Config:
        from_attributes = True


class ReportGenerateRequest(BaseModel):
    """Schema for generating a report from template"""
    template_id: str = Field(..., min_length=1)
    filter_overrides: Optional[List[FilterClauseSchema]] = None
    limit_override: Optional[int] = Field(None, ge=1, le=10000)


class ReportGenerateResponse(BaseModel):
    """Schema for generated report response"""
    template_id: str
    template_name: str
    data: List[Dict[str, Any]]
    total_count: int
    execution_time_ms: float
    columns: List[str]
    generated_at: datetime


class QueryValidationRequest(BaseModel):
    """Schema for validating query configuration"""
    query_config: QueryConfigSchema


class QueryValidationResponse(BaseModel):
    """Schema for query validation response"""
    is_valid: bool
    error_message: Optional[str] = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "",
    response_model=ReportTemplateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new report template",
    description="Create a custom report template with flexible query configuration"
)
async def create_report_template(
    template_data: ReportTemplateCreate,
    db: Session = Depends(get_db)
) -> ReportTemplateResponse:
    """
    Create a new report template.

    The template will store query configuration for generating custom reports.
    Query config is validated before storage.
    """
    # Validate query configuration
    query_builder = QueryBuilder(db)
    is_valid, error_msg = query_builder.validate_query_config(template_data.query_config.dict())

    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid query configuration: {error_msg}"
        )

    # Generate unique template ID
    template_id = f"template_{uuid.uuid4().hex[:12]}"

    # Create template in database
    new_template = ReportTemplate(
        template_id=template_id,
        name=template_data.name,
        description=template_data.description,
        report_type=template_data.report_type,
        query_config=template_data.query_config.dict(),
        visualization_config=template_data.visualization_config.dict() if template_data.visualization_config else None,
        filter_config=template_data.filter_config,
        is_system_template=False,  # User templates are not system templates
        created_by=None  # TODO: Add user context when auth is implemented
    )

    db.add(new_template)
    db.commit()
    db.refresh(new_template)

    return new_template


@router.get(
    "",
    response_model=List[ReportTemplateResponse],
    summary="List all report templates",
    description="Get all report templates with optional filtering by type"
)
async def list_report_templates(
    report_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[ReportTemplateResponse]:
    """
    List all report templates.

    Supports filtering by report_type and pagination.
    """
    query = db.query(ReportTemplate)

    # Apply filters
    if report_type:
        query = query.filter(ReportTemplate.report_type == report_type)

    # Apply pagination
    templates = query.offset(skip).limit(limit).all()

    return templates


@router.get(
    "/{template_id}",
    response_model=ReportTemplateResponse,
    summary="Get a specific report template",
    description="Retrieve a report template by ID"
)
async def get_report_template(
    template_id: str,
    db: Session = Depends(get_db)
) -> ReportTemplateResponse:
    """Get a report template by template_id"""
    template = db.query(ReportTemplate).filter(
        ReportTemplate.template_id == template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report template not found: {template_id}"
        )

    return template


@router.put(
    "/{template_id}",
    response_model=ReportTemplateResponse,
    summary="Update a report template",
    description="Update an existing report template"
)
async def update_report_template(
    template_id: str,
    update_data: ReportTemplateUpdate,
    db: Session = Depends(get_db)
) -> ReportTemplateResponse:
    """
    Update an existing report template.

    Cannot update system templates.
    """
    template = db.query(ReportTemplate).filter(
        ReportTemplate.template_id == template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report template not found: {template_id}"
        )

    if template.is_system_template:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot update system templates"
        )

    # Validate new query config if provided
    if update_data.query_config:
        query_builder = QueryBuilder(db)
        is_valid, error_msg = query_builder.validate_query_config(update_data.query_config.dict())

        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid query configuration: {error_msg}"
            )

    # Update fields
    if update_data.name is not None:
        template.name = update_data.name
    if update_data.description is not None:
        template.description = update_data.description
    if update_data.query_config is not None:
        template.query_config = update_data.query_config.dict()
    if update_data.visualization_config is not None:
        template.visualization_config = update_data.visualization_config.dict()
    if update_data.filter_config is not None:
        template.filter_config = update_data.filter_config

    db.commit()
    db.refresh(template)

    return template


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a report template",
    description="Delete a report template by ID"
)
async def delete_report_template(
    template_id: str,
    db: Session = Depends(get_db)
) -> None:
    """
    Delete a report template.

    Cannot delete system templates.
    """
    template = db.query(ReportTemplate).filter(
        ReportTemplate.template_id == template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report template not found: {template_id}"
        )

    if template.is_system_template:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot delete system templates"
        )

    db.delete(template)
    db.commit()


@router.post(
    "/generate",
    response_model=ReportGenerateResponse,
    summary="Generate a report from template",
    description="Execute template query and return data"
)
async def generate_report_from_template(
    request: ReportGenerateRequest,
    db: Session = Depends(get_db)
) -> ReportGenerateResponse:
    """
    Generate a report from a template.

    Executes the template's query configuration with optional filter overrides.
    Increments template usage count.
    """
    # Get template
    template = db.query(ReportTemplate).filter(
        ReportTemplate.template_id == request.template_id
    ).first()

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report template not found: {request.template_id}"
        )

    # Build query config with overrides
    query_config = template.query_config.copy()

    if request.filter_overrides:
        # Merge filter overrides
        query_config['filters'] = [f.dict() for f in request.filter_overrides]

    if request.limit_override:
        query_config['limit'] = request.limit_override

    # Execute query
    try:
        query_builder = QueryBuilder(db)
        result = query_builder.build_and_execute(query_config)

        # Increment usage count
        template.usage_count += 1
        db.commit()

        return ReportGenerateResponse(
            template_id=template.template_id,
            template_name=template.name,
            data=result.data,
            total_count=result.total_count,
            execution_time_ms=result.execution_time_ms,
            columns=result.columns,
            generated_at=datetime.utcnow()
        )

    except QueryValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Query validation failed: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Report generation failed: {str(e)}"
        )


@router.post(
    "/validate",
    response_model=QueryValidationResponse,
    summary="Validate query configuration",
    description="Validate a query configuration without executing it"
)
async def validate_query_config(
    request: QueryValidationRequest,
    db: Session = Depends(get_db)
) -> QueryValidationResponse:
    """
    Validate a query configuration.

    Checks that table, columns, operators, and aggregations are valid
    without actually executing the query.
    """
    query_builder = QueryBuilder(db)
    is_valid, error_msg = query_builder.validate_query_config(request.query_config.dict())

    return QueryValidationResponse(
        is_valid=is_valid,
        error_message=error_msg
    )
