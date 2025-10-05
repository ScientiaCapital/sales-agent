"""
ReportGenerator - Multi-Agent Report Generation Orchestrator

Orchestrates the 3-agent pipeline for comprehensive report generation:
1. SearchAgent: Company research and data gathering
2. AnalysisAgent: Strategic insights and opportunity identification
3. SynthesisAgent: Professional report formatting

Target: <10s total execution time using ultra-fast Cerebras inference
"""

import logging
import time
from typing import Dict, Any, Optional
from datetime import datetime

from app.models.lead import Lead
from app.models.report import Report
from app.services.agents.search_agent import SearchAgent, CompanyResearch
from app.services.agents.analysis_agent import AnalysisAgent, StrategicInsights
from app.services.agents.synthesis_agent import SynthesisAgent, ReportContent
from app.services.llm_router import LLMRouter, RoutingStrategy
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Multi-agent orchestrator for report generation
    
    Pipeline:
    1. SearchAgent (BALANCED) - Cost-effective research
    2. AnalysisAgent (QUALITY_OPTIMIZED) - High-quality insights
    3. SynthesisAgent (QUALITY_OPTIMIZED) - Professional writing
    
    Uses different routing strategies per agent for optimal cost/quality balance.
    """
    
    def __init__(self):
        """Initialize report generator with agent instances"""
        # Shared LLM router for cost tracking
        base_router = LLMRouter()
        
        # Initialize agents with optimized routing strategies
        self.search_agent = SearchAgent(
            llm_router=base_router,
            routing_strategy=RoutingStrategy.BALANCED
        )
        self.analysis_agent = AnalysisAgent(
            llm_router=base_router,
            routing_strategy=RoutingStrategy.QUALITY_OPTIMIZED
        )
        self.synthesis_agent = SynthesisAgent(
            llm_router=base_router,
            routing_strategy=RoutingStrategy.QUALITY_OPTIMIZED
        )
    
    async def generate_report(self, lead: Lead, db: Session) -> Report:
        """
        Generate comprehensive report for lead using 3-agent pipeline
        
        Args:
            lead: Lead object from database
            db: SQLAlchemy database session
            
        Returns:
            Report object with complete generated content
            
        Raises:
            Exception: If any agent fails (report status set to 'failed')
        """
        start_time = time.time()
        report_record = None
        
        try:
            logger.info(f"Starting report generation for lead {lead.id}: {lead.company_name}")
            
            # Create initial report record with 'generating' status
            report_record = Report(
                lead_id=lead.id,
                title=f"Generating Report: {lead.company_name}",
                status="generating"
            )
            db.add(report_record)
            db.commit()
            db.refresh(report_record)
            
            # Phase 1: Company Research (SearchAgent)
            logger.info(f"Phase 1: Running SearchAgent for {lead.company_name}")
            research: CompanyResearch = await self.search_agent.research_company(
                company_name=lead.company_name,
                industry=lead.industry,
                company_website=lead.company_website
            )
            logger.info(f"SearchAgent complete: {len(research.news)} news items, confidence={research.confidence}")
            
            # Phase 2: Strategic Analysis (AnalysisAgent)
            logger.info(f"Phase 2: Running AnalysisAgent for {lead.company_name}")
            lead_context = {
                "industry": lead.industry,
                "company_size": lead.company_size,
                "qualification_score": lead.qualification_score,
                "contact_title": lead.contact_title
            }
            insights: StrategicInsights = await self.analysis_agent.analyze_research(
                research=research,
                lead_context=lead_context
            )
            logger.info(f"AnalysisAgent complete: {len(insights.opportunities)} opportunities, urgency={insights.urgency_score}")
            
            # Phase 3: Report Synthesis (SynthesisAgent)
            logger.info(f"Phase 3: Running SynthesisAgent for {lead.company_name}")
            report_content: ReportContent = await self.synthesis_agent.generate_report(
                company_name=lead.company_name,
                research=research,
                insights=insights
            )
            logger.info(f"SynthesisAgent complete: {len(report_content.markdown)} chars")
            
            # Calculate total generation time
            generation_time = int((time.time() - start_time) * 1000)
            
            # Update report record with complete data
            report_record.title = report_content.title
            report_record.content_markdown = report_content.markdown
            report_record.content_html = report_content.html
            report_record.research_data = research.model_dump()
            report_record.insights_data = insights.model_dump()
            report_record.confidence_score = report_content.confidence * 100  # Convert to 0-100 scale
            report_record.generation_time_ms = generation_time
            report_record.status = "completed"
            
            db.commit()
            db.refresh(report_record)
            
            logger.info(
                f"Report generation complete for {lead.company_name}: "
                f"{generation_time}ms, confidence={report_record.confidence_score:.1f}"
            )
            
            return report_record
            
        except Exception as e:
            # Handle failure - update report with error status
            generation_time = int((time.time() - start_time) * 1000)
            
            error_msg = f"Report generation failed: {str(e)}"
            logger.error(error_msg, exc_info=True)
            
            if report_record:
                # Update existing record with error
                report_record.status = "failed"
                report_record.error_message = error_msg
                report_record.generation_time_ms = generation_time
                db.commit()
                db.refresh(report_record)
            else:
                # Create new failed report record
                report_record = Report(
                    lead_id=lead.id,
                    title=f"Report Generation Failed: {lead.company_name}",
                    status="failed",
                    error_message=error_msg,
                    generation_time_ms=generation_time
                )
                db.add(report_record)
                db.commit()
                db.refresh(report_record)
            
            # Re-raise exception for API error handling
            raise
