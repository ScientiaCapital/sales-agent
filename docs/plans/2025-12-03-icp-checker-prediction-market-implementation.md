# Implementation Plan: ICP Checker + Lead Prediction Market

**Date:** December 3, 2025
**Design Doc:** `2025-12-03-icp-checker-prediction-market-design.md`
**Migration:** `backend/migrations/2025-12-03-icp-checker-prediction-market.sql` (DONE)

---

## Implementation Order

```
Task 1: ICP Scorer Service ──► Task 2: ICP Celery Tasks ──► Task 3: Test ICP Checker
                                                                      │
Task 4: Prediction Market Service ◄───────────────────────────────────┘
    │
    ▼
Task 5: Lead Prediction Agent (LLM) ──► Task 6: Prediction Tasks ──► Task 7: Rankings API
    │
    ▼
Task 8: Celery Beat Config ──► Task 9: Integration Test ──► Task 10: Commit
```

---

## Task 1: ICP Scorer Service

**File:** `backend/app/services/icp_scorer.py`

**What to build:**
- Extract ICP scoring logic from `create_gold_standard_lists.py` into reusable service
- Pure Python, no LLM dependencies
- Supabase read/write for company data

**Functions to implement:**
```python
from typing import Tuple, Dict, Any, Optional
from uuid import UUID

def calculate_icp_score(company: Dict[str, Any]) -> Tuple[float, str]:
    """
    Calculate ICP score and tier from company data.

    Scoring algorithm (max ~115 points):
    - has_phone: +20
    - has_email: +5
    - multi_oem (1 OEM = 5pts, cap 15): 0-15
    - multi_trade (1 trade = 3pts, cap 12): 0-12
    - self_performing: +3
    - multi_location (1 state = 4pts, cap 8): 0-8
    - oem_certifications: +5 to +10
    - website: +5
    - employee_count: +2 to +5
    - google_rating: +2 to +5
    - google_reviews: +2 to +5
    - ideal_state_bonus: +5 to +15

    Tier determination:
    - PLATINUM: score >= 80 AND has_phone AND is_oem_certified
    - GOLD: score >= 65 AND has_phone AND has_email
    - SILVER: score >= 50 AND has_phone
    - BRONZE: score >= 35 AND (has_phone OR has_email)
    - LEAD: has domain

    Args:
        company: Dict with company data from dim_companies

    Returns:
        (score, tier) tuple
    """
    pass

async def check_and_update_icp(company_id: UUID) -> Dict[str, Any]:
    """
    Check if company needs ICP recalculation, update if changed.

    Returns:
        {
            "changed": bool,
            "old_score": float,
            "new_score": float,
            "old_tier": str,
            "new_tier": str,
            "tier_upgraded": bool
        }
    """
    pass

async def batch_check_icp(limit: int = 100) -> Dict[str, Any]:
    """
    Check ICP for recently modified companies.

    Queries companies where updated_at > icp_last_checked.

    Returns:
        {
            "checked": int,
            "changed": int,
            "upgrades": List[{"company_id": UUID, "company_name": str, "old_tier": str, "new_tier": str}]
        }
    """
    pass
```

**Verification:**
```bash
cd backend && python -c "from app.services.icp_scorer import calculate_icp_score; print('OK')"
```

---

## Task 2: ICP Celery Tasks

**File:** `backend/app/tasks/icp_tasks.py`

**What to build:**
- Celery task wrappers for ICP scorer functions
- Event hook that other agents can call after enrichment

**Tasks to implement:**
```python
from app.celery_app import celery_app

@celery_app.task(name="run_icp_checker", bind=True)
def run_icp_checker_task(self, limit: int = 100):
    """
    Scheduled task: Check ICP for recently modified companies.

    Called every 15 minutes by Celery Beat.
    """
    pass

@celery_app.task(name="recheck_icp_for_company")
def recheck_icp_for_company_task(company_id: str):
    """
    Event-driven task: Recheck ICP for a specific company.

    Called by other agents after enrichment.
    Usage: recheck_icp_for_company_task.delay(str(company_id))
    """
    pass
```

**Update:** Add to `celery_app.py` includes:
```python
include=[
    "app.tasks.agent_tasks",
    "app.tasks.batch_tasks",
    "app.tasks.icp_tasks",  # ADD THIS
]
```

**Verification:**
```bash
cd backend && python -c "from app.tasks.icp_tasks import run_icp_checker_task; print('OK')"
```

---

## Task 3: Test ICP Checker

**Manual test:**
```bash
cd backend && source ../venv/bin/activate

# Test scoring function
python -c "
from app.services.icp_scorer import calculate_icp_score

test_company = {
    'phone': '+1234567890',
    'email': 'test@example.com',
    'oem_brands': ['Carrier', 'Trane'],
    'state': 'TX',
    'employee_count': 50,
    'google_rating': 4.7,
    'google_review_count': 120,
}
score, tier = calculate_icp_score(test_company)
print(f'Score: {score}, Tier: {tier}')
"

# Test Celery task
python -c "from app.tasks.icp_tasks import run_icp_checker_task; run_icp_checker_task.delay(10)"
```

