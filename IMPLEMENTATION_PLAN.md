# Social Intelligence System - Implementation Plan

**Feature Branch**: `feature/social-intelligence`
**Worktree Location**: `.worktrees/social-intelligence`
**Design Doc**: `backend/docs/plans/design/2025-11-16-social-intelligence-serverless.md`
**Estimated Timeline**: 4 weeks
**Owner**: Tim Kipper

---

## Implementation Phases

### **WEEK 1: Infrastructure Setup** (5 days)

#### Task 1.1: Supabase Database Setup
**Estimated Time**: 2 hours
**Dependencies**: None
**Deliverable**: Production database with schema

**Steps**:
1. Log into Supabase dashboard (existing account ✅)
2. Create new project: "sales-agent-social-intel"
3. Copy connection string from Settings → Database
4. Run SQL schema from design doc (Section: Supabase Database)
5. Create database migrations in `backend/alembic/versions/`
6. Test connection from local machine

**Verification**:
```bash
# Test Supabase connection
python -c "
import psycopg
conn = psycopg.connect('YOUR_SUPABASE_CONNECTION_STRING')
cur = conn.cursor()
cur.execute('SELECT COUNT(*) FROM social_posts')
print('✅ Database connected')
"
```

**Files Created**:
- `backend/alembic/versions/2025_11_17_social_intelligence_schema.py`
- `.env` updated with `SUPABASE_DATABASE_URL`

---

#### Task 1.2: Upstash Redis Setup (Optional)
**Estimated Time**: 1 hour
**Dependencies**: None
**Deliverable**: Redis cache for LinkedIn profiles

**Steps**:
1. Sign up at upstash.com (free tier)
2. Create Redis database (choose closest region)
3. Copy connection string
4. Update `.env` with `UPSTASH_REDIS_URL`
5. Test connection

**Verification**:
```python
import redis
r = redis.from_url('YOUR_UPSTASH_URL')
r.set('test', 'hello')
print(r.get('test'))  # Should print b'hello'
```

**Files Updated**:
- `.env` with Redis URL

---

#### Task 1.3: RunPod Serverless Endpoint Creation
**Estimated Time**: 3 hours
**Dependencies**: Task 1.1 complete
**Deliverable**: Serverless endpoint ready to deploy

**Steps**:
1. Install RunPod CLI: `pip install runpod`
2. Authenticate: `runpod config --api-key YOUR_API_KEY`
3. Create Dockerfile for serverless container
4. Build and push Docker image to GitHub Container Registry
5. Create RunPod endpoint with CLI
6. Test endpoint with simple "hello world" function

**Files Created**:
- `backend/Dockerfile.serverless`
- `backend/requirements-serverless.txt`
- `.github/workflows/build-docker.yml` (automated image builds)

**Verification**:
```bash
# Test RunPod endpoint
curl -X POST https://api.runpod.io/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": {"test": "hello"}}'
```

---

#### Task 1.4: GitHub Actions Workflow Setup
**Estimated Time**: 2 hours
**Dependencies**: Task 1.3 complete
**Deliverable**: Automated cron triggers working

**Steps**:
1. Create `.github/workflows/social-intelligence.yml`
2. Add GitHub Secrets (RunPod API key, endpoint ID, etc.)
3. Configure cron schedules (6 AM daily, hourly engagement)
4. Test manual trigger (`workflow_dispatch`)
5. Monitor first automated run

**Files Created**:
- `.github/workflows/social-intelligence.yml`

**GitHub Secrets to Add**:
- `RUNPOD_API_KEY`
- `RUNPOD_ENDPOINT_ID`
- `SUPABASE_DATABASE_URL`
- `CLOSE_API_KEY`
- `ANTHROPIC_API_KEY`
- `NOTIFICATION_EMAIL`

**Verification**:
- Manually trigger workflow from GitHub Actions UI
- Check RunPod logs for successful execution

---

