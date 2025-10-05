"""
Multi-factor lead scoring service for intelligent lead qualification
"""
import logging
from typing import Dict, Any, Optional, List, Tuple
from pydantic import BaseModel, Field, validator
import numpy as np
from datetime import datetime, timedelta

from app.core.logging import setup_logging

logger = setup_logging(__name__)


class ScoringWeights(BaseModel):
    """Configurable scoring weights for different factors"""
    company_size: float = Field(default=0.30, ge=0, le=1.0, description="Weight for company size factor")
    industry: float = Field(default=0.25, ge=0, le=1.0, description="Weight for industry factor")
    signals: float = Field(default=0.45, ge=0, le=1.0, description="Weight for buying signals factor")

    @validator('*')
    def validate_weight_sum(cls, v, values):
        """Ensure weights sum to 1.0"""
        if len(values) == 2:  # All three values are set
            total = sum(values.values()) + v
            if not (0.99 <= total <= 1.01):  # Allow small floating point errors
                raise ValueError(f"Weights must sum to 1.0, got {total}")
        return v

    model_config = {
        "json_schema_extra": {
            "example": {
                "company_size": 0.30,
                "industry": 0.25,
                "signals": 0.45
            }
        }
    }


class SignalData(BaseModel):
    """Buying signals and intent indicators"""
    recent_funding: Optional[bool] = Field(None, description="Recent funding round (<6 months)")
    funding_amount_millions: Optional[float] = Field(None, ge=0, description="Funding amount in millions")
    employee_growth_rate: Optional[float] = Field(None, description="YoY employee growth rate")
    tech_stack_modern: Optional[bool] = Field(None, description="Uses modern tech stack")
    cloud_adoption: Optional[bool] = Field(None, description="Has cloud infrastructure")
    website_traffic_rank: Optional[int] = Field(None, ge=1, description="Global website traffic rank")
    content_downloads: Optional[int] = Field(None, ge=0, description="Number of content downloads")
    demo_requested: Optional[bool] = Field(None, description="Has requested product demo")
    competitor_customer: Optional[bool] = Field(None, description="Currently uses competitor product")
    expansion_planned: Optional[bool] = Field(None, description="Planning expansion/growth")

    model_config = {
        "json_schema_extra": {
            "example": {
                "recent_funding": True,
                "funding_amount_millions": 10.5,
                "employee_growth_rate": 0.25,
                "tech_stack_modern": True,
                "demo_requested": False
            }
        }
    }


class ScoringResult(BaseModel):
    """Lead scoring result with confidence metrics"""
    score: float = Field(..., ge=0, le=100, description="Overall lead score (0-100)")
    confidence: float = Field(..., ge=0, le=1.0, description="Confidence level in the score (0-1)")
    factors: Dict[str, float] = Field(..., description="Individual factor scores")
    reasoning: str = Field(..., description="Human-readable explanation of the score")
    recommendations: List[str] = Field(default_factory=list, description="Recommended actions")
    tier: str = Field(..., description="Lead tier classification (A/B/C/D)")

    model_config = {
        "json_schema_extra": {
            "example": {
                "score": 78.5,
                "confidence": 0.85,
                "factors": {
                    "company_size": 80.0,
                    "industry": 75.0,
                    "signals": 79.0
                },
                "reasoning": "High-value lead with strong buying signals and good company fit",
                "recommendations": ["Prioritize for immediate outreach", "Schedule executive demo"],
                "tier": "A"
            }
        }
    }


