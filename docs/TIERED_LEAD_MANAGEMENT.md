# Tiered Lead Management: Gold Standard Lists

**Author**: Tim Kipper | GTM Engineering
**Date**: November 26, 2025
**Purpose**: Always work the BEST leads, nurture the REST

---

## The Tier System

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    TIERED LEAD MANAGEMENT PYRAMID                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│                           ┌───────────┐                                 │
│                           │  TOP 100  │  ← GOLD STANDARD               │
│                           │   -200    │  ← Work DAILY                  │
│                           │   🏆🏆🏆   │  ← Score 85+                   │
│                           └─────┬─────┘                                 │
│                                 │                                       │
│                        ┌────────┴────────┐                              │
│                        │    NEXT 500     │  ← SILVER                   │
│                        │   ⭐⭐⭐⭐⭐       │  ← Work WEEKLY              │
│                        │   Score 70-84   │                              │
│                        └────────┬────────┘                              │
│                                 │                                       │
│               ┌─────────────────┴─────────────────┐                     │
│               │         WORKING 1,000             │  ← BRONZE          │
│               │          📋📋📋📋📋📋              │  ← Active Pipeline  │
│               │          Score 50-69              │                     │
│               └─────────────────┬─────────────────┘                     │
│                                 │                                       │
│     ┌───────────────────────────┼───────────────────────────┐          │
│     │                   NURTURE POOLS                        │          │
│     │  ┌─────────────┐                 ┌─────────────┐      │          │
│     │  │ NURTURE HOT │                 │ NURTURE COLD│      │          │
│     │  │  🔥 90 days │                 │  ❄️ 6-12 mo │      │          │
│     │  │ Monthly     │                 │ Quarterly   │      │          │
│     │  │ touch       │                 │ touch       │      │          │
│     │  └─────────────┘                 └─────────────┘      │          │
│     └───────────────────────────────────────────────────────┘          │
│                                                                         │
│     ┌───────────────────────────────────────────────────────┐          │
│     │                    DEAD / REMOVED                      │          │
│     │  ❌ Not Interested  |  ❌ Bad Fit  |  ❌ Out of Business │          │
│     └───────────────────────────────────────────────────────┘          │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Tier Definitions

### 🏆 TIER 1: Gold Standard (Top 100-200)

**WHO**: Absolute best-fit leads with highest conversion potential

**CRITERIA**:
- Qualification score: 85-100
- ATL contact verified (Owner, CEO, VP)
- Mobile or direct phone available
- Website active and professional
- Multi-state license OR OEM certified
- In target geography

**WORK CADENCE**:
- Touch DAILY
- Full multi-channel sequence
- Personalized outreach only
- CEO/Founder personal attention

**CAPACITY**: 100-200 leads max (quality over quantity)

---

### ⭐ TIER 2: Silver (Next 500)

**WHO**: Strong leads that need more work or timing

**CRITERIA**:
- Qualification score: 70-84
- ATL contact identified (may need direct number)
- Company website exists
- Single state license OK
- Meets basic ICP

**WORK CADENCE**:
- Touch WEEKLY
- Semi-personalized templates
- Focus on getting mobile/direct number
- Promote to Gold when qualified

**CAPACITY**: 300-500 leads

---

### 📋 TIER 3: Bronze (Working 1,000)

**WHO**: Active pipeline, being worked

**CRITERIA**:
- Qualification score: 50-69
- Company exists and is real
- Some contact info available
- May need enrichment

**WORK CADENCE**:
- Touch BI-WEEKLY
- Template outreach with light personalization
- Focus on qualification and enrichment
- Promote or demote based on engagement

**CAPACITY**: 500-1,000 leads

---

### 🔥 NURTURE HOT: Opportunity in 90 Days

**WHO**: Good fit but timing not right NOW

**SIGNALS**:
- Said "call me in Q1" or "after the busy season"
- Budget approved but project delayed
- Decision maker change coming
- Currently in contract with competitor

**WORK CADENCE**:
- Monthly value touch
- Watch for timing signals
- Re-engage when signal detected
- Move to Working when ready

