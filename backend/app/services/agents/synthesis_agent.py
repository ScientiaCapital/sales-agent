"""
SynthesisAgent for professional report generation

Consumes research and analysis data to generate:
- Professional markdown reports
- HTML formatted output
- Executive summaries
- Actionable recommendations
"""

import logging
import markdown
from typing import Dict, Optional
from datetime import datetime
from pydantic import BaseModel, Field

from app.services.llm_router import LLMRouter, RoutingStrategy
from .search_agent import CompanyResearch
from .analysis_agent import StrategicInsights

logger = logging.getLogger(__name__)


class ReportContent(BaseModel):
    """Generated report content"""
    title: str
    markdown: str
    html: str
    confidence: float = Field(ge=0.0, le=1.0)
    total_cost: float = 0.0
    generation_timestamp: datetime = Field(default_factory=datetime.utcnow)


class SynthesisAgent:
    """
    AI agent for report synthesis and formatting
    
    Combines research and analysis into polished, professional reports.
    Uses quality-optimized routing for high-quality writing.
    """
    
    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        routing_strategy: RoutingStrategy = RoutingStrategy.QUALITY_OPTIMIZED
    ):
        """
        Initialize SynthesisAgent
        
        Args:
            llm_router: LLMRouter instance (creates new if not provided)
            routing_strategy: Strategy for LLM routing (default: QUALITY_OPTIMIZED for professional writing)
        """
        self.llm_router = llm_router or LLMRouter(strategy=routing_strategy)
    
    async def generate_report(
        self,
        company_name: str,
        research: CompanyResearch,
        insights: StrategicInsights
    ) -> ReportContent:
        """
        Generate professional markdown report from research and insights
        
        Args:
            company_name: Company name
            research: CompanyResearch from SearchAgent
            insights: StrategicInsights from AnalysisAgent
            
        Returns:
            ReportContent with markdown and HTML versions
        """
        # Build comprehensive report generation prompt
        report_prompt = self._build_report_prompt(company_name, research, insights)
        
        try:
            # Use quality-optimized routing for professional writing
            result = await self.llm_router.generate(
                prompt=report_prompt,
                temperature=0.3,  # Lower temperature for professional, consistent writing
                max_tokens=2000
            )
            
            markdown_content = result["content"]
            
            # Convert markdown to HTML
            html_content = self._markdown_to_html(markdown_content)
            
            # Generate title
            title = f"Strategic Report: {company_name}"
            
            # Calculate average confidence from research and insights
            avg_confidence = (research.confidence + insights.confidence_score) / 2
            
            return ReportContent(
                title=title,
                markdown=markdown_content,
                html=html_content,
                confidence=avg_confidence,
                total_cost=result["metadata"]["total_cost_usd"],
                generation_timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Report generation failed for {company_name}: {e}")
            raise
    
    def _build_report_prompt(
        self,
        company_name: str,
        research: CompanyResearch,
        insights: StrategicInsights
    ) -> str:
        """Build comprehensive report generation prompt"""
        
        # Serialize research and insights data
        research_json = research.model_dump_json(indent=2)
        insights_json = insights.model_dump_json(indent=2)
        
        prompt = f"""
You are a professional business analyst creating a strategic report for a sales team.

Generate a comprehensive, well-structured markdown report for {company_name}.

RESEARCH DATA:
{research_json}

STRATEGIC INSIGHTS:
{insights_json}

Create a professional markdown report with the following sections:

# Executive Summary
- 2-3 paragraph overview of key findings
- Highlight most compelling opportunities

# Company Overview
- Industry and market position
- Recent news and developments
- Technology stack and capabilities

# Key Findings
- Strategic insights from research
- Growth signals and pain points
- Competitive positioning

# Strategic Opportunities
- High-priority engagement opportunities
- Product-market fit assessment
- Timing and urgency factors

# Recommended Next Steps
- Specific, actionable recommendations
- Engagement strategy
- Priority sequencing

# Engagement Strategy
- Personalized approach based on insights
- Key talking points
- Value proposition alignment

Requirements:
- Use professional business language
- Include specific data points from research
- Focus on actionable insights
- Maintain objective, data-driven tone
- Use markdown formatting (headers, lists, bold, italic)

Generate ONLY the markdown report content. Do not include any meta-commentary.
"""
        return prompt
    
    def _markdown_to_html(self, markdown_content: str) -> str:
        """
        Convert markdown to HTML with extensions
        
        Args:
            markdown_content: Markdown string
            
        Returns:
            HTML string
        """
        html = markdown.markdown(
            markdown_content,
            extensions=[
                'markdown.extensions.tables',
                'markdown.extensions.fenced_code',
                'markdown.extensions.nl2br',
                'markdown.extensions.sane_lists'
            ]
        )
        return html
