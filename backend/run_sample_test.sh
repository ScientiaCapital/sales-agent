#!/bin/bash
# Process 20 HVAC contractors through enrichment pipeline

set -e

CSV_FILE="data/csv/inbox/hvac_contractors_formatted.csv"
API_URL="http://localhost:8001/api/v1"

# Change to backend directory
cd "$(dirname "$0")"

echo "🚀 Starting pipeline enrichment test..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Read CSV and process each company
tail -n +2 "$CSV_FILE" | head -20 | while IFS=, read -r company_name domain industry revenue_band notes; do
    # Remove quotes from fields
    company_name=$(echo "$company_name" | tr -d '"')
    domain=$(echo "$domain" | tr -d '"')
    industry=$(echo "$industry" | tr -d '"')

    echo "📊 Processing: $company_name"
    echo "   Domain: $domain"
    echo ""

    # Trigger qualification
    response=$(curl -s -X POST "$API_URL/leads/qualify" \
        -H "Content-Type: application/json" \
        -d "{
            \"company_name\": \"$company_name\",
            \"company_website\": \"$domain\",
            \"industry\": \"$industry\",
            \"notes\": \"HVAC contractor\"
        }" 2>&1)

    # Check if qualification succeeded
    if echo "$response" | grep -q '"qualification_score"'; then
        score=$(echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('qualification_score', 0))")
        atl=$(echo "$response" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('is_atl', False))")
        echo "   ✅ Score: $score | ATL: $atl"
    else
        echo "   ❌ Qualification failed"
        echo "$response" | head -3
    fi

    echo ""
    sleep 1  # Rate limiting
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Pipeline test complete!"
echo ""
echo "📈 Next steps:"
echo "   1. Check Close CRM smart views for new leads"
echo "   2. Review enrichment quality"
echo "   3. Generate KPI dashboard"
