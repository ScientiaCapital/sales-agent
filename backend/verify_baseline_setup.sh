#!/bin/bash

# Baseline Metrics System - Verification Script
# =============================================
# Verifies that all baseline components are properly installed
# and ready for execution

echo ""
echo "================================================================================"
echo "BASELINE METRICS SYSTEM - SETUP VERIFICATION"
echo "================================================================================"
echo ""

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

CHECKS_PASSED=0
CHECKS_FAILED=0

# Helper functions
check_file() {
    local file=$1
    local description=$2

    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $description"
        ((CHECKS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $description - MISSING: $file"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_directory() {
    local dir=$1
    local description=$2

    if [ -d "$dir" ]; then
        echo -e "${GREEN}✓${NC} $description"
        ((CHECKS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $description - MISSING: $dir"
        ((CHECKS_FAILED++))
        return 1
    fi
}

check_python_module() {
    local module=$1
    local description=$2

    if python3 -c "import $module" 2>/dev/null; then
        echo -e "${GREEN}✓${NC} $description"
        ((CHECKS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} $description - Module not installed: $module"
        ((CHECKS_FAILED++))
        return 1
    fi
}

# Start checks
echo "1. Checking Python Scripts..."
echo "   ─────────────────────────────────────────────────────────────"

check_file "generate_baseline_metrics.py" "Main metrics generator script"
check_file "compare_baseline_metrics.py" "Comparison tool script"

echo ""
echo "2. Checking Documentation Files..."
echo "   ─────────────────────────────────────────────────────────────"

check_file "BASELINE_QUICK_START.md" "Quick start guide"
check_file "BASELINE_EXECUTION_CHECKLIST.md" "Execution checklist"
check_file "BASELINE_METRICS_README.md" "Full documentation"
check_file "BASELINE_IMPLEMENTATION_SUMMARY.md" "Implementation summary"
check_file "BASELINE_METRICS_INDEX.md" "Master index"

echo ""
echo "3. Checking Directory Structure..."
echo "   ─────────────────────────────────────────────────────────────"

check_directory "data" "Data output directory"

echo ""
echo "4. Checking Python Requirements..."
echo "   ─────────────────────────────────────────────────────────────"

# Check Python version
PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
echo "Python version: $PYTHON_VERSION"

if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' 2>/dev/null; then
    echo -e "${GREEN}✓${NC} Python 3.9 or higher"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}✗${NC} Python 3.9 or higher required (found: $PYTHON_VERSION)"
    ((CHECKS_FAILED++))
fi

check_python_module "supabase" "Supabase client library"
check_python_module "dotenv" "Python dotenv library"

echo ""
echo "5. Checking Environment Configuration..."
echo "   ─────────────────────────────────────────────────────────────"

# Check .env file
if [ -f "../.env" ]; then
    echo -e "${GREEN}✓${NC} .env file exists"
    ((CHECKS_PASSED++))

    # Check for required credentials
    if grep -q "SUPABASE_URL" "../.env"; then
        echo -e "${GREEN}✓${NC} SUPABASE_URL configured"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} SUPABASE_URL not found in .env"
        ((CHECKS_FAILED++))
    fi

    if grep -q "SUPABASE_SERVICE_KEY" "../.env"; then
        echo -e "${GREEN}✓${NC} SUPABASE_SERVICE_KEY configured"
        ((CHECKS_PASSED++))
    else
        echo -e "${RED}✗${NC} SUPABASE_SERVICE_KEY not found in .env"
        ((CHECKS_FAILED++))
    fi
else
    echo -e "${RED}✗${NC} .env file not found"
    ((CHECKS_FAILED++))
fi

echo ""
echo "6. Checking File Permissions..."
echo "   ─────────────────────────────────────────────────────────────"

# Check if scripts are readable
if [ -r "generate_baseline_metrics.py" ]; then
    echo -e "${GREEN}✓${NC} generate_baseline_metrics.py is readable"
    ((CHECKS_PASSED++))
else
    echo -e "${YELLOW}⚠${NC} generate_baseline_metrics.py may not be readable"
fi

if [ -r "compare_baseline_metrics.py" ]; then
    echo -e "${GREEN}✓${NC} compare_baseline_metrics.py is readable"
    ((CHECKS_PASSED++))
else
    echo -e "${YELLOW}⚠${NC} compare_baseline_metrics.py may not be readable"
fi

# Check if data directory is writable
if [ -w "data" ]; then
    echo -e "${GREEN}✓${NC} data/ directory is writable"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}✗${NC} data/ directory is not writable"
    ((CHECKS_FAILED++))
fi

echo ""
echo "7. Checking Supabase Connectivity..."
echo "   ─────────────────────────────────────────────────────────────"

# Test connection silently
python3 << 'EOF' 2>/dev/null
import os
import sys
from dotenv import load_dotenv
from pathlib import Path

env_file = Path(__file__).parent.parent / '.env'
load_dotenv(env_file, override=True)

try:
    from supabase import create_client
    url = os.getenv('SUPABASE_URL')
    key = os.getenv('SUPABASE_SERVICE_KEY')

    if not url or not key:
        print("ERROR: Missing Supabase credentials")
        sys.exit(1)

    # Try to create client (doesn't actually connect yet)
    client = create_client(url, key)
    print("SUCCESS")
except Exception as e:
    print(f"ERROR: {e}")
    sys.exit(1)
EOF

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓${NC} Supabase client can be instantiated"
    ((CHECKS_PASSED++))
else
    echo -e "${RED}✗${NC} Supabase connection test failed"
    ((CHECKS_FAILED++))
fi

echo ""
echo "================================================================================"
echo "VERIFICATION SUMMARY"
echo "================================================================================"
echo ""

echo -e "Checks Passed:  ${GREEN}$CHECKS_PASSED${NC}"
echo -e "Checks Failed:  ${RED}$CHECKS_FAILED${NC}"
echo ""

if [ $CHECKS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ ALL CHECKS PASSED - System is ready!${NC}"
    echo ""
    echo "Next steps:"
    echo "  1. Read: BASELINE_QUICK_START.md"
    echo "  2. Run: python generate_baseline_metrics.py"
    echo "  3. Review: cat data/BASELINE_METRICS_20251215.md"
    echo ""
    exit 0
else
    echo -e "${RED}✗ SOME CHECKS FAILED - Please fix issues above${NC}"
    echo ""
    echo "Common fixes:"
    echo "  - Missing dependencies: pip install -r requirements.txt"
    echo "  - Missing .env: cp ../. env.example ../.env (then edit)"
    echo "  - Missing data dir: mkdir -p data"
    echo "  - Permission issues: chmod 755 data/"
    echo ""
    exit 1
fi
