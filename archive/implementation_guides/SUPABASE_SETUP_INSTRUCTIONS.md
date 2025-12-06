# Supabase CLI Setup & Authentication Instructions

## Current Status

✅ **Completed:**
- Supabase CLI installed (v2.62.10)
- Migration files analyzed (7 migrations found)
- Issues report generated (113+ issues identified)

⏳ **Pending:**
- Authentication (requires access token)
- Project link
- Live database queries

---

## Quick Start: Authentication

### Option 1: Environment Variable (Recommended)

1. Get your access token from Supabase Dashboard:
   - Go to: https://app.supabase.com/account/tokens
   - Click "Generate new token"
   - Give it a name (e.g., "sales-agent-cli")
   - Copy the token

2. Set environment variable:
   ```bash
   export SUPABASE_ACCESS_TOKEN="sbp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
   ```

3. Link to project:
   ```bash
   cd /Users/tmk/Desktop/sales-agent
   supabase link --project-ref oyyakkuvvtckocncuwwf
   ```

4. Verify connection:
   ```bash
   supabase projects list
   ```

### Option 2: Direct Token Login

```bash
supabase login --token sbp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
supabase link --project-ref oyyakkuvvtckocncuwwf
```

### Option 3: Add to .env File

Add to `/Users/tmk/Desktop/sales-agent/.env`:
```bash
# Supabase Configuration
SUPABASE_ACCESS_TOKEN=sbp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SUPABASE_URL=https://oyyakkuvvtckocncuwwf.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here
SUPABASE_DATABASE_URL=postgresql://postgres:[password]@db.oyyakkuvvtckocncuwwf.supabase.co:5432/postgres
```

---

## Post-Authentication Steps

### 1. Pull Current Schema
```bash
cd /Users/tmk/Desktop/sales-agent
supabase db pull
```
This creates `supabase/schema.sql` with your current database state.

### 2. Run Audit Queries

Create audit query file:
```bash
cat > /tmp/audit_queries.sql << 'EOF'
-- Tables without RLS
SELECT schemaname, tablename, rowsecurity as rls_enabled
FROM pg_tables
WHERE schemaname = 'public' AND rowsecurity = FALSE
ORDER BY tablename;

-- Duplicate policies
SELECT schemaname, tablename, policyname, COUNT(*) as count
FROM pg_policies
WHERE schemaname = 'public'
GROUP BY schemaname, tablename, policyname
HAVING COUNT(*) > 1;

-- Multiple permissive policies
SELECT schemaname, tablename, cmd, roles,
       COUNT(*) as policy_count, array_agg(policyname) as policies
FROM pg_policies
WHERE schemaname = 'public' AND permissive = 'PERMISSIVE'
GROUP BY schemaname, tablename, roles, cmd
HAVING COUNT(*) > 1;
EOF
```

Execute queries:
```bash
supabase db execute --file /tmp/audit_queries.sql
```

### 3. Create Fix Migrations

Generate migration files:
```bash
# Fix RLS policies
supabase migration new fix_missing_rls_policies

# Add missing indexes
supabase migration new add_performance_indexes

# Optimize materialized views
supabase migration new optimize_mv_queries
```

### 4. Apply Critical Fixes

Edit the migration files and add fixes from SUPABASE_ISSUES_CATEGORIZED.md:

**Priority 1 - Enable RLS:**
```sql
-- In: supabase/migrations/[timestamp]_fix_missing_rls_policies.sql

-- Enable RLS on all tables
ALTER TABLE lead_audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE scraper_imports ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_users ENABLE ROW LEVEL SECURITY;
ALTER TABLE dim_sources ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_activities ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_opportunities ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_pipeline_stages ENABLE ROW LEVEL SECURITY;
ALTER TABLE fact_enrichments ENABLE ROW LEVEL SECURITY;
ALTER TABLE re_enrich_queue ENABLE ROW LEVEL SECURITY;

-- Create service role policies
CREATE POLICY "lead_audit_log_service_access" ON lead_audit_log
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "scraper_batches_service_access" ON scraper_batches
  FOR ALL TO service_role USING (TRUE) WITH CHECK (TRUE);

-- ... (add for all tables)
```