**EXAMPLES**:
- "We're interested but finishing a project first" → Hot 60 days
- "Budget opens in January" → Hot until Jan 15
- "Talk after the holidays" → Hot 30 days

---

### ❄️ NURTURE COLD: Opportunity in 6-12 Months

**WHO**: Long-term potential, not ready now

**SIGNALS**:
- "Maybe next year"
- Small company that will grow
- New business, not stable yet
- Competitor contract with 6+ months remaining

**WORK CADENCE**:
- Quarterly value touch
- Newsletter/content only
- Annual check-in call
- Watch for growth signals

**EXAMPLES**:
- "We just signed a 2-year deal with X" → Cold 18 months
- "Company is too small right now" → Cold, watch for growth
- "Not a priority this year" → Cold 12 months

---

### ❌ DEAD / REMOVED

**WHO**: Never contact again

**REASONS**:
- Explicitly said "Do not contact"
- Company out of business
- Wrong industry/bad fit
- Duplicate (merged elsewhere)
- Spam/fake company

**IMPORTANT**: Keep in database for dedup, mark as `status=dead`

---

## Lead Lifecycle Flow

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         LEAD LIFECYCLE                                  │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  NEW LEAD ENTERS                                                        │
│       │                                                                 │
│       ▼                                                                 │
│  ┌─────────────┐                                                        │
│  │ QUALIFICATION│                                                       │
│  │   Score 0-100│                                                       │
│  └──────┬──────┘                                                        │
│         │                                                               │
│    ┌────┼────┬────────────┐                                            │
│    │    │    │            │                                            │
│    ▼    ▼    ▼            ▼                                            │
│  85+  70-84  50-69      <50                                            │
│   │    │      │          │                                             │
│   ▼    ▼      ▼          ▼                                             │
│ GOLD SILVER BRONZE    REJECT                                           │
│                          │                                              │
│                          ▼                                              │
│                    rejected_leads.csv                                   │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════   │
│                                                                         │
│  DURING OUTREACH                                                        │
│       │                                                                 │
│  ┌────┴────────────────────────────────────────┐                       │
│  │                                              │                       │
│  ▼                  ▼                    ▼      │                       │
│ ENGAGED         NOT NOW            NOT INTERESTED                      │
│  │                │                      │                              │
│  ▼                ▼                      ▼                              │
│ Stay in      ┌────┴────┐           Move to DEAD                        │
│ Tier or      │         │                                               │
│ Promote      ▼         ▼                                               │
│          NURTURE    NURTURE                                            │
│           HOT       COLD                                               │
│          (90d)     (6-12mo)                                            │
│                                                                         │
│  ═══════════════════════════════════════════════════════════════════   │
│                                                                         │
│  PROMOTION TRIGGERS                                                     │
│  ───────────────────                                                    │
│  Bronze → Silver:  Score improves 70+ OR strong engagement             │
│  Silver → Gold:    Score 85+ AND mobile/direct obtained                │
│  Nurture → Working: Signal detected OR time elapsed                    │
│                                                                         │
│  DEMOTION TRIGGERS                                                      │
│  ───────────────────                                                    │
│  Gold → Silver:    No response after full sequence                     │
│  Silver → Bronze:  No engagement in 30 days                            │
│  Bronze → Nurture: "Not now" response                                  │
│  Any → Dead:       "Not interested" or bad fit confirmed               │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### Lead Status Field

```sql
ALTER TABLE leads ADD COLUMN tier VARCHAR(20) DEFAULT 'bronze';
ALTER TABLE leads ADD COLUMN status VARCHAR(20) DEFAULT 'new';
ALTER TABLE leads ADD COLUMN nurture_until DATE;
ALTER TABLE leads ADD COLUMN last_touch_date DATE;
ALTER TABLE leads ADD COLUMN touch_count INTEGER DEFAULT 0;
ALTER TABLE leads ADD COLUMN next_action VARCHAR(100);
ALTER TABLE leads ADD COLUMN next_action_date DATE;

-- Tier values: 'gold', 'silver', 'bronze', 'nurture_hot', 'nurture_cold', 'dead'
-- Status values: 'new', 'working', 'engaged', 'meeting_set', 'opportunity', 'won', 'lost', 'nurture', 'dead'
```

