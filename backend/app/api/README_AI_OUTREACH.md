# AI Outreach API - Quick Start

## 🚀 Endpoints

```
POST   /api/v1/ai/enrich/{company_id}         # Trigger SalesIntelAgent
GET    /api/v1/ai/drafts                      # List drafts (paginated)
GET    /api/v1/ai/drafts/{draft_id}           # Get single draft
PUT    /api/v1/ai/drafts/{draft_id}           # Edit draft
POST   /api/v1/ai/drafts/{draft_id}/send      # Send via Close CRM
POST   /api/v1/ai/drafts/{draft_id}/regenerate # Regenerate with AI
DELETE /api/v1/ai/drafts/{draft_id}           # Discard draft
```

## 📦 Files

- `ai_outreach.py` - FastAPI router (666 lines)
- `ai_outreach_migration.sql` - Supabase table schema
- `AI_OUTREACH_README.md` - Full documentation

## 🔧 Setup

1. Run migration in Supabase:
```bash
cat ai_outreach_migration.sql | pbcopy
# Paste into Supabase SQL Editor
```

2. Set environment variables:
```bash
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_KEY=eyJhbGci...
```

3. Test:
```bash
curl -X POST http://localhost:8001/api/v1/ai/enrich/abc123 \
  -H "Content-Type: application/json" \
  -d '{"contact_name": "Chris Parker"}'
```

## 📊 Example Response

```json
{
  "drafts": [
    {
      "draft_id": "uuid-123",
      "company_name": "Command Comfort",
      "draft_type": "email",
      "subject": "Quick question about your Mitsubishi units",
      "body": "Hi Chris,\n\nI saw you have 2 dogs...",
      "personal_hooks": [
        {"category": "pets", "detail": "Has 2 dogs: Burnt Bacon & Oreo"}
      ],
      "confidence": 0.85
    }
  ]
}
```

## 🔗 Related

- SalesIntelAgent: `app/services/langgraph/agents/sales_intel_agent.py`
- Full docs: `AI_OUTREACH_README.md`
