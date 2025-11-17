#!/bin/bash
#
# Full Pipeline Test Script - Runs COMPLETE enrichment pipeline
#
# Pipeline Stages:
# 1. Qualification - Lead scoring + Hunter.io contact discovery
# 2. Close CRM Check - Check for existing ATL contacts
# 3. Enrichment - Apollo/LinkedIn company data enrichment
# 4. Deduplication - Final duplicate check
# 5. Close CRM - Create/update lead with all discovered contacts
#
# This is what you need to find emails and phones for sales outreach!
#

API_URL="http://localhost:8001/api/v1"
CSV_FILE="../companies_ready_to_import.csv"
TOTAL_LEADS=20

echo "🚀 Starting FULL PIPELINE enrichment test..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "🎯 This will:"
echo "   1. Score leads with Cerebras AI"
echo "   2. Discover contact emails via Hunter.io"
echo "   3. Check Close CRM for duplicates"
echo "   4. Enrich company data via Apollo/LinkedIn"
echo "   5. Create leads in Close CRM with ATL contacts"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Counter for processed leads
processed=0
enriched=0
skipped=0
failed=0

# Read CSV and skip header
tail -n +2 "$CSV_FILE" | head -n "$TOTAL_LEADS" | while IFS=',' read -r company_name company_website company_size industry contact_name contact_email contact_phone contact_title notes; do
    # Clean fields (remove quotes)
    company_name=$(echo "$company_name" | tr -d '"')
    company_website=$(echo "$company_website" | tr -d '"')

    # Extract domain from website URL
    domain=$(echo "$company_website" | sed 's|https\?://||' | sed 's|www\.||' | sed 's|/.*||')

    echo "📊 Processing: $company_name"
    echo "   Website: $company_website"

    # Call FULL PIPELINE endpoint (not just /qualify!)
    response=$(curl -s -X POST "$API_URL/leads/test-pipeline" \
        -H "Content-Type: application/json" \
        -d "{
            \"lead\": {
                \"name\": \"$company_name\",
                \"company\": \"$company_name\",
                \"website\": \"$company_website\",
                \"domain\": \"$domain\",
                \"industry\": \"HVAC/Generator Services\",
                \"notes\": \"ATL HVAC contractor from dealer scraper\"
            },
            \"options\": {
                \"stop_on_duplicate\": false,
                \"skip_enrichment\": false,
                \"create_in_crm\": true,
                \"dry_run\": false
            }
        }" 2>&1)

    # Parse response
    success=$(echo "$response" | jq -r '.success // false')
    score=$(echo "$response" | jq -r '.stages.qualification.output.qualification_score // 0')

    # Check for enrichment results
    enrichment_status=$(echo "$response" | jq -r '.stages.enrichment.status // "unknown"')

    # Check for discovered contacts from Hunter.io
    discovered_contacts=$(echo "$response" | jq -r '.stages.qualification.output.metadata.discovered_contacts // [] | length')

    # Check Close CRM creation
    crm_status=$(echo "$response" | jq -r '.stages.close_crm.status // "unknown"')
    contacts_created=$(echo "$response" | jq -r '.stages.close_crm.output.contacts_created // 0')

    if [ "$success" = "true" ]; then
        if [ "$discovered_contacts" -gt 0 ]; then
            echo "   ✅ Score: $score | Hunter Contacts: $discovered_contacts | CRM Contacts: $contacts_created"
            ((enriched++))
        else
            echo "   ⚠️  Score: $score | No contacts found"
            ((skipped++))
        fi
    else
        error=$(echo "$response" | jq -r '.error_message // "Unknown error"')
        echo "   ❌ Failed: $error"
        ((failed++))
    fi

    ((processed++))
    echo ""
done

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Full pipeline test complete!"
echo ""
echo "📈 Results:"
echo "   Total Processed: $processed"
echo "   ✅ Enriched with contacts: $enriched"
echo "   ⚠️  No contacts found: $skipped"
echo "   ❌ Failed: $failed"
echo ""
echo "📊 Next steps:"
echo "   1. Check Close CRM for new leads with ATL contacts"
echo "   2. Review Hunter.io contact quality"
echo "   3. Start calling hot prospects! 📞🔥"
echo ""