---

## Task 4: Prediction Market Service

**File:** `backend/app/services/prediction_market.py`

**What to build:**
- Algorithmic scoring for lead prioritization
- Signal aggregation from fact_lead_signals
- Ranking calculation and storage

**Functions to implement:**
```python
from typing import Dict, Any, List
from uuid import UUID

async def calculate_momentum_score(company_id: UUID) -> float:
    """
    Calculate momentum score from recent signals.

    Queries fact_lead_signals for company, applies weights,
    decays older signals.

    Returns: momentum_score (0-100)
    """
    pass

async def calculate_revenue_potential(company: Dict[str, Any]) -> float:
    """
    Estimate revenue potential from company attributes.

    Factors:
    - employee_count (larger = bigger deal)
    - oem_count (more = multi-location/complex)
    - multi_location (more states = bigger footprint)

    Returns: revenue_score (0-100)
    """
    pass

async def calculate_prediction_score(company: Dict[str, Any]) -> float:
    """
    Calculate overall prediction score.

    Formula:
    prediction_score =
        (icp_score × 0.35)
      + (revenue_potential × 0.25)
      + (momentum_score × 0.25)
      + (recency_boost × 0.15)

    Returns: prediction_score (0-100)
    """
    pass

async def update_rankings(limit: int = 1000) -> Dict[str, Any]:
    """
    Recalculate and update prediction rankings for all active leads.

    Updates dim_companies:
    - prediction_score
    - prediction_rank
    - prediction_updated_at

    Returns:
        {
            "updated": int,
            "top_10": List[{"company_id": UUID, "company_name": str, "rank": int, "score": float}]
        }
    """
    pass

async def log_signal(
    company_id: UUID,
    signal_type: str,
    signal_value: Dict[str, Any] = None,
    weight: float = 1.0
) -> None:
    """
    Log a momentum signal for a company.

    Called by other agents after significant events.

    Signal types: 'phone_added', 'email_added', 'stage_change',
                  'enrichment', 'bdr_note', 'email_open'
    """
    pass
```

**Verification:**
```bash
cd backend && python -c "from app.services.prediction_market import update_rankings; print('OK')"
```

---

## Task 5: Lead Prediction Agent (LLM)

**File:** `backend/app/services/langgraph/agents/lead_prediction_agent.py`

**What to build:**
- LangGraph agent for "why call now" reasoning
- Uses OpenRouter (Qwen/DeepSeek/Mixtral)
- Only runs for top-N leads (cost control)

**Agent structure:**
```python
from app.services.langgraph.agents.base_agent import BaseAgent

class LeadPredictionAgent(BaseAgent):
    """
    Generates 'why call now' reasoning for top leads.

    Uses OpenRouter for LLM access to various models.
    """

    def __init__(self, model: str = "qwen/qwen-2.5-72b-instruct"):
        super().__init__(
            config=AgentConfig(
                name="lead_prediction",
                provider="openrouter",
                model=model,
                optimize_for="cost",
            )
        )

    async def generate_why_now(self, company: Dict[str, Any]) -> str:
        """
        Generate 1-2 sentence "why call now" reasoning.

        Input: company data with ai_company_story, ai_personal_hooks, recent signals
        Output: "Call because [specific timely reason based on their situation]"
        """
        pass

    async def generate_morning_briefing(self, top_leads: List[Dict]) -> str:
        """
        Generate morning briefing markdown for top leads.

        Returns formatted list with rankings and call reasons.
        """
        pass
```

**Verification:**
```bash
cd backend && python -c "from app.services.langgraph.agents.lead_prediction_agent import LeadPredictionAgent; print('OK')"
```

---

## Task 6: Prediction Celery Tasks

**File:** `backend/app/tasks/prediction_tasks.py`

**What to build:**
- Celery tasks for prediction market operations
- Morning briefing task with Slack integration

**Tasks to implement:**
```python
@celery_app.task(name="run_prediction_market", bind=True)
def run_prediction_market_task(self, limit: int = 1000):
    """
    Scheduled task: Update prediction rankings.

    Called every 5 minutes by Celery Beat.
    Sends Slack alert for significant rank changes.
    """
    pass

@celery_app.task(name="run_morning_briefing", bind=True)
def run_morning_briefing_task(self, top_n: int = 10):
    """
    Scheduled task: Generate morning briefing with LLM.

    Called at 7 AM EST by Celery Beat.
    Sends formatted Slack message with top leads.
    """
    pass

@celery_app.task(name="log_lead_signal")
def log_lead_signal_task(company_id: str, signal_type: str, signal_value: dict = None, weight: float = 1.0):
    """
    Event-driven task: Log a momentum signal.

    Called by other agents after significant events.
    """
    pass
```

**Update:** Add to `celery_app.py` includes:
```python
include=[
    "app.tasks.agent_tasks",
    "app.tasks.batch_tasks",
    "app.tasks.icp_tasks",
    "app.tasks.prediction_tasks",  # ADD THIS
]
```

---

