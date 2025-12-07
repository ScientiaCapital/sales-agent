# Start Here - December 8, 2025

## What Was Completed (Dec 7)

**BDR/SDR Automation System - Phases 1-6 COMPLETE**

Commit: `3fc3a41` - 48 files, 11,758 insertions
GitHub: Synced to main

---

## New Architecture (7 Agents)

| Agent | Schedule | What It Does |
|-------|----------|--------------|
| **ScoutAgent** | Every 30 min | Scrapes websites + LinkedIn for ATL/BTL contacts |
| **RankingAgent** | Every 10 min | Calculates ICP scores, assigns tiers (PLATINUM/GOLD/SILVER/BRONZE) |
| **SyncAgent** | Every 5 min | Syncs activities from Close CRM, handles replies |
| **BriefingAgent** | 7:30 AM EST | Morning prep with "why call now" reasoning |
| **DropInAgent** | On-demand | Universal input handler (URL, name, Close ID) |
| **LinkedInAgent** | Daily + events | LinkedIn connection requests + messages |
| **OutreachAgent** | Hourly | Email/SMS/Call draft generation |

---

## 4 Ways to Trigger Enrichment

### 1. Terminal CLI
```bash
cd backend && source ../venv/bin/activate
python -m cli.enrich "https://acme-hvac.com"
python -m cli.enrich "Acme HVAC" --type name
python -m cli.enrich "lead_abc123" --type close_id
python -m cli.enrich "https://acme.com" --stage email,sms
```

### 2. Claude Code Session
```
/enrich https://acme-hvac.com
/enrich "Acme HVAC" --stage email,linkedin
```

### 3. Slack Command
```
/enrich https://acme-hvac.com
/enrich "John Smith at Acme HVAC"
```

### 4. Close CRM Webhook (Automatic)
- New lead enters "Raw" stage → Auto-enriched by ScoutAgent
- Lead status changes to "Qualified" → RankingAgent recalculates
- Email received → SyncAgent processes reply

---

## Key Files Created

```
backend/
├── app/
│   ├── api/
│   │   ├── slack_commands.py      # Slack /enrich handler
│   │   └── webhooks/close.py      # Close CRM webhook endpoint
│   ├── services/
│   │   ├── langgraph/agents/
│   │   │   ├── scout_agent.py     # Website + LinkedIn scraping
│   │   │   ├── ranking_agent.py   # ICP scoring + prediction
│   │   │   ├── sync_agent.py      # Close CRM sync
│   │   │   ├── briefing_agent.py  # Morning prep
│   │   │   ├── dropin_agent.py    # Universal input handler
│   │   │   └── linkedin_agent.py  # Social selling
│   │   ├── browser/
│   │   │   ├── browserbase_client.py  # Cloud browser client
│   │   │   └── linkedin_session.py    # LinkedIn auth manager
│   │   └── staging_service.py     # Draft/Auto/Review modes
│   ├── tasks/
│   │   ├── scout_tasks.py
│   │   ├── ranking_tasks.py
│   │   ├── sync_tasks.py
│   │   ├── briefing_tasks.py
│   │   ├── dropin_tasks.py
│   │   └── linkedin_tasks.py
│   └── models/
│       └── outreach.py            # StagingMode, OutreachChannel enums
├── cli/
│   ├── __main__.py                # Entry: python -m cli.enrich
│   ├── enrich.py                  # Main enrich command
│   ├── staging.py                 # Outreach staging options
│   └── formatters.py              # Pretty terminal output
```

---

## What to Do Next (Priority Order)

### Priority 1: Test the New Agents
```bash
cd backend && source ../venv/bin/activate

# Test CLI enrichment
python -m cli.enrich "https://example-hvac.com" --dry-run

# Test Celery worker with new tasks
celery -A app.celery_app worker --loglevel=info

# In another terminal, trigger scout manually
python -c "from app.tasks.scout_tasks import run_scout_cycle; run_scout_cycle.delay()"
```

### Priority 2: Configure Browserbase (for LinkedIn)
1. Sign up at https://browserbase.com
2. Get API key and Project ID
3. Add to `.env`:
   ```
   BROWSERBASE_API_KEY=bb_...
   BROWSERBASE_PROJECT_ID=proj_...
   ```
4. Log into LinkedIn once via Browserbase console to create persistent session

### Priority 3: Register Close Webhooks
```bash
# Use Close API to register webhook endpoint
curl -X POST "https://api.close.com/api/v1/webhook/" \
  -H "Authorization: Basic $CLOSE_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-api.com/api/v1/webhooks/close/events",
    "events": [
      {"object_type": "lead", "action": "created"},
      {"object_type": "lead", "action": "status_changed"},
      {"object_type": "activity", "action": "created"}
    ]
  }'
```

### Priority 4: Create Slack App
1. Create Slack app at https://api.slack.com/apps
2. Add slash command `/enrich`
3. Point to: `https://your-api.com/api/v1/slack/commands/enrich`
4. Add to `.env`:
   ```
   SLACK_BOT_TOKEN=xoxb-...
   SLACK_SIGNING_SECRET=...
   ```

---

## Testing Checklist

- [ ] CLI enrichment works: `python -m cli.enrich "test.com"`
- [ ] Celery worker starts without errors
- [ ] ScoutAgent runs on schedule (check logs)
- [ ] RankingAgent recalculates after enrichment
- [ ] Browserbase connection established
- [ ] LinkedIn session persists between runs
- [ ] Close webhook receives test event
- [ ] Slack command responds

---

## Code Review Findings (to address later)

From Dec 7 code review (70% production ready):

| Priority | Issue | File |
|----------|-------|------|
| Important | Add unit tests for new agents | tests/ |
| Important | Migrate Pydantic v1 validators to v2 | Various |
| Minor | Add retry logic to browserbase_client.py | browser/ |
| Minor | Logging improvements | All agents |

---

## Quick Commands Reference

```bash
# Start everything
docker-compose up -d                    # PostgreSQL + Redis
celery -A app.celery_app worker -l info # Worker
celery -A app.celery_app beat -l info   # Scheduler
python start_server.py                  # API server

# Check agent health
curl http://localhost:8001/api/dashboard/agents

# View Celery tasks
celery -A app.celery_app inspect active

# Check recent commits
git log --oneline -10
```

---

## Questions? Contact

- **Plan file**: `.claude/plans/noble-giggling-dawn.md` (full architecture)
- **CLAUDE.md**: `.claude/CLAUDE.md` (project guide)
- **Backlog**: `BACKLOG.md` (remaining items)

---

*Last updated: Dec 7, 2025 @ 5:50 PM EST*
*Commit: 3fc3a41 - feat: Complete BDR/SDR Automation System - Phases 1-6*
