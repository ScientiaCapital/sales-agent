# Social Intelligence System - Serverless Architecture Design

**Date**: 2025-11-16
**Status**: Approved - Ready for Implementation
**Owner**: Tim Kipper
**Architecture**: Hybrid Smart Start - Serverless

---

## Executive Summary

**Goal**: Automate social media monitoring (LinkedIn + Twitter/X) to generate personalized email drafts in Close CRM, enabling Tim to focus on high-value ATL contacts with context-rich outreach.

**Approach**: Serverless batch processing using RunPod Serverless + Supabase + GitHub Actions for 78% cost savings vs dedicated infrastructure.

**Business Impact**:
- **100x productivity**: 20 ATL contacts researched daily vs 0-2 manual research
- **Higher response rates**: Personalized emails based on recent LinkedIn posts
- **Priority intelligence**: Automatic detection of high-intent contacts (3+ email opens)
- **Cost**: $17/month (vs $77/month dedicated pod)

---

## Architecture Overview

### System Components

```
┌─────────────────────────────────────────────────────────────┐
│                    GitHub Actions (FREE)                     │
│                   Cron Trigger: 6 AM daily                   │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│              RunPod Serverless ($17/month)                   │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐ │
│  │   LinkedIn     │  │   Twitter/X    │  │  AI Analysis  │ │
│  │   Scraper      │  │   Monitor      │  │  (Claude)     │ │
│  └────────────────┘  └────────────────┘  └───────────────┘ │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                  Supabase PostgreSQL (FREE)                  │
│         Stores: Contact history, Posts, Email drafts         │
└─────────────────────────────────────────────────────────────┘
                         │
                         ↓
┌─────────────────────────────────────────────────────────────┐
│                    Close CRM API (FREE)                      │
│         Creates: Email drafts, Research activities           │
└─────────────────────────────────────────────────────────────┘
```

### Daily Workflow

**6:00 AM**: GitHub Actions triggers RunPod serverless endpoint
**6:01 AM**: Container boots, mounts Supabase connection
**6:02-6:30 AM**: Scrape LinkedIn profiles (20 ATL contacts)
**6:30-6:40 AM**: Monitor Twitter/X for recent posts
**6:40-6:50 AM**: AI analysis extracts context and talking points
**6:50-7:00 AM**: Create email drafts in Close CRM
**7:00 AM**: Container shuts down, Tim reviews drafts over coffee

**Hourly (8 AM - 6 PM)**: Check email engagement, flag 3+ opens

---

## Infrastructure Setup

### 1. Supabase Database (Already Have Account ✅)

**Database Schema**:

```sql
-- Social media post tracking
CREATE TABLE social_posts (
    id SERIAL PRIMARY KEY,
    contact_id VARCHAR(255) NOT NULL,
    platform VARCHAR(50) NOT NULL,  -- 'linkedin' or 'twitter'
    post_text TEXT,
    post_url VARCHAR(500),
    posted_at TIMESTAMP,
    scraped_at TIMESTAMP DEFAULT NOW(),
    ai_analysis JSONB,  -- Stores pain points, urgency, talking points
    quality_score INTEGER  -- 1-10 score from AI
);

-- Contact monitoring status
CREATE TABLE contact_monitoring (
    id SERIAL PRIMARY KEY,
    close_contact_id VARCHAR(255) UNIQUE NOT NULL,
    linkedin_url VARCHAR(500),
    twitter_handle VARCHAR(100),
    last_linkedin_check TIMESTAMP,
    last_twitter_check TIMESTAMP,
    monitoring_enabled BOOLEAN DEFAULT TRUE,
    total_posts_found INTEGER DEFAULT 0
);

-- Email draft history
CREATE TABLE email_drafts (
    id SERIAL PRIMARY KEY,
    close_lead_id VARCHAR(255) NOT NULL,
    close_contact_id VARCHAR(255) NOT NULL,
    close_activity_id VARCHAR(255),  -- ID from Close CRM API
    subject VARCHAR(500),
    body_html TEXT,
    research_context TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    sent_at TIMESTAMP,
    opens_count INTEGER DEFAULT 0,
    last_opened_at TIMESTAMP
);

-- Email engagement tracking
CREATE TABLE email_engagement (
    id SERIAL PRIMARY KEY,
    email_draft_id INTEGER REFERENCES email_drafts(id),
    event_type VARCHAR(50),  -- 'open', 'click', 'reply'
    event_timestamp TIMESTAMP DEFAULT NOW(),
    metadata JSONB
);

-- Indexes for performance
CREATE INDEX idx_social_posts_contact ON social_posts(contact_id);
CREATE INDEX idx_social_posts_scraped ON social_posts(scraped_at DESC);
CREATE INDEX idx_email_drafts_opens ON email_drafts(opens_count DESC);
CREATE INDEX idx_email_engagement_timestamp ON email_engagement(event_timestamp DESC);
```

