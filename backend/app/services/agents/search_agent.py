"""
SearchAgent for automated company research and data gathering

Performs parallel searches for company information including:
- Recent news and press releases
- Funding rounds and investors
- Technology stack analysis
- Pain point identification
- Growth signal detection
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import aiohttp
from bs4 import BeautifulSoup

from app.services.llm_router import LLMRouter, RoutingStrategy
from app.core.exceptions import ExternalAPIException, ValidationError

logger = logging.getLogger(__name__)


class NewsItem(BaseModel):
    """Individual news item"""
    title: str
    url: Optional[str] = None
    summary: str
    date: Optional[str] = None
    source: Optional[str] = None
    relevance_score: float = Field(ge=0.0, le=1.0)
"""
SearchAgent for automated company research and data gathering

Performs parallel searches for company information including:
- Recent news and press releases
- Funding rounds and investors
- Technology stack analysis
- Pain point identification
- Growth signal detection
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
import aiohttp
from bs4 import BeautifulSoup

from app.services.llm_router import LLMRouter, RoutingStrategy
from app.core.exceptions import ExternalAPIException, ValidationError

logger = logging.getLogger(__name__)


class NewsItem(BaseModel):
    """Individual news item"""
    title: str
    url: Optional[str] = None
    summary: str
    date: Optional[str] = None
    source: Optional[str] = None
    relevance_score: float = Field(ge=0.0, le=1.0)


class FundingInfo(BaseModel):
    """Funding information"""
    round_type: Optional[str] = None  # Seed, Series A, B, C, etc.
    amount: Optional[str] = None
    date: Optional[str] = None
    investors: List[str] = Field(default_factory=list)
    valuation: Optional[str] = None
    source: Optional[str] = None


class CompanyResearch(BaseModel):
    """Comprehensive company research results"""
    company_name: str
    industry: Optional[str] = None
    news: List[NewsItem] = Field(default_factory=list)
    funding: Optional[FundingInfo] = None
    tech_stack: List[str] = Field(default_factory=list)
    pain_points: List[str] = Field(default_factory=list)
    growth_signals: List[str] = Field(default_factory=list)
    competitors: List[str] = Field(default_factory=list)
    market_position: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    research_timestamp: datetime = Field(default_factory=datetime.utcnow)
    total_cost: float = 0.0
    total_latency_ms: int = 0

    @validator('confidence')
    def validate_confidence(cls, v):
        """Ensure confidence is between 0 and 1"""
        return max(0.0, min(1.0, v))
