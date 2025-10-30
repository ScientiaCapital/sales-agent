"""
LinkedIn Post Writer Agent - LCEL Chain

AI-powered LinkedIn content creation agent that generates engaging, professional
posts optimized for LinkedIn's algorithm and audience engagement.

Architecture:
    Input → ChatPromptTemplate → ChatCerebras → with_structured_output() → Result

Features:
- Industry-specific content generation
- Optimal posting time recommendations
- Hashtag optimization
- Engagement strategy suggestions
- Multiple post formats (text, carousel, video)
- A/B testing variations

Performance:
- Target: <2000ms for post generation
- Model: llama3.1-8b via Cerebras
- Cost: $0.000012 per post generation

Usage:
    ```python
    from app.services.langgraph.agents import LinkedInPostWriter

    agent = LinkedInPostWriter()
    result = await agent.write_post(
        topic="AI in Sales",
        industry="SaaS",
        post_type="educational",
        target_audience="sales professionals"
    )

    print(f"Post: {result.post_content}")
    print(f"Hashtags: {result.hashtags}")
    print(f"Best time: {result.optimal_posting_time}")
    ```
"""

import os
import time
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime, timedelta

from langchain_core.prompts import ChatPromptTemplate
from langchain_cerebras import ChatCerebras

from app.core.logging import setup_logging
from app.core.exceptions import CerebrasAPIError

logger = setup_logging(__name__)

# ========== Output Schema ==========

class LinkedInPostResult(BaseModel):
    """
    Structured output schema for LinkedIn post generation.
    
    Enforced by with_structured_output() - guarantees this structure
    without manual JSON parsing or error handling.
    """
    post_content: str = Field(
        description="Complete LinkedIn post content with proper formatting and structure"
    )
    
    headline: str = Field(
        description="Compelling headline or opening line for the post"
    )
    
    hashtags: List[str] = Field(
        description="Relevant hashtags optimized for LinkedIn (5-10 hashtags)"
    )
    
    post_type: str = Field(
        description="Type of post: educational, inspirational, industry_news, personal_story, or question"
    )
    
    target_audience: str = Field(
        description="Primary target audience for this post"
    )
    
    engagement_strategy: str = Field(
        description="Strategy to maximize engagement and reach"
    )
    
    optimal_posting_time: str = Field(
        description="Recommended posting time for maximum engagement"
    )
    
    call_to_action: str = Field(
        description="Clear call-to-action to encourage engagement"
    )
    
    estimated_engagement: str = Field(
        description="Estimated engagement level: high, medium, or low"
    )
    
    content_variations: List[str] = Field(
        default_factory=list,
        description="2-3 alternative versions for A/B testing"
    )
    
    industry_insights: List[str] = Field(
        default_factory=list,
        description="Key industry insights included in the post"
    )

# ========== LinkedIn Post Writer Agent ==========

class LinkedInPostWriter:
    """
    LCEL-based LinkedIn post generation agent using Cerebras for fast content creation.
    
    Patterns:
        - LCEL chain composition with | operator
        - with_structured_output() for Pydantic validation
        - Async-first design with ainvoke()
        - Built-in LangSmith tracing
    
    Content Types:
        - Educational: How-to guides, tips, best practices
        - Inspirational: Motivational content, success stories
        - Industry News: Breaking news, trends, analysis
        - Personal Story: Behind-the-scenes, lessons learned
        - Question: Engagement-driving questions, polls
    """

    def __init__(
        self,
        model: str = "llama3.1-8b",
        temperature: float = 0.7,
        max_tokens: int = 400
    ):
        """
        Initialize LinkedIn Post Writer with Cerebras LLM.
        
        Args:
            model: Cerebras model ID (default: llama3.1-8b)
            temperature: Sampling temperature (0.7 for creative content)
            max_tokens: Max completion tokens (400 for detailed posts)
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

        # Initialize Cerebras LLM via langchain-cerebras
        api_key = os.getenv("CEREBRAS_API_KEY")
        if not api_key:
            raise ValueError("CEREBRAS_API_KEY environment variable not set")

        self.llm = ChatCerebras(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            api_key=api_key
        )

        # Build LCEL chain with structured output
        self.chain = self._build_chain()

        logger.info(
            f"LinkedInPostWriter initialized: model={model}, "
            f"temperature={temperature}, max_tokens={max_tokens}"
        )

    def _build_chain(self):
        """
        Build LCEL chain: prompt | llm.with_structured_output()
        
        Returns:
            Compiled LCEL chain ready for invocation
        """
        # System prompt for LinkedIn content creation
        system_prompt = """You are an expert LinkedIn content creator and social media strategist specializing in B2B professional content.

Create engaging, professional LinkedIn posts that drive meaningful engagement and establish thought leadership.

