# VLM-AI-Core Current Tasks

## Active Sprint (2025-12-24)

### In Progress
- [ ] Multi-page PDF with PyMuPDF (NOT STARTED)

### Up Next
- [ ] RAG similarity search integration
- [ ] ROI detection and re-analysis
- [ ] Batch image analysis optimization
- [ ] Construction material detection

## Recently Completed (Today)
- [x] Blueprint analysis runtime implementation (36c8f92)
  - AnalysisCache with Supabase (cache.py)
  - Trade-specific prompts (prompts.py)
  - BlueprintAnalyzer pipeline (analyzer.py)
  - Wired up in routes.py /analyze endpoint
- [x] TDD unit tests for analysis service (39 tests)
- [x] Provider unit tests (99 tests) - 79d48e9

## Previously Completed
- [x] OpenRouter VLM integration (5 Chinese VLMs)
- [x] Gemini Vision provider (5 models)
- [x] Anthropic Vision provider (3 Claude models)
- [x] Cost tracking integration (calculate_cost + audit_analyze + AuditLogger)
- [x] Image preprocessing (resize, crop, format) - 29 unit tests
- [x] lang-core dependency added
- [x] 344-test investor audit (11.8x cost advantage validated)
- [x] 14 vision models cataloged with pricing

## Blocked
None

## Notes
- All 3 VLM providers COMPLETE (OpenRouter, Anthropic, Gemini)
- Blueprint runtime COMPLETE (VLM + hash + cache + confidence)
- 138 total unit tests passing
- PDF processing next priority (needs PyMuPDF)
