"""
Social Network Research Agent - LangGraph StateGraph

Comprehensive social media research agent that discovers, analyzes, and synthesizes
content across Meta, X, Instagram, YouTube, and TikTok platforms.

Architecture:
    StateGraph with parallel platform research → sentiment analysis → content synthesis

Features:
- Multi-platform content discovery (Meta, X, Instagram, YouTube, TikTok)
- Real-time sentiment analysis with Cerebras AI
- Hashtag and trend research
- Influencer identification
- Content performance analysis
- Competitive intelligence gathering

Performance:
- Target: <5000ms for comprehensive research
- Parallel platform queries for efficiency
- Streaming support for real-time updates

Usage:
    ```python
    from app.services.langgraph.agents import SocialResearchAgent

    agent = SocialResearchAgent()
    result = await agent.research(
        company_name="TechCorp",
        research_depth="comprehensive",
        platforms=["twitter", "instagram", "youtube", "tiktok"]
    )

    print(f"Found {result.total_mentions} mentions")
    print(f"Sentiment: {result.overall_sentiment}")
    print(f"Top platforms: {result.top_platforms}")
    ```
"""

import os
import time
import asyncio
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.redis import RedisSaver as RedisCheckpointer
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.tools import tool

from app.services.langgraph.tools.social_media_tools import (
    search_social_media_tool,
    analyze_content_sentiment_tool,
    research_hashtags_tool
)
from app.services.cerebras import CerebrasService
from app.core.logging import setup_logging
from app.core.exceptions import CerebrasAPIError

logger = setup_logging(__name__)

# ========== State Schema ==========

class SocialResearchState(BaseModel):
    """State schema for social media research workflow."""
    # Input data
    company_name: str
    research_depth: Literal["quick", "standard", "comprehensive"] = "standard"
    platforms: List[str] = ["twitter", "reddit", "instagram", "youtube", "tiktok"]
    max_results_per_platform: int = 50
    days_back: int = 7
    
    # Research data
    platform_results: Dict[str, Any] = Field(default_factory=dict)
    all_content: List[Dict[str, Any]] = Field(default_factory=list)
    sentiment_analysis: Dict[str, Any] = Field(default_factory=dict)
    hashtag_research: Dict[str, Any] = Field(default_factory=dict)
    
    # Analysis results
    top_content: List[Dict[str, Any]] = Field(default_factory=list)
    key_insights: List[str] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    
    # Metadata
    current_step: str = "initializing"
    confidence_score: float = 0.0
    total_mentions: int = 0
    research_duration_ms: int = 0
    errors: List[str] = Field(default_factory=list)

# ========== Result Schema ==========

class SocialResearchResult(BaseModel):
    """Structured result for social media research."""
    company_name: str
    total_mentions: int
    platforms_researched: List[str]
    overall_sentiment: str
    sentiment_score: float
    top_platforms: List[Dict[str, Any]]
    top_content: List[Dict[str, Any]]
    trending_hashtags: List[Dict[str, Any]]
    key_insights: List[str]
    recommendations: List[str]
    research_metadata: Dict[str, Any]

# ========== Social Research Agent ==========

