-- =============================================================================
-- Migration 009 Rollback: Restore Original Duplicate Policies
-- Created: 2025-12-01
-- Purpose: Rollback the policy consolidation to original state
-- Warning: This will restore the duplicate policy issue!
-- =============================================================================

-- =============================================================================
-- SECTION 1: close_activities - Restore Duplicate Policies
-- =============================================================================
DROP POLICY IF EXISTS "close_activities_service_all" ON close_activities;

-- Restore original policies from migrations 002 and 003
CREATE POLICY "Service role full access" ON close_activities
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

CREATE POLICY "Service role access" ON close_activities
    FOR ALL USING (true);

-- =============================================================================
-- SECTION 2: list_imports - Restore Original Generic Policy
-- =============================================================================
DROP POLICY IF EXISTS "list_imports_service_all" ON list_imports;
CREATE POLICY "Service role full access" ON list_imports
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- =============================================================================
-- SECTION 3: lead_current_state - Restore Original Generic Policy
-- =============================================================================
DROP POLICY IF EXISTS "lead_current_state_service_all" ON lead_current_state;
CREATE POLICY "Service role full access" ON lead_current_state
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- =============================================================================
-- SECTION 4: pipeline_alerts - Restore Original Generic Policy
-- =============================================================================
DROP POLICY IF EXISTS "pipeline_alerts_service_all" ON pipeline_alerts;
CREATE POLICY "Service role full access" ON pipeline_alerts
    FOR ALL USING (TRUE) WITH CHECK (TRUE);

-- =============================================================================
-- SECTION 5: close_opportunities - Restore Original Generic Policy
-- =============================================================================
DROP POLICY IF EXISTS "close_opportunities_service_all" ON close_opportunities;
CREATE POLICY "Service role access" ON close_opportunities
    FOR ALL USING (true);

-- =============================================================================
-- SECTION 6: hot_nurture_leads - Restore Original Generic Policy
-- =============================================================================
DROP POLICY IF EXISTS "hot_nurture_leads_service_all" ON hot_nurture_leads;
CREATE POLICY "Service role access" ON hot_nurture_leads
    FOR ALL USING (true);

-- =============================================================================
-- SECTION 7: icp_gold_leads - Restore Original Generic Policy
-- =============================================================================
DROP POLICY IF EXISTS "icp_gold_leads_service_all" ON icp_gold_leads;
CREATE POLICY "Service role access" ON icp_gold_leads
    FOR ALL USING (true);

-- =============================================================================
-- VERIFICATION: Check duplicate policies are restored
-- =============================================================================
DO $$
DECLARE
    duplicate_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO duplicate_count
    FROM (
        SELECT
            schemaname,
            tablename,
            cmd,
            roles::text,
            COUNT(*) as policy_count
        FROM pg_policies
        WHERE schemaname = 'public'
          AND permissive = 'PERMISSIVE'
          AND tablename IN (
              'close_activities', 'list_imports', 'lead_current_state',
              'pipeline_alerts', 'close_opportunities', 'hot_nurture_leads',
              'icp_gold_leads'
          )
        GROUP BY schemaname, tablename, roles::text, cmd
        HAVING COUNT(*) > 1
    ) duplicates;

    IF duplicate_count > 0 THEN
        RAISE NOTICE 'Rollback successful: Found % duplicate policies (original state)', duplicate_count;
    ELSE
        RAISE WARNING 'Rollback issue: Expected duplicate policies but found none';
    END IF;
END $$;

-- Success message
SELECT 'Migration 009 rolled back successfully' AS status;