**Connection String** (from Supabase dashboard):
```
postgresql://postgres:[YOUR-PASSWORD]@db.[PROJECT-REF].supabase.co:5432/postgres
```

### 2. RunPod Serverless Endpoint

**Setup via RunPod CLI**:

```bash
# Install RunPod CLI
pip install runpod

# Authenticate
runpod config --api-key [YOUR_RUNPOD_API_KEY]

# Create serverless endpoint
runpod create endpoint \
  --name social-intelligence \
  --docker-image ghcr.io/tkipper/sales-agent-social:latest \
  --gpu-type NONE \
  --cpu 4 \
  --memory 16 \
  --min-workers 0 \
  --max-workers 1 \
  --idle-timeout 60
```

**Dockerfile** (for the container):

```dockerfile
FROM python:3.13-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements-serverless.txt .
RUN pip install --no-cache-dir -r requirements-serverless.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps

# Copy application code
COPY backend/app /app/app
COPY backend/social_intelligence_runner.py /app/

# Set environment variables
ENV PYTHONUNBUFFERED=1

# RunPod handler entry point
CMD ["python", "-u", "social_intelligence_runner.py"]
```

**requirements-serverless.txt**:
```
fastapi==0.104.1
httpx==0.25.1
anthropic==0.7.1
openai==1.3.7
playwright==1.40.0
tweepy==4.14.0
beautifulsoup4==4.12.2
lxml==4.9.3
psycopg[binary]==3.1.13
redis==5.0.1
pydantic==2.5.0
python-dotenv==1.0.0
```

### 3. GitHub Actions Workflow

**File**: `.github/workflows/social-intelligence.yml`

```yaml
name: Social Intelligence Pipeline

on:
  schedule:
    # Daily at 6:00 AM UTC (adjust for your timezone)
    - cron: '0 6 * * *'

    # Hourly engagement checks (8 AM - 6 PM UTC)
    - cron: '0 8-18 * * *'

  # Allow manual triggers for testing
  workflow_dispatch:

jobs:
  social-intelligence:
    runs-on: ubuntu-latest

    steps:
      - name: Determine Job Type
        id: job_type
        run: |
          HOUR=$(date +%H)
          if [ "$HOUR" == "06" ]; then
            echo "type=full_pipeline" >> $GITHUB_OUTPUT
          else
            echo "type=engagement_check" >> $GITHUB_OUTPUT
          fi

      - name: Trigger RunPod Serverless Endpoint
        run: |
          curl -X POST https://api.runpod.io/v2/${{ secrets.RUNPOD_ENDPOINT_ID }}/run \
            -H "Authorization: Bearer ${{ secrets.RUNPOD_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{
              "input": {
                "task": "${{ steps.job_type.outputs.type }}",
                "config": {
                  "max_contacts": 20,
                  "platforms": ["linkedin", "twitter"]
                }
              }
            }'

      - name: Wait for Completion
        run: |
          echo "Pipeline triggered successfully"
          # Optional: Poll for completion status

      - name: Send Notification on Failure
        if: failure()
        run: |
          curl -X POST https://api.sendgrid.com/v3/mail/send \
            -H "Authorization: Bearer ${{ secrets.SENDGRID_API_KEY }}" \
            -H "Content-Type: application/json" \
            -d '{
              "personalizations": [{
                "to": [{"email": "${{ secrets.NOTIFICATION_EMAIL }}"}]
              }],
              "from": {"email": "alerts@sales-agent.com"},
              "subject": "⚠️ Social Intelligence Pipeline Failed",
              "content": [{
                "type": "text/plain",
                "value": "The social intelligence pipeline failed to run. Check GitHub Actions logs."
              }]
            }'
```

