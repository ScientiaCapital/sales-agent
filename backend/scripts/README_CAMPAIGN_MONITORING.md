# Campaign Monitoring Tools - Quick Start

Tools for monitoring the Dec 29, 2025 Apollo campaign launch.

## Files

| File | Purpose |
|------|---------|
| `campaign_health_check.py` | Python script to query Close CRM API for metrics |
| `campaign_monitoring_queries.sql` | SQL queries for Supabase monitoring |
| `/docs/CAMPAIGN_MONITORING_DEC29.md` | **Main checklist** - Your daily playbook |

---

## Option 1: Python Script (Recommended)

The Python script queries Close CRM API directly and displays health metrics with color-coded indicators.

### Prerequisites

```bash
# Ensure CLOSE_API_KEY is set
export CLOSE_API_KEY="your_close_api_key_here"

# Or add to .env file
echo "CLOSE_API_KEY=your_key_here" >> backend/.env
```

### Basic Usage

```bash
# Check today's metrics
cd backend/scripts
python campaign_health_check.py

# Check specific date
python campaign_health_check.py --date 2025-12-29

# Check date range (Week 1)
python campaign_health_check.py --date-range 2025-12-29 2026-01-05

# Check sequence subscription health
python campaign_health_check.py --sequence-id seq_469XPP98mPXSR2wh5cX9y6

# Export to CSV
python campaign_health_check.py --date 2025-12-29 --export metrics_dec29.csv

# Check without daily breakdown
python campaign_health_check.py --date-range 2025-12-29 2026-01-05 --no-daily
```

### Sample Output

```
Campaign Health Check
Date Range: 2025-12-29 to 2026-01-05

Fetching email activities from Close CRM...
✅ Found 1,134 email activities

================================================================================
Campaign Metrics (2025-12-29 to 2026-01-05)
================================================================================

📧 Delivery Performance
--------------------------------------------------------------------------------
Total Sent:        1,134
Total Delivered:   1,082
Total Bounced:     52
Delivery Rate:     95.4% 🟢 (Target: >95%)
Bounce Rate:       4.6% 🟢 (Target: <5%)
Spam Complaints:   0 (0.00%) 🟢 (Target: <0.1%)

📊 Engagement Performance
--------------------------------------------------------------------------------
Total Opened:      217
Total Replied:     34
Total Unsubscribe: 12
Open Rate:         20.1% 🟢 (Target: 15-25%)
Reply Rate:        3.1% 🟢 (Target: 2-5%)
Unsubscribe Rate:  1.1% 🟢 (Target: <2%)
================================================================================

🏥 Overall Campaign Health
================================================================================
🟢 ALL SYSTEMS GREEN
✅ Campaign performing within targets
================================================================================
```

---

## Option 2: SQL Queries (Supabase)

Use these SQL queries in Supabase SQL Editor for manual checks.

### Quick Queries

```sql
-- Today's email activity
SELECT
    status,
    COUNT(*) as count
FROM fact_close_activities
WHERE activity_date::date = CURRENT_DATE
  AND activity_type = 'email'
GROUP BY status;

-- Hot leads (interested replies)
SELECT
    c.name,
    c.email,
    co.name as company_name,
    a.activity_date
FROM fact_close_activities a
JOIN dim_contacts c ON a.contact_id = c.close_contact_id
JOIN dim_companies co ON c.company_id = co.id
WHERE a.status = 'replied'
  AND a.activity_date::date >= '2025-12-29'
  AND a.metadata->>'intent' = 'interested'
ORDER BY a.activity_date DESC;

-- Week 1 summary
SELECT
    COUNT(*) FILTER (WHERE status IN ('sent', 'delivered', 'bounced')) as sent,
    COUNT(*) FILTER (WHERE status = 'delivered') as delivered,
    COUNT(*) FILTER (WHERE status = 'opened') as opened,
    COUNT(*) FILTER (WHERE status = 'replied') as replied
FROM fact_close_activities
WHERE activity_date::date BETWEEN '2025-12-29' AND '2026-01-05'
  AND activity_type = 'email';
```

**Full Queries**: See `campaign_monitoring_queries.sql` for complete set.

---

## Option 3: Close CRM Dashboard (Manual)

1. Log into Close CRM
2. Navigate to **Reports** → **Email Performance**
3. Filter: Date Range = Last 7 Days
4. Review:
   - Delivery rate
   - Open rate
   - Reply rate
   - Bounce rate

---

## Daily Monitoring Workflow

### Morning (9:00 AM)

```bash
# Check overnight activity
python campaign_health_check.py --date $(date -v-1d +%Y-%m-%d)

# Review hot leads
# Log into Close CRM → Inbox → Filter: Unread
```

### End of Day (5:00 PM)

```bash
# Export today's metrics
python campaign_health_check.py --date $(date +%Y-%m-%d) --export daily_$(date +%Y%m%d).csv

# Add notes to tracking log
```

### Week 1 Analysis (Jan 5)

```bash
# Export full Week 1 metrics
python campaign_health_check.py \
  --date-range 2025-12-29 2026-01-05 \
  --export week1_analysis.csv

# Check both sequence subscriptions
python campaign_health_check.py --sequence-id seq_469XPP98mPXSR2wh5cX9y6  # ICP-Energy
python campaign_health_check.py --sequence-id seq_0FHFD0OQtDAOS8x40MIANW  # Solar-Pivot
```

---

## Troubleshooting

### "CLOSE_API_KEY environment variable not set"

```bash
# Add to .env file
echo "CLOSE_API_KEY=api_xxxxx" >> backend/.env

# Or export temporarily
export CLOSE_API_KEY="api_xxxxx"
```

### "Close API error: 401 Unauthorized"

- Check API key is correct
- Verify API key has read permissions
- Test with: `curl https://api.close.com/api/v1/me/ -u $CLOSE_API_KEY:`

### "No activities found"

- Verify date format is correct (ISO: YYYY-MM-DD)
- Check if emails have been sent yet
- Confirm activities are synced to Supabase

---

## Health Status Legend

| Color | Symbol | Meaning | Action |
|-------|--------|---------|--------|
| 🟢 Green | ✅ | All targets met | Continue monitoring |
| 🟡 Yellow | ⚠️ | Below target, needs attention | Review and improve |
| 🔴 Red | ❌ | Critical issue | Escalate immediately |

---

## Next Steps

1. **Read the main checklist**: `/docs/CAMPAIGN_MONITORING_DEC29.md`
2. **Test the script**: Run `python campaign_health_check.py --help`
3. **Set up daily monitoring**: Add to cron or run manually each day
4. **Review escalation procedures**: Know when to pause/stop campaign

---

## Support

- Main Checklist: `/docs/CAMPAIGN_MONITORING_DEC29.md`
- Close CRM API Docs: `https://developer.close.com`
- SQL Queries: `campaign_monitoring_queries.sql`
