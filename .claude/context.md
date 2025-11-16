# Project Context: Sales-Agent - Social Intelligence System

**Last Updated:** 2025-11-16T12:30:00Z

## Current Sprint Focus: Social Intelligence Infrastructure (Week 1)
- **Status**: ✅ Week 1 Infrastructure 100% COMPLETE
- **Branch**: `feature/social-intelligence`
- **Latest Commit**: `c4b4b53` - Social intelligence infrastructure files
- **Working Directory**: `.worktrees/social-intelligence/backend`

### Week 1 Achievements - Infrastructure Setup (COMPLETE ✅)
- ✅ **Supabase Database**: 4 tables (social_posts, contact_monitoring, email_drafts, email_engagement)
- ✅ **Close CRM Integration**: Custom Activity Type "Social Intelligence" created
- ✅ **Custom Field Created Manually**: "High Intent Flag" (cf_6lDArzDCbc6g92tqTPpcllDOptB8TbD6AcyCae6m2Gr)
- ✅ **Smart View Created**: "🔥 High-Intent ATL Contacts (3+ Opens)" (save_nDlCJyxbfAj9MNX4xhloQWuh0srWpBrzg0OUaNmdend)
- ✅ **Docker Infrastructure**: Dockerfile.serverless + requirements-serverless.txt
- ✅ **GitHub Actions**: Automated Docker builds configured (.github/workflows/social-intelligence.yml)
- ✅ **Cleanup Script**: Duplicate smart view remover
- ✅ **Setup Scripts**: create_smart_view.py, setup_close_social_intelligence.py
- ✅ **RunPod CLI**: Installed and authenticated
- ✅ **RunPod Template**: Created (ynttskho0t) - Docker image + environment variables
- ✅ **RunPod Endpoint**: Created (s6m25m225cuq1h) - AMPERE_16 GPU, 0-1 workers, 5s idle timeout
- ✅ **GitHub Secrets**: All 4 secrets configured (RUNPOD_ENDPOINT_ID, RUNPOD_API_KEY, SUPABASE_DATABASE_URL, CLOSE_API_KEY)

### Week 1 Complete - Ready for Week 2
All infrastructure tasks completed. System is ready for core service development.

### Next Week Goals (Week 2 - Core Services)
- [ ] LinkedIn scraper with Playwright (~4-6 hours)
- [ ] Twitter/X monitor service (~3-4 hours)
- [ ] AI analyzer (DeepSeek + Claude tiering) (~4-6 hours)
- [ ] Email draft generator (~3-4 hours)
- [ ] Email engagement tracker (~2-3 hours)

## Architecture Overview
- **Platform**: Serverless (RunPod + GitHub Actions)
- **Database**: Supabase PostgreSQL (500MB free tier)
- **CRM**: Close CRM (bidirectional sync)
- **Scraping**: Playwright (LinkedIn) + Tweepy (Twitter/X)
- **AI**: DeepSeek (simple analysis), Claude Sonnet 4 (complex)
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
- **Social Intelligence Infrastructure**: Week 1 Setup (70% complete)
  - ✅ Supabase database schema (185 lines SQL)
  - ✅ Close CRM custom field + activity type + smart view
  - ✅ Docker + GitHub Actions for serverless deployment
  - ✅ Setup and cleanup scripts
  - ⏸️ RunPod CLI installation (pending)
  - ⏸️ GitHub Secrets configuration (pending)

## Current Blockers
- None. Infrastructure setup on track. Lunch break before completing RunPod deployment.

## Next Steps
1. **RunPod CLI Installation**: Install CLI tool and authenticate with API key
2. **Serverless Endpoint Creation**: Deploy Docker image to RunPod
3. **GitHub Secrets**: Configure RUNPOD_API_KEY, SUPABASE_DATABASE_URL, CLOSE_API_KEY
4. **Week 1 Review**: Verify all infrastructure components working
5. **Week 2 Start**: Begin LinkedIn scraper development

## Development Workflow
```bash
# Social Intelligence Development (Current)
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/social-intelligence/backend
source ../../../venv/bin/activate

# Test Supabase connection
python test_supabase_connection.py

# Run Close CRM setup (if needed)
python setup_close_social_intelligence.py

# Create Smart View (one-time, already done)
python create_smart_view.py

# Clean up duplicate smart views (if needed)
python cleanup_duplicate_smart_views.py

# Check git status
git status
git log --oneline -10
```

## Key Files for Social Intelligence
- `backend/supabase_schema.sql` - Database schema (4 tables, views, indexes)
- `backend/test_supabase_connection.py` - Connection verification
- `backend/setup_close_social_intelligence.py` - Close CRM configuration
- `backend/create_smart_view.py` - Smart View creation with custom field
- `backend/cleanup_duplicate_smart_views.py` - Utility to remove duplicates
- `backend/Dockerfile.serverless` - RunPod container definition
- `backend/requirements-serverless.txt` - Python dependencies
- `.github/workflows/build-docker.yml` - Automated builds
- `docs/plans/2025-11-16-social-intelligence-serverless.md` - Architecture design (500+ lines)
- `IMPLEMENTATION_PLAN.md` - 4-week roadmap (30 tasks)
- `SETUP_GUIDE.md` - Step-by-step setup instructions

## Environment Variables (`.env`)
```env
# Supabase Database
SUPABASE_DATABASE_URL="postgresql://postgres.[PROJECT_REF]:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:6543/postgres"

# Close CRM
CLOSE_API_KEY=api_***  # Located in .env file
CLOSE_DEFAULT_OWNER_USER_ID=user_***  # Tim Kipper's user ID
CLOSE_STATUS_HOT_ATL=stat_***  # Hot ATL status ID
CLOSE_STATUS_VALIDATED_ATL=stat_***  # Validated ATL status ID

# RunPod (to be added)
RUNPOD_API_KEY=rpa_***  # Located in .env file

# AI Providers
ANTHROPIC_API_KEY=sk-ant-***  # Located in .env file
DEEPSEEK_API_KEY=sk-***  # Located in .env file
OPENROUTER_API_KEY=sk-or-***  # Located in .env file
```

**Note**: All actual API keys are stored in `.env` file (never committed to git).

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

## Notes
- **Part of GTM Engineer Strategy**: Located at `tmkipper/desktop/tk_projects/gtm_engineer_strategy`
- **Design Pattern**: Serverless event-driven architecture
- **Cost Efficient**: $17/month vs $72/month dedicated pod (78% savings)
- **Free Tier**: Supabase (500MB), GitHub Actions, Upstash Redis
- **Git Worktrees**: Using isolated worktree for feature branch isolation
- **Manual Steps**: Custom field creation required manual setup (API restrictions on Close CRM plan)
- **Duplicate Smart Views**: Cleanup script created to handle accidental duplicates
- **Next Deployment**: RunPod CLI + GitHub Secrets configuration