class LeadScorer:
    """Multi-factor lead scoring engine with industry-specific logic"""

    def __init__(self, weights: Optional[ScoringWeights] = None):
        """
        Initialize the lead scorer with configurable weights

        Args:
            weights: Custom scoring weights (defaults to standard weights)
        """
        self.weights = weights or ScoringWeights()

        # Industry-specific multipliers (higher = better fit)
        self.industry_multipliers = {
            "SaaS": 1.2,
            "Software": 1.2,
            "Enterprise Software": 1.15,
            "FinTech": 1.1,
            "Financial Services": 1.1,
            "HealthTech": 1.1,
            "Healthcare": 1.05,
            "E-commerce": 1.0,
            "Retail": 0.95,
            "Manufacturing": 0.9,
            "Construction": 0.85,
            "Non-profit": 0.7
        }

        # Company size scoring (employees)
        self.size_scores = {
            "1-10": 40,
            "11-50": 60,
            "51-200": 75,
            "201-500": 85,
            "501-1000": 90,
            "1000+": 95,
            "1001-5000": 95,
            "5000+": 100,
            "Enterprise": 100
        }

        # Default/unknown values
        self.default_industry_multiplier = 1.0
        self.default_size_score = 50

        logger.info("LeadScorer initialized with weights: %s", self.weights.dict())

    def calculate_score(
        self,
        lead_data: Dict[str, Any],
        signals: Optional[SignalData] = None
    ) -> ScoringResult:
        """
        Calculate weighted lead score with confidence intervals

        Args:
            lead_data: Dictionary containing lead information
            signals: Optional buying signals data

        Returns:
            ScoringResult with score, confidence, and breakdown
        """
        # Extract lead fields
        company_size = lead_data.get('company_size')
        industry = lead_data.get('industry')

        # Calculate individual factor scores
        size_score = self.get_size_score(company_size)
        industry_score = self.get_industry_score(industry)
        signals_score = self.analyze_signals(signals) if signals else 50.0

        # Apply weights to calculate final score
        weighted_score = (
            size_score * self.weights.company_size +
            industry_score * self.weights.industry +
            signals_score * self.weights.signals
        )

        # Calculate confidence based on data completeness
        confidence = self._calculate_confidence(
            has_size=company_size is not None,
            has_industry=industry is not None,
            has_signals=signals is not None,
            signals_completeness=self._get_signals_completeness(signals) if signals else 0
        )

        # Generate tier classification
        tier = self._classify_tier(weighted_score)

        # Generate reasoning
        reasoning = self._generate_reasoning(
            score=weighted_score,
            size_score=size_score,
            industry_score=industry_score,
            signals_score=signals_score,
            company_size=company_size,
            industry=industry,
            tier=tier
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            score=weighted_score,
            tier=tier,
            signals=signals,
            industry=industry
        )

        return ScoringResult(
            score=round(weighted_score, 1),
            confidence=round(confidence, 2),
            factors={
                "company_size": round(size_score, 1),
                "industry": round(industry_score, 1),
                "signals": round(signals_score, 1)
            },
            reasoning=reasoning,
            recommendations=recommendations,
            tier=tier
        )

    def get_industry_score(self, industry: Optional[str]) -> float:
        """
        Get industry-specific score with multiplier

        Args:
            industry: Industry name

        Returns:
            Score from 0-100 based on industry fit
        """
        if not industry:
            logger.debug("No industry provided, using default score")
            return 50.0  # Medium score for unknown

        # Normalize industry name for matching
        industry_normalized = industry.strip().title()

        # Check for exact match first
        if industry_normalized in self.industry_multipliers:
            multiplier = self.industry_multipliers[industry_normalized]
        else:
            # Check for partial matches
            multiplier = self.default_industry_multiplier
            for key, value in self.industry_multipliers.items():
                if key.lower() in industry.lower() or industry.lower() in key.lower():
                    multiplier = value
                    break

        # Convert multiplier to 0-100 score
        # 1.2x multiplier = 100 score, 0.7x = 35 score
        base_score = 70  # Base score for 1.0x multiplier
        score = base_score * multiplier

        # Cap at 0-100 range
        return min(max(score, 0), 100)

    def get_size_score(self, company_size: Optional[str]) -> float:
        """
        Get company size score

        Args:
            company_size: Company size range

        Returns:
            Score from 0-100 based on company size
        """
        if not company_size:
            logger.debug("No company size provided, using default score")
            return self.default_size_score

        # Direct lookup
        if company_size in self.size_scores:
            return float(self.size_scores[company_size])

        # Try to parse numeric ranges
        size_normalized = company_size.strip().lower()

        # Check for keywords
        if 'enterprise' in size_normalized or 'large' in size_normalized:
            return 100.0
        elif 'medium' in size_normalized or 'mid' in size_normalized:
            return 75.0
        elif 'small' in size_normalized or 'startup' in size_normalized:
            return 50.0

        # Try to extract numbers
        import re
        numbers = re.findall(r'\d+', company_size)
        if numbers:
            # Get the larger number as employee count
            max_employees = max(map(int, numbers))
            if max_employees <= 10:
                return 40.0
            elif max_employees <= 50:
                return 60.0
            elif max_employees <= 200:
                return 75.0
            elif max_employees <= 500:
                return 85.0
            elif max_employees <= 1000:
                return 90.0
            else:
                return 95.0

        return self.default_size_score

    def analyze_signals(self, signals: Optional[SignalData]) -> float:
        """
        Analyze buying signals and intent indicators

        Args:
            signals: SignalData with various buying signals

        Returns:
            Score from 0-100 based on signal strength
        """
        if not signals:
            return 50.0  # Default medium score

        signal_scores = []
        signal_weights = []

        # Recent funding (very strong signal)
        if signals.recent_funding is not None:
            score = 90 if signals.recent_funding else 40
            if signals.funding_amount_millions:
                # Adjust based on funding size
                if signals.funding_amount_millions >= 50:
                    score = min(score + 10, 100)
                elif signals.funding_amount_millions >= 10:
                    score = min(score + 5, 100)
            signal_scores.append(score)
            signal_weights.append(2.0)  # High weight

        # Employee growth (strong signal)
        if signals.employee_growth_rate is not None:
            if signals.employee_growth_rate >= 0.5:  # 50%+ growth
                score = 95
            elif signals.employee_growth_rate >= 0.2:  # 20%+ growth
                score = 80
            elif signals.employee_growth_rate >= 0:  # Positive growth
                score = 60
            else:  # Negative growth
                score = 30
            signal_scores.append(score)
            signal_weights.append(1.5)

        # Tech stack modernization (moderate signal)
        if signals.tech_stack_modern is not None:
            score = 75 if signals.tech_stack_modern else 40
            signal_scores.append(score)
            signal_weights.append(1.0)

        # Cloud adoption (moderate signal)
        if signals.cloud_adoption is not None:
            score = 70 if signals.cloud_adoption else 45
            signal_scores.append(score)
            signal_weights.append(1.0)

        # Website traffic (weak signal)
        if signals.website_traffic_rank:
            if signals.website_traffic_rank <= 10000:
                score = 90
            elif signals.website_traffic_rank <= 100000:
                score = 70
            elif signals.website_traffic_rank <= 1000000:
                score = 50
            else:
                score = 30
            signal_scores.append(score)
            signal_weights.append(0.5)

        # Demo requested (very strong signal)
        if signals.demo_requested is not None:
            score = 95 if signals.demo_requested else 50
            signal_scores.append(score)
            signal_weights.append(2.5)  # Highest weight

        # Content engagement (moderate signal)
        if signals.content_downloads is not None:
            if signals.content_downloads >= 10:
                score = 85
            elif signals.content_downloads >= 5:
                score = 70
            elif signals.content_downloads >= 1:
                score = 60
            else:
                score = 40
            signal_scores.append(score)
            signal_weights.append(1.0)

        # Competitor customer (strong signal)
        if signals.competitor_customer is not None:
            score = 85 if signals.competitor_customer else 50
            signal_scores.append(score)
            signal_weights.append(1.5)

        # Expansion planned (strong signal)
        if signals.expansion_planned is not None:
            score = 80 if signals.expansion_planned else 50
            signal_scores.append(score)
            signal_weights.append(1.5)

        # Calculate weighted average
        if signal_scores:
            total_weight = sum(signal_weights)
            weighted_sum = sum(s * w for s, w in zip(signal_scores, signal_weights))
            return weighted_sum / total_weight

        return 50.0  # Default if no signals

    def _calculate_confidence(
        self,
        has_size: bool,
        has_industry: bool,
        has_signals: bool,
        signals_completeness: float
    ) -> float:
        """
        Calculate confidence based on data completeness and quality

        Args:
            has_size: Whether company size is provided
            has_industry: Whether industry is provided
            has_signals: Whether any signals are provided
            signals_completeness: Percentage of signals filled (0-1)

        Returns:
            Confidence score from 0 to 1
        """
        # Base confidence from data presence
        data_points = sum([has_size, has_industry, has_signals])

        if data_points == 3:
            # All data present
            base_confidence = 0.85
            # Adjust based on signal completeness
            confidence = base_confidence + (0.15 * signals_completeness)
        elif data_points == 2:
            # Two factors present
            base_confidence = 0.65
            if has_signals:
                confidence = base_confidence + (0.15 * signals_completeness)
            else:
                confidence = base_confidence
        elif data_points == 1:
            # Only one factor
            base_confidence = 0.40
            if has_signals:
                confidence = base_confidence + (0.20 * signals_completeness)
            else:
                confidence = base_confidence
        else:
            # No data (shouldn't happen in practice)
            confidence = 0.25

        return min(confidence, 1.0)

    def _get_signals_completeness(self, signals: Optional[SignalData]) -> float:
        """
        Calculate how complete the signals data is

        Args:
            signals: SignalData object

        Returns:
            Completeness ratio from 0 to 1
        """
        if not signals:
            return 0.0

        # Count non-None fields
        fields = [
            signals.recent_funding,
            signals.funding_amount_millions,
            signals.employee_growth_rate,
            signals.tech_stack_modern,
            signals.cloud_adoption,
            signals.website_traffic_rank,
            signals.content_downloads,
            signals.demo_requested,
            signals.competitor_customer,
            signals.expansion_planned
        ]

        filled = sum(1 for f in fields if f is not None)
        total = len(fields)

        return filled / total if total > 0 else 0.0

    def _classify_tier(self, score: float) -> str:
        """
        Classify lead into tier based on score

        Args:
            score: Overall lead score (0-100)

        Returns:
            Tier classification (A/B/C/D)
        """
        if score >= 80:
            return "A"
        elif score >= 65:
            return "B"
        elif score >= 50:
            return "C"
        else:
            return "D"

    def _generate_reasoning(
        self,
        score: float,
        size_score: float,
        industry_score: float,
        signals_score: float,
        company_size: Optional[str],
        industry: Optional[str],
        tier: str
    ) -> str:
        """
        Generate human-readable reasoning for the score

        Args:
            score: Overall score
            size_score: Company size factor score
            industry_score: Industry factor score
            signals_score: Signals factor score
            company_size: Company size description
            industry: Industry name
            tier: Lead tier

        Returns:
            Reasoning text explaining the score
        """
        tier_desc = {
            "A": "high-priority",
            "B": "strong",
            "C": "moderate",
            "D": "low-priority"
        }

        reasoning_parts = [f"This is a {tier_desc[tier]} lead (Tier {tier}) with a score of {score:.1f}/100."]

        # Company size analysis
        if company_size:
            if size_score >= 80:
                reasoning_parts.append(f"The company size ({company_size}) indicates excellent market fit.")
            elif size_score >= 60:
                reasoning_parts.append(f"The company size ({company_size}) shows good potential.")
            else:
                reasoning_parts.append(f"The company size ({company_size}) suggests limited immediate opportunity.")

        # Industry analysis
        if industry:
            if industry_score >= 80:
                reasoning_parts.append(f"The {industry} industry is a prime target market.")
            elif industry_score >= 60:
                reasoning_parts.append(f"The {industry} industry has moderate alignment.")
            else:
                reasoning_parts.append(f"The {industry} industry has lower priority.")

        # Signals analysis
        if signals_score >= 80:
            reasoning_parts.append("Strong buying signals indicate high purchase intent.")
        elif signals_score >= 60:
            reasoning_parts.append("Moderate buying signals suggest active interest.")
        elif signals_score < 50:
            reasoning_parts.append("Limited buying signals detected.")

        return " ".join(reasoning_parts)

    def _generate_recommendations(
        self,
        score: float,
        tier: str,
        signals: Optional[SignalData],
        industry: Optional[str]
    ) -> List[str]:
        """
        Generate actionable recommendations based on the score

        Args:
            score: Overall lead score
            tier: Lead tier classification
            signals: Buying signals data
            industry: Industry name

        Returns:
            List of recommended actions
        """
        recommendations = []

        # Tier-based recommendations
        if tier == "A":
            recommendations.append("🎯 Prioritize for immediate outreach")
            recommendations.append("📞 Schedule executive-level demo within 48 hours")
            recommendations.append("💼 Assign to senior sales representative")

            if signals and signals.demo_requested:
                recommendations.append("⚡ Fast-track demo scheduling - buyer intent detected")
            if signals and signals.competitor_customer:
                recommendations.append("🔄 Prepare competitive displacement strategy")

        elif tier == "B":
            recommendations.append("📧 Add to active nurture campaign")
            recommendations.append("📅 Schedule discovery call within 1 week")
            recommendations.append("📊 Gather additional qualification data")

            if signals and signals.expansion_planned:
                recommendations.append("📈 Focus on scalability in messaging")

        elif tier == "C":
            recommendations.append("✉️ Add to standard email sequence")
            recommendations.append("📚 Share educational content")
            recommendations.append("🔍 Monitor for buying signals")

        else:  # Tier D
            recommendations.append("📨 Add to long-term nurture list")
            recommendations.append("📡 Set up automated engagement tracking")

        # Industry-specific recommendations
        if industry and "tech" in industry.lower():
            recommendations.append("🔧 Emphasize technical capabilities and integrations")
        elif industry and "finance" in industry.lower():
            recommendations.append("🔒 Highlight security and compliance features")
        elif industry and "health" in industry.lower():
            recommendations.append("⚕️ Focus on HIPAA compliance and patient outcomes")

        return recommendations[:5]  # Limit to 5 recommendations


class LeadScorerFactory:
    """Factory for creating lead scorers with different configurations"""

    @staticmethod
    def create_default() -> LeadScorer:
        """Create a scorer with default weights"""
        return LeadScorer()

    @staticmethod
    def create_enterprise_focused() -> LeadScorer:
        """Create a scorer optimized for enterprise leads"""
        weights = ScoringWeights(
            company_size=0.40,  # Higher weight on size
            industry=0.20,
            signals=0.40
        )
        return LeadScorer(weights)

    @staticmethod
    def create_signal_focused() -> LeadScorer:
        """Create a scorer that prioritizes buying signals"""
        weights = ScoringWeights(
            company_size=0.20,
            industry=0.20,
            signals=0.60  # Higher weight on signals
        )
        return LeadScorer(weights)

    @staticmethod
    def create_industry_focused() -> LeadScorer:
        """Create a scorer that prioritizes industry fit"""
        weights = ScoringWeights(
            company_size=0.25,
            industry=0.40,  # Higher weight on industry
            signals=0.35
        )
        return LeadScorer(weights)