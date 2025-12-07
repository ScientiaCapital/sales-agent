# /enrich Slash Command

Enrich a company or person, checking Close CRM first for duplicates.

## Usage

```
/enrich <input> [--stage channels] [--auto-trigger]
```

## Arguments

- `<input>` - Any of:
  - URL: `https://acme-hvac.com`
  - Domain: `acme-hvac.com`
  - Company name: `"Acme HVAC"`
  - Close lead ID: `lead_abc123`
  - Person: `"John Smith, Owner at Acme HVAC"`

## Options

- `--stage <channels>` - Stage outreach for channels (comma-separated)
  - `email` - Create email draft
  - `sms` - Create SMS draft
  - `linkedin` - Queue LinkedIn connection request
  - `call` - Create call task
  - `all` - All channels

- `--auto-trigger` - Auto-send outreach if lead is HOT (default: false)

## Examples

### Basic enrichment
```
/enrich https://acme-hvac.com
```

**Output:**
```
🔍 Checking Close CRM for duplicates...
✅ Not a duplicate. Starting enrichment...
📊 Enriched: Acme HVAC
   - Domain: acme-hvac.com
   - ICP Score: 78
   - Tier: GOLD
   - Priority: WARM
   - Duration: 4.2s

Ready to stage outreach. Which channels?
[ ] Email  [ ] SMS  [ ] LinkedIn  [ ] Call
```

### Company name
```
/enrich "Acme HVAC"
```

### Close lead ID
```
/enrich lead_abc123
```

### Person with context
```
/enrich "John Smith, Owner at Acme HVAC"
```

### With staging
```
/enrich https://acme.com --stage email,sms
```

**Output:**
```
🔍 Checking Close CRM... Not a duplicate.
📊 Enriched: Acme Inc (ICP: 82, Tier: GOLD)
📝 Staging outreach:
   - ✅ Email draft created → awaiting approval
   - ✅ SMS draft created → awaiting approval
🔔 Slack notification sent to #bdr-approvals
```

### Auto-trigger for HOT leads
```
/enrich https://beta-hvac.com --stage email --auto-trigger
```

**Output:**
```
🔍 Checking Close CRM... Not a duplicate.
📊 Enriched: Beta HVAC (ICP: 88, Tier: PLATINUM)
🔥 HOT lead detected!
📧 Email auto-sent to john@beta-hvac.com
✅ Lead added to Close CRM
```

### Duplicate found
```
/enrich https://acme-hvac.com
```

**Output:**
```
🔍 Checking Close CRM for duplicates...
⚠️  Already exists: Acme HVAC Inc
   - Confidence: 92.3%
   - Close URL: https://app.close.com/lead/lead_xyz/
   - Last updated: 2 days ago

No enrichment needed.
```

## Pipeline

The `/enrich` command follows this pipeline:

```
Input → Parse → 🔍 CHECK CLOSE CRM FIRST →
  ├─ Exists: Return link to existing lead
  └─ New: Enrich with ScoutAgent →
          Rank with RankingAgent →
          (Optional) Stage outreach →
          Notify user
```

## Implementation

**Backend:**
- `backend/app/services/langgraph/agents/dropin_agent.py` - DropInAgent
- `backend/app/tasks/dropin_tasks.py` - Celery task `run_dropin_enrichment`

**Terminal CLI:**
```bash
cd backend && source ../venv/bin/activate
python -m cli.enrich "https://acme.com" --stage email,sms
```

**API Endpoint:**
```
POST /api/v1/langgraph/dropin
{
  "input": "https://acme-hvac.com",
  "input_type": "auto",
  "stage_channels": ["email", "sms"],
  "auto_trigger": false
}
```

**Slack Integration:**
```
/enrich https://acme-hvac.com
```

## Critical Rules

1. **Close CRM dedup is ALWAYS FIRST** - Never enrich without checking for duplicates
2. **Domain + fuzzy name match** - 85% similarity threshold for company matching
3. **Safe defaults** - Draft mode by default, auto-trigger only when explicitly requested
4. **No OpenAI** - Uses Cerebras, Claude, or DeepSeek only

## Error Handling

**Invalid input:**
```
/enrich ""
→ ❌ Error: Input cannot be empty
```

**Network error:**
```
/enrich https://timeout-example.com
→ ❌ Error: Network timeout. Retrying in 30 seconds...
```

**Close CRM API error:**
```
/enrich https://acme.com
→ ⚠️  Warning: Close CRM API unavailable. Proceeding without dedup check.
```

## Performance

- **Fast path (duplicate found):** ~500ms (Close CRM search only)
- **Enrichment path (new lead):** ~3-5s (Close search + website scraping + AI scoring)
- **With staging:** +1-2s (draft generation)

## Cost

- **Duplicate check:** $0 (Close CRM API call only)
- **Enrichment:** ~$0.0003 (Cerebras AI inference)
- **Total per lead:** < $0.001
