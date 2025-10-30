"""
Social Media Research Tools for LangGraph Agents

Provides LangChain-compatible tools for comprehensive social media research
across Meta, X, Instagram, YouTube, and TikTok platforms.

Features:
- Multi-platform content discovery
- Sentiment analysis with Cerebras AI
- Engagement metrics collection
- Hashtag and trend analysis
- Influencer identification
- Content performance tracking

Usage:
    ```python
    from app.services.langgraph.tools import get_social_media_tools
    from langgraph.prebuilt import create_react_agent

    tools = get_social_media_tools()
    agent = create_react_agent(llm, tools)
    ```
"""

import os
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from langchain.tools import tool

# Note: ToolException doesn't exist in langchain_core, using ValueError instead
class ToolException(ValueError):
    """Exception raised when a tool encounters an error."""
    pass

from app.services.social_media_scraper import SocialMediaScraper
from app.services.cerebras import CerebrasService
from app.core.exceptions import MissingAPIKeyError

logger = logging.getLogger(__name__)

# ========== Input Schemas ==========

class SocialMediaSearchInput(BaseModel):
    """Input schema for social media search operations."""
    company_name: str = Field(description="Company name to search for")
    platforms: List[str] = Field(
        default=["twitter", "reddit", "instagram", "youtube", "tiktok"],
        description="List of platforms to search (twitter, reddit, instagram, youtube, tiktok)"
    )
    max_results_per_platform: int = Field(
        default=50,
        ge=1,
        le=100,
        description="Maximum results per platform (1-100)"
    )
    days_back: int = Field(
        default=7,
        ge=1,
        le=30,
        description="Days back to search (1-30)"
    )

class ContentAnalysisInput(BaseModel):
    """Input schema for content analysis operations."""
    content_text: str = Field(description="Text content to analyze")
    platform: str = Field(description="Platform where content was found")
    content_type: str = Field(
        default="post",
        description="Type of content (post, comment, video, story)"
    )

class HashtagResearchInput(BaseModel):
    """Input schema for hashtag research operations."""
    topic: str = Field(description="Topic or industry to research hashtags for")
    platform: str = Field(
        default="instagram",
        description="Platform to research hashtags on"
    )
    max_hashtags: int = Field(
        default=20,
        ge=5,
        le=50,
        description="Maximum number of hashtags to return"
    )

# ========== Tool Implementations ==========

