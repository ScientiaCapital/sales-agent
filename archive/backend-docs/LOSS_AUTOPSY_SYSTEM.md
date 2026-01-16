# Loss Autopsy System

## Goal
Pull all closed-lost and churned opportunities from Close CRM, run full enrichment, analyze patterns from communication history, and identify what went wrong to improve future ICP scoring.

---

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LOSS AUTOPSY PIPELINE                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌───────────────┐                                                           │
│  │  Close CRM    │                                                           │
│  │  Closed-Lost  │                                                           │
│  │  + Churned    │                                                           │
│  └───────┬───────┘                                                           │
│          │                                                                   │
│          ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  STEP 1: EXTRACT FROM CLOSE CRM                                        │  │
│  │  ─────────────────────────────────                                     │  │
│  │  - All opportunities with status = "lost" or "churned"                 │  │
│  │  - Lead data (company, contacts)                                       │  │
│  │  - ALL activities:                                                     │  │
│  │    • Emails (sent + received, full body)                              │  │
│  │    • SMS messages (full body)                                          │  │
│  │    • Call recordings/transcripts/summaries                            │  │
│  │    • Notes (BDR observations)                                          │  │
│  │    • Meetings/tasks                                                    │  │
│  │  - Timeline of touchpoints                                             │  │
│  │  - Lost reason (if captured)                                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│          │                                                                   │
│          ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  STEP 2: SAVE TO SUPABASE (Staging Area)                               │  │
│  │  ────────────────────────────────────────                              │  │
│  │  New tables:                                                           │  │
│  │  - dim_lost_opportunities (core data)                                  │  │
│  │  - fact_lost_activities (all communications)                          │  │
│  │  - fact_lost_analysis (AI insights)                                    │  │
│  │                                                                        │  │
│  │  Status: staged_for_enrichment                                         │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│          │                                                                   │
│          ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  STEP 3: FULL RE-ENRICHMENT                                            │  │
│  │  ──────────────────────────                                            │  │
│  │  ScoutAgent scrapes website fresh:                                     │  │
│  │  - Current ATL/BTL contacts                                            │  │
│  │  - Current OEM brands                                                  │  │
│  │  - Current service areas                                               │  │
│  │  - Company changes since we last looked                                │  │
│  │                                                                        │  │
│  │  RankingAgent rescores:                                                │  │
│  │  - New ICP score                                                       │  │
│  │  - New prediction score                                                │  │
│  │  - Compare to original score                                           │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│          │                                                                   │
│          ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  STEP 4: AUTOPSY ANALYSIS (AI Pattern Detection)                       │  │
│  │  ───────────────────────────────────────────────                       │  │
│  │                                                                        │  │
│  │  AutopsyAgent analyzes each lost deal:                                 │  │
│  │                                                                        │  │
│  │  A. COMMUNICATION ANALYSIS                                             │  │
│  │     - Read all emails (both directions)                                │  │
│  │     - Read all SMS exchanges                                           │  │
│  │     - Read call transcripts/summaries                                  │  │
│  │     - Read BDR notes                                                   │  │
│  │                                                                        │  │
│  │  B. PATTERN DETECTION                                                  │  │
│  │     Questions to answer:                                               │  │
│  │     1. What objections came up? (price, timing, competitor, no need)   │  │
│  │     2. Did we contact the right person? (ATL vs BTL)                   │  │
│  │     3. Was timing wrong? (busy season, just signed contract)           │  │
│  │     4. Did we miss buying signals?                                     │  │
│  │     5. Was follow-up too slow/fast?                                    │  │
│  │     6. Was messaging off? (wrong pain points, wrong tone)              │  │
│  │     7. Was this ever a real opportunity? (bad ICP fit)                 │  │
│  │                                                                        │  │
│  │  C. SCORING RETROACTIVE                                                │  │
│  │     - What ICP score did we give?                                      │  │
│  │     - What should we have given? (knowing outcome)                     │  │
│  │     - What signals did we miss?                                        │  │
│  │     - What signals were misleading?                                    │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│          │                                                                   │
│          ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  STEP 5: AGGREGATE INSIGHTS                                            │  │
│  │  ──────────────────────────                                            │  │
│  │                                                                        │  │
│  │  Pattern Summary:                                                      │  │
│  │  ┌─────────────────────────────────────────────────────────────────┐  │  │
│  │  │ "Analysis of 47 lost opportunities reveals:                     │  │  │
│  │  │                                                                  │  │  │
│  │  │ TOP LOSS REASONS:                                               │  │  │
│  │  │ 1. Timing (34%) - 'Just signed 3-year contract'                 │  │  │
│  │  │ 2. Price (26%) - 'Too expensive compared to...'                 │  │  │
│  │  │ 3. No Decision Maker (19%) - Contacted tech, not owner          │  │  │
│  │  │ 4. Bad Fit (13%) - Residential-only, we're commercial           │  │  │
│  │  │ 5. Ghost (8%) - No response after initial interest              │  │  │
│  │  │                                                                  │  │  │
│  │  │ ICP SCORING ERRORS:                                             │  │  │
│  │  │ - 23 leads scored GOLD that should have been BRONZE             │  │  │
│  │  │ - Common trait: High OEM count but small team (<10 employees)   │  │  │
│  │  │ - Recommendation: Add employee_count > 15 requirement for GOLD  │  │  │
│  │  │                                                                  │  │  │
│  │  │ COMMUNICATION PATTERNS:                                         │  │  │
│  │  │ - Deals that mentioned 'Generac' in email had 40% lower close   │  │  │
│  │  │ - Leads who replied within 1 hour were 3x more likely to close  │  │  │
│  │  │ - 'Price' objection in first call = 12% close rate              │  │  │
│  │  │ - 'When can we start?' in email = 78% close rate                │  │  │
│  │  │                                                                  │  │  │
│  │  │ ACTIONABLE CHANGES:                                             │  │  │
│  │  │ 1. Add 'contract_renewal_timing' to enrichment                  │  │  │
│  │  │ 2. Reduce weight for OEM count alone (+5 → +2)                  │  │  │
│  │  │ 3. Add 'reply_speed' as momentum signal                         │  │  │
│  │  │ 4. Flag leads mentioning competitors in first email             │  │  │
│  │  └─────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│          │                                                                   │
│          ▼                                                                   │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │  STEP 6: WEIGHT ADJUSTMENT RECOMMENDATIONS                             │  │
│  │  ─────────────────────────────────────────                             │  │
│  │                                                                        │  │
│  │  Output: Proposed changes to dim_icp_weights                          │  │
│  │                                                                        │  │
│  │  | Feature           | Current | Proposed | Reason                    │  │
│  │  |-------------------|---------|----------|---------------------------|  │
│  │  | oem_count         | +5/each | +2/each  | Over-indexed on brands    │  │
│  │  | employee_10_20    | +10     | +5       | Too small to buy          │  │
│  │  | employee_50_plus  | +15     | +25      | Strong correlation w/wins │  │
│  │  | reply_within_1h   | (new)   | +20      | 3x close rate             │  │
│  │  | competitor_mention| (new)   | -15      | Price shopper signal      │  │
│  │                                                                        │  │
│  │  Status: STAGED (requires human approval)                              │  │
│  └───────────────────────────────────────────────────────────────────────┘  │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Table: `dim_lost_opportunities`

