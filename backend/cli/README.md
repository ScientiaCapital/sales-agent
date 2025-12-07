# CLI Module - Drop-In Enrichment

Terminal-based enrichment command for the sales-agent platform with automatic Close CRM deduplication.

## Installation

Install Typer (if not already installed):

```bash
cd backend
source ../venv/bin/activate
pip install typer==0.15.1
```

## Usage

### Basic Enrichment

```bash
# Enrich by URL
python -m cli.enrich "https://acme-hvac.com"

# Enrich by company name
python -m cli.enrich "Acme HVAC" --type name

# Enrich by Close lead ID
python -m cli.enrich "lead_abc123" --type close_id

# Enrich person + company
python -m cli.enrich "John Smith, Acme HVAC" --type person
```

### With Outreach Staging

```bash
# Stage email only
python -m cli.enrich "https://acme-hvac.com" --stage email

# Stage email + SMS
python -m cli.enrich "https://acme-hvac.com" --stage email,sms

# Stage all channels
python -m cli.enrich "https://acme-hvac.com" --stage all

# Auto-trigger (skip approval)
python -m cli.enrich "https://acme-hvac.com" --stage email --auto-trigger
```

### Help

```bash
python -m cli.enrich --help
python -m cli.enrich version
```

## Input Types

| Type | Detection | Example |
|------|-----------|---------|
| **URL** | Starts with http/https | `https://acme-hvac.com` |
| **LinkedIn** | Contains linkedin.com | `https://linkedin.com/company/acme` |
| **Close ID** | Starts with `lead_` | `lead_abc123` |
| **Person** | Contains `,` or ` at ` | `John Smith, Acme HVAC` |
| **Name** | Default fallback | `Acme HVAC` |

Auto-detection is enabled by default (`--type auto`).

## Dedup-First Pipeline

Every enrichment command follows this flow:

```
Input → Parse → CHECK CLOSE CRM FIRST → Duplicate? → Return existing lead
                                        ↓
                                       New? → Enrich → Display results → Stage outreach
```

Close CRM deduplication checks:
1. Domain match (exact)
2. Company name match (fuzzy, 85% threshold)

## Outreach Channels

| Channel | Description |
|---------|-------------|
| `email` | Email draft (goes to Slack approval) |
| `sms` | SMS draft (goes to Slack approval) |
| `linkedin` | LinkedIn connection request |
| `call` | Creates call task (human calls) |
| `all` | All channels |

## Staging Modes

| Mode | Flag | Behavior |
|------|------|----------|
| **DRAFT** | (default) | Create draft, wait for approval |
| **AUTO_APPROVE** | `--auto-trigger` | Send immediately (use with caution) |

## Architecture

```
cli/
├── __init__.py           # Package init
├── __main__.py           # Entry point (python -m cli.enrich)
├── enrich.py             # Main enrich command + Typer app
├── staging.py            # Outreach staging models
├── formatters.py         # Pretty terminal output (Rich)
└── README.md             # This file
```

## Development

### Adding New Input Types

1. Add enum to `InputType` in `enrich.py`
2. Update `detect_input_type()` with detection logic
3. Update `parse_input()` to extract fields
4. Update documentation

### Adding New Channels

1. Add enum to `OutreachChannel` in `staging.py`
2. Update `parse_channels()` to handle new channel
3. Update `stage_outreach()` in `enrich.py`

## Integration Points

- **Close CRM Deduplication**: `app.services.crm.close_deduplication.CloseDeduplicationService`
- **ScoutAgent** (TODO): Website scraping + contact discovery
- **RankingAgent** (TODO): ICP scoring + tier assignment
- **OutreachAgent** (TODO): Draft generation for channels

## Examples

### Simple URL Enrichment

```bash
$ python -m cli.enrich "https://acme-hvac.com"

🔍 Checking Close CRM for duplicates...
✅ Not a duplicate. Starting enrichment...
  → Fetching company data from Supabase...
  → Scraping website for contacts...
  → Discovering ATL contacts via Apollo...
  → Calculating ICP score...
  → Assigning quality tier...

✅ Enrichment Complete: Acme HVAC

┌─ Company Information ────────────────┐
│ Domain       │ acme-hvac.com         │
│ ICP Score    │ 75/100                │
│ ICP Tier     │ GOLD                  │
│ Quality Tier │ WARM                  │
└──────────────────────────────────────┘

✅ Enrichment complete!
```

### Duplicate Detection

```bash
$ python -m cli.enrich "Acme HVAC"

🔍 Checking Close CRM for duplicates...

┌─ Duplicate Detected ──────────────────┐
│ ⚠️  Lead Already Exists               │
│                                        │
│ Company: Acme HVAC Inc                │
│ Match Confidence: 92.3%               │
│ Lead ID: lead_abc123                  │
│ Close URL: https://app.close.com/...  │
└────────────────────────────────────────┘
```

### With Outreach Staging

```bash
$ python -m cli.enrich "https://acme.com" --stage email,sms

🔍 Checking Close CRM for duplicates...
✅ Not a duplicate. Starting enrichment...
[... enrichment output ...]

📝 Staging outreach for channels: email, sms

┌─ Staging Complete ────────────────────┐
│ ✅ Outreach Staged Successfully       │
│                                        │
│ Drafts created: 2                     │
│ Status: Awaiting approval in Slack    │
└────────────────────────────────────────┘
```

## Testing

```bash
# Test help
python -m cli.enrich --help

# Test version
python -m cli.enrich version

# Test with mock data (no real API calls yet)
python -m cli.enrich "https://test-company.com" --verbose
```

## Next Steps (TODOs)

1. Wire up ScoutAgent for actual enrichment
2. Connect to Supabase for lead storage
3. Implement OutreachAgent staging logic
4. Add error handling for network issues
5. Add progress bars for long-running operations
6. Add `--dry-run` flag for testing
7. Add `--output json` flag for programmatic use