Content Guidelines:
1. **Professional Tone**: Maintain a professional yet approachable voice
2. **Value-First**: Always provide value to your audience
3. **Storytelling**: Use personal stories and experiences when relevant
4. **Actionable Insights**: Include practical takeaways and actionable advice
5. **Industry Relevance**: Ensure content is relevant to the target industry
6. **Engagement Focus**: Write content that encourages comments and shares

Post Structure:
- Compelling headline/opening line
- Clear value proposition
- Supporting details or story
- Key insights or takeaways
- Strong call-to-action
- Relevant hashtags (5-10)

Content Types:
- Educational: How-to guides, tips, best practices, tutorials
- Inspirational: Success stories, motivational content, career advice
- Industry News: Breaking news, trends, market analysis, predictions
- Personal Story: Behind-the-scenes, lessons learned, experiences
- Question: Engagement-driving questions, polls, discussion starters

Hashtag Strategy:
- Mix of popular and niche hashtags
- Industry-specific tags
- Trending relevant tags
- Brand or personal tags
- 5-10 hashtags total

Optimal Posting Times (LinkedIn):
- Tuesday-Thursday: 8-10 AM, 12-2 PM, 5-6 PM
- Monday: 8-10 AM, 12-2 PM
- Friday: 8-10 AM, 12-1 PM
- Avoid: Weekends, late evenings, early mornings

Provide structured output with all required fields for comprehensive LinkedIn post creation."""

        # User prompt template
        user_prompt_template = """Create a LinkedIn post with these specifications:

Topic: {topic}
Industry: {industry}
Post Type: {post_type}
Target Audience: {target_audience}
{optional_context}

Requirements:
- Write engaging, professional content
- Include relevant hashtags (5-10)
- Provide optimal posting time
- Include call-to-action
- Create 2-3 content variations for A/B testing
- Focus on {post_type} content style

