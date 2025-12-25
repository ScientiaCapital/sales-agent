# Critical Blockers Fix Plan - Dec 25, 2025

**Status**: Ready for parallel execution
**Agents**: 6 Claude Opus 4.5 agents running in worktrees
**Methodology**: TDD + Parallelization + 100% Review Gates

---

## Executive Summary

Fix 6 critical blockers preventing Dec 29 Apollo campaign launch and unblock autonomous agent development.

**Blockers to Fix Today:**
1. Missing pandas dependency (blocks tests)
2. OpenAI policy violations (6 files)
3. CLOSE_WRITE_DISABLED=True (blocks GTM)
4. 3 Celery tasks stubbed (blocks automation)
5. CVE vulnerabilities (blocks commits)
6. Security hardening (prepare for production)

---

## Workstream Assignments

### WORKSTREAM 1: Dependencies & CVEs (sales-agent worktree)
**Agent**: sales-agent/feature-vlm-optimization
**Priority**: CRITICAL - Do First
**Est. Time**: 30 min

**Tasks:**
1. Add `pandas>=2.0.0` to requirements.txt
2. Upgrade `urllib3>=2.0.0` (CVE fixes)
3. Upgrade `Pillow>=10.0.0` (CVE fixes)
4. Upgrade `Jinja2>=3.1.0` (CVE fixes)
5. Run `pip install -r requirements.txt`
6. Run `pytest --collect-only` to verify test collection works
7. Commit: "fix: Add pandas, upgrade vulnerable dependencies"

**TDD Approach:**
- Before: `pytest --collect-only` fails with pandas import error
- After: `pytest --collect-only` succeeds with 0 collection errors

**Files to Modify:**
- `/backend/requirements.txt`

---

### WORKSTREAM 2: OpenAI Policy Violations (sales-agent worktree)
**Agent**: sales-agent/feature-vlm-optimization
**Priority**: CRITICAL
**Est. Time**: 2-3 hours

**Files Violating Policy (6 total):**
1. `backend/app/services/transcription_service.py` (line 11)
2. `backend/app/services/outreach/message_generator.py` (line 10)
3. `backend/app/services/gist_memory.py` (lines 198, 296, 345, 417)
4. `backend/app/services/runpod_vllm.py` (line 19)
5. `backend/app/services/model_router.py` (lines 143, 164)
6. `backend/app/services/document_analyzer.py` (lines 195, 239)

**Replacement Strategy:**
- Replace `from openai import AsyncOpenAI` with Anthropic Claude
- Use OpenRouter for OpenAI-compatible endpoints if needed
- Prefer: `anthropic.Anthropic()` or `litellm` with Claude models

**TDD Approach:**
- Write test that imports each module successfully
- Verify no `openai` imports remain: `grep -r "from openai" backend/`
- Run existing tests for each service

**Commit**: "fix: Replace OpenAI with Anthropic Claude (policy compliance)"

---

### WORKSTREAM 3: Enable Close CRM Writes (sales-agent worktree)
**Agent**: sales-agent/feature-vlm-optimization
**Priority**: CRITICAL - Unblocks GTM
**Est. Time**: 15 min

**File**: `backend/app/core/config.py` (Line 61)

**Change:**
```python
# Before
CLOSE_WRITE_DISABLED: bool = True

# After
CLOSE_WRITE_DISABLED: bool = os.getenv("CLOSE_WRITE_DISABLED", "false").lower() == "true"
```

**Also Update `.env`:**
```
CLOSE_WRITE_DISABLED=false
```

**TDD Approach:**
- Test that `settings.CLOSE_WRITE_DISABLED == False` when env var is false
- Test that write methods in `crm/close.py` are no longer returning early

**Files to Modify:**
- `backend/app/core/config.py`
- `.env`

**Commit**: "feat: Enable Close CRM writes for GTM automation"

---

