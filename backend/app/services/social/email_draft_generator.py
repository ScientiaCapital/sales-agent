"""
Email Draft Generator Service

Generates personalized email drafts in Close CRM based on AI-analyzed social media posts.
Uses Claude Sonnet 4.5 for high-quality, context-aware email composition.
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


class EmailDraftGenerator:
    """
    Generates personalized email drafts from social intelligence.

    Features:
    - Claude Sonnet 4.5 for premium email composition
    - Context-aware personalization (uses AI analysis)
    - Stores drafts directly in Close CRM
    - Templates for different scenarios (pain point, urgency, general)

    Performance:
    - ~3-5 seconds per email draft
    - Target: 20 email drafts in ~2 minutes (parallel batches)
    """

    ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
    CLOSE_API_URL = "https://api.close.com/api/v1"
    BATCH_SIZE = 5

    def __init__(
        self,
        anthropic_api_key: str,
        close_api_key: str,
        database_url: str
    ):
        """
        Initialize email draft generator.

        Args:
            anthropic_api_key: Anthropic API key
            close_api_key: Close CRM API key
            database_url: Supabase PostgreSQL connection string
        """
        self.anthropic_key = anthropic_api_key
        self.close_key = close_api_key
        self.database_url = database_url

    async def generate_drafts(
        self,
        contact_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Generate email drafts for multiple contacts based on their social posts.

        Args:
            contact_ids: List of contact IDs (LinkedIn URLs or Twitter handles)

        Returns:
            List of draft dictionaries with fields:
            - contact_id: Contact identifier
            - subject_line: Email subject
            - email_body: Full email text
            - talking_points: List of key points used
            - created_at: Timestamp
        """
        logger.info(f"Generating email drafts for {len(contact_ids)} contacts...")

        # Fetch analyzed posts for each contact
        contact_posts = await self._fetch_contact_posts(contact_ids)

        if not contact_posts:
            logger.warning("No analyzed posts found for contacts")
            return []

        # Generate drafts in batches
        all_drafts = []

        for i in range(0, len(contact_posts), self.BATCH_SIZE):
            batch = contact_posts[i:i + self.BATCH_SIZE]

            tasks = [self._generate_single_draft(contact_data) for contact_data in batch]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in batch_results:
                if isinstance(result, Exception):
                    logger.error(f"Draft generation error: {result}")
                elif result:
                    all_drafts.append(result)

        # Save drafts to database and Close CRM
        await self._save_drafts(all_drafts)

        logger.info(f"Generated {len(all_drafts)} email drafts successfully")
        return all_drafts

    async def _fetch_contact_posts(
        self,
        contact_ids: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Fetch analyzed social posts for contacts.

        Returns:
            List of contact data with their posts and analysis
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
                            json_agg(
                                json_build_object(
                                    'post_text', post_text,
                                    'platform', platform,
                                    'posted_at', posted_at,
                                    'pain_points', ai_analysis->'pain_points',
                                    'urgency_signals', ai_analysis->'urgency_signals',
                                    'talking_points', ai_analysis->'talking_points',
                                    'quality_score', quality_score
                                )
                                ORDER BY quality_score DESC, posted_at DESC
                            ) as posts
                        FROM social_posts
                        WHERE contact_id = ANY(%s)
                          AND ai_analysis IS NOT NULL
                          AND quality_score >= 5
                        GROUP BY contact_id
                    """, (contact_ids,))

                    results = await cur.fetchall()
                    return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Error fetching contact posts: {e}")
            return []

    async def _generate_single_draft(
        self,
        contact_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate a personalized email draft for a single contact.

        Args:
            contact_data: Dictionary with contact_id and posts array

        Returns:
            Email draft dictionary
        """
        try:
            contact_id = contact_data['contact_id']
            posts = contact_data['posts']

            logger.info(f"Generating email draft for {contact_id} using {len(posts)} posts")

            # Build context from posts
            context = self._build_email_context(posts)

            # Generate email using Claude
            draft = await self._generate_with_claude(contact_id, context)

            if not draft:
                logger.warning(f"No draft generated for {contact_id}")
                return None

            return {
                'contact_id': contact_id,
                'subject_line': draft['subject'],
                'email_body': draft['body'],
                'talking_points': draft['talking_points'],
                'created_at': datetime.now()
            }

        except Exception as e:
            logger.error(f"Error generating draft for {contact_data.get('contact_id')}: {e}")
            return None

    def _build_email_context(self, posts: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build structured context from analyzed posts."""
        all_pain_points = []
        all_urgency = []
        all_talking_points = []
        highest_score = 0

        for post in posts:
            if post.get('pain_points'):
                all_pain_points.extend(post['pain_points'])
            if post.get('urgency_signals'):
                all_urgency.extend(post['urgency_signals'])
            if post.get('talking_points'):
                all_talking_points.extend(post['talking_points'])
            if post.get('quality_score', 0) > highest_score:
                highest_score = post['quality_score']

        return {
            'pain_points': list(set(all_pain_points))[:3],  # Top 3 unique
            'urgency_signals': list(set(all_urgency))[:2],  # Top 2 unique
            'talking_points': list(set(all_talking_points))[:4],  # Top 4 unique
            'quality_score': highest_score,
            'recent_post': posts[0]['post_text'] if posts else ""
        }

    async def _generate_with_claude(
        self,
        contact_id: str,
        context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Generate email draft using Claude Sonnet 4.5.

        Returns:
            Dictionary with subject, body, and talking_points
        """
        try:
            prompt = self._build_email_prompt(contact_id, context)

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
                        "max_tokens": 1500,
                        "temperature": 0.7,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ]
                    }
                )

                response.raise_for_status()
                data = response.json()

                # Parse JSON response
                content = data['content'][0]['text']
                draft = json.loads(content)

                logger.info(f"Claude draft generated for {contact_id}")
                return draft

        except Exception as e:
            logger.error(f"Claude email generation error: {e}")
            return None

    def _build_email_prompt(
        self,
        contact_id: str,
        context: Dict[str, Any]
    ) -> str:
        """Build prompt for Claude to generate personalized email."""
        return f"""Generate a personalized sales email draft for this prospect:

Contact: {contact_id}
Recent Social Activity Analysis:
- Pain Points: {', '.join(context['pain_points'])}
- Urgency Signals: {', '.join(context['urgency_signals'])}
- Talking Points: {', '.join(context['talking_points'])}
- Most Recent Post: "{context['recent_post'][:200]}..."

Email Guidelines:
1. Subject line: Catchy, references their recent post or pain point
2. Opening: Natural reference to their social media activity (not creepy)
3. Value prop: Address their specific pain point with our solution
4. CTA: Low-pressure ask for 15-min call
5. Tone: Professional but friendly, B2B SaaS style
6. Length: 3-4 short paragraphs (~150 words max)

Return JSON format:
{{
  "subject": "Subject line here",
  "body": "Full email body with \\n for line breaks",
  "talking_points": ["key point 1", "key point 2", "key point 3"]
}}

Return only valid JSON. No explanation."""

    async def _save_drafts(
        self,
        drafts: List[Dict[str, Any]]
    ) -> int:
        """
        Save email drafts to Supabase and create in Close CRM.

        Args:
            drafts: List of draft dictionaries

        Returns:
            Number of drafts saved
        """
        if not drafts:
            return 0

        try:
            # Save to Supabase database
            async with await psycopg.AsyncConnection.connect(
                self.database_url,
                row_factory=dict_row
            ) as conn:
                async with conn.cursor() as cur:
                    for draft in drafts:
                        await cur.execute("""
                            INSERT INTO email_drafts (
                                contact_id, subject_line, email_body,
                                talking_points, created_at, status
                            )
                            VALUES (%s, %s, %s, %s, %s, 'draft')
                        """, (
                            draft['contact_id'],
                            draft['subject_line'],
                            draft['email_body'],
                            json.dumps(draft['talking_points']),
                            draft['created_at']
                        ))

                    await conn.commit()

            # Create drafts in Close CRM (via API)
            await self._create_close_drafts(drafts)

            logger.info(f"Saved {len(drafts)} email drafts to database and Close CRM")
            return len(drafts)

        except Exception as e:
            logger.error(f"Error saving email drafts: {e}")
            return 0

    async def _create_close_drafts(
        self,
        drafts: List[Dict[str, Any]]
    ):
        """
        Create email drafts in Close CRM.

        Note: This creates email drafts via Close API for manual review/sending.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for draft in drafts:
                    # First, find the Close contact by email/LinkedIn
                    # (This is simplified - you'd need to implement contact lookup)

                    # Create email draft activity
                    response = await client.post(
                        f"{self.CLOSE_API_URL}/activity/email/",
                        auth=(self.close_key, ''),
                        json={
                            "subject": draft['subject_line'],
                            "body_text": draft['email_body'],
                            "status": "draft",
                            # "contact_id": close_contact_id,  # Would be populated from lookup
                            # "lead_id": close_lead_id  # Would be populated from lookup
                        }
                    )

                    if response.status_code == 201:
                        logger.info(f"Created Close draft for {draft['contact_id']}")
                    else:
                        logger.warning(f"Failed to create Close draft: {response.status_code}")

        except Exception as e:
            logger.error(f"Error creating Close CRM drafts: {e}")


# Example usage for testing
async def main():
    """Test email draft generator locally."""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    anthropic_key = os.getenv('ANTHROPIC_API_KEY')
    close_key = os.getenv('CLOSE_API_KEY')
    database_url = os.getenv('SUPABASE_DATABASE_URL')

    if not all([anthropic_key, close_key, database_url]):
        print("Error: Missing required environment variables")
        return

    generator = EmailDraftGenerator(anthropic_key, close_key, database_url)

    try:
        # Test with sample contact IDs
        test_contacts = [
            "https://linkedin.com/in/example-profile",
            "@example_twitter"
        ]

        drafts = await generator.generate_drafts(test_contacts)

        print(f"\n{'='*60}")
        print(f"Generated {len(drafts)} email drafts")
        print(f"{'='*60}\n")

        for draft in drafts:
            print(f"Contact: {draft['contact_id']}")
            print(f"Subject: {draft['subject_line']}")
            print(f"\nBody:\n{draft['email_body']}\n")
            print(f"Talking Points: {', '.join(draft['talking_points'])}")
            print("-" * 60)

    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
