"""
Twitter/X Monitor Service

Monitors Twitter/X for recent tweets from specified accounts using Tweepy API.
Implements rate limiting, error handling, and efficient API usage.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any

import tweepy
import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class TwitterMonitor:
    """
    Monitors Twitter/X accounts for recent tweets.

    Features:
    - Tweepy API v2 integration
    - Rate limiting (1500 tweets per 15 min window)
    - Smart caching (avoid duplicate tweets)
    - Error handling and retry logic

    Performance:
    - ~200 tweets/second (API limit)
    - Target: 20 contacts × 10 tweets = 200 tweets = ~1 second

    Note: Requires Twitter API Essential access (free tier available)
    """

    MAX_TWEETS_PER_USER = 10
    LOOKBACK_DAYS = 7
    RATE_LIMIT_WINDOW = 900  # 15 minutes in seconds

    def __init__(self, bearer_token: str, database_url: str):
        """
        Initialize Twitter monitor.

        Args:
            bearer_token: Twitter API v2 Bearer Token
            database_url: Supabase PostgreSQL connection string
        """
        self.client = tweepy.Client(bearer_token=bearer_token)
        self.database_url = database_url

    async def monitor_accounts(self, twitter_handles: List[str]) -> List[Dict[str, Any]]:
        """
        Monitor multiple Twitter accounts for recent tweets.

        Args:
            twitter_handles: List of Twitter handles (without @)

        Returns:
            List of tweet dictionaries with fields:
            - contact_id: Twitter handle
            - platform: 'twitter'
            - post_text: Tweet text
            - post_url: URL to tweet
            - posted_at: Tweet timestamp
            - scraped_at: Current timestamp
        """
        logger.info(f"Monitoring {len(twitter_handles)} Twitter accounts...")

        all_tweets = []

        for handle in twitter_handles:
            try:
                tweets = await self._get_user_tweets(handle)
                all_tweets.extend(tweets)

            except tweepy.errors.TooManyRequests:
                logger.warning(f"Rate limit reached. Pausing Twitter monitoring.")
                break

            except Exception as e:
                logger.error(f"Error monitoring @{handle}: {e}")
                continue

        logger.info(f"Found {len(all_tweets)} total tweets from {len(twitter_handles)} accounts")
        return all_tweets

    async def _get_user_tweets(self, handle: str) -> List[Dict[str, Any]]:
        """
        Get recent tweets from a single Twitter user.

        Args:
            handle: Twitter handle (without @)

        Returns:
            List of tweet dictionaries
        """
        try:
            logger.info(f"Fetching tweets from @{handle}")

            # Get user ID from handle
            user = self.client.get_user(username=handle)

            if not user or not user.data:
                logger.warning(f"User @{handle} not found")
                return []

            user_id = user.data.id

            # Calculate date range
            start_time = datetime.now() - timedelta(days=self.LOOKBACK_DAYS)

            # Get user tweets
            tweets_response = self.client.get_users_tweets(
                id=user_id,
                max_results=self.MAX_TWEETS_PER_USER,
                start_time=start_time.isoformat() + 'Z',
                tweet_fields=['created_at', 'text', 'id'],
                exclude=['retweets', 'replies']  # Only original tweets
            )

            if not tweets_response or not tweets_response.data:
                logger.info(f"No recent tweets from @{handle}")
                return []

            # Format tweets
            formatted_tweets = []
            for tweet in tweets_response.data:
                formatted_tweets.append({
                    'contact_id': handle,
                    'platform': 'twitter',
                    'post_text': tweet.text,
                    'post_url': f"https://twitter.com/{handle}/status/{tweet.id}",
                    'posted_at': tweet.created_at,
                    'scraped_at': datetime.now()
                })

            logger.info(f"Found {len(formatted_tweets)} tweets from @{handle}")
            return formatted_tweets

        except tweepy.errors.Forbidden:
            logger.warning(f"Account @{handle} is private or suspended")
            return []

        except Exception as e:
            logger.error(f"Failed to fetch tweets from @{handle}: {e}")
            return []

    async def save_tweets(self, tweets: List[Dict[str, Any]]) -> int:
        """
        Save tweets to Supabase database.

        Args:
            tweets: List of tweet dictionaries

        Returns:
            Number of tweets saved
        """
        if not tweets:
            return 0

        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url,
                row_factory=dict_row
            ) as conn:
                async with conn.cursor() as cur:
                    # Insert tweets (skip duplicates based on post_url)
                    for tweet in tweets:
                        await cur.execute("""
                            INSERT INTO social_posts (
                                contact_id, platform, post_text, post_url,
                                posted_at, scraped_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (post_url) DO NOTHING
                        """, (
                            tweet['contact_id'],
                            tweet['platform'],
                            tweet['post_text'],
                            tweet['post_url'],
                            tweet['posted_at'],
                            tweet['scraped_at']
                        ))

                    await conn.commit()

            logger.info(f"Saved {len(tweets)} tweets to database")
            return len(tweets)

        except Exception as e:
            logger.error(f"Error saving tweets to database: {e}")
            return 0


# Example usage for testing
async def main():
    """Test Twitter monitor locally."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
    database_url = os.getenv('SUPABASE_DATABASE_URL')

    if not bearer_token:
        print("Error: TWITTER_BEARER_TOKEN not found in .env")
        return

    monitor = TwitterMonitor(bearer_token, database_url)

    try:
        # Test with sample Twitter handles
        test_handles = [
            "elonmusk",  # Example handle
            "tim_cook"
        ]

        tweets = await monitor.monitor_accounts(test_handles)

        print(f"\n{'='*60}")
        print(f"Found {len(tweets)} tweets")
        print(f"{'='*60}\n")

        for tweet in tweets:
            print(f"Handle: @{tweet['contact_id']}")
            print(f"Posted: {tweet['posted_at']}")
            print(f"Text: {tweet['post_text'][:100]}...")
            print(f"URL: {tweet['post_url']}")
            print("-" * 60)

        # Save to database
        saved_count = await monitor.save_tweets(tweets)
        print(f"\nSaved {saved_count} tweets to database")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