### CSV Export Columns

```csv
company_name,contact_name,contact_email,contact_phone,phone_type,
qualification_score,tier,status,
nurture_until,nurture_reason,
last_touch_date,touch_count,next_action,next_action_date,
city,state,industry,source
```

---

## Tier CSV Files

### File Structure

```
backend/data/tiered_lists/
├── gold_standard_top_200.csv       # 🏆 Best leads, work daily
├── silver_next_500.csv             # ⭐ Good leads, work weekly
├── bronze_working_1000.csv         # 📋 Active pipeline
├── nurture_hot_90_days.csv         # 🔥 Coming soon
├── nurture_cold_6_12_months.csv    # ❄️ Long term
├── dead_do_not_contact.csv         # ❌ Never contact
└── rejected_low_score.csv          # 🗑️ Failed qualification
```

### Gold Standard CSV Example

```csv
company_name,contact_name,contact_email,contact_phone,phone_type,qualification_score,tier,status,last_touch,next_action
"Brower Mechanical","John Brower","john@browermechanical.com","555-123-4567","mobile",92,"gold","working","2025-11-25","Call - follow up on proposal"
"ABC HVAC Services","Jane Smith","jsmith@abchvac.com","555-987-6543","direct",88,"gold","engaged","2025-11-24","Email case study"
```

---

## Adding New Leads

### From dealer-scraper

```bash
# 1. Export new batch from dealer-scraper
cd /Users/tmkipper/Desktop/tk_projects/dealer-scraper-mvp
python export_master_list.py --since "2025-11-25" --output csv

# 2. Import to sales-agent (auto-qualifies and tiers)
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/backend
python import_and_tier.py ../dealer-scraper-mvp/output/master/new_leads.csv

# 3. New leads distributed to tiers based on score
# 85+ → gold_standard_top_200.csv (if under 200)
# 70-84 → silver_next_500.csv
# 50-69 → bronze_working_1000.csv
# <50 → rejected_low_score.csv
```

### From Other Sources

```python
# Add single lead
from app.services.lead_manager import LeadManager

manager = LeadManager()

# Qualify and auto-tier
result = await manager.add_lead({
    "company_name": "New HVAC Co",
    "phone": "555-111-2222",
    "state": "CA"
})

print(f"Added to tier: {result.tier}")  # gold/silver/bronze/rejected
```

---

## Removing Bad Leads

### Mark as Dead (Keep for Dedup)

```python
# Mark single lead as dead
await manager.mark_dead(
    lead_id=123,
    reason="not_interested",  # or "out_of_business", "bad_fit", "duplicate"
    notes="Said never contact again on 11/26 call"
)

# Bulk mark as dead
dead_ids = [123, 456, 789]
await manager.bulk_mark_dead(dead_ids, reason="not_interested")
```

### Remove from Active Lists

```python
# Move to dead list (for dedup) but remove from working lists
await manager.remove_from_active(lead_id=123)

# This:
# 1. Sets tier='dead', status='dead'
# 2. Removes from gold/silver/bronze CSVs
# 3. Adds to dead_do_not_contact.csv
# 4. KEEPS in database for dedup matching
```

---

## Moving to Nurture

### Nurture Hot (90 Days)

```python
# After call: "Not now, but interested for Q1"
await manager.move_to_nurture(
    lead_id=123,
    nurture_type="hot",  # 90 days
    reason="Q1 budget",
    reactivate_date="2025-02-01",
    notes="Said to call back after January planning"
)

# Auto-creates task for reactivation date
```

### Nurture Cold (6-12 Months)

```python
# After call: "Maybe next year"
await manager.move_to_nurture(
    lead_id=123,
    nurture_type="cold",  # 6-12 months
    reason="Not priority this year",
    reactivate_date="2026-01-15",
    notes="Small company, check back next year"
)
```

