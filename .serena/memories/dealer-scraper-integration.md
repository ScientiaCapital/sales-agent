# Dealer-Scraper Integration

## Overview
Bridge between dealer-scraper-mvp (contractor discovery) and sales-agent (enrichment + qualification).

## CSV File Location
```
/Users/tmkipper/Desktop/dealer-scraper-mvp/output/
├── top_200_prospects_final_20251029.csv (100K) - PRIMARY TARGET
├── gold_tier_prospects_20251029.csv (26K)
├── silver_tier_prospects_20251029.csv (3.8M)
├── bronze_tier_prospects_20251029.csv (24K)
└── icp_scored_contractors_final_20251029.csv (3.8M) - Full list
```

## CSV Schema (60+ Fields)
**Core Identifiers**:
- name, phone, domain, website, email

**ICP Scoring**:
- ICP_Score (0-100)
- ICP_Tier (Gold/Silver/Bronze)
- OEM_Count, OEMs_Certified

**Capabilities**:
- has_hvac, has_solar, has_inverters, has_battery, has_generator
- has_plumbing, has_roofing, has_electrical
- has_ops_maintenance (O&M capability)

**Business Intelligence**:
- Resimercial_Score (residential + commercial)
- MultiOEM_Score (multi-OEM certification)
- MEPR_Score (MEP + Resimercial)
- OM_Score (operations & maintenance)

**Company Data**:
- employee_count, capability_count, estimated_revenue
- is_mep_contractor, is_self_performing, is_sub, is_gc

**Enrichment**:
- apollo_enriched (boolean)
- linkedin_url
- certifications (JSON)

**Location**:
- street, city, state, zip
- distance_miles (from target zip)

## Import Workflow

### Step 1: CSV Import
```bash
POST /api/v1/leads/import/csv
Content-Type: multipart/form-data
```
**Performance**: 1,000 leads in ~4 seconds using PostgreSQL COPY

### Step 2: Field Mapping
```python
# CSV → PostgreSQL leads table
name → company_name
domain → website
email → contact_email
ICP_Score → qualification_score (initial)
linkedin_url → enrichment_metadata['linkedin_url']
```

### Step 3: Enrichment Pipeline
1. **LinkedIn Scraper** (Browserbase) - ATL contact discovery
2. **EnrichmentAgent** (ReAct) - Orchestrate tools + merge data
3. **QualificationAgent** (Cerebras) - Generate final scores

### Step 4: Storage
```sql
-- Leads table
INSERT INTO leads (company_name, website, contact_email, qualification_score, enrichment_status)

-- Enriched contacts
INSERT INTO crm_contacts (crm_platform='linkedin', external_id, email, enrichment_data)

-- API call tracking
INSERT INTO cerebras_api_calls (lead_id, latency_ms, cost, tokens)
```

## Enrichment Status Tracking
```python
enrichment_status = "pending" | "in_progress" | "completed" | "failed"
```

## Expected Volumes
- Top 200 list: ~2 minutes for full enrichment + qualification
- Gold tier (26K): ~8 hours
- Full list (3.8M): ~48 hours with rate limiting

## Cost Estimates
**Per Lead**:
- Cerebras qualification: $0.000006
- LinkedIn scraping: Free (Browserbase within limits)
- Apollo enrichment: DISABLED (no API access)

**Top 200**:
- Total cost: ~$0.0012
- Total time: ~2 minutes
