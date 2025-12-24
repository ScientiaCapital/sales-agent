# AI Command Center - Design Document

**Date**: December 2, 2025
**Status**: Approved
**Author**: Claude Code + Tim Kipper

---

## Executive Summary

Transform the existing Sales Agent Dashboard into an **AI Command Center** that enables Tim (Sr. BDR) to:
1. **One-Click Enrichment** - Select lead, click "Enrich", get AI-powered sales intel
2. **Draft Review Queue** - Review/edit/approve AI-generated email, SMS, and voice drafts
3. **Voice Script Generator** - Personalized cold call openers with objection handlers

**Target Outcome**: 100x outreach effectiveness by combining killer scraping with intelligent LangGraph agents.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                   AI COMMAND CENTER                          │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │ LEAD QUEUE   │  │ AI INSIGHTS  │  │ DRAFT QUEUE  │       │
│  │ (Existing)   │→ │ (NEW Panel)  │→ │ (NEW Tab)    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
│         │                  │                 │               │
│         ▼                  ▼                 ▼               │
│  ┌──────────────────────────────────────────────────────┐   │
│  │              BACKEND API (FastAPI)                    │   │
│  │  /api/ai/enrich  →  SalesIntelAgent                  │   │
│  │  /api/ai/drafts  →  BDRAgent (draft generation)      │   │
│  │  /api/ai/send    →  Close CRM integration            │   │
│  └──────────────────────────────────────────────────────┘   │
│                            │                                 │
│         ┌──────────────────┼──────────────────┐             │
│         ▼                  ▼                  ▼             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │  Cerebras   │  │  Supabase   │  │  Close CRM  │         │
│  │  (LLM)      │  │  (Storage)  │  │  (Outreach) │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

---

## Database Schema

### New Table: `dim_ai_drafts`

```sql
CREATE TABLE dim_ai_drafts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID REFERENCES dim_companies(id),
    contact_id UUID REFERENCES dim_contacts(id),

    -- Draft content
    draft_type TEXT NOT NULL CHECK (draft_type IN ('email', 'sms', 'voice')),
    subject TEXT,           -- For email only
    body TEXT NOT NULL,

    -- AI metadata
    personal_hooks JSONB,   -- Hooks used in this draft
    confidence FLOAT,
    model_used TEXT DEFAULT 'llama-3.3-70b',
    processing_time_ms INT,

    -- Status tracking
    status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'sent', 'discarded')),
    sent_at TIMESTAMPTZ,
    close_activity_id TEXT, -- Close CRM activity ID after send

    -- Audit
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    created_by TEXT DEFAULT 'system'
);

-- Performance indexes
CREATE INDEX idx_drafts_pending ON dim_ai_drafts(status, created_at DESC)
WHERE status = 'pending';

CREATE INDEX idx_drafts_company ON dim_ai_drafts(company_id);

-- RLS Policy
ALTER TABLE dim_ai_drafts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all for service role" ON dim_ai_drafts
    FOR ALL USING (true);
```

### Enhanced Table: `dim_companies` (add columns)

```sql
ALTER TABLE dim_companies ADD COLUMN IF NOT EXISTS
    ai_enriched_at TIMESTAMPTZ,
    ai_personal_hooks JSONB,
    ai_company_story TEXT,
    ai_pain_points JSONB,
    ai_buying_signals JSONB,
    ai_confidence FLOAT;
```

---

## API Endpoints

### `/backend/app/api/ai_outreach.py`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/ai/enrich/{company_id}` | POST | Trigger SalesIntelAgent enrichment |
| `/api/ai/drafts` | GET | List pending drafts (paginated) |
| `/api/ai/drafts/{id}` | GET | Get single draft |
| `/api/ai/drafts/{id}` | PUT | Update draft content |
| `/api/ai/drafts/{id}/send` | POST | Approve and send via Close CRM |
| `/api/ai/drafts/{id}/regenerate` | POST | Regenerate with fresh analysis |
| `/api/ai/drafts/{id}` | DELETE | Discard draft |
| `/api/ai/bulk-enrich` | POST | Enrich multiple leads |

---

## Frontend Components

### New Dashboard Tab Structure

```tsx
<Tabs defaultValue="command-center">
  <TabsList>
    <TabsTrigger value="command-center">Command Center</TabsTrigger>
    <TabsTrigger value="draft-queue">Draft Queue</TabsTrigger>
    <TabsTrigger value="icp-queue">ICP Queue</TabsTrigger>
    <TabsTrigger value="bdr-view">BDR View</TabsTrigger>
    <TabsTrigger value="ceo-view">CEO/CTO</TabsTrigger>
  </TabsList>
</Tabs>
```

### Component Hierarchy

```
dashboard/src/components/
├── ai/
│   ├── CommandCenter.tsx        # Main layout (lead list + insights)
│   ├── LeadListPanel.tsx        # Paginated lead list with actions
│   ├── AIInsightsPanel.tsx      # Personal hooks, company story, pain points
│   ├── EnrichButton.tsx         # One-click enrichment trigger
│   ├── DraftReviewQueue.tsx     # Queue of pending drafts
│   ├── DraftCard.tsx            # Single draft with edit/approve/discard
│   ├── DraftEditor.tsx          # Inline editing with character count
│   ├── VoiceScriptCard.tsx      # Cold call script with hooks
│   └── BulkEnrichButton.tsx     # Enrich multiple selected leads
```

---

## Implementation Phases

### Phase 1: Database & Core API (Week 1)

**Tasks (can run in parallel):**
- [ ] Create `dim_ai_drafts` table migration
- [ ] Add AI columns to `dim_companies`
- [ ] Create `/api/ai/enrich` endpoint
- [ ] Create `/api/ai/drafts` CRUD endpoints
- [ ] Unit tests for API endpoints

