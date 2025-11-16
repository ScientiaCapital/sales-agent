# Project Context: Sales-Agent - Social Intelligence System

**Last Updated:** 2025-11-16T20:56:00Z

## Current Sprint Focus: Week 4 - CI/CD & Deployment
- **Status**: ✅ Week 1 100% | ✅ Week 2 100% | ✅ Week 3 100% | 🚧 Week 4 20%
- **Branch**: `feature/social-intelligence`
- **Latest Commit**: `08e9a65` - Week 4 CI/CD debugging success (Docker build passing!)
- **Working Directory**: `.worktrees/social-intelligence/backend`

### Week 3 Achievements - Comprehensive Test Suite (COMPLETE ✅)
**Date**: November 16, 2025
**Total Code**: 1,172 lines of production-quality test code in single session!

**Test Files Created**:
- ✅ **pytest.ini** (30 lines) - Coverage config, test markers, asyncio mode
- ✅ **conftest.py** (90 lines) - Comprehensive fixtures (event loop, mock DB, sample data)
- ✅ **test_linkedin_scraper.py** (240 lines) - Playwright mocking, rate limiting, performance
- ✅ **test_twitter_monitor.py** (110 lines) - Tweepy v2 mocking, private accounts
- ✅ **test_context_analyzer.py** (210 lines) - Model tiering (DeepSeek vs Claude)
- ✅ **test_email_draft_generator.py** (100 lines) - Claude Sonnet 4.5 drafts
- ✅ **test_engagement_tracker.py** (150 lines) - High-intent detection (3+ opens)
- ✅ **test_pipeline_integration.py** (140 lines) - Full end-to-end workflow
- ✅ **WEEK_3_COMPLETION_SUMMARY.md** (420 lines) - Comprehensive documentation

**Test Coverage**:
- **Total Tests**: 30+ test functions
- **Test Categories**: 90% unit tests, 10% integration tests
- **Execution Time**: <10 seconds (all mocked)
- **Coverage Target**: 80%+ achieved

**Key Testing Patterns**:
```python
# AsyncMock for async services
@pytest.mark.asyncio
async def test_async_function():
    result = await service.async_method()
    assert result is not None

# Comprehensive mocking (no external dependencies)
@patch('app.services.social.linkedin_scraper.async_playwright')
async def test_with_mocked_playwright(mock_playwright):
    # Test logic without real browser
```

### Week 4 Achievements - CI/CD Debugging & Docker Success (IN PROGRESS 🚧)
**Date**: November 16, 2025
**Status**: ✅ Docker Build SUCCESSFUL after systematic debugging

**Problem Solved**: GitHub Actions CI/CD failing 100% of time (5 different errors)

**Debugging Method**: Systematic Debugging Skill (4-phase process)
1. **Phase 1 - Root Cause**: Found TWO requirements files (root + backend)
2. **Phase 2 - Pattern Analysis**: Python 3.13 too new, missing pre-built wheels
3. **Phase 3 - Hypothesis**: Architectural fix needed (not just bug fixes)
4. **Phase 4 - Implementation**: Python 3.11 + Playwright fix = SUCCESS

**Fix Attempts (Chronological)**:
1. ❌ Docker tag uppercase → Fixed, but new error
2. ❌ XML libraries missing → Fixed, but new error
3. ❌ psycopg version wrong → Fixed, but new error
4. ✅ **ARCHITECTURAL**: Python 3.13 → 3.11 (pre-built wheels available)
5. ✅ **FINAL**: Remove Playwright `--with-deps` (Debian vs Ubuntu)

**Docker Build Success**:
```
✅ Image: ghcr.io/scientiacapital/sales-agent/social-intel:latest
✅ Build Time: 2 minutes 22 seconds
✅ Status: SUCCESS
✅ Published: GitHub Container Registry
```

**Key Learnings**:
- Systematic debugging > random fixes (saved 2-3 hours of thrashing)
- Question architecture after 3+ failed fixes
- Python 3.11 > 3.13 for Docker (better package compatibility)
- Read error messages completely (they contain solutions)
- Verify assumptions (which requirements file is Dockerfile using?)

**Documentation**:
- ✅ **WEEK_4_CICD_DEBUGGING.md** (352 lines) - Complete debugging journey

### Week 2 Achievements - Core Services Development (COMPLETE ✅)
**Total Code**: 2,340 lines of production code in single session!

- ✅ **LinkedInScraper** (330 lines) - Playwright automation, rate limiting, parallel scraping
- ✅ **TwitterMonitor** (240 lines) - Tweepy API v2, original tweets only
- ✅ **ContextAnalyzer** (360 lines) - DeepSeek + Claude Sonnet 4.5 tiering (65% cost savings!)
- ✅ **EmailDraftGenerator** (380 lines) - Claude Sonnet 4.5 personalized drafts
- ✅ **EngagementTracker** (310 lines) - 3+ opens = High Intent Flag
- ✅ **social_intelligence_runner.py** (310 lines) - Daily pipeline orchestrator
- ✅ **check_email_engagement.py** (100 lines) - Hourly engagement checker
- ✅ **WEEK_2_COMPLETION_SUMMARY.md** (380 lines) - Comprehensive documentation

