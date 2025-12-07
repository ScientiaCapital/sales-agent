# Close CRM Webhooks v2 - Setup Guide

**Status**: Phase 2 Complete ✅
**Created**: 2025-12-07
**Endpoint**: `/api/v1/webhooks/close/events`

---

## Overview

The Close CRM Webhooks v2 endpoint is the central event hub for all Close CRM automation. It receives real-time webhook events from Close CRM and routes them to appropriate agents for processing.

This replaces polling-based sync with **event-driven architecture** for instant responses to CRM changes.

---

## Supported Events

| Event Type | Trigger | Agent/Action |
|------------|---------|--------------|
| `lead.created` | New lead created in Close | → ScoutAgent enrichment (if status=Raw) |
| `lead.status_changed` | Lead status updated | → RankingAgent re-evaluation (if promoted) |
| `lead.updated` | Lead fields modified | → Check for significant changes |
| `activity.email.received` | Email reply received | → SyncAgent reply classification |
| `activity.call.completed` | Call logged | → Log call outcome |
| `opportunity.status_changed` | Opportunity status updated | → Update pipeline metrics |
| `opportunity.won` | Deal closed (won) | → Celebrate + analytics |
| `opportunity.lost` | Deal closed (lost) | → Route to COLD nurture |

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   EVENT FLOW                            │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Close CRM Event (e.g., lead.created)                   │
│           ↓                                             │
│  POST /api/v1/webhooks/close/events                     │
│           ↓                                             │
│  ┌──────────────────┐                                   │
│  │ Verify Signature │  (HMAC-SHA256)                    │
│  └────────┬─────────┘                                   │
│           ↓                                             │
│  ┌──────────────────┐                                   │
│  │  Parse Payload   │  (Pydantic validation)            │
│  └────────┬─────────┘                                   │
│           ↓                                             │
│  ┌──────────────────┐                                   │
│  │  Return 200 OK   │  (immediately - prevent retries)  │
│  └────────┬─────────┘                                   │
│           ↓                                             │
│  ┌──────────────────┐                                   │
│  │ Background Task  │  (FastAPI BackgroundTasks)        │
│  └────────┬─────────┘                                   │
│           ↓                                             │
│  ┌──────────────────┐                                   │
│  │  Route Event     │                                   │
│  └────────┬─────────┘                                   │
│           │                                             │
│      ┌────┴─────┬────────┬────────────┐                 │
│      │          │        │            │                 │
│   Scout     Ranking   Sync      Outreach               │
│   Agent     Agent     Agent     Agent                   │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

---

## Setup Instructions

### 1. Configure Webhook Secret (Required for Production)

```bash
# Add to .env
CLOSE_WEBHOOK_SECRET=your_webhook_secret_from_close
```

**Security Notes**:
- In **production**: Signature verification is **REQUIRED** (webhooks rejected without valid signature)
- In **development**: Signature verification is optional (logs warning if not configured)

### 2. Register Webhook in Close CRM

1. Log in to Close CRM
2. Go to **Settings** → **Webhooks**
3. Click **Create Webhook Subscription**
4. Configure:

```json
{
  "url": "https://your-api.com/api/v1/webhooks/close/events",
  "events": [
    {
      "object_type": "lead",
      "action": "created"
    },
    {
      "object_type": "lead",
      "action": "status_changed"
    },
    {
      "object_type": "lead",
      "action": "updated"
    },
    {
      "object_type": "activity",
      "action": "created"
    },
    {
      "object_type": "opportunity",
      "action": "status_changed"
    },
    {
      "object_type": "opportunity",
      "action": "won"
    },
    {
      "object_type": "opportunity",
      "action": "lost"
    }
  ]
}
```

5. Copy the **Webhook Secret** and add to `.env` as `CLOSE_WEBHOOK_SECRET`

### 3. Test Webhook

```bash
# Health check
curl https://your-api.com/api/v1/webhooks/close/health

# Response:
{
  "status": "healthy",
  "service": "close_webhooks_v2",
  "environment": "production",
  "configuration": {
    "webhook_secret_configured": true,
    "close_api_configured": true,
    "signature_verification_required": true
  },
  "supported_events": [
    "lead.created",
    "lead.status_changed",
    ...
  ],
  "endpoint": "/api/v1/webhooks/close/events"
}
```

### 4. Send Test Event from Close CRM

In Close CRM webhook settings:
1. Click **Send Test Event**
2. Check logs for: `📨 Close webhook received: event=lead.created`
3. Verify signature validation passed
4. Check routing decision in logs

---

## Event Examples

### Lead Created (Raw Status)

**Webhook Payload**:
```json
{
  "event": "lead.created",
  "data": {
    "id": "lead_abc123",
    "name": "Acme HVAC",
    "status_label": "Raw",
    "status_id": "stat_xyz",
    "created_at": "2025-12-07T10:00:00Z"
  },
  "subscription_id": "whsub_123",
  "webhook_id": "whevt_456",
  "sent_at": "2025-12-07T10:00:01Z"
}
```

