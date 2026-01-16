# Campaign Monitoring Checklist - Dec 29 Launch

**Campaign**: Apollo ICP-Energy Multi-Touch Outreach
**Launch Date**: December 29, 2025 @ 9:00 AM ET
**Platform**: Close CRM Sequences
**Total Enrolled**: 1,134 contacts
**Duration**: 23 days (Day 1-23)
**Owner**: Tim Kipper

---

## Executive Summary

### Campaign Overview

| Metric | Value |
|--------|-------|
| **Total Contacts** | 1,134 |
| **Workflows** | 2 (ICP-Energy-Multitrade: 688, Solar-Pivot-2026: 95) |
| **Launch Time** | Dec 29, 2025 @ 9:00 AM ET |
| **Cadence Pattern** | Email → SMS → Call (23-day cycle) |
| **Touch Points** | 11 touches over 23 days |
| **Platform** | Close CRM Sequences |

### Workflow Distribution

| Workflow Name | Contacts | Sequence ID | Persona |
|--------------|----------|-------------|---------|
| ICP-Energy-Multitrade | 688 | `seq_469XPP98mPXSR2wh5cX9y6` | Multi-trade contractors (default) |
| Solar-Pivot-2026 | 95 | `seq_0FHFD0OQtDAOS8x40MIANW` | Pure solar adding trades |
| **Not Yet Enrolled** | 351 | N/A | TBD workflow assignment |

---

## 1. Pre-Launch Checklist (Dec 28, 2025)

Complete these tasks the day BEFORE launch to ensure smooth deployment.

### Data Verification

- [ ] **Verify 1,134 contacts enrolled in Close CRM**
  - Log into Close CRM
  - Navigate to Sequences → Subscriptions
  - Filter by "Scheduled Start Date = Dec 29, 2025"
  - Confirm total = 1,134 contacts
  - **Red Flag**: If count ≠ 1,134, investigate missing contacts

- [ ] **Check workflow distribution**
  - ICP-Energy-Multitrade: 688 contacts
  - Solar-Pivot-2026: 95 contacts
  - **Red Flag**: If totals don't match, check enrollment logs

- [ ] **Verify scheduled start time**
  - All subscriptions: `start: 2025-12-29T09:00:00-05:00`
  - Time zone: Eastern Time (ET)
  - **Red Flag**: If start times vary, batch may send at wrong time

- [ ] **Review exclusion rules applied**
  - No leads with status = "Customer"
  - No leads with status = "Unqualified"
  - No contacts reached in last 30 days
  - No companies in exclusion list
  - **Red Flag**: If exclusions not applied, risk spam complaints

### Email Deliverability Check

- [ ] **Test email deliverability**
  - Send test email from `tim@coperniq.io` to:
    - Gmail (personal)
    - Outlook (business)
    - Apple Mail
  - Check inbox placement (not spam)
  - Verify unsubscribe link works
  - **Red Flag**: If emails land in spam, PAUSE campaign

