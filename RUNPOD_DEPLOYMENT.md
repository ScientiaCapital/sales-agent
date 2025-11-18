# RunPod Serverless Deployment Guide

## Critical Lessons Learned (January 17, 2025)

This document captures the **exact process** for deploying to RunPod Serverless after systematic debugging resolved multiple architectural issues. Follow this guide to avoid repeating the same mistakes.

---

## 🚨 NEVER DO THIS

### ❌ Local Docker Builds for RunPod
**DON'T:**
```bash
# This builds for ARM64 (Apple Silicon) - INCOMPATIBLE with RunPod
docker build -f backend/Dockerfile.serverless -t social-intel .
docker push ghcr.io/scientiacapital/sales-agent:social-intelligence-latest
```

**WHY IT FAILS:**
- Apple Silicon Macs build `linux/arm64` images by default
- RunPod requires `linux/amd64` architecture
- Cross-compilation with `--platform linux/amd64` takes **15-20 minutes**
- Often gets stuck or fails silently
- Workers fail with: `"failed to pull image: no matching manifest for linux/amd64"`

---

## ✅ ALWAYS DO THIS

### ✅ GitHub Actions Workflow (AMD64 Native)
**DO:**
```bash
# Trigger GitHub Actions workflow - builds AMD64 natively in ~21 seconds
gh workflow run social-intelligence.yml
```

**WHY IT WORKS:**
- GitHub Actions runners are AMD64 (ubuntu-latest)
- No emulation needed - native builds are **40x faster**
- Docker layer caching via GitHub Actions cache
- Automatic push to GHCR (GitHub Container Registry)

**Workflow File:** `.github/workflows/social-intelligence.yml`
```yaml
jobs:
  build-and-push:
    runs-on: ubuntu-latest  # AMD64 runner

    steps:
      - name: Build and push Docker image
        uses: docker/build-push-action@v5
        with:
          context: ./backend
          file: ./backend/Dockerfile.serverless
          push: true
          platforms: linux/amd64  # ✅ Explicit AMD64
          tags: ghcr.io/scientiacapital/sales-agent:social-intelligence-latest
          cache-from: type=gha
          cache-to: type=gha,mode=max
```

**Monitoring:**
```bash
# Watch build progress
gh run list --workflow="Social Intelligence Pipeline" --limit 3

# View specific run
gh run view <run-id>
```

---

## 🐛 Critical Bug Fixes

### 1. Async Handler Pattern (REQUIRED)

**❌ BROKEN (causes RuntimeError):**
```python
def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """Sync handler - FAILS in RunPod"""
    result = asyncio.run(run_full_pipeline(config))  # ERROR!
    return result
```

**Error:**
```
RuntimeError: asyncio.run() cannot be called from a running event loop
```

**✅ FIXED:**
```python
async def handler(job: Dict[str, Any]) -> Dict[str, Any]:
    """Async handler - uses existing event loop"""
    result = await run_full_pipeline(config)  # ✅ Correct
    return result
```

**WHY:**
- RunPod executes handlers in an **existing asyncio event loop**
- `asyncio.run()` tries to create a **new** event loop → RuntimeError
- Must use `async def` + `await` to use the existing loop

**File:** `backend/handler.py`

---

### 2. Environment Variable Loading

**❌ BROKEN (401 Unauthorized):**
```python
# Loads root .env instead of backend/.env
env_path = Path(__file__).parent.parent / '.env'
```

**✅ FIXED:**
```python
# Loads backend/.env with API keys
env_path = Path(__file__).parent / '.env'
load_dotenv(env_path)

RUNPOD_API_KEY = os.getenv('RUNPOD_API_KEY')
RUNPOD_ENDPOINT_ID = "e2zekp154j2zfj"
```

**WHY:**
- Test scripts in `backend/` directory need `backend/.env`
- Root `.env` may not have all required API keys
- Always verify `.env` path relative to script location

**File:** `backend/trigger_runpod_test.py`

---

## 📦 Dependency Management (Critical)

### The Cascading Dependency Hell We Survived

**Pattern Recognized:** Each fix revealed a new conflict:
1. ❌ `langchain-text-splitters==0.3.2` → Updated to 0.3.3
2. ❌ `langchain-postgres` conflicted with `numpy>=2.1.0` → Removed
3. ❌ `langchain-ollama` conflicted with `langchain-core>=0.3.31` → Removed
4. ❌ `openai==2.2.0` conflicted with `langchain-openai 0.3.0` → Downgraded
5. ❌ `pyaudio==0.2.14` required C headers (portaudio) → Removed