#### Task 1.5: Close CRM Custom Fields & Smart Views
**Estimated Time**: 1 hour
**Dependencies**: None
**Deliverable**: Close CRM configured for social intelligence

**Steps**:
1. Create setup script: `backend/setup_social_intelligence.py`
2. Create custom field: "High Intent Flag" (boolean)
3. Create custom activity type: "Social Intelligence"
4. Create Smart View: "🔥 High-Intent ATL Contacts (3+ Opens)"
5. Run setup script against production Close CRM

**Files Created**:
- `backend/setup_social_intelligence.py`

**Verification**:
- Log into Close CRM web UI
- Check Custom Fields exist under Settings
- Check Smart View appears in sidebar

---

### **WEEK 2: Core Services Development** (5 days)

#### Task 2.1: LinkedIn Scraper Service
**Estimated Time**: 8 hours (2 days)
**Dependencies**: Task 1.1, 1.3 complete
**Deliverable**: Production-ready LinkedIn scraper

**Steps**:
1. Create `backend/app/services/social/linkedin_scraper.py`
2. Implement Playwright browser automation
3. Add login + session management
4. Implement post scraping logic (last 7 days)
5. Add respectful rate limiting (2-5 sec delays)
6. Add error handling for blocked accounts
7. Write unit tests
8. Test with 5 real LinkedIn profiles

**Files Created**:
- `backend/app/services/social/__init__.py`
- `backend/app/services/social/linkedin_scraper.py`
- `backend/tests/services/social/test_linkedin_scraper.py`

**Implementation Pseudocode**:
```python
class LinkedInScraper:
    async def scrape_recent_posts(self, contacts: List[Contact], days_back=7):
        posts = []
        for contact in contacts:
            profile = await self._visit_profile(contact.linkedin_url)
            recent_posts = await self._extract_posts(profile, days_back)
            posts.extend(recent_posts)
            await self._random_delay()  # 2-5 seconds
        return posts
```

**Verification**:
```bash
pytest tests/services/social/test_linkedin_scraper.py -v
```

---

#### Task 2.2: Twitter/X Monitor Service
**Estimated Time**: 4 hours (1 day)
**Dependencies**: Task 1.1 complete
**Deliverable**: Twitter API integration working

**Steps**:
1. Create Twitter Developer account (if needed)
2. Get API keys (free tier: 500k tweets/month)
3. Create `backend/app/services/social/twitter_monitor.py`
4. Implement tweet fetching by username
5. Add keyword filtering (industry terms)
6. Write unit tests with mock API responses
7. Test with real Twitter accounts

**Files Created**:
- `backend/app/services/social/twitter_monitor.py`
- `backend/tests/services/social/test_twitter_monitor.py`

**Implementation Pseudocode**:
```python
class TwitterMonitor:
    async def fetch_recent_tweets(self, contacts: List[Contact], days_back=7):
        tweets = []
        for contact in contacts:
            if contact.twitter_handle:
                user_tweets = await self._get_user_timeline(contact.twitter_handle)
                filtered = self._filter_relevant_tweets(user_tweets)
                tweets.extend(filtered)
        return tweets
```

**Verification**:
```bash
pytest tests/services/social/test_twitter_monitor.py -v
```

---

#### Task 2.3: AI Context Analyzer Service
**Estimated Time**: 6 hours (1.5 days)
**Dependencies**: Task 2.1, 2.2 complete
**Deliverable**: AI analysis generating email drafts

**Steps**:
1. Create `backend/app/services/social/context_analyzer.py`
2. Implement Claude API integration
3. Create analysis prompts (pain points, urgency, talking points)
4. Implement quality scoring (1-10 scale)
5. Create email generation prompts (5 template types)
6. Add tiered model selection (DeepSeek for simple, Claude for complex)
7. Write unit tests with sample posts
8. Test with 10 real LinkedIn/Twitter posts

