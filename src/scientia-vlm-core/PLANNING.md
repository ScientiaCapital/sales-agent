# VLM-AI-Core Planning

## Overview
Enterprise-grade Vision Language Model services for construction AI, blueprint analysis, and document processing.

## Current Phase: Development

### Completed
- [x] Core VLM provider abstraction (BaseVLMProvider + ProviderRegistry)
- [x] OpenRouter integration (Qwen 2.5 VL, Qwen 3 VL, GLM-4.6V)
- [x] Gemini Vision integration (2.0 Flash, 2.5 Flash/Pro, 3.0 Flash)
- [x] Claude Vision integration (Sonnet 4, Opus 4, Haiku 3.5)
- [x] Image preprocessing pipeline (29 unit tests)
- [x] lang-core integration
- [x] Cost tracking per image (full runtime in shared/audit/)
- [x] 344-test investor audit (11.8x cost advantage validated)
- [x] 14 vision models cataloged with pricing
- [x] **Blueprint analysis runtime** (VLM + hash + cache + confidence)
  - AnalysisCache with Supabase (7-day TTL)
  - Trade-specific prompts (7 trades)
  - BlueprintAnalyzer pipeline orchestrator
  - Routes.py /analyze endpoint wired up
- [x] **TDD unit test coverage** (138 tests total)
  - Provider tests: 99 tests (OpenRouter, Anthropic, Gemini)
  - Analysis tests: 39 tests (cache, prompts, analyzer)

### In Progress
- [ ] Multi-page PDF processing (NOT STARTED: needs PyMuPDF)

### Next Steps
- [ ] PyMuPDF integration for PDF page extraction
- [ ] RAG similarity search for cache augmentation
- [ ] ROI detection and re-analysis
- [ ] Batch image analysis optimization

## Architecture

### Provider Priority (Cost-Optimized)
1. **OpenRouter Chinese VLMs** - Cost leader ($0.12-$0.73/1M tokens)
   - Qwen 3 VL 30B, Qwen 2.5 VL 72B, GLM-4.6V
2. **Gemini Vision** - Balanced cost/quality ($0.075-$2.00/1M tokens)
   - Gemini 2.0/2.5/3.0 Flash, Gemini 2.5 Pro
3. **Anthropic Claude** - Western baseline for accuracy validation ($1-$75/1M tokens)
   - Claude Sonnet 4, Opus 4, Haiku 3.5

### Processing Pipeline
```
Image Upload → Hash → Cache Check → [Hit? Return] → VLM Analysis → Confidence → Cache Store → Response
```

## Integration Points
- FieldVault AI: Blueprint analysis
- Construction estimating: Material takeoffs
- Quality inspection: Defect detection
