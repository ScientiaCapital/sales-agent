# Close CRM Sequence Configuration

**Last Updated**: 2025-12-29
**Status**: LIVE - Apollo Campaign Launched

---

## Active Sequences

### ICP-Energy-Multitrade
- **Sequence ID**: `seq_469XPP98mPXSR2wh5cX9y6`
- **Target Persona**: Multi-trade contractors (HVAC + electrical + plumbing)
- **Enrollments**: 688 total (241 active, 443 errors, 4 reached goal)

**Schedule Configuration:**
```json
{
  "schedule": {
    "ranges": [
      {"weekday": 1, "start": "09:00:00", "end": "18:00:00"},
      {"weekday": 2, "start": "09:00:00", "end": "18:00:00"},
      {"weekday": 3, "start": "09:00:00", "end": "18:00:00"},
      {"weekday": 4, "start": "09:00:00", "end": "18:00:00"},
      {"weekday": 5, "start": "09:00:00", "end": "18:00:00"}
    ]
  },
  "timezone": "America/Mexico_City"
}
```
- **Days**: Monday - Friday (weekday 1-5)
- **Hours**: 9:00 AM - 6:00 PM CST
- **Timezone**: America/Mexico_City (Central Standard Time)

---

### Solar-Pivot-2026
- **Sequence ID**: `seq_0FHFD0OQtDAOS8x40MIANW`
- **Target Persona**: Solar contractors adding trades (diversification play)
- **Enrollments**: 95 total (46 active, 48 errors, 1 reached goal)

**Schedule Configuration:**
```json
{
  "schedule": {
    "ranges": [
      {"weekday": 1, "start": "08:00:00", "end": "18:00:00"},
      {"weekday": 2, "start": "08:00:00", "end": "18:00:00"},
      {"weekday": 3, "start": "08:00:00", "end": "18:00:00"},
      {"weekday": 4, "start": "08:00:00", "end": "18:00:00"},
      {"weekday": 5, "start": "08:00:00", "end": "18:00:00"}
    ]
  },
  "timezone": "America/Boise"
}
```
- **Days**: Monday - Friday (weekday 1-5)
- **Hours**: 8:00 AM - 6:00 PM MST
- **Timezone**: America/Boise (Mountain Standard Time) - **NEEDS UPDATE TO CST**

---

## Schedule Schema Reference

Close CRM uses this schedule format:

```python
{
    "schedule": {
        "ranges": [
            {
                "weekday": int,      # 1=Monday, 2=Tuesday, ..., 7=Sunday
                "start": "HH:MM:SS", # Local time start (24h format)
                "end": "HH:MM:SS"    # Local time end (24h format)
            }
        ]
    },
    "timezone": "IANA_TIMEZONE"      # e.g., "America/Mexico_City", "America/Chicago"
}
```

### Weekday Values
| Value | Day |
|-------|-----|
| 1 | Monday |
| 2 | Tuesday |
| 3 | Wednesday |
| 4 | Thursday |
| 5 | Friday |
| 6 | Saturday |
| 7 | Sunday |

### Recommended Timezones for US Contractors
| Timezone | Region |
|----------|--------|
| America/Mexico_City | Central (CST/CDT) - Texas, Illinois, etc. |
| America/New_York | Eastern (EST/EDT) - Florida, New York, etc. |
| America/Denver | Mountain (MST/MDT) - Colorado, Arizona |
| America/Los_Angeles | Pacific (PST/PDT) - California, Washington |

---

## Daily Send Limits

**CRITICAL**: To limit daily sends to 50 or less, configure **Email Sending Limits** in Close:

1. Go to **Settings** > **Email Sending Limits**
2. Enable sending limits for your organization
3. Set daily limit to **50** (or desired maximum)
4. Set hourly limit to **10** (spreads sends throughout day)

**Note**: Sequence schedule windows (above) control WHEN emails send. Email Sending Limits control HOW MANY send per day across all sequences and bulk emails.

```
Daily Limit: 50 emails/day (rolling 24-hour window)
Hourly Limit: 10 emails/hour (optional pacing)
Minimum Delay: 60 seconds between sends (recommended)
```

---

## API Reference

### Get Sequence Configuration
```python
import httpx
import base64
import os

api_key = os.getenv('CLOSE_API_KEY')
auth_b64 = base64.b64encode(f'{api_key}:'.encode()).decode()
headers = {'Authorization': f'Basic {auth_b64}'}

response = httpx.get(
    'https://api.close.com/api/v1/sequence/seq_xxx/',
    headers=headers
)
sequence = response.json()
print(sequence['schedule'])
print(sequence['timezone'])
```

### Update Sequence Schedule
```python
# Update timezone to CST
response = httpx.put(
    'https://api.close.com/api/v1/sequence/seq_xxx/',
    headers=headers,
    json={
        "timezone": "America/Mexico_City",
        "schedule": {
            "ranges": [
                {"weekday": 1, "start": "08:00:00", "end": "19:00:00"},
                {"weekday": 2, "start": "08:00:00", "end": "19:00:00"},
                {"weekday": 3, "start": "08:00:00", "end": "19:00:00"},
                {"weekday": 4, "start": "08:00:00", "end": "19:00:00"},
                {"weekday": 5, "start": "08:00:00", "end": "19:00:00"}
            ]
        }
    }
)
```

---

## Subscription Status Codes

| Status | Meaning |
|--------|---------|
| `active` | Currently progressing through sequence |
| `paused` | Temporarily halted (OOO, manual pause) |
| `finished` | Completed all steps |
| `goal` | Reached goal (reply received) |
| `error` | Execution error (invalid email, etc.) |
| `stopped` | Manually stopped |

---

## Current Issues (Dec 29, 2025)

### ✅ FIXED (Dec 29, 2025)
1. ~~**Solar-Pivot-2026 Wrong Timezone**~~: Updated to `America/Mexico_City` (CST)
2. ~~**ICP-Energy-Multitrade Schedule**~~: Updated to 8AM-7PM CST

### ⏸️ SEQUENCES PAUSED (Dec 29, 2025)
Both sequences are **PAUSED** until email sending limits are configured by an admin.

**To resume after limits are set:**
```bash
cd backend
source venv/bin/activate
python scripts/resume_sequences.py --dry-run  # Check status
python scripts/resume_sequences.py             # Resume (requires confirmation)
```

### ⚠️ REQUIRES ADMIN ACTION
3. **Email Sending Limits**: **MUST BE SET IN CLOSE UI** (not available via API)
   - Go to: Settings → Email → Email Sending Limits
   - Daily Limit: **50**
   - Hourly Limit: **10**
   - Minimum Delay: **60 seconds**
   - **Contact your Close admin to configure this**

### 🔍 TO INVESTIGATE
4. **371 Error Subscriptions**: No detailed error messages available via API
   - ICP-Energy-Multitrade: 323 errors
   - Solar-Pivot-2026: 48 errors
   - Most show "Unknown" error - may be email validation failures

---

## Related Files

- `backend/app/services/crm/close_sequences.py` - Sequence client implementation
- `backend/app/services/crm/close_email.py` - Email activity fetching
- `backend/app/tasks/close_sync.py` - Celery sync tasks
- `PLANNING.md` - ADR-016: Celery Campaign Automation

---

## Sources

- [Close Workflows Help](https://help.close.com/docs/workflows)
- [Close Email Sending Limits](https://help.close.com/docs/email-sending-limits)
- [Close Sequences API](https://developer.close.com/resources/sequences/)
- [Close Workflow Schedules Changelog](https://www.close.com/changelog/workflow-schedules-pausing)
