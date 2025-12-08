# START TOMORROW - December 8, 2025

## Executive Summary

**TONIGHT'S STATUS (Dec 7, 11:30 PM CST)**:
- Dashboard: LIVE at Vercel with Solarized Dark theme
- Enriched: 152 companies (1.7% of 8,896)
- PLATINUM leads: 126 (up from 6!)
- ATL Contacts: 487
- Draft Queue: FIXED and wired to live API

**CRITICAL FIX NEEDED**: Celery enrichment wasn't running! Added to schedule tonight.

---

## Part 1: What Was Fixed Tonight

### 1. Draft Queue Wiring
- Fixed API path: `/api/ai/drafts` → `/api/v1/ai/drafts`
- Made endpoint public (internal tool)
- Fixed schema mismatch: `id` → `draft_id`, `created_at` → `generated_at`

### 2. Agent Squad Live Status
- Changed from static mock to live FastAPI status
- Dashboard now shows real agent health

### 3. Celery Schedule Fixes
```python
# BEFORE: PredictionAgent hogging worker (6+ min every 5 min!)
"prediction-agent-every-5-min": {
    "schedule": 300.0,  # PROBLEM!
}

# AFTER: Runs twice daily
"prediction-agent-twice-daily": {
    "schedule": crontab(hour="6,18", minute=0),  # 6 AM and 6 PM
}

# NEW: Website enrichment every 5 min
"website-enrichment-continuous": {
    "task": "run_website_enrichment_batch",
    "schedule": 300.0,
    "args": (5,),  # 5 companies per batch = 60/hour = 1,440/day
}
```

---

## Part 2: Best Practices Audit (From Anthropic + LangChain Docs)

