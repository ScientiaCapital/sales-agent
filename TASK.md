# sales-agent - Current Tasks

**Last Updated**: 2025-11-30

---

## Active Work

### In Progress
| Task | PRP | Status |
|------|-----|--------|
| (none) | - | - |

### Up Next (From PROJECT_CONTEXT.md)
| Task | Priority | Est. Effort |
|------|----------|-------------|
| Run Hunter.io Batch 2 (leads 501-1000) | High | ~$5, 30 min |
| Connect dashboard to real Supabase data | High | 2 hours |
| Increase HOT leads (need unique direct phones) | Medium | Ongoing |
| Clean up untracked files (20+ review docs) | Low | 30 min |

---

## Completed (This Session)
- (populated during work)

---

## Blockers
- Close CRM is read-only (`CLOSE_WRITE_DISABLED=True`)

---

## Quick Commands

```bash
# Activate environment
source venv/bin/activate

# Start services
docker-compose up -d                              # PostgreSQL + Redis
python start_server.py                            # API server (port 8001)

# Lead pipeline
python backend/enrich_gold_standard_batch.py --batch 2  # Hunter.io
python backend/sync_gold_standard_to_supabase.py        # Sync to Supabase

# Validation
/validate        # Run all checks
/generate-prp    # Create implementation blueprint
/execute-prp     # Execute a PRP
```

---

## Critical Rules

- **NO OpenAI models** - Use Cerebras, Claude, DeepSeek only
- API keys in `.env` only
- Close CRM read-only
