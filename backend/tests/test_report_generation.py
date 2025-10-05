"""
Tests for report generation system

Tests the complete multi-agent pipeline:
- SearchAgent
- AnalysisAgent
- SynthesisAgent
- ReportGenerator orchestrator
- API endpoints
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from app.services.agents.search_agent import SearchAgent, CompanyResearch, NewsItem
from app.services.agents.analysis_agent import AnalysisAgent, StrategicInsights, OpportunityItem
from app.services.agents.synthesis_agent import SynthesisAgent, ReportContent
from app.services.report_generator import ReportGenerator
from app.models.lead import Lead
from app.models.report import Report


class TestSearchAgent:
    """Test SearchAgent functionality"""
    
    @pytest.mark.asyncio
    async def test_search_agent_initialization(self):
        """Test SearchAgent can be initialized"""
        agent = SearchAgent()
        assert agent is not None
        assert agent.llm_router is not None
    
    @pytest.mark.asyncio
    async def test_company_research_model(self):
        """Test CompanyResearch Pydantic model"""
        research = CompanyResearch(
            company_name="TechCorp Inc",
            industry="SaaS",
            confidence=0.85,
            total_cost=0.0001,
            total_latency_ms=945
        )
        assert research.company_name == "TechCorp Inc"
        assert research.confidence == 0.85
        assert len(research.news) == 0


class TestAnalysisAgent:
    """Test AnalysisAgent functionality"""
    
    @pytest.mark.asyncio
    async def test_analysis_agent_initialization(self):
        """Test AnalysisAgent can be initialized"""
        agent = AnalysisAgent()
        assert agent is not None
        assert agent.llm_router is not None
    
    @pytest.mark.asyncio
    async def test_strategic_insights_model(self):
        """Test StrategicInsights Pydantic model"""
        insights = StrategicInsights(
            company_name="TechCorp Inc",
            engagement_strategy="Focus on pain point X",
            urgency_score=0.75,
            confidence_score=0.88,
            total_cost=0.0002
        )
        assert insights.company_name == "TechCorp Inc"
        assert insights.urgency_score == 0.75
        assert len(insights.opportunities) == 0


class TestSynthesisAgent:
    """Test SynthesisAgent functionality"""
    
    @pytest.mark.asyncio
    async def test_synthesis_agent_initialization(self):
        """Test SynthesisAgent can be initialized"""
        agent = SynthesisAgent()
        assert agent is not None
        assert agent.llm_router is not None
    
    def test_markdown_to_html_conversion(self):
        """Test markdown to HTML conversion"""
        agent = SynthesisAgent()
        markdown = "# Heading\n\n**Bold text**"
        html = agent._markdown_to_html(markdown)
        
        assert "<h1>Heading</h1>" in html
        assert "<strong>Bold text</strong>" in html


class TestReportGenerator:
    """Test ReportGenerator orchestrator"""
    
    def test_report_generator_initialization(self):
        """Test ReportGenerator can be initialized"""
        generator = ReportGenerator()
        assert generator is not None
        assert generator.search_agent is not None
        assert generator.analysis_agent is not None
        assert generator.synthesis_agent is not None
    
    @pytest.mark.asyncio
    async def test_report_generator_with_mocked_agents(self, db_session):
        """Test complete report generation with mocked agents"""
        # Create test lead
        lead = Lead(
            company_name="TechCorp Inc",
            industry="SaaS",
            company_size="50-200",
            qualification_score=85.0
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        
        # Mock the agents
        generator = ReportGenerator()
        
        # Mock SearchAgent
        mock_research = CompanyResearch(
            company_name="TechCorp Inc",
            industry="SaaS",
            confidence=0.9,
            total_cost=0.0001,
            total_latency_ms=900
        )
        generator.search_agent.research_company = AsyncMock(return_value=mock_research)
        
        # Mock AnalysisAgent
        mock_insights = StrategicInsights(
            company_name="TechCorp Inc",
            engagement_strategy="Focus on automation",
            urgency_score=0.8,
            confidence_score=0.85,
            total_cost=0.0002
        )
        generator.analysis_agent.analyze_research = AsyncMock(return_value=mock_insights)
        
        # Mock SynthesisAgent
        mock_report_content = ReportContent(
            title="Strategic Report: TechCorp Inc",
            markdown="# Executive Summary\n\nTest report",
            html="<h1>Executive Summary</h1><p>Test report</p>",
            confidence=0.875,
            total_cost=0.0003
        )
        generator.synthesis_agent.generate_report = AsyncMock(return_value=mock_report_content)
        
        # Generate report
        report = await generator.generate_report(lead, db_session)
        
        # Verify report was created
        assert report is not None
        assert report.lead_id == lead.id
        assert report.status == "completed"
        assert report.title == "Strategic Report: TechCorp Inc"
        assert report.content_markdown == "# Executive Summary\n\nTest report"
        assert report.content_html == "<h1>Executive Summary</h1><p>Test report</p>"
        assert report.confidence_score == 87.5  # 0.875 * 100
        assert report.generation_time_ms > 0
        
        # Verify agents were called
        generator.search_agent.research_company.assert_called_once()
        generator.analysis_agent.analyze_research.assert_called_once()
        generator.synthesis_agent.generate_report.assert_called_once()


class TestReportAPI:
    """Test report API endpoints"""
    
    def test_generate_report_endpoint(self, client, db_session):
        """Test POST /api/reports/generate endpoint"""
        # Create test lead
        lead = Lead(
            company_name="TechCorp Inc",
            industry="SaaS"
        )
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        
        # Request report generation
        response = client.post(
            "/api/reports/generate",
            json={"lead_id": lead.id}
        )
        
        # Verify response
        assert response.status_code == 202
        data = response.json()
        assert data["status"] == "generating"
        assert "message" in data
    
    def test_get_report_endpoint(self, client, db_session):
        """Test GET /api/reports/{id} endpoint"""
        # Create test lead and report
        lead = Lead(company_name="TechCorp Inc", industry="SaaS")
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        
        report = Report(
            lead_id=lead.id,
            title="Test Report",
            status="completed",
            content_markdown="# Test",
            content_html="<h1>Test</h1>",
            confidence_score=85.0,
            generation_time_ms=5000
        )
        db_session.add(report)
        db_session.commit()
        db_session.refresh(report)
        
        # Get report
        response = client.get(f"/api/reports/{report.id}")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == report.id
        assert data["title"] == "Test Report"
        assert data["status"] == "completed"
    
    def test_list_reports_by_lead(self, client, db_session):
        """Test GET /api/reports/lead/{lead_id} endpoint"""
        # Create test lead with multiple reports
        lead = Lead(company_name="TechCorp Inc", industry="SaaS")
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        
        # Create multiple reports
        for i in range(3):
            report = Report(
                lead_id=lead.id,
                title=f"Report {i+1}",
                status="completed",
                content_markdown=f"# Report {i+1}",
                confidence_score=80.0 + i
            )
            db_session.add(report)
        db_session.commit()
        
        # Get reports for lead
        response = client.get(f"/api/reports/lead/{lead.id}")
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3
        assert len(data["reports"]) == 3
        assert data["page"] == 1
    
    def test_report_not_found(self, client):
        """Test 404 for non-existent report"""
        response = client.get("/api/reports/99999")
        assert response.status_code == 404


class TestReportModel:
    """Test Report database model"""
    
    def test_create_report(self, db_session):
        """Test creating a report in the database"""
        lead = Lead(company_name="TechCorp Inc", industry="SaaS")
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        
        report = Report(
            lead_id=lead.id,
            title="Test Report",
            status="generating"
        )
        db_session.add(report)
        db_session.commit()
        db_session.refresh(report)
        
        assert report.id is not None
        assert report.lead_id == lead.id
        assert report.status == "generating"
    
    def test_report_lead_relationship(self, db_session):
        """Test Report-Lead relationship"""
        lead = Lead(company_name="TechCorp Inc", industry="SaaS")
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        
        report = Report(
            lead_id=lead.id,
            title="Test Report",
            status="completed"
        )
        db_session.add(report)
        db_session.commit()
        db_session.refresh(report)
        
        # Test relationship
        assert report.lead.company_name == "TechCorp Inc"
        assert len(lead.reports) == 1
        assert lead.reports[0].id == report.id
    
    def test_cascade_delete(self, db_session):
        """Test cascade delete when lead is deleted"""
        lead = Lead(company_name="TechCorp Inc", industry="SaaS")
        db_session.add(lead)
        db_session.commit()
        db_session.refresh(lead)
        
        report = Report(
            lead_id=lead.id,
            title="Test Report",
            status="completed"
        )
        db_session.add(report)
        db_session.commit()
        report_id = report.id
        
        # Delete lead
        db_session.delete(lead)
        db_session.commit()
        
        # Verify report was also deleted (cascade)
        deleted_report = db_session.query(Report).filter(Report.id == report_id).first()
        assert deleted_report is None
