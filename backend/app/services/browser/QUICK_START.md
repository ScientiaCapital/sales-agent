# LinkedIn Agent - Quick Start Guide

## Installation (One-Time Setup)

```bash
# 1. Install dependencies
cd backend
pip install playwright==1.48.0
playwright install chromium

# 2. Add to .env
echo "BROWSERBASE_API_KEY=bb_your_key_here" >> .env
echo "BROWSERBASE_PROJECT_ID=proj_your_project_id" >> .env

# 3. Run database migration
psql $DATABASE_URL < supabase/migrations/20251207_linkedin_action_queue.sql

# 4. First-time login (saves session for future use)
python -c "
import asyncio
from app.services.langgraph.agents import LinkedInAgent

async def setup():
    async with LinkedInAgent() as agent:
        await agent.session.ensure_authenticated()
        print('✅ LinkedIn session saved')

asyncio.run(setup())
"
```

## Basic Usage

### Send Connection Request

```python
from app.services.langgraph.agents import LinkedInAgent

async with LinkedInAgent() as agent:
    result = await agent.send_connection_request(
        profile_url="https://linkedin.com/in/john-smith",
        note="Hi John, saw your work at Acme HVAC!",
    )
    print(result.success, result.message)
```

### Queue Action for Daily Batch

```python
from app.tasks.linkedin_tasks import queue_linkedin_connection

action_id = queue_linkedin_connection(
    lead_id="company-uuid-here",
    profile_url="https://linkedin.com/in/john-smith",
    note="Hi John...",
)
# Runs in daily scheduled task at 9 AM
```

### Check Rate Limits

```python
async with LinkedInAgent() as agent:
    remaining = agent.get_remaining_actions()
    # {'connections': 7, 'messages': 25, ...}
```

## Daily Limits (Safe Defaults)

| Action | Limit/Day |
|--------|-----------|
| Connections | 10 |
| Messages | 25 |
| Reactions | 30 |
| Comments | 20 |
| Profile Views | 50 |

## File Locations

```
backend/
├── app/
│   ├── services/
│   │   ├── browser/
│   │   │   ├── browserbase_client.py    # Cloud browser
│   │   │   ├── linkedin_session.py      # Auth + rate limits
│   │   │   └── README.md                # Full docs
│   │   └── langgraph/agents/
│   │       └── linkedin_agent.py        # Main agent (606 lines)
│   └── tasks/
│       └── linkedin_tasks.py            # Celery tasks (403 lines)
└── supabase/migrations/
    └── 20251207_linkedin_action_queue.sql
```

## Celery Beat Schedule (Add to celery_app.py)

```python
beat_schedule = {
    "linkedin-daily-actions": {
        "task": "run_linkedin_daily_actions",
        "schedule": crontab(hour=9, minute=0),
        "options": {"queue": "linkedin"},
    },
}
```

## Troubleshooting

**Problem**: "Not authenticated" error
**Solution**: Run first-time login script (see Installation step 4)

**Problem**: "Rate limit reached"
**Solution**: Wait until next day or check `get_remaining_actions()`

**Problem**: "Connect button not found"
**Solution**: Verify URL is valid, check if already connected

## Get API Key

1. Go to https://www.browserbase.com
2. Sign up / Login
3. Create new project
4. Copy API key and project ID to `.env`

## View Sessions

Browserbase records all sessions for debugging:
https://www.browserbase.com/sessions