---

## Daily Workflow

### Morning Routine (30 min)

```
1. CHECK REACTIVATIONS
   - Who is coming out of nurture today?
   - Move back to working tier

2. REVIEW GOLD LIST (Top 200)
   - Who needs follow-up today?
   - Check for new signals

3. PLAN THE DAY
   - 10 Gold touches (calls/emails)
   - 20 Silver touches
   - New lead qualification
```

### Weekly Review (1 hour)

```
1. TIER REVIEW
   - Any Bronze ready to promote to Silver?
   - Any Silver ready to promote to Gold?
   - Any dead weight to demote?

2. NURTURE CHECK
   - Any hot nurtures showing signals?
   - Any cold nurtures ready for quarterly touch?

3. LIST HEALTH
   - Gold list: Is it full (200)?
   - Total working: Under 1000?
   - Dead list growing? (good sign of qualification)
```

---

## Automation Triggers

### Auto-Promote

```python
# Bronze → Silver: Score improves to 70+
if lead.score >= 70 and lead.tier == 'bronze':
    await manager.promote(lead, to_tier='silver')

# Silver → Gold: Score 85+ AND has mobile
if lead.score >= 85 and lead.phone_type == 'mobile' and lead.tier == 'silver':
    await manager.promote(lead, to_tier='gold')
```

### Auto-Demote

```python
# Gold → Silver: No response after 10 touches
if lead.touch_count >= 10 and lead.status == 'working' and lead.tier == 'gold':
    await manager.demote(lead, to_tier='silver')

# Any → Nurture Cold: Said "not now"
if response_type == 'not_now':
    await manager.move_to_nurture(lead, nurture_type='cold')
```

### Signal-Based Reactivation

```python
# Check daily for signals
for lead in nurture_leads:
    signals = await social_intel.check_signals(lead)

    if signals.high_intent:
        # 3+ email opens, LinkedIn view, etc.
        await manager.reactivate(lead, to_tier='gold', reason=signals.reason)
        await notify_sales_rep(lead, "🔥 HIGH INTENT - Call now!")
```

---

## Metrics to Track

### Tier Health

| Metric | Target | Formula |
|--------|--------|---------|
| Gold List Fill Rate | 90%+ | Gold leads / 200 |
| Gold Conversion Rate | 15%+ | Gold wins / Gold total |
| Promotion Rate | 5%/week | Promotions / Total |
| Demotion Rate | <10%/week | Demotions / Total |
| Nurture Reactivation | 20%+ | Reactivated / Nurture total |

### List Quality

| Metric | Target | Formula |
|--------|--------|---------|
| Mobile Coverage (Gold) | 50%+ | Mobile phones / Gold |
| ATL Coverage | 80%+ | ATL contacts / Total |
| Avg Score (Gold) | 88+ | Sum scores / Gold count |
| Stale Leads | <10% | No touch 30d / Total |

---

## Quick Reference

### Status Codes

| Code | Meaning | Tier Location |
|------|---------|---------------|
| `new` | Just added | Based on score |
| `working` | Active outreach | Gold/Silver/Bronze |
| `engaged` | Responded positively | Stay or promote |
| `meeting_set` | Meeting scheduled | Gold |
| `opportunity` | Deal in pipeline | Gold |
| `won` | Closed-won | Archive |
| `lost` | Closed-lost | Archive |
| `nurture_hot` | 90-day timing | Nurture Hot |
| `nurture_cold` | 6-12 month timing | Nurture Cold |
| `dead` | Do not contact | Dead list |

### Tier Limits

| Tier | Capacity | Work Cadence |
|------|----------|--------------|
| Gold | 100-200 | Daily |
| Silver | 300-500 | Weekly |
| Bronze | 500-1000 | Bi-weekly |
| Nurture Hot | Unlimited | Monthly |
| Nurture Cold | Unlimited | Quarterly |
| Dead | Unlimited | Never |

---

**"Work the best, nurture the rest, remove the dead weight"**

*Last Updated: November 26, 2025*
