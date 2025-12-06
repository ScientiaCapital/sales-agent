# Close CRM Reply Webhook Setup Guide

## Overview

The reply webhook endpoint processes incoming email replies from Close CRM and automatically classifies and routes them based on intent.

## Endpoint Details

**URL**: `POST /api/v1/webhooks/close/email-reply`

**Supported Events**:
- `email.received` - Incoming email reply (processed)
- Other events ignored (email.sent, email.opened, email.clicked)

## Close CRM Configuration

### Step 1: Create Webhook in Close CRM

1. Log into Close CRM
2. Go to Settings → API & Integrations → Webhooks
3. Click "Add Webhook"
4. Configure:
   - **URL**: `https://your-domain.com/api/v1/webhooks/close/email-reply`
   - **Events**: Select `email.received`
   - **Status**: Active

### Step 2: Configure Webhook Secret (Optional but Recommended)

Close CRM provides a webhook secret for signature verification.

1. Copy the webhook secret from Close CRM
2. Add to `.env`:
   ```bash
   CLOSE_WEBHOOK_SECRET=your_secret_here
   ```

**Security Notes**:
- Signature verification is **required** in production
- In development, it's optional (warning logged)
- Uses HMAC-SHA256 for verification

### Step 3: Test the Webhook

Send a test email reply to one of your outbound emails and check:

1. **Close CRM Webhook Logs** - Should show 200 OK response
2. **Application Logs** - Should show:
   ```
   INFO - Received Close webhook: event=email.received, lead_id=lead_xxx
   INFO - Reply classified: intent=interested, sentiment=positive
   INFO - Reply routed: action=interested, priority=high
   ```

## Webhook Payload Format

Close CRM sends webhooks in this format:

```json
{
  "event": "email.received",
  "data": {
    "id": "acti_xxx",
    "lead_id": "lead_xxx",
    "contact_id": "cont_xxx",
    "subject": "Re: Quick question about solar",
    "body_text": "Hi Tim, I'd love to learn more...",
    "body_html": "<p>Hi Tim...</p>",
    "from": [{"email": "prospect@company.com", "name": "John Doe"}],
    "to": [{"email": "tim@coperniq.io", "name": "Tim Kipper"}],
    "date_created": "2025-12-06T15:30:00Z",
    "direction": "incoming"
  },
  "subscription_id": "sub_xxx",
  "webhook_id": "wh_xxx"
}
```

## Reply Classification

The webhook automatically classifies replies into these categories:

| Intent | Sentiment | Next Action |
|--------|-----------|-------------|
| `interested` | positive | Create BDR task, notify Slack, stop sequence |
| `meeting_request` | positive | Send calendar link, create opportunity |
| `question` | neutral | Queue for human response, pause sequence |
| `not_interested` | negative | Stop sequence, mark unqualified |
| `unsubscribe` | negative | Remove from all sequences, suppress |
| `out_of_office` | neutral | Pause sequence for 7 days |
| `auto_reply` | neutral | Continue sequence (ignore) |
| `unknown` | neutral | Pause sequence, queue for review |

## Environment Variables

Required variables in `.env`:

```bash
# Close CRM API
CLOSE_API_KEY=api_xxx

# Close CRM Webhook (optional but recommended)
CLOSE_WEBHOOK_SECRET=your_webhook_secret

# Environment (affects signature verification)
ENVIRONMENT=production  # or development
```

## Response Format

The webhook returns 200 OK immediately (to prevent Close retries):

```json
{
  "status": "success",
  "message": "Email reply queued for processing",
  "webhook_id": "wh_xxx",
  "processing_queued": true
}
```

Processing happens asynchronously in the background.

## Health Check

Check webhook configuration status:

```bash
GET /api/v1/webhooks/close/health
```

Response:
```json
{
  "status": "healthy",
  "close_webhooks": {
    "webhook_secret_configured": true,
    "close_api_configured": true,
    "supported_events": ["email.received"]
  }
}
```

