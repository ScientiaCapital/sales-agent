# Elite Team - Trifecta Hunter Squad

**Mission**: Dominate emerging verticals through intelligent market signal detection and targeted lead acquisition.

## Squad Members

### 1. Signal Scout Agent (COMPLETE)
**File**: `signal_scout_agent.py`
**Mission**: Detect emerging market opportunities from Close CRM inbound patterns

**Detects**:
- NEW VERTICAL EMERGENCE: 3+ leads from same category in 7 days
- WIN RATE SPIKE: >50% close rate in specific vertical
- GEOGRAPHIC CLUSTER: 5+ leads from same state/region
- TRIFECTA SIGNAL: Companies with 2+ MEP services (HVAC + Solar + Battery)

**Outputs**:
- `VerticalSignal`: Market pattern with confidence score
- `ScrapingOrder`: Actionable mission for Deep Hunter

**Scheduled**: Hourly at :15 via Celery Beat

**Usage**:
```python
from app.services.langgraph.agents.elite_team import SignalScoutAgent

scout = SignalScoutAgent()
result = await scout.scan(lookback_days=7)

print(f"Detected {result.signals_detected} signals")
for order in result.scraping_orders:
    print(f"ORDER: {order.vertical} - {order.priority}")
```

### 2. Deep Hunter Agent (PLANNED)
**File**: `deep_hunter_agent.py` (TODO)
**Mission**: Execute targeted scraping missions from Signal Scout orders

**Executes**:
- Vertical-specific searches (Google, Yelp, industry directories)
- State-focused scraping based on geographic clusters
- OEM-filtered searches (e.g., "Generac generator dealer Florida")
- High-quality contact extraction (ATL + BTL)

**Outputs**:
- Enriched company records ready for Package Forge
- Quality metrics per scraping mission

**Scheduled**: Triggered by Signal Scout orders

### 3. Package Forge Agent (PLANNED)
**File**: `package_forge_agent.py` (TODO)
**Mission**: Transform raw scraper data into Close-ready lead packages

**Transforms**:
- Raw scraper JSON → Close CRM import CSV
- Deduplication against existing pipeline
- ICP scoring and prioritization
- Vertical-specific enrichment (brands, service areas, etc.)

**Outputs**:
- `CLOSE_CRM_IMPORT_*.csv` ready for manual review
- Quality report (% with phones, emails, ATL contacts)

**Scheduled**: Runs after Deep Hunter completes

## Vertical Coverage

### Supported Verticals
| Vertical | Patterns | OEM Brands | Priority |
|----------|----------|------------|----------|
| **Fire Safety** | 5 patterns | Honeywell, Tyco, Simplex, Notifier, Edwards | HIGH |
| **Low Voltage** | 7 patterns | Honeywell, Bosch, Hikvision, Axis, Avigilon | HIGH |
| **Trifecta** | 6 patterns | Tesla Powerwall, Generac PWRcell, Enphase IQ | CRITICAL |
| **Commercial HVAC** | 6 patterns | Carrier, Trane, Daikin VRV, Mitsubishi, York | MEDIUM |
| **Solar** | 5 patterns | Enphase, SolarEdge, SMA, Fronius, Tesla | MEDIUM |
| **Generator** | 5 patterns | Generac, Kohler, Cummins, Caterpillar | MEDIUM |
| **Electrical** | 5 patterns | N/A (general contractors) | LOW |
| **Plumbing** | 5 patterns | N/A (general contractors) | LOW |

### Pattern Examples

**Fire Safety**:
- "ABC Fire Protection Services"
- "Life Safety Systems Inc"
- "Fire Sprinkler Installation"

**Low Voltage**:
- "Low Voltage Security Systems"
- "Access Control Specialists"
- "Camera & Surveillance Installation"

**Trifecta** (GOLD):
- "Solar + Generator + Battery Solutions"
- "Energy Storage & Backup Power"
- "Microgrid Resilience Systems"

**Commercial HVAC**:
- "VRF HVAC Systems"
- "Commercial Chiller Service"
- "Rooftop Unit Installation"

## Signal Types

### 1. NEW_VERTICAL
**Criteria**: 3+ leads from previously untapped vertical in 7 days
**Action**: Create MEDIUM priority scraping order
**Example**: First 3 fire safety leads ever → scrape 100 more

### 2. WIN_SPIKE
**Criteria**: >50% close rate in specific vertical
**Action**: Create HIGH priority scraping order
**Example**: 5 low voltage leads, 3 won → scrape 200 more

### 3. GEO_CLUSTER
**Criteria**: 5+ leads from same state/region
**Action**: Focus scraping on that geography
**Example**: 7 Florida solar leads → scrape FL only

### 4. TRIFECTA
**Criteria**: Company offers 2+ services (HVAC + Solar + Battery)
**Action**: Create CRITICAL priority order
**Example**: Find companies doing solar + generator installs

## Scraping Order Priority

### HIGH (75%+ confidence)
- Target: 200 leads
- States: Top 5 geographic clusters
- OEMs: All brands in vertical
- Execution: Within 24 hours

### MEDIUM (60-75% confidence)
- Target: 100 leads
- States: Top 3 states
- OEMs: Top 5 brands
- Execution: Within 48 hours

### LOW (50-60% confidence)
- Target: 50 leads
- States: Top 2 states
- OEMs: Top 3 brands
- Execution: Next sprint

## Data Flow

