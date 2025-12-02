# AI Outreach Router - API Documentation

## Overview

The AI Outreach Router provides endpoints for AI-powered sales intelligence extraction and outreach draft management. It integrates with the SalesIntelAgent to analyze company websites and generate personalized email/SMS/voice drafts.

## Architecture

```
┌─────────────┐     ┌──────────────────┐     ┌──────────────┐
│   Frontend  │────>│  AI Outreach API │────>│  SalesIntel  │
│  Dashboard  │     │                  │     │    Agent     │
└─────────────┘     └──────────────────┘     └──────────────┘
                             │                       │
                             ├───────────────────────┘
                             ▼
                    ┌─────────────────┐
                    │    Supabase     │
                    │  dim_ai_drafts  │
                    │                 │
                    └─────────────────┘
```

## Database Schema

### `dim_ai_drafts` Table (Supabase)

See migration: `supabase/migrations/20251202_create_ai_drafts.sql`

```sql
CREATE TABLE IF NOT EXISTS public.dim_ai_drafts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES public.dim_companies(id) ON DELETE CASCADE,
    contact_id UUID REFERENCES public.dim_contacts(id) ON DELETE SET NULL,
    draft_type TEXT NOT NULL CHECK (draft_type IN ('email', 'sms', 'voice')),
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'sent', 'discarded')),
    subject TEXT,  -- For email only
    body TEXT NOT NULL,
    personal_hooks JSONB DEFAULT '[]'::jsonb,
    confidence FLOAT DEFAULT 0.5 CHECK (confidence >= 0 AND confidence <= 1),
    model_used TEXT DEFAULT 'llama-3.3-70b',
    processing_time_ms INT DEFAULT 0,
    sent_at TIMESTAMPTZ,
    close_activity_id TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'system'
);
```

## API Endpoints

### 1. POST /api/v1/ai/enrich/{company_id}

Trigger SalesIntelAgent enrichment for a company.

**Request Body:**
```json
{
  "contact_name": "Chris Parker",
  "contact_title": "CEO",
  "scraped_content": "Optional - fetched from database if not provided",
  "regenerate": false
}
```

**Response:**
```json
{
  "company_id": "abc123",
  "company_name": "Command Comfort",
  "drafts_generated": 3,
  "processing_time_ms": 2847,
  "confidence": 0.82,
  "message": "Generated 3 drafts for Command Comfort"
}
```

**Workflow:**
1. Fetch company data from `dim_companies`
2. Get scraped content (from request or `fact_enrichments`)
3. Run SalesIntelAgent to extract personal hooks + generate drafts
4. Save 3 drafts (email, SMS, voice) to `dim_ai_drafts`
5. Return summary

**Use Cases:**
- Enrich a newly discovered lead
- Regenerate drafts after scraping new content
- Bulk enrichment from dashboard (loop over company_ids)

---

### 2. GET /api/v1/ai/drafts

List pending outreach drafts with pagination and filtering.

**Query Parameters:**
- `status` (optional): `pending`, `approved`, `sent`, `discarded`
- `draft_type` (optional): `email`, `sms`, `voice`
- `page` (default: 1): Page number
- `page_size` (default: 50, max: 100): Items per page

**Response:**
```json
{
  "drafts": [
    {
      "draft_id": "draft-uuid-123",
      "company_id": "comp-uuid-456",
      "company_name": "Command Comfort",
      "draft_type": "email",
      "status": "pending",
      "subject": "Quick question about your Mitsubishi units",
      "body": "Hi Chris,\n\nI saw you have 2 dogs (Burnt Bacon & Oreo) - adorable names!...",
      "contact_name": "Chris Parker",
      "contact_title": "CEO",
      "personal_hooks": [
        {
          "category": "pets",
          "detail": "Has 2 dogs: Burnt Bacon & Oreo",
          "opener": "I saw you have 2 dogs - Burnt Bacon is such a unique name! How'd you come up with it?"
        }
      ],
      "confidence": 0.85,
      "generated_at": "2025-12-02T15:30:00Z",
      "updated_at": "2025-12-02T15:30:00Z",
      "sent_at": null
    }
  ],
  "total": 142,
  "page": 1,
  "page_size": 50
}
```

**Use Cases:**
- Dashboard inbox for BDRs to review AI-generated drafts
- Filter by `status=pending` to see what needs review
- Filter by `draft_type=email` to focus on email outreach

---

### 3. GET /api/v1/ai/drafts/{draft_id}

Get a single draft by ID.

**Response:** Same as individual draft object above.

**Use Cases:**
- View full draft details before editing
- Fetch draft for approval modal

---

### 4. PUT /api/v1/ai/drafts/{draft_id}

Update draft content (subject/body).

**Request Body:**
```json
{
  "subject": "Updated subject line",
  "body": "Updated body text with human edits"
}
```

**Response:** Updated draft object.

**Use Cases:**
- BDR edits AI-generated draft before sending
- Fix typos or adjust tone
- Add custom CTA

---

### 5. POST /api/v1/ai/drafts/{draft_id}/send

Approve and send draft via Close CRM.

**Request Body:**
```json
{
  "send_now": true,
  "scheduled_at": null
}
```

**Response:**
```json
{
  "draft_id": "draft-uuid-123",
  "status": "sent",
  "message": "Draft sent successfully",
  "close_activity_id": "act_abc123"
}
```

**Workflow:**
1. Validate draft exists and is pending/approved
2. Mark as approved (if pending)
3. Send via Close CRM API (email/SMS)
4. Mark as sent with timestamp
5. Return confirmation with Close CRM activity ID

**Safety:**
- If `CLOSE_WRITE_DISABLED=true`, marks as sent but doesn't actually send
- Prevents sending already-sent or discarded drafts

