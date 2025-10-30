"""
A/B Test Analytics API Endpoints

Provides endpoints for creating, analyzing, and managing A/B tests
with statistical significance testing.
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from datetime import datetime

from app.models.database import get_db
from app.models.analytics_models import AnalyticsABTest
from app.services.analytics.ab_test_service import ABTestAnalyticsService, ABTestAnalysis


router = APIRouter(prefix="/ab-tests", tags=["A/B Tests"])


# ============================================================================
# Pydantic Schemas
# ============================================================================

class ABTestCreate(BaseModel):
    """Schema for creating a new A/B test"""
    test_name: str = Field(..., min_length=1, max_length=200)
    test_description: Optional[str] = None
    variant_a_name: str = Field(..., min_length=1, max_length=100)
    variant_b_name: str = Field(..., min_length=1, max_length=100)
    test_type: str = Field(default="campaign", pattern="^(campaign|agent_performance|ui_element)$")
    campaign_id: Optional[int] = None
    segment_filters: Optional[dict] = None


class ABTestUpdate(BaseModel):
    """Schema for updating A/B test metrics"""
    participants_a: Optional[int] = Field(None, ge=0)
    participants_b: Optional[int] = Field(None, ge=0)
    conversions_a: Optional[int] = Field(None, ge=0)
    conversions_b: Optional[int] = Field(None, ge=0)


class ABTestStopRequest(BaseModel):
    """Schema for stopping an A/B test"""
    reason: Optional[str] = Field(None, max_length=500)


class ABTestResponse(BaseModel):
    """Schema for A/B test response"""
    id: int
    test_id: str
    test_name: str
    test_description: Optional[str]
    variant_a_name: str
    variant_b_name: str
    test_type: str
    status: str
    participants_a: int
    participants_b: int
    conversions_a: int
    conversions_b: int
    conversion_rate_a: Optional[float]
    conversion_rate_b: Optional[float]
    statistical_significance: Optional[float]  # p-value
    confidence_level: Optional[float]
    winner: Optional[str]
    start_date: Optional[datetime]
    end_date: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class ABTestAnalysisResponse(BaseModel):
    """Schema for statistical analysis response"""
    test_id: str
    test_name: str

    # Variant A
    variant_a_name: str
    variant_a_conversions: int
    variant_a_participants: int
    variant_a_conversion_rate: float
    variant_a_confidence_interval: tuple[float, float]

    # Variant B
    variant_b_name: str
    variant_b_conversions: int
    variant_b_participants: int
    variant_b_conversion_rate: float
    variant_b_confidence_interval: tuple[float, float]

    # Statistical significance
    p_value: float
    chi_square_statistic: float
    is_significant: bool
    confidence_level: float

    # Winner
    winner: Optional[str]
    lift_percentage: float

    # Sample adequacy
    minimum_sample_size: int
    sample_adequacy: float
    can_stop_early: bool

    # Recommendations
    recommendations: List[str]
    days_remaining_estimate: Optional[int]


class EarlyStoppingResponse(BaseModel):
    """Schema for early stopping recommendation"""
    can_stop: bool
    confidence: float
    sample_adequacy: float
    is_significant: bool
    winner: Optional[str]
    lift_percentage: float
    recommendation: Optional[str]


# ============================================================================
# API Endpoints
# ============================================================================

@router.post(
    "",
    response_model=ABTestResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new A/B test",
    description="Create a formal A/B test with statistical tracking"
)
async def create_ab_test(
    test_data: ABTestCreate,
    db: Session = Depends(get_db)
) -> ABTestResponse:
    """
    Create a new A/B test.

    The test will track participants and conversions for two variants,
    calculate statistical significance, and provide recommendations.
    """
    # Generate unique test ID
    import uuid
    test_id = f"test_{uuid.uuid4().hex[:8]}"

    # Create test in database
    new_test = AnalyticsABTest(
        test_id=test_id,
        test_name=test_data.test_name,
        test_description=test_data.test_description,
        variant_a_name=test_data.variant_a_name,
        variant_b_name=test_data.variant_b_name,
        test_type=test_data.test_type,
        status="draft",
        test_config={
            "campaign_id": test_data.campaign_id,
            "segment_filters": test_data.segment_filters
        }
    )

    db.add(new_test)
    db.commit()
    db.refresh(new_test)

    return ABTestResponse.model_validate(new_test)


@router.get(
    "/{test_id}",
    response_model=ABTestResponse,
    summary="Get A/B test details",
    description="Retrieve A/B test configuration and current metrics"
)
async def get_ab_test(
    test_id: str,
    db: Session = Depends(get_db)
) -> ABTestResponse:
    """Get A/B test by ID"""
    test = db.query(AnalyticsABTest).filter(
        AnalyticsABTest.test_id == test_id
    ).first()

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test '{test_id}' not found"
        )

    return ABTestResponse.model_validate(test)


@router.get(
    "/{test_id}/analysis",
    response_model=ABTestAnalysisResponse,
    summary="Get statistical analysis",
    description="Get comprehensive statistical analysis with significance testing"
)
async def get_ab_test_analysis(
    test_id: str,
    db: Session = Depends(get_db)
) -> ABTestAnalysisResponse:
    """
    Get statistical analysis for an A/B test.

    Includes:
    - Chi-square significance testing
    - Confidence intervals for each variant
    - Winner determination
    - Sample size adequacy
    - Recommendations
    """
    service = ABTestAnalyticsService(db)

    try:
        analysis = service.analyze_ab_test(test_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    return ABTestAnalysisResponse(
        test_id=analysis.test_id,
        test_name=analysis.test_name,
        variant_a_name=analysis.variant_a_name,
        variant_a_conversions=analysis.variant_a_conversions,
        variant_a_participants=analysis.variant_a_participants,
        variant_a_conversion_rate=analysis.variant_a_conversion_rate,
        variant_a_confidence_interval=analysis.variant_a_confidence_interval,
        variant_b_name=analysis.variant_b_name,
        variant_b_conversions=analysis.variant_b_conversions,
        variant_b_participants=analysis.variant_b_participants,
        variant_b_conversion_rate=analysis.variant_b_conversion_rate,
        variant_b_confidence_interval=analysis.variant_b_confidence_interval,
        p_value=analysis.p_value,
        chi_square_statistic=analysis.chi_square_statistic,
        is_significant=analysis.is_significant,
        confidence_level=analysis.confidence_level,
        winner=analysis.winner,
        lift_percentage=analysis.lift_percentage,
        minimum_sample_size=analysis.minimum_sample_size,
        sample_adequacy=analysis.sample_adequacy,
        can_stop_early=analysis.can_stop_early,
        recommendations=analysis.recommendations,
        days_remaining_estimate=analysis.days_remaining_estimate
    )


@router.patch(
    "/{test_id}",
    response_model=ABTestResponse,
    summary="Update A/B test metrics",
    description="Update participant and conversion counts"
)
async def update_ab_test(
    test_id: str,
    update_data: ABTestUpdate,
    db: Session = Depends(get_db)
) -> ABTestResponse:
    """Update A/B test metrics"""
    test = db.query(AnalyticsABTest).filter(
        AnalyticsABTest.test_id == test_id
    ).first()

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test '{test_id}' not found"
        )

    # Update provided fields
    if update_data.participants_a is not None:
        test.participants_a = update_data.participants_a
    if update_data.participants_b is not None:
        test.participants_b = update_data.participants_b
    if update_data.conversions_a is not None:
        test.conversions_a = update_data.conversions_a
    if update_data.conversions_b is not None:
        test.conversions_b = update_data.conversions_b

    # Calculate conversion rates
    if test.participants_a > 0:
        test.conversion_rate_a = (test.conversions_a / test.participants_a) * 100
    if test.participants_b > 0:
        test.conversion_rate_b = (test.conversions_b / test.participants_b) * 100

    db.commit()
    db.refresh(test)

    return ABTestResponse.model_validate(test)


@router.post(
    "/{test_id}/start",
    response_model=ABTestResponse,
    summary="Start A/B test",
    description="Activate an A/B test"
)
async def start_ab_test(
    test_id: str,
    db: Session = Depends(get_db)
) -> ABTestResponse:
    """Start an A/B test"""
    test = db.query(AnalyticsABTest).filter(
        AnalyticsABTest.test_id == test_id
    ).first()

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test '{test_id}' not found"
        )

    if test.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start test with status '{test.status}'"
        )

    test.status = "running"
    test.start_date = datetime.utcnow()

    db.commit()
    db.refresh(test)

    return ABTestResponse.model_validate(test)


@router.post(
    "/{test_id}/stop",
    response_model=ABTestAnalysisResponse,
    summary="Stop A/B test",
    description="Stop test and get final statistical analysis"
)
async def stop_ab_test(
    test_id: str,
    stop_request: Optional[ABTestStopRequest] = None,
    db: Session = Depends(get_db)
) -> ABTestAnalysisResponse:
    """
    Stop an A/B test and return final analysis.

    Updates test status to 'completed' and performs final statistical analysis.
    """
    test = db.query(AnalyticsABTest).filter(
        AnalyticsABTest.test_id == test_id
    ).first()

    if not test:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"A/B test '{test_id}' not found"
        )

    if test.status not in ["running", "paused"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot stop test with status '{test.status}'"
        )

    # Perform final analysis
    service = ABTestAnalyticsService(db)
    analysis = service.analyze_ab_test(test_id)

    # Update test status
    test.status = "completed"
    test.end_date = datetime.utcnow()
    test.winner = analysis.winner
    test.statistical_significance = analysis.p_value
    test.confidence_level = analysis.confidence_level

    db.commit()

    return ABTestAnalysisResponse(
        test_id=analysis.test_id,
        test_name=analysis.test_name,
        variant_a_name=analysis.variant_a_name,
        variant_a_conversions=analysis.variant_a_conversions,
        variant_a_participants=analysis.variant_a_participants,
        variant_a_conversion_rate=analysis.variant_a_conversion_rate,
        variant_a_confidence_interval=analysis.variant_a_confidence_interval,
        variant_b_name=analysis.variant_b_name,
        variant_b_conversions=analysis.variant_b_conversions,
        variant_b_participants=analysis.variant_b_participants,
        variant_b_conversion_rate=analysis.variant_b_conversion_rate,
        variant_b_confidence_interval=analysis.variant_b_confidence_interval,
        p_value=analysis.p_value,
        chi_square_statistic=analysis.chi_square_statistic,
        is_significant=analysis.is_significant,
        confidence_level=analysis.confidence_level,
        winner=analysis.winner,
        lift_percentage=analysis.lift_percentage,
        minimum_sample_size=analysis.minimum_sample_size,
        sample_adequacy=analysis.sample_adequacy,
        can_stop_early=analysis.can_stop_early,
        recommendations=analysis.recommendations,
        days_remaining_estimate=analysis.days_remaining_estimate
    )


@router.get(
    "/{test_id}/recommendations",
    response_model=EarlyStoppingResponse,
    summary="Get early stopping recommendations",
    description="Check if test can be stopped early based on statistical significance"
)
async def get_early_stopping_recommendations(
    test_id: str,
    db: Session = Depends(get_db)
) -> EarlyStoppingResponse:
    """
    Get recommendations for early stopping.

    Determines if the test has reached statistical significance
    with adequate sample size to make a confident decision.
    """
    service = ABTestAnalyticsService(db)

    try:
        result = service.detect_early_stopping_opportunity(test_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

    return EarlyStoppingResponse(**result)


@router.get(
    "",
    response_model=List[ABTestResponse],
    summary="List all A/B tests",
    description="Get all A/B tests with optional filtering"
)
async def list_ab_tests(
    status_filter: Optional[str] = None,
    test_type: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db)
) -> List[ABTestResponse]:
    """List all A/B tests with optional filtering"""
    query = db.query(AnalyticsABTest)

    if status_filter:
        query = query.filter(AnalyticsABTest.status == status_filter)

    if test_type:
        query = query.filter(AnalyticsABTest.test_type == test_type)

    tests = query.offset(skip).limit(limit).all()

    return [ABTestResponse.model_validate(test) for test in tests]
