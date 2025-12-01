# RLS Security Migration - Deployment Checklist

**Migration:** 015_enable_rls_security
**Date:** 2025-12-01
**Status:** READY FOR DEPLOYMENT

---

## Pre-Deployment Checklist

### 1. Review Migration Files
- [ ] Review `/backend/alembic/versions/015_enable_rls_security.py`
- [ ] Review `/backend/alembic/versions/015_enable_rls_security_rollback.sql`
- [ ] Review `AGENT_7_RLS_SECURITY_FIXES_REPORT.md`

### 2. Backup Database
- [ ] Create database backup via Supabase Dashboard
- [ ] Or run: `supabase db dump -f backup_before_rls_$(date +%Y%m%d).sql`
- [ ] Verify backup file is saved and accessible

### 3. Test in Development
- [ ] Apply migration to dev/staging database first
- [ ] Run all 5 verification queries (see report)
- [ ] Test backend API endpoints
- [ ] Verify no authentication errors

---

## Deployment Steps

### Step 1: Apply Migration
```bash
cd /Users/tmk/Desktop/sales-agent/backend
alembic upgrade head
```

**Expected Output:**
```
INFO  [alembic.runtime.migration] Running upgrade 014 -> 015_enable_rls_security
✓ Enabled RLS on 14 tables
✓ Created 14 service role policies
✓ Fixed duplicate close_activities policies
```

### Step 2: Verify RLS Enabled
```sql
-- Connect to Supabase and run:
SELECT tablename, rowsecurity as rls_enabled
FROM pg_tables
WHERE schemaname = 'public'
    AND tablename IN (
        'lead_audit_log', 'scraper_batches', 'scraper_imports',
        'dim_companies', 'dim_contacts', 'dim_users', 'dim_sources',
        'fact_activities', 'fact_opportunities', 'fact_pipeline_stages',
        'fact_enrichments', 're_enrich_queue',
        'close_activities', 'close_opportunities'
    )
ORDER BY tablename;
```

**Expected:** All 14 tables show `rls_enabled = TRUE`

### Step 3: Verify Policies Created
```sql
SELECT tablename, COUNT(*) as policy_count, array_agg(policyname) as policies
FROM pg_policies
WHERE schemaname = 'public'
    AND tablename IN (
        'lead_audit_log', 'scraper_batches', 'scraper_imports',
        'dim_companies', 'dim_contacts', 'dim_users', 'dim_sources',
        'fact_activities', 'fact_opportunities', 'fact_pipeline_stages',
        'fact_enrichments', 're_enrich_queue',
        'close_activities', 'close_opportunities'
    )
GROUP BY tablename
ORDER BY tablename;
```

**Expected:** Each table has exactly 1 policy (table_name_service_all)

### Step 4: Test Application
- [ ] Start backend server
- [ ] Test GET /api/companies (uses dim_companies)
- [ ] Test GET /api/contacts (uses dim_contacts)
- [ ] Test GET /api/activities (uses fact_activities)
- [ ] Verify all responses return data (not empty or errors)
- [ ] Check application logs for RLS errors

### Step 5: Monitor Production
- [ ] Watch application logs for 15 minutes
- [ ] Check Supabase Dashboard > Database Performance
- [ ] Monitor error rates in monitoring tools
- [ ] Verify query latency is <20ms increased

---

## Rollback Procedure (Emergency Only)

### If Issues Occur in Production

**Option 1: Via Alembic**
```bash
cd /Users/tmk/Desktop/sales-agent/backend
alembic downgrade -1
```

**Option 2: Via SQL Script**
```bash
psql -h <supabase_host> -U postgres -d postgres \
  -f backend/alembic/versions/015_enable_rls_security_rollback.sql
```

**Option 3: Via Supabase Dashboard**
1. Go to SQL Editor
2. Paste contents of `015_enable_rls_security_rollback.sql`
3. Execute

