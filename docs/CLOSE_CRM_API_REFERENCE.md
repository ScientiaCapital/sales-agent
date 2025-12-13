# Close CRM API Reference

Complete reference for integrating sales-agent with Close CRM.

**Base URL**: `https://api.close.com/api/v1`
**Authentication**: Basic Auth with API Key (no password)

```python
import base64
auth = base64.b64encode(f"{CLOSE_API_KEY}:".encode()).decode()
headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
```

---

## 1. LEADS (Companies)

### List/Search Leads
```http
GET /lead/
GET /lead/?_skip=0&_limit=100
GET /lead/?query=status:"Hot Lead"
```

**Query Parameters:**
- `_skip` - Pagination offset
- `_limit` - Results per page (max 100)
- `_fields` - Specific fields to return
- `query` - Search query (Close query language)

### Fetch Single Lead
```http
GET /lead/{lead_id}/
```

### Create Lead
```http
POST /lead/
```
```json
{
  "name": "Acme Corp",
  "status_id": "stat_xxx",
  "contacts": [{
    "name": "John Doe",
    "title": "CEO",
    "emails": [{"email": "john@acme.com", "type": "work"}],
    "phones": [{"phone": "+15551234567", "type": "mobile"}]
  }],
  "custom.cf_FIELD_ID": "Custom Value"
}
```

### Update Lead
```http
PUT /lead/{lead_id}/
```
```json
{
  "name": "Updated Company Name",
  "status_id": "stat_new_status",
  "custom.cf_FIELD_ID": "New Value"
}
```

### Delete Lead
```http
DELETE /lead/{lead_id}/
```

---

## 2. CONTACTS

### List Contacts
```http
GET /contact/
GET /contact/?lead_id={lead_id}
```

### Create Contact
```http
POST /contact/
```
```json
{
  "lead_id": "lead_xxx",
  "name": "Jane Smith",
  "title": "VP Sales",
  "emails": [{"email": "jane@company.com", "type": "work"}],
  "phones": [{"phone": "+15559876543", "type": "office"}],
  "urls": [{"url": "https://linkedin.com/in/jane", "type": "linkedin"}]
}
```

### Update Contact
```http
PUT /contact/{contact_id}/
```

### Delete Contact
```http
DELETE /contact/{contact_id}/
```

---

## 3. SEND SMS

### Create SMS Activity (Send Immediately)
```http
POST /activity/sms/
```
```json
{
  "lead_id": "lead_xxx",
  "contact_id": "cont_xxx",
  "local_phone": "+15551234567",
  "remote_phone": "+15559876543",
  "text": "Hi! Following up on our conversation...",
  "status": "outbox",
  "direction": "outbound"
}
```

**Status Options:**
- `inbox` - Log received SMS
- `draft` - Save as draft
- `scheduled` - Schedule for later (requires `date_scheduled`)
- `outbox` - Send immediately
- `sent` - Log already sent SMS

### Schedule SMS
```json
{
  "status": "scheduled",
  "date_scheduled": "2024-01-15T10:00:00Z",
  "text": "Your scheduled message...",
  "local_phone": "+15551234567",
  "remote_phone": "+15559876543"
}
```

### Use SMS Template
```json
{
  "status": "outbox",
  "template_id": "tmpl_xxx",
  "local_phone": "+15551234567",
  "remote_phone": "+15559876543"
}
```

### List SMS Activities
```http
GET /activity/sms/?lead_id={lead_id}
GET /activity/sms/?date_created__gt=2024-01-01
```

### Update SMS (Modify Draft / Send)
```http
PUT /activity/sms/{id}/
```
```json
{
  "status": "outbox",
  "text": "Updated message content"
}
```

---

## 4. SEND EMAILS

### Create Email Activity (Send Immediately)
```http
POST /activity/email/
```
```json
{
  "lead_id": "lead_xxx",
  "contact_id": "cont_xxx",
  "user_id": "user_xxx",
  "status": "outbox",
  "subject": "Following up on our conversation",
  "body_html": "<p>Hi John,</p><p>Just wanted to follow up...</p>",
  "sender": "\"Tim Kipper\" <tim@company.com>",
  "to": ["john@acme.com"],
  "cc": [],
  "bcc": []
}
```

**Status Options:**
- `inbox` - Log received email
- `draft` - Save as draft
- `scheduled` - Schedule for later
- `outbox` - Send immediately
- `sent` - Log already sent email

### Schedule Email
```json
{
  "status": "scheduled",
  "date_scheduled": "2024-01-15T09:00:00Z",
  "subject": "Scheduled follow-up",
  "body_html": "<p>Your message here...</p>"
}
```