**Files Created**:
- `backend/app/services/social/context_analyzer.py`
- `backend/app/services/social/prompts.py` (analysis & email templates)
- `backend/tests/services/social/test_context_analyzer.py`

**Implementation Pseudocode**:
```python
class ContextAnalyzer:
    async def analyze_social_activity(self, posts: List[SocialPost]):
        insights = []
        for post in posts:
            # Extract context
            context = await self._extract_context(post)

            # Quality check
            if context.quality_score >= 7:
                # Generate email
                email = await self._generate_email(context, post.contact)
                insights.append(Insight(
                    contact_id=post.contact_id,
                    email_subject=email.subject,
                    email_body=email.body,
                    talking_points=context.talking_points,
                    quality_score=context.quality_score
                ))
        return insights
```

**Verification**:
```bash
pytest tests/services/social/test_context_analyzer.py -v
```

---

#### Task 2.4: Database Service Layer
**Estimated Time**: 4 hours (1 day)
**Dependencies**: Task 1.1 complete
**Deliverable**: Database CRUD operations working

**Steps**:
1. Create `backend/app/core/database.py`
2. Implement `store_social_posts()`
3. Implement `store_email_draft()`
4. Implement `store_email_engagement()`
5. Implement `get_contact_monitoring_status()`
6. Add connection pooling
7. Write integration tests

**Files Created/Updated**:
- `backend/app/core/database.py` (enhanced)
- `backend/tests/core/test_database_social.py`

**Verification**:
```bash
pytest tests/core/test_database_social.py -v
```

---

#### Task 2.5: Close CRM Service Extensions
**Estimated Time**: 4 hours (1 day)
**Dependencies**: None
**Deliverable**: Close CRM methods for social intelligence

**Steps**:
1. Update `backend/app/services/crm/close.py`
2. Add `get_contacts_by_smart_view()`
3. Add `create_email_draft()` (status='draft')
4. Add `create_custom_activity()` (social research notes)
5. Add `update_lead_custom_field()` (high intent flag)
6. Add `get_recent_email_activities()` (engagement tracking)
7. Write integration tests with Close CRM sandbox

**Files Updated**:
- `backend/app/services/crm/close.py` (add new methods)
- `backend/tests/services/crm/test_close_social.py`

**Verification**:
```bash
pytest tests/services/crm/test_close_social.py -v
```

---

### **WEEK 3: Pipeline Integration & Testing** (5 days)

#### Task 3.1: Main Pipeline Runner
**Estimated Time**: 6 hours (1.5 days)
**Dependencies**: All Week 2 tasks complete
**Deliverable**: Complete pipeline working end-to-end

**Steps**:
1. Create `backend/social_intelligence_runner.py`
2. Implement `run_full_pipeline()` function
3. Implement `run_engagement_check()` function
4. Add logging and error handling
5. Add RunPod handler function
6. Test locally with 5 sample contacts

**Files Created**:
- `backend/social_intelligence_runner.py`

**Verification**:
```bash
# Local test
cd backend
python social_intelligence_runner.py

# Expected output:
# Starting Social Intelligence Pipeline
# Found 5 ATL contacts to monitor
# Scraped 8 LinkedIn posts
# Found 3 relevant tweets
# Generated 6 actionable insights
# Created 4 email drafts in Close CRM
# Pipeline Complete! Runtime: 847 seconds
```

---

#### Task 3.2: Email Engagement Tracking
**Estimated Time**: 4 hours (1 day)
**Dependencies**: Task 2.5 complete
**Deliverable**: Hourly engagement checks working

**Steps**:
1. Create `backend/check_email_engagement.py`
2. Implement Close CRM email activity polling
3. Detect 3+ opens, update custom field
4. Store engagement events in database
5. Test with historical sent emails

**Files Created**:
- `backend/check_email_engagement.py`

