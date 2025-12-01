#!/bin/bash
#
# LinkedIn Enrichment Pipeline Runner
# ====================================
#
# Convenience script to run the LinkedIn enrichment pipeline.
#
# Usage:
#   ./run_linkedin_scrape.sh 10        # Enrich 10 companies
#   ./run_linkedin_scrape.sh 100       # Enrich 100 companies
#   ./run_linkedin_scrape.sh --dry-run # Test without writing
#
# Rate Limits:
#   - ~2 min per company (company scraping)
#   - ~6 min per ATL profile (profile searching)
#   - 10 companies ≈ 20-30 minutes
#   - 100 companies ≈ 4-5 hours
#

set -e

# Change to backend directory
cd "$(dirname "$0")"

# Activate virtual environment
if [ -f "../venv/bin/activate" ]; then
    source ../venv/bin/activate
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
else
    echo "❌ Virtual environment not found"
    exit 1
fi

# Check for required env vars
if [ -z "$BROWSERBASE_API_KEY" ] && [ ! -f "../.env" ]; then
    echo "❌ BROWSERBASE_API_KEY not set and .env not found"
    exit 1
fi

# Default to 10 companies if no argument
LIMIT=${1:-10}

# Check for flags
if [[ "$1" == "--dry-run" ]] || [[ "$2" == "--dry-run" ]]; then
    DRY_RUN="--dry-run"
    echo "🔍 DRY RUN MODE - No writes to Supabase"
else
    DRY_RUN=""
fi

if [[ "$1" == "--all" ]]; then
    LIMIT_ARG="--all"
    echo "⚠️  WARNING: Processing ALL companies without LinkedIn data"
    echo "    This may take many hours and consume significant resources."
    read -p "    Continue? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 0
    fi
else
    LIMIT_ARG="--limit $LIMIT"
    echo "🚀 LinkedIn Enrichment Pipeline"
    echo "   Processing: $LIMIT companies"
fi

# Run the pipeline
echo "   Starting at: $(date)"
echo ""

python run_linkedin_enrichment.py $LIMIT_ARG $DRY_RUN --output "data/linkedin_enrichment_$(date +%Y%m%d_%H%M%S).json"

echo ""
echo "✅ Pipeline complete at: $(date)"