### Use Email Template
```json
{
  "status": "outbox",
  "template_id": "tmpl_xxx",
  "lead_id": "lead_xxx"
}
```

### With Attachments
```json
{
  "status": "outbox",
  "subject": "Document attached",
  "body_html": "<p>Please find attached...</p>",
  "attachments": [{
    "url": "https://app.close.com/go/file/file_xxx",
    "filename": "proposal.pdf",
    "content_type": "application/pdf",
    "size": 102400
  }]
}
```

### List Email Activities
```http
GET /activity/email/?lead_id={lead_id}
GET /activity/email/?user_id={user_id}&date_created__gt=2024-01-01
```

---

## 5. MAKE/LOG CALLS

### Log Call Activity (Manual)
```http
POST /activity/call/
```
```json
{
  "lead_id": "lead_xxx",
  "contact_id": "cont_xxx",
  "user_id": "user_xxx",
  "duration": 180,
  "direction": "outbound",
  "disposition": "answered",
  "note_html": "<p>Discussed pricing options...</p>",
  "recording_url": "https://example.com/recordings/call.mp3"
}
```

**Disposition Options:**
- `answered` - Call was answered
- `no-answer` - No answer
- `vm-answer` - Voicemail (machine answered)
- `vm-left` - Left voicemail
- `busy` - Line busy
- `blocked` - Call blocked
- `error` - Call error
- `abandoned` - Call abandoned

**Call Methods:**
- `regular` - Standard call
- `power` - Power dialer
- `predictive` - Predictive dialer

### List Call Activities
```http
GET /activity/call/?lead_id={lead_id}
GET /activity/call/?user_id={user_id}&date_created__gt=2024-01-01
```

### Update Call (Add Notes)
```http
PUT /activity/call/{id}/
```
```json
{
  "note_html": "<p>Updated call notes...</p>",
  "outcome_id": "outcome_xxx"
}
```

---

## 6. SEQUENCES (Automated Workflows)

### List Sequences
```http
GET /sequence/
```

### Create Sequence
```http
POST /sequence/
```
```json
{
  "name": "New Lead Follow-up",
  "steps": [
    {
      "type": "email",
      "delay_minutes": 0,
      "template_id": "tmpl_intro"
    },
    {
      "type": "email",
      "delay_minutes": 2880,
      "template_id": "tmpl_followup1"
    },
    {
      "type": "call",
      "delay_minutes": 5760,
      "content": "Call to follow up"
    },
    {
      "type": "sms",
      "delay_minutes": 7200,
      "template_id": "tmpl_sms_check"
    }
  ]
}
```

### Subscribe Contact to Sequence
```http
POST /sequence_subscription/
```
```json
{
  "sequence_id": "seq_xxx",
  "contact_id": "cont_xxx",
  "lead_id": "lead_xxx"
}
```

### List Sequence Subscriptions
```http
GET /sequence_subscription/?sequence_id={seq_id}
GET /sequence_subscription/?contact_id={contact_id}
GET /sequence_subscription/?lead_id={lead_id}
```

### Pause/Resume Subscription
```http
PUT /sequence_subscription/{id}/
```
```json
{
  "status": "paused"
}
```

### Unsubscribe from Sequence
```http
DELETE /sequence_subscription/{id}/
```

### Execute Specific Step
```http
POST /sequence/{sequence_id}/steps/{step_id}/execute
```
```json
{
  "lead_id": "lead_xxx"
}
```

---

## 7. TASKS & REMINDERS

### Create Task
```http
POST /task/
```
```json
{
  "_type": "lead",
  "lead_id": "lead_xxx",
  "assigned_to": "user_xxx",
  "text": "Follow up on proposal",
  "date": "2024-01-15",
  "is_complete": false
}
```

### List Tasks
```http
GET /task/?lead_id={lead_id}
GET /task/?assigned_to={user_id}&is_complete=false
GET /task/?date__gte=2024-01-01&date__lte=2024-01-31
```

### Update Task
```http
PUT /task/{id}/
```
```json
{
  "is_complete": true,
  "text": "Updated task description"
}
```

### Bulk Update Tasks
```http
PUT /task/?id__in=task_a,task_b,task_c
```
```json
{
  "is_complete": true,
  "assigned_to": "user_new"
}
```

---

## 8. OPPORTUNITIES (Deals)