**Verification**:
```bash
python check_email_engagement.py

# Expected output:
# Starting Email Engagement Check
# Found 2 high-intent contacts (3+ opens)
# Updated Close CRM custom fields
# ✓ Engagement check complete
```

---

#### Task 3.3: Notification System
**Estimated Time**: 4 hours (1 day)
**Dependencies**: Task 3.1, 3.2 complete
**Deliverable**: Email notifications working

**Steps**:
1. Create `backend/app/services/notifications.py`
2. Implement `send_daily_summary()` (SMTP or SendGrid)
3. Implement `send_high_intent_alert()` (for 3+ opens)
4. Implement `send_error_notification()` (pipeline failures)
5. Create email templates (HTML + plain text)
6. Test with real email sending

**Files Created**:
- `backend/app/services/notifications.py`
- `backend/app/templates/email/daily_summary.html`
- `backend/app/templates/email/high_intent_alert.html`

**Verification**:
- Trigger daily summary manually
- Check inbox for formatted email

---

#### Task 3.4: Docker Container Build & Deploy
**Estimated Time**: 4 hours (1 day)
**Dependencies**: Task 3.1 complete
**Deliverable**: Docker image deployed to RunPod

**Steps**:
1. Complete `Dockerfile.serverless`
2. Build image: `docker build -f Dockerfile.serverless -t social-intel .`
3. Test image locally: `docker run social-intel`
4. Push to GitHub Container Registry
5. Update RunPod endpoint with new image
6. Test serverless execution via RunPod API

**Files Updated**:
- `backend/Dockerfile.serverless` (finalized)
- `.github/workflows/build-docker.yml` (automated builds)

**Verification**:
```bash
# Trigger RunPod endpoint
curl -X POST https://api.runpod.io/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"input": {"task": "full_pipeline"}}'

# Check RunPod logs for success
```

---

#### Task 3.5: End-to-End Integration Testing
**Estimated Time**: 6 hours (1.5 days)
**Dependencies**: All Week 3 tasks complete
**Deliverable**: Production-ready system verified

**Steps**:
1. Select 10 real Hot ATL contacts from Close CRM
2. Run full pipeline end-to-end
3. Verify email drafts appear in Close CRM
4. Verify research notes stored correctly
5. Test engagement tracking with test emails
6. Monitor for LinkedIn blocks or errors
7. Review AI-generated email quality
8. Fix any bugs discovered

**Test Scenarios**:
- ✅ Pipeline completes in <60 minutes
- ✅ At least 3 email drafts created
- ✅ All drafts have quality score >7
- ✅ Research notes visible in Close CRM
- ✅ No LinkedIn account blocks
- ✅ Engagement tracking updates custom fields
- ✅ Daily summary email received

**Bug Fixes**:
- Document any issues found
- Fix critical bugs before Week 4
- Create tickets for non-critical improvements

---

### **WEEK 4: Production Deployment & Monitoring** (5 days)

#### Task 4.1: GitHub Actions Production Deployment
**Estimated Time**: 2 hours
**Dependencies**: Task 3.5 complete
**Deliverable**: Automated daily pipeline running in production

**Steps**:
1. Update GitHub Actions workflow with production config
2. Set cron schedule to 6 AM your timezone
3. Enable hourly engagement checks (8 AM - 6 PM)
4. Monitor first automated run
5. Verify email drafts appear at 7 AM

**Verification**:
- Wait for 6 AM cron trigger
- Check GitHub Actions logs
- Check Close CRM for new drafts
- Check inbox for daily summary

---

#### Task 4.2: Monitoring & Alerting Setup
**Estimated Time**: 4 hours (1 day)
**Dependencies**: Task 4.1 complete
**Deliverable**: Production monitoring in place

**Steps**:
1. Set up RunPod logging (view in dashboard)
2. Create Supabase query dashboard (monitor database growth)
3. Set up error alerting (email on pipeline failure)
4. Create weekly report script (success rates, costs)
5. Document troubleshooting guide