class SocialResearchAgent:
    """
    LangGraph StateGraph agent for comprehensive social media research.
    
    Workflow:
    1. Initialize research parameters
    2. Parallel platform research (Twitter, Instagram, YouTube, TikTok)
    3. Content sentiment analysis
    4. Hashtag and trend research
    5. Content synthesis and insights
    6. Generate recommendations
    """

    def __init__(
        self,
        model: str = "llama3.1-8b",
        temperature: float = 0.3,
        max_tokens: int = 500
    ):
        """
        Initialize Social Research Agent.
        
        Args:
            model: Cerebras model ID
            temperature: Sampling temperature
            max_tokens: Max completion tokens
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Initialize Cerebras service
        api_key = os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY environment variable not set")
        
        self.cerebras = CerebrasService()
        
        # Build StateGraph
        self.graph = self._build_graph()
        
        logger.info(f"SocialResearchAgent initialized: model={model}")

    def _build_graph(self) -> StateGraph:
        """Build LangGraph StateGraph for social media research."""
        
        # Create StateGraph
        graph = StateGraph(SocialResearchState)
        
        # Add nodes
        graph.add_node("initialize", self._initialize_research)
        graph.add_node("research_platforms", self._research_platforms)
        graph.add_node("analyze_sentiment", self._analyze_sentiment)
        graph.add_node("research_hashtags", self._research_hashtags)
        graph.add_node("synthesize_insights", self._synthesize_insights)
        graph.add_node("generate_recommendations", self._generate_recommendations)
        
        # Add edges
        graph.set_entry_point("initialize")
        graph.add_edge("initialize", "research_platforms")
        graph.add_edge("research_platforms", "analyze_sentiment")
        graph.add_edge("analyze_sentiment", "research_hashtags")
        graph.add_edge("research_hashtags", "synthesize_insights")
        graph.add_edge("synthesize_insights", "generate_recommendations")
        graph.add_edge("generate_recommendations", END)
        
        return graph.compile()

    async def _initialize_research(self, state: SocialResearchState) -> SocialResearchState:
        """Initialize research parameters and validate inputs."""
        logger.info(f"Initializing social research for '{state.company_name}'")
        
        state.current_step = "initializing"
        state.confidence_score = 0.0
        state.errors = []
        
        # Validate platforms
        valid_platforms = ["twitter", "reddit", "instagram", "youtube", "tiktok"]
        state.platforms = [p for p in state.platforms if p in valid_platforms]
        
        if not state.platforms:
            state.errors.append("No valid platforms specified")
            return state
        
        # Adjust parameters based on research depth
        if state.research_depth == "quick":
            state.max_results_per_platform = 20
            state.days_back = 3
        elif state.research_depth == "comprehensive":
            state.max_results_per_platform = 100
            state.days_back = 14
        
        logger.info(f"Research initialized: {len(state.platforms)} platforms, "
                   f"{state.max_results_per_platform} results each, {state.days_back} days back")
        
        return state

    async def _research_platforms(self, state: SocialResearchState) -> SocialResearchState:
        """Research all specified platforms in parallel."""
        logger.info(f"Researching platforms: {state.platforms}")
        
        state.current_step = "researching_platforms"
        start_time = time.time()
        
        try:
            # Use social media search tool
            content, artifact = await search_social_media_tool(
                company_name=state.company_name,
                platforms=state.platforms,
                max_results_per_platform=state.max_results_per_platform,
                days_back=state.days_back
            )
            
            # Store results
            state.platform_results = artifact["platform_results"]
            state.all_content = artifact["posts"]
            state.total_mentions = artifact["total_mentions"]
            state.sentiment_analysis = artifact["sentiment_analysis"]
            
            # Calculate confidence based on results
            successful_platforms = sum(1 for r in state.platform_results.values() if r["status"] == "success")
            state.confidence_score = successful_platforms / len(state.platforms)
            
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"Platform research complete: {state.total_mentions} mentions, "
                       f"{successful_platforms}/{len(state.platforms)} platforms, {duration_ms}ms")
            
        except Exception as e:
            error_msg = f"Platform research failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def _analyze_sentiment(self, state: SocialResearchState) -> SocialResearchState:
        """Analyze sentiment of discovered content."""
        logger.info("Analyzing content sentiment")
        
        state.current_step = "analyzing_sentiment"
        
        if not state.all_content:
            logger.warning("No content to analyze")
            return state
        
        try:
            # Analyze top content pieces
            top_content = state.all_content[:10]  # Analyze top 10 pieces
            
            sentiment_scores = []
            for content in top_content:
                try:
                    content_text = f"{content.get('title', '')} {content.get('text', '')}"
                    if content_text.strip():
                        content_result, analysis_data = await analyze_content_sentiment_tool(
                            content_text=content_text[:500],  # Limit length
                            platform=content.get("platform", "unknown"),
                            content_type="post"
                        )
                        sentiment_scores.append(analysis_data["sentiment_score"])
                except Exception as e:
                    logger.warning(f"Failed to analyze content sentiment: {e}")
                    continue
            
            # Calculate average sentiment
            if sentiment_scores:
                avg_sentiment = sum(sentiment_scores) / len(sentiment_scores)
                state.sentiment_analysis["detailed_analysis"] = {
                    "average_sentiment_score": avg_sentiment,
                    "content_analyzed": len(sentiment_scores),
                    "sentiment_distribution": {
                        "positive": len([s for s in sentiment_scores if s >= 70]),
                        "neutral": len([s for s in sentiment_scores if 40 <= s < 70]),
                        "negative": len([s for s in sentiment_scores if s < 40])
                    }
                }
            
            logger.info(f"Sentiment analysis complete: {len(sentiment_scores)} pieces analyzed")
            
        except Exception as e:
            error_msg = f"Sentiment analysis failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def _research_hashtags(self, state: SocialResearchState) -> SocialResearchState:
        """Research trending hashtags and keywords."""
        logger.info("Researching hashtags and trends")
        
        state.current_step = "researching_hashtags"
        
        try:
            # Research hashtags for the company/industry
            content, hashtag_data = await research_hashtags_tool(
                topic=state.company_name,
                platform="instagram",  # Start with Instagram, can be expanded
                max_hashtags=20
            )
            
            state.hashtag_research = hashtag_data
            
            logger.info(f"Hashtag research complete: {len(hashtag_data['trending_hashtags'])} hashtags found")
            
        except Exception as e:
            error_msg = f"Hashtag research failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def _synthesize_insights(self, state: SocialResearchState) -> SocialResearchState:
        """Synthesize insights from all research data."""
        logger.info("Synthesizing insights")
        
        state.current_step = "synthesizing_insights"
        
        try:
            # Prepare data for synthesis
            synthesis_prompt = f"""
            Synthesize insights from social media research for '{state.company_name}':

            Platform Results: {state.platform_results}
            Total Mentions: {state.total_mentions}
            Sentiment Analysis: {state.sentiment_analysis}
            Hashtag Research: {state.hashtag_research.get('trending_hashtags', [])}

            Provide:
            1. Top 3 key insights about the company's social media presence
            2. Top 5 most engaging content pieces
            3. Platform performance analysis
            4. Sentiment trends and patterns
            5. Content themes and topics
            """
            
            # Get synthesis from Cerebras
            score, reasoning, latency_ms = self.cerebras.qualify_lead(
                company_name="Social Media Synthesis",
                notes=synthesis_prompt
            )
            
            # Parse insights (simplified - in production, use more robust parsing)
            lines = reasoning.split('\n')
            insights = []
            current_section = None
            
            for line in lines:
                line = line.strip()
                if "key insights" in line.lower():
                    current_section = "insights"
                elif "engaging content" in line.lower():
                    current_section = "content"
                elif line.startswith(("1.", "2.", "3.", "4.", "5.")):
                    if current_section == "insights":
                        insights.append(line)
            
            state.key_insights = insights[:5]  # Top 5 insights
            
            # Select top content based on engagement
            state.top_content = sorted(
                state.all_content,
                key=lambda x: x.get("metrics", {}).get("likes", 0) + 
                             x.get("metrics", {}).get("retweets", 0) + 
                             x.get("metrics", {}).get("comments", 0),
                reverse=True
            )[:5]
            
            logger.info(f"Insights synthesis complete: {len(state.key_insights)} insights generated")
            
        except Exception as e:
            error_msg = f"Insights synthesis failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def _generate_recommendations(self, state: SocialResearchState) -> SocialResearchState:
        """Generate actionable recommendations."""
        logger.info("Generating recommendations")
        
        state.current_step = "generating_recommendations"
        
        try:
            # Generate recommendations based on research
            recommendations_prompt = f"""
            Generate actionable recommendations for '{state.company_name}' based on social media research:

            Key Insights: {state.key_insights}
            Platform Performance: {state.platform_results}
            Sentiment: {state.sentiment_analysis.get('overall_sentiment', 'unknown')}
            Trending Hashtags: {[h['hashtag'] for h in state.hashtag_research.get('trending_hashtags', [])]}

            Provide 5-7 specific, actionable recommendations for:
            1. Content strategy improvements
            2. Platform optimization
            3. Engagement tactics
            4. Hashtag strategy
            5. Sentiment management
            """
            
            # Get recommendations from Cerebras
            score, reasoning, latency_ms = self.cerebras.qualify_lead(
                company_name="Social Media Recommendations",
                notes=recommendations_prompt
            )
            
            # Parse recommendations (simplified)
            lines = reasoning.split('\n')
            recommendations = []
            
            for line in lines:
                line = line.strip()
                if line.startswith(("1.", "2.", "3.", "4.", "5.", "6.", "7.")):
                    recommendations.append(line)
            
            state.recommendations = recommendations[:7]  # Top 7 recommendations
            
            # Calculate final confidence
            if state.total_mentions > 0 and len(state.key_insights) > 0:
                state.confidence_score = min(1.0, state.confidence_score + 0.2)
            
            logger.info(f"Recommendations generated: {len(state.recommendations)} recommendations")
            
        except Exception as e:
            error_msg = f"Recommendations generation failed: {str(e)}"
            state.errors.append(error_msg)
            logger.error(error_msg, exc_info=True)
        
        return state

    async def research(
        self,
        company_name: str,
        research_depth: Literal["quick", "standard", "comprehensive"] = "standard",
        platforms: List[str] = None,
        max_results_per_platform: int = 50,
        days_back: int = 7
    ) -> tuple[SocialResearchResult, int, Dict[str, Any]]:
        """
        Perform comprehensive social media research.
        
        Args:
            company_name: Company name to research
            research_depth: Depth of research (quick/standard/comprehensive)
            platforms: List of platforms to research
            max_results_per_platform: Max results per platform
            days_back: Days back to search
            
        Returns:
            Tuple of (result, latency_ms, metadata)
        """
        if not company_name:
            raise ValueError("company_name is required")
        
        if platforms is None:
            platforms = ["twitter", "reddit", "instagram", "youtube", "tiktok"]
        
        # Initialize state
        initial_state = SocialResearchState(
            company_name=company_name,
            research_depth=research_depth,
            platforms=platforms,
            max_results_per_platform=max_results_per_platform,
            days_back=days_back
        )
        
        # Measure latency
        start_time = time.time()
        
        try:
            # Execute StateGraph
            final_state = await self.graph.ainvoke(initial_state)
            
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            # Build result
            result = SocialResearchResult(
                company_name=final_state.company_name,
                total_mentions=final_state.total_mentions,
                platforms_researched=final_state.platforms,
                overall_sentiment=final_state.sentiment_analysis.get("overall_sentiment", "unknown"),
                sentiment_score=final_state.sentiment_analysis.get("sentiment_score", 50.0),
                top_platforms=[
                    {"platform": k, "count": v["count"], "status": v["status"]}
                    for k, v in final_state.platform_results.items()
                ],
                top_content=final_state.top_content,
                trending_hashtags=final_state.hashtag_research.get("trending_hashtags", []),
                key_insights=final_state.key_insights,
                recommendations=final_state.recommendations,
                research_metadata={
                    "research_depth": final_state.research_depth,
                    "confidence_score": final_state.confidence_score,
                    "errors": final_state.errors,
                    "research_duration_ms": latency_ms
                }
            )
            
            # Build metadata
            metadata = {
                "model": self.model,
                "temperature": self.temperature,
                "latency_ms": latency_ms,
                "agent_type": "social_research",
                "langgraph_state": True,
                "platforms_researched": len(final_state.platforms),
                "total_mentions": final_state.total_mentions,
                "confidence_score": final_state.confidence_score,
                "errors_count": len(final_state.errors)
            }
            
            logger.info(
                f"Social research complete: company={company_name}, "
                f"mentions={final_state.total_mentions}, platforms={len(final_state.platforms)}, "
                f"latency={latency_ms}ms"
            )
            
            return result, latency_ms, metadata
            
        except Exception as e:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)
            
            logger.error(
                f"Social research failed: company={company_name}, "
                f"latency={latency_ms}ms, error={str(e)}",
                exc_info=True
            )
            
            raise CerebrasAPIError(
                message="Social media research failed",
                details={
                    "company_name": company_name,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

# ========== Exports ==========

__all__ = [
    "SocialResearchAgent",
    "SocialResearchResult",
    "SocialResearchState"
]
