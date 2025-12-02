#!/usr/bin/env python3
"""
Social Intelligence Pipeline - Main Orchestrator

Daily pipeline (triggered at 6:00 AM UTC):
1. Fetch Hot ATL contacts from Close CRM
2. Scrape LinkedIn profiles for recent posts
3. Monitor Twitter/X for recent tweets
4. AI analysis of all posts (DeepSeek + Claude tiering)
5. Generate personalized email drafts
6. Store drafts in Close CRM
7. Send summary report

Triggered by: GitHub Actions → RunPod Serverless
"""

import asyncio
import os
import sys
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ''))

from app.services.social.linkedin_scraper import LinkedInScraper
from app.services.social.twitter_monitor import TwitterMonitor
from app.services.social.context_analyzer import ContextAnalyzer
from app.services.social.email_draft_generator import EmailDraftGenerator

import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


class SocialIntelligenceRunner:
    """Main orchestrator for social intelligence pipeline."""

    CLOSE_API_URL = "https://api.close.com/api/v1"
    MAX_CONTACTS_PER_RUN = 20  # ATL contacts to process

    def __init__(self):
        """Initialize runner with all required services."""
        # Environment variables
        self.supabase_url = os.getenv('SUPABASE_DATABASE_URL')
        self.close_key = os.getenv('CLOSE_API_KEY')
        self.anthropic_key = os.getenv('ANTHROPIC_API_KEY')
        self.deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        self.twitter_token = os.getenv('TWITTER_BEARER_TOKEN')

        # Validate required variables
        if not all([self.supabase_url, self.close_key, self.anthropic_key, self.deepseek_key]):
            raise ValueError("Missing required environment variables")

        # Initialize services
        self.linkedin_scraper = LinkedInScraper(self.supabase_url)
        self.twitter_monitor = TwitterMonitor(self.twitter_token, self.supabase_url) if self.twitter_token else None
        self.context_analyzer = ContextAnalyzer(
            self.deepseek_key,
            self.anthropic_key,
            self.supabase_url
        )
        self.email_generator = EmailDraftGenerator(
            self.anthropic_key,
            self.close_key,
            self.supabase_url
        )

    async def run_full_pipeline(self):
        """Execute complete social intelligence pipeline."""
        start_time = datetime.now()

        logger.info("=" * 80)
        logger.info("SOCIAL INTELLIGENCE PIPELINE STARTED")
        logger.info(f"Time: {start_time.isoformat()}")
        logger.info("=" * 80)

        try:
            # Step 1: Fetch Hot ATL contacts from Close CRM
            logger.info("\n📇 Step 1: Fetching Hot ATL contacts from Close CRM...")
            contacts = await self._fetch_hot_atl_contacts()

            if not contacts:
                logger.warning("No ATL contacts found. Exiting.")
                return {
                    'success': True,
                    'contacts_processed': 0,
                    'message': 'No contacts to process'
                }

            logger.info(f"✅ Found {len(contacts)} Hot ATL contacts")

            # Step 2: Scrape LinkedIn profiles
            logger.info("\n🔍 Step 2: Scraping LinkedIn profiles...")
            linkedin_urls = [c['linkedin_url'] for c in contacts if c.get('linkedin_url')]

            if linkedin_urls:
                await self.linkedin_scraper.initialize()
                linkedin_posts = await self.linkedin_scraper.scrape_profiles(linkedin_urls)
                await self.linkedin_scraper.save_posts(linkedin_posts)
                await self.linkedin_scraper.close()
                logger.info(f"✅ Scraped {len(linkedin_posts)} LinkedIn posts")
            else:
                linkedin_posts = []
                logger.info("⚠️  No LinkedIn URLs found")

            # Step 3: Monitor Twitter/X
            logger.info("\n🐦 Step 3: Monitoring Twitter/X...")
            twitter_handles = [c['twitter_handle'] for c in contacts if c.get('twitter_handle')]

            if twitter_handles and self.twitter_monitor:
                tweets = await self.twitter_monitor.monitor_accounts(twitter_handles)
                await self.twitter_monitor.save_tweets(tweets)
                logger.info(f"✅ Found {len(tweets)} tweets")
            else:
                tweets = []
                logger.info("⚠️  No Twitter handles found or Twitter monitoring disabled")

            total_posts = len(linkedin_posts) + len(tweets)

            if total_posts == 0:
                logger.warning("No social media posts found. Skipping analysis.")
                return {
                    'success': True,
                    'contacts_processed': len(contacts),
                    'posts_found': 0,
                    'message': 'No posts to analyze'
                }

            # Step 4: AI Analysis
            logger.info(f"\n🤖 Step 4: Analyzing {total_posts} social media posts...")
            post_ids = [p.get('id') for p in linkedin_posts + tweets if p.get('id')]

            # Note: post_ids would need to be fetched from database after saving
            # For now, we'll fetch all unanalyzed posts from the last 24 hours
            analysis_results = await self._analyze_recent_posts()
            logger.info(f"✅ Analyzed {len(analysis_results)} posts")

            # Step 5: Generate Email Drafts
            logger.info("\n✉️  Step 5: Generating personalized email drafts...")
            contact_ids = [c['linkedin_url'] or c['twitter_handle'] for c in contacts]
            drafts = await self.email_generator.generate_drafts(contact_ids)
            logger.info(f"✅ Generated {len(drafts)} email drafts")

            # Step 6: Summary Report
            duration = (datetime.now() - start_time).total_seconds()

            logger.info("\n" + "=" * 80)
            logger.info("PIPELINE COMPLETED SUCCESSFULLY")
            logger.info("=" * 80)
            logger.info(f"Duration: {duration:.1f} seconds")
            logger.info(f"Contacts Processed: {len(contacts)}")
            logger.info(f"LinkedIn Posts: {len(linkedin_posts)}")
            logger.info(f"Tweets: {len(tweets)}")
            logger.info(f"Posts Analyzed: {len(analysis_results)}")
            logger.info(f"Email Drafts: {len(drafts)}")
            logger.info("=" * 80)

            return {
                'success': True,
                'duration_seconds': duration,
                'contacts_processed': len(contacts),
                'linkedin_posts': len(linkedin_posts),
                'tweets': len(tweets),
                'analyzed_posts': len(analysis_results),
                'email_drafts': len(drafts)
            }

        except Exception as e:
            logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
            return {
                'success': False,
                'error': str(e)
            }

    async def _fetch_hot_atl_contacts(self) -> List[Dict[str, Any]]:
        """
        Fetch Hot ATL contacts from Close CRM.

        Returns:
            List of contact dictionaries with linkedin_url and twitter_handle
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Fetch leads with status "Hot ATL" or "Validated ATL"
                response = await client.get(
                    f"{self.CLOSE_API_URL}/lead/",
                    auth=(self.close_key, ''),
                    params={
                        'query': 'status:"Hot ATL" OR status:"Validated ATL"',
                        '_limit': self.MAX_CONTACTS_PER_RUN,
                        '_fields': 'id,contacts,custom'
                    }
                )

                response.raise_for_status()
                data = response.json()

                leads = data.get('data', [])

                # Extract contact information
                contacts = []
                for lead in leads:
                    lead_contacts = lead.get('contacts', [])

                    for contact in lead_contacts:
                        # Extract LinkedIn URL and Twitter handle from custom fields or URLs
                        linkedin_url = None
                        twitter_handle = None

                        # Check URLs array for social links
                        urls = contact.get('urls', [])
                        for url_obj in urls:
                            url = url_obj.get('url', '')
                            if 'linkedin.com' in url:
                                linkedin_url = url
                            elif 'twitter.com' in url or 'x.com' in url:
                                # Extract handle from URL
                                twitter_handle = url.split('/')[-1].lstrip('@')

                        contacts.append({
                            'contact_id': contact.get('id'),
                            'name': contact.get('name'),
                            'linkedin_url': linkedin_url,
                            'twitter_handle': twitter_handle
                        })

                return contacts

        except Exception as e:
            logger.error(f"Error fetching Hot ATL contacts: {e}")
            return []

    async def _analyze_recent_posts(self) -> List[Dict[str, Any]]:
        """
        Analyze all unanalyzed posts from the last 24 hours.

        Returns:
            List of analysis results
        """
        try:
            import psycopg
            from psycopg.rows import dict_row

            # Fetch unanalyzed posts
            async with await psycopg.AsyncConnection.connect(
                self.supabase_url,
                row_factory=dict_row
            ) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT id
                        FROM social_posts
                        WHERE ai_analysis IS NULL
                          AND scraped_at >= NOW() - INTERVAL '24 hours'
                        ORDER BY quality_score DESC NULLS LAST
                    """)

                    results = await cur.fetchall()
                    post_ids = [row['id'] for row in results]

            if not post_ids:
                return []

            # Analyze posts
            return await self.context_analyzer.analyze_posts(post_ids)

        except Exception as e:
            logger.error(f"Error analyzing recent posts: {e}")
            return []


async def main():
    """Main entry point for RunPod serverless invocation."""
    try:
        runner = SocialIntelligenceRunner()
        result = await runner.run_full_pipeline()

        # Return result for RunPod
        return result

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == "__main__":
    # Run pipeline
    result = asyncio.run(main())

    # Exit with appropriate code
    sys.exit(0 if result.get('success') else 1)