@tool(
    args_schema=SocialMediaSearchInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def search_social_media_tool(
    company_name: str,
    platforms: List[str] = ["twitter", "reddit", "instagram", "youtube", "tiktok"],
    max_results_per_platform: int = 50,
    days_back: int = 7
) -> Tuple[str, Dict[str, Any]]:
    """Search multiple social media platforms for company mentions and content.

    This tool performs comprehensive social media research across multiple platforms
    to discover brand mentions, content, engagement metrics, and sentiment analysis.

    Supported Platforms:
    - Twitter/X: Real-time tweets and mentions via API
    - Reddit: Posts and comments via PRAW API
    - Instagram: Posts and stories via web scraping (Browserbase)
    - YouTube: Videos and comments via YouTube Data API
    - TikTok: Videos and hashtags via web scraping (Browserbase)

    Use this tool when you need to:
    - Monitor brand mentions across social platforms
    - Analyze social media presence and engagement
    - Track content performance and sentiment
    - Discover user-generated content
    - Identify trending topics and hashtags
    - Research competitor social media activity

    Rate Limits:
    - Twitter: 300 requests/15min (bearer token)
    - Reddit: 60 requests/minute (PRAW)
    - Instagram: 200 requests/hour (scraping)
    - YouTube: 10,000 requests/day (API key)
    - TikTok: 100 requests/hour (scraping)

    Prerequisites:
    - TWITTER_BEARER_TOKEN for Twitter API
    - REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET for Reddit
    - BROWSERBASE_API_KEY for Instagram/TikTok scraping
    - YOUTUBE_API_KEY for YouTube Data API

    Args:
        company_name: Company name to search for
        platforms: List of platforms to search (default: all platforms)
        max_results_per_platform: Maximum results per platform (1-100)
        days_back: Days back to search (1-30)

    Returns:
        Tuple of:
        - Success message with summary statistics (for LLM)
        - Artifact dict with complete research data (for downstream processing)

    Raises:
        ToolException: If search fails or no platforms are available

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [search_social_media_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Research 'TechCorp' on social media across all platforms"
            )]
        })

        content, artifact = result
        print(content)  # "Found 150 mentions across 5 platforms..."
        print(artifact["sentiment_analysis"])  # Overall sentiment data
        ```
    """
    try:
        # Initialize social media scraper
        scraper = SocialMediaScraper()
        
        # Perform multi-platform search
        results = scraper.scrape_company_social(
            company_name=company_name,
            platforms=platforms,
            max_results_per_platform=max_results_per_platform
        )
        
        # Format success message
        total_mentions = results["total_mentions"]
        platform_counts = {k: v["count"] for k, v in results["platform_results"].items()}
        sentiment = results["sentiment_analysis"]["overall_sentiment"]
        
        success_message = (
            f"Successfully researched '{company_name}' across {len(platforms)} platforms. "
            f"Found {total_mentions} total mentions with {sentiment} sentiment. "
            f"Platform breakdown: {platform_counts}"
        )
        
        return success_message, results
        
    except Exception as e:
        logger.error(f"Social media search failed: {str(e)}", exc_info=True)
        raise ToolException(f"Social media search failed: {str(e)}")

@tool(
    args_schema=ContentAnalysisInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def analyze_content_sentiment_tool(
    content_text: str,
    platform: str,
    content_type: str = "post"
) -> Tuple[str, Dict[str, Any]]:
    """Analyze sentiment and engagement potential of social media content.

    This tool uses Cerebras AI to perform deep sentiment analysis on social media
    content, providing insights into emotional tone, engagement potential, and
    content quality assessment.

    Analysis includes:
    - Sentiment classification (positive, negative, neutral)
    - Emotional tone analysis (excitement, concern, satisfaction, etc.)
    - Engagement potential scoring (likelihood of likes, shares, comments)
    - Content quality assessment (clarity, relevance, authenticity)
    - Platform-specific optimization suggestions

    Use this tool when you need to:
    - Analyze sentiment of brand mentions or user content
    - Assess engagement potential of social media posts
    - Evaluate content quality and authenticity
    - Get platform-specific optimization recommendations
    - Monitor brand sentiment trends over time

    Args:
        content_text: Text content to analyze
        platform: Platform where content was found (twitter, instagram, etc.)
        content_type: Type of content (post, comment, video, story)

    Returns:
        Tuple of:
        - Analysis summary with key insights (for LLM)
        - Detailed analysis data (for downstream processing)

    Raises:
        ToolException: If analysis fails or Cerebras unavailable

    Example:
        ```python
        result = await analyze_content_sentiment_tool(
            content_text="Love this new product! Game changer!",
            platform="twitter",
            content_type="post"
        )
        
        content, analysis = result
        print(content)  # "Positive sentiment (85/100), high engagement potential..."
        print(analysis["sentiment_score"])  # 85
        ```
    """
    try:
        # Initialize Cerebras service
        try:
            cerebras = CerebrasService()
        except (ImportError, MissingAPIKeyError):
            raise ToolException("Cerebras service unavailable for sentiment analysis")
        
        # Create analysis prompt
        analysis_prompt = f"""
        Analyze this {platform} {content_type} for sentiment and engagement potential:

        Content: "{content_text}"

        Provide analysis in this format:
        1. Sentiment Score (0-100): [score]
        2. Emotional Tone: [primary emotion]
        3. Engagement Potential (0-100): [score]
        4. Content Quality (0-100): [score]
        5. Key Insights: [2-3 bullet points]
        6. Platform Optimization: [specific suggestions for {platform}]
        """
        
        # Get analysis from Cerebras
        score, reasoning, latency_ms = cerebras.qualify_lead(
            company_name="Content Analysis",
            notes=analysis_prompt
        )
        
        # Parse the reasoning to extract structured data
        # This is a simplified parser - in production, you'd want more robust parsing
        lines = reasoning.split('\n')
        sentiment_score = score
        emotional_tone = "neutral"
        engagement_potential = score
        content_quality = score
        
        for line in lines:
            if "Emotional Tone:" in line:
                emotional_tone = line.split(":")[-1].strip()
            elif "Engagement Potential" in line:
                try:
                    engagement_potential = int(line.split(":")[-1].strip().split()[0])
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse engagement potential: {e}")
            elif "Content Quality" in line:
                try:
                    content_quality = int(line.split(":")[-1].strip().split()[0])
                except (ValueError, IndexError) as e:
                    logger.warning(f"Failed to parse content quality: {e}")
        
        # Determine overall sentiment
        if sentiment_score >= 70:
            overall_sentiment = "positive"
        elif sentiment_score >= 40:
            overall_sentiment = "neutral"
        else:
            overall_sentiment = "negative"
        
        # Build analysis result
        analysis_data = {
            "sentiment_score": sentiment_score,
            "overall_sentiment": overall_sentiment,
            "emotional_tone": emotional_tone,
            "engagement_potential": engagement_potential,
            "content_quality": content_quality,
            "platform": platform,
            "content_type": content_type,
            "analysis_latency_ms": latency_ms,
            "detailed_reasoning": reasoning,
            "timestamp": datetime.now().isoformat()
        }
        
        success_message = (
            f"Content analysis complete: {overall_sentiment} sentiment ({sentiment_score}/100), "
            f"engagement potential {engagement_potential}/100, quality {content_quality}/100. "
            f"Emotional tone: {emotional_tone}"
        )
        
        return success_message, analysis_data
        
    except Exception as e:
        logger.error(f"Content sentiment analysis failed: {str(e)}", exc_info=True)
        raise ToolException(f"Content sentiment analysis failed: {str(e)}")

@tool(
    args_schema=HashtagResearchInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def research_hashtags_tool(
    topic: str,
    platform: str = "instagram",
    max_hashtags: int = 20
) -> Tuple[str, Dict[str, Any]]:
    """Research trending hashtags and keywords for a specific topic or industry.

    This tool discovers relevant hashtags, trending keywords, and content themes
    for social media marketing and content strategy development.

    Research includes:
    - Trending hashtags related to the topic
    - Popular keywords and phrases
    - Content theme suggestions
    - Platform-specific hashtag strategies
    - Competitor hashtag analysis
    - Engagement potential scoring

    Use this tool when you need to:
    - Find trending hashtags for content marketing
    - Research keywords for social media campaigns
    - Discover content themes and topics
    - Optimize hashtag strategies for specific platforms
    - Analyze competitor hashtag usage

    Args:
        topic: Topic or industry to research hashtags for
        platform: Platform to research hashtags on (instagram, twitter, tiktok)
        max_hashtags: Maximum number of hashtags to return (5-50)

    Returns:
        Tuple of:
        - Hashtag research summary (for LLM)
        - Complete hashtag data and recommendations (for downstream processing)

    Raises:
        ToolException: If hashtag research fails

    Example:
        ```python
        result = await research_hashtags_tool(
            topic="artificial intelligence",
            platform="instagram",
            max_hashtags=15
        )
        
        content, hashtags = result
        print(content)  # "Found 15 trending hashtags for AI on Instagram..."
        print(hashtags["trending_hashtags"])  # List of hashtag data
        ```
    """
    try:
        # Initialize Cerebras for hashtag research
        try:
            cerebras = CerebrasService()
        except (ImportError, MissingAPIKeyError):
            raise ToolException("Cerebras service unavailable for hashtag research")
        
        # Create hashtag research prompt
        research_prompt = f"""
        Research trending hashtags and keywords for "{topic}" on {platform}.

        Provide {max_hashtags} relevant hashtags in this format:
        
        Trending Hashtags:
        #hashtag1 - [engagement level] - [description]
        #hashtag2 - [engagement level] - [description]
        ...
        
        Popular Keywords:
        - keyword1 (high volume)
        - keyword2 (medium volume)
        ...
        
        Content Themes:
        - theme1: [description]
        - theme2: [description]
        ...
        
        Platform Strategy:
        - Best posting times for {platform}
        - Optimal hashtag count
        - Content format recommendations
        """
        
        # Get research from Cerebras
        score, reasoning, latency_ms = cerebras.qualify_lead(
            company_name="Hashtag Research",
            notes=research_prompt
        )
        
        # Parse hashtags from reasoning (simplified parser)
        lines = reasoning.split('\n')
        trending_hashtags = []
        popular_keywords = []
        content_themes = []
        
        current_section = None
        for line in lines:
            line = line.strip()
            if "Trending Hashtags:" in line:
                current_section = "hashtags"
            elif "Popular Keywords:" in line:
                current_section = "keywords"
            elif "Content Themes:" in line:
                current_section = "themes"
            elif line.startswith("#") and current_section == "hashtags":
                # Parse hashtag line: #hashtag - level - description
                parts = line.split(" - ", 2)
                if len(parts) >= 2:
                    hashtag_data = {
                        "hashtag": parts[0],
                        "engagement_level": parts[1] if len(parts) > 1 else "medium",
                        "description": parts[2] if len(parts) > 2 else "",
                        "platform": platform
                    }
                    trending_hashtags.append(hashtag_data)
            elif line.startswith("- ") and current_section == "keywords":
                keyword = line[2:].split(" (")[0]  # Remove "- " and volume info
                popular_keywords.append(keyword)
            elif line.startswith("- ") and current_section == "themes":
                theme = line[2:].split(":")[0]  # Remove "- " and description
                content_themes.append(theme)
        
        # Build research result
        research_data = {
            "topic": topic,
            "platform": platform,
            "trending_hashtags": trending_hashtags[:max_hashtags],
            "popular_keywords": popular_keywords,
            "content_themes": content_themes,
            "research_latency_ms": latency_ms,
            "full_analysis": reasoning,
            "timestamp": datetime.now().isoformat()
        }
        
        success_message = (
            f"Hashtag research complete for '{topic}' on {platform}. "
            f"Found {len(trending_hashtags)} trending hashtags, "
            f"{len(popular_keywords)} keywords, and {len(content_themes)} content themes."
        )
        
        return success_message, research_data
        
    except Exception as e:
        logger.error(f"Hashtag research failed: {str(e)}", exc_info=True)
        raise ToolException(f"Hashtag research failed: {str(e)}")

# ========== Convenience Functions ==========

def get_social_media_tools() -> List:
    """
    Get all social media research tools.
    
    Returns:
        List of LangChain tools for social media research
    """
    return [
        search_social_media_tool,
        analyze_content_sentiment_tool,
        research_hashtags_tool
    ]

def get_platform_specific_tools(platform: str) -> List:
    """
    Get tools specific to a platform.
    
    Args:
        platform: Platform name (twitter, instagram, youtube, tiktok)
        
    Returns:
        List of platform-specific tools
    """
    # All tools work across platforms, but you could add platform-specific tools here
    return get_social_media_tools()

# ========== Exports ==========

__all__ = [
    "search_social_media_tool",
    "analyze_content_sentiment_tool", 
    "research_hashtags_tool",
    "get_social_media_tools",
    "get_platform_specific_tools",
    "SocialMediaSearchInput",
    "ContentAnalysisInput",
    "HashtagResearchInput"
]
