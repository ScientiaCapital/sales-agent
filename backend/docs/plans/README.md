# Plans Directory

This is the canonical location for all project plans.

## Structure

- `design/` - Design documents and architecture plans
- `execution/` - Execution summaries and pipeline documentation  
- `data/` - Data inventories and master lists

## Adding New Plans

- **Design plans**: Place in `design/` with date prefix (YYYY-MM-DD)
- **Execution summaries**: Place in `execution/` with descriptive name
- **Data inventories**: Place in `data/` with descriptive name

## Naming Convention

- Design: `YYYY-MM-DD-description-design.md`
- Implementation: `YYYY-MM-DD-description-implementation.md`
- Execution: `description-execution-summary.md` or `YYYYMMDD-description.md`
- Data: `DESCRIPTION_INVENTORY.md` or `MASTER_DESCRIPTION.md`

## Current Plans

### Design Documents (`design/`)
- Architecture and system design documents
- Implementation plans with detailed task breakdowns
- Integration design specifications

### Execution Summaries (`execution/`)
- Pipeline execution results and summaries
- Validation and production readiness reports
- Pipeline documentation and guides

### Data Inventories (`data/`)
- Master data inventories
- Data source catalogs
- Data quality reports

## Guidelines

1. **Always use this directory** - Do not create plans in other locations
2. **Use descriptive names** - Include dates and clear descriptions
3. **Organize by type** - Place files in the appropriate subfolder
4. **Update references** - When moving files, update all references in documentation
5. **Archive old plans** - Move completed/outdated plans to `archive/` subfolder if needed

## Prevention

To prevent plans from being created in wrong locations:

- This directory (`backend/docs/plans/`) is tracked in git
- All plans should be placed here with proper categorization
- Reference this README when creating new plans

