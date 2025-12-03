# Supervised Enrichment Pipeline

Start the supervised enrichment pipeline with Claude guidance.

## Usage
```
/enrich-supervised [--budget 5.00] [--batch-size 2]
```

## What This Does

1. Query Supabase for unenriched companies
2. Launch interactive terminal pipeline
3. Process batches with manual checkpoints
4. Guide you through results and next actions

## Execution

```bash
cd backend
source ../venv/bin/activate
python run_supervised_enrichment.py --budget ${BUDGET:-5.0} --batch-size ${BATCH_SIZE:-2}
```

## Controls

| Key | Action |
|-----|--------|
| c | Continue to next batch |
| s | Stop and save progress |
| v | View detailed results |
| q | Quit immediately |

## Budget Guidelines

- Apollo Free: $0.00/company
- LinkedIn scrape: $0.03/company (Browserbase)
- Hunter.io: $0.01/email lookup
- Apollo Paid: ~$1.00/contact (only if needed)

Typical cost: $0.05-0.15 per company