**GitHub Secrets to Add**:
- `RUNPOD_API_KEY`: Your RunPod API key
- `RUNPOD_ENDPOINT_ID`: Created when you deploy the endpoint
- `NOTIFICATION_EMAIL`: tim@coperniq.com
- `SENDGRID_API_KEY`: (Optional) For failure notifications

### 4. Upstash Redis (Optional - for caching)

**Free Tier**: 10,000 commands/day
**Use Case**: Cache LinkedIn profiles to avoid re-scraping

```bash
# Sign up at upstash.com
# Create Redis database (choose closest region)
# Copy connection string

REDIS_URL=rediss://default:[PASSWORD]@[ENDPOINT]:6379
```

---

## Code Implementation

### Primary File: `social_intelligence_runner.py`

```python
"""
Social Intelligence Pipeline - Serverless Entry Point
Triggered by GitHub Actions via RunPod Serverless
"""
import asyncio
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Services
from app.services.social.linkedin_scraper import LinkedInScraper
from app.services.social.twitter_monitor import TwitterMonitor
from app.services.social.context_analyzer import ContextAnalyzer
from app.services.crm.close import CloseService
from app.core.database import DatabaseService

# Logging
import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_full_pipeline():
    """
    Main social intelligence pipeline (runs at 6 AM daily)

    Flow:
    1. Fetch Hot ATL contacts from Close CRM
    2. Scrape LinkedIn profiles for recent posts
    3. Monitor Twitter/X for relevant tweets
    4. AI analysis of all posts
    5. Generate personalized email drafts
    6. Store drafts in Close CRM
    7. Send daily summary email
    """
    start_time = datetime.now()
    logger.info("=" * 80)
    logger.info("Starting Social Intelligence Pipeline")
    logger.info("=" * 80)

    try:
        # Initialize services
        close_service = CloseService()
        db = DatabaseService()

        # Step 1: Get Hot ATL contacts from Close CRM
        logger.info("[Step 1/7] Fetching Hot ATL contacts from Close CRM...")
        atl_contacts = await close_service.get_contacts_by_smart_view(
            smart_view_name="🔥 Hot ATL Leads (Priority)",
            limit=20
        )
        logger.info(f"✓ Found {len(atl_contacts)} ATL contacts to monitor")

        if not atl_contacts:
            logger.warning("No ATL contacts found. Exiting pipeline.")
            return

        # Step 2: Scrape LinkedIn profiles
        logger.info("[Step 2/7] Scraping LinkedIn profiles...")
        linkedin_scraper = LinkedInScraper()
        linkedin_posts = await linkedin_scraper.scrape_recent_posts(
            contacts=atl_contacts,
            days_back=7
        )
        logger.info(f"✓ Scraped {len(linkedin_posts)} LinkedIn posts")

        # Step 3: Monitor Twitter/X
        logger.info("[Step 3/7] Monitoring Twitter/X...")
        twitter_monitor = TwitterMonitor()
        tweets = await twitter_monitor.fetch_recent_tweets(
            contacts=atl_contacts,
            days_back=7
        )
        logger.info(f"✓ Found {len(tweets)} relevant tweets")

        # Step 4: Store posts in database
        logger.info("[Step 4/7] Storing posts in database...")
        await db.store_social_posts(linkedin_posts + tweets)
        logger.info(f"✓ Stored {len(linkedin_posts) + len(tweets)} posts")

        # Step 5: AI analysis
        logger.info("[Step 5/7] Running AI context analysis...")
        analyzer = ContextAnalyzer()
        insights = await analyzer.analyze_social_activity(
            posts=linkedin_posts + tweets
        )
        high_quality_insights = [i for i in insights if i.quality_score >= 7]
        logger.info(f"✓ Generated {len(insights)} insights ({len(high_quality_insights)} high-quality)")

        # Step 6: Create email drafts in Close CRM
        logger.info("[Step 6/7] Creating email drafts in Close CRM...")
        drafts_created = 0
        for insight in high_quality_insights:
            try:
                # Create draft in Close CRM
                activity = await close_service.create_email_draft(
                    contact_id=insight.contact_id,
                    lead_id=insight.lead_id,
                    subject=insight.email_subject,
                    body=insight.email_body
                )

                # Create research activity note
                await close_service.create_custom_activity(
                    lead_id=insight.lead_id,
                    activity_type="social_intelligence",
                    note=insight.research_context
                )

                # Store in database for tracking
                await db.store_email_draft(
                    close_activity_id=activity['id'],
                    close_lead_id=insight.lead_id,
                    close_contact_id=insight.contact_id,
                    subject=insight.email_subject,
                    body_html=insight.email_body,
                    research_context=insight.research_context
                )

                drafts_created += 1
                logger.info(f"  ✓ Created draft for {insight.contact_name}")

            except Exception as e:
                logger.error(f"  ✗ Failed to create draft for {insight.contact_name}: {e}")

        logger.info(f"✓ Created {drafts_created} email drafts in Close CRM")

        # Step 7: Send daily summary email
        logger.info("[Step 7/7] Sending daily summary email...")
        await send_daily_summary(
            contacts_monitored=len(atl_contacts),
            linkedin_posts_found=len(linkedin_posts),
            tweets_found=len(tweets),
            drafts_created=drafts_created,
            runtime=(datetime.now() - start_time).seconds
        )
        logger.info("✓ Summary email sent")

        # Pipeline complete
        elapsed = (datetime.now() - start_time).seconds
        logger.info("=" * 80)
        logger.info(f"Pipeline Complete! Runtime: {elapsed} seconds ({elapsed/60:.1f} minutes)")
        logger.info("=" * 80)

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        # Send error notification
        await send_error_notification(str(e))
        sys.exit(1)


async def run_engagement_check():
    """
    Check email engagement (runs hourly 8 AM - 6 PM)

    Detects high-intent contacts (3+ email opens) and updates Close CRM
    """
    logger.info("Starting Email Engagement Check...")

    try:
        close_service = CloseService()
        db = DatabaseService()

        # Get all sent emails from last 7 days
        recent_emails = await close_service.get_recent_email_activities(
            days_back=7,
            status="sent"
        )

        high_intent_contacts = []

        for email in recent_emails:
            # Check if email has 3+ opens
            if email.get('opens_count', 0) >= 3:
                # Update custom field in Close CRM
                await close_service.update_lead_custom_field(
                    lead_id=email['lead_id'],
                    field_name="high_intent_flag",
                    value=True
                )

                # Store engagement event
                await db.store_email_engagement(
                    email_activity_id=email['id'],
                    event_type='high_intent_detected',
                    opens_count=email['opens_count']
                )

                high_intent_contacts.append({
                    'contact_name': email.get('contact_name'),
                    'lead_name': email.get('lead_name'),
                    'opens_count': email['opens_count'],
                    'last_opened': email.get('last_opened_at')
                })

        if high_intent_contacts:
            logger.info(f"✓ Found {len(high_intent_contacts)} high-intent contacts")
            await send_high_intent_alert(high_intent_contacts)
        else:
            logger.info("No new high-intent contacts detected")

    except Exception as e:
        logger.error(f"Engagement check failed: {e}", exc_info=True)


async def send_daily_summary(
    contacts_monitored: int,
    linkedin_posts_found: int,
    tweets_found: int,
    drafts_created: int,
    runtime: int
):
    """Send daily summary email to Tim"""
    # Implementation using SMTP or SendGrid
    pass


async def send_high_intent_alert(contacts: List[Dict[str, Any]]):
    """Send real-time alert for 3+ email opens"""
    # Implementation for high-priority notifications
    pass


async def send_error_notification(error_message: str):
    """Send error alert if pipeline fails"""
    # Implementation for failure notifications
    pass


# RunPod serverless handler
def handler(event):
    """
    Entry point for RunPod serverless execution

    event = {
        "input": {
            "task": "full_pipeline" | "engagement_check",
            "config": {...}
        }
    }
    """
    task_type = event.get('input', {}).get('task', 'full_pipeline')

    if task_type == 'full_pipeline':
        asyncio.run(run_full_pipeline())
    elif task_type == 'engagement_check':
        asyncio.run(run_engagement_check())
    else:
        logger.error(f"Unknown task type: {task_type}")
        return {"error": f"Unknown task: {task_type}"}

    return {"status": "success", "task": task_type}


# Local testing
if __name__ == "__main__":
    # For local testing: python social_intelligence_runner.py
    asyncio.run(run_full_pipeline())
```