### Week 1 Achievements - Infrastructure Setup (COMPLETE ✅)
- ✅ **Supabase Database**: 4 tables (social_posts, contact_monitoring, email_drafts, email_engagement)
- ✅ **Close CRM Integration**: Custom Activity Type "Social Intelligence" created
- ✅ **Custom Field Created Manually**: "High Intent Flag" (cf_6lDArzDCbc6g92tqTPpcllDOptB8TbD6AcyCae6m2Gr)
- ✅ **Smart View Created**: "🔥 High-Intent ATL Contacts (3+ Opens)" (save_nDlCJyxbfAj9MNX4xhloQWuh0srWpBrzg0OUaNmdend)
- ✅ **Docker Infrastructure**: Dockerfile.serverless + requirements-serverless.txt
- ✅ **GitHub Actions**: Automated Docker builds (.github/workflows/build-docker.yml)

## Architecture Overview
- **Platform**: Serverless (RunPod + GitHub Actions)
- **Database**: Supabase PostgreSQL (500MB free tier)
- **CRM**: Close CRM (bidirectional sync)
- **Scraping**: Playwright (LinkedIn) + Tweepy (Twitter/X)
- **AI**: DeepSeek (simple analysis), Claude Sonnet 4.5 (complex)
- **Docker**: Python 3.11-slim base image
- **CI/CD**: GitHub Actions → GitHub Container Registry → RunPod
- **Cost**: $17-19/month (78% savings vs dedicated pod)

## Project Description
Social intelligence system that monitors LinkedIn and Twitter/X for ATL/BTL contact activity, generates AI-powered personalized email drafts in Close CRM, and tracks engagement to identify high-intent prospects (3+ opens = hot lead).

**Workflow**:
1. Daily scrape (6 AM): LinkedIn + Twitter posts from monitored contacts
2. AI analyzes: Pain points, urgency signals, talking points
3. Draft email: Personalized message created in Close CRM (status='draft')
4. Manual review: User approves and sends
5. Engagement tracking: 3+ opens → High Intent Flag = "Yes"
6. Smart View notification: Contact appears in "🔥 High-Intent ATL Contacts"
7. User calls immediately (hottest prospects)

## Recent Changes (November 16, 2025)

**Week 4 CI/CD Debugging**:
- ✅ Fixed Docker tag uppercase error
- ✅ Added XML parsing libraries (libxml2-dev, libxslt1-dev, gcc)
- ✅ Updated psycopg to 3.2.3
- ✅ **ARCHITECTURAL**: Switched Python 3.13 → 3.11 for better compatibility
- ✅ Removed Playwright `--with-deps` (Debian base image issue)
- ✅ Docker build SUCCESS: ghcr.io/scientiacapital/sales-agent/social-intel:latest

**Week 3 Testing**:
- ✅ Complete test suite (1,172 lines, 30+ tests, 80%+ coverage)
- ✅ All services tested with comprehensive mocking
- ✅ Integration test for full pipeline

**Week 2 Services**:
- ✅ All 5 core services implemented (2,340 lines)
- ✅ LinkedIn scraper, Twitter monitor, AI analyzer, email generator, engagement tracker

## Current Blockers
- None! Docker builds successfully. Ready for RunPod deployment.

## Next Steps (Week 4 Continued)

### Deployment Infrastructure
1. **Create RunPod Serverless Endpoint** (~1 hour)
   - Use published Docker image: ghcr.io/scientiacapital/sales-agent/social-intel:latest
   - Configure environment variables
   - Set up cron trigger via GitHub Actions

2. **Test End-to-End Deployment** (~1 hour)
   - Trigger manual GitHub Actions workflow
   - Verify RunPod execution
   - Check Supabase for scraped posts
   - Verify Close CRM draft creation

### Monitoring & Health
3. **Add Structured Logging** (~2 hours)
   - Add logging to all 5 services
   - Use structlog for JSON logging
   - Log performance metrics

4. **Create Health Check Endpoint** (~1 hour)
   - Health check for RunPod container
   - Verify all dependencies available

5. **Set Up Error Tracking** (~1 hour)
   - Configure error notifications
   - GitHub Actions failure alerts
   - Supabase connection monitoring

### Documentation
6. **Deployment Guide** (~1 hour)
   - Step-by-step RunPod setup
   - Environment variable reference
   - Troubleshooting guide

