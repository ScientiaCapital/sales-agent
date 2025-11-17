# RunPod "Not Found" Fix - Make GHCR Package Public

**Date**: January 16, 2025
**Issue**: RunPod endpoint returns `{"message":"Not Found"}`
**Root Cause**: GHCR Docker image is private (HTTP 401 unauthorized)
**Solution**: Make the package public so RunPod can pull it

---

## Root Cause Analysis

The RunPod serverless endpoint is properly configured with:
- ✅ Endpoint ID: `s6m25m225cuq1h`
- ✅ Docker Image: `ghcr.io/scientiacapital/sales-agent:social-intelligence-latest`
- ✅ Environment variables set
- ✅ Scaling configuration correct

However, when RunPod tries to pull the Docker image, it gets **401 Unauthorized** because the GHCR package is private by default.

**Verification**:
```bash
curl -I https://ghcr.io/v2/scientiacapital/sales-agent/manifests/social-intelligence-latest
# Returns: HTTP/2 401
```

---

## Solution: Make GHCR Package Public

### Option 1: Via GitHub Web UI (Recommended - 2 minutes)

1. **Navigate to the package**:
   - Go to: https://github.com/orgs/scientiacapital/packages
   - Or direct link: https://github.com/orgs/scientiacapital/packages/container/sales-agent

2. **Change visibility**:
   - Click on the `sales-agent` package
   - Click "Package settings" in the right sidebar
   - Scroll down to "Danger Zone"
   - Click "Change visibility"
   - Select "Public"
   - Type the package name to confirm: `sales-agent`
   - Click "I understand, change package visibility"

3. **Verify the change**:
   ```bash
   curl -I https://ghcr.io/v2/scientiacapital/sales-agent/manifests/social-intelligence-latest
   # Should return: HTTP/2 200 (instead of 401)
   ```

### Option 2: Via GitHub CLI (If you prefer CLI)

```bash
# Note: This requires GitHub CLI with proper permissions
# The scientiacapital organization owner needs to run this:

gh api \
  --method PATCH \
  -H "Accept: application/vnd.github+json" \
  /orgs/scientiacapital/packages/container/sales-agent \
  -f visibility='public'
```

---

## After Making the Package Public

### Step 1: Verify Public Access
```bash
# Test anonymous access (should succeed)
docker logout ghcr.io
docker pull ghcr.io/scientiacapital/sales-agent:social-intelligence-latest

# You should see:
# social-intelligence-latest: Pulling from scientiacapital/sales-agent
# Digest: sha256:d576c2c8570f64a1a0dd827212b6bcc75a7472e32b8d8bf17364e68dc2c8f976
# Status: Downloaded newer image...
```

### Step 2: Re-test RunPod Endpoint

The RunPod endpoint configuration is already correct - no changes needed. Just re-trigger the workflow:

```bash
# Trigger the workflow
gh workflow run "Social Intelligence Pipeline" --ref main

# Watch the execution
gh run watch
```

### Step 3: Verify Success

The workflow should now succeed with RunPod actually processing the job:

Expected output:
```json
{
  "id": "job-id-here",
  "status": "IN_QUEUE"
}
```

NOT:
```json
{"message":"Not Found"}
```

---

## Alternative: Configure RunPod with Private Registry Credentials

If you prefer to keep the image private, you can configure RunPod with GHCR credentials:

1. **Create a GHCR Personal Access Token**:
   - Go to: https://github.com/settings/tokens
   - Generate new token (classic)
   - Select scopes: `read:packages`
   - Copy the token

2. **Configure RunPod Image Pull Secret** (Web Console):
   - Go to endpoint settings
   - Under "Container Registry" section
   - Add credentials:
     - Registry: `ghcr.io`
     - Username: Your GitHub username
     - Password: The PAT you created
   - Save configuration

However, **making the package public is simpler** since this is the Social Intelligence system and doesn't contain highly sensitive source code.

---

## Security Considerations

### What's Public (if you make the package public):
- ✅ Docker image layers (compiled Python code)
- ✅ Dependencies (requirements.txt packages)
- ✅ Application structure

### What Remains Private:
- ✅ Environment variables (NEVER in the image)
- ✅ API keys (stored in RunPod secrets)
- ✅ Database credentials (stored in RunPod secrets)
- ✅ Source code repository (still private)

The Docker image contains the application code but no secrets. All sensitive data is injected via environment variables at runtime.

---

## Testing After Fix

Once the package is public, test the complete pipeline:

```bash
# 1. Re-trigger workflow
gh workflow run "Social Intelligence Pipeline" --ref main

# 2. Get the run ID
gh run list --workflow="Social Intelligence Pipeline" --limit 1

# 3. Watch the execution
gh run watch <RUN_ID>

# 4. Check for success
# Look for:
# ✓ Build Docker image
# ✓ Trigger RunPod Serverless Endpoint
# ✓ Wait for Completion
```

Expected result:
- ✅ No "Not Found" error
- ✅ RunPod job ID returned
- ✅ Pipeline executes social intelligence analysis
- ✅ Data populated in Supabase
- ✅ Draft emails created in Close CRM

---

## Update Documentation

After successful testing, update:

1. **WEEK_5_TESTING_RESULTS.md**:
   - Mark RunPod integration as ✅ Complete
   - Document the GHCR visibility requirement
   - Add final test results

2. **Memory** (already saved):
   - `runpod-serverless-endpoint-configuration` memory contains this knowledge
   - Future Claude sessions will reference this

---

## Quick Reference

**Problem**: `{"message":"Not Found"}`
**Cause**: Private GHCR image (HTTP 401)
**Fix**: Make package public at https://github.com/orgs/scientiacapital/packages/container/sales-agent
**Verify**: `curl -I https://ghcr.io/v2/scientiacapital/sales-agent/manifests/social-intelligence-latest`
**Test**: Re-trigger GitHub Actions workflow

---

**Created**: January 16, 2025
**Status**: Ready to execute
**Estimated Time**: 2 minutes to fix
