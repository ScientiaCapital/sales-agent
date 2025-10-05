"""
Test Suite for SearchAgent and AnalysisAgent

Tests multi-agent research and analysis functionality including:
- Company research gathering
- Strategic insight generation
- Agent integration and data flow
- Error handling and fallbacks
- Mock LLM responses for deterministic testing
"""

import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agents.search_agent import SearchAgent, CompanyResearch, NewsItem, FundingInfo
from app.services.agents.analysis_agent import AnalysisAgent, StrategicInsights, OpportunityItem
from app.services.llm_router import LLMRouter, RoutingStrategy


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_llm_router():
    """Create mock LLMRouter for testing"""
    router = MagicMock(spec=LLMRouter)
    router.generate = AsyncMock()
    return router


@pytest.fixture
def sample_news_response():
    """Sample news search response"""
    return {
        "result": json.dumps([
            {
                "title": "TechCorp raises $50M Series B",
                "summary": "Leading AI company secures major funding round led by top VCs.",
                "date": "2025-01-15",
                "source": "TechCrunch",
                "relevance_score": 0.95
            },
            {
                "title": "TechCorp launches new AI platform",
                "summary": "Revolutionary platform transforms enterprise operations.",
                "date": "2025-01-10",
                "source": "VentureBeat",
                "relevance_score": 0.85
            }
        ]),
        "total_cost": 0.00002,
        "latency_ms": 850
    }


@pytest.fixture
def sample_funding_response():
    """Sample funding search response"""
    return {
        "result": json.dumps({
            "round_type": "Series B",
            "amount": "$50M",
            "date": "2025-01-15",
            "investors": ["Sequoia Capital", "a16z", "Tiger Global"],
            "valuation": "$500M",
            "source": "Crunchbase"
        }),
        "total_cost": 0.00001,
        "latency_ms": 780
    }


@pytest.fixture
def sample_tech_stack_response():
    """Sample tech stack analysis response"""
    return {
        "result": json.dumps([
            "Python", "React", "PostgreSQL", "AWS", "Kubernetes",
            "Docker", "Redis", "FastAPI", "Terraform"
        ]),
        "total_cost": 0.00001,
        "latency_ms": 650
    }


@pytest.fixture
def sample_pain_points_response():
    """Sample pain points response"""
    return {
        "result": json.dumps([
            "Scaling infrastructure for rapid growth",
            "Integrating legacy systems with modern AI",
            "Data privacy compliance across regions",
            "Customer onboarding automation"
        ]),
        "total_cost": 0.00001,
        "latency_ms": 720
    }


@pytest.fixture
def sample_growth_signals_response():
    """Sample growth signals response"""
    return {
        "result": json.dumps([
            "Hiring 50+ engineers in Q1 2025",
            "Opening new offices in London and Singapore",
            "Launching enterprise tier product",
            "Partnership with Microsoft announced"
        ]),
        "total_cost": 0.00001,
        "latency_ms": 680
    }

@pytest.fixture
def sample_competitors_response():
    """Sample competitors response"""
    return {
        "result": json.dumps([
            "CompetitorCorp", "RivalTech", "IndustryLeader", "StartupX"
        ]),
        "total_cost": 0.00001,
        "latency_ms": 600
    }


@pytest.fixture
def sample_analysis_response():
    """Sample strategic analysis response"""
    return {
        "result": json.dumps({
            "key_insights": [
                "Recent $50M Series B signals aggressive growth phase",
                "Strong technical foundation with modern stack",
                "Active expansion into international markets"
            ],
            "opportunities": [
                {
                    "type": "timing",
                    "description": "Post-funding window for enterprise infrastructure investment",
                    "priority": "high",
                    "confidence": 0.9,
                    "recommended_action": "Position as growth enabler for international expansion"
                },
                {
                    "type": "pain_point_match",
                    "description": "Scaling challenges align with our infrastructure solutions",
                    "priority": "high",
                    "confidence": 0.85,
                    "recommended_action": "Lead with scalability and compliance case studies"
                }
            ],
            "recommendations": [
                "Reach out within 2 weeks of funding announcement",
                "Target VP Engineering and CTO for technical pitch",
                "Emphasize international compliance and scaling capabilities"
            ],
            "engagement_strategy": "TechCorp is in prime buying window post-Series B with clear infrastructure needs. Approach with focus on enabling international expansion while maintaining compliance. Reference their partnership with Microsoft as validation point.",
            "competitive_positioning": "Differentiate on international compliance and proven enterprise scaling"
        }),
        "total_cost": 0.00003,
        "latency_ms": 1200
    }