**Routing Decision**:
```json
{
  "event_type": "lead.created",
  "action": "enrich",
  "tasks_queued": ["scout_agent_enrichment"],
  "reason": "New Raw lead lead_abc123 needs enrichment"
}
```

**What Happens**:
1. Webhook received and signature verified
2. Returns 200 OK to Close (within 200ms)
3. Background task routes to ScoutAgent
4. ScoutAgent queued via Celery: `run_scout_enrichment.delay(lead_id='lead_abc123')`
5. ScoutAgent scrapes website, extracts contacts
6. RankingAgent calculates ICP score
7. If HOT → OutreachAgent generates drafts

---

### Email Reply Received

**Webhook Payload**:
```json
{
  "event": "activity.email.received",
  "data": {
    "id": "acti_xyz",
    "lead_id": "lead_abc123",
    "contact_id": "cont_def",
    "direction": "incoming",
    "subject": "Re: HVAC service inquiry",
    "body_text": "Yes, I'm interested. Can we schedule a call?",
    "from": [{"email": "john@acmehvac.com", "name": "John Smith"}],
    "date_created": "2025-12-07T14:30:00Z"
  },
  "subscription_id": "whsub_123",
  "webhook_id": "whevt_789",
  "sent_at": "2025-12-07T14:30:01Z"
}
```

**Routing Decision**:
```json
{
  "event_type": "activity.email.received",
  "action": "classify_reply",
  "tasks_queued": ["sync_agent_reply_classification"],
  "reason": "Email reply needs classification and routing"
}
```

**What Happens**:
1. Webhook received and signature verified
2. Returns 200 OK to Close
3. Background task routes to SyncAgent
4. SyncAgent classifies reply: `intent=interested, sentiment=positive`
5. Routes to OutreachAgent for next steps
6. Updates sequence enrollment (pause/advance)
7. Sends Slack notification if requires human review

---

### Opportunity Won

**Webhook Payload**:
```json
{
  "event": "opportunity.won",
  "data": {
    "id": "oppo_123",
    "lead_id": "lead_abc123",
    "value": 15000,
    "value_period": "one_time",
    "status_label": "Won",
    "date_won": "2025-12-07T16:00:00Z"
  },
  "subscription_id": "whsub_123",
  "webhook_id": "whevt_999",
  "sent_at": "2025-12-07T16:00:01Z"
}
```

**Routing Decision**:
```json
{
  "event_type": "opportunity.won",
  "action": "celebrate",
  "tasks_queued": ["send_won_notification", "update_analytics"],
  "reason": "Opportunity won: $15000/one_time"
}
```

**What Happens**:
1. Webhook received
2. Returns 200 OK
3. Sends Slack notification: "🎉 Deal won: $15,000!"
4. Updates analytics dashboard
5. Triggers customer onboarding workflow (future)

---

## Security

### HMAC-SHA256 Signature Verification

Close CRM signs webhook payloads using HMAC-SHA256:

```python
# How Close generates signature
signature = hmac.new(
    webhook_secret.encode('utf-8'),
    request_body,  # Raw bytes
    hashlib.sha256
).hexdigest()

# Sent in header: X-Close-Signature: <signature>
```

**Our verification**:
```python
def verify_close_signature(body: bytes, signature: str) -> bool:
    secret = os.getenv("CLOSE_WEBHOOK_SECRET")
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)  # Constant-time comparison
```

**Why constant-time comparison?**
- Prevents timing attacks
- `hmac.compare_digest()` takes same time regardless of where strings differ

---

## Error Handling

### Always Return 200 OK

**Critical Rule**: ALWAYS return 200 OK to Close CRM, even on errors.

**Why?**
- Close retries failed webhooks exponentially (5min, 15min, 1hr, 4hr, 12hr)
- Returning 500 causes unnecessary retries
- Errors are logged internally for debugging

**Implementation**:
```python
try:
    # Process webhook
    ...
except Exception as e:
    logger.error(f"Error processing webhook: {e}", exc_info=True)

    # STILL return 200 to prevent retries
    return WebhookResponse(
        status="error",
        message=f"Error: {str(e)}",
        processing_queued=False
    )
```

---

## Monitoring

### Health Check

```bash
GET /api/v1/webhooks/close/health
```

Returns:
- Webhook secret configured?
- Close API key configured?
- Supported event types
- Environment (production/development)

### Event Statistics

```bash
GET /api/v1/webhooks/close/events/stats
```

Returns:
- Total events received
- Events by type (lead.created, activity.email.received, etc.)
- Events by routing action (enrich, classify_reply, etc.)
- Last 24 hours count

*Note*: Stats endpoint queries Supabase `audit_events` table (implementation pending).

---

## Logs

All webhook events are logged with structured logging:

```
2025-12-07 10:00:01 INFO  📨 Close webhook received: event=lead.created, webhook_id=whevt_456, subscription=whsub_123
2025-12-07 10:00:01 INFO  Routing webhook event: lead.created
2025-12-07 10:00:01 INFO  New Raw lead created: lead_abc123 - queueing ScoutAgent enrichment
2025-12-07 10:00:01 INFO  Event routed: action=enrich, tasks_queued=['scout_agent_enrichment'], reason=New Raw lead lead_abc123 needs enrichment
2025-12-07 10:00:01 INFO  Webhook event logged: lead.created
2025-12-07 10:00:01 INFO  Webhook event processing complete: lead.created
```