```
┌─────────────────┐
│   Close CRM     │ ◄─── Inbound leads (webhooks + polling)
│  (Inbound 7d)   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SIGNAL SCOUT    │ ─── Detect patterns, classify verticals
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Scraping Orders │ ─── Priority queue (Supabase table)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  DEEP HUNTER    │ ─── Execute scraping missions
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  PACKAGE FORGE  │ ─── Transform to Close-ready format
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Tim's Review    │ ─── Manual import approval
└─────────────────┘
```

## Database Schema (Supabase)

### `dim_scraping_orders`
```sql
CREATE TABLE dim_scraping_orders (
    order_id TEXT PRIMARY KEY,
    vertical TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    priority TEXT NOT NULL, -- HIGH, MEDIUM, LOW
    target_count INT NOT NULL,
    states JSONB,
    oems JSONB,
    reasoning TEXT,
    status TEXT DEFAULT 'PENDING', -- PENDING, IN_PROGRESS, COMPLETE, FAILED
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    leads_found INT DEFAULT 0,
    metadata JSONB
);
```

### `dim_vertical_signals`
```sql
CREATE TABLE dim_vertical_signals (
    signal_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    vertical TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    lead_count INT NOT NULL,
    confidence FLOAT NOT NULL,
    sample_companies JSONB,
    states JSONB,
    win_rate FLOAT,
    recommended_action TEXT,
    detected_at TIMESTAMPTZ DEFAULT NOW(),
    actioned BOOLEAN DEFAULT FALSE,
    metadata JSONB
);
```

## API Endpoints

### Manual Trigger
```bash
POST /api/v1/elite-team/signal-scout/scan
{
    "lookback_days": 7,
    "min_lead_threshold": 3
}
```

**Response**:
```json
{
    "scan_timestamp": "2025-12-08T12:00:00Z",
    "total_inbound_leads": 42,
    "signals_detected": 3,
    "signals": [...],
    "scraping_orders": [
        {
            "order_id": "SO-20251208120000-fire_safety",
            "vertical": "fire_safety",
            "priority": "HIGH",
            "target_count": 200,
            "states": ["CA", "TX", "FL"],
            "reasoning": "Strong inbound signal with 5 leads in 7 days"
        }
    ],
    "duration_ms": 3500,
    "next_scan_at": "2025-12-08T13:00:00Z"
}
```

### Get Active Orders
```bash
GET /api/v1/elite-team/scraping-orders?status=PENDING
```

### Execute Scraping Order (Deep Hunter)
```bash
POST /api/v1/elite-team/deep-hunter/execute
{
    "order_id": "SO-20251208120000-fire_safety"
}
```

## Celery Tasks

### Signal Scout (Hourly)
```python
@celery_app.task(name="elite_team.signal_scout")
def run_signal_scout():
    """Run hourly at :15 (e.g., 10:15, 11:15, 12:15)"""
    scout = SignalScoutAgent()
    result = await scout.scan(lookback_days=7)
    return {
        "signals_detected": result.signals_detected,
        "orders_created": len(result.scraping_orders)
    }
```

### Deep Hunter (Triggered)
```python
@celery_app.task(name="elite_team.deep_hunter")
def run_deep_hunter(order_id: str):
    """Execute when Signal Scout creates order"""
    hunter = DeepHunterAgent()
    result = await hunter.execute(order_id)
    return {
        "leads_found": result.leads_found,
        "quality_score": result.quality_score
    }
```

### Package Forge (Chained)
```python
@celery_app.task(name="elite_team.package_forge")
def run_package_forge(hunter_result):
    """Chain after Deep Hunter completes"""
    forge = PackageForgeAgent()
    result = await forge.package(hunter_result)
    return {
        "close_import_file": result.csv_path,
        "lead_count": result.lead_count
    }
```

## Testing

### Unit Tests
```bash
cd backend
python3 test_signal_scout_basic.py
```

### Integration Test (Requires API Keys)
```bash
cd backend
source ../venv/bin/activate
python -c "
import asyncio
from app.services.langgraph.agents.elite_team import SignalScoutAgent

async def test():
    scout = SignalScoutAgent()
    result = await scout.scan()
    print(f'Signals: {result.signals_detected}')
    print(f'Orders: {len(result.scraping_orders)}')

asyncio.run(test())
"
```

## Performance Metrics

### Signal Scout
- **Latency**: <5 seconds per scan
- **Throughput**: 100+ leads/scan
- **Cost**: $0.0003 per scan (Cerebras)

### Deep Hunter (Estimated)
- **Latency**: 5-10 minutes per 100 leads
- **Throughput**: 100-200 leads/hour
- **Cost**: Browserbase usage (~$0.50/hour)

### Package Forge (Estimated)
- **Latency**: <1 minute per 100 leads
- **Throughput**: 1000+ leads/hour
- **Cost**: Minimal (ICP scoring only)

## Next Steps

1. **Week 1**: Complete Signal Scout (DONE)
2. **Week 2**: Build Deep Hunter agent
3. **Week 3**: Build Package Forge agent
4. **Week 4**: End-to-end testing + production deployment

## Philosophy

**Quality Over Quantity**
- Only pursue high-confidence signals (>50%)
- Focus on verticals with proven win rates
- Geographic clustering = easier sales process

**Speed to Market**
- Hourly scans detect opportunities within 60 minutes
- Auto-execute scraping orders (no manual approval)
- Same-day lead delivery to Tim's pipeline

**Vertical Domination**
- Once we find a winner, go ALL IN
- Scrape every company in that vertical + state
- Build category expertise (OEMs, pain points, buyers)

**Trifecta is King**
- Multi-service companies = 3x revenue potential
- Higher ACV, longer contracts, stickier relationships
- Priority #1 for all squad members
