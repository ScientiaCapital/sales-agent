# Self-Learning ICP System

## Goal
Make the ICP scoring system learn from won/lost deals to continuously improve lead prioritization.

---

## Architecture

### New Table: `fact_deal_outcomes`

```sql
CREATE TABLE fact_deal_outcomes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID NOT NULL REFERENCES dim_companies(company_id),
    close_lead_id VARCHAR(100),
    close_opportunity_id VARCHAR(100),

    -- Outcome
    outcome VARCHAR(20) NOT NULL,  -- 'won', 'lost', 'stalled'
    deal_value DECIMAL(12,2),
    lost_reason VARCHAR(200),

    -- Snapshot of ICP features AT TIME OF OUTCOME
    -- This is critical - we learn from what we knew when we made the prediction
    snapshot_icp_score FLOAT,
    snapshot_icp_tier VARCHAR(20),
    snapshot_prediction_score FLOAT,
    snapshot_prediction_rank INT,

    -- Feature snapshot for ML training
    features_snapshot JSONB,  -- All features at time of deal close
    /*
    {
        "employee_count": 25,
        "state": "TX",
        "oem_count": 4,
        "oem_brands": ["Carrier", "Trane", "Mitsubishi", "Generac"],
        "has_direct_phone": true,
        "has_email": true,
        "atl_count": 2,
        "btl_count": 3,
        "revenue_estimate": 5000000,
        "days_in_pipeline": 45,
        "touchpoints": 8,
        "reply_sentiment": "interested"
    }
    */

    -- Timestamps
    outcome_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_deal_outcomes_outcome ON fact_deal_outcomes(outcome);
CREATE INDEX idx_deal_outcomes_company ON fact_deal_outcomes(company_id);
```

---

### New Table: `dim_icp_weights`

Store dynamic weights that update based on outcomes:

```sql
CREATE TABLE dim_icp_weights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Feature identification
    feature_name VARCHAR(100) NOT NULL UNIQUE,  -- 'direct_phone', 'email', 'state_TX', etc.
    feature_category VARCHAR(50),  -- 'contact', 'company', 'engagement', 'geography'

    -- Weights
    current_weight FLOAT NOT NULL,
    initial_weight FLOAT NOT NULL,  -- Original human-set weight
    confidence FLOAT DEFAULT 0.5,  -- 0-1, increases with more data

    -- Learning stats
    won_count INT DEFAULT 0,
    lost_count INT DEFAULT 0,
    total_count INT DEFAULT 0,
    correlation_with_win FLOAT,  -- -1 to +1

    -- History
    weight_history JSONB,  -- [{date, weight, reason}, ...]
    last_updated TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Constraints
    min_weight FLOAT DEFAULT 0,
    max_weight FLOAT DEFAULT 200,
    is_locked BOOLEAN DEFAULT FALSE  -- Human can lock certain weights
);

-- Insert initial weights
INSERT INTO dim_icp_weights (feature_name, feature_category, current_weight, initial_weight) VALUES
('direct_phone', 'contact', 100, 100),
('email', 'contact', 50, 50),
('state_CA', 'geography', 15, 15),
('state_TX', 'geography', 15, 15),
('state_FL', 'geography', 15, 15),
('oem_carrier', 'company', 5, 5),
('oem_trane', 'company', 5, 5),
('oem_generac', 'company', 5, 5),
('employee_100plus', 'company', 20, 20),
('multi_location', 'company', 15, 15);
```

---

### New Agent: `LearningAgent`

**Purpose**: Analyze won/lost outcomes and adjust ICP weights.

**Schedule**: Daily at 6 AM (before morning briefing)

**Pipeline**:
```
┌─────────────────────────────────────────────────────────────────┐
│                     LEARNING AGENT PIPELINE                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. COLLECT OUTCOMES (last 24h)                                  │
│     ─────────────────────────────                                │
│     Query fact_deal_outcomes WHERE outcome_at > yesterday        │
│                                                                  │
│  2. ANALYZE PATTERNS                                             │
│     ────────────────────                                         │
│     For each feature:                                            │
│       won_with_feature = count(won AND has_feature)              │
│       lost_with_feature = count(lost AND has_feature)            │
│       correlation = (won - lost) / total                         │
│                                                                  │
│  3. UPDATE WEIGHTS (Bayesian approach)                           │
│     ─────────────────────────────────                            │
│     new_weight = (prior_weight * prior_confidence +              │
│                   observed_correlation * observed_count) /       │
│                   (prior_confidence + observed_count)            │
│                                                                  │
│     # Constraints:                                                │
│     - Max adjustment: ±20% per day                               │
│     - Min confidence threshold: 10 outcomes                      │
│     - Respect locked weights                                     │
│                                                                  │
│  4. LOG CHANGES                                                  │
│     ───────────────                                              │
│     Append to weight_history with reasoning                      │
│     Slack notification if major shifts detected                  │
│                                                                  │
│  5. GENERATE INSIGHTS REPORT                                     │
│     ────────────────────────────                                 │
│     "Leads with Generac OEMs are 23% more likely to close"       │
│     "TX leads outperforming CA leads by 15%"                     │
│     "Direct phone importance increased: 100 → 112 pts"           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

### Webhook Integration

Update `close.py` to capture outcomes:

```python
elif event_type == "opportunity.won":
    # Capture feature snapshot for learning
    company = await get_company_by_close_id(lead_id)

    await save_deal_outcome(
        company_id=company['company_id'],
        outcome='won',
        deal_value=data.get('value'),
        features_snapshot={
            'icp_score': company['icp_score'],
            'icp_tier': company['icp_tier'],
            'state': company['state'],
            'oem_brands': company['oem_brands'],
            'has_direct_phone': bool(company.get('direct_phone')),
            'has_email': bool(company.get('email')),
            'employee_count': company.get('employee_count'),
            # ... all relevant features
        }
    )

    # Trigger async learning update
    from app.tasks.learning_tasks import update_learning_from_outcome
    update_learning_from_outcome.delay(company['company_id'], 'won')