**Solution:** Systematic package audit, not symptom-by-symptom fixes.

### ✅ Packages Removed (7 total)
```python
# Voice packages - NOT imported anywhere in backend/app/
# pyaudio==0.2.14      # Requires C headers, fails CI builds
# wave==0.0.2          # Python stdlib module sufficient
# websockets==13.1     # Cartesia SDK handles internally

# LangChain packages - NOT used in production
# langchain-postgres==0.0.12   # Only in unused enhanced_vector_store.py
# pgvector==0.3.6              # Dependency of langchain-postgres
# langchain-ollama==0.1.0      # Conflicts with langchain-core
# langchain-huggingface==0.1.0 # Not imported anywhere
```

### ✅ Package Audit Process
```bash
# 1. Scan codebase for actual imports
grep -r "^import\|^from" backend/app/ --include="*.py" | \
  cut -d':' -f2 | cut -d' ' -f2 | sort -u > /tmp/actual_imports.txt

# 2. Extract packages from requirements.txt
grep -v "^#" backend/requirements.txt | grep -v "^$" | \
  grep -E "^[a-zA-Z]" | cut -d'=' -f1 | cut -d'[' -f1 | \
  sort -u > /tmp/requirements_packages.txt

# 3. Compare and remove unused packages
# If package NOT in actual_imports.txt, remove from requirements.txt
```

### 🔍 When Dependency Conflicts Cascade
**If you see 3+ sequential fixes each revealing new conflicts:**
- **STOP fixing symptoms**
- Run systematic package audit
- Remove unused packages in ONE commit
- This is an **architectural problem**, not individual bugs

**Commits:**
- `3a23414` - Update langchain-text-splitters to 0.3.3
- `393ab58` - Remove langchain-postgres and pgvector
- `49fb3a1` - Remove unused voice packages (final fix)

---

## 🚀 Deployment Workflow

### Step 1: Code Changes
```bash
# Make changes to backend/handler.py or backend/app/services/social/
git add backend/
git commit -m "feat: Add social intelligence feature"
git push origin main
```

### Step 2: Trigger Docker Build
```bash
# Option A: Automatic (on push to main)
# GitHub Actions auto-triggers on push

# Option B: Manual trigger
gh workflow run social-intelligence.yml
```

### Step 3: Monitor Build
```bash
# Check build status
gh run list --workflow="Social Intelligence Pipeline" --limit 1

# View logs if failed
gh run view <run-id> --log-failed
```

### Step 4: Verify Docker Image
```bash
# Check image was pushed to GHCR
gh run view <run-id> | grep "digest"
```

### Step 5: RunPod Auto-Pulls New Image
- RunPod endpoint configured with: `ghcr.io/scientiacapital/sales-agent:social-intelligence-latest`
- On next job, workers auto-pull latest image
- No manual intervention needed

### Step 6: Test Deployment
```bash
cd backend
source ../venv/bin/activate
python trigger_runpod_test.py
```

**Expected Output:**
```
✅ Job Submitted Successfully!
   Job ID: <uuid>
   Status: IN_QUEUE

Attempt 1/60: Status = IN_PROGRESS
Attempt 2/60: Status = COMPLETED

✅ Job succeeded!
```

---

## 🔧 RunPod Configuration

### Endpoint Settings
- **Name:** `visiting_sapphire_kangaroo`
- **ID:** `e2zekp154j2zfj`
- **GPU:** AMPERE_16 (A4000/A5000 class)
- **Workers:** 0-3 (auto-scale on demand)
- **Scaler:** QUEUE_DELAY (4 seconds)
- **Idle Timeout:** 5 seconds
- **Container Image:** `ghcr.io/scientiacapital/sales-agent:social-intelligence-latest`

### Worker Auto-Scaling
- **Cold start:** Workers spin up from 0 on first job
- **Warm:** Workers stay active if jobs within 5 seconds
- **Shutdown:** Workers terminate after 5s idle

### Environment Variables (RunPod Dashboard)
```bash
SUPABASE_URL=https://...supabase.co
SUPABASE_KEY=eyJh...
CLOSE_API_KEY=api_...
DEEPSEEK_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
LINKEDIN_EMAIL=your@email.com
LINKEDIN_PASSWORD=***
TWITTER_BEARER_TOKEN=***
```

