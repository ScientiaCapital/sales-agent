# Content Module - GTME Integration

Bridges GTME playbooks from `coperniq-forge` to the sales-agent system.

## Architecture

```
coperniq-forge/05-gtme-motions/     sales-agent/backend/app/
├── sequences/                  →    content/gtme_loader.py
├── prospects/                  →    (parses markdown → structured data)
├── resources/                  →    
└── competitive-intel/          →    services/sequences/engine.py
                                     (consumes structured sequences)
```

## Usage

### Load a Sequence for the Engine

```python
from app.content import get_sequence_for_engine

# Get sequence in engine-ready format
seq_data = get_sequence_for_engine("solar-plus-plus")

# Create in database
sequence = await engine.create_sequence(**seq_data)
```

### List Available Sequences

```python
from app.content import list_available_sequences

sequences = list_available_sequences()
# ['solar_plus_plus', 'frankenstack', 'norrell_construction']
```

### Get Personalization Context

```python
from app.content import get_personalization_context

context = get_personalization_context("norrell-construction")
# {
#   'prospect_intel': '...markdown...',
#   'competitive_context': '...buildops intel...',
#   'market_data': '...industry stats...',
#   'value_add_resource': '...field-to-office-gap content...',
# }
```

### Direct Loader Access

```python
from app.content import GTMEContentLoader

loader = GTMEContentLoader()

# Load specific content
buildops = loader.get_buildops_intel()
norrell = loader.get_norrell_intel()
resource = loader.get_field_to_office_gap()
```

## Content Source

All content lives in:
```
~/Desktop/tk_projects/coperniq-forge/05-gtme-motions/
```

Edit content there, and it's automatically available to agents.

## Sequence Markdown Format

The loader expects sequences in this format:

```markdown
# Sequence Name

## TOUCH 1: Initial Email (Day 0)
**Subject:** Your subject line here

**Body:**
Email body content with {{first_name}} and {{company}} placeholders.

---

## TOUCH 2: Follow-up (Day 3)
...
```

## GTME Note

This architecture separates *content strategy* (human-readable playbooks) from *execution systems* (agent code). 

Benefits:
- Sales/marketing can edit sequences without touching code
- Version control on playbook changes
- Easy A/B testing (duplicate sequence, change copy)
- Content reusable across multiple agent systems