## Task 7: Rankings API Endpoint

**File:** `backend/app/api/v1/endpoints/rankings.py`

**What to build:**
- FastAPI endpoint for live leaderboard
- Returns top-N leads with scores and reasoning

**Endpoint:**
```python
from fastapi import APIRouter, Query
from typing import List

router = APIRouter(prefix="/rankings", tags=["rankings"])

@router.get("/")
async def get_lead_rankings(
    limit: int = Query(default=10, le=100),
    include_why_now: bool = Query(default=True)
) -> List[dict]:
    """
    Get current lead rankings.

    Returns:
        [
            {
                "rank": 1,
                "company_id": "uuid",
                "company_name": "ACME Corp",
                "prediction_score": 87.5,
                "icp_tier": "GOLD",
                "why_now": "Recently added direct phone, high momentum",
                "top_contact": {"name": "John Smith", "title": "Owner", "phone": "+1..."}
            },
            ...
        ]
    """
    pass
```

**Update:** Add router to `main.py`:
```python
from app.api.v1.endpoints import rankings
app.include_router(rankings.router, prefix="/api/v1")
```

---

## Task 8: Celery Beat Configuration

**File:** `backend/app/celery_app.py`

**Add to beat_schedule:**
```python
beat_schedule = {
    # ... existing schedules ...

    # ICP Checker - every 15 minutes
    "icp-checker-every-15-min": {
        "task": "run_icp_checker",
        "schedule": 900.0,
        "args": (100,),
        "options": {"queue": "default"},
    },

    # Prediction Market - every 5 minutes
    "prediction-market-every-5-min": {
        "task": "run_prediction_market",
        "schedule": 300.0,
        "args": (1000,),
        "options": {"queue": "default"},
    },

    # Morning Briefing - 7 AM EST (12:00 UTC)
    "morning-briefing-7am-est": {
        "task": "run_morning_briefing",
        "schedule": crontab(hour=12, minute=0),
        "args": (10,),
        "options": {"queue": "workflows"},
    },
}
```

**Add task routes:**
```python
task_routes = {
    # ... existing routes ...
    "app.tasks.icp_tasks.run_icp_checker_task": {"queue": "default"},
    "app.tasks.icp_tasks.recheck_icp_for_company_task": {"queue": "default"},
    "app.tasks.prediction_tasks.run_prediction_market_task": {"queue": "default"},
    "app.tasks.prediction_tasks.run_morning_briefing_task": {"queue": "workflows"},
    "app.tasks.prediction_tasks.log_lead_signal_task": {"queue": "default"},
}
```

---

## Task 9: Integration Test

**Test script:**
```bash
cd backend && source ../venv/bin/activate

# 1. Test ICP Checker
python -c "
from app.tasks.icp_tasks import run_icp_checker_task
result = run_icp_checker_task.delay(10)
print(f'ICP Checker task: {result.id}')
"

# 2. Test Prediction Market
python -c "
from app.tasks.prediction_tasks import run_prediction_market_task
result = run_prediction_market_task.delay(100)
print(f'Prediction Market task: {result.id}')
"

# 3. Test Rankings API
curl http://localhost:8001/api/v1/rankings?limit=5

# 4. Test Morning Briefing
python -c "
from app.tasks.prediction_tasks import run_morning_briefing_task
result = run_morning_briefing_task.delay(5)
print(f'Morning Briefing task: {result.id}')
"
```

---

## Task 10: Commit and Deploy

```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent

# Verify no OpenAI references
grep -r "OPENAI" --include="*.py" backend/app/ && echo "ERROR: OpenAI found" || echo "OK: No OpenAI"

# Verify no hardcoded keys
grep -r "sk-" --include="*.py" backend/app/ && echo "ERROR: Hardcoded key" || echo "OK: No hardcoded keys"

# Run tests
cd backend && pytest tests/ -v --tb=short

# Commit
git add .
git commit -m "feat: Add ICP Checker Worker + Lead Prediction Market Agent

- ICP Checker: Pure Python service for automatic ICP rescoring
- Lead Prediction Market: Hybrid algo + LLM agent for lead ranking
- New table: fact_lead_signals for momentum tracking
- New columns: prediction_score, prediction_rank, prediction_why_now
- API: GET /api/v1/rankings for live leaderboard
- Celery Beat: 15-min ICP check, 5-min rankings, 7 AM briefing

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>"

git push origin main
```

---

## Files Summary

| Task | File | Type |
|------|------|------|
| 1 | `backend/app/services/icp_scorer.py` | New |
| 2 | `backend/app/tasks/icp_tasks.py` | New |
| 4 | `backend/app/services/prediction_market.py` | New |
| 5 | `backend/app/services/langgraph/agents/lead_prediction_agent.py` | New |
| 6 | `backend/app/tasks/prediction_tasks.py` | New |
| 7 | `backend/app/api/v1/endpoints/rankings.py` | New |
| 8 | `backend/app/celery_app.py` | Modify |
| 8 | `backend/app/main.py` | Modify |

**Total: 6 new files, 2 modifications**