elif event_type == "opportunity.lost":
    # Same pattern for losses
    await save_deal_outcome(
        company_id=company['company_id'],
        outcome='lost',
        lost_reason=data.get('note'),
        # ... features snapshot
    )
    update_learning_from_outcome.delay(company['company_id'], 'lost')
```

---

### RankingAgent Integration

Update `ranking_agent.py` to use dynamic weights:

```python
async def get_feature_weight(feature_name: str) -> float:
    """Get current weight from dim_icp_weights, falling back to defaults."""
    supabase = get_supabase_client()

    result = supabase.table('dim_icp_weights').select(
        'current_weight'
    ).eq('feature_name', feature_name).single().execute()

    if result.data:
        return result.data['current_weight']

    # Fallback to hardcoded defaults
    return DEFAULT_WEIGHTS.get(feature_name, 0)

async def calculate_icp_score(company: Dict[str, Any]) -> float:
    """Calculate ICP score using DYNAMIC weights."""
    score = 0.0

    # Direct phone (dynamic weight)
    if company.get('direct_phone'):
        score += await get_feature_weight('direct_phone')

    # Email (dynamic weight)
    if company.get('email'):
        score += await get_feature_weight('email')

    # State (dynamic weight per state)
    state = company.get('state')
    if state:
        score += await get_feature_weight(f'state_{state}')

    # OEM brands (dynamic weight per brand)
    for brand in company.get('oem_brands', []):
        brand_key = brand.lower().replace(' ', '_')
        score += await get_feature_weight(f'oem_{brand_key}')

    return score
```

---

### Dashboard Additions

New endpoint: `/api/dashboard/learning`

```json
{
  "weight_changes_24h": [
    {
      "feature": "state_TX",
      "old_weight": 15.0,
      "new_weight": 17.3,
      "change_pct": 15.3,
      "reason": "TX deals 23% more likely to close (n=14)"
    }
  ],
  "top_predictors": [
    {"feature": "direct_phone", "correlation": 0.72},
    {"feature": "oem_generac", "correlation": 0.65},
    {"feature": "employee_100plus", "correlation": 0.58}
  ],
  "model_confidence": 0.73,  // Increases with more data
  "total_outcomes_tracked": 156,
  "won_count": 89,
  "lost_count": 67
}
```

---

### Learning Safeguards

1. **Minimum Data Threshold**: Don't adjust weights until 10+ outcomes for that feature
2. **Max Daily Adjustment**: ±20% to prevent wild swings
3. **Locked Weights**: Human can lock critical weights (e.g., keep phone at 100)
4. **Audit Trail**: Every change logged with reasoning
5. **Rollback**: One-click revert to initial weights

---

## Implementation Priority

| Priority | Task | Effort |
|----------|------|--------|
| P1 | Create `fact_deal_outcomes` table | 1 hour |
| P1 | Wire up webhook to capture outcomes | 2 hours |
| P2 | Create `dim_icp_weights` table | 1 hour |
| P2 | Update RankingAgent for dynamic weights | 3 hours |
| P3 | Create LearningAgent | 4 hours |
| P3 | Dashboard learning endpoint | 2 hours |

**Total**: ~13 hours of work

---

## When to Start

**Wait until you have 50+ won/lost outcomes** before turning on adaptive weights.

Until then:
1. Capture outcomes via webhooks ✅ (already wired up)
2. Log to `fact_deal_outcomes`
3. Analyze manually
4. Adjust weights manually based on patterns

The self-learning system becomes valuable once you have statistical significance (50-100 outcomes).

---

## Monday Action Items

For the Monday lead processing run:
1. ✅ Use current static weights (they're good starting points)
2. 🔧 Enable outcome capture in webhook handlers
3. 📊 Track which leads become opportunities
4. 📝 Log when opportunities close won/lost
5. ⏳ After 50+ outcomes → enable adaptive learning

---

*Created: Dec 7, 2025*
*Status: DESIGN COMPLETE - Ready for implementation when needed*
