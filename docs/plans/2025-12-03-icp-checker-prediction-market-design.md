# ICP Checker Worker + Lead Prediction Market Agent

**Date:** December 3, 2025
**Status:** Design Approved, Migration Complete
**Migration:** `backend/migrations/2025-12-03-icp-checker-prediction-market.sql`

---

## Overview

Two new components for the Sales Agent autonomous pipeline:

1. **ICP Checker Worker** - Pure Python service that re-scores leads when data changes
2. **Lead Prediction Market Agent** - Hybrid algorithm + LLM agent that ranks leads by follow-up priority

---

## Agent 1: ICP Checker Worker

### Purpose
Automatically recalculate ICP scores and tiers when lead data is enriched by other agents or manual BDR updates.

### Architecture
- **Type:** Pure Python + Celery (no LLM - deterministic scoring)
- **Trigger:** Hybrid
  - Scheduled sweep every 15 minutes
  - Event-driven for high-value changes (phone/email added)
  - Manual trigger via Claude Code

### Data Flow
```
Enrichment Event → ICP Checker Worker → Update dim_companies → Trigger Prediction Market
```

### Components

| File | Purpose |
|------|---------|
| `backend/app/services/icp_scorer.py` | Pure Python ICP scoring service (extracted from create_gold_standard_lists.py) |
| `backend/app/tasks/icp_tasks.py` | Celery tasks for scheduled/event-driven scoring |

### Celery Beat Schedule
```python
"icp-checker-every-15-min": {
    "task": "run_icp_checker",
    "schedule": 900.0,  # 15 minutes
    "args": (),
    "options": {"queue": "default"},
}
```

### Database Columns (dim_companies)
- `icp_last_checked` (TIMESTAMPTZ) - When ICP was last recalculated
- `icp_score_previous` (FLOAT) - Previous score for change detection

### Key Functions
```python
# icp_scorer.py
def calculate_icp_score(company: dict) -> tuple[float, str]:
    """
    Calculate ICP score and tier for a company.

    Returns:
        (score: float, tier: str)  # tier = PLATINUM/GOLD/SILVER/BRONZE/LEAD
    """

def check_and_update_icp(company_id: UUID) -> dict:
    """
    Check if ICP needs recalculation, update if changed.

    Returns:
        {"changed": bool, "old_score": float, "new_score": float, "old_tier": str, "new_tier": str}
    """
```

### Notification Logic
- Slack alert when tier upgrades (e.g., BRONZE → SILVER)
- No alert for score changes within same tier

---

## Agent 2: Lead Prediction Market

### Purpose
Rank leads by follow-up priority using multi-factor scoring, with LLM-generated "why call now" reasoning for top leads.

### Architecture
- **Type:** Hybrid (Algorithm + LangGraph agent for LLM insights)
- **Algorithm:** Weighted scoring formula
- **LLM:** OpenRouter (Qwen/DeepSeek/Mixtral) for top-10 "why now" reasoning
- **Schedule:** Every 5 minutes + 7 AM EST morning briefing

### Scoring Formula
```
prediction_score =
    (icp_score × 0.35)           # Quality
  + (revenue_potential × 0.25)   # Size/deal value
  + (momentum_score × 0.25)      # Recent activity
  + (recency_boost × 0.15)       # Freshness
```

### Momentum Signals (fact_lead_signals)
| Signal Type | Weight | Description |
|-------------|--------|-------------|
| `phone_added` | 2.0 | Direct phone discovered |
| `email_added` | 1.5 | Email discovered |
| `stage_change` | 1.5 | Lead progressed (COLD→WARM→HOT) |
| `enrichment` | 1.0 | New data from any agent |
| `bdr_note` | 1.2 | Manual BDR activity |
| `email_open` | 1.3 | Outreach engagement |

### Output Channels
1. **Live Leaderboard API** - `GET /api/v1/leads/rankings`
2. **Slack Alerts** - When rank changes by 3+ spots or new #1
3. **Morning Briefing** - Daily at 7 AM EST (2 hrs before work)

### Components

| File | Purpose |
|------|---------|
| `backend/app/services/prediction_market.py` | Core algorithmic scoring |
| `backend/app/services/langgraph/agents/lead_prediction_agent.py` | LangGraph agent for LLM insights |
| `backend/app/tasks/prediction_tasks.py` | Celery tasks for ranking updates |
| `backend/app/api/v1/endpoints/rankings.py` | API endpoint for leaderboard |

### Celery Beat Schedule
```python
"prediction-market-every-5-min": {
    "task": "run_prediction_market",
    "schedule": 300.0,  # 5 minutes
    "args": (),
    "options": {"queue": "default"},
},
"morning-briefing-7am-est": {
    "task": "run_morning_briefing",
    "schedule": crontab(hour=12, minute=0),  # 7 AM EST = 12:00 UTC
    "args": (10,),  # top_n=10
    "options": {"queue": "workflows"},
}
```

### Database Columns (dim_companies)
- `prediction_score` (FLOAT) - Current prediction score
- `prediction_rank` (INTEGER) - Current ranking position
- `prediction_why_now` (TEXT) - LLM-generated call reasoning
- `prediction_updated_at` (TIMESTAMPTZ) - Last recalculation

### New Table: fact_lead_signals
```sql
CREATE TABLE fact_lead_signals (
    id UUID PRIMARY KEY,
    company_id UUID REFERENCES dim_companies(company_id),
    signal_type VARCHAR(50),
    signal_value JSONB,
    weight FLOAT DEFAULT 1.0,
    created_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ  -- Signals decay after 7 days
);
```

---

## Integration Points

### Agent Communication
```
LeadScoutAgent ──────┐
QualificationAgent ──┤
EnrichmentAgent ─────┼──→ INSERT signal → ICP Checker → Prediction Market
BDRAgent ────────────┤
SalesIntelAgent ─────┘
```

### Supabase (Source of Truth)
All reads/writes go through Supabase client:
- `dim_companies` - Lead data + prediction columns
- `dim_contacts` - Contact data
- `fact_lead_signals` - Momentum tracking

### Manual Trigger Commands
```bash
# Run ICP Checker now
python -c "from app.tasks.icp_tasks import run_icp_checker; run_icp_checker.delay()"

# Run Prediction Market now
python -c "from app.tasks.prediction_tasks import run_prediction_market; run_prediction_market.delay()"

# Get current top-10 with LLM reasoning
python -c "from app.tasks.prediction_tasks import run_morning_briefing; run_morning_briefing.delay(10)"
```

---

## Success Criteria

1. **ICP Checker** - Scores recalculated within 15 minutes of enrichment
2. **Prediction Market** - Rankings updated every 5 minutes
3. **Morning Briefing** - Tim receives top-10 with "why call now" at 7 AM EST
4. **Slack Alerts** - Notifications for significant rank changes
5. **API** - `/api/v1/leads/rankings` returns current leaderboard

---

## Cost Estimates

| Component | Cost/Run | Frequency | Daily Cost |
|-----------|----------|-----------|------------|
| ICP Checker | $0 | 96/day | $0 |
| Prediction Market (algo) | $0 | 288/day | $0 |
| Morning Briefing (LLM) | ~$0.02 | 1/day | $0.02 |
| Slack Alerts | $0 | ~10/day | $0 |

**Total:** ~$0.02/day (only LLM reasoning costs)