**Use Cases:**
- BDR approves draft and sends immediately
- Schedule for later (if `scheduled_at` provided)

---

### 6. POST /api/v1/ai/drafts/{draft_id}/regenerate

Regenerate draft with fresh AI analysis.

**Response:** Same as POST `/ai/enrich/{company_id}`

**Workflow:**
1. Get existing draft to extract company_id
2. Delete old draft
3. Re-run SalesIntelAgent enrichment
4. Generate new draft

**Use Cases:**
- AI-generated draft is off-brand or low quality
- New website content scraped, need fresh analysis
- Want different tone/style

---

### 7. DELETE /api/v1/ai/drafts/{draft_id}

Discard/delete a draft (mark as discarded).

**Response:**
```json
{
  "message": "Draft draft-uuid-123 discarded successfully"
}
```

**Use Cases:**
- Reject low-quality AI draft
- Lead is no longer valid
- Already contacted via different channel

---

## Workflow Example: From Enrichment to Send

```python
import httpx

async def enrich_and_send_workflow(company_id: str):
    """Full workflow: enrich -> review -> edit -> send"""

    # 1. Trigger enrichment
    response = await client.post(f"/api/v1/ai/enrich/{company_id}", json={
        "contact_name": "Chris Parker",
        "regenerate": False
    })
    print(f"Generated {response.json()['drafts_generated']} drafts")

    # 2. List pending drafts for this company
    drafts = await client.get("/api/v1/ai/drafts", params={
        "status": "pending",
        "draft_type": "email"
    })

    email_draft = drafts.json()['drafts'][0]
    draft_id = email_draft['draft_id']

    # 3. Review and edit (optional)
    await client.put(f"/api/v1/ai/drafts/{draft_id}", json={
        "body": email_draft['body'] + "\n\nP.S. Love the dog names!"
    })

    # 4. Send via Close CRM
    response = await client.post(f"/api/v1/ai/drafts/{draft_id}/send", json={
        "send_now": True
    })

    print(f"Sent! Activity ID: {response.json()['close_activity_id']}")
```

## Integration with SalesIntelAgent

The router uses `extract_sales_intel()` from `app.services.langgraph.agents`:

```python
intel_result = await extract_sales_intel(
    company_name="Command Comfort",
    contact_name="Chris Parker",
    contact_title="CEO",
    scraped_content="Website content here...",
    services=["HVAC", "Solar"],
    brands=["Mitsubishi", "Carrier"],
    location="Austin, TX"
)

# Returns:
# {
#   "personal_hooks": [{"category": "pets", "detail": "Has 2 dogs", ...}],
#   "company_story": "Founded in 2010 by Chris Parker...",
#   "email_subject": "Quick question about your Mitsubishi units",
#   "email_body": "Hi Chris, ...",
#   "sms_draft": "Chris - loved reading about Burnt Bacon...",
#   "voice_opener": "Hi Chris, this is Tom from Scientia...",
#   "confidence": 0.85,
#   "processing_time_ms": 2847
# }
```

## Environment Variables

```bash
# Required
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Optional (for Close CRM integration)
CLOSE_API_KEY=api_xxxxxxxxxxxx
CLOSE_WRITE_DISABLED=true  # Set to false in production
```

## Error Handling

All endpoints return proper HTTP status codes:

- `200 OK`: Success
- `404 Not Found`: Draft/company not found
- `400 Bad Request`: Invalid status transition (e.g., sending already-sent draft)
- `500 Internal Server Error`: Database or AI extraction error
- `503 Service Unavailable`: Supabase not configured

Errors include detailed messages:
```json
{
  "detail": "Draft draft-uuid-123 not found"
}
```

## Performance

| Endpoint | Typical Latency |
|----------|-----------------|
| POST /ai/enrich/{company_id} | 2000-3000ms (AI extraction) |
| GET /ai/drafts | 50-200ms (database query) |
| GET /ai/drafts/{draft_id} | 20-100ms (single record) |
| PUT /ai/drafts/{draft_id} | 50-150ms (update) |
| POST /ai/drafts/{draft_id}/send | 500-1000ms (Close CRM API) |
| DELETE /ai/drafts/{draft_id} | 50-150ms (soft delete) |

## Security

- Uses Supabase Service Key for database access (never exposed to client)
- Validates draft ownership before allowing edits/sends
- Prevents sending already-sent drafts (status checks)
- Supports CLOSE_WRITE_DISABLED safety flag for testing

## Testing

```bash
# Start server
cd backend
source ../venv/bin/activate
python start_server.py

# Test endpoints (requires valid company_id in Supabase)
curl -X POST http://localhost:8001/api/v1/ai/enrich/abc123 \
  -H "Content-Type: application/json" \
  -d '{"contact_name": "Chris Parker"}'

curl http://localhost:8001/api/v1/ai/drafts?status=pending

curl -X PUT http://localhost:8001/api/v1/ai/drafts/draft-uuid-123 \
  -H "Content-Type: application/json" \
  -d '{"body": "Updated text"}'
```

## Future Enhancements

1. **Batch Enrichment**: POST /ai/enrich/batch (process 100+ companies)
2. **A/B Testing**: Generate 3 variants per draft (professional/friendly/direct)
3. **Sentiment Analysis**: Rate draft tone before sending
4. **Learning**: Track reply rates per draft style, optimize over time
5. **Templates**: Save best-performing drafts as templates
6. **Scheduled Sends**: Actually implement scheduled sending (currently mocked)
7. **Multi-language**: Detect prospect language, generate in Spanish/etc.

## Support

For issues or questions, check:
- `/api/v1/docs` - Interactive API documentation
- `backend/app/api/ai_outreach.py` - Source code
- `backend/app/services/langgraph/agents/sales_intel_agent.py` - AI agent logic