**Files Created**:
- `backend/scripts/weekly_report.py`
- `docs/TROUBLESHOOTING.md`

**Dashboards to Monitor**:
- GitHub Actions: Run success rate
- RunPod: Execution time, cold starts
- Supabase: Database size, query performance
- Close CRM: Draft creation rate, email open rates

---

#### Task 4.3: AI Prompt Refinement
**Estimated Time**: 6 hours (1.5 days)
**Dependencies**: Task 4.1 complete (real production data)
**Deliverable**: Improved email quality based on real results

**Steps**:
1. Review 20 AI-generated email drafts
2. Identify patterns in low-quality outputs
3. Refine analysis prompts (better context extraction)
4. Refine email prompts (more natural language)
5. A/B test prompt variations
6. Update production prompts

**Metrics to Improve**:
- Quality score average: Target >8/10
- Email acceptance rate: Target 80% (Tim sends without edits)
- Personalization depth: At least 2 specific details per email

**Files Updated**:
- `backend/app/services/social/prompts.py`

---

#### Task 4.4: Cost Optimization
**Estimated Time**: 2 hours
**Dependencies**: Task 4.1 complete (1 week of production data)
**Deliverable**: Optimized costs

**Steps**:
1. Analyze RunPod execution times (optimize if >60 min)
2. Review AI API costs (switch models if too expensive)
3. Check Supabase database size (cleanup old data if needed)
4. Optimize scraping (reduce redundant requests)
5. Document actual monthly costs

**Target Costs**:
- RunPod: <$20/month
- AI APIs: <$2/month
- Total: <$25/month (vs $77 dedicated pod)

**Optimization Ideas**:
- Cache LinkedIn profiles for 24 hours (reduce scraping)
- Use DeepSeek for 80% of analysis (cheaper than Claude)
- Batch database operations (reduce Supabase queries)

---

#### Task 4.5: Documentation & Handoff
**Estimated Time**: 4 hours (1 day)
**Dependencies**: All tasks complete
**Deliverable**: Complete documentation for future maintenance

**Steps**:
1. Write `README_SOCIAL_INTELLIGENCE.md`
2. Document daily workflow (how Tim uses the system)
3. Document common troubleshooting steps
4. Create runbook for emergencies
5. Update main project CLAUDE.md with social intelligence section
6. Record demo video (optional)

**Files Created**:
- `README_SOCIAL_INTELLIGENCE.md`
- `docs/RUNBOOK_SOCIAL_INTEL.md`
- `docs/DAILY_WORKFLOW.md`

**Documentation Sections**:
- System overview
- How to add/remove contacts from monitoring
- How to pause/resume pipeline
- How to update AI prompts
- How to troubleshoot LinkedIn blocks
- How to scale to 50-100 contacts

---

## Success Criteria

### Week 1 Success
- ✅ Supabase database operational
- ✅ RunPod endpoint deployed
- ✅ GitHub Actions workflow triggering
- ✅ Close CRM custom fields created

### Week 2 Success
- ✅ LinkedIn scraper working (5 profiles tested)
- ✅ Twitter monitor working (5 accounts tested)
- ✅ AI analysis generating quality emails (8+/10 score)
- ✅ Database storing all data correctly

### Week 3 Success
- ✅ End-to-end pipeline completes successfully
- ✅ 5+ email drafts created in Close CRM
- ✅ Engagement tracking detecting 3+ opens
- ✅ Docker container running on RunPod

### Week 4 Success
- ✅ Automated daily pipeline running at 6 AM
- ✅ Tim receives 3-5 quality email drafts per day
- ✅ Zero LinkedIn account blocks
- ✅ Monthly cost <$25
- ✅ Complete documentation delivered

---

## Risk Mitigation Timeline

### Week 1 Risks
**Risk**: Supabase connection issues
**Mitigation**: Test connection immediately, fallback to local PostgreSQL if needed

