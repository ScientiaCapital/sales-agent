"""
Context Analyzer Service

Analyzes social media posts using AI to extract pain points, urgency signals,
and talking points. Uses intelligent model tiering (DeepSeek for simple analysis,
Claude Sonnet 4 for complex reasoning).
"""

import asyncio
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional, Any

import httpx
import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class ContextAnalyzer:
    """
    AI-powered social media post analyzer.

    Features:
    - Intelligent model tiering (DeepSeek for simple, Claude for complex)
    - Extracts pain points, urgency signals, and talking points
    - Quality scoring (1-10 for prioritization)
    - Parallel batch processing

    Model Selection Logic:
    - DeepSeek ($0.00027/1K tokens): Simple posts (<200 chars, straightforward content)
    - Claude Sonnet 4 ($0.001743/1K tokens): Complex posts (>200 chars, nuanced content)

    Performance:
    - ~1-2 seconds per post (DeepSeek)
    - ~3-4 seconds per post (Claude)
    - Target: 50 posts analyzed in <3 minutes (parallel batches)
    """

    DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"
    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"

    SIMPLE_POST_THRESHOLD = 200  # Character count
    BATCH_SIZE = 5  # Parallel analysis

    def __init__(
        self,
        deepseek_api_key: str,
        anthropic_api_key: str,
        database_url: str
    ):
        """
        Initialize context analyzer.

        Args:
            deepseek_api_key: DeepSeek API key
            anthropic_api_key: Anthropic API key
            database_url: Supabase PostgreSQL connection string
        """
        self.deepseek_key = deepseek_api_key
        self.anthropic_key = anthropic_api_key
        self.database_url = database_url

    async def analyze_posts(
        self,
        post_ids: List[int]
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple social media posts in parallel.

        Args:
            post_ids: List of social_posts table IDs

        Returns:
            List of analysis results with fields:
            - post_id: ID of the post
            - pain_points: List of extracted pain points
            - urgency_signals: List of urgency indicators
            - talking_points: List of conversation starters
            - quality_score: 1-10 (10 = highest priority)
            - model_used: 'deepseek' or 'claude'
        """
        logger.info(f"Analyzing {len(post_ids)} social media posts...")

        # Fetch posts from database
        posts = await self._fetch_posts(post_ids)

        if not posts:
            logger.warning("No posts found to analyze")
            return []

        # Batch analysis
        all_results = []

        for i in range(0, len(posts), self.BATCH_SIZE):
            batch = posts[i:i + self.BATCH_SIZE]

            tasks = [self._analyze_single_post(post) for post in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Analysis error: {result}")
                elif result:
                    all_results.append(result)

        # Save analysis results to database
        await self._save_analysis(all_results)

        logger.info(f"Analyzed {len(all_results)} posts successfully")
        return all_results

    async def _fetch_posts(self, post_ids: List[int]) -> List[Dict[str, Any]]:
        """Fetch posts from database by IDs."""
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url,
                row_factory=dict_row
            ) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT id, contact_id, platform, post_text, post_url, posted_at
                        FROM social_posts
                        WHERE id = ANY(%s)
                          AND ai_analysis IS NULL
                    """, (post_ids,))

                    posts = await cur.fetchall()
                    return [dict(post) for post in posts]

        except Exception as e:
            logger.error(f"Error fetching posts: {e}")
            return []

    async def _analyze_single_post(
        self,
        post: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze a single social media post using AI.

        Args:
            post: Post dictionary from database

        Returns:
            Analysis result dictionary
        """
        try:
            post_text = post['post_text']
            post_length = len(post_text)

            # Select model based on complexity
            if post_length < self.SIMPLE_POST_THRESHOLD:
                model_used = 'deepseek'
                analysis = await self._analyze_with_deepseek(post_text)
            else:
                model_used = 'claude'
                analysis = await self._analyze_with_claude(post_text)

            if not analysis:
                logger.warning(f"No analysis returned for post {post['id']}")
                return None

            return {
                'post_id': post['id'],
                'contact_id': post['contact_id'],
                'platform': post['platform'],
                'pain_points': analysis.get('pain_points', []),
                'urgency_signals': analysis.get('urgency_signals', []),
                'talking_points': analysis.get('talking_points', []),
                'quality_score': analysis.get('quality_score', 5),
                'model_used': model_used
            }

        except Exception as e:
            logger.error(f"Error analyzing post {post['id']}: {e}")
            return None

    async def _analyze_with_deepseek(
        self,
        post_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze post with DeepSeek (cost-effective for simple content).

        Cost: $0.27/1M input tokens, $1.10/1M output tokens
        """
        try:
            prompt = self._build_analysis_prompt(post_text)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.DEEPSEEK_API_URL,
                    headers={
                        "Authorization": f"Bearer {self.deepseek_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "deepseek-chat",
                        "messages": [
                            {"role": "system", "content": "You are a sales intelligence AI that analyzes social media posts."},
                            {"role": "user", "content": prompt}
                        ],
                        "temperature": 0.3,
                        "max_tokens": 500
                    }
                )

                response.raise_for_status()
                data = response.json()

                # Parse JSON response
                content = data['choices'][0]['message']['content']
                analysis = json.loads(content)

                logger.info(f"DeepSeek analysis complete (${data.get('usage', {}).get('total_tokens', 0) * 0.00000027:.6f})")
                return analysis

        except Exception as e:
            logger.error(f"DeepSeek analysis error: {e}")
            return None

    async def _analyze_with_claude(
        self,
        post_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Analyze post with Claude Sonnet 4 (premium for complex content).

        Cost: $3.00/1M input tokens, $15.00/1M output tokens
        """
        try:
            prompt = self._build_analysis_prompt(post_text)

            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.ANTHROPIC_API_URL,
                    headers={
                        "x-api-key": self.anthropic_key,
                        "anthropic-version": "2023-06-01",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "claude-sonnet-4-5-20250929",
                        "max_tokens": 1000,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    }
                )

                response.raise_for_status()
                data = response.json()

                # Parse JSON response
                content = data['content'][0]['text']
                analysis = json.loads(content)

                logger.info(f"Claude analysis complete (${data.get('usage', {}).get('input_tokens', 0) * 0.000003:.6f})")
                return analysis

        except Exception as e:
            logger.error(f"Claude analysis error: {e}")
            return None

    def _build_analysis_prompt(self, post_text: str) -> str:
        """Build standardized analysis prompt for AI models."""
        return f"""Analyze this social media post for sales intelligence:

"{post_text}"

Extract the following as JSON:
1. pain_points (list): Business problems or challenges mentioned
2. urgency_signals (list): Time-sensitive keywords (e.g., "ASAP", "urgent", "deadline")
3. talking_points (list): Specific topics to mention in outreach
4. quality_score (int 1-10): Priority for sales outreach (10 = highest)

Example output:
{{
  "pain_points": ["struggling with lead generation", "manual data entry"],
  "urgency_signals": ["need solution by Q1"],
  "talking_points": ["automation ROI", "CRM integration"],
  "quality_score": 8
}}

Return only valid JSON. No explanation."""

    async def _save_analysis(
        self,
        results: List[Dict[str, Any]]
    ) -> int:
        """
        Save analysis results to database.

        Args:
            results: List of analysis result dictionaries

        Returns:
            Number of results saved
        """
        if not results:
            return 0

        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url,
                row_factory=dict_row
            ) as conn:
                async with conn.cursor() as cur:
                    for result in results:
                        # Update social_posts table with analysis
                        await cur.execute("""
                            UPDATE social_posts
                            SET ai_analysis = %s,
                                quality_score = %s
                            WHERE id = %s
                        """, (
                            json.dumps({
                                'pain_points': result['pain_points'],
                                'urgency_signals': result['urgency_signals'],
                                'talking_points': result['talking_points'],
                                'model_used': result['model_used']
                            }),
                            result['quality_score'],
                            result['post_id']
                        ))

                    await conn.commit()

            logger.info(f"Saved {len(results)} analysis results to database")
            return len(results)

        except Exception as e:
            logger.error(f"Error saving analysis results: {e}")
            return 0


# Example usage for testing
async def main():
    """Test context analyzer locally."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    deepseek_key = os.getenv('DEEPSEEK_API_KEY')
    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    database_url = os.getenv('SUPABASE_DATABASE_URL')

    if not all([deepseek_key, anthropic_key, database_url]):
        print("Error: Missing required environment variables")
        return

    analyzer = ContextAnalyzer(deepseek_key, anthropic_key, database_url)

    try:
        # Test with sample post IDs (replace with actual IDs from your database)
        test_post_ids = [1, 2, 3]

        results = await analyzer.analyze_posts(test_post_ids)

        print(f"\n{'='*60}")
        print(f"Analyzed {len(results)} posts")
        print(f"{'='*60}\n")

        for result in results:
            print(f"Post ID: {result['post_id']}")
            print(f"Contact: {result['contact_id']}")
            print(f"Model: {result['model_used']}")
            print(f"Quality Score: {result['quality_score']}/10")
            print(f"Pain Points: {result['pain_points']}")
            print(f"Urgency Signals: {result['urgency_signals']}")
            print(f"Talking Points: {result['talking_points']}")
            print("-" * 60)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
