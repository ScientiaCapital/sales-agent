"""
LinkedIn Content Scraping Tools for LangGraph Agents

Provides comprehensive LinkedIn content scraping tools for company pages,
personal profiles, and ATL contact activity tracking using Browserbase automation.

Features:
- Company page posts and updates scraping
- Personal profile posts and activity scraping
- ATL contact LinkedIn activity monitoring
- Company employee posts discovery
- Content engagement metrics collection
- Post sentiment analysis with Cerebras AI

Usage:
    ```python
    from app.services.langgraph.tools import get_linkedin_content_tools
    from langgraph.prebuilt import create_react_agent

    tools = get_linkedin_content_tools()
    agent = create_react_agent(llm, tools)
    ```
"""

import os
import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field

from langchain.tools import tool
from langchain_core.exceptions import ToolException

from app.services.linkedin_scraper import LinkedInScraper
from app.services.cerebras import CerebrasService
from app.core.exceptions import MissingAPIKeyError

logger = logging.getLogger(__name__)

# ========== Input Schemas ==========

class LinkedInCompanyPostsInput(BaseModel):
    """Input schema for LinkedIn company posts scraping."""
    company_linkedin_url: str = Field(description="LinkedIn company page URL")
    max_posts: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum number of posts to scrape (1-100)"
    )
    days_back: int = Field(
        default=30,
        ge=1,
        le=90,
        description="Days back to scrape posts (1-90)"
    )
    include_engagement: bool = Field(
        default=True,
        description="Include engagement metrics (likes, comments, shares)"
    )

class LinkedInProfilePostsInput(BaseModel):
    """Input schema for LinkedIn profile posts scraping."""
    profile_url: str = Field(description="LinkedIn profile URL")
    max_posts: int = Field(
        default=15,
        ge=1,
        le=50,
        description="Maximum number of posts to scrape (1-50)"
    )
    days_back: int = Field(
        default=30,
        ge=1,
        le=90,
        description="Days back to scrape posts (1-90)"
    )
    include_engagement: bool = Field(
        default=True,
        description="Include engagement metrics"
    )

class ATLContactActivityInput(BaseModel):
    """Input schema for ATL contact LinkedIn activity tracking."""
    contact_linkedin_url: str = Field(description="ATL contact's LinkedIn profile URL")
    company_linkedin_url: str = Field(description="Company's LinkedIn page URL")
    max_posts: int = Field(
        default=10,
        ge=1,
        le=30,
        description="Maximum posts per contact (1-30)"
    )
    days_back: int = Field(
        default=14,
        ge=1,
        le=30,
        description="Days back to track activity (1-30)"
    )

class LinkedInContentAnalysisInput(BaseModel):
    """Input schema for LinkedIn content analysis."""
    posts: List[Dict[str, Any]] = Field(description="List of LinkedIn posts to analyze")
    analysis_type: str = Field(
        default="sentiment",
        description="Type of analysis: sentiment, topics, engagement, trends"
    )

# ========== Tool Implementations ==========

