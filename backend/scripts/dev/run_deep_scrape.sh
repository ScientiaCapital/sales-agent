#!/bin/bash
# ====================================================
# DEEP SCRAPE RUNNER
# ====================================================
# Scrapes company websites + LinkedIn for ATL/BTL contacts
#
# Usage:
#   ./run_deep_scrape.sh          # Top 1000 companies (full run ~8 hours)
#   ./run_deep_scrape.sh 100      # Top 100 companies (test ~1 hour)
#   ./run_deep_scrape.sh 10       # Quick test with 10 companies (~15 min)
#
# Output: backend/data/final_enrichment_output/DEEP_SCRAPE_*.csv
# ====================================================

set -e

cd "$(dirname "$0")/backend"

# Activate virtual environment
source ../venv/bin/activate

# Default to 1000 companies if no argument
COUNT=${1:-1000}

echo "=============================================="
echo "DEEP SCRAPE - Processing TOP $COUNT companies"
echo "=============================================="
echo ""
echo "This will scrape:"
echo "  - Company website (landing, team, about, contact pages)"
echo "  - LinkedIn company page (employee count, visible employees)"
echo ""
echo "Data extracted:"
echo "  - ATL contacts (CEO, Owner, President, VP, Director)"
echo "  - BTL contacts (Managers, Coordinators)"
echo "  - Phone numbers (with source)"
echo "  - Email addresses"
echo "  - Company addresses"
echo ""
echo "Estimated time: ~$((COUNT * 30 / 60)) minutes"
echo "=============================================="
echo ""

# Run the deep scraper
python deep_scrape_companies.py --top $COUNT --concurrent 10

echo ""
echo "=============================================="
echo "DEEP SCRAPE COMPLETE"
echo "=============================================="
echo ""
echo "Output files:"
ls -la data/final_enrichment_output/DEEP_SCRAPE_*.csv 2>/dev/null | tail -3
echo ""
echo "Close CRM Export (for Tim to import manually):"
ls -la data/final_enrichment_output/CLOSE_CRM_IMPORT_*.csv 2>/dev/null | tail -3
echo ""
echo "Next step: Review CLOSE_CRM_IMPORT_*.csv and import into Close CRM"
