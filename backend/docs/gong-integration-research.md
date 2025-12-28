# Gong Integration Research & Implementation Plan

**Date**: 2025-12-27
**Status**: Research Complete - Awaiting API Key

---

## Executive Summary

Gong provides conversation intelligence APIs that can significantly enhance our Call Intelligence, Trigger Engine, and Attribution systems. Key integration opportunities:

1. **Replace/Augment AssemblyAI** - Gong provides richer call analysis (trackers, scorecards, topics)
2. **Unified Call Recording** - Single source of truth for all sales calls
3. **Enhanced Attribution** - Deal intelligence with conversation context
4. **Trigger Automation** - Webhook-based real-time triggers on call events

---

## Gong API Overview

### Two API Types

| API | Purpose | Use Case |
|-----|---------|----------|
| **Standard API** | Extract call data, transcripts, analytics | Our primary integration |
| **Engage API** | Outreach automation, sequences | Complement our email sequences |

### Base URLs
- **API**: `https://api.gong.io/v2/`
- **OAuth**: `https://app.gong.io/oauth2/`

### Rate Limits
- **Default**: 3 requests/second, 10,000 requests/day
- **Pagination**: 100 records per request max

---

## Authentication

### Option 1: API Key (Recommended for MVP)
```python
import base64
import requests

# Credentials from Gong Admin > Settings > Ecosystem > API
ACCESS_KEY = os.getenv("GONG_ACCESS_KEY")
ACCESS_SECRET = os.getenv("GONG_ACCESS_SECRET")

# Basic Auth header
credentials = base64.b64encode(f"{ACCESS_KEY}:{ACCESS_SECRET}".encode()).decode()
headers = {
    "Authorization": f"Basic {credentials}",
    "Content-Type": "application/json"
}
```

### Option 2: OAuth 2.0 (For Published App)
- Required scopes: `api:calls:read:basic`, `api:calls:read:transcript`, `api:users:read`
- Access tokens expire after 24 hours
- Requires Gong developer instance (5 business days to provision)

---

## Key API Endpoints

### 1. Calls Retrieval

```http
GET /v2/calls?fromDateTime=2025-01-01T00:00:00Z&toDateTime=2025-01-31T23:59:59Z
```

**Response Fields**:
- `id` - Unique call ID
- `url` - Gong call URL
- `title` - Call title
- `scheduled` - Scheduled time
- `started` - Actual start time
- `duration` - Duration in seconds
- `primaryUserId` - Rep's Gong user ID
- `direction` - inbound/outbound
- `parties` - List of participants

### 2. Extensive Call Data

```http
POST /v2/calls/extensive
```

**Request Body**:
```json
{
  "contentSelector": {
    "exposedFields": {
      "content": {
        "topics": true,
        "trackers": true,
        "trackerOccurrences": true,
        "pointsOfInterest": true,
        "structure": true
      },
      "parties": true,
      "collaboration": {
        "publicComments": true
      },
      "interaction": {
        "speakers": true,
        "questions": true,
        "personInteractionStats": true
      }
    }
  },
  "filter": {
    "callIds": ["1234567890"]
  }
}
```

**Response Includes**:
- `topics` - Detected conversation topics with duration
- `trackers` - Keyword/phrase matches (competitors, objections, pricing)
- `pointsOfInterest` - Key moments in call
- `questions` - Questions asked by each party
- `personInteractionStats` - Talk time, patience, engagement scores

### 3. Transcripts

```http
POST /v2/calls/transcript
```

**Request Body**:
```json
{
  "filter": {
    "callIds": ["1234567890"]
  }
}
```

**Response Structure**:
```json
{
  "callTranscripts": [
    {
      "callId": "1234567890",
      "transcript": [
        {
          "speakerId": "6143068094786164742",
          "topic": "Discovery",
          "sentences": [
            {
              "start": 60,
              "end": 600,
              "text": "Tell me about your current challenges."
            }
          ]
        }
      ]
    }
  ]
}
```

### 4. Scorecards

```http
GET /v2/settings/scorecards
```

Returns all scorecard templates configured in Gong.

```http
GET /v2/calls/{callId}/scorecards
```

Returns scores given to a specific call.

### 5. Users

```http
GET /v2/users
```

Returns all Gong users for mapping to our reps.

### 6. Stats & Activity

```http
POST /v2/stats/activity/day-by-day
```

Returns daily activity stats by user.

---

## Webhooks

### Setup
1. Enable in Gong Developer Hub > Automations
2. Configure endpoint URL and authentication
3. Set trigger conditions (call processed, call scored, etc.)

