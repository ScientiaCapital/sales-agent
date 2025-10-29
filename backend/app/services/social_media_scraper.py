"""
Social Media Scraper Service

Multi-platform social media scraping and sentiment analysis.
Platforms: Twitter/X, Reddit, Instagram, Facebook/Meta
"""

import logging
import os
import re
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

# Twitter/X API - using Tweepy (Context7 documented)
try:
    import tweepy
except ImportError:
    tweepy = None

# Reddit API - using PRAW (Context7 documented)
try:
    import praw
except ImportError:
    praw = None

from fastapi import HTTPException
from app.services.cerebras import CerebrasService
from app.core.exceptions import MissingAPIKeyError

logger = logging.getLogger(__name__)


class SocialMediaScraper:
    """
    Service for scraping social media platforms for company mentions and activity

    Platforms supported:
    - Twitter/X (via Tweepy API v2)
    - Reddit (via PRAW)
    - Instagram (via web scraping - requires Browserbase)
    - Meta/Facebook (via Graph API - requires access token)

    Features:
    - Company mention tracking
    - Sentiment analysis with Cerebras AI
    - Engagement metrics collection
    - Activity timeline tracking
    """

    def __init__(self):
        # Initialize Cerebras service (optional - may fail if SDK not installed)
        try:
            self.cerebras = CerebrasService()
        except (ImportError, MissingAPIKeyError):
            self.cerebras = None
            logger.warning("CerebrasService unavailable. Social media sentiment analysis will be limited.")
        
        # Initialize Twitter/X client
        self.twitter_client = self._init_twitter_client()
        
        # Initialize Reddit client
        self.reddit_client = self._init_reddit_client()

    def _init_twitter_client(self):
        """Initialize Twitter API v2 client with bearer token"""
        if not tweepy:
            logger.warning("Tweepy not installed - Twitter scraping disabled")
            return None

        bearer_token = os.getenv("TWITTER_BEARER_TOKEN")
        if not bearer_token:
            logger.warning("TWITTER_BEARER_TOKEN not set - Twitter scraping disabled")
            return None

        try:
            # Use bearer token for read-only access (Context7 pattern)
            client = tweepy.Client(bearer_token=bearer_token)
            logger.info("Twitter API v2 client initialized")
            return client
        except Exception as e:
            logger.error(f"Twitter client initialization failed: {e}")
            return None

    def _init_reddit_client(self):
        """Initialize Reddit PRAW client"""
        if not praw:
            logger.warning("PRAW not installed - Reddit scraping disabled")
            return None

        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "sales-agent:v1.0 (by /u/sales_agent)")

        if not client_id or not client_secret:
            logger.warning("Reddit credentials not set - Reddit scraping disabled")
            return None

        try:
            # Read-only mode (Context7 pattern)
            reddit = praw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent=user_agent
            )
            reddit.read_only = True
            logger.info("Reddit PRAW client initialized (read-only)")
            return reddit
        except Exception as e:
            logger.error(f"Reddit client initialization failed: {e}")
            return None

    def search_twitter_mentions(
        self,
        company_name: str,
        max_results: int = 100,
        days_back: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Search Twitter for company mentions

        Args:
            company_name: Company name to search for
            max_results: Maximum tweets to return (10-100)
            days_back: How many days back to search

        Returns:
            List of tweet data dictionaries

        Raises:
            HTTPException: If Twitter API unavailable or fails
        """
        if not self.twitter_client:
            raise HTTPException(
                status_code=501,
                detail="Twitter scraping not configured - missing credentials"
            )

        try:
            # Build search query (exclude retweets for quality)
            query = f'"{company_name}" -is:retweet lang:en'
            
            # Calculate start time
            start_time = datetime.utcnow() - timedelta(days=days_back)

            # Search tweets (Context7 pattern with rate limit awareness)
            response = self.twitter_client.search_recent_tweets(
                query=query,
                max_results=min(max_results, 100),  # API limit: 100
                start_time=start_time,
                tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
                user_fields=['username', 'name', 'verified']
            )

            if not response.data:
                return []

            tweets = []
            for tweet in response.data:
                tweets.append({
                    "id": tweet.id,
                    "text": tweet.text,
                    "created_at": tweet.created_at.isoformat() if tweet.created_at else None,
                    "metrics": {
                        "retweets": tweet.public_metrics.get('retweet_count', 0),
                        "likes": tweet.public_metrics.get('like_count', 0),
                        "replies": tweet.public_metrics.get('reply_count', 0)
                    },
                    "platform": "twitter"
                })

            logger.info(f"Found {len(tweets)} Twitter mentions for '{company_name}'")
            return tweets

        except tweepy.TooManyRequests:
            # Context7 documented rate limit handling
            logger.warning("Twitter rate limit hit - waiting required")
            raise HTTPException(
                status_code=429,
                detail="Twitter API rate limit exceeded - try again later"
            )
        except Exception as e:
            logger.error(f"Twitter search failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Twitter search failed: {str(e)}"
            )

    def search_reddit_mentions(
        self,
        company_name: str,
        max_results: int = 100,
        subreddits: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search Reddit for company mentions

        Args:
            company_name: Company name to search for
            max_results: Maximum posts to return
            subreddits: Optional list of specific subreddits to search

        Returns:
            List of Reddit post/comment data

        Raises:
            HTTPException: If Reddit API unavailable or fails
        """
        if not self.reddit_client:
            raise HTTPException(
                status_code=501,
                detail="Reddit scraping not configured - missing credentials"
            )

        try:
            posts = []
            
            if subreddits:
                # Search specific subreddits
                for subreddit_name in subreddits:
                    subreddit = self.reddit_client.subreddit(subreddit_name)
                    for submission in subreddit.search(company_name, limit=max_results // len(subreddits)):
                        posts.append(self._format_reddit_post(submission))
            else:
                # Search all of Reddit
                for submission in self.reddit_client.subreddit('all').search(company_name, limit=max_results):
                    posts.append(self._format_reddit_post(submission))

            logger.info(f"Found {len(posts)} Reddit mentions for '{company_name}'")
            return posts

        except Exception as e:
            logger.error(f"Reddit search failed: {str(e)}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail=f"Reddit search failed: {str(e)}"
            )

    def _format_reddit_post(self, submission) -> Dict[str, Any]:
        """Format Reddit submission data"""
        return {
            "id": submission.id,
            "title": submission.title,
            "text": submission.selftext[:500],  # Limit text length
            "created_at": datetime.fromtimestamp(submission.created_utc).isoformat(),
            "subreddit": submission.subreddit.display_name,
            "metrics": {
                "upvotes": submission.score,
                "comments": submission.num_comments,
                "upvote_ratio": submission.upvote_ratio
            },
            "url": f"https://reddit.com{submission.permalink}",
            "platform": "reddit"
        }

    def analyze_sentiment(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze sentiment of social media posts using Cerebras AI

        Args:
            posts: List of social media posts to analyze

        Returns:
            Sentiment analysis summary
        """
        if not posts:
            return {
                "overall_sentiment": "neutral",
                "sentiment_score": 50.0,
                "total_posts": 0
            }

        # Combine post texts for batch analysis
        combined_text = "\n\n---\n\n".join([
            f"Platform: {post['platform']}\n{post.get('title', '')} {post.get('text', '')[:200]}"
            for post in posts[:20]  # Analyze max 20 posts to avoid token limits
        ])

        try:
            # Use Cerebras for sentiment analysis
            score, reasoning, latency_ms = self.cerebras.qualify_lead(
                company_name="Sentiment Analysis",
                notes=f"Analyze overall sentiment (positive/negative/neutral) of these social media posts:\n\n{combined_text}"
            )

            # Interpret score as sentiment (0-100 scale)
            if score >= 70:
                sentiment = "positive"
            elif score >= 40:
                sentiment = "neutral"
            else:
                sentiment = "negative"

            return {
                "overall_sentiment": sentiment,
                "sentiment_score": score,
                "sentiment_reasoning": reasoning,
                "total_posts_analyzed": min(len(posts), 20),
                "analysis_latency_ms": latency_ms
            }

        except Exception as e:
            logger.error(f"Sentiment analysis failed: {str(e)}")
            return {
                "overall_sentiment": "unknown",
                "sentiment_score": 50.0,
                "error": str(e),
                "total_posts": len(posts)
            }

    def scrape_company_social(
        self,
        company_name: str,
        platforms: List[str] = ["twitter", "reddit"],
        max_results_per_platform: int = 50
    ) -> Dict[str, Any]:
        """
        Scrape multiple social media platforms for company mentions

        Args:
            company_name: Company name to search
            platforms: List of platforms to scrape
            max_results_per_platform: Max results per platform

        Returns:
            Aggregated social media data with sentiment analysis
        """
        start_time = datetime.now()
        all_posts = []
        platform_results = {}

        # Twitter
        if "twitter" in platforms and self.twitter_client:
            try:
                twitter_posts = self.search_twitter_mentions(
                    company_name,
                    max_results=max_results_per_platform
                )
                all_posts.extend(twitter_posts)
                platform_results["twitter"] = {
                    "count": len(twitter_posts),
                    "status": "success"
                }
            except Exception as e:
                platform_results["twitter"] = {
                    "count": 0,
                    "status": "failed",
                    "error": str(e)
                }

        # Reddit
        if "reddit" in platforms and self.reddit_client:
            try:
                reddit_posts = self.search_reddit_mentions(
                    company_name,
                    max_results=max_results_per_platform
                )
                all_posts.extend(reddit_posts)
                platform_results["reddit"] = {
                    "count": len(reddit_posts),
                    "status": "success"
                }
            except Exception as e:
                platform_results["reddit"] = {
                    "count": 0,
                    "status": "failed",
                    "error": str(e)
                }

        # Analyze sentiment
        sentiment = self.analyze_sentiment(all_posts)

        end_time = datetime.now()
        duration_ms = int((end_time - start_time).total_seconds() * 1000)

        return {
            "company_name": company_name,
            "total_mentions": len(all_posts),
            "platform_results": platform_results,
            "sentiment_analysis": sentiment,
            "posts": all_posts[:20],  # Return top 20 posts
            "scraping_duration_ms": duration_ms
        }
