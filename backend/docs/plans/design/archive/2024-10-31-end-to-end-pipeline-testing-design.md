# End-to-End Pipeline Testing System

**Date**: October 31, 2024
**Status**: Design Approved
**Goal**: Test the complete lead processing pipeline with 200 real prospects

## Problem

We built six agents (Qualification, Enrichment, Growth, Marketing, BDR, Conversation) and a Close CRM integration with deduplication. We must verify the pipeline works with real leads before production use.

We have 200 high-quality prospects (ICP scores 60-100) from dealer-scraper-mvp. These leads include company names, phone numbers, websites, OEM certifications, and industry signals.

## Requirements

**Functional:**
- Process one lead through all pipeline stages manually
- Measure accuracy, performance, data flow, error handling
- Import leads from CSV with minimal transformation
- Halt on duplicates to protect CRM data

**Non-Functional:**
- Qualification: <1000ms, ~$0.000006 per lead
- Enrichment: <3000ms, ~$0.00027 per lead
- Deduplication: <100ms, $0 (in-memory)
- Close CRM: <2000ms, ~$0.00027 per lead
- Total pipeline: <5000ms, <$0.002 per lead

## Solution: Pipeline Orchestration API

### Architecture

Create a FastAPI endpoint that orchestrates the four-stage pipeline:

```
CSV Lead → Qualification → Enrichment → Deduplication → Close CRM
```

Each stage runs sequentially. The pipeline halts if a lead fails qualification or matches an existing contact.

### API Design

**Endpoint:**
```
POST /api/leads/test-pipeline
```

**Request:**
```json
{
  "lead": {
    "name": "A & A GENPRO INC.",
    "email": "contact@aagenpro.com",
    "phone": "(713) 830-3280",
    "company": "A & A GENPRO INC.",
    "website": "https://www.aagenpro.com/",
    "icp_score": 72.8,
    "oem_certifications": ["Generac", "Cummins"]
  },
  "options": {
    "stop_on_duplicate": true,
    "skip_enrichment": false,
    "create_in_crm": true,
    "dry_run": false
  }
}
```

**Response:**
```json
{
  "success": true,
  "total_latency_ms": 4250,
  "total_cost_usd": 0.002014,
  "stages": {
    "qualification": {
      "status": "success",
      "latency_ms": 633,
      "cost_usd": 0.000006,
      "output": {"score": 72, "tier": "high_value"}
    },
    "enrichment": {
      "status": "success",
      "latency_ms": 2450,
      "cost_usd": 0.00027,
      "output": {"email": "found@...", "linkedin": "..."}
    },
    "deduplication": {
      "status": "no_duplicate",
      "latency_ms": 45,
      "confidence": 0.0
    },
    "close_crm": {
      "status": "created",
      "latency_ms": 1122,
      "cost_usd": 0.00027,
      "lead_id": "lead_abc123"
    }
  }
}
```

### Pipeline Flow

**Stage 1: Qualification (Cerebras)**
- Input: Company name, industry signals, ICP data
- Agent: QualificationAgent with Cerebras (633ms target)
- Output: Qualification score (0-100)
- Decision: Score < 60 → Reject and halt

**Stage 2: Enrichment (Apollo + LinkedIn)**
- Input: Company name, domain, LinkedIn URL
- Agent: EnrichmentAgent with Apollo API + LinkedIn scraping
- Output: Email, contact name, company details
- Decision: Continue regardless (enrichment failure is non-blocking)

**Stage 3: Deduplication**
- Input: Email, phone, company name from enrichment
- Engine: DeduplicationEngine with multi-field matching
- Output: Duplicate confidence (0-100%)
- Decision: Confidence >= 85% → Flag duplicate and halt (if stop_on_duplicate=true)

**Stage 4: Close CRM Creation (DeepSeek)**
- Input: Enriched lead data
- Agent: CloseCRMAgent with DeepSeek provider
- Output: Close CRM lead ID
- Decision: Success → Complete, Failure → Report error

### Error Handling

**Non-Blocking Errors:**
- Qualification failure → Use default score (50) and continue
- Enrichment failure → Use CSV data only and continue

**Blocking Errors:**
- Duplicate with stop_on_duplicate=true → Halt with warning
- Close CRM API failure → Halt with error

All errors return detailed messages with stage, error type, and recovery suggestions.

### CSV Integration

**CSV Importer:**
```python
class LeadCSVImporter:
    def __init__(self, csv_path: str):
        self.df = pd.read_csv(csv_path)

    def get_lead(self, index: int) -> Dict:
        """Extract lead at index (0-199)"""
        row = self.df.iloc[index]
        return {
            "name": row["name"],
            "phone": row["phone"],
            "domain": row["domain"],
            "website": row["website"],
            "email": row.get("email"),
            "icp_score": row["ICP_Score"],
            "oem_certifications": row["OEMs_Certified"].split(", ")
        }
```

