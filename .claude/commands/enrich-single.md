# Single Lead Enrichment

Enrich one company by domain.

**Usage**: `/enrich-single [domain]`

---

## Quick Start

```bash
cd backend && source ../venv/bin/activate
python run_enrichment.py --domain example.com
```

---

## What Gets Extracted

| Data | Source |
|------|--------|
| ATL Contacts | Website team/about pages |
| BTL Contacts | Technicians, installers |
| Emails | Hunter.io lookup |
| Phone Numbers | Website scraping |
| OEM Brands | 100+ brand detection |
| Service Areas | Cities served |

---

## Output

Results saved to Supabase `dim_companies`:
- `last_enriched_at` - Timestamp
- `atl_contacts` - Decision makers found
- `btl_contacts` - Staff found
- `oem_brands` - Brands detected
- `service_areas` - Cities served