```sql
CREATE TABLE dim_lost_opportunities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Close CRM IDs
    close_lead_id VARCHAR(100) NOT NULL,
    close_opportunity_id VARCHAR(100),
    close_contact_id VARCHAR(100),

    -- Company info (snapshot at time of loss)
    company_name VARCHAR(255) NOT NULL,
    domain VARCHAR(255),
    phone VARCHAR(50),
    city VARCHAR(100),
    state VARCHAR(10),

    -- Outcome details
    outcome_type VARCHAR(20) NOT NULL,  -- 'lost', 'churned', 'no_decision'
    lost_reason VARCHAR(255),
    lost_reason_category VARCHAR(50),  -- 'timing', 'price', 'competitor', 'no_fit', 'ghost'
    value_estimate DECIMAL(12,2),
    lost_at TIMESTAMP WITH TIME ZONE,

    -- Original scoring (what we thought)
    original_icp_score FLOAT,
    original_icp_tier VARCHAR(20),
    original_prediction_score FLOAT,

    -- Re-enriched scoring (what we know now)
    new_icp_score FLOAT,
    new_icp_tier VARCHAR(20),
    new_prediction_score FLOAT,
    score_delta FLOAT,  -- new - original

    -- Pipeline metrics
    days_in_pipeline INT,
    touchpoint_count INT,
    email_count INT,
    call_count INT,
    sms_count INT,

    -- Autopsy results
    autopsy_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'analyzed', 'reviewed'
    autopsy_summary TEXT,
    autopsy_insights JSONB,
    /*
    {
        "primary_loss_reason": "timing",
        "decision_maker_contacted": false,
        "objections": ["just signed contract", "call back in 2024"],
        "missed_signals": ["mentioned renewal in first email"],
        "scoring_error": "over-scored due to OEM count",
        "recommended_weight_changes": {...}
    }
    */

    -- Timestamps
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    enriched_at TIMESTAMP WITH TIME ZONE,
    analyzed_at TIMESTAMP WITH TIME ZONE,

    UNIQUE(close_lead_id)
);

CREATE INDEX idx_lost_opps_outcome ON dim_lost_opportunities(outcome_type);
CREATE INDEX idx_lost_opps_reason ON dim_lost_opportunities(lost_reason_category);
CREATE INDEX idx_lost_opps_status ON dim_lost_opportunities(autopsy_status);
```