---

## Close CRM Integration

### Smart Views to Create

**1. High-Intent ATL Contacts** (3+ Email Opens)

```python
{
    "name": "🔥 High-Intent ATL Contacts (3+ Opens)",
    "query": {
        "type": "and",
        "queries": [
            {"type": "object_type", "object_type": "lead"},
            {
                "type": "field_condition",
                "field": {"type": "regular_field", "field_name": "status_id"},
                "condition": {
                    "type": "reference",
                    "object_ids": ["stat_hot_atl_id", "stat_validated_atl_id"]
                }
            },
            {
                "type": "field_condition",
                "field": {"type": "custom_field", "custom_field_id": "high_intent_flag"},
                "condition": {"type": "boolean", "value": true}
            }
        ]
    }
}
```

**Setup Script**: Run once to create custom fields

```python
# backend/setup_social_intelligence.py
import asyncio
from app.services.crm.close import CloseService

async def setup():
    close = CloseService()

    # Create custom field for high-intent flag
    await close.create_custom_field(
        name="High Intent Flag",
        field_type="boolean",
        object_type="lead"
    )

    # Create custom activity type for social research
    await close.create_custom_activity_type(
        name="Social Intelligence",
        description="LinkedIn/Twitter research insights"
    )

    # Create Smart View
    await close.create_smart_view(
        name="🔥 High-Intent ATL Contacts (3+ Opens)",
        query={...}  # From above
    )

    print("✅ Close CRM configured for social intelligence")

if __name__ == "__main__":
    asyncio.run(setup())
```

