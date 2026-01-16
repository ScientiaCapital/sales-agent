# Deep Hunter Agent - Quick Start

## 🎯 What It Does
Orchestrates 30 OEM scrapers to find contractors, identifies multi-OEM targets (high-value), and exports for Supabase import.

## 🚀 Quick Test
```bash
cd backend
source ../venv/bin/activate
python test_deep_hunter.py
```

## 💻 Basic Usage
```python
from app.services.langgraph.agents.elite_team import DeepHunterAgent, ScrapingOrder

# Create agent
hunter = DeepHunterAgent()

# Create order
order = ScrapingOrder(
    vertical="solar",      # fire_safety, low_voltage, generator, solar, battery, ev_charger, hvac
    states=["FL", "TX"],   # State codes
    limit_per_oem=100
)

# Execute hunt
result = await hunter.hunt(order)
print(f"Found {result.total_scraped} contractors, {result.multi_oem_count} multi-OEM")
```

## 📊 What You Get
- **Total contractors**: All matching contractors from pipeline.db
- **Multi-OEM contractors**: High-value targets in 2+ dealer networks
- **CSV export**: Ready for Intake Commander
- **Top 20 analysis**: DeepSeek AI recommendations (if API key configured)

## 🗂️ OEM Coverage (32 total)
- **Fire Safety**: Honeywell, Siemens, Johnson Controls
- **Low Voltage**: Honeywell, Alarm.com, Control4
- **Generator**: Generac, Kohler, Cummins
- **Solar**: Enphase, SolarEdge, Tesla, Fronius, SMA, Sungrow, Growatt
- **Battery**: Tesla, Generac, Enphase, SimpliPhi
- **EV Charger**: ABB, Delta, Schneider
- **HVAC**: Carrier, Trane, Lennox, York, Mitsubishi, Rheem, etc.

## 📁 Output Location
`/backend/data/deep_hunter_exports/deep_hunter_{vertical}_{states}_{timestamp}.csv`

## 🔑 Required Files
- `dealer-scraper-mvp/output/pipeline.db` (SQLite database)

## ⚙️ Optional Config
```bash
# For multi-OEM analysis (optional)
export ANTHROPIC_API_KEY=your_deepseek_key
```

## 📈 Performance
- 5,000 contractors queried in ~500ms
- Multi-OEM matching in ~3ms
- Full hunt: ~12 seconds

## 🔗 Integration
**Input**: ScrapingOrder from Signal Scout Agent  
**Output**: CSV for Intake Commander Agent  
**Data Source**: dealer-scraper-mvp/output/pipeline.db

## ✅ Status
Phase 1 Complete - Ready for Elite Squad integration