### Payload Structure
```json
{
  "callData": {
    "metaData": {
      "id": "1234567890",
      "url": "https://app.gong.io/call?id=...",
      "title": "Discovery Call - Acme Corp",
      "started": "2025-01-15T10:30:00Z",
      "duration": 1800,
      "primaryUserId": "user_123"
    },
    "parties": [...],
    "content": {
      "topics": [...],
      "trackers": [...]
    }
  },
  "isTest": false
}
```

### Webhook Limitations
- Only fires after call is processed (not real-time)
- No webhook for call updates (data is immutable after processing)
- Must handle JWT signature verification

---

## Engage API (Sequences)

### List Flows
```http
GET /v2/flows?flowEmailOwner=user@company.com
```

### Assign Prospects to Flow
```http
POST /v2/flows/{flowId}/prospects
```

**Request Body**:
```json
{
  "crmIds": ["lead_123", "lead_456"],
  "useDefaultOwner": true
}
```

### Unassign Prospects
```http
DELETE /v2/flows/{flowId}/prospects/{crmId}
```

---

## Data Mapping to Our Models

### Gong Call → CallInsight

| Gong Field | Our Field | Notes |
|------------|-----------|-------|
| `callId` | `voice_session_id` | Store Gong ID as reference |
| `parties[].emailAddress` | `lead_id` | Match to dim_companies |
| `transcript` | `transcript` | Concatenate sentences |
| `content.topics` | `key_topics` | Map topic names |
| `content.trackers` | `objections`, `buying_signals`, `competitors_mentioned` | Categorize by tracker type |
| `interaction.speakers[].talkRatio` | `talk_ratio` | Use rep's ratio |
| `scorecards[].score` | `call_score` | Use Gong's scorecard |
| `content.pointsOfInterest` | `action_items` | Extract action items |

### Gong Tracker Types → Our Categories

| Gong Tracker | Our Category | Example Phrases |
|--------------|--------------|-----------------|
| Competitor mention | `competitors_mentioned` | "Salesforce", "HubSpot" |
| Objection | `objections` | "too expensive", "not ready" |
| Positive sentiment | `buying_signals` | "sounds great", "when can we start" |
| Pricing discussion | `key_topics` | "what's the cost", "pricing" |
| Next steps | `action_items` | "I'll send", "follow up" |

### Gong User → Rep Attribution

| Gong Field | Our Field |
|------------|-----------|
| `userId` | `rep_id` |
| `firstName` + `lastName` | `rep_name` |
| `emailAddress` | Match to existing users |

---

## Implementation Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Sales-Agent Backend                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐  │
│  │ Gong Service │───▶│ CallInsights │───▶│ TriggerEngine│  │
│  │              │    │   Service    │    │              │  │
│  └──────┬───────┘    └──────────────┘    └──────────────┘  │
│         │                    │                    │         │
│         │                    ▼                    ▼         │
│         │           ┌──────────────┐    ┌──────────────┐   │
│         │           │ call_insights│    │trigger_rules │   │
│         │           │    table     │    │    table     │   │
│         │           └──────────────┘    └──────────────┘   │
│         │                                                   │
│         ▼                                                   │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                   Celery Tasks                        │  │
│  │  • sync_gong_calls       (scheduled, every 15 min)   │  │
│  │  • process_gong_webhook  (on webhook receipt)        │  │
│  │  • enrich_call_with_gong (on demand)                 │  │
│  └──────────────────────────────────────────────────────┘  │
│                              │                              │
└──────────────────────────────┼──────────────────────────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │    Gong API         │
                    │  api.gong.io/v2     │
                    └─────────────────────┘
```

---

## Implementation Plan

### Phase 1: Core Integration (Week 1)

**Files to Create**:
```
app/
├── services/
│   └── integrations/
│       └── gong/
│           ├── __init__.py
│           ├── client.py          # Gong API client
│           ├── models.py          # Pydantic models for Gong responses
│           └── sync_service.py    # Sync logic
├── tasks/
│   └── gong_tasks.py              # Celery tasks
└── api/
    └── gong_webhooks.py           # Webhook endpoint
```

**Key Classes**:
```python
# app/services/integrations/gong/client.py
class GongClient:
    """Gong API client with rate limiting and retries."""

    async def get_calls(self, from_date, to_date) -> List[GongCall]
    async def get_call_extensive(self, call_id) -> GongCallExtensive
    async def get_transcript(self, call_id) -> GongTranscript
    async def get_scorecards(self, call_id) -> List[GongScorecard]
    async def get_users(self) -> List[GongUser]