---

## Cost Analysis

### Monthly Costs

| Service | Tier | Usage | Cost |
|---------|------|-------|------|
| **RunPod Serverless** | 4 vCPU | 48 hrs/month × $0.0001/sec | $17.28 |
| **Supabase PostgreSQL** | Free | 500MB database | $0.00 |
| **Upstash Redis** | Free | 10k cmds/day | $0.00 |
| **GitHub Actions** | Free | <2000 min/month | $0.00 |
| **Claude API** | Pay-as-you-go | 75 emails × $0.02 | $1.50 |
| **DeepSeek API** | OpenRouter | Low-tier analysis | $0.30 |
| **Twitter API** | Free | 500k tweets/month | $0.00 |
| **TOTAL** | | | **$19.08/month** |

### Phase 2 Scaling Costs

When scaling to 100 contacts or adding features:

| Upgrade | Cost | Benefit |
|---------|------|---------|
| Supabase Pro | $25/month | 8GB database, better performance |
| PhantomBuster | $30/month | LinkedIn automation (less risky) |
| Twitter Premium | $200/month | Real-time webhooks |
| **Scaled Total** | **$254/month** | 100 contacts, real-time monitoring |

---

## Implementation Timeline

### Week 1: Setup & Configuration
- **Day 1-2**: Supabase database setup, schema creation
- **Day 3**: RunPod serverless endpoint configuration
- **Day 4**: GitHub Actions workflow setup
- **Day 5**: Testing with 5 sample contacts