**Priority 2 - Add JSONB Indexes:**
```sql
-- In: supabase/migrations/[timestamp]_add_performance_indexes.sql

-- JSONB indexes
CREATE INDEX idx_dim_companies_oem_brands ON dim_companies USING GIN (oem_brands);
CREATE INDEX idx_dim_companies_license_types ON dim_companies USING GIN (license_types);
CREATE INDEX idx_scraper_imports_oem_brands ON scraper_imports USING GIN (oem_brands);
CREATE INDEX idx_scraper_imports_license_types ON scraper_imports USING GIN (license_types);

-- Composite indexes
CREATE INDEX idx_dim_companies_tier_score ON dim_companies(icp_tier, icp_score DESC);
CREATE INDEX idx_lead_state_stage_attention ON lead_current_state(current_stage, needs_attention);
```

### 5. Push Migrations

Test locally first (if you have local Supabase):
```bash
supabase db reset  # Reset local database
```

Push to production:
```bash
supabase db push
```

---

## Verification Checklist

After applying fixes, verify:

### 1. RLS Status
```bash
supabase db execute --sql "
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
ORDER BY tablename;
"
```

Expected: All tables should have `rowsecurity = true`

### 2. Policy Count
```bash
supabase db execute --sql "
SELECT tablename, COUNT(*) as policy_count
FROM pg_policies
WHERE schemaname = 'public'
GROUP BY tablename
ORDER BY tablename;
"
```

Expected: All tables should have at least 1 policy

### 3. Index Status
```bash
supabase db execute --sql "
SELECT tablename, indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND indexname LIKE 'idx_%'
ORDER BY tablename, indexname;
"
```

Expected: Should see new JSONB and composite indexes

### 4. Materialized View Refresh
```bash
supabase db execute --sql "
SELECT refresh_star_schema_views();
SELECT COUNT(*) FROM mv_icp_gold_leads;
SELECT COUNT(*) FROM mv_bdr_work_queue;
"
```

Expected: Views should refresh without errors

---

## Troubleshooting

### Issue: "Access token not provided"
```bash
# Solution: Set token explicitly
export SUPABASE_ACCESS_TOKEN="your_token_here"
```

### Issue: "Project not found"
```bash
# Solution: Verify project ref
supabase projects list
# Should show project: oyyakkuvvtckocncuwwf
```

### Issue: "Permission denied"
```bash
# Solution: Check token permissions
# Token needs: Database, API, and Management access
# Generate new token with full permissions
```

### Issue: "Already linked to different project"
```bash
# Solution: Unlink first
supabase unlink
supabase link --project-ref oyyakkuvvtckocncuwwf
```

---

## Key Files

| File | Location | Purpose |
|------|----------|---------|
| Issues Report | `/Users/tmk/Desktop/sales-agent/SUPABASE_ISSUES_CATEGORIZED.md` | Detailed analysis of 113+ issues |
| Setup Instructions | `/Users/tmk/Desktop/sales-agent/SUPABASE_SETUP_INSTRUCTIONS.md` | This file |
| Migrations | `/Users/tmk/Desktop/sales-agent/supabase/migrations/` | Database migration files |
| Schema | `/Users/tmk/Desktop/sales-agent/supabase/schema.sql` | Generated after `db pull` |

---

## Quick Commands Reference

```bash
# Check CLI version
supabase --version

# Login
supabase login --token YOUR_TOKEN

# Link project
supabase link --project-ref oyyakkuvvtckocncuwwf

# Pull schema
supabase db pull

# Execute SQL file
supabase db execute --file migration.sql

# Execute SQL string
supabase db execute --sql "SELECT * FROM dim_companies LIMIT 5;"

# Create new migration
supabase migration new fix_name

# Push migrations
supabase db push

# View project info
supabase projects list

# Unlink project
supabase unlink
```

---

## Next Actions

1. ✅ **Read this document**
2. 🔄 **Get Supabase access token** from https://app.supabase.com/account/tokens
3. 🔄 **Authenticate** using Option 1, 2, or 3 above
4. 🔄 **Run audit queries** to get live database state
5. 🔄 **Create fix migrations** for critical issues
6. 🔄 **Test and apply migrations**
7. 🔄 **Verify fixes** using verification checklist

---

**Need Help?**
- Supabase Docs: https://supabase.com/docs/guides/cli
- Migration Guide: https://supabase.com/docs/guides/cli/local-development
- RLS Guide: https://supabase.com/docs/guides/auth/row-level-security

**Project Info:**
- Project ID: oyyakkuvvtckocncuwwf
- Account: scientiacapital
- Region: Check Supabase dashboard
- Database: PostgreSQL 15+ (Supabase managed)
