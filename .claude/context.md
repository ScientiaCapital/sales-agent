```markdown
# Project Context: Sales-Agent

**Last Updated:** 2025-10-31T17:30:00Z

## Current Sprint Focus
- **Pipeline Testing System**: End-to-end testing infrastructure for 200-lead validation
- **Close CRM Integration**: Bidirectional sync with deduplication complete (Phase 5)
- **Performance Validation**: Real-world throughput testing with dealer-scraper dataset
- **Production Readiness**: Database models, schemas, and CSV importer operational

## Architecture Overview
- **Language**: Python 3.13
- **Framework**: FastAPI (web), LangGraph (agent orchestration)
- **Type**: AI/ML Sales Automation Platform
- **Database**: PostgreSQL (primary), Redis (checkpointing/caching)
- **Inference**: Cerebras for ultra-fast model execution

## Project Description
Enterprise-grade sales automation platform with sophisticated multi-agent AI system. Six specialized agents handle qualification, enrichment, growth analysis, marketing campaigns, BDR workflows, and voice conversations. Achieves 633ms lead qualification using hybrid LangGraph architecture and Cerebras inference. Designed for high-throughput enterprise sales with real-time streaming and comprehensive CRM integrations.

## Recent Changes
- **Phase 5 Complete**: Close CRM integration with probabilistic deduplication (fuzzy matching + confidence scoring)
- **Phase 6 In Progress**: Pipeline testing system development
  - ✅ Database model (PipelineTestExecution) with per-stage metrics
  - ✅ Pydantic schemas (PipelineTestRequest, PipelineTestResponse, CSVLeadImportRequest)
  - ✅ CSV lead importer with field mapping (200 dealer-scraper prospects)
  - 🚧 Pipeline orchestrator service (pending)
  - 🚧 API endpoints (pending)
  - 🚧 Manual testing with real leads (pending)

## Current Blockers
- None identified - pipeline testing on track for completion

## Next Steps
1. **Complete Pipeline Testing** (3/6 tasks remaining): Orchestrator, API endpoints, manual validation
2. **Scale Testing**: Load test with full 200-lead dataset
3. **Performance Optimization**: Reduce enrichment latency under heavy load
4. **Monitoring Dashboard**: Real-time pipeline metrics and cost tracking
5. **CRM Expansion**: Salesforce, HubSpot connectors beyond Close

## Development Workflow
```bash
# Pipeline Testing Development (Current)
cd backend
source venv/bin/activate
docker-compose up -d
python start_server.py

# Test CSV Importer
pytest tests/services/test_csv_lead_importer.py -v

# Test Pipeline Models
pytest tests/models/test_pipeline_models.py -v

# Manual Pipeline Test (After completion)
curl -X POST http://localhost:8001/api/leads/test-pipeline \
  -H "Content-Type: application/json" \
  -d '{"csv_path": "/path/to/dealers.csv", "lead_index": 0}'
```

## Notes
- **Part of GTM Engineer Strategy**: Located at `tmkipper/desktop/tk_projects/gtm_engineer_strategy`
- **Design Patterns**: Factory, Abstract Base Class, Circuit Breaker, TDD (Test-Driven Development)
- **Performance Critical**: All agents have strict latency SLAs (633ms-5000ms range)
- **Cost Efficient**: Ultra-low cost per request ($0.000006 for qualification)
- **Git Worktrees**: Using isolated worktree for pipeline-testing feature branch
- **Test Coverage**: 96% overall, 100% for new pipeline testing components
```