### Week 2: Core Development
- **Day 1-2**: LinkedIn scraper implementation
- **Day 3**: Twitter monitor implementation
- **Day 4**: AI context analyzer
- **Day 5**: Close CRM integration

### Week 3: Integration & Testing
- **Day 1-2**: End-to-end pipeline testing
- **Day 3**: Email engagement tracking
- **Day 4**: Notification system
- **Day 5**: Production deployment

### Week 4: Monitoring & Refinement
- **Day 1-7**: Monitor daily runs, refine AI prompts, fix edge cases

**Total: 4 weeks to production-ready system**

---

## Success Metrics

### Week 1 Goals
- ✅ 5 test contacts monitored successfully
- ✅ 1-2 email drafts created with quality score >7
- ✅ Pipeline runs in <15 minutes

### Month 1 Goals
- ✅ 20 ATL contacts monitored daily
- ✅ 30-50 email drafts created per month
- ✅ 10+ high-quality conversations started
- ✅ Zero LinkedIn account blocks

### Month 3 Goals
- ✅ 50 ATL contacts monitored
- ✅ 80%+ email draft acceptance rate (Tim sends without major edits)
- ✅ 3+ meetings booked from social intelligence outreach
- ✅ ROI: $10k+ pipeline generated from $60 infrastructure cost

---

## Risk Mitigation

### Risk 1: LinkedIn Blocks Scraper Account
**Mitigation**:
- Use respectful rate limits (2-5 sec delays)
- Rotate user agents
- Use real Chrome browser (not headless)
- Fallback to PhantomBuster ($30/month) if blocked

### Risk 2: AI Generates Low-Quality Emails
**Mitigation**:
- Quality scoring system (only >7/10 get drafted)
- Template library with proven patterns
- Weekly review of AI outputs, refine prompts

### Risk 3: Close CRM API Rate Limits
**Mitigation**:
- Batch API calls (max 20 drafts at once)
- Close CRM has generous limits (10,000 calls/day)
- Add exponential backoff retry logic

### Risk 4: RunPod Serverless Cold Start Delays
**Mitigation**:
- Acceptable for 6 AM batch job (60 sec doesn't matter)
- Keep container warm with hourly engagement checks
- Pre-build Docker image for faster boots

---

## Next Steps

1. **Immediate**: Review this design document, approve architecture
2. **Week 1**: Set up Supabase database schema
3. **Week 1**: Configure RunPod serverless endpoint
4. **Week 1**: Create GitHub Actions workflow
5. **Week 2**: Implement core scraping and AI services
6. **Week 3**: End-to-end testing with real ATL contacts
7. **Week 4**: Production deployment and monitoring

---

## Appendix: Environment Variables

**Required Environment Variables** (store in GitHub Secrets + Supabase):

```bash
# Database
DATABASE_URL=postgresql://postgres:[PASSWORD]@db.[PROJECT].supabase.co:5432/postgres
REDIS_URL=rediss://default:[PASSWORD]@[ENDPOINT]:6379

# Close CRM
CLOSE_API_KEY=api_7XGY8uyh1B8kPO2JUUprXl.21kpTTohPsn5G1IGK2hps0
CLOSE_DEFAULT_OWNER_USER_ID=user_RCfVbzPJJUMj6HDQ8JGtpBkouK7fMB25X15B08FUpt1

# AI Providers
ANTHROPIC_API_KEY=sk-ant-api03-...
DEEPSEEK_API_KEY=sk-9dea183cc865...
OPENROUTER_API_KEY=sk-or-v1-314933...

# Social Media
LINKEDIN_EMAIL=your_email@gmail.com
LINKEDIN_PASSWORD=your_secure_password
TWITTER_API_KEY=your_twitter_key
TWITTER_API_SECRET=your_twitter_secret
TWITTER_BEARER_TOKEN=your_bearer_token

# Notifications
NOTIFICATION_EMAIL=tim@coperniq.com
SMTP_SERVER=smtp.gmail.com
SMTP_USERNAME=your_gmail@gmail.com
SMTP_PASSWORD=your_app_password
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-16
**Approved By**: Tim Kipper
**Implementation Start**: 2025-11-17