@tool(
    args_schema=LinkedInCompanyPostsInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def scrape_linkedin_company_posts_tool(
    company_linkedin_url: str,
    max_posts: int = 20,
    days_back: int = 30,
    include_engagement: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """Scrape LinkedIn company page posts and updates.

    This tool uses Browserbase automation to extract recent posts, updates,
    and content from a LinkedIn company page. Includes engagement metrics
    and post metadata for comprehensive analysis.

    Use this tool when you need to:
    - Monitor company's LinkedIn content strategy
    - Analyze company's social media engagement
    - Track company announcements and updates
    - Research competitor content performance
    - Discover company's thought leadership content

    Rate Limits:
    - 50 company page requests/day (conservative limit)
    - Rate limit status tracked in Redis

    Prerequisites:
    - BROWSERBASE_API_KEY in environment (for scraping automation)
    - BROWSERBASE_PROJECT_ID in environment
    - Company page must be publicly accessible

    Args:
        company_linkedin_url: LinkedIn company page URL (e.g., https://linkedin.com/company/acme-corp)
        max_posts: Maximum number of posts to scrape (1-100)
        days_back: Days back to scrape posts (1-90)
        include_engagement: Include engagement metrics (likes, comments, shares)

    Returns:
        Tuple of:
        - Success message with post summary (for LLM)
        - Artifact dict with complete post data (for downstream processing)

    Raises:
        ToolException: If scraping fails (rate limit, invalid URL, scraping error)

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [scrape_linkedin_company_posts_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Scrape Acme Corp's LinkedIn company posts from the last 30 days"
            )]
        })

        content, artifact = result
        print(content)  # "Successfully scraped 15 company posts..."
        print(artifact["posts"])  # List of post data
        ```
    """
    try:
        # Initialize LinkedIn scraper
        scraper = LinkedInScraper()
        
        if not scraper.browserbase_api_key:
            raise ToolException("BROWSERBASE_API_KEY not configured for LinkedIn scraping")
        
        # Validate company URL
        if not company_linkedin_url.startswith("https://linkedin.com/company/"):
            raise ToolException("Invalid LinkedIn company URL format")
        
        # Scrape company posts
        posts_data = await scraper.scrape_company_posts(
            company_url=company_linkedin_url,
            max_posts=max_posts,
            days_back=days_back,
            include_engagement=include_engagement
        )
        
        # Format response
        total_posts = len(posts_data.get("posts", []))
        avg_engagement = posts_data.get("avg_engagement", 0)
        
        content = f"Successfully scraped {total_posts} company posts from {company_linkedin_url}. "
        content += f"Average engagement: {avg_engagement:.1f} interactions per post."
        
        artifact = {
            "company_url": company_linkedin_url,
            "posts": posts_data.get("posts", []),
            "total_posts": total_posts,
            "avg_engagement": avg_engagement,
            "scraped_at": datetime.now().isoformat(),
            "metadata": posts_data.get("metadata", {})
        }
        
        return content, artifact
        
    except Exception as e:
        logger.error(f"LinkedIn company posts scraping failed: {e}")
        raise ToolException(f"Failed to scrape company posts: {str(e)}")


@tool(
    args_schema=LinkedInProfilePostsInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def scrape_linkedin_profile_posts_tool(
    profile_url: str,
    max_posts: int = 15,
    days_back: int = 30,
    include_engagement: bool = True
) -> Tuple[str, Dict[str, Any]]:
    """Scrape LinkedIn profile posts and activity.

    This tool uses Browserbase automation to extract recent posts and activity
    from a LinkedIn profile. Includes engagement metrics and post content
    for personal brand analysis.

    Use this tool when you need to:
    - Analyze individual's LinkedIn content strategy
    - Track personal brand engagement
    - Monitor thought leadership activity
    - Research individual's professional interests
    - Discover personal posts and updates

    Rate Limits:
    - 30 profile requests/day (conservative limit)
    - Rate limit status tracked in Redis

    Prerequisites:
    - BROWSERBASE_API_KEY in environment (for scraping automation)
    - BROWSERBASE_PROJECT_ID in environment
    - Profile must be publicly accessible

    Args:
        profile_url: LinkedIn profile URL (e.g., https://linkedin.com/in/johndoe)
        max_posts: Maximum number of posts to scrape (1-50)
        days_back: Days back to scrape posts (1-90)
        include_engagement: Include engagement metrics

    Returns:
        Tuple of:
        - Success message with post summary (for LLM)
        - Artifact dict with complete post data (for downstream processing)

    Raises:
        ToolException: If scraping fails (rate limit, invalid URL, scraping error)

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [scrape_linkedin_profile_posts_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Scrape John Doe's LinkedIn posts from the last 30 days"
            )]
        })

        content, artifact = result
        print(content)  # "Successfully scraped 12 profile posts..."
        print(artifact["posts"])  # List of post data
        ```
    """
    try:
        # Initialize LinkedIn scraper
        scraper = LinkedInScraper()
        
        if not scraper.browserbase_api_key:
            raise ToolException("BROWSERBASE_API_KEY not configured for LinkedIn scraping")
        
        # Validate profile URL
        if not profile_url.startswith("https://linkedin.com/in/"):
            raise ToolException("Invalid LinkedIn profile URL format")
        
        # Scrape profile posts
        posts_data = await scraper.scrape_profile_posts(
            profile_url=profile_url,
            max_posts=max_posts,
            days_back=days_back,
            include_engagement=include_engagement
        )
        
        # Format response
        total_posts = len(posts_data.get("posts", []))
        avg_engagement = posts_data.get("avg_engagement", 0)
        
        content = f"Successfully scraped {total_posts} profile posts from {profile_url}. "
        content += f"Average engagement: {avg_engagement:.1f} interactions per post."
        
        artifact = {
            "profile_url": profile_url,
            "posts": posts_data.get("posts", []),
            "total_posts": total_posts,
            "avg_engagement": avg_engagement,
            "scraped_at": datetime.now().isoformat(),
            "metadata": posts_data.get("metadata", {})
        }
        
        return content, artifact
        
    except Exception as e:
        logger.error(f"LinkedIn profile posts scraping failed: {e}")
        raise ToolException(f"Failed to scrape profile posts: {str(e)}")


@tool(
    args_schema=ATLContactActivityInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def track_atl_contact_linkedin_activity_tool(
    contact_linkedin_url: str,
    company_linkedin_url: str,
    max_posts: int = 10,
    days_back: int = 14
) -> Tuple[str, Dict[str, Any]]:
    """Track ATL contact's LinkedIn activity and company engagement.

    This tool monitors an ATL (Above The Line) contact's LinkedIn activity,
    including their personal posts and engagement with company content.
    Perfect for understanding contact's interests and engagement patterns.

    Use this tool when you need to:
    - Monitor ATL contact's LinkedIn activity
    - Track engagement with company content
    - Understand contact's professional interests
    - Identify conversation starters
    - Monitor thought leadership activity

    Rate Limits:
    - 20 ATL contact requests/day (conservative limit)
    - Rate limit status tracked in Redis

    Prerequisites:
    - BROWSERBASE_API_KEY in environment (for scraping automation)
    - BROWSERBASE_PROJECT_ID in environment
    - Both profile and company page must be publicly accessible

    Args:
        contact_linkedin_url: ATL contact's LinkedIn profile URL
        company_linkedin_url: Company's LinkedIn page URL
        max_posts: Maximum posts per contact (1-30)
        days_back: Days back to track activity (1-30)

    Returns:
        Tuple of:
        - Success message with activity summary (for LLM)
        - Artifact dict with complete activity data (for downstream processing)

    Raises:
        ToolException: If tracking fails (rate limit, invalid URL, scraping error)

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [track_atl_contact_linkedin_activity_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Track John Doe's LinkedIn activity with Acme Corp"
            )]
        })

        content, artifact = result
        print(content)  # "Tracked 8 posts and 3 company engagements..."
        print(artifact["activity_summary"])  # Activity summary
        ```
    """
    try:
        # Initialize LinkedIn scraper
        scraper = LinkedInScraper()
        
        if not scraper.browserbase_api_key:
            raise ToolException("BROWSERBASE_API_KEY not configured for LinkedIn scraping")
        
        # Validate URLs
        if not contact_linkedin_url.startswith("https://linkedin.com/in/"):
            raise ToolException("Invalid LinkedIn profile URL format")
        if not company_linkedin_url.startswith("https://linkedin.com/company/"):
            raise ToolException("Invalid LinkedIn company URL format")
        
        # Track ATL contact activity
        activity_data = await scraper.track_atl_contact_activity(
            contact_url=contact_linkedin_url,
            company_url=company_linkedin_url,
            max_posts=max_posts,
            days_back=days_back
        )
        
        # Format response
        personal_posts = len(activity_data.get("personal_posts", []))
        company_engagements = len(activity_data.get("company_engagements", []))
        
        content = f"Successfully tracked ATL contact activity: {personal_posts} personal posts, "
        content += f"{company_engagements} company engagements over {days_back} days."
        
        artifact = {
            "contact_url": contact_linkedin_url,
            "company_url": company_linkedin_url,
            "personal_posts": activity_data.get("personal_posts", []),
            "company_engagements": activity_data.get("company_engagements", []),
            "activity_summary": activity_data.get("summary", {}),
            "tracked_at": datetime.now().isoformat(),
            "metadata": activity_data.get("metadata", {})
        }
        
        return content, artifact
        
    except Exception as e:
        logger.error(f"ATL contact LinkedIn activity tracking failed: {e}")
        raise ToolException(f"Failed to track ATL contact activity: {str(e)}")


@tool(
    args_schema=LinkedInContentAnalysisInput,
    response_format="content_and_artifact",
    parse_docstring=True
)
async def analyze_linkedin_content_tool(
    posts: List[Dict[str, Any]],
    analysis_type: str = "sentiment"
) -> Tuple[str, Dict[str, Any]]:
    """Analyze LinkedIn content using Cerebras AI.

    This tool performs AI-powered analysis of LinkedIn posts including
    sentiment analysis, topic extraction, engagement patterns, and trend analysis.

    Use this tool when you need to:
    - Analyze sentiment of LinkedIn content
    - Extract key topics and themes
    - Identify engagement patterns
    - Discover content trends
    - Generate insights from post data

    Analysis Types:
    - sentiment: Sentiment analysis (positive, negative, neutral)
    - topics: Topic extraction and categorization
    - engagement: Engagement pattern analysis
    - trends: Trend identification and analysis

    Prerequisites:
    - CEREBRAS_API_KEY in environment (for AI analysis)

    Args:
        posts: List of LinkedIn posts to analyze
        analysis_type: Type of analysis (sentiment, topics, engagement, trends)

    Returns:
        Tuple of:
        - Success message with analysis summary (for LLM)
        - Artifact dict with complete analysis data (for downstream processing)

    Raises:
        ToolException: If analysis fails (API error, invalid data)

    Example:
        ```python
        from langgraph.prebuilt import create_react_agent

        agent = create_react_agent(llm, [analyze_linkedin_content_tool])

        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Analyze sentiment of these LinkedIn posts"
            )]
        })

        content, artifact = result
        print(content)  # "Analyzed 15 posts: 60% positive, 30% neutral, 10% negative"
        print(artifact["sentiment_analysis"])  # Detailed sentiment data
        ```
    """
    try:
        # Initialize Cerebras service
        cerebras = CerebrasService()
        
        if not cerebras.api_key:
            raise ToolException("CEREBRAS_API_KEY not configured for content analysis")
        
        # Perform analysis based on type
        if analysis_type == "sentiment":
            analysis_data = await cerebras.analyze_sentiment_batch(posts)
        elif analysis_type == "topics":
            analysis_data = await cerebras.extract_topics_batch(posts)
        elif analysis_type == "engagement":
            analysis_data = await cerebras.analyze_engagement_patterns(posts)
        elif analysis_type == "trends":
            analysis_data = await cerebras.identify_trends(posts)
        else:
            raise ToolException(f"Unsupported analysis type: {analysis_type}")
        
        # Format response
        total_posts = len(posts)
        analysis_summary = analysis_data.get("summary", {})
        
        content = f"Successfully analyzed {total_posts} LinkedIn posts using {analysis_type} analysis. "
        content += f"Key insights: {analysis_summary.get('key_insights', 'N/A')}"
        
        artifact = {
            "analysis_type": analysis_type,
            "total_posts": total_posts,
            "analysis_data": analysis_data,
            "analyzed_at": datetime.now().isoformat(),
            "metadata": analysis_data.get("metadata", {})
        }
        
        return content, artifact
        
    except Exception as e:
        logger.error(f"LinkedIn content analysis failed: {e}")
        raise ToolException(f"Failed to analyze LinkedIn content: {str(e)}")


# ========== Convenience Functions ==========

def get_linkedin_content_tools() -> List:
    """
    Get all LinkedIn content scraping tools.

    Returns:
        List of LinkedIn content tools: [
            scrape_linkedin_company_posts_tool,
            scrape_linkedin_profile_posts_tool,
            track_atl_contact_linkedin_activity_tool,
            analyze_linkedin_content_tool
        ]

    Example:
        ```python
        from app.services.langgraph.tools import get_linkedin_content_tools
        from langgraph.prebuilt import create_react_agent

        linkedin_tools = get_linkedin_content_tools()
        agent = create_react_agent(llm, linkedin_tools)

        # Agent can now scrape LinkedIn content and analyze it
        result = await agent.ainvoke({
            "messages": [HumanMessage(
                content="Scrape Acme Corp's LinkedIn posts and analyze sentiment"
            )]
        })
        ```
    """
    return [
        scrape_linkedin_company_posts_tool,
        scrape_linkedin_profile_posts_tool,
        track_atl_contact_linkedin_activity_tool,
        analyze_linkedin_content_tool
    ]