### After Rollback
- [ ] Verify RLS is disabled on all 14 tables
- [ ] Test application functionality
- [ ] Investigate root cause of issues
- [ ] Plan re-deployment after fixes

---

## Success Criteria

### Migration Success
- ✅ All 14 tables have RLS enabled
- ✅ All 14 tables have service role policies
- ✅ No duplicate policies exist
- ✅ close_activities duplicate policies removed

### Application Success
- ✅ Backend API endpoints return data
- ✅ No authentication errors in logs
- ✅ Query latency increase <20ms
- ✅ Zero data exposure errors

### Security Success
- ✅ Anonymous users cannot query tables
- ✅ Service role can access all data
- ✅ PostgREST API requires authentication
- ✅ All sensitive data protected

---

## Troubleshooting

### Issue: Migration Fails with "table does not exist"
**Solution:** Some tables may not exist in your database
1. Check which tables exist: `\dt` in psql
2. Comment out missing tables in migration
3. Re-run migration

### Issue: "permission denied for table"
**Solution:** Service role authentication issue
1. Verify Supabase service role key is set
2. Check JWT token includes `role: service_role`
3. Test JWT parsing: `SELECT auth.jwt()`

### Issue: Application returns empty results
**Solution:** RLS blocking legitimate queries
1. Check backend is using service role key
2. Verify policy allows service_role access
3. Test policy: `SET ROLE service_role; SELECT * FROM table;`

### Issue: Query performance degraded
**Solution:** RLS policy overhead
1. Check query latency in Supabase Dashboard
2. Optimize RLS policy if needed
3. Consider caching frequently accessed data

---

## Post-Deployment Actions

### Immediate (First 24 Hours)
- [ ] Monitor application logs hourly
- [ ] Track query latency metrics
- [ ] Watch for error spikes
- [ ] Respond to any user reports

### Short-Term (First Week)
- [ ] Review query performance metrics
- [ ] Check for slow query logs
- [ ] Analyze RLS policy effectiveness
- [ ] Document any issues encountered

### Long-Term (First Month)
- [ ] Analyze security audit compliance
- [ ] Plan next migration (performance indexes)
- [ ] Update documentation with lessons learned
- [ ] Share results with team

---

## Next Migrations Recommended

### Priority 1: Performance Indexes (016)
- Add JSONB GIN indexes
- Add composite indexes
- Optimize materialized view queries
- **Timeline:** 1 week after RLS migration

### Priority 2: Policy Standardization (017)
- Rename all policies to standard format
- Add read-only policies for authenticated users
- **Timeline:** 2 weeks after RLS migration

### Priority 3: Schema Constraints (018)
- Add CHECK constraints
- Add NOT NULL constraints
- Standardize data types
- **Timeline:** 3 weeks after RLS migration

---

## Contact & Support

**Project Owner:** Tim Kipper (tim@coperniq.io)
**Supabase Project:** oyyakkuvvtckocncuwwf (scientiacapital)
**Migration Files:**
- `/backend/alembic/versions/015_enable_rls_security.py`
- `/backend/alembic/versions/015_enable_rls_security_rollback.sql`
- `AGENT_7_RLS_SECURITY_FIXES_REPORT.md`

**Documentation:**
- Full Report: `AGENT_7_RLS_SECURITY_FIXES_REPORT.md`
- Audit Report: `SUPABASE_ISSUES_CATEGORIZED.md`
- Fix SQL: `supabase_fix_migrations.sql`

---

## Final Sign-Off

- [ ] All pre-deployment checks completed
- [ ] Backup created and verified
- [ ] Migration tested in dev/staging
- [ ] Deployment plan reviewed
- [ ] Rollback procedure understood
- [ ] Monitoring plan in place
- [ ] Ready for production deployment

**Deployment Approved By:** ________________
**Date:** ________________
**Time:** ________________

---

**END OF CHECKLIST**