### Table: `fact_lost_activities`

```sql
CREATE TABLE fact_lost_activities (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lost_opportunity_id UUID REFERENCES dim_lost_opportunities(id),

    -- Activity details
    activity_type VARCHAR(20) NOT NULL,  -- 'email_sent', 'email_received', 'call', 'sms', 'note', 'meeting'
    activity_id VARCHAR(100),  -- Close CRM activity ID
    direction VARCHAR(10),  -- 'outbound', 'inbound'

    -- Content (for analysis)
    subject VARCHAR(500),
    body_text TEXT,  -- Full email/SMS body
    body_html TEXT,  -- HTML version if available

    -- Call-specific
    call_duration_seconds INT,
    call_transcript TEXT,
    call_summary TEXT,
    call_recording_url VARCHAR(500),

    -- Metadata
    from_address VARCHAR(255),
    to_address VARCHAR(255),
    contact_name VARCHAR(255),

    -- AI Analysis
    sentiment VARCHAR(20),  -- 'positive', 'negative', 'neutral', 'objection'
    detected_objections JSONB,  -- ["price", "timing"]
    detected_buying_signals JSONB,  -- ["when can we start", "send proposal"]
    key_phrases JSONB,  -- Important phrases extracted

    -- Timestamps
    occurred_at TIMESTAMP WITH TIME ZONE,
    imported_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_lost_activities_opp ON fact_lost_activities(lost_opportunity_id);
CREATE INDEX idx_lost_activities_type ON fact_lost_activities(activity_type);
CREATE INDEX idx_lost_activities_sentiment ON fact_lost_activities(sentiment);
```

### Table: `fact_loss_patterns`

```sql
CREATE TABLE fact_loss_patterns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Pattern identification
    pattern_name VARCHAR(100) NOT NULL,
    pattern_category VARCHAR(50),  -- 'timing', 'messaging', 'icp_fit', 'process'
    pattern_description TEXT,

    -- Statistics
    occurrence_count INT DEFAULT 0,
    percentage_of_losses FLOAT,

    -- Correlation with loss
    correlation_strength FLOAT,  -- 0-1

    -- Examples
    example_opportunity_ids JSONB,  -- UUIDs of opportunities showing this pattern

    -- Recommendations
    recommended_action TEXT,
    recommended_weight_change JSONB,
    /*
    {
        "feature": "oem_count",
        "current_weight": 5,
        "proposed_weight": 2,
        "confidence": 0.78
    }
    */

    -- Status
    status VARCHAR(20) DEFAULT 'detected',  -- 'detected', 'confirmed', 'actioned', 'dismissed'
    actioned_at TIMESTAMP WITH TIME ZONE,

    -- Timestamps
    detected_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
```