**Test Endpoints:**
```
# Single lead by index
GET /api/leads/test-pipeline/quick?csv_path=...&lead_index=0

# Batch processing (future)
POST /api/leads/test-pipeline/batch
{
  "csv_path": "...",
  "start_index": 0,
  "batch_size": 10
}
```

### Observability

**Metrics Tracked:**
- Latency per stage (milliseconds)
- Cost per stage (USD)
- Token usage for LLM calls
- Cache hit/miss rates
- Error counts by type

**Database Logging:**
- Table: `pipeline_test_executions`
- Fields: lead_name, stages_json, total_latency_ms, total_cost_usd, success, created_at
- Indexed by: lead_name, created_at, success

**Timeline Visualization:**
```json
"timeline": [
  {"stage": "qualification", "start": 0, "end": 633},
  {"stage": "enrichment", "start": 633, "end": 3083},
  {"stage": "deduplication", "start": 3083, "end": 3128},
  {"stage": "close_crm", "start": 3128, "end": 4250}
]
```

## Implementation Plan

**Phase 1: Core Endpoint (1-2 hours)**
- Create `/api/leads/test-pipeline` endpoint
- Implement PipelineOrchestrator class
- Wire up four agents in sequence
- Add basic error handling

**Phase 2: CSV Integration (30 min)**
- Build LeadCSVImporter utility
- Add GET endpoint for quick testing
- Test with first lead from top_200 CSV

**Phase 3: Observability (1 hour)**
- Add pipeline_test_executions table
- Log all executions with timing/cost data
- Return detailed stage-by-stage results

**Phase 4: Manual Testing (1 hour)**
- Test lead index 0: "A & A GENPRO INC." (ICP: 72.8, GOLD tier)
- Verify all four success criteria
- Document results and issues

**Phase 5: Batch Preparation (optional)**
- Add batch endpoint for 10/50/200 lead tests
- Implement rate limiting and retry logic
- Add progress tracking

## Success Criteria

**Accuracy:**
- Qualification scores match expected ICP tiers
- Enrichment finds valid emails (>80% success rate)
- Deduplication catches test duplicates (100% accuracy)
- Close CRM creates leads with complete data

**Performance:**
- Qualification: <1000ms ✓
- Enrichment: <3000ms ✓
- Deduplication: <100ms ✓
- Close CRM: <2000ms ✓
- Total: <5000ms ✓

**Data Flow:**
- Enrichment data reaches Close CRM
- No data loss between stages
- All fields populated correctly

**Error Handling:**
- Missing email doesn't crash pipeline
- API failures return clear errors
- Duplicate detection prevents CRM pollution

## Testing Approach

**Initial Test:**
1. Start server: `python start_server.py`
2. Load first lead: `GET /api/leads/test-pipeline/quick?lead_index=0`
3. Observe each stage output
4. Verify timing and cost metrics
5. Check Close CRM for created lead

**Iterative Testing:**
- Test leads 0-4 individually (top 5 prospects)
- Verify different ICP scores (GOLD, SILVER tiers)
- Test missing email scenario (lead without email)
- Test duplicate scenario (import same lead twice)

## Files to Create

```
backend/
├── app/
│   ├── api/
│   │   └── test_pipeline.py          # New endpoint
│   └── services/
│       ├── pipeline_orchestrator.py  # New orchestrator
│       └── csv_importer.py           # New CSV utility
└── tests/
    └── api/
        └── test_pipeline.py          # Endpoint tests
```

## Dependencies

**Existing:**
- QualificationAgent (cerebras)
- EnrichmentAgent (apollo, linkedin)
- DeduplicationEngine (multi-field matching)
- CloseCRMAgent (deepseek)

**New:**
- pandas (CSV parsing) - already installed
- pipeline_test_executions table migration

## Risks & Mitigations

**Risk: API rate limits (Apollo 600/hr, LinkedIn 100/day)**
- Mitigation: Test with 1 lead first, then batch slowly

**Risk: Duplicate leads polluting Close CRM**
- Mitigation: Use stop_on_duplicate=true, test in dev environment first

**Risk: Missing emails cause enrichment failures**
- Mitigation: Enrichment is non-blocking, uses CSV email as fallback

**Risk: Pipeline too slow (>5s per lead)**
- Mitigation: Agents already optimized, can parallelize enrichment if needed

## Future Enhancements

- Batch processing with progress tracking
- A/B testing different agent configurations
- Cost optimization recommendations
- Automated quality scoring
- CSV export of results for analysis

---

**Next Steps:**
1. Review and approve this design
2. Set up git worktree for isolated development
3. Create implementation plan with detailed tasks
4. Begin Phase 1: Core endpoint implementation