Generate a complete LinkedIn post with all required elements."""

        # Create ChatPromptTemplate
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ("user", user_prompt_template)
        ])

        # Build LCEL chain with structured output
        chain = prompt | self.llm.with_structured_output(LinkedInPostResult)

        return chain

    def _format_optional_context(
        self,
        company_name: Optional[str] = None,
        personal_story: Optional[str] = None,
        key_points: Optional[List[str]] = None,
        current_trends: Optional[List[str]] = None,
        target_engagement: Optional[str] = None
    ) -> str:
        """Format optional context for prompt."""
        context_parts = []

        if company_name:
            context_parts.append(f"Company: {company_name}")
        if personal_story:
            context_parts.append(f"Personal Story: {personal_story}")
        if key_points:
            context_parts.append(f"Key Points: {', '.join(key_points)}")
        if current_trends:
            context_parts.append(f"Current Trends: {', '.join(current_trends)}")
        if target_engagement:
            context_parts.append(f"Target Engagement: {target_engagement}")

        return "\n".join(context_parts) if context_parts else "No additional context provided."

    async def write_post(
        self,
        topic: str,
        industry: str,
        post_type: Literal["educational", "inspirational", "industry_news", "personal_story", "question"] = "educational",
        target_audience: str = "professionals",
        company_name: Optional[str] = None,
        personal_story: Optional[str] = None,
        key_points: Optional[List[str]] = None,
        current_trends: Optional[List[str]] = None,
        target_engagement: Optional[str] = None
    ) -> tuple[LinkedInPostResult, int, Dict[str, Any]]:
        """
        Generate a LinkedIn post using LCEL chain with Cerebras inference.
        
        Args:
            topic: Main topic or subject of the post
            industry: Target industry (SaaS, FinTech, Healthcare, etc.)
            post_type: Type of content to create
            target_audience: Primary audience (sales professionals, executives, etc.)
            company_name: Company name (optional)
            personal_story: Personal story or experience (optional)
            key_points: Key points to include (optional)
            current_trends: Current industry trends (optional)
            target_engagement: Target engagement level (optional)
            
        Returns:
            Tuple of (result, latency_ms, metadata):
                - result: LinkedInPostResult with all fields populated
                - latency_ms: End-to-end latency in milliseconds
                - metadata: Dict with model, tokens, cost, etc.
                
        Raises:
            CerebrasAPIError: If Cerebras API call fails
            ValueError: If topic is empty
            
        Example:
            >>> agent = LinkedInPostWriter()
            >>> result, latency, meta = await agent.write_post(
            ...     topic="AI in Sales",
            ...     industry="SaaS",
            ...     post_type="educational",
            ...     target_audience="sales professionals"
            ... )
            >>> print(f"Post: {result.post_content}")
        """
        if not topic:
            raise ValueError("topic is required")

        # Format optional context
        optional_context = self._format_optional_context(
            company_name=company_name,
            personal_story=personal_story,
            key_points=key_points,
            current_trends=current_trends,
            target_engagement=target_engagement
        )

        # Measure latency
        start_time = time.time()

        try:
            # Invoke LCEL chain (async)
            result: LinkedInPostResult = await self.chain.ainvoke({
                "topic": topic,
                "industry": industry,
                "post_type": post_type,
                "target_audience": target_audience,
                "optional_context": optional_context
            })

            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            # Build metadata
            metadata = {
                "model": self.model,
                "temperature": self.temperature,
                "latency_ms": latency_ms,
                "agent_type": "linkedin_post_writer",
                "lcel_chain": True,
                "post_type": post_type,
                "industry": industry,
                "target_audience": target_audience,
                # Cost calculation (Cerebras pricing: $0.10/M tokens input+output)
                # Estimated 200 tokens input + 200 tokens output = 400 tokens
                "estimated_tokens": 400,
                "estimated_cost_usd": 0.00004  # (400 / 1_000_000) * 0.10
            }

            logger.info(
                f"LinkedIn post generated successfully: topic={topic}, "
                f"type={post_type}, industry={industry}, latency={latency_ms}ms"
            )

            return result, latency_ms, metadata

        except Exception as e:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            logger.error(
                f"LinkedIn post generation failed: topic={topic}, "
                f"latency={latency_ms}ms, error={str(e)}",
                exc_info=True
            )

            raise CerebrasAPIError(
                message="LinkedIn post generation failed",
                details={
                    "topic": topic,
                    "industry": industry,
                    "post_type": post_type,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

    async def write_post_batch(
        self,
        post_requests: List[Dict[str, Any]],
        max_concurrency: int = 3
    ) -> List[tuple[LinkedInPostResult, int, Dict[str, Any]]]:
        """
        Generate multiple LinkedIn posts in parallel.
        
        Args:
            post_requests: List of post request dicts with topic, industry, etc.
            max_concurrency: Maximum concurrent API calls (default: 3)
            
        Returns:
            List of (result, latency_ms, metadata) tuples
            
        Example:
            >>> requests = [
            ...     {"topic": "AI in Sales", "industry": "SaaS", "post_type": "educational"},
            ...     {"topic": "Remote Work", "industry": "Tech", "post_type": "inspirational"}
            ... ]
            >>> results = await agent.write_post_batch(requests)
        """
        import asyncio

        # Create tasks with concurrency limit
        semaphore = asyncio.Semaphore(max_concurrency)

        async def write_with_semaphore(request: Dict[str, Any]):
            async with semaphore:
                return await self.write_post(**request)

        tasks = [write_with_semaphore(request) for request in post_requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Filter out exceptions and log them
        successful_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch post generation failed for request {i}: {result}")
            else:
                successful_results.append(result)

        return successful_results

    async def optimize_post(
        self,
        existing_post: str,
        optimization_goal: Literal["engagement", "reach", "clicks", "comments"] = "engagement"
    ) -> tuple[LinkedInPostResult, int, Dict[str, Any]]:
        """
        Optimize an existing LinkedIn post for better performance.
        
        Args:
            existing_post: Current post content to optimize
            optimization_goal: What to optimize for
            
        Returns:
            Tuple of (optimized_result, latency_ms, metadata)
        """
        optimization_prompt = f"""
        Optimize this LinkedIn post for {optimization_goal}:

        Current Post:
        {existing_post}

        Optimization Goals:
        - Improve {optimization_goal}
        - Maintain professional tone
        - Keep original message intact
        - Add engaging elements
        - Optimize hashtags
        - Improve call-to-action

        Provide the optimized version with all LinkedIn post elements.
        """

        # Use the same chain but with optimization prompt
        start_time = time.time()

        try:
            # Create a temporary chain for optimization
            from langchain_core.prompts import ChatPromptTemplate
            
            opt_prompt = ChatPromptTemplate.from_messages([
                ("system", "You are a LinkedIn optimization expert. Improve posts for better performance while maintaining their core message."),
                ("user", optimization_prompt)
            ])
            
            opt_chain = opt_prompt | self.llm.with_structured_output(LinkedInPostResult)
            
            result: LinkedInPostResult = await opt_chain.ainvoke({
                "optimization_goal": optimization_goal,
                "existing_post": existing_post
            })

            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            metadata = {
                "model": self.model,
                "optimization_goal": optimization_goal,
                "latency_ms": latency_ms,
                "agent_type": "linkedin_post_optimizer",
                "estimated_tokens": 300,
                "estimated_cost_usd": 0.00003
            }

            logger.info(f"Post optimization complete: goal={optimization_goal}, latency={latency_ms}ms")

            return result, latency_ms, metadata

        except Exception as e:
            end_time = time.time()
            latency_ms = int((end_time - start_time) * 1000)

            logger.error(f"Post optimization failed: {str(e)}", exc_info=True)
            raise CerebrasAPIError(
                message="Post optimization failed",
                details={
                    "optimization_goal": optimization_goal,
                    "latency_ms": latency_ms,
                    "error": str(e)
                }
            )

# ========== Exports ==========

__all__ = [
    "LinkedInPostWriter",
    "LinkedInPostResult"
]
