# Supervised Enrichment

Interactive enrichment with manual checkpoints.

**Usage**: `/enrich-supervised [--budget 5.00] [--batch-size 2]`

---

## Quick Start

```bash
cd backend && source ../venv/bin/activate
python run_supervised_enrichment.py --budget 5.0 --batch-size 2
```

---

## Controls

| Key | Action |
|-----|--------|
| `c` | Continue to next batch |
| `s` | Stop and save progress |
| `v` | View detailed results |
| `q` | Quit immediately |

---

## Cost Estimates

| Service | Cost |
|---------|------|
| Website scrape | $0.03/company |
| Hunter.io | $0.01/email |
| **Typical total** | $0.05-0.15/company |

---

## When to Use

- Verifying enrichment quality
- Testing new extraction logic
- Processing high-value leads manually