---

## Audit Trail

All webhook events are logged to Supabase `audit_events` table:

```sql
CREATE TABLE audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type TEXT NOT NULL,  -- 'close_webhook'
    event_subtype TEXT,          -- 'lead.created', 'activity.email.received'
    webhook_id TEXT,
    subscription_id TEXT,
    routing_action TEXT,         -- 'enrich', 'classify_reply', 'celebrate'
    tasks_queued TEXT[],
    data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_audit_events_webhook_id ON audit_events(webhook_id);
CREATE INDEX idx_audit_events_created_at ON audit_events(created_at);
CREATE INDEX idx_audit_events_event_subtype ON audit_events(event_subtype);
```

---

## Next Steps (Phase 3+)

### Immediate (Phase 3)
- [ ] Implement Celery task imports in `route_webhook_event()`
- [ ] Create `run_scout_enrichment` task
- [ ] Create `process_email_reply` task in SyncAgent
- [ ] Implement Supabase audit logging in `log_webhook_event()`

### Near-term (Phase 4-5)
- [ ] Implement Slack notifications in `send_webhook_notification()`
- [ ] Add webhook event stats dashboard
- [ ] Implement webhook replay (for failed events)
- [ ] Add webhook event filtering (ignore certain events)

### Future
- [ ] Webhook event deduplication (prevent double-processing)
- [ ] Webhook event ordering guarantees
- [ ] Webhook signature rotation support
- [ ] Custom webhook actions via UI

---

## Troubleshooting

### Signature Verification Failing

**Symptoms**: Webhooks rejected with "Invalid webhook signature"

**Causes**:
1. Wrong `CLOSE_WEBHOOK_SECRET` in `.env`
2. Secret rotated in Close CRM but not updated in app
3. Reverse proxy modifying request body

**Fix**:
```bash
# Check secret matches Close CRM
echo $CLOSE_WEBHOOK_SECRET

# Verify signature manually
curl -X POST https://your-api.com/api/v1/webhooks/close/events \
  -H "Content-Type: application/json" \
  -H "X-Close-Signature: <signature>" \
  -d '{"event": "lead.created", "data": {...}}'
```

### Events Not Being Processed

**Symptoms**: Webhook received, 200 OK returned, but no agent processing

**Causes**:
1. Celery worker not running
2. Tasks not imported/registered
3. Redis not running

**Fix**:
```bash
# Check Celery worker status
celery -A app.celery_app inspect active

# Check Redis
redis-cli ping

# Restart Celery worker
celery -A app.celery_app worker -l info
```

### Close CRM Retrying Webhooks

**Symptoms**: Same webhook received multiple times

**Causes**:
1. Endpoint returning 500 instead of 200
2. Endpoint timeout (>30s)
3. Network issues

**Fix**:
- Ensure ALWAYS return 200 OK (even on errors)
- Reduce processing time (move to background)
- Check webhook logs in Close CRM settings

---

## API Reference

### POST /api/v1/webhooks/close/events

Receive Close CRM webhook events.

**Headers**:
- `Content-Type: application/json`
- `X-Close-Signature: <hmac_sha256_signature>` (optional in dev, required in prod)

**Request Body**:
```json
{
  "event": "lead.created",
  "data": { ... },
  "subscription_id": "whsub_xxx",
  "webhook_id": "whevt_xxx",
  "sent_at": "2025-12-07T10:00:00Z"
}
```

**Response** (200 OK):
```json
{
  "status": "success",
  "message": "Event 'lead.created' queued for processing",
  "webhook_id": "whevt_xxx",
  "event": "lead.created",
  "processing_queued": true
}
```

### GET /api/v1/webhooks/close/health

Health check endpoint.

**Response** (200 OK):
```json
{
  "status": "healthy",
  "service": "close_webhooks_v2",
  "environment": "production",
  "configuration": {
    "webhook_secret_configured": true,
    "close_api_configured": true,
    "signature_verification_required": true
  },
  "supported_events": [...],
  "endpoint": "/api/v1/webhooks/close/events"
}
```

### GET /api/v1/webhooks/close/events/stats

Webhook event statistics.

**Response** (200 OK):
```json
{
  "total_events_received": 1234,
  "events_by_type": {
    "lead.created": 456,
    "activity.email.received": 678,
    "opportunity.won": 12
  },
  "events_by_action": {
    "enrich": 456,
    "classify_reply": 678,
    "celebrate": 12
  },
  "last_24h": 89
}
```

---

## Related Documentation

- [Close CRM Webhooks Documentation](https://developer.close.com/topics/webhooks/)
- [Phase 2 Implementation Plan](/.claude/plans/noble-giggling-dawn.md)
- [Agent Architecture](/../../../CLAUDE.md)
- [Close CRM Client](/app/services/crm/close.py)

---

**Phase 2 Status**: ✅ Complete
**Next Phase**: Phase 3 - Agent Integration (ScoutAgent, SyncAgent, OutreachAgent)