---

## New Agent: `AutopsyAgent`

**Purpose**: Analyze lost deals to find patterns and improve ICP scoring.

**Schedule**: On-demand (triggered after loss import)

**Tools**:
- `analyze_email_thread` - Extract sentiment, objections, signals from email chain
- `analyze_call_transcript` - Parse call for objections and intent
- `categorize_loss_reason` - Classify into standard buckets
- `compare_to_wins` - What's different about this vs won deals?
- `recommend_weight_changes` - Suggest ICP weight adjustments

```python
class AutopsyAgentState(TypedDict):
    opportunity_id: str
    activities: List[Dict]  # All emails, calls, SMS, notes

    # Analysis results
    loss_reason_primary: str
    loss_reason_secondary: List[str]
    objections_detected: List[str]
    buying_signals_missed: List[str]

    # Scoring analysis
    original_score: float
    correct_score: float  # What it should have been
    scoring_errors: List[str]

    # Recommendations
    weight_changes: List[Dict]
    process_improvements: List[str]


async def analyze_communications(state: AutopsyAgentState) -> AutopsyAgentState:
    """
    Read all communications and extract patterns.

    Uses Claude to analyze:
    - Email threads (both directions)
    - Call transcripts/summaries
    - SMS exchanges
    - BDR notes

    Extracts:
    - Objections raised
    - Buying signals (if any)
    - Tone/sentiment progression
    - Decision maker identification
    - Timing issues
    """
    prompt = f"""
    Analyze this lost deal's communication history.

    ACTIVITIES:
    {json.dumps(state['activities'], indent=2)}

    Answer these questions:

    1. PRIMARY LOSS REASON: What was the main reason this deal was lost?
       Categories: timing, price, competitor, no_decision_maker, bad_fit, ghost, other

    2. OBJECTIONS: What specific objections were raised?
       - Quote exact phrases when possible
       - Note when in the process they appeared

    3. MISSED SIGNALS: Were there buying signals we missed or ignored?
       - "When can we start?" = ready to buy
       - "Send proposal" = interested
       - "What's the timeline?" = serious

    4. DECISION MAKER: Did we reach the actual decision maker?
       - Was this person ATL (owner, president, VP) or BTL (tech, coordinator)?
       - Did they mention needing to "check with" someone?

    5. TIMING: Were there timing issues?
       - "Just signed a contract"
       - "Budget locked until Q2"
       - "Call back in 6 months"

    6. MESSAGING FIT: Was our pitch aligned with their needs?
       - Did we address their actual pain points?
       - Was our value prop relevant?

    7. PROCESS ISSUES: What could we have done differently?
       - Followed up faster/slower?
       - Different channel?
       - Different contact?

    Return structured analysis.
    """

    response = await llm.invoke(prompt)
    return parse_autopsy_response(response, state)


async def compare_to_wins(state: AutopsyAgentState) -> AutopsyAgentState:
    """
    Compare this lost deal to similar WON deals.

    Find deals with similar:
    - ICP score
    - Company size
    - State
    - OEM profile

    Identify what was different about the wins:
    - Faster follow-up?
    - Different contact level?
    - Different messaging?
    - Different timing?
    """
    # Query similar won deals
    similar_wins = await get_similar_won_deals(
        icp_score_range=(state['original_score'] - 10, state['original_score'] + 10),
        state=state['company_state'],
        limit=5
    )

    if not similar_wins:
        state['comparison_notes'] = "No similar won deals found for comparison"
        return state

    prompt = f"""
    Compare this LOST deal to these similar WON deals.

    LOST DEAL:
    - Company: {state['company_name']}
    - ICP Score: {state['original_score']}
    - Days in pipeline: {state['days_in_pipeline']}
    - Touchpoints: {state['touchpoint_count']}
    - Loss reason: {state['loss_reason_primary']}

    SIMILAR WON DEALS:
    {json.dumps(similar_wins, indent=2)}

    What patterns do you see? What did we do differently in the wins?
    """

    response = await llm.invoke(prompt)
    state['comparison_insights'] = response
    return state


async def recommend_weight_changes(state: AutopsyAgentState) -> AutopsyAgentState:
    """
    Based on autopsy findings, recommend ICP weight changes.

    If this deal was:
    - Over-scored (high ICP but lost quickly) → reduce weight of its features
    - Under-scored but showed interest → increase weight of its features
    """
    if state['original_score'] > 70 and state['days_in_pipeline'] < 14:
        # High score but fast loss = over-indexed on something
        state['weight_changes'].append({
            'observation': 'High ICP score but lost within 2 weeks',
            'likely_cause': 'Over-weighted certain features',
            'recommendation': 'Review which features contributed most to score'
        })

    if 'competitor' in state['loss_reason_primary'].lower():
        state['weight_changes'].append({
            'observation': 'Lost to competitor',
            'likely_cause': 'Price sensitivity not captured in ICP',
            'recommendation': 'Add negative weight for competitor mentions in early comms'
        })

    return state
```