# ============================================================================
# SearchAgent Tests
# ============================================================================

@pytest.mark.asyncio
async def test_search_agent_initialization():
    """Test SearchAgent initializes correctly"""
    agent = SearchAgent()
    assert agent.llm_router is not None
    assert isinstance(agent.research_cache, dict)


@pytest.mark.asyncio
async def test_search_agent_research_company(
    mock_llm_router,
    sample_news_response,
    sample_funding_response,
    sample_tech_stack_response,
    sample_pain_points_response,
    sample_growth_signals_response,
    sample_competitors_response
):
    """Test complete company research flow"""
    # Configure mock to return different responses for each call
    mock_llm_router.generate.side_effect = [
        sample_news_response,
        sample_funding_response,
        sample_tech_stack_response,
        sample_pain_points_response,
        sample_growth_signals_response,
        sample_competitors_response
    ]
    
    agent = SearchAgent(llm_router=mock_llm_router)
    
    research = await agent.research_company(
        company_name="TechCorp",
        industry="AI/ML",
        company_website="https://techcorp.ai"
    )
    
    # Verify research object
    assert research.company_name == "TechCorp"
    assert research.industry == "AI/ML"
    assert len(research.news) == 2
    assert research.funding is not None
    assert research.funding.round_type == "Series B"
    assert len(research.tech_stack) > 0
    assert len(research.pain_points) > 0
    assert len(research.growth_signals) > 0
    assert research.confidence > 0
    
    # Verify all parallel tasks were called
    assert mock_llm_router.generate.call_count == 6

@pytest.mark.asyncio
async def test_search_agent_caching(mock_llm_router, sample_news_response):
    """Test research caching mechanism"""
    mock_llm_router.generate.return_value = sample_news_response
    
    agent = SearchAgent(llm_router=mock_llm_router)
    
    # First call should hit the API
    research1 = await agent.research_company("TechCorp")
    call_count_first = mock_llm_router.generate.call_count
    
    # Second call should use cache
    research2 = await agent.research_company("TechCorp")
    call_count_second = mock_llm_router.generate.call_count
    
    assert research1.company_name == research2.company_name
    assert call_count_first == call_count_second  # No new API calls


@pytest.mark.asyncio
async def test_search_agent_force_refresh(mock_llm_router, sample_news_response):
    """Test force refresh bypasses cache"""
    mock_llm_router.generate.return_value = sample_news_response
    
    agent = SearchAgent(llm_router=mock_llm_router)
    
    # First call
    await agent.research_company("TechCorp")
    call_count_first = mock_llm_router.generate.call_count
    
    # Force refresh should make new API calls
    await agent.research_company("TechCorp", force_refresh=True)
    call_count_second = mock_llm_router.generate.call_count
    
    assert call_count_second > call_count_first


@pytest.mark.asyncio
async def test_search_agent_handles_partial_failures(mock_llm_router):
    """Test SearchAgent handles partial research failures gracefully"""
    # Mock some calls to succeed and some to fail
    mock_llm_router.generate.side_effect = [
        {"result": json.dumps([]), "total_cost": 0.00001},  # news - empty
        Exception("API timeout"),  # funding - fails
        {"result": json.dumps(["Python", "React"]), "total_cost": 0.00001},  # tech - succeeds
        {"result": json.dumps([]), "total_cost": 0.00001},  # pain points - empty
        Exception("Rate limited"),  # growth signals - fails
        {"result": json.dumps([]), "total_cost": 0.00001},  # competitors - empty
    ]
    
    agent = SearchAgent(llm_router=mock_llm_router)
    
    # Should not raise exception
    research = await agent.research_company("TechCorp")
    
    # Verify graceful degradation
    assert research.company_name == "TechCorp"
    assert research.news == []
    assert research.funding is None
    assert len(research.tech_stack) == 2
    assert research.confidence < 1.0  # Lower confidence due to failures


