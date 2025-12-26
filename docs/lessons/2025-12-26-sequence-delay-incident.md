# Close CRM Sequence Incident - Lessons Learned

**Date**: 2025-12-26
**Severity**: HIGH
**Campaign**: ICP-Energy-Multitrade
**Impact**: 340/500 contacts (68%) hit errors

## What Happened

The Apollo campaign launched on Dec 24 (not Dec 29 as intended) and 340 contacts immediately hit errors because all 11 sequence steps had `delay: 0 days`.

## Root Cause

```
WRONG (what happened):
  Step 0: email (delay: 0 days)
  Step 1: sms (delay: 0 days)    ← Fires immediately after email
  Step 2: call (delay: 0 days)   ← Fires immediately after SMS
  Step 3: email (delay: 0 days)  ← Fires immediately after call
  ... all 11 steps with 0 delay

CORRECT (what should have happened):
  Step 0: email (delay: 0 days)   # Day 1
  Step 1: sms (delay: 2 days)     # Day 3
  Step 2: call (delay: 2 days)    # Day 5
  Step 3: email (delay: 3 days)   # Day 8
  ...
```

## Prevention for Agents

Before enrolling contacts in ANY sequence:

### 1. VERIFY Sequence Delays
```python
seq = requests.get(f'/sequence/{seq_id}', auth=(api_key, '')).json()
for i, step in enumerate(seq['steps']):
    if i > 0 and step.get('delay_days', 0) == 0:
        raise ValueError(f"STOP: Step {i} has 0 delay - will fire immediately!")
```

### 2. Test with 1-2 Contacts First
Never bulk enroll without testing the sequence flow first.

### 3. Use Future Start Dates
```python
subscription = {
    'sequence_id': seq_id,
    'contact_id': contact_id,
    'start': '2025-12-29T09:00:00-05:00'  # Future date, NOT immediate
}
```

### 4. Verify Sender Configuration
- Email account connected
- SMS enabled
- Phone numbers configured

## Recovery Steps

1. Pause sequence immediately
2. Export error contacts
3. Fix sequence delays in Close CRM UI
4. Re-enroll error contacts with proper scheduling
5. Monitor first 24 hours

## Sequence IDs

| Sequence | ID | Status |
|----------|-----|--------|
| ICP-Energy-Multitrade | `seq_469XPP98mPXSR2wh5cX9y6` | 340 errors |
| Solar-Pivot-2026 | `seq_0FHFD0OQtDAOS8x40MIANW` | TBD |

## Current State (Dec 26)

| Metric | Count |
|--------|-------|
| Total Enrolled | 500 |
| Active (Step 0) | 158 |
| Errors | 340 |
| Finished | 0 |
| Goals | 2 |

The 158 "active" contacts are stuck on Step 0 (first email) - they haven't progressed because the delays are broken.
