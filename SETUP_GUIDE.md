# Social Intelligence - Setup Guide (8-Hour Sprint)

**Goal**: Complete Week 1 infrastructure setup in 8 hours
**Status**: Task 1.1 In Progress

---

## ✅ TASK 1.1: Supabase Database Setup (30 minutes)

### Step 1: Log into Supabase
1. Go to https://app.supabase.com/
2. Click on your existing project OR create new project
   - Project name: `sales-agent-social-intel`
   - Database password: (choose strong password, save it!)
   - Region: Choose closest to you (US West, US East, EU, etc.)

### Step 2: Get Your Connection String
1. In Supabase dashboard, click **Settings** (gear icon)
2. Click **Database** tab
3. Scroll to **Connection string** section
4. Select **URI** tab (not Session Pooler)
5. Copy the connection string (looks like this):
   ```
   postgresql://postgres.[PROJECT]:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:5432/postgres
   ```
6. Replace `[YOUR-PASSWORD]` with your actual password

### Step 3: Run the Database Schema
1. In Supabase dashboard, click **SQL Editor** (left sidebar)
2. Click **New query**
3. Open this file on your computer:
   ```
   /Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/social-intelligence/backend/supabase_schema.sql
   ```
4. Copy ALL the SQL code
5. Paste it into the Supabase SQL Editor
6. Click **Run** button (or press Cmd+Enter)
7. You should see:
   ```
   Success. No rows returned
   ```

### Step 4: Verify Tables Created
Scroll to bottom of SQL Editor, you should see output like this:
```
table_name          | column_count
--------------------|-------------
contact_monitoring  | 9
email_drafts        | 10
email_engagement    | 5
social_posts        | 8
```

If you see all 4 tables → ✅ Success!

### Step 5: Update .env File
1. Open `.env` file in your main project directory:
   ```bash
   code /Users/tmkipper/Desktop/tk_projects/sales-agent/.env
   ```
2. Add this line (replace with your actual connection string):
   ```bash
   SUPABASE_DATABASE_URL=postgresql://postgres.[PROJECT]:[PASSWORD]@aws-0-us-west-1.pooler.supabase.com:5432/postgres
   ```
3. Save the file

### Step 6: Test Connection
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent/.worktrees/social-intelligence/backend

# Set environment variable
export SUPABASE_DATABASE_URL="your_connection_string_here"

# Or source from .env
export $(cat ../../../../.env | grep SUPABASE_DATABASE_URL | xargs)

# Run test script
python test_supabase_connection.py
```

**Expected output**:
```
===============================================================================
Testing Supabase Connection
===============================================================================

[1/5] Connecting to Supabase...
✅ Connection successful!

[2/5] Verifying tables created...
✅ All 4 tables created successfully:
   - contact_monitoring
   - email_drafts
   - email_engagement
   - social_posts

[3/5] Testing data insertion...
✅ Test contact created (ID: 1)

[4/5] Testing data retrieval...
✅ Data retrieved successfully

[5/5] Testing database views...
✅ high_intent_contacts view working
✅ daily_social_summary view working

===============================================================================
✅ ALL TESTS PASSED! Supabase database is ready.
===============================================================================
```

If you see this → **TASK 1.1 COMPLETE! ✅**

---

## ⏭️ TASK 1.3: RunPod Serverless Endpoint (Next - 1.5 hours)

### Step 1: Install RunPod CLI
```bash
pip install runpod
```

### Step 2: Get RunPod API Key
1. Log into RunPod: https://www.runpod.io/
2. Click your profile (top right) → **Settings**
3. Click **API Keys** tab
4. Click **+ API Key**
5. Name: `sales-agent-social-intel`
6. Copy the API key (save it!)

### Step 3: Authenticate RunPod CLI
```bash
runpod config --api-key YOUR_RUNPOD_API_KEY
```

### Step 4: Create Dockerfile (I'll create this next)
Wait for Claude to create `Dockerfile.serverless` file...

---

## 🕐 Today's Timeline (8 hours)

| Time | Task | Duration | Status |
|------|------|----------|--------|
| Now - 11:30 AM | Task 1.1: Supabase Setup | 30 min | 🟡 In Progress |
| 11:30 AM - 1:00 PM | Task 1.3: RunPod Serverless | 1.5 hrs | ⏸️ Pending |
| 1:00 PM - 2:00 PM | LUNCH BREAK | 1 hr | - |
| 2:00 PM - 4:00 PM | Task 1.4: GitHub Actions | 2 hrs | ⏸️ Pending |
| 4:00 PM - 5:00 PM | Task 1.5: Close CRM Setup | 1 hr | ⏸️ Pending |
| 5:00 PM - 6:00 PM | Testing & Documentation | 1 hr | ⏸️ Pending |
| 6:00 PM - 7:00 PM | Buffer for issues | 1 hr | ⏸️ Buffer |

---

## 🚨 Troubleshooting

### Supabase Connection Errors

**Error**: `could not connect to server`
- **Fix**: Check your project isn't paused (Supabase free tier pauses after 1 week of inactivity)
- Go to Supabase dashboard → Click "Resume" button if needed

**Error**: `password authentication failed`
- **Fix**: Double-check your password in the connection string
- Or reset password in Supabase Settings → Database → Reset database password

**Error**: `relation "social_posts" does not exist`
- **Fix**: You didn't run the SQL schema yet
- Go back to Step 3 and run `supabase_schema.sql`

### Installation Errors

**Error**: `pip: command not found`
- **Fix**: You're not in the virtual environment
```bash
cd /Users/tmkipper/Desktop/tk_projects/sales-agent
source venv/bin/activate
```

---

## 📞 Get Help

If you hit a blocker:
1. Check the error message
2. Look in the Troubleshooting section above
3. Ask Claude for help (describe the exact error)

---

**Let's go! Start with Task 1.1 now.** 🚀

When you complete Task 1.1, message me:
"Task 1.1 complete - moving to Task 1.3"

And I'll create the next set of files you need.