---

## Implementation: Close CRM Data Pull

```python
async def pull_lost_opportunities_from_close(
    days_back: int = 365,
    include_churned: bool = True
) -> List[Dict]:
    """
    Pull all lost/churned opportunities from Close CRM.

    Includes:
    - Lead data
    - Opportunity data
    - ALL activities (emails, calls, SMS, notes)
    """
    close_client = CloseClient(api_key=os.getenv("CLOSE_API_KEY"))

    # Query opportunities with status = lost
    opportunities = await close_client.get_opportunities(
        status__in=['lost', 'churned'] if include_churned else ['lost'],
        date_lost__gte=(datetime.now() - timedelta(days=days_back)).isoformat()
    )

    logger.info(f"Found {len(opportunities)} lost/churned opportunities")

    results = []
    for opp in opportunities:
        lead_id = opp.get('lead_id')

        # Get lead details
        lead = await close_client.get_lead(lead_id)

        # Get ALL activities for this lead
        activities = await close_client.get_activities(
            lead_id=lead_id,
            _type__in=['Email', 'Call', 'SMS', 'Note', 'Meeting']
        )

        # For calls, try to get transcripts
        for activity in activities:
            if activity.get('_type') == 'Call' and activity.get('recording_url'):
                transcript = await get_call_transcript(activity['recording_url'])
                activity['transcript'] = transcript

        results.append({
            'opportunity': opp,
            'lead': lead,
            'activities': activities,
            'lost_reason': opp.get('note') or opp.get('lost_reason'),
            'value': opp.get('value'),
            'date_lost': opp.get('date_lost')
        })

    return results
```

---

## CLI Command

```bash
# Pull and analyze lost opportunities
python -m cli.autopsy --days 365 --analyze

# Just import without analysis
python -m cli.autopsy --days 365 --import-only

# Analyze specific opportunity
python -m cli.autopsy --opportunity-id opp_abc123

# Generate aggregate report
python -m cli.autopsy --report
```

---

## Expected Outputs

### Per-Opportunity Analysis
```json
{
  "opportunity_id": "opp_abc123",
  "company_name": "Acme HVAC",
  "original_icp_score": 72,
  "new_icp_score": 68,

  "autopsy_summary": "Lost due to timing - prospect just signed 3-year contract with competitor. We contacted correct ATL (owner) but messaging focused on wrong pain point (efficiency vs reliability). Reply speed was slow (4 days) which allowed competitor to close first.",

  "loss_reason_primary": "timing",
  "loss_reason_secondary": ["competitor", "slow_follow_up"],

  "objections_detected": [
    "Just signed with ServiceTitan",
    "Happy with current provider",
    "Maybe next year"
  ],

  "missed_signals": [
    "Mentioned 'contract renewal' in first email - should have asked when",
    "Asked about pricing early - was price shopping"
  ],

  "scoring_errors": [
    "OEM count (4) over-weighted - they're small shop (8 employees)",
    "State bonus (TX +15) may be too high for this segment"
  ],

  "recommended_weight_changes": [
    {"feature": "oem_count", "change": -3, "reason": "small shops have many brands"},
    {"feature": "reply_speed_1day", "change": +15, "reason": "fast replies 3x close rate"}
  ]
}
```

