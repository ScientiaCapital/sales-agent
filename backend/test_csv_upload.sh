#!/bin/bash
# Test CSV upload and processing workflow

API_BASE="http://localhost:8001/api/v1"
CSV_FILE="test_leads_sample.csv"

echo "============================================"
echo "CSV Upload Test Script"
echo "============================================"
echo ""

# Check if server is running
echo "1. Checking if server is running..."
if ! curl -s "${API_BASE}/health" > /dev/null; then
    echo "ERROR: Server is not running at ${API_BASE}"
    echo "Please start the server with: python start_server.py"
    exit 1
fi
echo "✓ Server is running"
echo ""

# Upload CSV
echo "2. Uploading CSV file: ${CSV_FILE}"
UPLOAD_RESPONSE=$(curl -s -X POST "${API_BASE}/leads/import/csv" \
  -F "file=@${CSV_FILE}")

echo "Upload Response:"
echo "$UPLOAD_RESPONSE" | jq .
echo ""

# Extract import_id
IMPORT_ID=$(echo "$UPLOAD_RESPONSE" | jq -r '.import_id')

if [ "$IMPORT_ID" == "null" ] || [ -z "$IMPORT_ID" ]; then
    echo "ERROR: Failed to upload CSV"
    exit 1
fi

echo "✓ CSV uploaded successfully (Import ID: $IMPORT_ID)"
echo ""

# Poll for status
echo "3. Polling for processing status..."
echo "(Press Ctrl+C to stop)"
echo ""

MAX_POLLS=30
POLL_COUNT=0
POLL_INTERVAL=5  # seconds

while [ $POLL_COUNT -lt $MAX_POLLS ]; do
    STATUS_RESPONSE=$(curl -s "${API_BASE}/leads/import/${IMPORT_ID}/status")

    STATUS=$(echo "$STATUS_RESPONSE" | jq -r '.status')
    PROGRESS=$(echo "$STATUS_RESPONSE" | jq -r '.progress_percent')
    PROCESSED=$(echo "$STATUS_RESPONSE" | jq -r '.processed_rows')
    TOTAL=$(echo "$STATUS_RESPONSE" | jq -r '.total_rows')
    COST=$(echo "$STATUS_RESPONSE" | jq -r '.total_cost_usd')

    echo "[$(date '+%H:%M:%S')] Status: $STATUS | Progress: ${PROGRESS}% | Processed: ${PROCESSED}/${TOTAL} | Cost: \$${COST}"

    # Check if completed or failed
    if [ "$STATUS" == "completed" ]; then
        echo ""
        echo "============================================"
        echo "✓ CSV PROCESSING COMPLETED"
        echo "============================================"
        echo ""
        echo "Final Results:"
        echo "$STATUS_RESPONSE" | jq .
        echo ""
        echo "Total Cost: \$${COST}"
        exit 0
    fi

    if [ "$STATUS" == "failed" ]; then
        echo ""
        echo "============================================"
        echo "✗ CSV PROCESSING FAILED"
        echo "============================================"
        echo ""
        echo "Error Details:"
        echo "$STATUS_RESPONSE" | jq .
        exit 1
    fi

    # Wait before next poll
    sleep $POLL_INTERVAL
    POLL_COUNT=$((POLL_COUNT + 1))
done

echo ""
echo "Timeout: Processing took longer than expected"
echo "Check status manually with:"
echo "curl ${API_BASE}/leads/import/${IMPORT_ID}/status"