**Specialized Agents:**
- `database-design:schema-design` - Schema validation
- `database-migrations:sql-migrations` - Migration generation
- `api-scaffolding:fastapi-pro` - API implementation

**Gate:** Code review (100% no errors) before Phase 2

---

### Phase 2: Draft Queue UI (Week 2)

**Tasks (can run in parallel):**
- [ ] `DraftReviewQueue.tsx` component
- [ ] `DraftCard.tsx` with inline editing
- [ ] `DraftEditor.tsx` with character count
- [ ] Draft Queue API route in dashboard
- [ ] Integration tests for draft workflow

**Specialized Agents:**
- `feature-dev:feature-dev` - Component implementation
- `application-performance:frontend-developer` - React optimization

**Gate:** Code review (100% no errors) before Phase 3

---

### Phase 3: One-Click Enrichment (Week 3)

**Tasks (can run in parallel):**
- [ ] `EnrichButton.tsx` component
- [ ] `AIInsightsPanel.tsx` component
- [ ] Loading states and error handling
- [ ] Integration with existing ICPQueue
- [ ] E2E tests for enrichment flow

**Specialized Agents:**
- `feature-dev:feature-dev` - Component implementation
- `llm-application-dev:ai-engineer` - Agent integration

**Gate:** Code review (100% no errors) before Phase 4

---

### Phase 4: Voice Script & Command Center (Week 4)

**Tasks (can run in parallel):**
- [ ] `VoiceScriptCard.tsx` component
- [ ] `CommandCenter.tsx` combined layout
- [ ] `LeadListPanel.tsx` with selection
- [ ] Keyboard shortcuts (J/K/E/A)
- [ ] Close CRM integration for call logging
- [ ] Performance optimization

**Specialized Agents:**
- `feature-dev:feature-dev` - Component implementation
- `application-performance:performance-engineer` - Optimization

**Final Gate:** Comprehensive code review + security scan

---

## Parallelization Matrix

| Task | Dependencies | Can Parallel With |
|------|--------------|-------------------|
| DB Migration | None | API Endpoints, UI Components |
| API Endpoints | DB Migration | UI Components |
| DraftCard.tsx | None | DraftQueue.tsx, AIInsightsPanel.tsx |
| EnrichButton.tsx | API /enrich | VoiceScriptCard.tsx |
| Close CRM Integration | API /send | All UI components |

---

## Testing Strategy

### Unit Tests
- API endpoint tests (pytest)
- Component tests (Vitest + React Testing Library)
- Agent mock tests

### Integration Tests
- Enrichment flow: Button → API → Agent → Database → UI
- Draft flow: Generate → Edit → Send → Close CRM

### E2E Tests (Playwright)
- Full enrichment workflow
- Draft review and approval
- Bulk enrichment

---

## Security Considerations

- RLS policies on `dim_ai_drafts`
- Rate limiting on `/api/ai/enrich` (prevent abuse)
- Input sanitization on draft content
- Close CRM API key in environment variables only
- Audit trail for all draft actions

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Enrichment time | < 5 seconds |
| Draft generation | < 3 seconds |
| Tim's approval rate | > 60% drafts approved |
| Outreach volume | 3x current rate |
| Reply rate | 2x improvement |

---

## Agent Assignment Summary

| Phase | Primary Agents | Review Agent |
|-------|---------------|--------------|
| 1 | database-design, api-scaffolding:fastapi-pro | code-reviewer |
| 2 | feature-dev:feature-dev, frontend-developer | code-reviewer |
| 3 | feature-dev:feature-dev, ai-engineer | code-reviewer |
| 4 | feature-dev:feature-dev, performance-engineer | code-reviewer + security-sast |

---

## Appendix: Component Mockups

### Command Center Layout
```
┌─────────────────────────────────────────────────────────────┐
│  AI COMMAND CENTER                          [Enrich All]    │
├────────────────────────┬────────────────────────────────────┤
│  LEAD LIST (40%)       │  AI INSIGHTS PANEL (60%)          │
│  ┌──────────────────┐  │  ┌────────────────────────────┐   │
│  │ Command Comfort  │  │  │ PERSONAL HOOKS             │   │
│  │ Chris Parker     │  │  │ • Dogs: Burnt Bacon, Oreo  │   │
│  │ [Enrich] [Call]  │  │  │ • Former child actor       │   │
│  └──────────────────┘  │  ├────────────────────────────┤   │
│                        │  │ EMAIL DRAFT                │   │
│                        │  │ [Edit] [Regenerate] [Send] │   │
│                        │  ├────────────────────────────┤   │
│                        │  │ SMS DRAFT                  │   │
│                        │  │ [Edit] [Send]              │   │
│                        │  ├────────────────────────────┤   │
│                        │  │ VOICE SCRIPT               │   │
│                        │  │ [Copy to Clipboard]        │   │
│                        │  └────────────────────────────┘   │
└────────────────────────┴────────────────────────────────────┘
```

### Draft Queue Layout
```
┌─────────────────────────────────────────────────────────────┐
│  DRAFT QUEUE                       [Approve All] [Filters]  │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │ EMAIL - Command Comfort (Chris Parker)               │  │
│  │ Subject: Quick question about your Mitsubishi setup  │  │
│  │ AI Confidence: 87% | Generated: 2 min ago            │  │
│  │ [Edit] [Regenerate] [Approve & Send] [Discard]       │  │
│  └───────────────────────────────────────────────────────┘  │
│  ┌───────────────────────────────────────────────────────┐  │
│  │ SMS - Arundel Cooling (John Smith)                   │  │
│  │ Characters: 142/160 | Confidence: 92%                │  │
│  │ [Edit] [Regenerate] [Send via Close] [Discard]       │  │
│  └───────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```
