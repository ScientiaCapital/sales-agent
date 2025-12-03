# Pipeline: End of Day

Comprehensive end-of-day workflow: audit → security → docs → quality → git → tomorrow.

**Usage**: `/pipeline-eod`

---

## Phase 1: Audit Today's Work

### Step 1: Load Context
```
Loading workflow-enforcer + project-context-skill...
```

### Step 2: Review Git Activity
```bash
# Today's commits
git log --oneline --since="midnight"

# Changed files (uncommitted)
git status --short

# Current branch
git branch --show-current
```

### Step 3: Summarize Work
```
Summarize:
- Completed tasks
- Blockers encountered
- Next steps for tomorrow
```

### Gate 1: Audit Review
**Ask:** "Phase 1 complete. Proceed to Phase 2 (Security Sweep)? (yes/no)"

---

## Phase 2: Security Sweep (BEFORE ANY COMMITS)

### Step 1: Secrets Scan
```bash
# API keys (common patterns)
echo "Scanning for secrets..."

# OpenAI keys (FORBIDDEN)
! grep -rn "sk-[a-zA-Z0-9]\{20,\}" --include="*.py" backend/ || {
    echo "ERROR: Possible API key found"; exit 1
}

# AWS keys
! grep -rn "AKIA[A-Z0-9]\{16\}" backend/ || {
    echo "ERROR: AWS key pattern found"; exit 1
}
```

### Step 2: Check .env Protection
```bash
# Ensure .env is gitignored
grep -q "\.env" .gitignore || {
    echo "ERROR: .env not in .gitignore!"; exit 1
}

# Verify no .env files tracked
git ls-files | grep -E "\.env$" && {
    echo "ERROR: .env file is tracked!"; exit 1
} || true
```

### Step 3: Code Security Check
```bash
# Check for dangerous patterns
! grep -rn "eval(" --include="*.py" backend/ || echo "WARNING: eval() usage"
! grep -rn "exec(" --include="*.py" backend/ || echo "WARNING: exec() usage"
! grep -rn "shell=True" --include="*.py" backend/ || echo "WARNING: shell=True"
```

### Gate 2: Security Verification
**Checklist:**
- [ ] No API keys in code
- [ ] .env properly gitignored
- [ ] No dangerous patterns

**On FAIL:** Fix now, note for tomorrow, or abort
**On PASS:** "Phase 2 complete. Proceed to Phase 3 (Update Docs)? (yes/no)"

---

## Phase 3: Update Project Docs

### Step 1: Check Doc Files
```bash
ls -la CLAUDE.md .claude/CLAUDE.md 2>/dev/null || true
```

### Step 2: Update CLAUDE.md
- Update enrichment stats (run `/enrich-status`)
- Note completed features
- Document any new patterns

### Step 3: Update Status Section
```
Current metrics:
- Total Companies: X
- Enriched: Y
- Contacts: Z
```

### Gate 3: Docs Updated
**Ask:** "Phase 3 complete. Proceed to Phase 4 (Code Quality)? (yes/no)"

---

## Phase 4: Code Quality Audit

### Step 1: Lint Check
```bash
cd backend && source ../venv/bin/activate
ruff check app/ --fix 2>/dev/null || true
```

### Step 2: Run Tests
```bash
pytest tests/ -v --tb=short -x
```

### Step 3: Type Check (if configured)
```bash
mypy app/ --ignore-missing-imports 2>/dev/null || echo "mypy skipped"
```

### Gate 4: Quality Verified
**Checklist:**
- [ ] Linter passes
- [ ] Tests pass
- [ ] No critical issues

**Ask:** "Phase 4 complete. Proceed to Phase 5 (Git Sync)? (yes/no)"

---

## Phase 5: Git Cleanup & Sync

### Step 1: Status Check
```bash
echo "=== Git Status ==="
git status

echo "=== Unpushed Commits ==="
git log --oneline @{u}..HEAD 2>/dev/null || echo "No upstream"

echo "=== Stashes ==="
git stash list
```

### Step 2: Commit Changes
If uncommitted changes exist:
```bash
git add .
git commit -m "$(cat <<'EOF'
chore: End of day commit

- [Summary of today's work]

🤖 Generated with [Claude Code](https://claude.com/claude-code)

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```

### Step 3: Push
```bash
git push origin $(git branch --show-current)
```

### Gate 5: Git Synced
**Checklist:**
- [ ] All changes committed
- [ ] All branches pushed
- [ ] Working tree clean

**Ask:** "Phase 5 complete. Proceed to Phase 6 (Final)? (yes/no)"

---

## Phase 6: Final Verification & Tomorrow Context

### Step 1: Final Security Gate (BLOCKING)
```bash
# Must pass
! grep -rn "sk-" --include="*.py" backend/app/ || {
    echo "BLOCKED: Secret found"; exit 1
}

# OpenAI check (project rule)
! grep -rn "OPENAI" --include="*.py" backend/app/ || {
    echo "BLOCKED: OpenAI reference found"; exit 1
}

echo "Security gate PASSED"
```

### Step 2: Final State Verification
```bash
# Clean working tree
if [ -z "$(git status --porcelain)" ]; then
    echo "Working tree: CLEAN"
else
    echo "WARNING: Uncommitted changes remain"
fi
```

### Step 3: Generate Tomorrow Context
```
Tomorrow's Context:

**Start Here:**
- Continue enrichment (3,397 remaining)
- Run: python run_enrichment.py --limit 100

**First Command:**
cd backend && source ../venv/bin/activate
```

### Gate 6: Day Complete
```
=== END OF DAY COMPLETE ===

Summary:
- Commits today: [N]
- Security: PASSED
- Docs: UPDATED
- Git: SYNCED

Tomorrow: Continue enrichment

Have a good evening!
```

---

## Phase Summary

```
Phase 1 (Audit) ──► Gate 1
        │
        ▼
Phase 2 (Security) ──► Gate 2 ◄── CRITICAL
        │
        ▼
Phase 3 (Docs) ──► Gate 3
        │
        ▼
Phase 4 (Quality) ──► Gate 4
        │
        ▼
Phase 5 (Git Sync) ──► Gate 5
        │
        ▼
Phase 6 (Final) ──► Gate 6 ◄── BLOCKING
        │
        ▼
   DAY COMPLETE
```

---

## Critical Rules

- **NO OpenAI** - Cerebras, Claude, DeepSeek only
- **API keys in .env only** - Never hardcode
- **Close CRM is read-only** - `CLOSE_WRITE_DISABLED=True`