### Week 2 Risks
**Risk**: LinkedIn blocks account during testing
**Mitigation**: Use test LinkedIn account, implement rate limits from day 1

**Risk**: AI generates low-quality emails
**Mitigation**: Manual review of first 20 emails, refine prompts before production

### Week 3 Risks
**Risk**: Pipeline takes >90 minutes (too slow)
**Mitigation**: Parallelize LinkedIn + Twitter scraping, optimize database queries

### Week 4 Risks
**Risk**: Production costs higher than expected
**Mitigation**: Monitor costs daily, switch to cheaper AI models if needed

---

## Post-Launch Iteration Plan

### Month 2 Goals
- Scale from 20 → 50 ATL contacts
- Improve email acceptance rate to 90%
- Add Facebook monitoring (if valuable)
- Implement email sequences (auto follow-ups)

### Month 3 Goals
- Evaluate PhantomBuster integration ($30/month)
- Test Twitter Premium API ($200/month) for real-time
- Build analytics dashboard (email performance metrics)
- Consider hiring SDR to handle BTL outreach

---

## Files to Create (Master Checklist)

**Week 1**:
- [ ] `backend/alembic/versions/2025_11_17_social_intelligence_schema.py`
- [ ] `backend/Dockerfile.serverless`
- [ ] `backend/requirements-serverless.txt`
- [ ] `.github/workflows/social-intelligence.yml`
- [ ] `.github/workflows/build-docker.yml`
- [ ] `backend/setup_social_intelligence.py`

**Week 2**:
- [ ] `backend/app/services/social/__init__.py`
- [ ] `backend/app/services/social/linkedin_scraper.py`
- [ ] `backend/app/services/social/twitter_monitor.py`
- [ ] `backend/app/services/social/context_analyzer.py`
- [ ] `backend/app/services/social/prompts.py`
- [ ] `backend/tests/services/social/test_linkedin_scraper.py`
- [ ] `backend/tests/services/social/test_twitter_monitor.py`
- [ ] `backend/tests/services/social/test_context_analyzer.py`
- [ ] `backend/tests/core/test_database_social.py`
- [ ] `backend/tests/services/crm/test_close_social.py`

**Week 3**:
- [ ] `backend/social_intelligence_runner.py`
- [ ] `backend/check_email_engagement.py`
- [ ] `backend/app/services/notifications.py`
- [ ] `backend/app/templates/email/daily_summary.html`
- [ ] `backend/app/templates/email/high_intent_alert.html`

**Week 4**:
- [ ] `backend/scripts/weekly_report.py`
- [ ] `docs/TROUBLESHOOTING.md`
- [ ] `README_SOCIAL_INTELLIGENCE.md`
- [ ] `docs/RUNBOOK_SOCIAL_INTEL.md`
- [ ] `docs/DAILY_WORKFLOW.md`

**Total Files**: 30 new files + 2 updated files

---

## Daily Standup Template (for tracking progress)

```markdown
## Day X Progress

**Completed Tasks**:
- [ ] Task X.X - Description

**In Progress**:
- [ ] Task X.X - Description

**Blockers**:
- None / [Describe blocker]

**Tomorrow's Plan**:
- [ ] Task X.X - Description

**Time Spent**: X hours
**Notes**: [Any learnings or issues discovered]
```

---

**Implementation Start Date**: 2025-11-17
**Target Completion**: 2025-12-15 (4 weeks)
**Status**: Ready to Begin ✅

---

## Quick Start Commands

```bash
# Clone worktree (already done ✅)
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
git worktree list  # Verify .worktrees/social-intelligence exists

# Start Week 1, Task 1.1 (Supabase setup)
cd .worktrees/social-intelligence/backend
# Follow Task 1.1 steps in this document

# Track progress with git commits
git add .
git commit -m "feat: Complete Task 1.1 - Supabase database schema"
git push origin feature/social-intelligence
```

**Let's build this! 🚀**
