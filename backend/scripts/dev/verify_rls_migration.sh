#!/bin/bash

# Verification Script for RLS Migration 015
# Run this script to verify all migration files are present and correct

echo "=================================================="
echo "RLS Migration 015 - File Verification"
echo "=================================================="
echo ""

# Check if files exist
echo "Checking migration files..."
echo ""

FILES=(
    "backend/alembic/versions/015_enable_rls_security.py"
    "backend/alembic/versions/015_enable_rls_security_rollback.sql"
    "AGENT_7_RLS_SECURITY_FIXES_REPORT.md"
    "DEPLOYMENT_CHECKLIST_RLS_MIGRATION.md"
)

all_present=true
for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        size=$(wc -c < "$file" | tr -d ' ')
        lines=$(wc -l < "$file" | tr -d ' ')
        echo "✅ $file"
        echo "   Size: $size bytes, Lines: $lines"
    else
        echo "❌ MISSING: $file"
        all_present=false
    fi
done

echo ""
echo "=================================================="
if [ "$all_present" = true ]; then
    echo "✅ All migration files present!"
    echo "=================================================="
    echo ""
    echo "Next Steps:"
    echo "1. Review: cat AGENT_7_RLS_SECURITY_FIXES_REPORT.md"
    echo "2. Backup: supabase db dump -f backup_before_rls.sql"
    echo "3. Deploy: cd backend && alembic upgrade head"
    echo ""
else
    echo "❌ Some files are missing!"
    echo "=================================================="
fi