@pytest.mark.asyncio
async def test_search_agent_confidence_calculation():
    """Test confidence score calculation"""
    agent = SearchAgent()
    
    # Test with full data
    news = [NewsItem(title="News", summary="Summary", relevance_score=0.9) for _ in range(5)]
    funding = FundingInfo(round_type="Series A", amount="$10M")
    tech_stack = ["Python", "React", "AWS"]
    pain_points = ["Pain 1", "Pain 2"]
    growth_signals = ["Signal 1", "Signal 2"]
    
    confidence = agent._calculate_confidence(news, funding, tech_stack, pain_points, growth_signals)
    assert 0.8 <= confidence <= 1.0  # High confidence with full data
    
    # Test with minimal data
    confidence_low = agent._calculate_confidence([], None, [], [], [])
    assert confidence_low == 0.0  # No confidence with no data

# ============================================================================
# AnalysisAgent Tests
# ============================================================================

@pytest.mark.asyncio
async def test_analysis_agent_initialization():
    """Test AnalysisAgent initializes correctly"""
    agent = AnalysisAgent()
    assert agent.llm_router is not None


@pytest.mark.asyncio
async def test_analysis_agent_analyze_research(
    mock_llm_router,
    sample_analysis_response
):
    """Test strategic analysis generation"""
    mock_llm_router.generate.return_value = sample_analysis_response
    
    agent = AnalysisAgent(llm_router=mock_llm_router)
    
    # Create sample research data
    research = CompanyResearch(
        company_name="TechCorp",
        industry="AI/ML",
        news=[NewsItem(title="Funding", summary="$50M raised", relevance_score=0.9)],
        funding=FundingInfo(round_type="Series B", amount="$50M"),
        tech_stack=["Python", "React"],
        pain_points=["Scaling"],
        growth_signals=["Hiring"],
        confidence=0.85
    )
    
    insights = await agent.analyze_research(
        research=research,
        lead_context={
            "qualification_score": 85,
            "industry": "AI/ML",
            "contact_title": "CTO"
        }
    )
    
    # Verify insights structure
    assert insights.company_name == "TechCorp"
    assert len(insights.key_insights) == 3
    assert len(insights.opportunities) == 2
    assert len(insights.recommendations) == 3
    assert insights.engagement_strategy != ""
    assert 0 < insights.confidence_score <= 1.0
    assert 0 < insights.urgency_score <= 1.0
    
    # Verify opportunities
    assert all(isinstance(opp, OpportunityItem) for opp in insights.opportunities)
    high_priority_opps = [opp for opp in insights.opportunities if opp.priority == "high"]
    assert len(high_priority_opps) == 2


@pytest.mark.asyncio
async def test_analysis_agent_handles_parse_errors(mock_llm_router):
    """Test AnalysisAgent handles JSON parse errors gracefully"""
    # Return invalid JSON
    mock_llm_router.generate.return_value = {
        "result": "This is not valid JSON",
        "total_cost": 0.00001
    }
    
    agent = AnalysisAgent(llm_router=mock_llm_router)
    
    research = CompanyResearch(
        company_name="TechCorp",
        confidence=0.7
    )
    
    insights = await agent.analyze_research(research)
    
    # Should return minimal insights without crashing
    assert insights.company_name == "TechCorp"
    assert len(insights.key_insights) > 0
    assert "parsing failed" in insights.key_insights[0].lower()
    assert insights.confidence_score >= 0


@pytest.mark.asyncio
async def test_analysis_agent_confidence_calculation():
    """Test analysis confidence calculation"""
    agent = AnalysisAgent()
    
    # High quality research
    research_high = CompanyResearch(
        company_name="TechCorp",
        confidence=0.9
    )
    
    insights_high = {
        "key_insights": ["Insight 1", "Insight 2", "Insight 3"],
        "opportunities": [
            OpportunityItem(type="timing", description="Opp 1", priority="high", confidence=0.9),
            OpportunityItem(type="fit", description="Opp 2", priority="medium", confidence=0.8)
        ],
        "recommendations": ["Rec 1", "Rec 2", "Rec 3"],
        "engagement_strategy": "A" * 200  # Long strategy
    }
    
    confidence = agent._calculate_analysis_confidence(insights_high, research_high)
    assert confidence > 0.8  # High confidence
    
    # Low quality research
    research_low = CompanyResearch(
        company_name="TechCorp",
        confidence=0.2
    )
    
    insights_low = {
        "key_insights": [],
        "opportunities": [],
        "recommendations": [],
        "engagement_strategy": ""
    }
    
    confidence_low = agent._calculate_analysis_confidence(insights_low, research_low)
    assert confidence_low < 0.3  # Low confidence

