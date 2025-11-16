#!/usr/bin/env python3
"""
Email Engagement Checker - Hourly Script

Runs hourly (8 AM - 6 PM UTC) to check email opens and flag high-intent contacts.

Workflow:
1. Fetch sent emails from Close CRM
2. Check open counts for each email
3. Flag contacts with 3+ opens as "High Intent"
4. Update Close CRM custom field
5. Send alert if new high-intent contacts found

Triggered by: GitHub Actions → RunPod Serverless
"""

import asyncio
import os
import sys
import logging
from datetime import datetime

# Add app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ''))

from app.services.social.engagement_tracker import EngagementTracker
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


async def main():
    """Main entry point for hourly engagement checks."""
    start_time = datetime.now()

    logger.info("=" * 80)
    logger.info("EMAIL ENGAGEMENT CHECK STARTED")
    logger.info(f"Time: {start_time.isoformat()}")
    logger.info("=" * 80)

    try:
        # Get environment variables
        close_key = os.getenv('CLOSE_API_KEY')
        database_url = os.getenv('SUPABASE_DATABASE_URL')

        if not all([close_key, database_url]):
            raise ValueError("Missing required environment variables")

        # Initialize engagement tracker
        tracker = EngagementTracker(close_key, database_url)

        # Check engagement
        logger.info("\n📊 Checking email engagement...")
        summary = await tracker.check_engagement()

        # Get high-intent contacts
        high_intent = await tracker.get_high_intent_contacts()

        # Calculate duration
        duration = (datetime.now() - start_time).total_seconds()

        # Log summary
        logger.info("\n" + "=" * 80)
        logger.info("ENGAGEMENT CHECK COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Duration: {duration:.1f} seconds")
        logger.info(f"Emails Checked: {summary['total_checked']}")
        logger.info(f"High-Intent Contacts: {summary['high_intent_count']}")
        logger.info("=" * 80)

        if high_intent:
            logger.info("\n🔥 HIGH-INTENT CONTACTS FOUND:")
            for contact in high_intent[:5]:  # Show top 5
                logger.info(
                    f"  - {contact['contact_id']}: "
                    f"{contact['total_opens']} opens (CALL NOW!)"
                )

        return {
            'success': True,
            'duration_seconds': duration,
            'emails_checked': summary['total_checked'],
            'high_intent_count': summary['high_intent_count'],
            'updated_contacts': summary['updated_contacts']
        }

    except Exception as e:
        logger.error(f"❌ Engagement check failed: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }


if __name__ == "__main__":
    # Run engagement check
    result = asyncio.run(main())

    # Exit with appropriate code
    sys.exit(0 if result.get('success') else 1)
