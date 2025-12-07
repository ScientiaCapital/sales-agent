# CLI Quick Reference Card

## Installation

```bash
cd backend && source ../venv/bin/activate
pip install typer==0.15.1
```

## Basic Commands

```bash
# URL enrichment
python -m cli.enrich "https://acme-hvac.com"

# Company name
python -m cli.enrich "Acme HVAC"

# Close lead ID
python -m cli.enrich "lead_abc123"

# Person + company
python -m cli.enrich "John Smith, Acme HVAC"
```

## With Staging

```bash
# Email only
python -m cli.enrich "https://acme.com" --stage email

# Multiple channels
python -m cli.enrich "https://acme.com" --stage email,sms,linkedin

# All channels
python -m cli.enrich "https://acme.com" --stage all

# Auto-send (skip approval)
python -m cli.enrich "https://acme.com" --stage email --auto-trigger
```

## Help

```bash
python -m cli.enrich --help
python -m cli.enrich version
```

## Input Types

| Type | Example |
|------|---------|
| URL | `https://acme-hvac.com` |
| LinkedIn | `https://linkedin.com/company/acme` |
| Close ID | `lead_abc123` |
| Person | `John Smith, Acme HVAC` |
| Name | `Acme HVAC` |

## Channels

| Channel | Description |
|---------|-------------|
| `email` | Email draft (Slack approval) |
| `sms` | SMS draft (Slack approval) |
| `linkedin` | LinkedIn connection request |
| `call` | Call task (human calls) |
| `all` | All channels |

## Testing

```bash
# Run validation tests
python cli/test_cli.py
```

## Environment Variables Required

```bash
CLOSE_API_KEY=api_...  # For Close CRM dedup check
```

## Dedup-First Flow

```
Input → Parse → CHECK CLOSE CRM → Duplicate? → Return existing
                                  ↓
                                 New? → Enrich → Display → Stage
```

## Status Indicators

- 🔍 Checking
- ✅ Success
- ❌ Error
- ⚠️ Warning
- 📝 Staging