### Create Opportunity
```http
POST /opportunity/
```
```json
{
  "lead_id": "lead_xxx",
  "status_id": "stat_xxx",
  "value": 50000,
  "value_period": "one_time",
  "confidence": 75,
  "note": "HVAC installation project",
  "date_won": null
}
```

### Update Opportunity
```http
PUT /opportunity/{id}/
```
```json
{
  "status_id": "stat_won",
  "confidence": 100,
  "date_won": "2024-01-15"
}
```

---

## 9. CUSTOM FIELDS

### List Lead Custom Fields
```http
GET /custom_field/lead/
```

### List Contact Custom Fields
```http
GET /custom_field/contact/
```

### Create Custom Field
```http
POST /custom_field/lead/
```
```json
{
  "name": "ICP Score",
  "type": "number",
  "description": "Ideal Customer Profile score 0-100"
}
```

**Field Types:**
- `text` - Single line text
- `textarea` - Multi-line text
- `number` - Numeric value
- `date` - Date value
- `datetime` - Date and time
- `choices` - Dropdown selection
- `user` - Close user reference
- `contact` - Contact reference
- `hidden` - Hidden field

### Update Lead with Custom Fields
```http
PUT /lead/{lead_id}/
```
```json
{
  "custom.cf_ICP_SCORE_ID": 85,
  "custom.cf_INDUSTRY_ID": "HVAC",
  "custom.cf_MULTI_SELECT.add": "New Option",
  "custom.cf_MULTI_SELECT.remove": "Old Option"
}
```

---

## 10. LEAD STATUSES

### List Lead Statuses
```http
GET /status/lead/
```

### Create Lead Status
```http
POST /status/lead/
```
```json
{
  "name": "Hot Lead",
  "is_active": true
}
```

### Update Lead Status
```http
PUT /lead/{lead_id}/
```
```json
{
  "status_id": "stat_hot_lead"
}
```

---

## 11. EXPORTS

### Export Leads (Bulk)
```http
POST /export/lead/
```
```json
{
  "format": "json",
  "type": "leads",
  "include_activities": true,
  "include_smart_fields": true,
  "send_done_email": true
}
```

**Export Types:**
- `leads` - One row per lead (JSON recommended)
- `contacts` - One row per contact
- `lead_opps` - One row per opportunity

---

## 12. USERS

### List Users
```http
GET /user/
```

### Get Current User
```http
GET /me/
```

---

## Agent Integration Examples

### BDR Agent: Stage Lead for Outreach
```python
async def stage_lead_for_outreach(lead_id: str, sequence_id: str, contact_id: str):
    # 1. Update lead status to "Outreach"
    await close_api.put(f"/lead/{lead_id}/", json={
        "status_id": "stat_outreach"
    })

    # 2. Subscribe contact to sequence
    await close_api.post("/sequence_subscription/", json={
        "sequence_id": sequence_id,
        "contact_id": contact_id,
        "lead_id": lead_id
    })

    # 3. Create task for follow-up
    await close_api.post("/task/", json={
        "_type": "lead",
        "lead_id": lead_id,
        "assigned_to": TIM_USER_ID,
        "text": "AI-staged: Follow up after sequence",
        "date": (datetime.now() + timedelta(days=7)).isoformat()
    })
```

### Voice Agent: Log Call with Transcript
```python
async def log_ai_call(lead_id: str, duration: int, transcript: str, disposition: str):
    await close_api.post("/activity/call/", json={
        "lead_id": lead_id,
        "user_id": TIM_USER_ID,
        "duration": duration,
        "direction": "outbound",
        "disposition": disposition,
        "note_html": f"<p><strong>AI Call Transcript:</strong></p><p>{transcript}</p>",
        "call_method": "regular"
    })
```

### Send Personalized SMS
```python
async def send_sms(lead_id: str, contact_phone: str, message: str):
    await close_api.post("/activity/sms/", json={
        "lead_id": lead_id,
        "status": "outbox",
        "direction": "outbound",
        "local_phone": CLOSE_PHONE_NUMBER,
        "remote_phone": contact_phone,
        "text": message
    })
```

---

## Rate Limits

- **Standard**: 100 requests per 10 seconds
- **Bulk Operations**: 1 request per second
- **Exports**: 10 per hour

## Error Codes

| Code | Meaning |
|------|---------|
| 400 | Bad Request - Invalid parameters |
| 401 | Unauthorized - Invalid API key |
| 403 | Forbidden - Insufficient permissions |
| 404 | Not Found - Resource doesn't exist |
| 429 | Too Many Requests - Rate limited |
| 500 | Internal Server Error |

---

*Generated: 2024-12-13 | Source: https://developer.close.com*
