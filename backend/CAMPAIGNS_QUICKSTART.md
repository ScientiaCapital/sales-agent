# Personalized Outreach Campaigns - Quick Start Guide

## 🚀 5-Minute Setup

### 1. Run Database Migration
```bash
cd backend
alembic upgrade head
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Running upgrade 007 -> 008, add_campaign_tables
```

### 2. Start Backend Server
```bash
python3 start_server.py
```

**Server should be running at:** http://localhost:8001

### 3. Run Test Suite
```bash
python3 test_campaigns.py
```

**Expected Result:** All 7 tests pass ✅

## 📖 Basic Usage

### Create Your First Campaign

```bash
curl -X POST http://localhost:8001/api/v1/campaigns/create \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My First Campaign",
    "channel": "email",
    "min_qualification_score": 70
  }'
```

**Response:**
```json
{
  "id": 1,
  "name": "My First Campaign",
  "channel": "email",
  "status": "draft",
  "total_messages": 0
}
```

### Generate Messages

```bash
curl -X POST http://localhost:8001/api/v1/campaigns/1/generate-messages \
  -H "Content-Type: application/json" \
  -d '{
    "custom_context": "Mention our AI-powered sales automation"
  }'
```

**Response:**
```json
{
  "success": true,
  "messages_generated": 10,
  "total_cost_usd": 0.000160,
  "average_latency_ms": 633,
  "messages": [...]
}
```

### View Campaign Analytics

```bash
curl http://localhost:8001/api/v1/campaigns/1/analytics
```

**Response includes:**
- Performance metrics (open rate, click rate, reply rate)
- A/B testing results (3 variants comparison)
- Cost analysis (total, per message, per reply)

## 🎯 Common Use Cases

### 1. Email Campaign for High-Scoring Leads

```python
import httpx

client = httpx.Client(base_url="http://localhost:8001")

# Create campaign
campaign = client.post("/api/v1/campaigns/create", json={
    "name": "Enterprise Email Outreach",
    "channel": "email",
    "target_audience": {
        "industry": "Software",
        "company_size": "200-1000 employees"
    },
    "min_qualification_score": 80.0
}).json()

# Generate messages
messages = client.post(
    f"/api/v1/campaigns/{campaign['id']}/generate-messages",
    json={
        "template": "Hi {{contact_name}}, I noticed {{company}} is growing in {{industry}}..."
    }
).json()

print(f"Generated {messages['messages_generated']} messages")
print(f"Cost: ${messages['total_cost_usd']}")
```

### 2. LinkedIn Campaign with Custom Context

```python
campaign = client.post("/api/v1/campaigns/create", json={
    "name": "VP Sales LinkedIn Outreach",
    "channel": "linkedin",
    "target_audience": {"contact_title": "VP Sales"},
    "min_qualification_score": 75.0
}).json()

messages = client.post(
    f"/api/v1/campaigns/{campaign['id']}/generate-messages",
    json={
        "custom_context": "Reference our recent $10M Series B funding",
        "lead_ids": [1, 2, 3]  # Specific high-value leads
    }
).json()
```

### 3. View Message Variants for A/B Testing

```python
# Get all 3 variants for a message
variants = client.get("/api/v1/messages/1/variants").json()

print("Professional variant:", variants['variants'][0]['body'])
print("Friendly variant:", variants['variants'][1]['body'])
print("Direct variant:", variants['variants'][2]['body'])
```

## 📊 API Endpoints Reference

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/campaigns/create` | POST | Create new campaign |
| `/api/v1/campaigns/{id}/generate-messages` | POST | Generate messages with variants |
| `/api/v1/campaigns/{id}/messages` | GET | List campaign messages |
| `/api/v1/campaigns/{id}/analytics` | GET | Get analytics & A/B results |
| `/api/v1/campaigns/{id}/send` | POST | Activate campaign |
| `/api/v1/messages/{id}/variants` | GET | Get all 3 variants |
| `/api/v1/messages/{id}/status` | PUT | Update message status |

## 🔧 Troubleshooting

### Issue: Migration fails

**Solution:**
```bash
# Check current migration version
alembic current

# If needed, run all migrations
alembic upgrade head
```

### Issue: No messages generated

**Cause:** No leads match campaign criteria

**Solution:**
```bash
# Create test lead first
curl -X POST http://localhost:8001/api/v1/leads/qualify \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "Test Corp",
    "industry": "Software",
    "contact_name": "John Doe"
  }'
```

### Issue: Slow message generation

**Expected:** 633ms per message (Cerebras is ultra-fast)

**If slower:**
- Check network connection to Cerebras API
- Verify CEREBRAS_API_KEY is set correctly
- Check API rate limits

## 📈 Performance Tips

1. **Batch Operations:** Generate messages for multiple leads in one call
2. **Filter Leads:** Use `min_qualification_score` to target best leads
3. **Monitor Costs:** Check analytics for cost per reply
4. **A/B Testing:** Review variant performance to optimize future campaigns

## 🎓 Next Steps

1. **Read Full Documentation:** `OUTREACH_CAMPAIGNS.md`
2. **Integrate Sending:** Add SendGrid/LinkedIn/Twilio
3. **Set up Webhooks:** Track delivery, opens, clicks
4. **Monitor Analytics:** Optimize based on variant performance

## 📚 Additional Resources

- **API Docs:** http://localhost:8001/api/v1/docs
- **Full Documentation:** `OUTREACH_CAMPAIGNS.md`
- **Test Suite:** `test_campaigns.py`
- **Task Summary:** `TASK_4_COMPLETION_SUMMARY.md`

---

**Questions?** Check `/api/v1/docs` for interactive API documentation.
