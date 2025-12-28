# Supabase Configuration

This directory contains Supabase-related configurations and migrations.

## Migrations

Database migrations are managed via SQL files in the `migrations/` subdirectory.

## Migration Naming Convention

- Format: `YYYYMMDD_description.sql`
- Example: `20251224_data_integrity_fixes.sql`

## Applying Migrations

Migrations are applied manually via Supabase dashboard or CLI:

```bash
supabase db push
```

## Key Tables

- `dim_companies` - Master lead/company records
- `dim_contacts` - Contact information linked to companies
- `fact_opportunities` - Sales opportunities/deals
