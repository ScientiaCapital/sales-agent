#!/bin/bash
# Quick API test for first contractor

curl -X POST http://localhost:8001/api/v1/pipeline/test \
  -H "Content-Type: application/json" \
  -d '{
    "lead": {
      "name": "ACS COMMERCIAL SERVICES LLC",
      "company_name": "ACS COMMERCIAL SERVICES LLC",
      "website": "https://acsfixit.com",
      "phone": "(281) 885-3300",
      "company_size": "50-100",
      "industry": "Commercial HVAC/Electrical",
      "state": "TX",
      "city": "Houston"
    },
    "options": {
      "skip_enrichment": false,
      "create_in_crm": false,
      "stop_on_duplicate": false,
      "dry_run": true
    }
  }' | python3 -m json.tool
