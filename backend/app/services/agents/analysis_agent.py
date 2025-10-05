"""
AnalysisAgent for strategic analysis and opportunity identification

Consumes research data from SearchAgent and generates:
- Strategic insights
- Engagement opportunities
- Personalized recommendations
- Engagement strategies
"""

import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator

from app.services.llm_router import LLMRouter, RoutingStrategy
from app.core.exceptions import ValidationError
from .search_agent import CompanyResearch

logger = logging.getLogger(__name__)


class OpportunityItem(BaseModel):
    """Individual engagement opportunity"""
    type: str  # e.g., "product_fit", "timing", "competitive_advantage"
    description: str
    priority: str  # "high", "medium", "low"
    confidence: float = Field(ge=0.0, le=1.0)
    recommended_action: Optional[str] = None


class StrategicInsights(BaseModel):
    """Strategic analysis results"""
    company_name: str
    key_insights: List[str] = Field(default_factory=list)
    opportunities: List[OpportunityItem] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    engagement_strategy: str
    competitive_positioning: Optional[str] = None
    urgency_score: float = Field(ge=0.0, le=1.0)
    confidence_score: float = Field(ge=0.0, le=1.0)
    analysis_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_cost: float = 0.0
    
    @validator('urgency_score', 'confidence_score')
    def validate_scores(cls, v):
        """Ensure scores are between 0 and 1"""
        return max(0.0, min(1.0, v))


