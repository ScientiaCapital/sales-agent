# Campaign Launch Summary - Dec 29, 2025

## Quick Reference

| Detail | Value |
|--------|-------|
| **Launch Date** | December 29, 2025 @ 9:00 AM ET |
| **Total Contacts** | 1,134 |
| **Workflows** | ICP-Energy-Multitrade (688), Solar-Pivot-2026 (95) |
| **Platform** | Close CRM Sequences |
| **Duration** | 23 days (11 touches) |
| **Owner** | Tim Kipper <tim@coperniq.io> |

## Critical Files

1. **MAIN CHECKLIST**: `/docs/CAMPAIGN_MONITORING_DEC29.md`
   - Daily monitoring tasks
   - Metrics thresholds
   - Escalation procedures
   - Week 1 analysis template

2. **Python Monitoring Script**: `/backend/scripts/campaign_health_check.py`
   - Real-time Close CRM API metrics
   - Color-coded health indicators
   - CSV export capability

3. **SQL Queries**: `/backend/scripts/campaign_monitoring_queries.sql`
   - Supabase monitoring queries
   - Hot lead identification
   - Week 1 summary report

4. **Quick Start Guide**: `/backend/scripts/README_CAMPAIGN_MONITORING.md`
   - Tool usage examples
   - Daily workflow
   - Troubleshooting

## Pre-Launch Checklist (Dec 28)

- [ ] Verify 1,134 contacts enrolled
- [ ] Check scheduled start time (Dec 29 @ 9:00 AM ET)
- [ ] Test email deliverability
- [ ] Verify SPF/DKIM/DMARC passing
- [ ] Check sender reputation
- [ ] Test unsubscribe workflow
- [ ] Confirm backend systems healthy

## Launch Day (Dec 29)

### 9:00 AM - Launch
- [ ] Confirm first batch sent (~100-200 emails)
- [ ] Monitor delivery rate (Target: >95%)
- [ ] Watch bounce rate (Target: <5%)

### 10:00 AM - First Hour Check
- [ ] Review delivery metrics
- [ ] Check spam complaints (Target: <0.1%)
- [ ] Verify unsubscribe link working

### 5:00 PM - End of Day
- [ ] Daily delivery summary
- [ ] Check for early replies
- [ ] Review sequence pauses/stops

## Daily Monitoring (Dec 29 - Jan 4)

### Morning (9:00 AM)
```bash
python campaign_health_check.py --date $(date -v-1d +%Y-%m-%d)
```

### Midday (12:00 PM)
- Check Close CRM → Inbox → Unread replies
- Review hot leads (interested, meeting requests)

### End of Day (5:00 PM)
```bash
python campaign_health_check.py --date $(date +%Y-%m-%d) --export daily_$(date +%Y%m%d).csv
```

## Week 1 Analysis (Jan 5)

```bash
# Export full metrics
python campaign_health_check.py \
  --date-range 2025-12-29 2026-01-05 \
  --export week1_analysis.csv

# Check sequence health
python campaign_health_check.py --sequence-id seq_469XPP98mPXSR2wh5cX9y6
```

### Success Criteria

| Metric | Minimum | Excellent |
|--------|---------|-----------|
| Delivery Rate | >95% | >98% |
| Bounce Rate | <5% | <3% |
| Spam Complaints | <0.1% | 0% |
| Open Rate | >10% | >20% |
| Reply Rate | >1% | >3% |
| Unsubscribe Rate | <2% | <1% |
| Hot Leads | >10 | >30 |

## Escalation Quick Reference

| Condition | Level | Action |
|-----------|-------|--------|
| Delivery Rate <90% | 🔴 RED | PAUSE campaign immediately |
| Bounce Rate >10% | 🔴 RED | PAUSE, clean email list |
| Spam Complaints >0.5% | 🔴 RED | STOP campaign immediately |
| Delivery Rate 90-95% | 🟡 YELLOW | Monitor closely, check bounce reasons |
| Open Rate <10% | 🟡 YELLOW | Review subject lines |
| Reply Rate >5% | 🟢 GREEN | Scale up response team (good news!) |

## Contact Information

- **Campaign Owner**: Tim Kipper
- **Close CRM Account**: tim@coperniq.io
- **Primary Phone**: +1 415-430-9565
- **BCC Email**: coperniq_inc-5rskqabn@leads.close.com

## Workflow IDs

| Workflow | Sequence ID |
|----------|-------------|
| ICP-Energy-Multitrade | `seq_469XPP98mPXSR2wh5cX9y6` |
| Solar-Pivot-2026 | `seq_0FHFD0OQtDAOS8x40MIANW` |

## Key Commands

### Check Health
```bash
cd backend/scripts
python campaign_health_check.py --date 2025-12-29
```

### Export Metrics
```bash
python campaign_health_check.py --date 2025-12-29 --export metrics.csv
```

### Check Sequence
```bash
python campaign_health_check.py --sequence-id seq_469XPP98mPXSR2wh5cX9y6
```

### Hot Leads Query (Supabase)
```sql
SELECT c.name, c.email, co.name as company, a.activity_date
FROM fact_close_activities a
JOIN dim_contacts c ON a.contact_id = c.close_contact_id
JOIN dim_companies co ON c.company_id = co.id
WHERE a.status = 'replied'
  AND a.activity_date::date >= '2025-12-29'
  AND a.metadata->>'intent' = 'interested'
ORDER BY a.activity_date DESC;
```

## Next Steps

1. ✅ **Created**: Campaign monitoring checklist
2. ✅ **Created**: Python health check script
3. ✅ **Created**: SQL monitoring queries
4. ⏳ **Dec 28**: Run pre-launch checklist
5. ⏳ **Dec 29**: Monitor launch day
6. ⏳ **Dec 29-Jan 4**: Daily monitoring
7. ⏳ **Jan 5**: Week 1 analysis

---

**Good luck with the launch! 🚀**