### WORKSTREAM 4: Implement Celery Tasks (Parallel - 3 agents)
**Agents**: dealer-scraper, cold-reach, bug-hive (each takes 1 task)
**Priority**: CRITICAL - Enables automation
**Est. Time**: 1-2 hours each

**File**: `backend/app/tasks/close_sync.py`

#### Task 4A: sync_close_activities (dealer-scraper agent)
**Lines**: 143-282
**Purpose**: Sync activities from Close CRM back to Supabase

**Implementation:**
```python
@celery.task(name="sync_close_activities")
async def sync_close_activities():
    """Fetch recent activities from Close and sync to Supabase."""
    close_client = CloseClient()
    supabase = get_supabase_client()

    # Fetch activities from last 24 hours
    activities = await close_client.get_activities(
        date_created__gte=(datetime.utcnow() - timedelta(hours=24)).isoformat()
    )

    for activity in activities:
        # Upsert to fact_activities table
        await supabase.table("fact_activities").upsert({
            "close_activity_id": activity["id"],
            "contact_id": activity.get("contact_id"),
            "activity_type": activity["_type"],
            "created_at": activity["date_created"],
            "data": activity
        }).execute()

    return {"synced": len(activities)}
```

**TDD:**
1. Write test: `test_sync_close_activities_fetches_from_close()`
2. Write test: `test_sync_close_activities_upserts_to_supabase()`
3. Mock Close API and Supabase
4. Run tests, implement, verify

#### Task 4B: poll_email_replies (cold-reach agent)
**Lines**: 288-431
**Purpose**: Fetch incoming emails and route to reply processor

**Implementation:**
```python
@celery.task(name="poll_email_replies")
async def poll_email_replies():
    """Poll Close for new email replies and process them."""
    close_client = CloseClient()

    # Fetch unprocessed email activities
    emails = await close_client.get_activities(
        _type="Email",
        direction="incoming",
        date_created__gte=(datetime.utcnow() - timedelta(hours=1)).isoformat()
    )

    for email in emails:
        # Check if already processed
        if await is_email_processed(email["id"]):
            continue

        # Classify reply intent
        classification = await classify_reply(email["body_text"])

        # Route based on classification
        await route_reply(email, classification)

        # Mark as processed
        await mark_email_processed(email["id"])

    return {"processed": len(emails)}
```

#### Task 4C: advance_sequences (bug-hive agent)
**Lines**: 438-569
**Purpose**: Advance contacts through multi-touch sequences

**Implementation:**
```python
@celery.task(name="advance_sequences")
async def advance_sequences():
    """Advance sequence enrollments to next step."""
    supabase = get_supabase_client()
    close_client = CloseClient()

    # Get enrollments due for next step
    due_enrollments = await supabase.table("sequence_enrollments")\
        .select("*")\
        .eq("status", "active")\
        .lte("next_step_at", datetime.utcnow().isoformat())\
        .execute()

    for enrollment in due_enrollments.data:
        try:
            # Execute next step via OutreachAgent
            result = await execute_sequence_step(
                enrollment["contact_id"],
                enrollment["sequence_id"],
                enrollment["current_step"]
            )

            # Update enrollment
            await supabase.table("sequence_enrollments").update({
                "current_step": enrollment["current_step"] + 1,
                "next_step_at": calculate_next_step_time(enrollment),
                "last_executed_at": datetime.utcnow().isoformat()
            }).eq("id", enrollment["id"]).execute()

        except Exception as e:
            logger.error(f"Failed to advance {enrollment['id']}: {e}")

    return {"advanced": len(due_enrollments.data)}
```

---

### WORKSTREAM 5: Security Hardening (vozlux agent)
**Agent**: vozlux/feature-voice-learning
**Priority**: HIGH
**Est. Time**: 1 hour

**Tasks:**
1. **Remove test error endpoint** (`backend/app/api/health.py` line 68-76)
2. **Fix CSP headers** (`backend/app/main.py` lines 121-128)
   - Remove `'unsafe-inline'` and `'unsafe-eval'`