- [ ] **Verify SPF/DKIM/DMARC records**
  - Use [MXToolbox](https://mxtoolbox.com/SuperTool.aspx)
  - Check `coperniq.io` domain
  - SPF: PASS
  - DKIM: PASS
  - DMARC: PASS
  - **Red Flag**: If any fail, FIX before launch (high bounce risk)

- [ ] **Check sender reputation baseline**
  - Use [Google Postmaster Tools](https://postmaster.google.com/)
  - Check domain reputation: "High" or "Medium"
  - Spam rate: <0.1%
  - **Red Flag**: If "Low" reputation, delay campaign for warming

### Close CRM Configuration

- [ ] **Verify tim@coperniq.io is connected**
  - Settings → Connected Accounts
  - Email: `Tim Kipper <tim@coperniq.io>`
  - Status: Active
  - BCC: `coperniq_inc-5rskqabn@leads.close.com`
  - **Red Flag**: If not connected, emails won't send

- [ ] **Check phone numbers configured**
  - Primary: +1 415-430-9565
  - Verify all 4 numbers active
  - **Red Flag**: If SMS disabled, SMS touches will fail

- [ ] **Test unsubscribe workflow**
  - Click unsubscribe link in test email
  - Verify lead marked "Do Not Contact"
  - Verify all sequences stopped
  - **Red Flag**: If unsubscribe broken, COMPLIANCE VIOLATION

### System Health Check

- [ ] **Backend API status**
  ```bash
  curl http://localhost:8000/api/v1/health
  # Expected: {"status": "healthy"}
  ```
  - **Red Flag**: If down, reply processing won't work

- [ ] **Celery workers running**
  ```bash
  cd backend && celery -A app.celery_app inspect active
  # Expected: 3 workers (close_sync, poll_replies, advance_sequences)
  ```
  - **Red Flag**: If not running, sequences won't advance

- [ ] **Redis connection**
  ```bash
  redis-cli ping
  # Expected: PONG
  ```
  - **Red Flag**: If down, agent status tracking fails

### Final Checklist

- [ ] All 1,134 contacts enrolled and scheduled
- [ ] Email deliverability verified (inbox placement)
- [ ] SPF/DKIM/DMARC all passing
- [ ] Sender reputation ≥ Medium
- [ ] tim@coperniq.io connected in Close
- [ ] Unsubscribe workflow tested
- [ ] Backend systems healthy
- [ ] **READY TO LAUNCH**: Yes / No

---

## 2. Launch Day Checklist (Dec 29, 2025 @ 9:00 AM ET)

Monitor these metrics in the FIRST HOUR after launch.

### 9:00 AM - Launch Time

- [ ] **Confirm first batch sent**
  - Log into Close CRM @ 9:05 AM
  - Navigate to Activities → Emails
  - Filter: Sent Today
  - **Expected**: ~100-200 emails sent (Close batches sends)
  - **Red Flag**: If 0 emails sent, check sequence status

- [ ] **Monitor delivery rate (first 30 min)**
  - Close CRM → Activities → Email Activity
  - Check "Delivered" status
  - **Target**: >95% delivery rate
  - **Red Flag**: If <90%, check sender reputation

- [ ] **Watch bounce rate**
  - Close CRM → Email Activity → Bounced
  - **Target**: <5% bounce rate
  - **Red Flag**: If >10%, bad email list quality

### 10:00 AM - First Hour Check

- [ ] **Review delivery metrics**
  - Total Sent: _______
  - Total Delivered: _______
  - Delivery Rate: _______% (Target: >95%)
  - Bounced: _______% (Target: <5%)
  - **Action**: If targets missed, investigate and pause if needed

- [ ] **Check spam complaints**
  - Close CRM → Email Activity → Spam Reports
  - **Target**: <0.1% (0 complaints ideal)
  - **Red Flag**: If >0.5%, STOP CAMPAIGN IMMEDIATELY

- [ ] **Verify unsubscribe link working**
  - Check if any unsubscribe clicks received
  - Test unsubscribe link yourself
  - **Red Flag**: If broken link, COMPLIANCE VIOLATION - fix NOW

### End of Day (5:00 PM)

- [ ] **Daily delivery summary**
  - Total Sent: _______
  - Total Delivered: _______
  - Total Bounced: _______
  - Total Spam Complaints: _______
  - Delivery Rate: _______% (Target: >95%)
  - Bounce Rate: _______% (Target: <5%)
  - Spam Rate: _______% (Target: <0.1%)

- [ ] **Check for early replies**
  - Close CRM → Activities → Emails → Replied
  - Count total replies: _______
  - **Expected**: 0-5 replies on Day 1 (open rates build over 24-48 hrs)
  - Flag any "interested" replies for immediate follow-up

- [ ] **Review sequence pauses/stops**
  - Close CRM → Sequences → Subscriptions → Stopped
  - Count stopped: _______
  - **Reasons**: Unsubscribe / OOO / Manual pause
  - **Expected**: <1% stopped on Day 1

---

## 3. Daily Monitoring Tasks (Dec 29-31, Jan 2-4)

Perform these checks DAILY during Week 1.

### Morning Check (9:00 AM)

- [ ] **Check overnight delivery**
  - Yesterday's total sent: _______
  - Yesterday's delivered: _______
  - Yesterday's bounced: _______
  - Delivery rate: _______% (Target: >95%)

- [ ] **Review new replies (HOT LEADS!)**
  - Close CRM → Inbox → Unread
  - Count new replies: _______
  - **Interested replies**: Flag for immediate response
  - **Questions**: Queue for human response
  - **Not interested**: Auto-stop sequence (reply router handles)
  - **OOO**: Auto-pause 7 days (reply router handles)

- [ ] **Check error logs**
  ```bash
  cd backend && tail -n 100 logs/celery.log | grep ERROR
  ```
  - **Expected**: 0 errors
  - **Red Flag**: If errors present, investigate root cause

### Midday Check (12:00 PM)

- [ ] **Monitor open rates**
  - Close CRM → Reports → Email Performance
  - Open rate: _______% (Target: 15-25% for cold emails)
  - **Red Flag**: If <10%, subject lines may need improvement

- [ ] **Track reply rate**
  - Total replies: _______
  - Reply rate: _______% (Target: 2-5%)
  - **Green**: >5% (excellent engagement)
  - **Yellow**: 2-5% (normal)
  - **Red**: <2% (may need message improvement)

- [ ] **Review sequence progress**
  - Active subscriptions: _______
  - Paused subscriptions: _______
  - Stopped subscriptions: _______
  - **Expected**: Most still active, <5% paused/stopped

### End of Day (5:00 PM)

- [ ] **Daily metrics snapshot**
  - Date: _______
  - Total Sent (cumulative): _______
  - Total Delivered: _______
  - Total Opened: _______
  - Total Replied: _______
  - Open Rate: _______% (Target: 15-25%)
  - Reply Rate: _______% (Target: 2-5%)
  - Unsubscribe Count: _______
  - Unsubscribe Rate: _______% (Target: <2%)

- [ ] **Hot leads identified**
  - Interested replies: _______
  - Meeting requests: _______
  - Questions: _______
  - **Action**: Respond within 24 hours

- [ ] **Flag issues for investigation**
  - Delivery problems: Yes / No
  - High bounce rate: Yes / No
  - High spam complaints: Yes / No
  - Low engagement: Yes / No
  - System errors: Yes / No

---

## 4. Week 1 Analysis (Jan 5, 2026)

Complete this analysis at the END of Week 1 (after 7 days).

### Delivery Performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Total Sent | _______ | 1,134 | ✅ / ⚠️ / ❌ |
| Total Delivered | _______ | >1,078 (95%) | ✅ / ⚠️ / ❌ |
| Delivery Rate | _______% | >95% | ✅ / ⚠️ / ❌ |
| Total Bounced | _______ | <57 (5%) | ✅ / ⚠️ / ❌ |
| Bounce Rate | _______% | <5% | ✅ / ⚠️ / ❌ |
| Spam Complaints | _______ | <2 (0.1%) | ✅ / ⚠️ / ❌ |

### Engagement Performance

| Metric | Value | Target | Status |
|--------|-------|--------|--------|
| Total Opened | _______ | 170-269 (15-25%) | ✅ / ⚠️ / ❌ |
| Open Rate | _______% | 15-25% | ✅ / ⚠️ / ❌ |
| Total Replied | _______ | 22-54 (2-5%) | ✅ / ⚠️ / ❌ |
| Reply Rate | _______% | 2-5% | ✅ / ⚠️ / ❌ |
| Unsubscribe Count | _______ | <23 (2%) | ✅ / ⚠️ / ❌ |
| Unsubscribe Rate | _______% | <2% | ✅ / ⚠️ / ❌ |

### Workflow Comparison

| Workflow | Contacts | Open Rate | Reply Rate | Notes |
|----------|----------|-----------|------------|-------|
| ICP-Energy-Multitrade | 688 | _______% | _______% | Multi-trade default |
| Solar-Pivot-2026 | 95 | _______% | _______% | Pure solar |

**Analysis**:
- Which workflow performed better? _______________________________
- Should we adjust targeting? _______________________________
- Any messaging improvements needed? _______________________________

### Reply Breakdown

| Intent | Count | % of Replies | Action Taken |
|--------|-------|--------------|--------------|
| Interested | _______ | _______% | 🔥 HOT - Immediate follow-up |
| Meeting Request | _______ | _______% | 📅 Calendar link sent |
| Question | _______ | _______% | ❓ Human response queued |
| Not Interested | _______ | _______% | Sequence stopped |
| Unsubscribe | _______ | _______% | 🚫 DNC marked |
| Out of Office | _______ | _______% | Paused 7 days |
| Auto-Reply | _______ | _______% | Ignored, continued |
| Unknown | _______ | _______% | Queued for review |

### Hot Leads Identified

**Total Hot Leads**: _______ (Interested + Meeting Requests)

**Follow-Up Status**:
- Responded within 24 hrs: _______ / _______
- Meetings booked: _______
- Opportunities created: _______

**Next Steps**:
- [ ] Respond to all remaining hot leads
- [ ] Schedule follow-up calls
- [ ] Move to sales pipeline

### Campaign Health Assessment

**Overall Grade**: ✅ Green / ⚠️ Yellow / ❌ Red

**Recommendation**:
- [ ] **Continue**: Campaign performing well, maintain course
- [ ] **Adjust**: Make messaging/targeting improvements and continue
- [ ] **Pause**: Delivery/engagement issues, need troubleshooting
- [ ] **Stop**: Compliance issues or poor ROI, cancel campaign

**Specific Actions**:
1. _______________________________________
2. _______________________________________
3. _______________________________________

---

## 5. Escalation Procedures

Use these procedures when metrics fall outside acceptable ranges.

### Escalation Level 1: YELLOW ⚠️ (Monitor Closely)

#### Trigger: Delivery Rate 90-95%
**Actions**:
1. Check bounce reasons in Close CRM
2. Segment bounced emails (hard vs soft bounces)
3. Remove hard bounces from future campaigns
4. Monitor next batch for improvement
5. **Timeline**: Fix within 24 hours

#### Trigger: Bounce Rate 5-10%
**Actions**:
1. Review email list quality
2. Check for typos in email addresses
3. Verify domain MX records valid
4. Consider email verification service
5. **Timeline**: Improve by next send batch

#### Trigger: Open Rate 10-15%
**Actions**:
1. Review subject lines for improvements
2. Check send time optimization
3. Test different subject line variants
4. Verify emails not landing in spam
5. **Timeline**: Test improvements within 48 hours

#### Trigger: Reply Rate 1-2%
**Actions**:
1. Review message content for improvements
2. Check if CTAs are clear
3. Test different messaging variants
4. Verify targeting is correct
5. **Timeline**: Adjust messaging by Day 10

### Escalation Level 2: RED ❌ (Immediate Action Required)

#### Trigger: Delivery Rate <90%
**Actions**:
1. **PAUSE CAMPAIGN IMMEDIATELY**
2. Check sender reputation (Google Postmaster Tools)
3. Verify SPF/DKIM/DMARC records
4. Review recent deliverability changes
5. Contact email infrastructure provider
6. **Timeline**: Fix before resuming (may take 3-7 days)

#### Trigger: Bounce Rate >10%
**Actions**:
1. **PAUSE CAMPAIGN IMMEDIATELY**
2. Segment email list by domain
3. Identify problematic domains
4. Use email verification service (ZeroBounce, NeverBounce)
5. Re-enroll only verified emails
6. **Timeline**: Clean list before resuming (1-2 days)

#### Trigger: Spam Complaints >0.5% (>6 complaints)
**Actions**:
1. **STOP CAMPAIGN IMMEDIATELY** 🚨
2. Investigate spam complaint sources
3. Review email content for spam triggers
4. Verify unsubscribe link is prominent
5. Check list source (was it opt-in?)
6. Consider domain warming period
7. **Timeline**: Do NOT resume until complaints <0.1%
8. **Risk**: Domain reputation damage, blacklisting

#### Trigger: Reply Rate >5%
**Actions** (This is GOOD news!):
1. **Scale up manual response team**
2. Prioritize "interested" replies first
3. Create response templates for common questions
4. Track conversion rate (replies → meetings)
5. Consider adding sales support
6. **Timeline**: Respond within 24 hours

#### Trigger: System Errors
**Actions**:
1. Check backend logs: `tail -f backend/logs/celery.log`
2. Verify database connections (Supabase, PostgreSQL, Redis)
3. Restart Celery workers if needed:
   ```bash
   cd backend
   celery -A app.celery_app control shutdown
   celery -A app.celery_app worker --loglevel=info &
   ```
4. Check Close CRM API status
5. Alert dev team if infrastructure issue
6. **Timeline**: Resolve within 2 hours

---

## 6. Metrics Thresholds Reference

Use this table to quickly assess campaign health.

### Delivery Metrics

| Metric | 🟢 Green | 🟡 Yellow | 🔴 Red | Action |
|--------|---------|----------|--------|--------|
| **Delivery Rate** | >95% | 90-95% | <90% | Red: PAUSE campaign |
| **Bounce Rate** | <5% | 5-10% | >10% | Red: PAUSE, clean list |
| **Spam Complaints** | <0.1% | 0.1-0.5% | >0.5% | Red: STOP immediately |

### Engagement Metrics (B2B Cold Email Benchmarks)

| Metric | 🟢 Green | 🟡 Yellow | 🔴 Red | Action |
|--------|---------|----------|--------|--------|
| **Open Rate** | 15-25% | 10-15% | <10% | Yellow: Test subject lines |
| **Reply Rate** | 2-5% | 1-2% | <1% | Yellow: Improve messaging |
| **Unsubscribe Rate** | <2% | 2-5% | >5% | Yellow: Review targeting |

### Sequence Health

| Metric | 🟢 Green | 🟡 Yellow | 🔴 Red | Action |
|--------|---------|----------|--------|--------|
| **Active Subscriptions** | >90% | 80-90% | <80% | Yellow: Investigate stops |
| **Paused (OOO)** | <5% | 5-10% | >10% | Normal seasonal variation |
| **Stopped (Unsubscribe)** | <5% | 5-10% | >10% | Red: Review message fit |

### Reply Quality

| Reply Type | 🟢 Excellent | 🟡 Normal | 🔴 Poor | Target % |
|------------|-------------|-----------|---------|----------|
| **Interested** | >30% | 10-30% | <10% | 20-40% of replies |
| **Not Interested** | <30% | 30-50% | >50% | 20-30% of replies |
| **Questions** | >20% | 10-20% | <10% | 15-25% of replies |
| **Unsubscribe** | <10% | 10-20% | >20% | <10% of replies |

---

## 7. Close CRM Monitoring Commands

Use these commands and queries for monitoring.

### API Endpoints (if backend running)

```bash
# Get sequence subscription status
curl http://localhost:8000/api/v1/sequences/subscriptions \
  -H "Authorization: Bearer $CLOSE_API_KEY"

# Get email activity for today
curl http://localhost:8000/api/v1/metrics/outreach?date=2025-12-29 \
  -H "Authorization: Bearer $CLOSE_API_KEY"

# Get all active alerts
curl http://localhost:8000/api/v1/alerts \
  -H "Authorization: Bearer $CLOSE_API_KEY"

# Check reply classification
curl http://localhost:8000/api/v1/outreach/replies?status=unread \
  -H "Authorization: Bearer $CLOSE_API_KEY"
```

### Supabase Monitoring Queries

```sql
-- Check total contacts in campaign
SELECT COUNT(*) as total_contacts
FROM dim_contacts
WHERE close_contact_id IS NOT NULL;

-- Check contact distribution by workflow
SELECT
  CASE
    WHEN company_name ILIKE '%solar%' THEN 'Solar-Pivot-2026'
    ELSE 'ICP-Energy-Multitrade'
  END as workflow,
  COUNT(*) as contact_count
FROM dim_contacts
WHERE close_contact_id IS NOT NULL
GROUP BY workflow;

-- Get recent Close CRM activities
SELECT
  activity_type,
  activity_date,
  status,
  COUNT(*) as count
FROM fact_close_activities
WHERE activity_date >= '2025-12-29'
GROUP BY activity_type, activity_date, status
ORDER BY activity_date DESC;

-- Find hot leads (interested replies)
SELECT
  c.name,
  c.email,
  a.activity_type,
  a.activity_date
FROM dim_contacts c
JOIN fact_close_activities a ON c.close_contact_id = a.contact_id
WHERE a.activity_type = 'email'
  AND a.status = 'replied'
  AND a.activity_date >= '2025-12-29'
ORDER BY a.activity_date DESC;
```

### Close CRM Manual Checks

**Daily Dashboard Check**:
1. Log into Close CRM
2. Navigate to **Reports** → **Email Performance**
3. Filter: Date Range = Last 7 Days
4. Export CSV for detailed analysis

**Sequence Status Check**:
1. Navigate to **Sequences** → **Subscriptions**
2. Filter: Sequence = ICP-Energy-Multitrade
3. Check Active / Paused / Stopped counts
4. Repeat for Solar-Pivot-2026

**Reply Review**:
1. Navigate to **Inbox**
2. Filter: Unread
3. Review each reply and categorize:
   - Interested → Tag "HOT LEAD"
   - Not Interested → Stop sequence
   - OOO → Pause 7 days
   - Question → Queue for response

---

## 8. Troubleshooting Guide

### Issue: No emails sent at 9:00 AM

**Possible Causes**:
1. Sequence not activated
2. Start time incorrect (timezone issue)
3. Close CRM connected account disconnected
4. Email service outage

**Debugging Steps**:
```bash
# Check sequence status via API
curl https://api.close.com/api/v1/sequence/seq_469XPP98mPXSR2wh5cX9y6/ \
  -u $CLOSE_API_KEY:

# Check subscription count
curl https://api.close.com/api/v1/sequence_subscription/?sequence_id=seq_469XPP98mPXSR2wh5cX9y6 \
  -u $CLOSE_API_KEY:
```

**Fix**:
- Verify sequence status = "active"
- Check subscription start times
- Reconnect email account if needed

---

### Issue: High bounce rate (>10%)

**Possible Causes**:
1. Bad email list (typos, invalid domains)
2. SPF/DKIM/DMARC not configured
3. Domain reputation low
4. Emails marked as spam

**Debugging Steps**:
1. Check bounce reasons in Close CRM
2. Segment by bounce type:
   - Hard bounce = invalid email (remove permanently)
   - Soft bounce = temporary issue (retry later)
3. Verify email addresses with [ZeroBounce](https://www.zerobounce.net/)
4. Check domain health with [MXToolbox](https://mxtoolbox.com/)

**Fix**:
- Remove hard bounces from list
- Use email verification service
- Fix SPF/DKIM/DMARC records
- Warm up domain if new

---

### Issue: Emails landing in spam

**Possible Causes**:
1. Spam trigger words in subject/body
2. SPF/DKIM/DMARC failing
3. Low sender reputation
4. High spam complaint rate
5. Unsubscribe link missing/broken

**Debugging Steps**:
1. Send test email to [Mail Tester](https://www.mail-tester.com/)
2. Check spam score (target: 8/10+)
3. Review spam triggers flagged
4. Test with [GlockApps](https://glockapps.com/)

**Fix**:
- Remove spam trigger words
- Add authentication records
- Warm up domain (start small, increase gradually)
- Make unsubscribe prominent
- Improve content quality (less salesy)

---

### Issue: Low open rates (<10%)

**Possible Causes**:
1. Weak subject lines
2. Wrong send time
3. Emails in spam/promotions folder
4. Bad sender name/email
5. Audience not interested

**Debugging Steps**:
1. A/B test subject lines
2. Test send times (9-11 AM, 2-4 PM work best)
3. Check inbox placement with seed tests
4. Review sender name (use personal name, not company)

**Fix**:
- Use curiosity-driven subject lines
- Personalize subject with {{first_name}}
- Send during business hours
- Verify inbox placement

---

### Issue: Reply router not classifying correctly

**Possible Causes**:
1. Claude API down
2. Reply classifier service not running
3. Webhook not configured
4. Celery worker not processing

**Debugging Steps**:
```bash
# Check reply router logs
cd backend
tail -f logs/reply_router.log

# Test reply classification manually
curl http://localhost:8000/api/v1/test/classify-reply \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"text": "Yes, I am interested!"}'

# Check Celery worker status
celery -A app.celery_app inspect active
```

**Fix**:
- Restart Celery workers
- Verify Claude API key valid
- Check webhook URL in Close CRM
- Review classification logs for errors

---

## 9. Week 1 Daily Log Template

Use this template to track daily metrics.

### Date: _____________

**Morning Check (9:00 AM)**:
- Overnight emails sent: _______
- Delivered: _______
- Bounced: _______
- Delivery rate: _______% (Target: >95%)
- New replies: _______

**Midday Check (12:00 PM)**:
- Total opened: _______
- Open rate: _______% (Target: 15-25%)
- Total replied: _______
- Reply rate: _______% (Target: 2-5%)

**End of Day (5:00 PM)**:
- Total sent (cumulative): _______
- Total delivered: _______
- Total opened: _______
- Total replied: _______
- Hot leads identified: _______
- Unsubscribes: _______

**Issues Flagged**:
- [ ] None
- [ ] Delivery problems
- [ ] High bounce rate
- [ ] Spam complaints
- [ ] Low engagement
- [ ] System errors

**Notes**:
_____________________________________________________
_____________________________________________________
_____________________________________________________

---

## 10. Success Criteria

### Minimum Acceptable Performance (Week 1)

| Metric | Target |
|--------|--------|
| Delivery Rate | >95% |
| Bounce Rate | <5% |
| Spam Complaints | <0.1% (max 1-2 total) |
| Open Rate | >10% |
| Reply Rate | >1% |
| Unsubscribe Rate | <2% |
| Hot Leads | >10 |

### Excellent Performance (Week 1)

| Metric | Target |
|--------|--------|
| Delivery Rate | >98% |
| Bounce Rate | <3% |
| Spam Complaints | 0 |
| Open Rate | >20% |
| Reply Rate | >3% |
| Unsubscribe Rate | <1% |
| Hot Leads | >30 |

### Campaign Continuation Decision

**Continue Campaign** if:
- All minimum targets met
- No compliance issues
- Positive ROI potential (hot leads identified)
- No deliverability problems

**Pause for Improvements** if:
- Yellow flags on 2+ metrics
- Open/reply rates below target
- Messaging needs adjustment
- Targeting needs refinement

**Stop Campaign** if:
- Red flag on any delivery metric
- Spam complaints >0.5%
- Deliverability issues
- Audience completely unresponsive (<1% reply rate)
- Compliance violations

---

## 11. Quick Reference Commands

### Start Backend (if not running)

```bash
cd /Users/tmkipper/tmp/worktrees/sales-agent/campaign-prep/backend
source venv/bin/activate
python start_server.py
```

### Start Celery Workers

```bash
cd /Users/tmkipper/tmp/worktrees/sales-agent/campaign-prep/backend
celery -A app.celery_app worker --loglevel=info &
celery -A app.celery_app beat --loglevel=info &
```

### Check System Health

```bash
# API health
curl http://localhost:8000/api/v1/health

# Redis
redis-cli ping

# PostgreSQL (Supabase)
psql $DATABASE_URL -c "SELECT 1;"
```

### Export Daily Metrics

```bash
# Export email activity to CSV
curl http://localhost:8000/api/v1/metrics/export/email?date=2025-12-29 \
  -o campaign_metrics_$(date +%Y%m%d).csv
```

---

## Appendix A: Close CRM Sequence IDs

| Workflow | Sequence ID | Description |
|----------|-------------|-------------|
| ICP-Energy-Multitrade | `seq_469XPP98mPXSR2wh5cX9y6` | Multi-trade contractors (default) |
| Solar-Pivot-2026 | `seq_0FHFD0OQtDAOS8x40MIANW` | Pure solar adding trades |

## Appendix B: Cadence Pattern (23 Days)

| Day | Touch Type | Delay | Notes |
|-----|-----------|-------|-------|
| 1 | Email | - | Initial outreach |
| 3 | SMS | 2 days | Follow-up text |
| 5 | Call | 2 days | First call attempt |
| 8 | Email | 3 days | Second email |
| 10 | SMS | 2 days | Second text |
| 12 | Call | 2 days | Second call attempt |
| 15 | Email | 3 days | Third email |
| 17 | SMS | 2 days | Third text |
| 19 | Call | 2 days | Third call attempt |
| 21 | Email | 2 days | Final email |
| 23 | SMS | 2 days | Final text |

**Total**: 11 touches over 23 days

## Appendix C: Industry Benchmarks (B2B Cold Email)

| Metric | Industry Average | Coperniq Target |
|--------|------------------|-----------------|
| Open Rate | 15-25% | 20% |
| Click Rate | 2-3% | N/A (not tracking) |
| Reply Rate | 1-5% | 3% |
| Meeting Conversion | 0.5-2% | 1% (11 meetings) |
| Unsubscribe Rate | 0.5-2% | <2% |
| Spam Complaint Rate | <0.1% | 0% |

**Sources**:
- Mailchimp Email Marketing Benchmarks
- HubSpot Cold Email Statistics 2024
- Close CRM Outreach Best Practices

---

## Document Control

| Field | Value |
|-------|-------|
| **Document Owner** | Tim Kipper |
| **Created** | 2024-12-24 |
| **Last Updated** | 2024-12-24 |
| **Version** | 1.0 |
| **Status** | ACTIVE |
| **Next Review** | 2026-01-05 (Week 1 Analysis) |

---

**END OF CHECKLIST**

Use this checklist as your daily playbook for the Dec 29 campaign launch. Print it out, check boxes, track metrics, and use the escalation procedures when needed. Good luck with the launch!
