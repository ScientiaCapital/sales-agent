"""
Engagement Tracker Service

Tracks email opens from Close CRM and flags high-intent contacts (3+ opens).
Updates Close CRM custom field "High Intent Flag" and populates smart view.
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

import httpx
import psycopg
from psycopg.rows import dict_row

logger = logging.getLogger(__name__)


class EngagementTracker:
    """
    Tracks email engagement to identify hot prospects.

    Features:
    - Monitors email opens via Close CRM API
    - 3+ opens in 7 days = High Intent Flag
    - Updates Close CRM custom field automatically
    - Stores engagement history in Supabase

    Business Logic:
    - 1 open = Interested
    - 2 opens = Engaged
    - 3+ opens = HIGH INTENT (Call immediately!)

    Performance:
    - ~1 second per 100 emails checked
    - Target: Check all drafts in <5 seconds
    """

    CLOSE_API_URL = "https://api.close.com/api/v1"
    HIGH_INTENT_THRESHOLD = 3
    LOOKBACK_DAYS = 7

    # Close CRM Custom Field ID (from your setup)
    HIGH_INTENT_FIELD_ID = "cf_6lDArzDCbc6g92tqTPpcllDOptB8TbD6AcyCae6m2Gr"

    def __init__(
        self,
        close_api_key: str,
        database_url: str
    ):
        """
        Initialize engagement tracker.

        Args:
            close_api_key: Close CRM API key
            database_url: Supabase PostgreSQL connection string
        """
        self.close_key = close_api_key
        self.database_url = database_url

    async def check_engagement(self) -> Dict[str, Any]:
        """
        Check email engagement for all sent drafts.

        Returns:
            Summary dictionary with:
            - total_checked: Number of emails checked
            - high_intent_count: Number of high-intent contacts
            - updated_contacts: List of contact IDs flagged
        """
        # SAFETY: Disable all writes to Close CRM
        if os.getenv("CLOSE_WRITE_DISABLED") == "True":
            logger.warning("⚠️ CLOSE_WRITE_DISABLED: Engagement tracker disabled - read-only mode")
            return {
                'total_checked': 0,
                'high_intent_count': 0,
                'updated_contacts': [],
                'status': 'disabled',
                'message': 'Close CRM write operations are disabled for safety'
            }

        logger.info("Starting email engagement check...")

        # Get sent emails from past 7 days
        sent_emails = await self._fetch_sent_emails()

        if not sent_emails:
            logger.info("No sent emails to check")
            return {
                'total_checked': 0,
                'high_intent_count': 0,
                'updated_contacts': []
            }

        # Check opens for each email
        engagement_data = []

        for email in sent_emails:
            opens = await self._get_email_opens(email['email_id'])

            engagement_data.append({
                'email_id': email['email_id'],
                'contact_id': email['contact_id'],
                'lead_id': email['lead_id'],
                'open_count': len(opens),
                'first_opened_at': opens[0]['opened_at'] if opens else None,
                'last_opened_at': opens[-1]['opened_at'] if opens else None
            })

        # Save engagement history
        await self._save_engagement(engagement_data)

        # Find high-intent contacts (3+ opens)
        high_intent = [
            data for data in engagement_data
            if data['open_count'] >= self.HIGH_INTENT_THRESHOLD
        ]

        # Update Close CRM custom field for high-intent contacts
        if high_intent:
            await self._flag_high_intent_contacts(high_intent)

        logger.info(
            f"Engagement check complete: {len(sent_emails)} checked, "
            f"{len(high_intent)} high-intent contacts found"
        )

        return {
            'total_checked': len(sent_emails),
            'high_intent_count': len(high_intent),
            'updated_contacts': [data['contact_id'] for data in high_intent]
        }

    async def _fetch_sent_emails(self) -> List[Dict[str, Any]]:
        """
        Fetch sent emails from past 7 days from Close CRM.

        Returns:
            List of email dictionaries
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=self.LOOKBACK_DAYS)

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.CLOSE_API_URL}/activity/email/",
                    auth=(self.close_key, ''),
                    params={
                        'date_created__gte': cutoff_date.isoformat(),
                        'status': 'outbox',  # Sent emails
                        '_fields': 'id,contact_id,lead_id,subject,date_sent'
                    }
                )

                response.raise_for_status()
                data = response.json()

                emails = data.get('data', [])
                logger.info(f"Found {len(emails)} sent emails in past {self.LOOKBACK_DAYS} days")

                return [
                    {
                        'email_id': email['id'],
                        'contact_id': email.get('contact_id'),
                        'lead_id': email.get('lead_id'),
                        'subject': email.get('subject'),
                        'sent_at': email.get('date_sent')
                    }
                    for email in emails
                ]

        except Exception as e:
            logger.error(f"Error fetching sent emails from Close: {e}")
            return []

    async def _get_email_opens(
        self,
        email_id: str
    ) -> List[Dict[str, Any]]:
        """
        Get open events for a specific email.

        Args:
            email_id: Close email activity ID

        Returns:
            List of open events with timestamps
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{self.CLOSE_API_URL}/activity/email/{email_id}/",
                    auth=(self.close_key, ''),
                    params={'_fields': 'opens'}
                )

                response.raise_for_status()
                data = response.json()

                opens = data.get('opens', [])

                return [
                    {
                        'opened_at': datetime.fromisoformat(open_event['date'].replace('Z', '+00:00')),
                        'user_agent': open_event.get('user_agent'),
                        'ip_address': open_event.get('ip')
                    }
                    for open_event in opens
                ]

        except Exception as e:
            logger.error(f"Error fetching opens for email {email_id}: {e}")
            return []

    async def _save_engagement(
        self,
        engagement_data: List[Dict[str, Any]]
    ):
        """
        Save engagement data to Supabase database.

        Args:
            engagement_data: List of engagement dictionaries
        """
        if not engagement_data:
            return

        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url,
                row_factory=dict_row
            ) as conn:
                async with conn.cursor() as cur:
                    for data in engagement_data:
                        await cur.execute("""
                            INSERT INTO email_engagement (
                                email_id, contact_id, open_count,
                                first_opened_at, last_opened_at, checked_at
                            )
                            VALUES (%s, %s, %s, %s, %s, %s)
                            ON CONFLICT (email_id) DO UPDATE SET
                                open_count = EXCLUDED.open_count,
                                last_opened_at = EXCLUDED.last_opened_at,
                                checked_at = EXCLUDED.checked_at
                        """, (
                            data['email_id'],
                            data['contact_id'],
                            data['open_count'],
                            data['first_opened_at'],
                            data['last_opened_at'],
                            datetime.now()
                        ))

                    await conn.commit()

            logger.info(f"Saved {len(engagement_data)} engagement records")

        except Exception as e:
            logger.error(f"Error saving engagement data: {e}")

    async def _flag_high_intent_contacts(
        self,
        high_intent_data: List[Dict[str, Any]]
    ):
        """
        Update Close CRM custom field for high-intent contacts.

        Args:
            high_intent_data: List of high-intent contact data
        """
        if not high_intent_data:
            return

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for data in high_intent_data:
                    contact_id = data['contact_id']

                    if not contact_id:
                        continue

                    # Update contact custom field
                    response = await client.put(
                        f"{self.CLOSE_API_URL}/contact/{contact_id}/",
                        auth=(self.close_key, ''),
                        json={
                            self.HIGH_INTENT_FIELD_ID: "Yes"  # Dropdown value
                        }
                    )

                    if response.status_code == 200:
                        logger.info(
                            f"Flagged {contact_id} as high-intent "
                            f"({data['open_count']} opens)"
                        )
                    else:
                        logger.warning(
                            f"Failed to flag {contact_id}: {response.status_code}"
                        )

                    # Rate limiting
                    await asyncio.sleep(0.2)

        except Exception as e:
            logger.error(f"Error flagging high-intent contacts: {e}")

    async def get_high_intent_contacts(self) -> List[Dict[str, Any]]:
        """
        Get all high-intent contacts from database.

        Returns:
            List of high-intent contact dictionaries
        """
        try:
            async with await psycopg.AsyncConnection.connect(
                self.database_url,
                row_factory=dict_row
            ) as conn:
                async with conn.cursor() as cur:
                    await cur.execute("""
                        SELECT
                            contact_id,
                            COUNT(*) as email_count,
                            SUM(open_count) as total_opens,
                            MAX(last_opened_at) as most_recent_open
                        FROM email_engagement
                        WHERE open_count >= %s
                          AND last_opened_at >= NOW() - INTERVAL '%s days'
                        GROUP BY contact_id
                        ORDER BY total_opens DESC, most_recent_open DESC
                    """, (self.HIGH_INTENT_THRESHOLD, self.LOOKBACK_DAYS))

                    results = await cur.fetchall()
                    return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error fetching high-intent contacts: {e}")
            return []


# Example usage for testing
async def main():
    """Test engagement tracker locally."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    close_key = os.getenv('CLOSE_API_KEY')
    database_url = os.getenv('SUPABASE_DATABASE_URL')

    if not all([close_key, database_url]):
        print("Error: Missing required environment variables")
        return

    tracker = EngagementTracker(close_key, database_url)

    try:
        # Check engagement
        summary = await tracker.check_engagement()

        print(f"\n{'='*60}")
        print("Engagement Check Summary")
        print(f"{'='*60}")
        print(f"Emails Checked: {summary['total_checked']}")
        print(f"High-Intent Contacts: {summary['high_intent_count']}")
        print(f"Updated Contacts: {summary['updated_contacts']}")

        # Get high-intent contacts
        high_intent = await tracker.get_high_intent_contacts()

        if high_intent:
            print(f"\n{'='*60}")
            print("High-Intent Contacts (3+ Opens)")
            print(f"{'='*60}")

            for contact in high_intent:
                print(f"\nContact: {contact['contact_id']}")
                print(f"  Emails Sent: {contact['email_count']}")
                print(f"  Total Opens: {contact['total_opens']}")
                print(f"  Most Recent: {contact['most_recent_open']}")
                print("  🔥 CALL IMMEDIATELY!")

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