3. **Add rate limiting** (install slowapi)
4. **Restrict CORS** to exact production domains

**TDD Approach:**
- Test that `/test-error` returns 404
- Test that CSP header doesn't contain `unsafe-inline`
- Test rate limiting triggers after N requests

---

### WORKSTREAM 6: Bare Exceptions & Code Quality (animation-ip agent)
**Agent**: animation-ip-factory/feature-content-pipeline
**Priority**: HIGH
**Est. Time**: 1 hour

**Files with Bare Exceptions:**
1. `backend/app/services/browserbase_team_scraper.py` (line 549)
2. `backend/app/tasks/agent_tasks.py` (line 1120)
3. `backend/app/api/claude_chat.py` (line 92)

**Fix Pattern:**
```python
# Before
except:
    pass

# After
except Exception as e:
    logger.warning(f"Non-critical error: {e}")
```

**Also Fix:**
- Register pytest marks in `pytest.ini`
- Fix `TestResults.__init__` in mcp_servers/test_mcp_server.py

---

## Review Gates (100% Required)

### Gate 1: Pre-Commit Checks
- [ ] All tests pass: `pytest -x`
- [ ] No OpenAI imports: `grep -r "from openai" backend/` returns empty
- [ ] CVE scan clean: `pip-audit`
- [ ] Type hints verified: `mypy backend/app/`

### Gate 2: Code Review
- [ ] Use `superpowers:requesting-code-review` skill
- [ ] Peer review before merge
- [ ] Security-sensitive changes flagged

### Gate 3: Integration Verification
- [ ] Close CRM write test: create test contact, verify in Close
- [ ] Celery task test: trigger each task, verify side effects
- [ ] Sequence advancement test: enroll test contact, advance manually

### Gate 4: Documentation
- [ ] Update TASK.md with completion
- [ ] Update BACKLOG.md to mark tasks done
- [ ] Update PLANNING.md if architecture changed

---

## Execution Order

```
Phase 1 (Parallel - All Agents):
├── [sales-agent] Workstream 1: Dependencies & CVEs (30 min)
├── [vozlux] Workstream 5: Security Hardening (1 hr)
└── [animation-ip] Workstream 6: Code Quality (1 hr)

Phase 2 (Sequential - After Phase 1):
├── [sales-agent] Workstream 2: OpenAI Violations (2-3 hrs)
└── [sales-agent] Workstream 3: Enable Close Writes (15 min)

Phase 3 (Parallel - 3 Agents):
├── [dealer-scraper] Task 4A: sync_close_activities (1.5 hrs)
├── [cold-reach] Task 4B: poll_email_replies (1.5 hrs)
└── [bug-hive] Task 4C: advance_sequences (1.5 hrs)

Phase 4 (All Agents):
└── Review gates, testing, commit
```

---

## Success Criteria

**By End of Day:**
- [ ] `pytest --collect-only` succeeds (no pandas error)
- [ ] `grep -r "from openai" backend/` returns empty
- [ ] `CLOSE_WRITE_DISABLED=false` in .env
- [ ] All 3 Celery tasks implemented (not stubbed)
- [ ] No bare exceptions in flagged files
- [ ] CVEs fixed (urllib3, Pillow, Jinja2 upgraded)
- [ ] Security hardening complete (CSP, rate limiting)

**Campaign Launch Ready:**
- [ ] Can enroll test contact in sequence
- [ ] Sequence advances on schedule
- [ ] Replies are classified and routed
- [ ] Activities sync from Close to Supabase

---

## Notes

- API keys in .env should be rotated separately (manual process)
- Dec 29 campaign has 1,134 contacts ready for enrollment
- 23,189 dealer-scraper companies waiting for pipeline after blockers fixed
- VLM batch extraction ready to run once pipeline unblocked