### Aggregate Report
```markdown
# Loss Autopsy Report - Last 365 Days

## Overview
- Total lost opportunities: 47
- Total value lost: $892,000
- Average days in pipeline: 34

## Loss Reason Distribution
| Reason | Count | % | Avg Value |
|--------|-------|---|-----------|
| Timing | 16 | 34% | $18,500 |
| Price | 12 | 26% | $22,000 |
| No Decision Maker | 9 | 19% | $15,000 |
| Bad Fit | 6 | 13% | $12,000 |
| Ghost | 4 | 8% | $8,000 |

## ICP Scoring Accuracy
- Correctly scored: 28 (60%)
- Over-scored: 15 (32%) - Avg error: +18 points
- Under-scored: 4 (8%) - Avg error: -12 points

## Top Patterns Detected

### Pattern 1: High OEM + Low Employees = Bad Fit (n=11)
Companies with 4+ OEM brands but <15 employees were 3x more likely to lose.
**Recommendation**: Add employee floor (15+) for GOLD tier

### Pattern 2: Slow Reply = Lost Deal (n=14)
Leads who replied within 1 hour: 78% close rate
Leads who replied after 24 hours: 23% close rate
**Recommendation**: Add reply_speed as momentum signal

### Pattern 3: Competitor Mention in First Email (n=8)
When prospect mentions competitor in first email: 12% close rate
**Recommendation**: Add competitor_mention as negative signal

## Recommended Weight Changes
| Feature | Current | Proposed | Confidence |
|---------|---------|----------|------------|
| employee_15_plus | 0 | +20 | 85% |
| oem_count | +5/each | +2/each | 78% |
| reply_1h | 0 | +25 | 82% |
| competitor_mention | 0 | -20 | 71% |

## Process Improvements
1. Ask about contract renewal timing in discovery call
2. Prioritize fast follow-up (<4 hours) for hot leads
3. Verify decision-maker authority before deep engagement
4. Flag competitor mentions for pricing strategy adjustment
```

---

## Monday Integration

Add to `MONDAY_8AM_LAUNCH.md`:

```markdown
## Phase 0: Loss Autopsy (Optional - Run First)

Before processing new leads, learn from past losses:

\`\`\`bash
# Pull last 365 days of lost opportunities
python -m cli.autopsy --days 365 --analyze

# Review aggregate report
cat data/reports/loss_autopsy_report.md

# Apply recommended weight changes (optional)
python -m cli.autopsy --apply-weights --confirm
\`\`\`

This gives you data-driven weight adjustments BEFORE processing 8,000 leads.
```

---

## Implementation Priority

| Priority | Task | Effort |
|----------|------|--------|
| P1 | Create Supabase tables | 1 hour |
| P1 | Close CRM lost opportunity pull | 3 hours |
| P1 | Activity import (emails, calls, SMS) | 2 hours |
| P2 | AutopsyAgent (communication analysis) | 4 hours |
| P2 | Pattern detection across all losses | 3 hours |
| P3 | Weight recommendation engine | 2 hours |
| P3 | Aggregate report generation | 2 hours |

**Total**: ~17 hours

---

## Quick Start for Monday

Minimal version to get value immediately:

```python
# Step 1: Pull data from Close
opportunities = await pull_lost_opportunities_from_close(days_back=365)

# Step 2: For each, have Claude analyze the communication thread
for opp in opportunities:
    analysis = await analyze_with_claude(
        emails=opp['activities']['emails'],
        calls=opp['activities']['calls'],
        notes=opp['activities']['notes']
    )

    # Save to Supabase
    await save_autopsy_result(opp['lead_id'], analysis)

# Step 3: Aggregate patterns
patterns = await detect_patterns_across_losses()
print(generate_report(patterns))
```

---

*Created: Dec 7, 2025*
*Status: DESIGN COMPLETE - Can implement Monday*