### Sources Reviewed
- [Anthropic: Effective Harnesses for Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Anthropic: Context Engineering for AI Agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [LangChain Deep Agents](https://github.com/langchain-ai/deepagents)
- [Claude 4 Best Practices](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-4-best-practices)

### What We're Missing vs Best Practices

| Best Practice | Current State | Gap |
|--------------|---------------|-----|
| **Subagent Delegation** | Agents run independently | No orchestrator spawning subagents |
| **write_todos Planning** | No task decomposition | Agents don't break down work |
| **File System Context Offloading** | Everything in memory | Large context windows, no persistence |
| **Checkpointing** | No state persistence | Agents restart from scratch |
| **Structured Note-Taking** | audit_log only | No NOTES.md or knowledge base |
| **Just-in-Time Context** | Pre-load everything | Should load on-demand |
| **Compaction/Summarization** | No context trimming | Risk of context rot |
| **LangSmith Observability** | Disabled (403 errors) | No tracing, no metrics |

### Priority Fixes

1. **Enable LangSmith** - Get API key, enable tracing
2. **Add Checkpointing** - PostgresSaver for Supabase
3. **Subagent Architecture** - Signal Scout → Deep Hunter → Intake Commander
4. **Structured Notes** - Write findings to Supabase `agent_notes` table

---

## Part 3: Observability Dashboards (Open Source)

### Recommended Stack

#### Option A: Langfuse (RECOMMENDED)
**GitHub**: https://github.com/langfuse/langfuse
- Open source, self-hostable
- LangGraph/LangChain integration built-in
- Trace visualization, evals, prompt management
- PostgreSQL backend (can share with Supabase!)

```bash
# Self-host with Docker
docker run -d -p 3000:3000 \
  -e DATABASE_URL=postgresql://... \
  -e NEXTAUTH_SECRET=... \
  langfuse/langfuse
```

#### Option B: Arize Phoenix
**GitHub**: https://github.com/Arize-ai/phoenix
- OpenTelemetry native
- Hallucination detection built-in
- Great for RAG pipelines

#### Option C: Flower + Grafana (For Celery)
**GitHub**: https://github.com/mher/flower
- Real-time Celery monitoring
- Export to Prometheus → Grafana dashboards
- See: https://grafana.com/grafana/dashboards/20076-celery-tasks-dashboard/

### Dashboard Integration Plan

```
┌─────────────────────────────────────────────────────────────────┐
│                    CONTRACTOR HUNTER DASHBOARD                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ LANGFUSE    │  │ FLOWER      │  │ SUPABASE    │             │
│  │ Agent Traces│  │ Celery Tasks│  │ Live Data   │             │
│  │ iframe/API  │  │ iframe/API  │  │ Direct      │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
│  ┌────────────────────────────────────────────────────────┐    │
│  │ AGENT OBSERVABILITY PANEL                              │    │
│  │ ─────────────────────────────────────────────────────  │    │
│  │ 🔭 Signal Scout    [IDLE]     Last: 2h ago   Traces: 47│    │
│  │ 🕵️ Deep Hunter      [ACTIVE]   Running: 3m   Cost: $0.02│    │
│  │ ⚡ Intake Commander [WAITING]  Queue: 12     Deduped: 8 │    │
│  │ 🤖 Enrichment       [ACTIVE]   Rate: 60/hr   Today: 127│    │
│  └────────────────────────────────────────────────────────┘    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Part 4: Elite Agent Team Architecture

### The Trifecta Hunter Squad

```
╔════════════════════════════════════════════════════════════════════╗
║  🎖️ TRIFECTA HUNTER ELITE TEAM                      SPEC OPS       ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  ┌─────────────────────────────────────────────────────────────┐  ║
║  │  🔭 SIGNAL SCOUT                                             │  ║
║  │  ─────────────────────────────────────────────────────────── │  ║
║  │  Mission: Detect emerging market opportunities               │  ║
║  │  Triggers: Close CRM inbound, win rate spikes, 3+ leads/wk  │  ║
║  │  Output: Scraping orders for Deep Hunter                     │  ║
║  │  Model: Cerebras (fast detection)                            │  ║
║  └─────────────────────────────────────────────────────────────┘  ║
║                              │                                     ║
║                              ▼                                     ║
║  ┌─────────────────────────────────────────────────────────────┐  ║
║  │  🕵️ DEEP HUNTER                                              │  ║
║  │  ─────────────────────────────────────────────────────────── │  ║
║  │  Mission: Orchestrate dealer-scraper-mvp operations          │  ║
║  │  Controls: ScraperFactory (20+ OEM scrapers)                 │  ║
║  │  Actions: Cross-reference OEMs, find Trifecta companies      │  ║
║  │  Model: DeepSeek (cost-effective for long research)          │  ║
║  └─────────────────────────────────────────────────────────────┘  ║
║                              │                                     ║
║                              ▼                                     ║
║  ┌─────────────────────────────────────────────────────────────┐  ║
║  │  ⚡ INTAKE COMMANDER                                         │  ║
║  │  ─────────────────────────────────────────────────────────── │  ║
║  │  Mission: Quality gate for all incoming leads                │  ║
║  │  Checks: Close CRM dedup, Supabase dedup, garbage filter     │  ║
║  │  Actions: Score immediately, route HOT to BDR queue          │  ║
║  │  Model: Cerebras (fast processing)                           │  ║
║  └─────────────────────────────────────────────────────────────┘  ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
```

### Trifecta Scoring (Find the Unicorns!)

```python
def calculate_trifecta_score(company) -> int:
    """
    Find Trifecta companies: Solar + Generator + Battery
    These are the UNICORNS - highest value contractors
    """
    score = 0
    signals = []

    # 1. TRADE DIVERSITY (25 pts)
    trades = len(company.services_offered or [])
    if trades >= 5:
        score += 25
        signals.append("5+ trades (BOSS)")
    elif trades >= 3:
        score += 18
    elif trades >= 2:
        score += 12

    # 2. ENERGY TRIFECTA (25 pts) - THE HOLY GRAIL
    has_solar = any(oem in SOLAR_OEMS for oem in company.oem_brands)
    has_generator = any(oem in GENERATOR_OEMS for oem in company.oem_brands)
    has_battery = any(oem in BATTERY_OEMS for oem in company.oem_brands)

    trifecta_count = sum([has_solar, has_generator, has_battery])
    if trifecta_count == 3:
        score += 25
        signals.append("☀️⚡🔋 FULL TRIFECTA!")
    elif trifecta_count == 2:
        score += 18
        signals.append(f"Partial trifecta ({trifecta_count}/3)")

    # 3. OEM BREADTH (20 pts) - Multi-platform pain = our solution
    oem_count = len(company.oem_brands or [])
    if oem_count >= 6:
        score += 20
        signals.append(f"{oem_count} OEMs (multi-platform pain!)")
    elif oem_count >= 3:
        score += 12

    # 4. GEOGRAPHIC REACH (15 pts)
    states = len(company.states_served or [])
    if states >= 5:
        score += 15
        signals.append(f"{states} states (regional player)")
    elif states >= 2:
        score += 10

    # 5. CONTACT QUALITY (15 pts)
    if company.atl_contact and company.email and company.direct_phone:
        score += 15
        signals.append("ATL + email + direct phone")

    return score, signals
```

### OEM Brand Categories

```python
# The Trifecta components
SOLAR_OEMS = ["Enphase", "SolarEdge", "SMA", "Tesla Solar", "Fronius", "Sungrow"]
GENERATOR_OEMS = ["Generac", "Kohler", "Cummins", "Briggs & Stratton", "Champion"]
BATTERY_OEMS = ["Tesla Powerwall", "Generac PWRcell", "Enphase IQ", "LG Chem", "Sonnen"]

# Premium multipliers
PREMIUM_OEMS = {
    "Tesla": 1.5,
    "Enphase": 1.4,
    "Generac": 1.3,
    "SolarEdge": 1.3,
}
```

---

## Part 5: dealer-scraper-mvp Integration

### Current State
- Location: `/Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp`
- 20+ OEM scrapers in ScraperFactory
- SQLite pipeline.db for staging
- NOT integrated with sales-agent Celery

### Tomorrow's Task: Create Scraper Celery Worker

**New file**: `dealer-scraper-mvp/scraper_celery.py`

```python
"""
Dealer Scraper Celery Worker

Runs 24/7 on M1 Mac alongside sales-agent worker.
Continuously fills the pipeline with ICP-qualified contractors.
"""

from celery import Celery
from celery.schedules import crontab

REDIS_URL = 'redis://localhost:6379/1'  # DB 1 (sales-agent uses DB 0)

app = Celery('dealer_scraper')

app.conf.beat_schedule = {
    # State license scraping (off-peak hours)
    'texas-licenses-daily': {
        'task': 'scrape_state_licenses',
        'schedule': crontab(hour=2, minute=0),
        'args': ['TX'],
    },
    'florida-licenses-daily': {
        'task': 'scrape_state_licenses',
        'schedule': crontab(hour=3, minute=0),
        'args': ['FL'],
    },
    'california-licenses-daily': {
        'task': 'scrape_state_licenses',
        'schedule': crontab(hour=4, minute=0),
        'args': ['CA'],
    },

    # OEM dealer network scraping (weekly)
    'generac-dealers-weekly': {
        'task': 'scrape_oem_dealers',
        'schedule': crontab(hour=6, day_of_week='monday'),
        'args': ['generac', ['TX', 'FL', 'CA', 'NY', 'PA']],
    },
    'enphase-dealers-weekly': {
        'task': 'scrape_oem_dealers',
        'schedule': crontab(hour=6, day_of_week='wednesday'),
        'args': ['enphase', ['TX', 'FL', 'CA', 'AZ', 'NV']],
    },

    # Push to sales-agent every 15 min
    'push-new-leads': {
        'task': 'push_to_sales_agent',
        'schedule': 900.0,
    },
}
```

### Dual Supabase + Dual Celery Architecture

**MASTER SOURCE OF TRUTH**: sales-agent Supabase (syncs from Close CRM + dealer-scraper)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DATA FLOW ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────────┐         ┌───────────────────────────────────────┐   │
│  │ 📞 CLOSE CRM      │────────▶│     🎯 SALES-AGENT SUPABASE           │   │
│  │ (Inbound leads)   │  sync   │     (MASTER SOURCE OF TRUTH)          │   │
│  └───────────────────┘         │                                       │   │
│                                │  • dim_companies (8,896+)             │   │
│  ┌───────────────────┐         │  • dim_contacts (781+)                │   │
│  │ 🕷️ DEALER-SCRAPER  │────────▶│  • lead_audit_log                    │   │
│  │ SUPABASE          │  push   │  • dim_ai_drafts                      │   │
│  │ (Raw scrape data) │         │  • fact_lead_signals                  │   │
│  └───────────────────┘         └───────────────────────────────────────┘   │
│         │                                      │                            │
│         │                                      │                            │
│         ▼                                      ▼                            │
│  ┌───────────────────┐         ┌───────────────────────────────────────┐   │
│  │ dealer-scraper    │         │     CONTRACTOR HUNTER DASHBOARD       │   │
│  │ Supabase Tables:  │         │     (React + Vite + SWR)              │   │
│  │ • raw_dealers     │         │                                       │   │
│  │ • oem_mappings    │         │  Reads from: sales-agent Supabase     │   │
│  │ • scrape_logs     │         │  (Single source of truth)             │   │
│  │ • pipeline_queue  │         │                                       │   │
│  └───────────────────┘         └───────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                    MACBOOK M1 - 24/7 OPERATION                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────────────────────┐  ┌─────────────────────────┐  │
│  │ 🤖 SALES-AGENT CELERY           │  │ 🕷️ DEALER-SCRAPER CELERY │  │
│  │ Redis DB 0                      │  │ Redis DB 1              │  │
│  │ Supabase: MASTER                │  │ Supabase: OWN (raw)     │  │
│  ├─────────────────────────────────┤  ├─────────────────────────┤  │
│  │ QUEUES:                         │  │ QUEUES:                 │  │
│  │ • default (agents)              │  │ • license_scrape        │  │
│  │ • workflows (BDR, Growth)       │  │ • oem_scrape            │  │
│  │ • enrichment (website scrape)   │  │ • website_scrape        │  │
│  │ • crm_sync (Close)              │  │ • cross_reference       │  │
│  ├─────────────────────────────────┤  ├─────────────────────────┤  │
│  │ TASKS:                          │  │ TASKS:                  │  │
│  │ • Website enrichment (5 min)    │  │ • TX Licenses (daily)   │  │
│  │ • ICP Checker (15 min)          │  │ • FL Licenses (daily)   │  │
│  │ • Scout Agent (30 min)          │  │ • OEM Networks (weekly) │  │
│  │ • BDR Outreach (hourly)         │  │ • Push qualified leads  │  │
│  │ • Prediction (12 hr)            │  │   to MASTER Supabase    │  │
│  └─────────────────────────────────┘  └─────────────────────────┘  │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### Why Two Supabase Instances?

| Purpose | sales-agent Supabase | dealer-scraper Supabase |
|---------|---------------------|------------------------|
| **Role** | MASTER (source of truth) | Raw scrape staging |
| **Data** | Clean, scored, deduplicated | Raw, may have dupes |
| **Access** | Dashboard, Close CRM, APIs | Internal only |
| **Tables** | dim_companies, dim_contacts | raw_dealers, scrape_logs |
| **Retention** | Permanent | Temporary (rotate) |

### Sync Flow

```python
# dealer-scraper pushes to sales-agent (one-way)
async def push_qualified_leads(leads: list[Lead]):
    """
    Push qualified leads from dealer-scraper to sales-agent Supabase.
    Only pushes leads that:
    1. Pass minimum quality threshold
    2. Don't already exist in sales-agent
    3. Have been cross-referenced for OEM certifications
    """
    sales_agent_supabase = create_client(
        SALES_AGENT_SUPABASE_URL,
        SALES_AGENT_SUPABASE_KEY
    )

    for lead in leads:
        # Check if exists (dedup)
        existing = sales_agent_supabase.table('dim_companies').select('company_id').eq(
            'normalized_name', normalize(lead.company_name)
        ).execute()

        if not existing.data:
            # Insert new lead
            sales_agent_supabase.table('dim_companies').insert({
                'company_name': lead.company_name,
                'domain': lead.domain,
                'phone': lead.phone,
                'source': 'dealer_scraper',
                'oem_brands': lead.oem_brands,
                # ... other fields
            }).execute()

            # Log the import
            sales_agent_supabase.table('lead_audit_log').insert({
                'company_name': lead.company_name,
                'event_type': 'imported_from_scraper',
                'details': {'source_scraper': lead.source_oem}
            }).execute()
```

### Startup Script

**Create**: `/Users/tmkipper/Desktop/tk_projects/start_all_workers.sh`

```bash
#!/bin/bash
# Start both Celery workers for 24/7 operation

echo "🚀 Starting Coperniq 24/7 Pipeline..."

# Start Redis if not running
if ! pgrep -x "redis-server" > /dev/null; then
    echo "📦 Starting Redis..."
    redis-server --daemonize yes
fi

# Kill existing workers
pkill -f 'celery.*sales-agent' 2>/dev/null
pkill -f 'celery.*dealer-scraper' 2>/dev/null
sleep 2

# Start Sales-Agent Celery
echo "🤖 Starting Sales-Agent Celery..."
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
source ../venv/bin/activate
celery -A app.celery_app worker --beat --loglevel=info \
    -Q default,workflows,enrichment,crm_sync \
    --hostname=sales-agent@%h \
    --logfile=/tmp/celery-sales-agent.log \
    --detach

# Start Dealer-Scraper Celery (after we create it)
# echo "🕷️ Starting Dealer-Scraper Celery..."
# cd /Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp
# source venv/bin/activate
# celery -A scraper_celery worker --beat --loglevel=info \
#     -Q license_scrape,oem_scrape,website_scrape \
#     --hostname=dealer-scraper@%h \
#     --logfile=/tmp/celery-dealer-scraper.log \
#     --detach

echo "✅ Workers started!"
echo ""
echo "📊 Monitor with:"
echo "   tail -f /tmp/celery-sales-agent.log"
echo "   # tail -f /tmp/celery-dealer-scraper.log"
```

---

## Part 6: Apollo.io Integration (10,000 Credits!)

### Current State
- 10,000 Apollo credits available
- Not being used automatically
- Manual enrichment only

### Tomorrow: Create Apollo Enrichment Agent

```python
class ApolloEnrichmentAgent:
    """
    Automated Apollo.io enrichment for high-priority leads.

    Strategy:
    1. Only enrich PLATINUM/GOLD tier leads
    2. Use Apollo for contact finding (emails, direct phones)
    3. Rate limit: 100/day to conserve credits
    4. Store results in dim_contacts
    """

    async def enrich_batch(self, company_ids: list[str], limit: int = 100):
        # Get companies needing Apollo enrichment
        companies = await self.get_unenriched_companies(
            tier_in=['PLATINUM', 'GOLD'],
            limit=limit
        )

        for company in companies:
            # Search Apollo for contacts
            contacts = await self.apollo_client.people_search(
                organization_name=company.company_name,
                person_titles=["Owner", "President", "CEO", "VP", "Director"],
                limit=5
            )

            # Insert to dim_contacts
            for contact in contacts:
                await self.insert_contact(
                    company_id=company.company_id,
                    full_name=contact.name,
                    email=contact.email,
                    phone=contact.phone,
                    title=contact.title,
                    source='apollo',
                    is_atl=self.is_atl_title(contact.title)
                )

            # Mark as Apollo enriched
            await self.mark_enriched(company.company_id, 'apollo')

            # Rate limit
            await asyncio.sleep(0.5)
```

---

## Part 7: Tomorrow's Priority Order

### Morning Session (8 AM - 12 PM)

1. **Restart Celery with New Schedule** (15 min)
   ```bash
   cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
   pkill -f celery
   source ../venv/bin/activate
   celery -A app.celery_app worker --beat --loglevel=info \
       -Q default,workflows,enrichment,crm_sync &
   ```

2. **Verify Enrichment Running** (15 min)
   - Watch logs: `tail -f celery_worker.log | grep enrichment`
   - Check Supabase: `ai_enriched_at` count increasing

3. **Set Up Langfuse** (1 hour)
   - Docker deploy or cloud signup
   - Add LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY to .env
   - Enable tracing in agents

4. **Build Signal Scout Agent** (2 hours)
   - Create `signal_scout_agent.py`
   - Query Close CRM for inbound patterns
   - Emit scraping orders

### Afternoon Session (1 PM - 5 PM)

5. **Build Intake Commander Agent** (2 hours)
   - Create `intake_commander_agent.py`
   - Dedup against Close + Supabase
   - Trifecta scoring algorithm
   - Route to BDR queue

6. **Create dealer-scraper Celery** (1 hour)
   - Create `scraper_celery.py`
   - Add beat schedule
   - Test with one OEM

7. **Add Observability Panel to Dashboard** (1 hour)
   - Agent status cards
   - Langfuse trace embed/link
   - Enrichment rate chart

---

## Part 8: Current Live Stats (Dec 7, 11:30 PM)

```
╔════════════════════════════════════════════════════════════════════╗
║  🎮 CONTRACTOR HUNTER - LIVE STATS                                 ║
╠════════════════════════════════════════════════════════════════════╣
║                                                                    ║
║  🏢 TOTAL CONTRACTORS:     8,896                                   ║
║  🔥 ENRICHED (AI scraped):   152  (1.7%)                          ║
║  🌐 WITH DOMAINS:          3,645                                   ║
║                                                                    ║
║  ───────────────────────────────────────────────────────────────── ║
║  ICP TIER BREAKDOWN                                                ║
║  ───────────────────────────────────────────────────────────────── ║
║  💎 PLATINUM:   126  (was 6 - 20x increase!)                       ║
║  🥇 GOLD:         5  (was 1)                                       ║
║  🥈 SILVER:     720  (was 360)                                     ║
║  🥉 BRONZE:   5,752                                                ║
║                                                                    ║
║  ───────────────────────────────────────────────────────────────── ║
║  CONTACTS                                                          ║
║  ───────────────────────────────────────────────────────────────── ║
║  👔 ATL CONTACTS:  487  (of 781 total)                            ║
║  📧 WITH EMAILS:   525                                             ║
║  📞 WITH PHONES:   328                                             ║
║                                                                    ║
║  ───────────────────────────────────────────────────────────────── ║
║  APOLLO CREDITS:  10,000 available                                 ║
║  ───────────────────────────────────────────────────────────────── ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
```

---

## Part 9: Files Modified Tonight

### sales-agent/backend/
- `app/celery_app.py` - Added enrichment task, changed prediction schedule
- `app/tasks/enrichment_tasks.py` - NEW: Website enrichment Celery task
- `app/api/ai_outreach.py` - Fixed /ai/drafts endpoint

### sales-agent/dashboard/
- `src/components/MissionControl.tsx` - Live agent status
- `src/components/ai/DraftReviewQueue.tsx` - Fixed API paths

### Commits
- `25a9b2a` - feat: Wire up FastAPI live agent status to dashboard
- `a530a90` - fix: Wire Draft Queue to live FastAPI endpoint

---

## Part 10: Quick Reference Links

### Documentation
- [Anthropic Long-Running Agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [LangChain Deep Agents](https://github.com/langchain-ai/deepagents)
- [LangGraph Docs](https://github.com/langchain-ai/langgraph)

### Open Source Dashboards
- [Langfuse](https://github.com/langfuse/langfuse) - LLM observability
- [Arize Phoenix](https://github.com/Arize-ai/phoenix) - AI observability
- [Flower](https://github.com/mher/flower) - Celery monitoring
- [celery-dashboard](https://github.com/mehdigmira/celery-dashboard) - PostgreSQL-backed

### Our Repos
- [sales-agent](https://github.com/ScientiaCapital/sales-agent)
- dealer-scraper-mvp (local only for now)

---

## Summary: The Mission

**Goal**: Find Trifecta companies (Solar + Generator + Battery) = UNICORNS

**Method**:
1. **Signal Scout** detects market opportunities
2. **Deep Hunter** orchestrates scraping across OEM networks
3. **Intake Commander** dedupes, scores, routes to BDR
4. **Website Enrichment** runs 24/7 (60/hour = 1,440/day)
5. **Apollo Enrichment** for PLATINUM/GOLD contacts

**Metrics to Watch**:
- Enrichment rate: Target 100+/hour
- PLATINUM leads: Target 500+ by end of week
- Trifecta companies: Count and track separately
- ATL contact coverage: Target 80%+

**Let's hunt some unicorns! 🦄**