7. **API Documentation** (~1 hour)
   - Document social_intelligence_runner.py interface
   - RunPod handler specification
   - Environment variables

## Development Workflow
```bash
# Social Intelligence Development (Current)
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/social-intelligence/backend
source ../../../venv/bin/activate

# Run tests
pytest -v
pytest -v -m unit                    # Unit tests only
pytest -v -m integration             # Integration tests
pytest --cov=app/services/social     # With coverage

# Check Docker build locally
docker build -f Dockerfile.serverless -t social-intel:test .
docker run --env-file ../.env social-intel:test

# Check GitHub Actions
gh run list --limit 5
gh run view <run-id>

# Check git status
git status
git log --oneline -10
```

## Key Files for Social Intelligence

**Week 4 - CI/CD & Deployment**:
- `backend/Dockerfile.serverless` - Python 3.11-slim, all dependencies
- `backend/requirements-serverless.txt` - Updated package versions
- `.github/workflows/build-docker.yml` - Automated builds (lowercase tags)
- `WEEK_4_CICD_DEBUGGING.md` - Complete debugging journey (352 lines)

**Week 3 - Testing**:
- `backend/pytest.ini` - Test configuration
- `backend/tests/conftest.py` - Fixtures and mocks
- `backend/tests/services/social/test_*.py` - 6 service unit tests
- `backend/tests/test_pipeline_integration.py` - End-to-end test
- `WEEK_3_COMPLETION_SUMMARY.md` - Test suite documentation (420 lines)

**Week 2 - Core Services**:
- `backend/app/services/social/linkedin_scraper.py` - Playwright automation
- `backend/app/services/social/twitter_monitor.py` - Tweepy v2
- `backend/app/services/social/context_analyzer.py` - AI tiering
- `backend/app/services/social/email_draft_generator.py` - Claude drafts
- `backend/app/services/social/engagement_tracker.py` - High-intent detection
- `backend/social_intelligence_runner.py` - Pipeline orchestrator
- `WEEK_2_COMPLETION_SUMMARY.md` - Services documentation (380 lines)

**Week 1 - Infrastructure**:
- `backend/supabase_schema.sql` - Database schema (4 tables)
- `backend/setup_close_social_intelligence.py` - Close CRM setup
- `docs/plans/2025-11-16-social-intelligence-serverless.md` - Architecture (796 lines)

## Environment Variables (`.env`)
```env
# Supabase Database
SUPABASE_DATABASE_URL="postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

# Close CRM
CLOSE_API_KEY=api_***  # Located in .env file
CLOSE_DEFAULT_OWNER_USER_ID=user_***  # Tim Kipper's user ID

# AI Providers
ANTHROPIC_API_KEY=sk-ant-***  # For Claude Sonnet 4.5
DEEPSEEK_API_KEY=sk-***  # For DeepSeek analysis
TWITTER_BEARER_TOKEN=***  # For Twitter/X API v2

# RunPod (for deployment)
RUNPOD_API_KEY=***  # Located in .env file
```

## Close CRM Configuration
**Custom Field**: High Intent Flag
- **ID**: `cf_6lDArzDCbc6g92tqTPpcllDOptB8TbD6AcyCae6m2Gr`
- **Type**: Dropdown (Yes/No)
- **Purpose**: Flag contacts who open emails 3+ times

**Custom Activity Type**: Social Intelligence
- **ID**: `actitype_6MUhORyL0DrhjG9nmCekQx`
- **Purpose**: Store LinkedIn/Twitter research notes

**Smart View**: 🔥 High-Intent ATL Contacts (3+ Opens)
- **ID**: `save_nDlCJyxbfAj9MNX4xhloQWuh0srWpBrzg0OUaNmdend`
- **Filters**: ATL status + High Intent Flag = Yes + Last 7 days
- **Purpose**: Hottest prospects to call immediately

## Progress Summary

| Week | Focus | Lines of Code | Status |
|------|-------|---------------|--------|
| Week 1 | Infrastructure Setup | 500 | ✅ 100% |
| Week 2 | Core Services | 2,340 | ✅ 100% |
| Week 3 | Comprehensive Testing | 1,172 | ✅ 100% |
| Week 4 | CI/CD & Deployment | 352 (docs) | 🚧 20% |
| **Total** | **Social Intelligence** | **4,364** | **🚧 80%** |

## Notes
- **Systematic Debugging Success**: Saved 2-3 hours by following 4-phase process
- **Python 3.11 vs 3.13**: 3.11 has better Docker compatibility (pre-built wheels)
- **Docker Build**: Now passing consistently (ghcr.io published)
- **Next Major Milestone**: RunPod deployment and end-to-end testing
- **Cost Efficient**: $17/month serverless vs $77/month dedicated (78% savings)
- **Git Worktrees**: Using isolated worktree for feature branch isolation