## Architecture

### Components

1. **`app/api/webhooks/close_reply.py`** - Webhook endpoint
   - Receives Close CRM webhooks
   - Validates signatures
   - Queues background processing
   - Returns 200 OK immediately

2. **`app/services/outreach/reply_classifier.py`** - Reply classification
   - Classifies email intent using AI (future: Cerebras/Claude)
   - Currently uses heuristic pattern matching
   - Returns intent, sentiment, confidence, reasoning

3. **`app/services/outreach/reply_router.py`** - Reply routing
   - Routes classified replies to handlers
   - Stops/pauses sequences
   - Creates tasks, opportunities
   - Sends notifications

### Processing Flow

```
Close CRM → Webhook Endpoint → Validate Signature
                               ↓
                         Queue Background Task
                               ↓
                         Return 200 OK
                               ↓
                    [Background Processing]
                               ↓
                    Classify Reply (AI)
                               ↓
                    Route to Handler
                               ↓
              ┌─────────────────┴──────────────┐
              ↓                                ↓
        Update Sequences              Send Notifications
        Update Close CRM              Create Tasks/Opps
```

## Error Handling

- **Invalid Signature**: Returns 200 with error status (prevents retries)
- **Processing Error**: Returns 200, logs error, no retry
- **Unknown Event**: Returns 200, ignores event
- **Outgoing Email**: Returns 200, ignores (only process incoming)

## Future Enhancements

### Reply Classification
- [ ] Integrate Cerebras for AI classification (ultra-fast)
- [ ] Multi-language support
- [ ] Sentiment analysis (currently basic)
- [ ] Custom training on Tim's reply patterns

### Reply Routing
- [ ] Implement sequence stop/pause logic
- [ ] Integrate with Close CRM API (update status, create tasks)
- [ ] Send Slack notifications with action buttons
- [ ] Create opportunities for meeting requests
- [ ] Auto-send calendar links
- [ ] Suppression list management

### Monitoring
- [ ] Webhook delivery tracking
- [ ] Classification accuracy metrics
- [ ] Response time SLAs
- [ ] Slack alerts for webhook failures

## Testing

### Manual Test

1. Send test email from Close:
   ```bash
   curl -X POST http://localhost:8001/api/v1/webhooks/close/email-reply \
     -H "Content-Type: application/json" \
     -d @test_webhook_payload.json
   ```

2. Check logs:
   ```bash
   tail -f logs/app.log | grep "Close webhook"
   ```

### Sample Test Payload

Create `test_webhook_payload.json`:

```json
{
  "event": "email.received",
  "data": {
    "id": "acti_test123",
    "lead_id": "lead_test123",
    "contact_id": "cont_test123",
    "subject": "Re: Solar installation quote",
    "body_text": "Hi Tim, I'm interested! Let's schedule a call.",
    "from": [{"email": "test@example.com", "name": "Test User"}],
    "to": [{"email": "tim@coperniq.io", "name": "Tim Kipper"}],
    "date_created": "2025-12-06T10:00:00Z",
    "direction": "incoming"
  }
}
```

Expected classification: `interested`, `positive`, priority `high`

## Troubleshooting

### Webhook Not Receiving Events

1. Check Close CRM webhook logs (Settings → Webhooks)
2. Verify URL is publicly accessible
3. Check firewall/security group rules
4. Test with curl from external IP

### Signature Verification Failing

1. Check `CLOSE_WEBHOOK_SECRET` in .env
2. Verify secret matches Close CRM webhook settings
3. Check logs for signature mismatch details

### Processing Errors

1. Check application logs: `tail -f logs/app.log`
2. Verify database connectivity
3. Check Slack webhook configuration
4. Verify Close CRM API key is valid

## Support

For issues or questions:
- Check application logs
- Review webhook health endpoint
- Contact: tim@coperniq.io