class AnalysisAgent:
    """
    AI agent for strategic analysis and opportunity identification
    
    Analyzes research data to generate actionable insights and engagement strategies.
    Uses quality-optimized routing for high-quality analysis.
    """
    
    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        routing_strategy: RoutingStrategy = RoutingStrategy.QUALITY_OPTIMIZED
    ):
        """
        Initialize AnalysisAgent
        
        Args:
            llm_router: LLMRouter instance (creates new if not provided)
            routing_strategy: Strategy for LLM routing (default: QUALITY_OPTIMIZED for best analysis)
        """
        self.llm_router = llm_router or LLMRouter(strategy=routing_strategy)
        
    async def analyze_research(
        self,
        research: CompanyResearch,
        lead_context: Optional[Dict[str, Any]] = None
    ) -> StrategicInsights:
        """
        Generate strategic insights from research data
        
        Args:
            research: CompanyResearch object from SearchAgent
            lead_context: Additional context about the lead (qualification score, contact info, etc.)
            
        Returns:
            StrategicInsights object with actionable recommendations
        """
        if lead_context is None:
            lead_context = {}
            
        # Build comprehensive analysis prompt
        analysis_prompt = self._build_analysis_prompt(research, lead_context)
        
        try:
            # Use quality-optimized routing for high-quality analysis
            result = await self.llm_router.generate(
                prompt=analysis_prompt,
                temperature=0.4,  # Moderate creativity for insights
                max_tokens=1200
            )            
            # Parse insights from LLM output
            insights_data = self._parse_insights(result.get("result", "{}"))
            
            # Calculate confidence score for analysis
            confidence = self._calculate_analysis_confidence(insights_data, research)
            
            # Calculate urgency score based on growth signals and opportunities
            urgency = self._calculate_urgency_score(research, insights_data)
            
            # Create StrategicInsights object
            insights = StrategicInsights(
                company_name=research.company_name,
                key_insights=insights_data.get("key_insights", []),
                opportunities=insights_data.get("opportunities", []),
                recommendations=insights_data.get("recommendations", []),
                engagement_strategy=insights_data.get("engagement_strategy", ""),
                competitive_positioning=insights_data.get("competitive_positioning"),
                urgency_score=urgency,
                confidence_score=confidence,
                total_cost=result.get("total_cost", 0.0)
            )
            
            logger.info(
                f"Completed analysis for {research.company_name} - "
                f"Confidence: {confidence:.2%}, Urgency: {urgency:.2%}, "
                f"Opportunities: {len(insights.opportunities)}"
            )
            
            return insights
            
        except Exception as e:
            logger.error(f"Failed to analyze research for {research.company_name}: {e}")
            # Return minimal insights on error
            return StrategicInsights(
                company_name=research.company_name,
                key_insights=["Analysis failed - manual review required"],
                opportunities=[],
                recommendations=[],
                engagement_strategy="Manual review recommended due to analysis failure",
                urgency_score=0.5,
                confidence_score=0.0
            )    
    def _build_analysis_prompt(
        self,
        research: CompanyResearch,
        context: Dict[str, Any]
    ) -> str:
        """
        Build comprehensive analysis prompt
        
        Args:
            research: CompanyResearch data
            context: Additional lead context
            
        Returns:
            Formatted analysis prompt
        """
        # Format research data for prompt
        news_summary = "\n".join([
            f"- {item.title}: {item.summary} ({item.date})"
            for item in research.news[:5]
        ]) if research.news else "No recent news found"
        
        funding_summary = ""
        if research.funding:
            funding_summary = f"""
Funding: {research.funding.round_type} - {research.funding.amount}
Investors: {', '.join(research.funding.investors[:3]) if research.funding.investors else 'N/A'}
Date: {research.funding.date}
"""
        else:
            funding_summary = "No funding information available"
        
        tech_stack_summary = ", ".join(research.tech_stack[:10]) if research.tech_stack else "Unknown"
        pain_points_summary = "\n".join([f"- {pp}" for pp in research.pain_points]) if research.pain_points else "None identified"
        growth_signals_summary = "\n".join([f"- {gs}" for gs in research.growth_signals]) if research.growth_signals else "None detected"
        competitors_summary = ", ".join(research.competitors[:5]) if research.competitors else "Unknown"        
        prompt = f"""
You are a strategic sales analyst. Analyze the following company research data and provide actionable insights.

COMPANY: {research.company_name}
INDUSTRY: {research.industry or 'Unknown'}

RECENT NEWS:
{news_summary}

FUNDING INFORMATION:
{funding_summary}

TECHNOLOGY STACK:
{tech_stack_summary}

PAIN POINTS:
{pain_points_summary}

GROWTH SIGNALS:
{growth_signals_summary}

COMPETITORS:
{competitors_summary}

LEAD CONTEXT:
- Industry: {context.get('industry', 'N/A')}
- Company Size: {context.get('company_size', 'N/A')}
- Qualification Score: {context.get('qualification_score', 'N/A')}
- Contact Title: {context.get('contact_title', 'N/A')}

Provide strategic analysis in this EXACT JSON format:
{{
    "key_insights": [
        "Insight 1: Brief strategic insight about the company",
        "Insight 2: Another key finding",
        "Insight 3: Market positioning or trend observation"
    ],
    "opportunities": [
        {{
            "type": "product_fit|timing|competitive_advantage|pain_point_match",
            "description": "Specific opportunity description",
            "priority": "high|medium|low",
            "confidence": 0.0-1.0,
            "recommended_action": "Specific action to take"
        }}
    ],
    "recommendations": [
        "Recommendation 1: Specific outreach approach",
        "Recommendation 2: Value proposition to emphasize",
        "Recommendation 3: Timing or channel suggestion"
    ],
    "engagement_strategy": "2-3 paragraph personalized engagement strategy covering approach, messaging, and next steps",
    "competitive_positioning": "How to position against competitors (optional)"
}}

Focus on:
1. Strategic insights that reveal opportunities
2. Prioritized opportunities ranked by potential impact
3. Actionable recommendations for outreach
4. Personalized engagement strategy
5. Competitive differentiation

Return ONLY valid JSON, no other text.
"""
        return prompt    
    def _parse_insights(self, llm_output: str) -> Dict[str, Any]:
        """
        Parse LLM output into structured insights
        
        Args:
            llm_output: Raw LLM response
            
        Returns:
            Parsed insights data
        """
        try:
            # Try to parse as JSON
            data = json.loads(llm_output)
            
            # Convert opportunity dicts to OpportunityItem objects
            if "opportunities" in data:
                opportunities = []
                for opp in data["opportunities"]:
                    try:
                        opportunities.append(OpportunityItem(**opp))
                    except Exception as e:
                        logger.warning(f"Failed to parse opportunity: {e}")
                data["opportunities"] = opportunities
            
            # Ensure required fields exist
            data.setdefault("key_insights", [])
            data.setdefault("opportunities", [])
            data.setdefault("recommendations", [])
            data.setdefault("engagement_strategy", "")
            
            return data
            
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse insights JSON: {e}")
            # Return minimal structure
            return {
                "key_insights": ["Analysis parsing failed - manual review required"],
                "opportunities": [],
                "recommendations": [],
                "engagement_strategy": "Manual analysis recommended"
            }    
    def _calculate_analysis_confidence(
        self,
        insights: Dict[str, Any],
        research: CompanyResearch
    ) -> float:
        """
        Calculate confidence score for analysis
        
        Args:
            insights: Parsed insights data
            research: Original research data
            
        Returns:
            Confidence score between 0 and 1
        """
        score = 0.0
        
        # Base confidence from research quality
        score += research.confidence * 0.40
        
        # Key insights contribute 20%
        if insights.get("key_insights"):
            score += min(len(insights["key_insights"]) / 3, 1.0) * 0.20
            
        # Opportunities contribute 20%
        if insights.get("opportunities"):
            score += min(len(insights["opportunities"]) / 3, 1.0) * 0.20
            
        # Recommendations contribute 10%
        if insights.get("recommendations"):
            score += min(len(insights["recommendations"]) / 3, 1.0) * 0.10
            
        # Engagement strategy contributes 10%
        if insights.get("engagement_strategy") and len(insights["engagement_strategy"]) > 100:
            score += 0.10
            
        return min(score, 1.0)
    
    def _calculate_urgency_score(
        self,
        research: CompanyResearch,
        insights: Dict[str, Any]
    ) -> float:
        """
        Calculate urgency score based on growth signals and opportunities
        
        Args:
            research: CompanyResearch data
            insights: Parsed insights data
            
        Returns:
            Urgency score between 0 and 1
        """
        score = 0.0
        
        # Growth signals contribute 40%
        if research.growth_signals:
            score += min(len(research.growth_signals) / 5, 1.0) * 0.40
            
        # Recent funding contributes 30%
        if research.funding:
            score += 0.30
            
        # High-priority opportunities contribute 20%
        high_priority_opps = [
            opp for opp in insights.get("opportunities", [])
            if isinstance(opp, OpportunityItem) and opp.priority == "high"
        ]
        if high_priority_opps:
            score += min(len(high_priority_opps) / 2, 1.0) * 0.20
            
        # Recent news contributes 10%
        if research.news:
            score += min(len(research.news) / 5, 1.0) * 0.10
            
        return min(score, 1.0)