---

## 🧪 Testing Locally (Before RunPod)

### Test Handler Locally
```bash
cd backend
source ../venv/bin/activate

# Test async handler (mimics RunPod environment)
python -c "
import asyncio
from handler import handler

async def test():
    job = {
        'input': {
            'task': 'full_pipeline',
            'config': {
                'max_contacts': 5,
                'platforms': ['linkedin']
            }
        }
    }
    result = await handler(job)
    print(result)

asyncio.run(test())
"
```

### Test Docker Build Locally (Optional)
```bash
# ONLY if you need to test Docker image locally (NOT for deployment)
docker build -f backend/Dockerfile.serverless \
  --platform linux/amd64 \
  -t social-intel:local-test .

# This takes 15-20 minutes due to cross-compilation
# Use GitHub Actions for actual deployment
```

---

## 📊 Performance Benchmarks

### Build Times
| Method | Platform | Time | Cache |
|--------|----------|------|-------|
| **GitHub Actions** | AMD64 (native) | **21-33 seconds** | ✅ Yes |
| Local (Apple Silicon) | ARM64 → AMD64 | 15-20 minutes | ❌ No |
| Local (Intel Mac) | AMD64 (native) | 2-3 minutes | ✅ Yes |

### Cold Start Latency
- **First job (0 workers):** ~90-120 seconds (image pull + container start)
- **Warm workers:** <5 seconds
- **Recommendation:** Keep endpoint warm with cron jobs every 4 minutes

---

## 🐞 Troubleshooting

### Workers Stuck IN_QUEUE
**Symptom:** Jobs stay IN_QUEUE for 5+ minutes, never execute

**Causes:**
1. No workers available (cold start taking too long)
2. Image pull failure (check worker logs in RunPod dashboard)
3. Image architecture mismatch (ARM64 instead of AMD64)

**Fix:**
```bash
# Check worker logs in RunPod dashboard
# Look for: "failed to pull image: no matching manifest"

# If architecture mismatch:
# 1. Delete local Docker image
docker rmi ghcr.io/scientiacapital/sales-agent:social-intelligence-latest

# 2. Trigger GitHub Actions rebuild
gh workflow run social-intelligence.yml

# 3. Wait for build to complete (~21s)
gh run list --workflow="Social Intelligence Pipeline" --limit 1

# 4. Verify workers pull new image
# Check RunPod dashboard worker logs
```

### RuntimeError: asyncio.run() cannot be called
**Fix:** Change `def handler` → `async def handler`, use `await` instead of `asyncio.run()`

### 401 Unauthorized (API Keys)
**Fix:** Verify environment variables loaded from correct `.env` file

### Dependency Conflicts in CI
**Fix:** Run package audit, remove unused packages (see Dependency Management section)

---

## 📝 Quick Reference

### Build Commands
```bash
# Trigger GitHub Actions build
gh workflow run social-intelligence.yml

# Check build status
gh run list --workflow="Social Intelligence Pipeline" --limit 1

# View build logs
gh run view <run-id>
```

### Test Commands
```bash
# Test RunPod endpoint
cd backend
source ../venv/bin/activate
python trigger_runpod_test.py

# Check endpoint status
python query_runpod_status.py
```

### Dependency Commands
```bash
# Audit packages
grep -r "^import\|^from" backend/app/ --include="*.py" | \
  cut -d':' -f2 | cut -d' ' -f2 | sort -u > /tmp/actual_imports.txt

# Test installation
pip install -r backend/requirements.txt
```

---

## 🎯 Summary: The Golden Rules

1. **ALWAYS use GitHub Actions** for Docker builds (never local on Apple Silicon)
2. **ALWAYS use async def handler** with await (never asyncio.run)
3. **ALWAYS load backend/.env** for API keys (not root .env)
4. **ALWAYS audit packages** when 3+ dependency conflicts cascade
5. **ALWAYS verify AMD64 platform** in Docker build logs

Following these rules prevents the 4+ hours of debugging we went through today. 🎉

---

**Last Updated:** January 17, 2025
**Docker Image:** `ghcr.io/scientiacapital/sales-agent:social-intelligence-latest`
**RunPod Endpoint:** `visiting_sapphire_kangaroo` (ID: `e2zekp154j2zfj`)
