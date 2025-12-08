# TrifectaPanel Integration Guide

## Component Overview

**File**: `/Users/tmkipper/Desktop/tk_projects/sales-agent/dashboard/src/components/TrifectaPanel.tsx`

The `TrifectaPanel` component displays Trifecta Detection stats for leads with Solar + Generator + Battery combinations (UNICORNS).

## Features

- **Full Trifecta**: Companies with Solar + Generator + Battery (UNICORN leads)
- **Partial Trifecta**: Companies with 2 of 3 products
- **Multi-OEM**: Companies with 3+ brands installed
- **Tier Distribution**: Breakdown by PLATINUM/GOLD/SILVER/BRONZE ICP tiers
- **Progress Bars**: Visual representation with percentage indicators
- **Real-time Updates**: Refreshes every 5 minutes via SWR
- **Error Handling**: Displays fallback UI when API fails

## Usage

### Basic Integration

```tsx
import { TrifectaPanel } from "@/components/TrifectaPanel";

function Dashboard() {
  return (
    <div className="grid gap-4">
      {/* Other dashboard components */}
      <TrifectaPanel />
    </div>
  );
}
```

### Grid Layout Example

```tsx
// Two-column layout
<div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
  <TrifectaPanel />
  <OutreachMetrics />
</div>

// Three-column layout
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
  <TrifectaPanel />
  <LifecycleMetrics />
  <WorkQueue />
</div>
```

### Full-width Layout

```tsx
// Full-width standalone
<div className="space-y-4">
  <TrifectaPanel />
</div>
```

## API Endpoint Required

The component expects a `/api/dashboard/trifecta` endpoint that returns:

```typescript
interface TrifectaResponse {
  metrics: {
    full_trifecta: {
      count: number;
      companies: string[];
      tier_distribution: {
        PLATINUM: number;
        GOLD: number;
        SILVER: number;
        BRONZE: number;
      };
    };
    partial_trifecta: {
      count: number;
      solar_gen: number;
      solar_battery: number;
      gen_battery: number;
    };
    multi_oem: {
      count: number;
      brands_3_plus: number;
      brands_5_plus: number;
      top_brands: Record<string, number>;
    };
    totals: {
      total_companies: number;
      with_solar: number;
      with_generator: number;
      with_battery: number;
      unicorn_count: number;
    };
  };
  summary: string;
  updated_at: string;
}
```

## Styling

The component uses:
- **Tailwind CSS v4** for styling
- **shadcn/ui** components (Card, Progress, Badge, Skeleton)
- **Turkish Blue** (`var(--turkish-blue)`) for primary colors
- **Purple gradient** for unicorn highlights
- **Responsive design** with mobile-friendly layout

## Backend Implementation (FastAPI)

Create the endpoint at `backend/api/routes/dashboard.py`:

```python
@router.get("/trifecta")
async def get_trifecta_metrics():
    """Get Trifecta Detection metrics (Solar + Generator + Battery)."""

    query = """
    WITH trifecta_companies AS (
        SELECT
            company_id,
            company_name,
            icp_tier,
            has_solar,
            has_generator,
            has_battery,
            oem_brands_detected,
            CASE
                WHEN has_solar AND has_generator AND has_battery THEN 'FULL'
                WHEN (has_solar AND has_generator)
                  OR (has_solar AND has_battery)
                  OR (has_generator AND has_battery) THEN 'PARTIAL'
                ELSE 'NONE'
            END as trifecta_status,
            array_length(string_to_array(oem_brands_detected, ','), 1) as brand_count
        FROM dim_companies
        WHERE has_solar = TRUE OR has_generator = TRUE OR has_battery = TRUE
    )
    SELECT
        COUNT(*) FILTER (WHERE trifecta_status = 'FULL') as full_count,
        COUNT(*) FILTER (WHERE trifecta_status = 'PARTIAL') as partial_count,
        COUNT(*) FILTER (WHERE brand_count >= 3) as multi_oem_count,
        COUNT(*) FILTER (WHERE has_solar = TRUE) as solar_count,
        COUNT(*) FILTER (WHERE has_generator = TRUE) as gen_count,
        COUNT(*) FILTER (WHERE has_battery = TRUE) as battery_count,
        -- Tier distribution for full trifecta
        COUNT(*) FILTER (WHERE trifecta_status = 'FULL' AND icp_tier = 'PLATINUM') as platinum_count,
        COUNT(*) FILTER (WHERE trifecta_status = 'FULL' AND icp_tier = 'GOLD') as gold_count,
        COUNT(*) FILTER (WHERE trifecta_status = 'FULL' AND icp_tier = 'SILVER') as silver_count,
        COUNT(*) FILTER (WHERE trifecta_status = 'FULL' AND icp_tier = 'BRONZE') as bronze_count
    FROM trifecta_companies
    """

    result = await db.fetch_one(query)

    return {
        "metrics": {
            "full_trifecta": {
                "count": result["full_count"],
                "tier_distribution": {
                    "PLATINUM": result["platinum_count"],
                    "GOLD": result["gold_count"],
                    "SILVER": result["silver_count"],
                    "BRONZE": result["bronze_count"]
                }
            },
            "partial_trifecta": {
                "count": result["partial_count"]
            },
            "multi_oem": {
                "count": result["multi_oem_count"]
            },
            "totals": {
                "with_solar": result["solar_count"],
                "with_generator": result["gen_count"],
                "with_battery": result["battery_count"],
                "unicorn_count": result["full_count"]
            }
        },
        "summary": f"{result['full_count']} UNICORN leads found with full energy independence systems",
        "updated_at": datetime.now().isoformat()
    }
```

## Visual Design

```
╔════════════════════════════════════════════════════════════════╗
║  ☀️⚡🔋 TRIFECTA HUNTERS                    UNICORN DETECTION  ║
╠════════════════════════════════════════════════════════════════╣
║                                                                ║
║  FULL TRIFECTA (Solar + Gen + Battery)                         ║
║  ████████████████░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  42       ║
║                                                                ║
║  PARTIAL TRIFECTA (2 of 3)                                     ║
║  ████████████████████████████░░░░░░░░░░░░░░░░░░░░░░  187      ║
║                                                                ║
║  MULTI-OEM (3+ brands)                                         ║
║  ████████████████████████████████████████░░░░░░░░░░  409      ║
║                                                                ║
║  🦄 UNICORNS: 42 contractors with FULL TRIFECTA                ║
║     → These are the HIGHEST VALUE targets                      ║
║     PLATINUM: 3 | GOLD: 1 | SILVER: 28 | BRONZE: 10            ║
║                                                                ║
║  Solar: 1,247  |  Generators: 893  |  Batteries: 456          ║
╚════════════════════════════════════════════════════════════════╝
```

## Next Steps

1. **Create Backend Endpoint**: Implement `/api/dashboard/trifecta` in FastAPI
2. **Add to Dashboard**: Import and use `<TrifectaPanel />` in your dashboard layout
3. **Test API**: Verify the endpoint returns correct data structure
4. **Adjust Styling**: Customize colors/layout if needed for your design system

## Dependencies

All required dependencies are already installed:
- `swr` - Data fetching
- `@radix-ui/react-progress` - Progress bar component
- `lucide-react` - Icons
- `tailwindcss` - Styling

## Build Status

✅ Component compiles successfully
✅ TypeScript types validated
✅ All dependencies available
✅ Ready for integration