# app/services/integrations/gong/sync_service.py
class GongSyncService:
    """Syncs Gong data to our call_insights table."""

    async def sync_recent_calls(self, hours=1) -> SyncResult
    async def process_call(self, call_id: str) -> CallInsight
    async def map_gong_to_insight(self, gong_data) -> CallInsight
```

### Phase 2: Webhook Integration (Week 2)

```python
# app/api/gong_webhooks.py
@router.post("/webhooks/gong/call-processed")
async def handle_gong_webhook(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
):
    """Handle Gong webhook for processed calls."""
    # Verify JWT signature
    # Extract call data
    # Queue processing task
    # Trigger rules evaluation
```

### Phase 3: Engage Integration (Week 3)

```python
# Integration with our SequenceManager
class GongEngageSync:
    """Sync our sequences with Gong Engage flows."""

    async def add_to_flow(self, lead_id, flow_id)
    async def remove_from_flow(self, lead_id, flow_id)
    async def sync_flow_status(self, lead_id) -> FlowStatus
```

### Phase 4: Dashboard & Analytics (Week 4)

- Add Gong metrics to existing dashboards
- Show Gong scorecards alongside our call_score
- Display tracker insights (objections, buying signals)
- Rep leaderboard with Gong stats

---

## Migration Strategy

### For Existing Calls (AssemblyAI)
1. Keep existing call_insights records
2. Add `source` column: `assemblyai` | `gong` | `hybrid`
3. Prefer Gong for new calls if available
4. Backfill historical calls from Gong on request

### Database Changes

```sql
-- Add Gong-specific columns to call_insights
ALTER TABLE call_insights ADD COLUMN gong_call_id VARCHAR(100);
ALTER TABLE call_insights ADD COLUMN gong_scorecard JSONB;
ALTER TABLE call_insights ADD COLUMN source VARCHAR(20) DEFAULT 'assemblyai';
ALTER TABLE call_insights ADD COLUMN trackers JSONB DEFAULT '[]';

-- Index for Gong lookups
CREATE INDEX ix_call_insights_gong_id ON call_insights(gong_call_id);
```

---

## Environment Variables Needed

```bash
# Gong API Credentials
GONG_ACCESS_KEY=<access-key>
GONG_ACCESS_SECRET=<access-secret>
GONG_API_BASE_URL=https://api.gong.io/v2

# Webhook Configuration
GONG_WEBHOOK_SECRET=<jwt-public-key>

# Optional: OAuth for published app
GONG_CLIENT_ID=<client-id>
GONG_CLIENT_SECRET=<client-secret>
GONG_REDIRECT_URI=https://your-app.com/oauth/gong/callback
```

---

## CRM Integration Note

Since we use **Close CRM**, and Gong doesn't have native Close integration:

1. Use Gong's CRM API to push Close data to Gong
2. This enables Gong to display Close context on calls
3. Calls will be linked to Close leads/opportunities

```python
# Register CRM integration
POST /v2/crm/integrations
{
    "integrationName": "Close CRM",
    "baseUrl": "https://api.close.com/api/v1"
}

# Upload lead data
POST /v2/crm/entities
{
    "integrationId": "...",
    "entities": [
        {
            "type": "ACCOUNT",
            "crmId": "lead_123",
            "name": "Acme Corp",
            "domain": "acme.com"
        }
    ]
}
```

---

## Sources

- [What the Gong API provides](https://help.gong.io/docs/what-the-gong-api-provides)
- [Create an OAuth app for Gong](https://help.gong.io/docs/create-an-app-for-gong)
- [Payload sent to webhooks](https://help.gong.io/docs/payload-sent-to-webhooks)
- [Gong database reference](https://help.gong.io/docs/gong-database-reference)
- [Data model & structure](https://help.gong.io/docs/data-model-structure)
- [Gong Engage API capabilities](https://help.gong.io/docs/gong-engage-api-capabilities)
- [Manage your CRM API integration](https://help.gong.io/docs/manage-your-crm-api-integration)
- [GitHub: gong-client (Rust)](https://github.com/ksindi/gong-client)
- [GitHub: gong-api (Ruby)](https://github.com/matteeyah/gong-api)
- [Guide: Ingesting Gong Transcripts For RAG](https://www.useparagon.com/learn/guide-ingesting-gong-transcripts/)

---

## Next Steps

1. **Get API Key** - Admin access required from Gong settings
2. **Test API Access** - Verify credentials with simple GET /v2/users call
3. **Create Gong Client** - Implement `GongClient` class
4. **Add Sync Task** - Celery task to sync calls periodically
5. **Configure Webhook** - Set up endpoint and register with Gong
6. **Update CallInsightsService** - Add Gong as data source option
7. **Test End-to-End** - Verify full flow with real calls