class SearchAgent:
    """
    AI agent for company research and data gathering
    
    Uses parallel searches and LLM routing for cost-effective research.
    Implements fallback mechanisms and comprehensive error handling.
    """
    
    def __init__(
        self,
        llm_router: Optional[LLMRouter] = None,
        routing_strategy: RoutingStrategy = RoutingStrategy.BALANCED
    ):
        """
        Initialize SearchAgent
        
        Args:
            llm_router: LLMRouter instance (creates new if not provided)
            routing_strategy: Strategy for LLM routing (default: BALANCED for 64% cost savings)
        """
        self.llm_router = llm_router or LLMRouter(strategy=routing_strategy)
        self.session: Optional[aiohttp.ClientSession] = None
        self.research_cache: Dict[str, CompanyResearch] = {}
        self.cache_ttl = timedelta(hours=24)  # Cache research for 24 hours
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            
    def _get_from_cache(self, company_name: str) -> Optional[CompanyResearch]:
        """Get research from cache if fresh"""
        if company_name in self.research_cache:
            cached = self.research_cache[company_name]
            age = datetime.utcnow() - cached.research_timestamp
            if age < self.cache_ttl:
                logger.info(f"Returning cached research for {company_name} (age: {age})")
                return cached
        return None

    async def research_company(
        self,
        company_name: str,
        industry: Optional[str] = None,
        company_website: Optional[str] = None,
        force_refresh: bool = False
    ) -> CompanyResearch:
        """
        Conduct comprehensive company research
        
        Args:
            company_name: Name of the company to research
            industry: Industry sector (helps improve search relevance)
            company_website: Company website URL (for tech stack analysis)
            force_refresh: Bypass cache and force new research
            
        Returns:
            CompanyResearch object with all gathered data
        """
        # Check cache unless force refresh
        if not force_refresh:
            cached = self._get_from_cache(company_name)
            if cached:
                return cached
                
        start_time = datetime.utcnow()
        total_cost = 0.0
        
        # Run all research tasks in parallel for efficiency
        research_tasks = [
            self._search_news(company_name, industry),
            self._search_funding(company_name),
            self._analyze_tech_stack(company_name, company_website),
            self._identify_pain_points(company_name, industry),
            self._detect_growth_signals(company_name),
            self._identify_competitors(company_name, industry)
        ]        
        try:
            results = await asyncio.gather(*research_tasks, return_exceptions=True)
            
            # Unpack results, handling any exceptions
            news_result, funding_result, tech_result, pain_points_result, growth_result, competitors_result = results
            
            # Process each result, using empty defaults for failures
            news = news_result if not isinstance(news_result, Exception) else []
            funding = funding_result if not isinstance(funding_result, Exception) else None
            tech_stack = tech_result if not isinstance(tech_result, Exception) else []
            pain_points = pain_points_result if not isinstance(pain_points_result, Exception) else []
            growth_signals = growth_result if not isinstance(growth_result, Exception) else []
            competitors = competitors_result if not isinstance(competitors_result, Exception) else []
            
            # Log any exceptions
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.warning(f"Research task {i} failed: {result}")
                    
            # Calculate confidence based on successful data gathering
            confidence = self._calculate_confidence(news, funding, tech_stack, pain_points, growth_signals)
            
            # Calculate total latency
            total_latency_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            # Create research object
            research = CompanyResearch(
                company_name=company_name,
                industry=industry,
                news=news,
                funding=funding,
                tech_stack=tech_stack,
                pain_points=pain_points,
                growth_signals=growth_signals,
                competitors=competitors,
                confidence=confidence,
                total_cost=total_cost,
                total_latency_ms=total_latency_ms
            )            
            # Cache the research
            self.research_cache[company_name] = research
            
            logger.info(
                f"Completed research for {company_name} - "
                f"Confidence: {confidence:.2%}, "
                f"Cost: ${total_cost:.6f}, "
                f"Latency: {total_latency_ms}ms"
            )
            
            return research
            
        except Exception as e:
            logger.error(f"Failed to research company {company_name}: {e}")
            raise ExternalAPIException(
                message=f"Company research failed for {company_name}",
                details={"company": company_name, "error": str(e)}
            )
    
    async def _search_news(
        self,
        company_name: str,
        industry: Optional[str] = None
    ) -> List[NewsItem]:
        """
        Search for recent company news using LLM
        
        Args:
            company_name: Company name to search for
            industry: Industry context for better search
            
        Returns:
            List of news items with summaries
        """
        prompt = f"""
        Find and summarize the 5 most recent and relevant news items about {company_name}.
        {f"Industry context: {industry}" if industry else ""}
        
        Return as JSON array with this structure:
        [
            {{
                "title": "News headline",
                "summary": "2-3 sentence summary of the news",
                "date": "YYYY-MM-DD or relative date",
                "source": "News source",
                "relevance_score": 0.0-1.0
            }}
        ]
        
        Focus on: funding, product launches, partnerships, leadership changes, major contracts.
        If no recent news found, return empty array [].
        """        
        try:
            result = await self.llm_router.generate(
                prompt=prompt,
                temperature=0.3,
                max_tokens=800
            )
            
            # Parse JSON response
            news_data = json.loads(result.get("result", "[]"))
            
            # Convert to NewsItem objects
            news_items = []
            for item in news_data[:5]:  # Limit to 5 items
                try:
                    news_items.append(NewsItem(**item))
                except Exception as e:
                    logger.warning(f"Failed to parse news item: {e}")
                    
            return news_items
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse news JSON for {company_name}")
            return []
        except Exception as e:
            logger.error(f"News search failed for {company_name}: {e}")
            return []    
    async def _search_funding(self, company_name: str) -> Optional[FundingInfo]:
        """
        Search for funding information
        
        Args:
            company_name: Company name to search for
            
        Returns:
            FundingInfo object or None if no funding found
        """
        prompt = f"""
        Find the most recent funding information for {company_name}.
        
        Return as JSON with this structure:
        {{
            "round_type": "Seed/Series A/B/C/IPO etc.",
            "amount": "Amount raised (e.g., $10M)",
            "date": "YYYY-MM-DD or relative date",
            "investors": ["Investor 1", "Investor 2"],
            "valuation": "Company valuation if available",
            "source": "Information source"
        }}
        
        If no funding information available, return {{}}.
        """
        
        try:
            result = await self.llm_router.generate(
                prompt=prompt,
                temperature=0.2,
                max_tokens=400
            )            
            funding_data = json.loads(result.get("result", "{}"))
            
            if funding_data:
                return FundingInfo(**funding_data)
            return None
            
        except (json.JSONDecodeError, ValidationError) as e:
            logger.warning(f"Failed to parse funding data for {company_name}: {e}")
            return None
        except Exception as e:
            logger.error(f"Funding search failed for {company_name}: {e}")
            return None
    
    async def _analyze_tech_stack(
        self,
        company_name: str,
        company_website: Optional[str] = None
    ) -> List[str]:
        """
        Analyze company technology stack
        
        Args:
            company_name: Company name
            company_website: Website URL for analysis
            
        Returns:
            List of identified technologies
        """
        context = f"Company: {company_name}"
        if company_website:
            context += f"\nWebsite: {company_website}"            
        prompt = f"""
        Identify the likely technology stack for {context}.
        
        Consider: programming languages, frameworks, databases, cloud providers, 
        DevOps tools, analytics, and other technical infrastructure.
        
        Return as JSON array of technology names:
        ["React", "Node.js", "PostgreSQL", "AWS", "Docker", ...]
        
        List only technologies you're confident about. If unknown, return [].
        Maximum 15 technologies.
        """
        
        try:
            result = await self.llm_router.generate(
                prompt=prompt,
                temperature=0.3,
                max_tokens=300
            )
            
            tech_list = json.loads(result.get("result", "[]"))
            return tech_list[:15]  # Limit to 15 technologies
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse tech stack for {company_name}")
            return []
        except Exception as e:
            logger.error(f"Tech stack analysis failed for {company_name}: {e}")
            return []    
    async def _identify_pain_points(
        self,
        company_name: str,
        industry: Optional[str] = None
    ) -> List[str]:
        """
        Identify potential pain points based on industry and company
        
        Args:
            company_name: Company name
            industry: Industry sector
            
        Returns:
            List of identified pain points
        """
        context = f"Company: {company_name}"
        if industry:
            context += f"\nIndustry: {industry}"
            
        prompt = f"""
        Identify 5 likely business pain points for {context}.
        
        Consider common challenges in their industry such as:
        - Operational inefficiencies
        - Customer acquisition/retention
        - Technology limitations
        - Compliance and regulation
        - Market competition
        - Scaling challenges
        
        Return as JSON array of pain point descriptions:
        ["Pain point 1", "Pain point 2", ...]
        
        Be specific and actionable. Maximum 5 pain points.
        """        
        try:
            result = await self.llm_router.generate(
                prompt=prompt,
                temperature=0.4,
                max_tokens=400
            )
            
            pain_points = json.loads(result.get("result", "[]"))
            return pain_points[:5]  # Limit to 5 pain points
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse pain points for {company_name}")
            return []
        except Exception as e:
            logger.error(f"Pain point identification failed for {company_name}: {e}")
            return []
    
    async def _detect_growth_signals(self, company_name: str) -> List[str]:
        """
        Detect growth signals (hiring, expansion, product launches)
        
        Args:
            company_name: Company name
            
        Returns:
            List of growth signals
        """
        prompt = f"""
        Identify growth signals and buying indicators for {company_name}.
        
        Look for signals such as:
        - Rapid hiring or team expansion
        - New office locations or market expansion
        - Product launches or major updates
        - Partnership announcements
        - Increased marketing activity
        - Technology modernization initiatives
        
        Return as JSON array of growth signals:
        ["Signal 1", "Signal 2", ...]
        
        List only clear, specific signals. Maximum 5 signals.
        """        
        try:
            result = await self.llm_router.generate(
                prompt=prompt,
                temperature=0.3,
                max_tokens=400
            )
            
            signals = json.loads(result.get("result", "[]"))
            return signals[:5]  # Limit to 5 signals
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse growth signals for {company_name}")
            return []
        except Exception as e:
            logger.error(f"Growth signal detection failed for {company_name}: {e}")
            return []
    
    async def _identify_competitors(
        self,
        company_name: str,
        industry: Optional[str] = None
    ) -> List[str]:
        """
        Identify main competitors
        
        Args:
            company_name: Company name
            industry: Industry sector
            
        Returns:
            List of competitor names
        """
        context = f"Company: {company_name}"
        if industry:
            context += f"\nIndustry: {industry}"            
        prompt = f"""
        Identify the top 5 competitors for {context}.
        
        Return as JSON array of competitor company names:
        ["Competitor 1", "Competitor 2", ...]
        
        Only list direct competitors in the same market segment.
        Maximum 5 competitors.
        """
        
        try:
            result = await self.llm_router.generate(
                prompt=prompt,
                temperature=0.2,
                max_tokens=200
            )
            
            competitors = json.loads(result.get("result", "[]"))
            return competitors[:5]  # Limit to 5 competitors
            
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse competitors for {company_name}")
            return []
        except Exception as e:
            logger.error(f"Competitor identification failed for {company_name}: {e}")
            return []
    
    def _calculate_confidence(
        self,
        news: List[NewsItem],
        funding: Optional[FundingInfo],
        tech_stack: List[str],
        pain_points: List[str],
        growth_signals: List[str]
    ) -> float:
        """
        Calculate confidence score based on data completeness
        
        Args:
            news: News items found
            funding: Funding information
            tech_stack: Technologies identified
            pain_points: Pain points identified
            growth_signals: Growth signals detected
            
        Returns:
            Confidence score between 0 and 1
        """
        score = 0.0
        
        # News contributes 30%
        if news:
            score += min(len(news) / 5, 1.0) * 0.30
            
        # Funding contributes 20%
        if funding:
            score += 0.20
            
        # Tech stack contributes 20%
        if tech_stack:
            score += min(len(tech_stack) / 10, 1.0) * 0.20
            
        # Pain points contribute 15%
        if pain_points:
            score += min(len(pain_points) / 5, 1.0) * 0.15
            
        # Growth signals contribute 15%
        if growth_signals:
            score += min(len(growth_signals) / 5, 1.0) * 0.15
            
        return min(score, 1.0)