@pytest.mark.asyncio
async def test_analysis_agent_urgency_calculation():
    """Test urgency score calculation"""
    agent = AnalysisAgent()
    
    # High urgency scenario
    research_urgent = CompanyResearch(
        company_name="TechCorp",
        news=[NewsItem(title="News", summary="Summary", relevance_score=0.9) for _ in range(5)],
        funding=FundingInfo(round_type="Series B", amount="$50M"),
        growth_signals=["Signal 1", "Signal 2", "Signal 3", "Signal 4", "Signal 5"],
        confidence=0.9
    )
    
    insights_urgent = {
        "opportunities": [
            OpportunityItem(type="timing", description="Urgent", priority="high", confidence=0.9),
            OpportunityItem(type="fit", description="Critical", priority="high", confidence=0.85)
        ]
    }
    
    urgency = agent._calculate_urgency_score(research_urgent, insights_urgent)
    assert urgency > 0.7  # High urgency
    
    # Low urgency scenario
    research_calm = CompanyResearch(
        company_name="TechCorp",
        confidence=0.5
    )
    
    insights_calm = {"opportunities": []}
    
    urgency_low = agent._calculate_urgency_score(research_calm, insights_calm)
    assert urgency_low < 0.3  # Low urgency


# ============================================================================
# Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_agent_integration_full_pipeline(
    mock_llm_router,
    sample_news_response,
    sample_funding_response,
    sample_tech_stack_response,
    sample_pain_points_response,
    sample_growth_signals_response,
    sample_competitors_response,
    sample_analysis_response
):
    """Test complete agent pipeline: SearchAgent → AnalysisAgent"""
    # Configure mock for both agents
    mock_llm_router.generate.side_effect = [
        # SearchAgent calls
        sample_news_response,
        sample_funding_response,
        sample_tech_stack_response,
        sample_pain_points_response,
        sample_growth_signals_response,
        sample_competitors_response,
        # AnalysisAgent call
        sample_analysis_response
    ]
    
    # Step 1: Research company
    search_agent = SearchAgent(llm_router=mock_llm_router)
    research = await search_agent.research_company(
        company_name="TechCorp",
        industry="AI/ML"
    )
    
    assert research.company_name == "TechCorp"
    assert research.confidence > 0
    
    # Step 2: Analyze research
    analysis_agent = AnalysisAgent(llm_router=mock_llm_router)
    insights = await analysis_agent.analyze_research(
        research=research,
        lead_context={"qualification_score": 85}
    )
    
    assert insights.company_name == "TechCorp"
    assert len(insights.opportunities) > 0
    assert insights.engagement_strategy != ""
    
    # Verify total API calls
    assert mock_llm_router.generate.call_count == 7


@pytest.mark.asyncio
async def test_agent_data_flow():
    """Test data flow between agents"""
    # Create SearchAgent with real router (will use actual models if configured)
    # For unit tests, we'll mock the router
    mock_router = MagicMock(spec=LLMRouter)
    mock_router.generate = AsyncMock(return_value={
        "result": json.dumps([]),
        "total_cost": 0.00001
    })
    
    search_agent = SearchAgent(llm_router=mock_router)
    analysis_agent = AnalysisAgent(llm_router=mock_router)
    
    # Verify agents share the same router instance if provided
    assert search_agent.llm_router == mock_router
    assert analysis_agent.llm_router == mock_router


# ============================================================================
# Error Handling Tests
# ============================================================================

@pytest.mark.asyncio
async def test_search_agent_handles_api_errors(mock_llm_router):
    """Test SearchAgent handles complete API failure"""
    mock_llm_router.generate.side_effect = Exception("Complete API failure")
    
    agent = SearchAgent(llm_router=mock_llm_router)
    
    # Should raise ExternalAPIError
    with pytest.raises(Exception):
        await agent.research_company("TechCorp")


@pytest.mark.asyncio
async def test_analysis_agent_handles_api_errors(mock_llm_router):
    """Test AnalysisAgent handles API errors gracefully"""
    mock_llm_router.generate.side_effect = Exception("API failure")
    
    agent = AnalysisAgent(llm_router=mock_llm_router)
    
    research = CompanyResearch(
        company_name="TechCorp",
        confidence=0.7
    )
    
    # Should return minimal insights without crashing
    insights = await agent.analyze_research(research)
    assert insights.company_name == "TechCorp"
    assert insights.confidence_score == 0.0  # Zero confidence on failure