#!/bin/bash

###############################################################################
# Deep Scrape Test Script
###############################################################################
# Tests the deep scrape on 10 companies before running full production scrape
#
# Usage:
#   bash backend/test_deep_scrape.sh
#   ./backend/test_deep_scrape.sh  # if executable
#
# Prerequisites:
#   - Run validation: python backend/validate_deep_scrape_prerequisites.py
#   - Phase 2 must be complete (enriched company data available)
###############################################################################

set -e  # Exit on any error

echo "============================================================"
echo "DEEP SCRAPE TEST (10 Companies)"
echo "============================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment is activated
if [[ -z "$VIRTUAL_ENV" ]]; then
    echo -e "${YELLOW}⚠ Virtual environment not activated${NC}"
    echo "Activating venv..."
    source venv/bin/activate || {
        echo -e "${RED}✗ Failed to activate virtual environment${NC}"
        exit 1
    }
fi

echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Check if validation passed
echo "Running prerequisites validation..."
python backend/validate_deep_scrape_prerequisites.py
validation_exit_code=$?

if [ $validation_exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ All prerequisites met${NC}"
elif [ $validation_exit_code -eq 2 ]; then
    echo -e "${YELLOW}⚠ Validation passed with warnings - continuing test${NC}"
else
    echo -e "${RED}✗ Validation failed - cannot proceed${NC}"
    exit 1
fi

echo ""
echo "============================================================"
echo "Starting Deep Scrape Test (10 companies)..."
echo "============================================================"
echo ""
echo "Expected duration: ~2-5 minutes"
echo "Output: backend/data/final_enrichment_output/DEEP_SCRAPE_10_*.csv"
echo ""

# Run deep scrape in test mode (10 companies)
python backend/deep_scrape_companies.py --top 10

scrape_exit_code=$?

echo ""
echo "============================================================"

if [ $scrape_exit_code -eq 0 ]; then
    echo -e "${GREEN}✓ TEST SCRAPE COMPLETED SUCCESSFULLY${NC}"
    echo "============================================================"
    echo ""
    echo "Output files:"
    ls -lh backend/data/final_enrichment_output/DEEP_SCRAPE_10_* 2>/dev/null || {
        echo -e "${YELLOW}⚠ No output files found (check if companies were processed)${NC}"
    }
    echo ""
    echo "Next steps:"
    echo "1. Review output file: backend/data/final_enrichment_output/DEEP_SCRAPE_10_*.csv"
    echo "2. Verify data quality (ATL contacts, phones, emails)"
    echo "3. If satisfied, proceed with full scrape:"
    echo "   python backend/deep_scrape_companies.py --top 1000"
else
    echo -e "${RED}✗ TEST SCRAPE FAILED${NC}"
    echo "============================================================"
    echo ""
    echo "Check logs in: backend/logs/"
    echo "Most recent log:"
    ls -t backend/logs/deep_scrape_*.log 2>/dev/null | head -1 | xargs -I {} echo "  {}"
    exit 1
fi

echo "============================================================"
