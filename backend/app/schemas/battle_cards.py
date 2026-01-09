"""
Pydantic schemas for Battle Cards API responses.
"""

from pydantic import BaseModel, Field
from typing import List, Optional


class CompetitorPricing(BaseModel):
    """Competitor pricing information."""
    model: str
    per_user: str = Field(alias="perUser")
    annual_10_users: str = Field(alias="annual10Users")

    class Config:
        populate_by_name = True


class KillerQuestion(BaseModel):
    """Sales killer question with expected answer."""
    question: str
    answer: str


class Competitor(BaseModel):
    """Full competitor battle card data."""
    id: str
    name: str
    tagline: str
    pricing: CompetitorPricing
    target_market: str = Field(alias="targetMarket")
    opener: str
    killer_question: KillerQuestion = Field(alias="killerQuestion")
    value_props: List[str] = Field(alias="valueProps")
    cant_do: List[str] = Field(alias="cantDo")
    coperniq_advantages: List[str] = Field(alias="coperniqAdvantages")

    class Config:
        populate_by_name = True


class Objection(BaseModel):
    """Sales objection handler."""
    id: str
    objection: str
    response: str


class AIFeature(BaseModel):
    """Coperniq AI feature for competitive positioning."""
    id: str
    name: str
    description: str
    examples: Optional[List[str]] = None
    roi: Optional[str] = None
    competitor_gap: str = Field(alias="competitorGap")

    class Config:
        populate_by_name = True


class AIEcosystemComparison(BaseModel):
    """AI ecosystem comparison with a specific competitor."""
    competitor: str
    limitation: str
    coperniq_advantage: str = Field(alias="coperniqAdvantage")

    class Config:
        populate_by_name = True


class AIEcosystemAdvantage(BaseModel):
    """Full AI ecosystem advantage data."""
    headline: str
    subheadline: str
    problem_with_bolted_on: List[str] = Field(alias="problemWithBoltedOn")
    coperniq_difference: List[str] = Field(alias="coperniqDifference")
    comparison: List[AIEcosystemComparison]
    key_message: str = Field(alias="keyMessage")

    class Config:
        populate_by_name = True


class SearchResult(BaseModel):
    """Search result from battle cards."""
    type: str  # "competitor", "objection", "ai_feature"
    id: str
    name: str
    match_context: str = Field(alias="matchContext")
    relevance_score: float = Field(alias="relevanceScore")

    class Config:
        populate_by_name = True


class BattleCardsHealthResponse(BaseModel):
    """Health check response."""
    status: str
    version: str
    data: dict
