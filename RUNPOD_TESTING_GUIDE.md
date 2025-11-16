# RunPod End-to-End Testing Guide - Social Intelligence

**Last Updated**: January 16, 2025
**Version**: 1.0
**Purpose**: Manual testing and validation of Social Intelligence pipeline on RunPod

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Manual GitHub Actions Trigger](#manual-github-actions-trigger)
3. [Monitoring Execution](#monitoring-execution)
4. [Verifying Results](#verifying-results)
5. [Troubleshooting](#troubleshooting)
6. [Performance Benchmarks](#performance-benchmarks)

---

## Prerequisites

### Required Access
- ✅ GitHub account with repository access
- ✅ Supabase account (database access)
- ✅ Close CRM account (API access)
- ✅ RunPod account (for advanced debugging)

### Environment Verification
```bash
# 1. Check GitHub Actions workflow exists
gh workflow list | grep "Social Intelligence"

# 2. Verify Docker image published
gh run list --workflow="Build Social Intelligence Docker Image" --limit 1

# 3. Check secrets configured
gh secret list | grep -E '(RUNPOD|SUPABASE|CLOSE|ANTHROPIC|DEEPSEEK)'
```

**Required Secrets**:
- `RUNPOD_API_KEY`
- `RUNPOD_ENDPOINT_ID`
- `SUPABASE_DATABASE_URL`
- `CLOSE_API_KEY`
- `ANTHROPIC_API_KEY`
- `DEEPSEEK_API_KEY`

---

## Manual GitHub Actions Trigger

### Step 1: Navigate to GitHub Actions

```bash
# Open in browser
gh browse --repo ScientiaCapital/sales-agent /actions/workflows/social-intelligence.yml

# Or use CLI
gh workflow view "Social Intelligence Pipeline"
```

### Step 2: Trigger Workflow

**Via GitHub UI**:
1. Go to **Actions** tab
2. Select **"Social Intelligence Pipeline"** workflow
3. Click **"Run workflow"** button (top right)
4. Select branch: `main`
5. Click **"Run workflow"** (green button)

**Via GitHub CLI**:
```bash
gh workflow run "Social Intelligence Pipeline" \
  --ref main \
  --field max_contacts=5 \
  --field test_mode=true
```

### Step 3: Get Run ID

```bash
# List recent runs
gh run list --workflow="Social Intelligence Pipeline" --limit 5

# Get latest run ID
LATEST_RUN=$(gh run list --workflow="Social Intelligence Pipeline" --limit 1 --json databaseId --jq '.[0].databaseId')
echo "Run ID: $LATEST_RUN"
```

---

## Monitoring Execution

### Real-Time Log Streaming

```bash
# Watch logs in real-time (auto-updates every 3 seconds)
gh run watch $LATEST_RUN

# View specific job logs
gh run view $LATEST_RUN --log

# Filter for errors
gh run view $LATEST_RUN --log | grep -i "error\|failed\|exception"
```

### Expected Execution Flow

**Total Duration**: 5-10 minutes

```
[00:00] Workflow started
[00:30] Docker image pulled
[01:00] RunPod endpoint invoked
[01:30] LinkedIn scraping started (3 contacts in parallel)
[02:30] Twitter monitoring started
[03:00] AI context analysis (DeepSeek)
[04:00] Email draft generation (Claude Sonnet 4.5)
[05:00] Close CRM draft creation
[06:00] Supabase data storage
[06:30] Engagement tracking check
[07:00] Cleanup and completion
```

### Key Log Markers

**Success Indicators**:
```
✓ LinkedIn: Scraped 5 profiles successfully
✓ Twitter: Found 8 original tweets
✓ AI Analysis: 12 posts analyzed (65% DeepSeek, 35% Claude)
✓ Email Drafts: 6 drafts created in Close CRM
✓ Supabase: 20 rows inserted (social_posts, email_drafts)
✓ Cost: $0.12 (within budget)
```

**Warning Signs**:
```
⚠ LinkedIn: Rate limit encountered (pausing 60s)
⚠ Twitter: Private account skipped
⚠ AI: Fallback to Claude for complex post
⚠ Close: Draft already exists, skipping
```

**Errors** (requires investigation):
```
❌ RunPod: Endpoint timeout after 300s
❌ Supabase: Connection refused
❌ Close CRM: API key invalid
❌ LinkedIn: Account blocked
```

---

## Verifying Results

### 1. Supabase Database Verification

**Login to Supabase** → Select Project → **Table Editor**

#### Check `social_posts` Table
```sql
-- Recent posts scraped
SELECT
  platform,
  contact_name,
  post_content,
  ai_analysis->>'pain_points' as pain_points,
  created_at
FROM social_posts
WHERE created_at > NOW() - INTERVAL '1 day'
ORDER BY created_at DESC
LIMIT 10;
```

**Expected Results**:
- 5-15 new rows (depending on contact activity)
- `platform` = 'linkedin' or 'twitter'
- `ai_analysis` JSON populated
- `created_at` within last hour

#### Check `email_drafts` Table
```sql
-- Draft emails created
SELECT
  contact_name,
  subject,
  body,
  close_crm_activity_id,
  created_at
FROM email_drafts
WHERE created_at > NOW() - INTERVAL '1 day'
ORDER BY created_at DESC
LIMIT 10;
```

**Expected Results**:
- 3-6 new draft emails
- `subject` and `body` populated
- `close_crm_activity_id` NOT NULL (successfully created in CRM)

---

### 2. Close CRM Verification

**Login to Close CRM** → **Activities**

#### Filter for Social Intelligence Drafts
```
1. Click "Activities" in left sidebar
2. Filter:
   - Activity Type: "Social Intelligence"
   - Status: "draft"
   - Date: Today
3. Sort by: Created (newest first)
```

**Expected Results**:
- **3-6 draft emails** visible
- **Status**: 'draft' (not sent)
- **Activity Notes**: Include post context
- **Contact**: Linked to ATL contact

#### Verify Draft Quality
For each draft:
- ✅ **Subject line**: References post topic
- ✅ **Body**: Personalized, not generic
- ✅ **Post context**: Included in activity notes
- ✅ **Talking points**: Pain points, urgency, hooks
- ✅ **Call-to-action**: Clear next step

**Example Good Draft**:
```
Subject: Re: Your post on sales automation bottlenecks

Hey [Name],

Saw your LinkedIn post about manual lead qualification eating up 20 hours/week.
We faced the same issue before building our Cerebras-powered agent (633ms per lead).

Happy to share our approach if helpful - no strings attached.

- Tim
```

---

### 3. Engagement Tracking Verification

#### Check `email_engagement` Table (Supabase)
```sql
-- Recent engagement events
SELECT
  contact_email,
  event_type,
  event_data,
  created_at
FROM email_engagement
WHERE created_at > NOW() - INTERVAL '1 day'
ORDER BY created_at DESC
LIMIT 20;
```

**Expected Events** (if emails were sent):
- `event_type` = 'opened', 'clicked', 'replied'
- `event_data` JSON with timestamp, browser, etc.

#### Check High-Intent Smart View (Close CRM)
```
1. Close CRM → Smart Views
2. Select: "🔥 High-Intent ATL Contacts (3+ Opens)"
3. Verify: Contacts with 3+ opens appear
```

---

## Troubleshooting

### Common Issues

#### **Issue 1: Workflow Doesn't Start**

**Symptoms**:
- GitHub Actions run not appearing
- "Run workflow" button disabled

**Solutions**:
```bash
# 1. Check workflow file exists
ls -la .github/workflows/social-intelligence.yml

# 2. Verify workflow is enabled
gh workflow view "Social Intelligence Pipeline"

# 3. Enable if disabled
gh workflow enable "Social Intelligence Pipeline"

# 4. Check branch protection rules
gh api repos/ScientiaCapital/sales-agent/branches/main/protection
```

---

#### **Issue 2: RunPod Timeout**

**Symptoms**:
```
Error: RunPod endpoint timeout after 300s
```

**Solutions**:
```bash
# 1. Check RunPod endpoint status
curl -X GET "https://api.runpod.io/v2/s6m25m225cuq1h/status" \
  -H "Authorization: Bearer $RUNPOD_API_KEY"

# 2. Increase timeout in workflow
# Edit .github/workflows/social-intelligence.yml
# Change: timeout-minutes: 5 → timeout-minutes: 10

# 3. Check RunPod logs
# Login to RunPod → Serverless → Endpoint Logs
```

---

#### **Issue 3: No Posts Scraped**

**Symptoms**:
```
LinkedIn: Scraped 0 profiles
Twitter: Found 0 tweets
```

**Possible Causes**:
1. **Contacts didn't post** - Normal, try again tomorrow
2. **Rate limit hit** - Check logs for rate limit errors
3. **Credentials invalid** - Verify API keys in secrets

**Solutions**:
```bash
# 1. Verify contacts exist in Close CRM with ATL tag
# 2. Check Playwright browser installation
gh run view $LATEST_RUN --log | grep "Playwright"

# 3. Test locally
cd backend
python social_intelligence_runner.py
```

---

#### **Issue 4: Supabase Connection Failed**

**Symptoms**:
```
Error: Could not connect to Supabase
psycopg.OperationalError: connection refused
```

**Solutions**:
```bash
# 1. Verify Supabase URL in secrets
gh secret list | grep SUPABASE

# 2. Test connection locally
python -c "
import psycopg
import os
conn = psycopg.connect(os.getenv('SUPABASE_DATABASE_URL'))
print('✓ Connected to Supabase')
"

# 3. Check Supabase service status
# Visit: https://status.supabase.com/
```

---

#### **Issue 5: Close CRM API Errors**

**Symptoms**:
```
Error: Close CRM API returned 401 Unauthorized
```

**Solutions**:
```bash
# 1. Verify API key
gh secret list | grep CLOSE_API_KEY

# 2. Test API key
curl -X GET "https://api.close.com/api/v1/me/" \
  -H "Authorization: Bearer $CLOSE_API_KEY"

# 3. Check Close CRM rate limits
# Max: 600 requests/minute
```

---

## Performance Benchmarks

### Expected Performance Metrics

#### **Scraping**:
- **LinkedIn**: 30-60s per profile (sequential, rate-limited)
- **Twitter**: 5-10s per account (API, parallelized)
- **Total Scraping**: 2-4 minutes for 5 contacts

#### **AI Analysis**:
- **DeepSeek** (65% of posts): 500-800ms per post
- **Claude Sonnet 4.5** (35% of posts): 2-4s per post
- **Total AI**: 1-2 minutes for 10-15 posts

#### **Draft Creation**:
- **Claude Sonnet 4.5**: 3-5s per draft
- **Close CRM API**: 200-500ms per activity
- **Total Drafting**: 30-60s for 5-6 drafts

#### **Database Operations**:
- **Supabase Inserts**: <100ms per row
- **Close CRM Sync**: 1-2s total

#### **Overall**:
- **End-to-End**: 5-10 minutes
- **Cost**: $0.10-0.15 per run
- **Drafts Generated**: 3-6 emails

### Cost Breakdown

**Per Run** (assuming 5 contacts, 12 posts, 6 drafts):
```
RunPod Serverless:     $0.01  (2 min runtime)
DeepSeek API:          $0.02  (8 posts × $0.0027)
Claude API:            $0.09  (4 posts + 6 drafts × $0.003)
LinkedIn/Twitter:      $0.00  (free scraping)
Supabase:              $0.00  (free tier)
Close CRM:             $0.00  (included)
-------------------------------------------
TOTAL:                 $0.12 per run
Monthly (30 runs):     $3.60
```

**Within Budget**: ✅ ($17-19/month budgeted)

---

## Next Steps After Testing

### ✅ Test Passed
1. Document results in `WEEK_5_TESTING_RESULTS.md`
2. Enable daily cron schedule (6 AM UTC)
3. Enable hourly engagement checks (8 AM - 6 PM)
4. Set up monitoring alerts
5. Train sales team on draft review process

### ❌ Test Failed
1. Review logs: `gh run view $LATEST_RUN --log`
2. Check error categories (connection, API, data)
3. Fix root cause
4. Re-run test
5. Document fix in troubleshooting guide

---

## Appendix: Useful Commands

### Quick Reference

```bash
# Trigger test run
gh workflow run "Social Intelligence Pipeline" --ref main

# Watch logs
gh run watch $(gh run list --workflow="Social Intelligence Pipeline" --limit 1 --json databaseId --jq '.[0].databaseId')

# View last 5 runs
gh run list --workflow="Social Intelligence Pipeline" --limit 5

# Cancel a run
gh run cancel <run-id>

# Rerun failed jobs
gh run rerun <run-id> --failed

# Download logs
gh run download <run-id>

# Check workflow status
gh workflow view "Social Intelligence Pipeline"
```

---

**Happy Testing!** 🚀

*For issues or questions, see `SOCIAL_INTELLIGENCE_USER_GUIDE.md` or create a GitHub issue.*
